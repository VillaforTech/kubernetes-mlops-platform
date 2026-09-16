"""Full platform components: pipelines, serverless serving, ingress and access."""

import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

import yaml

from . import cli

VERSIONS = json.loads((cli.ROOT / "platform/versions.json").read_text())


def helm(release, chart, namespace, version, values=()):
    if not shutil.which("helm"):
        raise RuntimeError("Helm is required for the full platform.")
    args = [
        "helm",
        "upgrade",
        "--install",
        release,
        chart,
        "--version",
        version,
        "--kubeconfig",
        str(cli.LOCAL / "kubeconfig"),
        "--kube-context",
        f"kind-{cli.CLUSTER}",
        "--namespace",
        namespace,
        "--create-namespace",
        "--wait",
        "--timeout",
        "300s",
    ]
    if chart in {"base", "istiod", "gateway"}:
        args += ["--repo", "https://istio-release.storage.googleapis.com/charts"]
    for value in values:
        args += ["--set", value]
    cli.command(args, timeout=330)


def apply_url(url):
    # Download YAML only; no remote code is executed.
    with urllib.request.urlopen(url, timeout=60) as response:
        contents = response.read().decode()
    cli.kubectl(
        "apply",
        "--server-side",
        "--field-manager=mlops-full",
        "-f",
        "-",
        payload=contents,
        timeout=180,
        namespace=None,
    )


def wait(namespace, resource, condition="Available", timeout=240):
    cli.kubectl(
        "-n",
        namespace,
        "wait",
        "--for=condition=" + condition,
        resource,
        f"--timeout={timeout}s",
        timeout=timeout + 10,
    )


def install():
    cli.verify_owner()
    print(
        "Installing full platform: Kubeflow Pipelines, serverless KServe, ingress and RBAC.",
        flush=True,
    )
    root = "https://github.com/kubeflow/pipelines/manifests/kustomize/cluster-scoped-resources"
    cli.kubectl(
        "apply",
        "--server-side",
        "-k",
        root + "?ref=" + VERSIONS["kfp_commit"] + "&timeout=120s",
        timeout=240,
        namespace=None,
    )
    wait("kubeflow", "crd/workflows.argoproj.io", "Established")
    cli.kubectl("apply", "--server-side", "-k", "platform/pipelines", timeout=240, namespace=None)
    for deployment in ["ml-pipeline", "ml-pipeline-ui", "workflow-controller"]:
        wait("kubeflow", "deployment/" + deployment)
    print("Kubeflow control plane available.", flush=True)

    helm(
        "cert-manager",
        "oci://quay.io/jetstack/charts/cert-manager",
        "cert-manager",
        VERSIONS["cert_manager"],
        ["crds.enabled=true"],
    )
    helm("istio-base", "base", "istio-system", VERSIONS["istio"], [])
    helm("istiod", "istiod", "istio-system", VERSIONS["istio"], [])
    helm(
        "istio-ingressgateway",
        "gateway",
        "istio-system",
        VERSIONS["istio"],
        ["service.type=ClusterIP"],
    )
    serving = "https://github.com/knative/serving/releases/download/" + VERSIONS["knative"] + "/"
    apply_url(serving + "serving-crds.yaml")
    wait("knative-serving", "crd/services.serving.knative.dev", "Established")
    apply_url(serving + "serving-core.yaml")
    apply_url(
        "https://github.com/knative/net-istio/releases/download/"
        + VERSIONS["knative"]
        + "/net-istio.yaml"
    )
    wait("knative-serving", "deployment/controller")
    wait("knative-serving", "deployment/webhook")
    wait("knative-serving", "deployment/net-istio-controller")
    helm("kserve-crd", "oci://ghcr.io/kserve/charts/kserve-crd", "kserve", VERSIONS["kserve"])
    helm(
        "kserve-resources",
        "oci://ghcr.io/kserve/charts/kserve-resources",
        "kserve",
        VERSIONS["kserve"],
        ["kserve.controller.deploymentMode=Knative"],
    )
    helm(
        "nginx",
        "oci://ghcr.io/nginx/charts/nginx-ingress",
        "nginx-ingress",
        "2.7.3",
        ["controller.service.type=ClusterIP"],
    )
    cli.kubectl("apply", "-f", "platform/access", namespace=None)
    cli.kubectl("apply", "-f", "platform/ingress", namespace=None)
    data = cli.state()
    data["full_installed"] = True
    cli.private_json(cli.LOCAL / "state.json", data)
    print("Full control plane installed. Run mlops pipeline and mlops serve to exercise it.")


