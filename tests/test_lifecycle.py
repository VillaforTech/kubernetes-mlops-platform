import json
import stat
from unittest.mock import Mock

import pytest

from mlops_platform import cli


def test_generated_credentials_are_private_and_stable(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "LOCAL", tmp_path)
    first = cli.credentials()
    second = cli.credentials()
    assert first == second
    assert len(set(first.values())) == 3
    assert stat.S_IMODE((tmp_path / "credentials.json").stat().st_mode) == 0o600


def test_unsafe_credential_permissions_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "LOCAL", tmp_path)
    cli.credentials()
    (tmp_path / "credentials.json").chmod(0o644)
    with pytest.raises(RuntimeError, match="owner-only"):
        cli.credentials()


def test_kubectl_always_has_project_config_and_context(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "LOCAL", tmp_path)
    mock = Mock(return_value="")
    monkeypatch.setattr(cli, "command", mock)
    cli.kubectl("get", "pods")
    args = mock.call_args.args[0]
    assert args[args.index("--kubeconfig") + 1] == str(tmp_path / "kubeconfig")
    assert args[args.index("--context") + 1] == "kind-mlops-platform"
    assert args[args.index("--namespace") + 1] == "mlops"


def test_teardown_requires_exact_target_before_any_command(monkeypatch):
    command = Mock()
    monkeypatch.setattr(cli, "command", command)
    with pytest.raises(RuntimeError, match="Deletion requires"):
        cli.down("yes")
    command.assert_not_called()


@pytest.mark.parametrize("labels", [{}, {"portfolio.mlops/owner": "different-owner"}])
def test_foreign_cluster_is_rejected(labels, monkeypatch):
    monkeypatch.setattr(cli, "state", lambda: {"owner": "my-owner"})
    monkeypatch.setattr(
        cli, "kubectl", lambda *args: json.dumps({"items": [{"metadata": {"labels": labels}}]})
    )
    with pytest.raises(RuntimeError, match="ownership"):
        cli.verify_owner()


def test_empty_cluster_is_rejected(monkeypatch):
    monkeypatch.setattr(cli, "state", lambda: {"owner": "my-owner"})
    monkeypatch.setattr(cli, "kubectl", lambda *args: '{"items": []}')
    with pytest.raises(RuntimeError, match="ownership"):
        cli.verify_owner()


def test_secret_payload_not_echoed_in_errors(monkeypatch):
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda *a, **k: Mock(returncode=1, stdout="sensitive-output", stderr="sensitive-error"),
    )
    with pytest.raises(RuntimeError) as error:
        cli.command(["kubectl", "apply"], payload="sensitive-input")
    assert "sensitive" not in str(error.value)
