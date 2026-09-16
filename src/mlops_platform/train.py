"""Train a seeded Iris classifier and record its complete artifact lineage."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

import joblib
import mlflow
import numpy as np
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SEED = 42


def fit_model():
    iris = load_iris()
    x_train, x_test, y_train, y_test = train_test_split(
        iris.data, iris.target, test_size=0.25, random_state=SEED, stratify=iris.target
    )
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=300, random_state=SEED))
    model.fit(x_train, y_train)
    prediction = model.predict(x_test)
    metrics = {"accuracy": float(accuracy_score(y_test, prediction))}
    manifest = {
        "dataset": "sklearn.datasets.load_iris",
        "dataset_sha256": hashlib.sha256(iris.data.tobytes() + iris.target.tobytes()).hexdigest(),
        "seed": SEED,
        "train_rows": len(x_train),
        "test_rows": len(x_test),
        "features": list(iris.feature_names),
        "classes": list(iris.target_names),
        "confusion_matrix": confusion_matrix(y_test, prediction).tolist(),
        "training_mean": np.mean(x_train, axis=0).tolist(),
        "training_std": np.std(x_train, axis=0).tolist(),
    }
    return model, metrics, manifest


def main():
    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    mlflow.set_experiment("iris-platform-demo")
    model, metrics, manifest = fit_model()
    with tempfile.TemporaryDirectory() as folder, mlflow.start_run() as run:
        mlflow.log_params(
            {"seed": SEED, "test_fraction": 0.25, "model": "scaled-logistic-regression"}
        )
        mlflow.set_tags(
            {
                "source_revision": os.getenv("SOURCE_REVISION", "unknown"),
                "image": os.getenv("PLATFORM_IMAGE", "unknown"),
            }
        )
        mlflow.set_tag("pipeline_execution", os.getenv("PIPELINE_EXECUTION", "standalone"))
        mlflow.log_metrics(metrics)
        path = Path(folder) / "model.joblib"
        joblib.dump(model, path)
        mlflow.log_artifact(str(path), artifact_path="model")
        mlflow.log_dict(manifest, "model/manifest.json")
        result = {
            "run_id": run.info.run_id,
            "metrics": metrics,
            "dataset_sha256": manifest["dataset_sha256"],
        }
    # Kubernetes exposes this structured, non-secret result in terminated.message.
    output = Path(os.getenv("RESULT_FILE", "/dev/termination-log"))
    output.write_text(json.dumps(result))
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
