# Repository maintenance

## GitHub settings

The following repository settings were applied and read back on 2026-09-16.
These settings are managed in GitHub; this document records the intended policy.

| Area | Configuration |
| --- | --- |
| Presentation | Technical description and component topics; public repository with MIT license |
| Navigation | Issues enabled; Wiki, Projects, and Discussions disabled |
| Merging | Squash only; commit title and body come from the concise PR description |
| Branch lifecycle | Offer branch updates; automatically delete merged feature branches |
| Main branch | PR required; current branch and successful `validate` check from GitHub Actions required |
| Reviews | Resolve conversations; zero additional approvals for the single-maintainer workflow |
| History | Linear history; no force pushes or deletion of `main`; rules include administrators |
| Actions | Default token access is read-only; workflows cannot approve PRs |
| Security | Secret scanning, push protection, Dependabot alerts/security updates, and private vulnerability reporting enabled |

Settings do not merge an open PR. Issue forms, CODEOWNERS, and scheduled dependency
updates become the repository's default configuration when their PR reaches
`main`. Runtime and infrastructure validation are recorded separately in
[validation](validation.md).

## Dependency updates

Dependabot checks GitHub Actions monthly, groups minor and patch updates, and
limits open version-update PRs to three. Review immutable action revisions before
merging. Automatic security fixes may open additional PRs for supported manifests;
they follow the same review and CI requirements.

Python runtime updates are curated because `pyproject.toml` and the hashed,
universal `requirements.lock` must change together. After updating the requested
version constraints, regenerate the lock using the command in its header:

```bash
uv pip compile pyproject.toml --universal --python-version 3.11 \
  --generate-hashes -o requirements.lock
python -m pip install --require-hashes -r requirements.lock
python -m pip install --no-deps -e .
make check
```

`make check` includes `pip check` so an updated package declaration cannot silently
pass with incompatible locked dependencies. Review the lock diff. Runtime changes
also need the relevant cluster smoke checks; changed control-plane versions need
full integration verification. Update the evidence only after observing results.

Pinned images, Helm charts, remote manifests, and Ansible dependencies require
explicit compatibility review. A Dependabot alert or a successful static check
does not establish that the Kubernetes platform still runs end to end.

CI installs `infra/requirements.txt` in an isolated Python 3.11 environment,
runs `pip check`, installs the pinned OpenStack collection, checks module
resolution, and validates both playbooks with `--syntax-check`. These checks
require no cloud credentials and do not provision infrastructure. Ansible
updates stay on stable releases compatible with the controller's Python version.
The OpenStack collection uses the official project's GitHub mirror at the
immutable commit for release `2.4.1`, avoiding a dependency on Galaxy's artifact
service. Update the release and commit together when upgrading the collection.

## Releases and support

Before a release, verify CI on the intended commit, review changed capabilities,
run affected integration checks, and update the dated evidence and operating
instructions. Create a version tag only after that review. No release or hosted
service is implied by the repository's package version.

Keep PR titles and descriptions concise. Refer to [support](../SUPPORT.md) for
public reports and [security](../SECURITY.md) for private vulnerability reports.
