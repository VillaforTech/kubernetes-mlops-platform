# Capability map

The full platform includes every capability below. The core profile is a smaller
installation used for fast feedback, not a substitute for the full profile.

| Capability | Source | Execute / verify |
| --- | --- | --- |
| OpenStack VM provisioning | `infra/ansible/provision.yml` | Explicit Ansible playbook; cloud credentials required |
| VM toolchain and source setup | `infra/ansible/configure.yml` | Explicit Ansible playbook |
| Kubernetes provisioning | `infra/kind.yaml`, CLI ownership state | `mlops up` |
| Configuration and deployment | Kustomize + pinned Helm charts | `mlops up`, `mlops full` |
| Experiment metadata | MLflow + PostgreSQL PVC | `mlops smoke` |
| Artifact persistence | MinIO PVC + MLflow proxy | Artifact round trip in `mlops smoke` |
| Workflow orchestration | Kubeflow Pipelines | `mlops pipeline` |
| Model quality gate | Pipeline approval component | Rejection/acceptance unit tests; pipeline execution |
| Model serving and scaling | KServe + Knative + Istio + cert-manager | `mlops serve`, `mlops verify-full` |
| Metrics and dashboards | Prometheus + Grafana | Prometheus query and Grafana health in `mlops smoke` |
| Data monitoring | Evidently persistent workspace | `mlops monitor`, `mlops verify-full` |
| Ingress routing | NGINX + hostname routes | Full install; access described in operations |
| User permissions | Observer Roles and RoleBindings | Positive/negative authorization checks |
| Short feedback cycle | Kubernetes training Job + FastAPI | `mlops demo` |

Implementation presence and runtime success are distinct. The dated
[validation record](validation.md) is the source of truth for what has actually
been exercised. No benchmark or cloud provisioning result is inferred from CI.
