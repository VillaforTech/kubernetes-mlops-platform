# Contributing

Use small commits and focused pull requests. Describe the behavior changed and
how it was checked; keep the description concise.

Install the locked dependencies and run `make check` before a PR. Changes to
cluster lifecycle, configuration, request validation, or promotion gates need
behavioral regression coverage. Run the relevant smoke checks for integration
changes and update the evidence record with their actual outcome.

Preserve the full capability map. Do not replace Kubeflow, KServe, or Evidently
with a smaller demo while retaining claims about the full platform. Keep generated
credentials and runtime state outside Git. See [AGENTS.md](AGENTS.md).

## Workflow

Use the issue forms for bugs and feature proposals. Follow the
[code of conduct](CODE_OF_CONDUCT.md) and [security policy](SECURITY.md).

Open a focused branch and PR with a concise title, behavior change, and validation
results. Resolve review conversations and keep the branch current before merging.
The `validate` check is required on `main`; merges use squash with the PR title
and description. The current single-maintainer workflow does not require an
additional approving reviewer. CODEOWNERS identifies the responsible maintainer.

See [maintenance](docs/maintenance.md) for dependency updates and repository settings.
