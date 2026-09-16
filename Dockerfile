FROM python:3.11.15-slim-bookworm@sha256:d29f48a31a8b408ed19272ca1e7b10ebae13b240a27e862d3d4217c528e2e0c3
ENV MLFLOW_ENABLE_PROXY_MULTIPART_DOWNLOAD=false MLFLOW_ENABLE_PROXY_MULTIPART_UPLOAD=false MLFLOW_DISABLE_AGENT_HINT=1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HOME=/tmp
WORKDIR /app
COPY requirements.lock ./
RUN pip install --require-hashes -r requirements.lock
COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-deps . && useradd --uid 10001 --no-create-home app
USER 10001:10001
EXPOSE 5000 8000
CMD ["python", "-m", "mlops_platform.tracking"]
