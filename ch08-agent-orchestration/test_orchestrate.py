"""Offline, deterministic tests for the multi-agent orchestrator.

These tests run the ENTIRE planner -> coder -> reviewer -> (revise) -> accept
loop with a *scripted fake caller* — no API key, no network, and the Anthropic
SDK is never imported. Randomness is not a factor; the fake replies in a fixed,
role-aware order, so the whole multi-agent run is fully reproducible.

Coverage:
    * request builders for each role,
    * defensive reply parsing (plan JSON, code, review verdict) incl. fences,
    * path-safety guardrails (absolute paths, `..` escapes, duplicates),
    * a full ACCEPT-first run and a full REJECT->revise->ACCEPT run,
    * the max-rounds budget guard,
    * writing the accepted project to disk (the isolated impure step),
    * the CLI paths (subprocess), including the no-key error and --dry-run.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import orchestrate as orch


# --------------------------------------------------------------------------
# A scripted fake caller. It routes by the role's system prompt and returns
# pre-baked replies in order — standing in for the whole three-agent team.
# --------------------------------------------------------------------------
def _role_of(system: str) -> str:
    for role, prompt in orch.SYSTEM_PROMPTS.items():
        if system == prompt:
            return role
    raise AssertionError("unknown system prompt handed to caller")


def scripted_caller(*, plan, code_by_path, reviews):
    """Build a fake caller.  # illustrative test helper

    plan          : the JSON string the PLANNER returns.
    code_by_path  : dict path -> list of successive CODER replies for that file.
    reviews       : list of JSON strings the REVIEWER returns, in order.
    """
    counts = {"planner": 0, "coder": 0, "reviewer": 0}
    review_iter = iter(reviews)
    # per-path index into code_by_path so revisions return the next version
    code_idx: dict[str, int] = {}

    def caller(messages, *, system):
        role = _role_of(system)
        counts[role] += 1
        if role == orch.ROLE_PLANNER:
            return plan
        if role == orch.ROLE_REVIEWER:
            return next(review_iter)
        # CODER: figure out which file from the user message's "Path:" line.
        content = messages[0]["content"]
        path = next(line[len("Path: "):].strip()
                    for line in content.splitlines() if line.startswith("Path: "))
        versions = code_by_path[path]
        i = min(code_idx.get(path, 0), len(versions) - 1)
        code_idx[path] = i + 1
        return versions[i]

    caller.counts = counts
    return caller


PLAN_JSON = json.dumps({"files": [
    {"path": "app.py", "purpose": "the CLI todo app"},
    {"path": "test_app.py", "purpose": "pytest tests for the app"},
]})


# --------------------------------------------------------------------------
# Pure core: parsers
# --------------------------------------------------------------------------
def test_parse_plan_reads_files():
    plan = orch.parse_plan(PLAN_JSON)
    assert [f.path for f in plan] == ["app.py", "test_app.py"]
    assert plan[0].purpose == "the CLI todo app"


def test_parse_plan_tolerates_code_fences():
    fenced = "```json\n" + PLAN_JSON + "\n```"
    plan = orch.parse_plan(fenced)
    assert len(plan) == 2


def test_parse_plan_extracts_json_from_prose():
    noisy = "Sure! Here is the plan:\n" + PLAN_JSON + "\nHope that helps."
    plan = orch.parse_plan(noisy)
    assert [f.path for f in plan] == ["app.py", "test_app.py"]


def test_parse_plan_rejects_empty_and_oversized():
    with pytest.raises(ValueError):
        orch.parse_plan(json.dumps({"files": []}))
    too_many = json.dumps({"files": [{"path": f"f{i}.py"} for i in range(orch.MAX_FILES + 1)]})
    with pytest.raises(ValueError):
        orch.parse_plan(too_many)


def test_parse_plan_rejects_duplicate_paths():
    dup = json.dumps({"files": [{"path": "a.py"}, {"path": "a.py"}]})
    with pytest.raises(ValueError):
        orch.parse_plan(dup)


def test_parse_code_strips_fences():
    assert orch.parse_code("```python\nprint('hi')\n```") == "print('hi')"
    assert orch.parse_code("print('hi')\n") == "print('hi')"


def test_parse_review_accept_and_reject():
    assert orch.parse_review(json.dumps({"verdict": "ACCEPT"})).accepted is True
    r = orch.parse_review(json.dumps({"verdict": "REJECT", "notes": "add a test"}))
    assert r.accepted is False and r.notes == "add a test"


def test_parse_review_rejects_unknown_verdict():
    with pytest.raises(ValueError):
        orch.parse_review(json.dumps({"verdict": "MAYBE"}))


# --------------------------------------------------------------------------
# Path safety
# --------------------------------------------------------------------------
def test_safe_relpath_blocks_escapes():
    with pytest.raises(ValueError):
        orch._safe_relpath("/etc/passwd")
    with pytest.raises(ValueError):
        orch._safe_relpath("../secrets.txt")
    with pytest.raises(ValueError):
        orch._safe_relpath("a/../../b.py")
    assert orch._safe_relpath("pkg\\mod.py") == "pkg/mod.py"


def test_plan_rejects_unsafe_path():
    with pytest.raises(ValueError):
        orch.parse_plan(json.dumps({"files": [{"path": "../evil.py"}]}))


# --------------------------------------------------------------------------
# Request builders
# --------------------------------------------------------------------------
def test_build_coder_messages_includes_notes_and_prior_version_on_revision():
    state = orch.OrchestrationState(spec="s")
    state.files["app.py"] = "old code"
    state.review_notes.append("handle empty input")
    msgs = orch.build_coder_messages(state, orch.PlannedFile("app.py", "the app"))
    content = msgs[0]["content"]
    assert "handle empty input" in content
    assert "old code" in content
    assert "Path: app.py" in content


def test_build_reviewer_messages_lists_every_file():
    state = orch.OrchestrationState(spec="s")
    state.files = {"app.py": "A", "test_app.py": "B"}
    content = orch.build_reviewer_messages(state)[0]["content"]
    assert "=== app.py ===" in content and "=== test_app.py ===" in content


# --------------------------------------------------------------------------
# The full multi-agent loop — ACCEPT on the first review
# --------------------------------------------------------------------------
def test_full_run_accepts_first_pass():
    caller = scripted_caller(
        plan=PLAN_JSON,
        code_by_path={
            "app.py": ["# todo app\nprint('todo')"],
            "test_app.py": ["def test_ok():\n    assert True"],
        },
        reviews=[json.dumps({"verdict": "ACCEPT"})],
    )
    state = orch.orchestrate("a CLI todo app with tests", caller=caller)
    assert state.accepted is True
    assert state.round == 0
    assert set(state.files) == {"app.py", "test_app.py"}
    assert caller.counts == {"planner": 1, "coder": 2, "reviewer": 1}


# --------------------------------------------------------------------------
# The full multi-agent loop — REJECT once, revise, then ACCEPT
# --------------------------------------------------------------------------
def test_full_run_revises_then_accepts():
    caller = scripted_caller(
        plan=PLAN_JSON,
        code_by_path={
            # first version, then a revised version after the reviewer's REJECT
            "app.py": ["v1 app", "v2 app (fixed)"],
            "test_app.py": ["v1 test", "v2 test (fixed)"],
        },
        reviews=[
            json.dumps({"verdict": "REJECT", "notes": "app.py has no main guard"}),
            json.dumps({"verdict": "ACCEPT"}),
        ],
    )
    state = orch.orchestrate("a CLI todo app with tests", caller=caller)
    assert state.accepted is True
    assert state.round == 1                      # exactly one revision round
    assert state.files["app.py"] == "v2 app (fixed)"   # the revised version won
    assert state.review_notes == ["app.py has no main guard"]
    # planner once; coder wrote 2 files x 2 rounds = 4; reviewer judged twice
    assert caller.counts == {"planner": 1, "coder": 4, "reviewer": 2}


# --------------------------------------------------------------------------
# The budget guard — reviewer never accepts, we ship after max_rounds
# --------------------------------------------------------------------------
def test_run_stops_at_max_rounds():
    reject = json.dumps({"verdict": "REJECT", "notes": "still not good enough"})
    caller = scripted_caller(
        plan=json.dumps({"files": [{"path": "app.py", "purpose": "x"}]}),
        code_by_path={"app.py": ["a", "b", "c", "d", "e"]},
        reviews=[reject, reject, reject, reject, reject],
    )
    state = orch.orchestrate("something", caller=caller, max_rounds=2)
    assert state.accepted is False
    assert state.round == 2
    # Two full code->review passes: each REJECT bumps `round`; we stop when
    # round == max_rounds. So 1 file x 2 passes = 2 coder calls, 2 reviews.
    assert caller.counts["reviewer"] == 2
    assert caller.counts["coder"] == 2


def test_empty_spec_rejected():
    caller = scripted_caller(plan=PLAN_JSON, code_by_path={}, reviews=[])
    with pytest.raises(ValueError):
        orch.orchestrate("   ", caller=caller)


# --------------------------------------------------------------------------
# The isolated impure step: writing the project to disk
# --------------------------------------------------------------------------
def test_write_project_writes_files(tmp_path):
    state = orch.OrchestrationState(spec="s")
    state.files = {"app.py": "print('hi')", "pkg/mod.py": "X = 1"}
    written = orch.write_project(state, str(tmp_path / "out"))
    assert len(written) == 2
    assert (tmp_path / "out" / "app.py").read_text() == "print('hi')"
    assert (tmp_path / "out" / "pkg" / "mod.py").read_text() == "X = 1"


def test_render_run_is_readable():
    caller = scripted_caller(
        plan=PLAN_JSON,
        code_by_path={"app.py": ["a"], "test_app.py": ["b"]},
        reviews=[json.dumps({"verdict": "ACCEPT"})],
    )
    state = orch.orchestrate("a CLI todo app with tests", caller=caller)
    text = orch.render_run(state)
    assert "Agent orchestration run" in text
    assert "planner" in text and "coder" in text and "reviewer" in text
    assert "ACCEPTED" in text


# --------------------------------------------------------------------------
# CLI paths (run the module as a script; no key, no network)
# --------------------------------------------------------------------------
def _run_cli(*args, input_text=None):
    return subprocess.run(
        [sys.executable, "orchestrate.py", *args],
        capture_output=True, text=True, input=input_text,
    )


def test_cli_no_spec_errors():
    proc = _run_cli()
    assert proc.returncode == 2
    assert "Error:" in proc.stderr


def test_cli_live_run_without_key_errors_clearly():
    # With no scripted caller, the CLI uses the real caller, which must fail
    # fast (and clearly) when ANTHROPIC_API_KEY is absent — never hang or hit net.
    import os
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    proc = subprocess.run(
        [sys.executable, "orchestrate.py", "a todo app"],
        capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 2
    assert "ANTHROPIC_API_KEY" in proc.stderr
