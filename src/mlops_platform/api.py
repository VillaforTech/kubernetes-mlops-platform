"""HTTP inference with explicit model lineage, validation, and bounded metrics."""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import joblib
from fastapi import FastAPI, HTTPException, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mlflow import MlflowClient
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, ConfigDict, Field

Feature = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
Row = Annotated[list[Feature], Field(min_length=4, max_length=4)]


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instances: Annotated[list[Row], Field(min_length=1, max_length=128)]


def load_model(run_id):
    if not run_id:
        raise RuntimeError("MODEL_RUN_ID is required")
    client = MlflowClient(tracking_uri=os.environ["MLFLOW_TRACKING_URI"])
    directory = client.download_artifacts(run_id, "model")
    manifest = json.loads((Path(directory) / "manifest.json").read_text())
    return joblib.load(Path(directory) / "model.joblib"), manifest


def create_app(loader=load_model):
    registry = CollectorRegistry()
    predictions = Counter("model_predictions_total", "Predicted rows", registry=registry)
    latency = Histogram(
        "model_prediction_seconds", "Prediction computation time", registry=registry
    )

    @asynccontextmanager
    async def lifespan(app):
        app.state.run_id = os.getenv("MODEL_RUN_ID", "")
        app.state.model, app.state.manifest = loader(app.state.run_id)
        yield

    app = FastAPI(title="MLOps Prediction API", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(_request, error):
        # Exclude raw inputs: NaN is not JSON-safe and payloads need not be echoed.
        detail = [{key: item[key] for key in ("loc", "msg", "type")} for item in error.errors()]
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.get("/healthz")
    def health():
        return {"status": "alive"}

    @app.get("/readyz")
    def ready():
        if not hasattr(app.state, "model"):
            raise HTTPException(503, "Model is not loaded")
        return {"status": "ready", "run_id": app.state.run_id}

    @app.get("/model")
    def model_info():
        return {"run_id": app.state.run_id, "manifest": app.state.manifest}

    @app.post("/v1/models/iris:predict", include_in_schema=False)
    @app.post("/predict")
    def predict(request: PredictionRequest):
        with latency.time():
            output = app.state.model.predict(request.instances)
        predictions.inc(len(request.instances))
        classes = app.state.manifest["classes"]
        return {
            "run_id": app.state.run_id,
            "predictions": [
                {"class_id": int(value), "label": classes[int(value)]} for value in output
            ],
        }

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
