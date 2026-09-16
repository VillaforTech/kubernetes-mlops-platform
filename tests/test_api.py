import pytest
from fastapi.testclient import TestClient

from mlops_platform.api import create_app
from mlops_platform.train import fit_model


@pytest.fixture(scope="module")
def trained():
    return fit_model()


@pytest.fixture
def client(trained, monkeypatch):
    model, _, manifest = trained
    monkeypatch.setenv("MODEL_RUN_ID", "verified-test-run")
    with TestClient(create_app(loader=lambda _: (model, manifest))) as client:
        yield client


def test_prediction_includes_model_lineage(client):
    result = client.post("/predict", json={"instances": [[5.1, 3.5, 1.4, 0.2]]})
    assert result.status_code == 200
    assert result.json() == {
        "run_id": "verified-test-run",
        "predictions": [{"class_id": 0, "label": "setosa"}],
    }
    assert client.get("/readyz").json()["run_id"] == "verified-test-run"


@pytest.mark.parametrize(
    "body",
    [
        {"instances": []},
        {"instances": [[1, 2, 3]]},
        {"instances": [[1, 2, 3, 4, 5]]},
        {"instances": [[-1, 2, 3, 4]]},
        {"instances": [[101, 2, 3, 4]]},
        {"instances": [[1, 2, 3, 4]] * 129},
        {"instances": [[1, 2, 3, 4]], "unrecognized": True},
    ],
)
def test_invalid_inputs_rejected(client, body):
    assert client.post("/predict", json=body).status_code == 422


def test_non_finite_values_are_rejected_without_server_error(client):
    response = client.post(
        "/predict",
        content='{"instances": [[NaN, 2, 3, 4]]}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_metrics_count_rows_without_unbounded_labels(client):
    client.post("/predict", json={"instances": [[5.1, 3.5, 1.4, 0.2]] * 2})
    text = client.get("/metrics").text
    assert "model_predictions_total 2.0" in text
    assert "model_prediction_seconds_count 1.0" in text
    assert "verified-test-run" not in text


def test_model_manifest_and_split_are_reproducible(trained):
    _, metrics, manifest = trained
    _, repeated_metrics, repeated_manifest = fit_model()
    assert manifest == repeated_manifest
    assert metrics == repeated_metrics
    assert manifest["train_rows"] + manifest["test_rows"] == 150
    assert manifest["test_rows"] == 38
    assert len(manifest["features"]) == 4


def test_model_loading_failure_blocks_startup():
    def failed_loader(_):
        raise RuntimeError("Artifact unavailable")

    with pytest.raises(RuntimeError, match="Artifact unavailable"):
        with TestClient(create_app(loader=failed_loader)):
            pass
