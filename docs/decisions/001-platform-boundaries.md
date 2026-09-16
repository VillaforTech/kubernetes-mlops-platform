# ADR 001: explicit full platform and a smaller verification path

Status: accepted.

The full platform retains workflow orchestration, experiment tracking, model
serving, monitoring, provisioning, ingress, and access management as distinct
capabilities. Kubeflow and KServe remain first-class components.

A smaller profile runs the same model code as a Kubernetes Job and a plain
Deployment. This shortens the feedback loop when diagnosing storage, tracking,
serialization, or request-validation problems. Its success is never reported as
full-platform success.

Both profiles use pinned dependencies, an explicitly scoped kubeconfig, and
ignored local credentials. The repository preserves a direct path from source to
image to run ID to prediction. The tradeoff is a larger dependency and capacity
requirement for the full profile; its runtime evidence is recorded separately.
