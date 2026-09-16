from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from mlops_platform import monitoring


def test_monitoring_uses_server_snapshot_reference(monkeypatch):
    project_id, snapshot_id = uuid4(), uuid4()
    workspace = Mock()
    workspace.search_project.return_value = [SimpleNamespace(id=project_id)]
    workspace.add_run.return_value = SimpleNamespace(id=snapshot_id)
    monkeypatch.setattr(monitoring, "RemoteWorkspace", lambda _: workspace)
    result = monitoring.publish("http://workspace.example")
    assert result["snapshot_id"] == str(snapshot_id)
    assert result["project_id"] == str(project_id)
    workspace.create_project.assert_not_called()
    # Real Evidently report serialization must contain computed results.
    snapshot = workspace.add_run.call_args.args[1]
    assert snapshot.dump_dict()["metric_results"]
