# Operations

Run commands from the repository root with `.venv` active.

## Installation

`mlops up` checks Docker and tools, creates a dedicated cluster, builds the
application image, loads it into kind, generates local credentials once, applies
core manifests, and waits for deployments. Re-running it reuses the owned cluster
and credentials. Image tags derive from the Dockerfile, lockfile, package metadata,
and source content.

`mlops full` installs Kubeflow Pipelines, cert-manager, Istio, Knative, KServe,
NGINX ingress, and the access roles. Upstream references are pinned. It creates
cluster-scoped resources only inside the dedicated cluster. It can be rerun after
a failed stage; it stops at the first unresolved failure.

`mlops pipeline` executes tracked training and a quality gate in Kubeflow.
`mlops serve` creates an InferenceService for the selected run. `mlops verify-full`
checks the selected model and the full integration path. `mlops monitor` creates
an Evidently report independently.

For the smaller profile, use `mlops up`, `mlops demo`, and `mlops smoke`.

To create a three-node topology, use `mlops up --workers 2` on a fresh cluster.
This places one control plane and two workers on the same Docker host; it does
not provide host failure tolerance. Existing cluster topology is preserved.

## Observer access

After `mlops full`, create an observer with a one-day client certificate:

```bash
python tools/create_user.py reviewer
kubectl --kubeconfig .local/users/reviewer/kubeconfig.json \
  --context kind-mlops-platform -n mlops get pods
```

The generated kubeconfig is owner-only. Observers can inspect selected workloads
and logs but cannot read Secrets or mutate workloads. A certificate is a
credential; do not commit or share it casually. Removing the shared observer
RoleBindings revokes that group's namespace access; deleting a local certificate
file alone does not revoke an already issued copy.

## Inspect services

```bash
mlops status
kubectl --kubeconfig .local/kubeconfig --context kind-mlops-platform \
  -n mlops port-forward --address=127.0.0.1 svc/mlflow 5000:5000
```

Use another terminal for each forwarding process. Stop it with Ctrl-C.

| Service | Namespace | Local mapping |
| --- | --- | --- |
| MLflow | mlops | `svc/mlflow 5000:5000` |
| Prediction API / OpenAPI docs | mlops | `svc/predictor 8000:8000` |
| Evidently | mlops | `svc/evidently 8001:8000` |
| Prometheus | mlops | `svc/prometheus 9090:9090` |
| MinIO console | mlops | `svc/minio 9001:9001` |
| Grafana | mlops | `svc/grafana 3000:3000` |
| Kubeflow UI | kubeflow | `svc/ml-pipeline-ui 8080:80` |
| KServe local gateway | istio-system | `svc/knative-local-gateway 8082:80` |
| NGINX hostname ingress | nginx-ingress | `svc/nginx-nginx-ingress-controller 8081:80` |

The Grafana username is `admin`; its generated password is in the owner-only
`.local/credentials.json`. Read it locally when needed; never copy that file into
an issue, screenshot, or commit. Hostname routes are defined in
`platform/ingress/routes.yaml`. Through the NGINX forward, send the matching Host
header (for example `curl -H 'Host: mlflow.local' http://127.0.0.1:8081/`).

To call the selected KServe model through the local gateway forward:

```bash
curl -H 'Host: iris.mlops.svc.cluster.local' \
  -H 'Content-Type: application/json' \
  -d '{"instances":[[5.1,3.5,1.4,0.2]]}' \
  http://127.0.0.1:8082/v1/models/iris:predict
```

## Remote VM / OpenStack

Provisioning can incur cloud charges. Run it only against your chosen account,
flavor, network, and SSH-only security group. Authentication stays outside Git.

```bash
python -m pip install -r infra/requirements.txt
ansible-galaxy collection install -r infra/ansible/collections.yml
cp infra/ansible/cloud-vars.yml.example .local/cloud-vars.yml
cp infra/ansible/inventory.ini.example .local/inventory.ini
# Edit both local files; configure OS_CLOUD outside the repository.
ansible-playbook infra/ansible/provision.yml -e @.local/cloud-vars.yml

git archive --format=tar.gz --output=.local/source.tar.gz HEAD
ansible-playbook -i .local/inventory.ini infra/ansible/configure.yml
```

Then run the platform commands on the VM. Access services using SSH local
forwarding; the Kubernetes API remains bound to the VM loopback interface.
Existing VM users can skip the provisioning playbook. The playbooks are not
executed by CI and require separate cloud validation.

## Diagnostics

Start with `mlops status` and `.local/last-command-error.json`. The CLI redacts its
generated credential values from that diagnostic file. Inspect pod logs locally;
review and redact them before sharing. Common distinctions:

- `Pending`: inspect resource requests, available memory, PVCs, and scheduling events.
- `ImagePullBackOff`: check the registry, pinned reference, and platform architecture.
- `OOMKilled`: inspect the affected process and configured memory limit; MLflow is
  configured for one worker with unused background job execution disabled.
- A green readiness probe with a failing smoke test: inspect artifact access and
  the selected run ID, not only the pod's status.
- No monitoring metric yet: allow the scrape interval and send a prediction.
- A remote manifest failure: verify the pinned upstream endpoint and network access.

MLflow artifact clients explicitly use the tracking proxy. Direct multipart
transfers would return cluster-internal MinIO addresses to a laptop. Helm 4 uses
client-side updates here because controllers own some webhook fields. The small
Istio control plane reserves 256 MiB and has a 1 GiB limit; resize it for larger
workloads. Cold registry pulls can take several minutes.

## Teardown and recovery

Back up any data you want to retain before teardown. The command below deletes
the managed kind cluster and its volume data; it does not delete a cloud VM.

```bash
mlops down --confirm mlops-platform
```

Credentials and evidence remain in `.local/`. No automatic backup/restore promise
is made. Recreating a cluster after teardown starts with empty Kubernetes volumes.
Delete an OpenStack VM through your cloud workflow only after reviewing its
attached storage and recovery requirements.
