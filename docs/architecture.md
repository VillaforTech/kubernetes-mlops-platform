# Architecture

## Execution and state

The operator provisions a dedicated kind cluster or an Ubuntu VM on OpenStack.
Ansible installs the VM toolchain and transfers a clean Git archive. The same
project CLI builds a content-tagged application image and loads it into kind.
Kustomize manages the platform's own resources; pinned upstream manifests and
Helm charts supply the workflow and serverless control planes.

PostgreSQL stores MLflow metadata. MinIO stores model artifacts. Training and
serving clients access artifacts through MLflow, so they do not receive object
storage credentials. PostgreSQL, MinIO, and Evidently have separate PVCs.
Prometheus history and Grafana's mutable local state are ephemeral; datasource
and dashboard definitions are restored from Git.

## Model lifecycle

1. A Kubeflow component trains a scaled logistic regression with a stratified,
   seeded train/test split. The scaler is fitted on training rows only.
2. The run records parameters, test metrics, dataset hash, image identifier,
   source revision, model artifact, feature names, and split sizes in MLflow.
3. A separate pipeline component rejects runs below a configured accuracy gate.
4. The operator selects the successful run by its unique execution tag.
5. The serving container downloads artifacts for that exact run ID. Failed
   artifact loading prevents successful startup.
6. KServe routes requests through Knative/Istio and can scale the service to zero.
7. Prometheus scrapes the core prediction deployment, which serves the same
   selected run as KServe. It observes bounded-cardinality metrics; Grafana displays
   throughput, latency, counts, and target availability.
8. Evidently stores a report comparing reference data with a controlled shift.
   That scenario demonstrates monitoring mechanics, not a production drift claim.

The quick demo executes the same training implementation as a Kubernetes Job and
uses a plain Deployment for prediction. Its smaller control-plane footprint is
useful for debugging the data path before exercising the full platform.

## Access and failure boundaries

Every CLI Kubernetes call selects the project kubeconfig and context. Node labels
bind lifecycle operations to a locally recorded ownership identifier. Cluster
creation refuses to adopt an existing foreign cluster. Teardown requires the
exact cluster name.

Core application pods run as non-root users, drop capabilities, use a read-only
root filesystem, define resource requests/limits, and disable service-account
token automount. Third-party control planes retain their required privileges.
Observer roles grant selected read operations and deny Secrets and mutation.
These Kubernetes roles do not authenticate service UIs.

No external LoadBalancer is created. Ingress controllers and UIs are reached
through loopback forwarding. NetworkPolicy enforcement and public TLS are not
claimed. Model artifacts use Python serialization and must come from this
trusted, operator-controlled tracking server.

## Reliability limits

The default single local node and single-replica databases are deliberate development
choices. Node or cluster deletion can destroy data. Kubernetes readiness verifies
process availability, while the explicit smoke checks verify selected service
interactions. Neither establishes an uptime target, backup safety, or resilience
under fault injection.
