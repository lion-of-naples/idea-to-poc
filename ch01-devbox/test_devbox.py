"""Tests for devbox — Chapter 1 POC.

Run with:  pytest -q
"""

import devbox


def test_readiness_returns_expected_shape():
    report = devbox.readiness()
    assert isinstance(report, dict)
    assert "python" in report
    assert "tools" in report
    assert "editor" in report
    assert "keys" in report


def test_python_version_is_nonempty_string():
    assert isinstance(report_python := devbox.python_version(), str)
    assert report_python  # non-empty
    assert report_python.count(".") >= 1  # looks like X.Y or X.Y.Z


def test_keys_present_returns_only_booleans():
    keys = devbox.keys_present()
    assert isinstance(keys, dict)
    assert set(keys.keys()) == set(devbox.PROVIDER_KEYS)
    assert all(isinstance(v, bool) for v in keys.values())


def test_tools_present_returns_only_booleans():
    tools = devbox.tools_present()
    assert isinstance(tools, dict)
    assert all(isinstance(v, bool) for v in tools.values())


def test_keys_present_never_exposes_values(monkeypatch):
    """Presence detection must be based on truthiness, never the value itself."""
    monkeypatch.setenv("OPENAI_API_KEY", "super-secret-value")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    keys = devbox.keys_present()
    assert keys["OPENAI_API_KEY"] is True
    assert keys["ANTHROPIC_API_KEY"] is False
    # The report must not contain the secret value anywhere.
    assert "super-secret-value" not in devbox.render(devbox.readiness())


def test_is_ready_requires_git():
    ready_report = {"python": "3.11.0", "tools": {"git": True}, "editor": None, "keys": {}}
    not_ready_report = {"python": "3.11.0", "tools": {"git": False}, "editor": None, "keys": {}}
    assert devbox.is_ready(ready_report) is True
    assert devbox.is_ready(not_ready_report) is False


def test_render_produces_report_header():
    output = devbox.render(devbox.readiness())
    assert "AM I READY TO BUILD?" in output
    assert "Verdict:" in output
