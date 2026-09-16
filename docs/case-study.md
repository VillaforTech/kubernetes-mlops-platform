# Case study: a traceable model lifecycle on Kubernetes

## Problem

A model's test score does not describe how it was trained, where its artifacts
live, which version serves a request, or whether the surrounding services work.
This project makes those connections explicit and executable.

## Design

Kubeflow coordinates training and approval. MLflow records the run and proxies
artifacts backed by MinIO, while PostgreSQL stores metadata. KServe serves the
selected run through Knative and Istio. Prometheus and Grafana expose system
signals, and Evidently adds data monitoring. Local kind and OpenStack/Ansible
provisioning use the same application and deployment assets.

The prediction API includes the MLflow run ID in every response and rejects
malformed input. The pipeline's quality gate precedes promotion. Credentials,
cluster ownership, and destructive teardown are explicit operational boundaries.

## Engineering decisions

- Use a small public dataset so the complete infrastructure path can be exercised.
- Keep scalers and model fitting inside the training split.
- Proxy artifacts through the tracking server instead of giving every client
  object-store credentials.
- Pin dependencies and use content-derived image tags.
- Provide both full-platform and core smoke checks with separate evidence.
- Store monitoring configuration in Git and runtime state outside Git.

## Results

Use the dated [validation record](validation.md) for measured outcomes and current
limits. This project does not claim production uptime, deployment latency, or
model accuracy beyond the specific recorded demonstration.

## Descripción para portafolio

Plataforma MLOps sobre Kubernetes que conecta entrenamiento con Kubeflow,
seguimiento y artefactos con MLflow, despliegue con KServe y monitoreo con
Evidently, Prometheus y Grafana. Incluye aprovisionamiento automatizado, controles
de acceso, pruebas y trazabilidad desde el código hasta la versión que responde
una predicción.
