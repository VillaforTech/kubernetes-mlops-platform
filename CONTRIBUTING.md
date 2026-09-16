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
