# Working agreement

- Work from this repository root. Never commit `.local/`, credentials, kubeconfigs, or rendered Secrets.
- Install locked dependencies, then run `make check` in `.venv`.
- `mlops up`, `full`, `demo`, `pipeline`, `serve`, and `monitor` mutate only the managed disposable cluster.
- Every Kubernetes and Helm command must select the project kubeconfig and context explicitly.
- Preserve node ownership checks. Teardown requires the exact cluster name.
- Keep all platform capabilities in docs/capabilities.md. Never silently replace Kubeflow, KServe, or Evidently with the quick demo.
- Record static, core-runtime, full-runtime, and cloud-provisioning evidence separately.
- Do not publish generated credentials, unsanitized pod logs, or invented performance claims.
