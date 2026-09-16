# Third-party components

The project integrates Kubernetes/kind, MLflow, Kubeflow Pipelines, KServe,
Knative, Istio, cert-manager, NGINX Ingress Controller, PostgreSQL, MinIO,
Evidently, Prometheus, Grafana, scikit-learn, and their dependencies.

These components retain their upstream licenses. The repository's MIT license
covers its own implementation and documentation; it does not relicense the
container images, downloaded manifests, Helm charts, or Python dependencies.
Pinned references are recorded in `requirements.lock`, Kubernetes manifests,
`infra/kind.yaml`, and `platform/versions.json`. No upstream project endorses
this platform.
