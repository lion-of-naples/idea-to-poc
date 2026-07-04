"""Offline tests for method_kit.py.

No network, no key, no third-party SDK. The optional advisor path is exercised
only through a scripted fake `advisor` seam, so `anthropic` is never imported here.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

import method_kit as mk


# --------------------------------------------------------------------------- #
# illustrative test helpers
# --------------------------------------------------------------------------- #


class ScriptedAdvisor:
    """Stands in for the real Anthropic-backed advisor. Deterministic, offline."""

    def __init__(self, reply: str = "1. Add tests.\n2. Isolate the edge."):
        self.reply = reply
        self.calls: list[str] = []

    def __call__(self, report: str) -> str:
        self.calls.append(report)
        return self.reply


def _repo(files: dict[str, str], *, name="R", readme=False, reqs=False) -> mk.RepoView:
    """Build a RepoView straight from data (no disk)."""
    rf = [mk.RepoFile(relpath=k, text=v) for k, v in files.items()]
    return mk.RepoView(name=name, files=rf, has_readme=readme, has_requirements=reqs)


# --------------------------------------------------------------------------- #
# slug / module name / path safety
# --------------------------------------------------------------------------- #


def test_slugify():
    assert mk.slugify("My Cool POC!") == "my-cool-poc"
    assert mk.slugify("  ") == "poc"


def test_module_name_valid():
    assert mk.module_name("My Cool POC") == "my_cool_poc"
    assert mk.module_name("123 go") == "poc_123_go"
    assert mk.module_name("!!!") == "poc"


def test_safe_relpath_rejects_absolute_and_traversal():
    assert mk._safe_relpath("./a/b.py") == "a/b.py"
    with pytest.raises(ValueError):
        mk._safe_relpath("/etc/passwd")
    with pytest.raises(ValueError):
        mk._safe_relpath("../x")


# --------------------------------------------------------------------------- #
# RepoView properties
# --------------------------------------------------------------------------- #


def test_repoview_partitions_py_and_tests():
    repo = _repo({"src.py": "x=1", "test_src.py": "def test_x(): pass", "notes.txt": "hi"})
    assert {f.relpath for f in repo.py_files} == {"src.py", "test_src.py"}
    assert [f.relpath for f in repo.test_files] == ["test_src.py"]
    assert [f.relpath for f in repo.source_files] == ["src.py"]


# --------------------------------------------------------------------------- #
# lint rules
# --------------------------------------------------------------------------- #


def test_check_has_tests():
    assert mk.check_has_tests(_repo({"test_a.py": "x"})).passed is True
    assert mk.check_has_tests(_repo({"a.py": "x"})).passed is False


def test_check_has_readme_and_requirements():
    assert mk.check_has_readme(_repo({}, readme=True)).passed is True
    assert mk.check_has_readme(_repo({})).passed is False
    assert mk.check_has_requirements(_repo({}, reqs=True)).passed is True
    assert mk.check_has_requirements(_repo({})).passed is False


def test_check_edges_isolated_flags_top_level_sdk():
    bad = _repo({"a.py": "import anthropic\n\ndef f(): pass\n"})
    assert mk.check_edges_isolated(bad).passed is False
    assert "a.py" in mk.check_edges_isolated(bad).detail


def test_check_edges_isolated_allows_local_import():
    good = _repo({"a.py": "def f():\n    import anthropic\n    return anthropic\n"})
    assert mk.check_edges_isolated(good).passed is True


def test_check_edges_isolated_ignores_test_files():
    # A test file importing an SDK at top-level should not fail the SOURCE rule.
    repo = _repo({"test_a.py": "import openai\n"})
    assert mk.check_edges_isolated(repo).passed is True


def test_check_seam_injectable_detects_caller_param():
    good = _repo({"a.py": "def run(task, *, caller):\n    return caller(task)\n"})
    assert mk.check_seam_injectable(good).passed is True


def test_check_seam_injectable_absent():
    bad = _repo({"a.py": "def run(task):\n    return task\n"})
    assert mk.check_seam_injectable(bad).passed is False


def test_check_no_eval():
    assert mk.check_no_eval(_repo({"a.py": "y = eval('1+1')\n"})).passed is False
    assert mk.check_no_eval(_repo({"a.py": "y = 1 + 1\n"})).passed is True


# --------------------------------------------------------------------------- #
# scoring + report
# --------------------------------------------------------------------------- #


def test_score_repo_all_pass():
    repo = _repo(
        {
            "core.py": "def run(task, *, caller):\n    return caller(task)\n",
            "test_core.py": "def test_x(): pass\n",
        },
        readme=True, reqs=True,
    )
    card = mk.score_repo(repo)
    assert card.total == 6
    assert card.passed_count == 6
    assert card.score == 100


def test_score_repo_all_fail():
    repo = _repo({"bad.py": "import anthropic\n\ndef f():\n    return eval('1')\n"})
    card = mk.score_repo(repo)
    assert card.passed_count == 0
    assert card.score == 0


def test_render_report_lists_every_rule():
    repo = _repo({"a.py": "x=1"})
    text = mk.render_report(mk.score_repo(repo))
    assert "Method scorecard for: R" in text
    for rule in ("has_tests", "has_readme", "has_requirements",
                 "edges_isolated", "seam_injectable", "no_eval"):
        assert rule in text


# --------------------------------------------------------------------------- #
# scaffold renderers
# --------------------------------------------------------------------------- #


def test_render_core_module_imports_sdk_locally():
    src = mk.render_core_module("Widget Bot")
    # anthropic must be imported inside _call_model, not at module top.
    assert "import anthropic" in src
    assert src.index("def _call_model") < src.index("import anthropic")
    assert "def run(task: str, *, caller: Caller)" in src
    assert "eval(" not in src


def test_render_test_module_uses_scripted_caller():
    t = mk.render_test_module("Widget Bot")
    assert "scripted_caller" in t
    assert "import widget_bot as m" in t
    assert "caller=scripted_caller" in t


def test_build_scaffold_is_house_pattern_compliant():
    files = {f.relpath: f.content for f in mk.build_scaffold("Widget Bot")}
    assert set(files) == {
        "widget_bot.py", "test_widget_bot.py",
        "requirements.txt", "README.md", ".gitignore",
    }
    # The scaffold it emits should itself pass every lint rule.
    repo = _repo(
        {"widget_bot.py": files["widget_bot.py"], "test_widget_bot.py": files["test_widget_bot.py"]},
        readme=True, reqs=True,
    )
    card = mk.score_repo(repo)
    assert card.score == 100, mk.render_report(card)


def test_render_scaffold_plan_lists_files():
    plan = mk.render_scaffold_plan("Widget Bot", "new_poc")
    assert "Scaffold 'Widget Bot' -> new_poc" in plan
    assert "widget_bot.py" in plan


# --------------------------------------------------------------------------- #
# lint() seam wiring
# --------------------------------------------------------------------------- #


def test_lint_without_advisor_returns_no_advice():
    repo = _repo({"a.py": "x=1"})
    card, advice = mk.lint(repo)
    assert isinstance(card, mk.Scorecard)
    assert advice is None


def test_lint_with_advisor_calls_seam_with_report():
    repo = _repo({"a.py": "x=1"})
    fake = ScriptedAdvisor(reply="do X")
    card, advice = mk.lint(repo, advisor=fake)
    assert advice == "do X"
    assert len(fake.calls) == 1
    assert "Method scorecard" in fake.calls[0]


# --------------------------------------------------------------------------- #
# impure edges — tmp_path, offline
# --------------------------------------------------------------------------- #


def test_scan_repo_reads_and_flags(tmp_path):
    (tmp_path / "core.py").write_text("def run(task, *, caller):\n    return caller(task)\n")
    (tmp_path / "test_core.py").write_text("def test_x(): pass\n")
    (tmp_path / "README.md").write_text("# hi")
    (tmp_path / "requirements.txt").write_text("pytest")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "junk.py").write_text("nope")
    repo = mk.scan_repo(str(tmp_path), name="Scanned")
    names = {f.relpath for f in repo.py_files}
    assert names == {"core.py", "test_core.py"}   # __pycache__ skipped
    assert repo.has_readme is True
    assert repo.has_requirements is True
    assert repo.name == "Scanned"


def test_scan_repo_missing_raises():
    with pytest.raises(FileNotFoundError):
        mk.scan_repo("/no/such/repo/dir")


def test_scan_then_score_round_trip(tmp_path):
    mk.write_scaffold("Round Trip", str(tmp_path / "rt"))
    repo = mk.scan_repo(str(tmp_path / "rt"))
    card = mk.score_repo(repo)
    assert card.score == 100, mk.render_report(card)


def test_write_scaffold_creates_files(tmp_path):
    written = mk.write_scaffold("Golf POC", str(tmp_path / "out"))
    assert len(written) == 5
    out = tmp_path / "out"
    assert (out / "golf_poc.py").exists()
    assert (out / "test_golf_poc.py").exists()
    assert (out / "README.md").exists()
    assert (out / "requirements.txt").exists()
    assert (out / ".gitignore").exists()


# --------------------------------------------------------------------------- #
# CLI paths (subprocess, offline)
# --------------------------------------------------------------------------- #


def _cli(*args, cwd=None, env=None):
    return subprocess.run(
        [sys.executable, "method_kit.py", *args],
        cwd=cwd or os.path.dirname(os.path.abspath(__file__)),
        capture_output=True, text=True, env=env,
    )


def test_cli_help():
    r = _cli("--help")
    assert r.returncode == 0
    assert "scaffold" in r.stdout and "lint" in r.stdout


def test_cli_scaffold_dry_run_writes_nothing(tmp_path):
    r = _cli("scaffold", "Demo POC", "--out", str(tmp_path / "x"), "--dry-run")
    assert r.returncode == 0
    assert "Scaffold 'Demo POC'" in r.stdout
    assert not (tmp_path / "x").exists()


def test_cli_scaffold_writes(tmp_path):
    r = _cli("scaffold", "Demo POC", "--out", str(tmp_path / "x"))
    assert r.returncode == 0
    assert (tmp_path / "x" / "demo_poc.py").exists()


def test_cli_lint_clean_scaffold_exits_zero(tmp_path):
    mk.write_scaffold("Clean POC", str(tmp_path / "c"))
    r = _cli("lint", str(tmp_path / "c"))
    assert r.returncode == 0
    assert "100/100" in r.stdout


def test_cli_lint_broken_exits_three(tmp_path):
    (tmp_path / "bad.py").write_text("import openai\n")
    r = _cli("lint", str(tmp_path))
    assert r.returncode == 3
    assert "FAIL" in r.stdout


def test_cli_lint_missing_dir_exits_two():
    r = _cli("lint", "/no/such/dir")
    assert r.returncode == 2
    assert "error:" in r.stderr


def test_cli_lint_advise_without_key_exits_one(tmp_path):
    (tmp_path / "a.py").write_text("x=1")
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    r = _cli("lint", str(tmp_path), "--advise", env=env)
    assert r.returncode == 1
    assert "ANTHROPIC_API_KEY" in r.stderr
