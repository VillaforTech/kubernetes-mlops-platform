from unittest.mock import Mock

import pytest
import yaml

from mlops_platform import cli
from mlops_platform.pipeline import compile_pipeline
from mlops_platform.pipeline_worker import quality_gate


def test_quality_gate_rejects_low_accuracy():
    with pytest.raises(ValueError, match="Quality gate"):
        quality_gate({"run_id": "candidate", "metrics": {"accuracy": 0.6}}, 0.8)


def test_quality_gate_accepts_boundary_and_rejects_invalid_threshold():
    result = {"run_id": "candidate", "metrics": {"accuracy": 0.8}}
    assert quality_gate(result, 0.8) == "candidate"
    with pytest.raises(ValueError, match="between"):
        quality_gate(result, 1.1)


def test_compiled_pipeline_has_training_and_gate_dependencies(tmp_path):
    target = tmp_path / "pipeline.yaml"
    compile_pipeline("mlops-platform:fixed-test-image", target)
    spec = yaml.safe_load(target.read_text())
    tasks = spec["root"]["dag"]["tasks"]
    assert set(tasks) == {"train", "approve"}
    assert tasks["approve"]["dependentTasks"] == ["train"]
    for executor in spec["deploymentSpec"]["executors"].values():
        assert executor["container"]["image"] == "mlops-platform:fixed-test-image"
    assert not tasks["train"].get("cachingOptions", {}).get("enableCache", False)


def test_cross_namespace_manifest_apply_keeps_context_without_forcing_namespace(monkeypatch):
    mock = Mock(return_value="")
    monkeypatch.setattr(cli, "command", mock)
    cli.kubectl("apply", "-f", "-", namespace=None)
    args = mock.call_args.args[0]
    assert "--context" in args
    assert "--namespace" not in args
