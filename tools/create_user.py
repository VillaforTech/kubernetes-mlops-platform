"""Create a one-day, read-only observer credential for the managed cluster."""

import argparse
import base64
import json
import re
import secrets
import time

from mlops_platform import cli


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Lowercase observer name; never an administrator identity")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,30}", args.name):
        parser.error("Use 2–31 lowercase letters, digits, or hyphens, starting with a letter.")
    cli.verify_owner()
    target = cli.LOCAL / "users" / args.name
    target.mkdir(parents=True, mode=0o700, exist_ok=False)
    key, csr = target / "client.key", target / "client.csr"
    cli.command(
        [
            "openssl",
            "req",
            "-new",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(csr),
            "-subj",
            f"/CN={args.name}/O=mlops-observers",
        ]
    )
    key.chmod(0o600)
    csr.chmod(0o600)
    name = "observer-" + args.name + "-" + secrets.token_hex(4)
    request = {
        "apiVersion": "certificates.k8s.io/v1",
        "kind": "CertificateSigningRequest",
        "metadata": {"name": name},
        "spec": {
            "request": base64.b64encode(csr.read_bytes()).decode(),
            "signerName": "kubernetes.io/kube-apiserver-client",
            "expirationSeconds": 86400,
            "usages": ["client auth"],
        },
    }
    cli.kubectl("create", "-f", "-", payload=json.dumps(request), namespace=None)
    try:
        cli.kubectl("certificate", "approve", name, namespace=None)
        for _ in range(30):
            response = json.loads(cli.kubectl("get", "csr", name, "-o", "json", namespace=None))
            certificate = response.get("status", {}).get("certificate")
            if certificate:
                break
            time.sleep(1)
        else:
            raise TimeoutError("Certificate signing timed out.")
        config = json.loads(
            cli.kubectl("config", "view", "--raw", "--minify", "-o", "json", namespace=None)
        )
        config["users"] = [
            {
                "name": args.name,
                "user": {
                    "client-certificate-data": certificate,
                    "client-key-data": base64.b64encode(key.read_bytes()).decode(),
                },
            }
        ]
        config["contexts"][0]["context"].update({"user": args.name, "namespace": "mlops"})
        cli.private_json(target / "kubeconfig.json", config)
    finally:
        cli.kubectl("delete", "csr", name, namespace=None)
    print(f"Created {target.relative_to(cli.ROOT)}/kubeconfig.json; expires after one day.")
    print("Observer permissions depend on mlops full. No credentials displayed.")


if __name__ == "__main__":
    main()
