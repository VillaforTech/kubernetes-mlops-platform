# Security boundaries

The platform is designed for an isolated development environment. UIs and APIs
are internal services exposed through loopback forwarding. Kubernetes RBAC does
not authenticate those UIs. Do not expose them publicly without an explicit
authentication, authorization, TLS, and network-isolation design.

Credentials are generated once in `.local/credentials.json` with owner-only
permissions and sent to Kubernetes through stdin. They are not command-line
arguments or committed manifests. The CLI selects a dedicated kubeconfig and
checks node ownership before changing the cluster. It never adopts an unrelated
cluster silently.

Model artifacts use Python serialization. Only load artifacts from a trusted
operator-controlled MLflow instance. An MLflow run ID identifies lineage; it is
not a cryptographic attestation or a permission boundary.

Never include kubeconfigs, tokens, passwords, OpenStack configuration, raw pod
logs, or local evidence containing access data in an issue or pull request. Report
an exposure through [private vulnerability reporting](https://github.com/VillaforTech/kubernetes-mlops-platform/security/advisories/new)
with affected paths, revisions, impact, and safe reproduction steps.
No response-time or production-security certification is claimed.
