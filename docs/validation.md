# Validation record

Date: 2026-09-16. This file distinguishes implemented capabilities from observed
execution. It is updated after verification, not inferred from configuration.

| Layer | Status |
| --- | --- |
| Offline tests and lint | 24 tests passed; Ruff passed |
| Core manifest rendering | 22 objects rendered; workload and exposure policies passed |
| Local core installation | Services started; end-to-end verification in progress |
| Full control plane | Installation validation in progress |
| Kubeflow pipeline / KServe inference | Pending runtime verification |
| OpenStack / Ansible | Implemented; no cloud resources provisioned |

Local environment: macOS ARM64, Docker 28.4.0, kind 0.32.0, Kubernetes 1.33.12,
Python 3.11.15. The Docker engine has approximately 7.7 GiB RAM. This is below the
full-profile planning allowance of 16 GiB; resource observations must be treated
as environment-specific.

Evidence files are generated under `.local/evidence/`. Only reviewed, non-secret
summaries belong in this directory. There is no performance or availability
benchmark in this revision.
