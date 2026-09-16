"""Project-scoped cluster lifecycle and end-to-end verification."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / ".local"
CLUSTER = "mlops-platform"
NAMESPACE = "mlops"
APP_IMAGE = "mlops-platform:dev"

# Local clients reach artifacts through tracking; MinIO remains cluster-internal.
os.environ["MLFLOW_ENABLE_PROXY_MULTIPART_DOWNLOAD"] = "false"
os.environ["MLFLOW_ENABLE_PROXY_MULTIPART_UPLOAD"] = "false"
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")


def command(args, *, payload=None, timeout=600, stream=False):
    result = subprocess.run(
        args, input=payload, text=True, cwd=ROOT, timeout=timeout, capture_output=not stream
    )
    if result.returncode:
        # Keep diagnostic context local and redact generated credentials.
        diagnostic = result.stderr or "Process failed; inspect the preceding output."
        credentials_path = LOCAL / "credentials.json"
        if credentials_path.exists():
            for value in json.loads(credentials_path.read_text()).values():
                diagnostic = diagnostic.replace(value, "[REDACTED]")
        private_json(LOCAL / "last-command-error.json", {"tool": args[0], "detail": diagnostic})
        raise RuntimeError(
            f"{args[0]} {args[1]} failed (exit {result.returncode}). See .local/last-command-error.json and mlops status."
        )
    return result.stdout or ""


def kubectl(*args, payload=None, timeout=120, namespace=NAMESPACE):
    command_args = [
        "kubectl",
        "--kubeconfig",
        str(LOCAL / "kubeconfig"),
        "--context",
        f"kind-{CLUSTER}",
    ]
    if namespace is not None:
        command_args += ["--namespace", namespace]
    return command(command_args + list(args), payload=payload, timeout=timeout)


def private_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_suffix(".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def state():
    path = LOCAL / "state.json"
    if not path.exists():
        raise RuntimeError("No managed cluster state. Run mlops up first.")
    return json.loads(path.read_text())


def credentials():
    path = LOCAL / "credentials.json"
    if not path.exists():
        private_json(
            path,
            {
                key: secrets.token_hex(24)
                for key in ["POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD", "GRAFANA_ADMIN_PASSWORD"]
            },
        )
    if path.stat().st_mode & 0o077:
        raise RuntimeError("Credentials must be owner-only (chmod 600 .local/credentials.json).")
    data = json.loads(path.read_text())
    if set(data) != {"POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD", "GRAFANA_ADMIN_PASSWORD"}:
        raise RuntimeError(
            "Invalid local credential schema; do not regenerate against existing volumes."
        )
    if any(
        len(value) != 48 or any(c not in "0123456789abcdef" for c in value)
        for value in data.values()
    ):
        raise RuntimeError("Unexpected credential format.")
    return data


def verify_owner():
    owner = state()["owner"]
    nodes = json.loads(kubectl("get", "nodes", "-o", "json"))["items"]
    if not nodes or any(
        node["metadata"].get("labels", {}).get("portfolio.mlops/owner") != owner for node in nodes
    ):
        raise RuntimeError("Cluster ownership check failed; no changes made.")


def image_tag():
    digest = hashlib.sha256()
    files = [ROOT / "Dockerfile", ROOT / "requirements.lock", ROOT / "pyproject.toml"]
    files += sorted((ROOT / "src").rglob("*.py"))
    for path in files:
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return "dev.local/mlops-platform:" + digest.hexdigest()[:16]


def source_revision():
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "uncommitted"


def doctor():
    for executable in ["docker", "kind", "kubectl"]:
        if not shutil.which(executable):
            raise RuntimeError(f"Missing prerequisite: {executable}")
    info = json.loads(command(["docker", "info", "--format", "{{json .}}"], timeout=20))
    print(f"Docker: {info['NCPU']} CPUs; {info['MemTotal'] / 1024**3:.1f} GiB available to engine")
    if info["MemTotal"] < 6 * 1024**3:
        raise RuntimeError("Allocate at least 6 GiB to Docker for the complete demo.")
    print("Tools available. No cloud account or public ingress required.")


def cluster_config(owner, workers=0):
    config = yaml.safe_load((ROOT / "infra/kind.yaml").read_text())
    image = config["nodes"][0]["image"]
    config["nodes"] += [{"role": "worker", "image": image} for _ in range(workers)]
    for node in config["nodes"]:
        node["labels"] = {"portfolio.mlops/owner": owner}
    return config


def up(workers=0):
    doctor()
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    existing = command(["kind", "get", "clusters"]).splitlines()
    if CLUSTER in existing:
        verify_owner()
    else:
        owner = secrets.token_hex(8)
        private_json(LOCAL / "state.json", {"owner": owner})
        config = cluster_config(owner, workers)
        (LOCAL / "kind.yaml").write_text(yaml.safe_dump(config))
        command(
            [
                "kind",
                "create",
                "cluster",
                "--name",
                CLUSTER,
                "--config",
                str(LOCAL / "kind.yaml"),
                "--kubeconfig",
                str(LOCAL / "kubeconfig"),
                "--wait",
                "120s",
            ],
            stream=True,
        )
        (LOCAL / "kubeconfig").chmod(0o600)
        verify_owner()
    data = state()
    image = image_tag()
    print(f"Building {image}", flush=True)
    command(["docker", "build", "--tag", image, "."], stream=True, timeout=1200)
    command(["kind", "load", "docker-image", "--name", CLUSTER, image], stream=True)
    data["image"] = image
    data["source_revision"] = source_revision()
    private_json(LOCAL / "state.json", data)
    deploy()


def render(image=APP_IMAGE):
    objects = list(yaml.safe_load_all(command(["kubectl", "kustomize", "k8s"])))
    for obj in objects:
        containers = obj.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        for container in containers:
            if container.get("image") == APP_IMAGE:
                container["image"] = image
    return objects


def deploy():
    verify_owner()
    data = state()
    kubectl("apply", "-f", "k8s/namespace.yaml")
    if (
        not (LOCAL / "credentials.json").exists()
        and kubectl("get", "secret", "platform-secrets", "--ignore-not-found", "-o", "name").strip()
    ):
        raise RuntimeError("Local credentials are missing. Restore the backup before redeploying.")
    values = credentials()
    values.update(
        {
            "MINIO_ROOT_USER": "mlops",
            "AWS_ACCESS_KEY_ID": "mlops",
            "AWS_SECRET_ACCESS_KEY": values["MINIO_ROOT_PASSWORD"],
        }
    )
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "platform-secrets", "namespace": NAMESPACE},
        "type": "Opaque",
        "stringData": values,
    }
    # Server-side apply avoids copying credentials into last-applied annotations.
    kubectl(
        "apply", "--server-side", "--field-manager=mlops", "-f", "-", payload=json.dumps(secret)
    )
    kubectl("apply", "-f", "-", payload=yaml.safe_dump_all(render(data["image"])))
    for name in ["postgres", "minio", "mlflow", "prometheus", "grafana", "evidently"]:
        print(f"Waiting for {name}", flush=True)
        kubectl("rollout", "status", f"deployment/{name}", "--timeout=600s", timeout=610)
    # Reapply must not discard a previously selected model.
    if data.get("run_id"):
        promote(data["run_id"])
    print("Platform ready. Run mlops demo to train and select a model.")


def promote(run_id):
    kubectl("set", "env", "deployment/predictor", f"MODEL_RUN_ID={run_id}")
    kubectl("scale", "deployment/predictor", "--replicas=1")
    kubectl("rollout", "status", "deployment/predictor", "--timeout=180s", timeout=190)


def demo():
    verify_owner()
    data = state()
    name = "train-iris-" + secrets.token_hex(4)
    job = yaml.safe_load((ROOT / "infra/training-job.yaml").read_text())
    job["metadata"]["name"] = name
    container = job["spec"]["template"]["spec"]["containers"][0]
    container["image"] = data["image"]
    container["env"] += [
        {"name": "SOURCE_REVISION", "value": data["source_revision"]},
        {"name": "PLATFORM_IMAGE", "value": data["image"]},
    ]
    kubectl("create", "-f", "-", payload=yaml.safe_dump(job))
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        status = json.loads(kubectl("get", "job", name, "-o", "json"))["status"]
        if status.get("succeeded"):
            break
        if any(
            c.get("type") == "Failed" and c.get("status") == "True"
            for c in status.get("conditions", [])
        ):
            raise RuntimeError(f"Training job {name} failed. Inspect its pod logs locally.")
        time.sleep(2)
    else:
        raise TimeoutError("Training deadline exceeded.")
    pods = json.loads(kubectl("get", "pods", "-l", f"job-name={name}", "-o", "json"))["items"]
    completed = [pod for pod in pods if pod["status"]["phase"] == "Succeeded"]
    result = json.loads(
        completed[0]["status"]["containerStatuses"][0]["state"]["terminated"]["message"]
    )
    if result["metrics"]["accuracy"] < 0.8:
        raise RuntimeError("Demo quality gate failed; serving version was not changed.")
    promote(result["run_id"])
    data.update(result)
    data["training_job"] = name
    private_json(LOCAL / "state.json", data)
    print(
        f"Selected run {result['run_id']}; held-out demo accuracy {result['metrics']['accuracy']:.4f}"
    )
    smoke()


def request(base, path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        base + path, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


@contextmanager
def forward(service, remote_port, namespace=NAMESPACE):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [
            "kubectl",
            "--kubeconfig",
            str(LOCAL / "kubeconfig"),
            "--context",
            f"kind-{CLUSTER}",
            "-n",
            namespace,
            "port-forward",
            f"svc/{service}",
            f"{port}:{remote_port}",
            "--address=127.0.0.1",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Port-forward failed for {service}.")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                time.sleep(0.2)
        else:
            raise TimeoutError(f"Port-forward timed out for {service}.")
        yield f"http://127.0.0.1:{port}"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def smoke():
    verify_owner()
    data = state()
    if not data.get("run_id"):
        raise RuntimeError("No selected model. Run mlops demo first.")
    with forward("predictor", 8000) as base:
        result = request(base, "/predict", {"instances": [[5.1, 3.5, 1.4, 0.2]]})
        if result["run_id"] != data["run_id"] or result["predictions"][0]["label"] != "setosa":
            raise RuntimeError("Inference lineage or prediction mismatch.")
        try:
            request(base, "/predict", {"instances": [[1, 2]]})
        except urllib.error.HTTPError as error:
            if error.code != 422:
                raise
        else:
            raise RuntimeError("Invalid input was accepted.")
    with forward("mlflow", 5000) as base:
        run = request(base, "/api/2.0/mlflow/runs/get?run_id=" + data["run_id"])["run"]
        if run["info"]["status"] != "FINISHED":
            raise RuntimeError("Training run is not finished.")
        import tempfile

        from mlflow import MlflowClient

        with tempfile.TemporaryDirectory() as directory:
            artifact = MlflowClient(tracking_uri=base).download_artifacts(
                data["run_id"], "model/manifest.json", dst_path=directory
            )
            manifest = json.loads(Path(artifact).read_text())
            if manifest["dataset_sha256"] != data["dataset_sha256"]:
                raise RuntimeError("Artifact round-trip mismatch.")
    with forward("prometheus", 9090) as base:
        deadline = time.monotonic() + 40
        query = urllib.parse.quote("sum(model_predictions_total)")
        while time.monotonic() < deadline:
            metrics = request(base, "/api/v1/query?query=" + query)["data"]["result"]
            if metrics and float(metrics[0]["value"][1]) >= 1:
                break
            time.sleep(2)
        else:
            raise RuntimeError("Prometheus did not observe the inference counter.")
    with forward("grafana", 3000) as base:
        if request(base, "/api/health")["database"] != "ok":
            raise RuntimeError("Grafana health check failed.")
    evidence = {
        key: data[key]
        for key in [
            "image",
            "source_revision",
            "run_id",
            "training_job",
            "metrics",
            "dataset_sha256",
        ]
    }
    evidence.update(
        {
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "checks": [
                "prediction",
                "invalid-input-422",
                "run-finished",
                "artifact-round-trip",
                "prometheus-counter",
                "grafana-health",
            ],
        }
    )
    private_json(LOCAL / "evidence/latest.json", evidence)
    print("PASS: inference, validation, tracking, artifact retrieval, metrics, Grafana health.")
    print("Evidence: .local/evidence/latest.json")


def down(confirm):
    if confirm != CLUSTER:
        raise RuntimeError(
            f"Deletion requires --confirm {CLUSTER}; this deletes all cluster volumes."
        )
    verify_owner()
    command(
        ["kind", "delete", "cluster", "--name", CLUSTER, "--kubeconfig", str(LOCAL / "kubeconfig")],
        stream=True,
    )
    # Evidence and credentials remain local for review; only ownership state is retired.
    (LOCAL / "state.json").rename(LOCAL / f"state-retired-{int(time.time())}.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in [
        "doctor",
        "deploy",
        "demo",
        "smoke",
        "status",
        "full",
        "pipeline",
        "serve",
        "monitor",
        "verify-full",
    ]:
        sub.add_parser(name)
    sub.add_parser("up").add_argument("--workers", type=int, choices=[0, 2], default=0)
    sub.add_parser("down").add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        if args.action == "down":
            down(args.confirm)
        elif args.action == "up":
            up(args.workers)
        elif args.action == "status":
            verify_owner()
            print(kubectl("get", "deployments,pods,pvc,jobs"))
        elif args.action in {"full", "pipeline", "serve", "monitor", "verify-full"}:
            from . import full

            {
                "full": full.install,
                "pipeline": full.pipeline,
                "serve": full.serve,
                "monitor": full.monitor,
                "verify-full": full.verify,
            }[args.action]()
        else:
            globals()[args.action]()
    except (RuntimeError, TimeoutError, subprocess.TimeoutExpired, FileNotFoundError) as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
