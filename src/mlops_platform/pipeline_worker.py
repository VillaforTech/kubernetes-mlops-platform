"""Entrypoint for the explicitly versioned Kubeflow component image."""

import argparse
import json
import os
from pathlib import Path

from . import train


def quality_gate(result, threshold):
    if not 0 <= threshold <= 1:
        raise ValueError("Accuracy threshold must be between zero and one.")
    accuracy = result["metrics"]["accuracy"]
    if not 0 <= accuracy <= 1 or accuracy < threshold:
        raise ValueError("Quality gate failed; model is not eligible for promotion.")
    return result["run_id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["train", "approve"])
    parser.add_argument("--execution")
    parser.add_argument("--source-revision", default="uncommitted")
    parser.add_argument("--image", default="unknown")
    parser.add_argument("--result")
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.action == "train":
        os.environ["MLFLOW_TRACKING_URI"] = "http://mlflow.mlops.svc.cluster.local:5000"
        os.environ["PIPELINE_EXECUTION"] = args.execution
        os.environ["SOURCE_REVISION"] = args.source_revision
        os.environ["PLATFORM_IMAGE"] = args.image
        os.environ["RESULT_FILE"] = str(output)
        train.main()
    else:
        output.write_text(quality_gate(json.loads(args.result), args.threshold))


if __name__ == "__main__":
    main()