def serve():
    cli.verify_owner()
    data = cli.state()
    if not data.get("full_installed") or not data.get("run_id"):
        raise RuntimeError("Run mlops full and mlops demo or mlops pipeline first.")
    obj = yaml.safe_load((cli.ROOT / "platform/serving/iris.yaml").read_text())
    container = obj["spec"]["predictor"]["containers"][0]
    container["image"] = data["image"]
    container["env"].append({"name": "MODEL_RUN_ID", "value": data["run_id"]})
    cli.kubectl("apply", "-f", "-", payload=yaml.safe_dump(obj))
    wait("mlops", "inferenceservice/iris", "Ready", 300)
    print("KServe InferenceService iris is ready.")


def pipeline():
    import secrets
    import tempfile

    import kfp
    from mlflow import MlflowClient

    from .pipeline import compile_pipeline

    cli.verify_owner()
    data = cli.state()
    if not data.get("full_installed"):
        raise RuntimeError("Run mlops full first.")
    execution = secrets.token_hex(12)
    with tempfile.TemporaryDirectory() as folder:
        package = Path(folder) / "pipeline.yaml"
        compile_pipeline(data["image"], package)
        with cli.forward("ml-pipeline", 8888, "kubeflow") as base:
            client = kfp.Client(host=base)
            result = client.create_run_from_pipeline_package(
                str(package),
                arguments={"execution": execution},
                experiment_name="platform-demo",
                run_name="iris-" + execution[:8],
                enable_caching=False,
            )
            completed = result.wait_for_run_completion(timeout=600)
            if completed.state != "SUCCEEDED":
                raise RuntimeError("Kubeflow pipeline did not succeed; no serving version changed.")
            data["pipeline_run_id"] = result.run_id
    with cli.forward("mlflow", 5000) as base:
        client = MlflowClient(tracking_uri=base)
        experiment = client.get_experiment_by_name("iris-platform-demo")
        runs = client.search_runs(
            [experiment.experiment_id], f"tags.pipeline_execution = '{execution}'"
        )
        if len(runs) != 1:
            raise RuntimeError("Could not uniquely resolve the pipeline's MLflow run.")
        run = runs[0]
        with tempfile.TemporaryDirectory() as directory:
            path = client.download_artifacts(
                run.info.run_id, "model/manifest.json", dst_path=directory
            )
            manifest = json.loads(Path(path).read_text())
        data.update(
            {
                "run_id": run.info.run_id,
                "metrics": run.data.metrics,
                "dataset_sha256": manifest["dataset_sha256"],
                "training_job": "kubeflow-pipeline",
            }
        )
    cli.promote(data["run_id"])
    cli.private_json(cli.LOCAL / "state.json", data)
    cli.smoke()
    print("Kubeflow pipeline passed its quality gate and the selected run is serving.")


def monitor():
    from .monitoring import publish

    cli.verify_owner()
    with cli.forward("evidently", 8000) as base:
        result = publish(base)
    cli.private_json(cli.LOCAL / "evidence/monitoring.json", result)
    print("Evidently drift snapshot stored; evidence: .local/evidence/monitoring.json")


def verify():
    import urllib.parse
    import urllib.request

    cli.verify_owner()
    data = cli.state()
    if not data.get("pipeline_run_id"):
        raise RuntimeError("A successful Kubeflow run is required. Run mlops pipeline.")
    cli.smoke()
    obj = json.loads(cli.kubectl("get", "inferenceservice", "iris", "-o", "json"))
    host = urllib.parse.urlsplit(obj["status"]["url"]).hostname
    with cli.forward("istio-ingressgateway", 80, "istio-system") as base:
        request = urllib.request.Request(
            base + "/v1/models/iris:predict",
            data=json.dumps({"instances": [[5.1, 3.5, 1.4, 0.2]]}).encode(),
            headers={"Host": host, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.load(response)
        if result["run_id"] != data["run_id"]:
            raise RuntimeError("KServe is serving the wrong model run.")
    monitor()
    for verb, resource, expected in [
        ("get", "pods", "yes"),
        ("get", "secrets", "no"),
        ("delete", "deployments", "no"),
    ]:
        # kubectl auth can-i returns 1 for an expected denial.
        args = [
            "kubectl",
            "--kubeconfig",
            str(cli.LOCAL / "kubeconfig"),
            "--context",
            f"kind-{cli.CLUSTER}",
            "-n",
            "mlops",
            "auth",
            "can-i",
            verb,
            resource,
            "--as=portfolio-observer",
            "--as-group=mlops-observers",
        ]
        answer = subprocess.run(args, capture_output=True, text=True, timeout=20)
        if answer.stdout.strip() != expected:
            raise RuntimeError("RBAC verification failed.")
    cli.private_json(
        cli.LOCAL / "evidence/full.json",
        {
            "pipeline_run_id": data["pipeline_run_id"],
            "run_id": data["run_id"],
            "checks": [
                "kubeflow-pipeline",
                "kserve-inference",
                "evidently-snapshot",
                "rbac-allow-deny",
            ],
            "versions": VERSIONS,
        },
    )
    print("PASS: Kubeflow, KServe, Evidently, and RBAC. Evidence: .local/evidence/full.json")
