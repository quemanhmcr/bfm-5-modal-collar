import pytest

from bfm5.tcz1 import assert_remote_femm_execution


def test_local_femm_is_rejected(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(RuntimeError, match="Local FEMM execution is disabled"):
        assert_remote_femm_execution()


def test_github_actions_femm_is_allowed(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert_remote_femm_execution() is None
