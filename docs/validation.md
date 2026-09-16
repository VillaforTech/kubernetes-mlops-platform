# Validation record

Date: 2026-09-16. [Machine-readable evidence](evidence/2026-09-16.json) records
run identifiers, image identity, versions, and observed checks. Runtime results
were obtained on a dedicated local cluster with synthetic demonstration traffic.

| Layer | Observed result |
| --- | --- |
| Offline tests and lint | 31 tests passed; Ruff passed |
| Core manifests | 22 objects rendered; workload and exposure policies passed |
| CI | GitHub Actions validation passed |
| Secret scan | Gitleaks found no leaks in repository history |
| Core runtime | Prediction, malformed-input rejection, finished tracking run, artifact retrieval, Prometheus counter, and Grafana health passed |
| Full control plane | Kubeflow, cert-manager, Istio, Knative, KServe, and NGINX installed |
| Kubeflow pipeline | Training and quality gate succeeded; selected run promoted |
| KServe inference | Returned the selected MLflow run ID and the expected prediction through Istio |
| Ingress | All six hostname routes returned HTTP 200 |
| Evidently | Drift report stored in the persistent workspace |
| Grafana | Provisioned dashboard retrieved with all four panels |
| Observer access | Issued certificate allowed pod reads and denied Secrets and deployment deletion |
| OpenStack / Ansible | Both playbooks passed syntax validation; no VM provisioned |
| Three-node topology | Configuration and ownership test passed; runtime not exercised |

## Demonstration result

The pipeline trained on 112 Iris rows and evaluated 38 held-out rows. Its accuracy
was **35/38 (0.9211)**. This is a deterministic infrastructure demonstration, not
a benchmark, production-quality claim, or estimate of broader model performance.
The split is stratified and seeded; preprocessing is fitted on training data.

The recorded MLflow run is `3830cfbc17af4b16983be8c4c23894cb`; its Kubeflow run is
`6405f0ad-153d-40c7-94ff-33b5afb635b3`. These identify the observed demonstration,
not an externally hosted service. Evidence includes the training image revision
and the later CLI verification revision separately.

## Environment and limits

The test used macOS ARM64, Docker 28.4.0, kind 0.32.0, Kubernetes 1.33.12, Python
3.11.15, and Helm 4.2.4. Docker had approximately 7.7 GiB RAM. The full stack ran
with the committed development resource settings; 16 GiB remains the planning
allowance for headroom. This observation is not a capacity or performance test.

Kubeflow's pinned metadata writer is amd64-only and ran with Docker Desktop's
architecture emulation. Native Linux ARM without that compatibility is not
verified. The VM playbooks install Helm 3.19.0 and require their own environment
validation. Optional worker nodes remain on the same host and do not provide
host-level availability.

The runtime checks executed `mlops up`, `mlops full`, `mlops pipeline`,
`mlops serve`, `mlops verify-full`, and the observer utility. Cold downloads and
controller readiness required several minutes. The implementation includes fixes
for proxied artifact downloads, controller reapplication, local gateway routing,
and pinned SDK behavior discovered during those checks.

No cloud deployment, public ingress, fault-injection result, recovery guarantee,
load benchmark, or production availability claim is implied by these results.
Generated credentials and raw logs remain outside Git.
