"""Validate local manifests without applying them or loading credentials."""

import json
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = [
        *ROOT.glob("k8s/**/*.yaml"),
        *ROOT.glob("k8s/**/*.yml"),
        *ROOT.glob("infra/**/*.yaml"),
        *ROOT.glob("infra/**/*.yml"),
        *ROOT.glob("platform/**/*.yaml"),
        *ROOT.glob(".github/**/*.yml"),
    ]
    for path in files:
        list(yaml.safe_load_all(path.read_text()))
    result = subprocess.run(
        ["kubectl", "kustomize", "k8s"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    documents = list(yaml.safe_load_all(result.stdout))
    identities = set()
    for obj in documents:
        identity = (
            obj["apiVersion"],
            obj["kind"],
            obj["metadata"].get("namespace"),
            obj["metadata"]["name"],
        )
        assert identity not in identities, f"Duplicate resource: {identity}"
        identities.add(identity)
        assert obj["kind"] != "Secret", "Credential values must be generated outside manifests."
        if obj["kind"] == "Service":
            assert obj["spec"].get("type", "ClusterIP") == "ClusterIP", (
                "No public service in the local platform."
            )
        if obj["kind"] == "Deployment":
            pod = obj["spec"]["template"]["spec"]
            assert pod["automountServiceAccountToken"] is False
            assert pod["securityContext"]["runAsNonRoot"] is True
            for container in pod["containers"]:
                assert container["securityContext"]["allowPrivilegeEscalation"] is False
                assert container["securityContext"]["readOnlyRootFilesystem"] is True
                assert container["resources"]["requests"] and container["resources"]["limits"]
                assert container.get("readinessProbe") and container.get("livenessProbe")
                assert (
                    "@sha256:" in container["image"] or container["image"] == "mlops-platform:dev"
                )
    for path in [ROOT / "README.md", *ROOT.glob("docs/**/*.md")]:
        if not path.exists():
            continue
        for target in re.findall(r"\[[^\]]*\]\(([^) ]+)\)", path.read_text()):
            if "://" not in target and not target.startswith("#"):
                assert (path.parent / target.split("#")[0]).exists(), (
                    f"Broken link: {path.name} -> {target}"
                )
    json.loads((ROOT / "k8s/config/dashboard.json").read_text())
    print(
        f"PASS: {len(files)} YAML files; {len(documents)} rendered objects; workload and exposure policies; documentation links."
    )


if __name__ == "__main__":
    main()
