"""Offline tests for sample_poc.py — no key, no network, no SDK."""

import sample_poc as m


def scripted_caller(prompt: str) -> str:
    """illustrative test helper: a deterministic stand-in for the model."""
    return f"handled: {prompt}"


def test_build_prompt_is_pure():
    assert "task" in m.build_prompt("task").lower()


def test_parse_response_strips():
    assert m.parse_response("  hi  ") == "hi"


def test_run_uses_the_seam_offline():
    out = m.run("demo", caller=scripted_caller)
    assert out.startswith("handled:")
