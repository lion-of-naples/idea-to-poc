"""Offline tests for package_poc.py.

Every test runs with NO network, NO key, NO third-party SDK. The optional
model-polish path is exercised only through a scripted fake `polisher` seam, so
`anthropic` is never imported here.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

import package_poc as pp


# --------------------------------------------------------------------------- #
# illustrative test helper: a scripted polisher that records what it saw
# --------------------------------------------------------------------------- #


class ScriptedPolisher:
    """Stands in for the real Anthropic-backed polisher. Deterministic, offline."""

    def __init__(self, reply: str = "A polished, portfolio-ready sentence."):
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def __call__(self, summary: str, draft: str) -> str:
        self.calls.append((summary, draft))
        return self.reply


# --------------------------------------------------------------------------- #
# slugify / path safety
# --------------------------------------------------------------------------- #


def test_slugify_basic():
    assert pp.slugify("My Cool POC!") == "my-cool-poc"


def test_slugify_empty_falls_back():
    assert pp.slugify("   ") == "poc"
    assert pp.slugify("!!!") == "poc"


def test_safe_relpath_accepts_normal():
    assert pp._safe_relpath("cloudflare/public/index.html") == "cloudflare/public/index.html"
    assert pp._safe_relpath("./a/./b.txt") == "a/b.txt"


def test_safe_relpath_rejects_absolute():
    with pytest.raises(ValueError):
        pp._safe_relpath("/etc/passwd")


def test_safe_relpath_rejects_traversal():
    with pytest.raises(ValueError):
        pp._safe_relpath("../../secrets.txt")


def test_safe_relpath_rejects_empty():
    with pytest.raises(ValueError):
        pp._safe_relpath("   ")


# --------------------------------------------------------------------------- #
# entrypoint detection
# --------------------------------------------------------------------------- #


def test_detect_entrypoint_prefers_app_py():
    assert pp.detect_entrypoint(["main.py", "app.py", "util.py"]) == "app.py"


def test_detect_entrypoint_index_html():
    assert pp.detect_entrypoint(["style.css", "index.html"]) == "index.html"


def test_detect_entrypoint_falls_back_to_first_top_level_code():
    assert pp.detect_entrypoint(["sub/deep.py", "widget.js"]) == "widget.js"


def test_detect_entrypoint_none_when_no_code():
    assert pp.detect_entrypoint(["notes.txt", "data.csv"]) is None


# --------------------------------------------------------------------------- #
# build_manifest (pure, from data)
# --------------------------------------------------------------------------- #


def test_build_manifest_sorts_and_flags_requirements():
    m = pp.build_manifest(
        "Widget",
        [("app.py", 10), ("requirements.txt", 5), ("readme.md", 3)],
        summary="does a thing",
    )
    assert m.name == "Widget"
    assert m.file_count == 3
    assert [f.relpath for f in m.files] == ["app.py", "readme.md", "requirements.txt"]
    assert m.has_requirements is True
    assert m.entrypoint == "app.py"
    assert m.summary == "does a thing"


def test_build_manifest_no_requirements():
    m = pp.build_manifest("X", [("index.html", 1)])
    assert m.has_requirements is False
    assert m.entrypoint == "index.html"


def test_build_manifest_rejects_bad_paths():
    with pytest.raises(ValueError):
        pp.build_manifest("X", [("../evil.py", 1)])


# --------------------------------------------------------------------------- #
# renderers (pure)
# --------------------------------------------------------------------------- #


def test_render_wrangler_toml_has_slug_and_output_dir():
    m = pp.build_manifest("My POC", [("index.html", 1)])
    toml = pp.render_wrangler_toml(m)
    assert 'name = "my-poc"' in toml
    assert 'pages_build_output_dir = "public"' in toml
    assert "wrangler pages deploy" in toml


def test_render_pages_index_includes_summary_and_entry():
    m = pp.build_manifest("Alpha", [("app.py", 1)], summary="Classifies text.")
    html = pp.render_pages_index(m)
    assert "<title>Alpha</title>" in html
    assert "Classifies text." in html
    assert "app.py" in html


def test_render_space_readme_has_yaml_header():
    m = pp.build_manifest("Beta", [("app.py", 1)], summary="Does beta things.")
    readme = pp.render_space_readme(m)
    assert readme.startswith("---\n")
    assert "sdk: gradio" in readme
    assert "app_file: app.py" in readme
    assert "Does beta things." in readme


def test_render_space_app_imports_gradio_locally():
    m = pp.build_manifest("Gamma", [("app.py", 1)])
    app = pp.render_space_app(m)
    # gradio must be imported inside the launch guard, not at module top.
    assert "import gradio" in app
    assert app.index("__main__") < app.index("import gradio")
    assert "def run(" in app


def test_render_portfolio_readme_sections_and_run_cmd():
    m = pp.build_manifest("Delta", [("app.py", 12), ("requirements.txt", 3)], summary="Delta POC.")
    md = pp.render_portfolio_readme(m)
    assert "## What it does" in md
    assert "## Run it locally" in md
    assert "## How it's hosted" in md
    assert "pip install -r requirements.txt" in md
    assert "python app.py" in md
    assert "`app.py` (12 bytes)" in md


def test_render_portfolio_readme_uses_polished_summary():
    m = pp.build_manifest("Delta", [("app.py", 1)], summary="plain")
    md = pp.render_portfolio_readme(m, polished_summary="SHINY SUMMARY")
    assert "SHINY SUMMARY" in md
    assert "plain" not in md.split("## Run it")[0].replace("plain summary", "")


# --------------------------------------------------------------------------- #
# build_plan / render_plan (pure)
# --------------------------------------------------------------------------- #


def test_build_plan_covers_all_three_targets():
    m = pp.build_manifest("Echo", [("app.py", 1)])
    plan = pp.build_plan(m, "ship_out")
    assert plan.targets == ["cloudflare", "huggingface", "portfolio"]
    relpaths = {f.relpath for f in plan.files}
    assert "cloudflare/wrangler.toml" in relpaths
    assert "cloudflare/public/index.html" in relpaths
    assert "huggingface/README.md" in relpaths
    assert "huggingface/app.py" in relpaths
    assert "PORTFOLIO_README.md" in relpaths


def test_render_plan_is_human_readable():
    m = pp.build_manifest("Echo", [("app.py", 1)])
    text = pp.render_plan(pp.build_plan(m, "ship_out"))
    assert "Plan -> ship_out" in text
    assert "[cloudflare]" in text
    assert "[portfolio]" in text


# --------------------------------------------------------------------------- #
# package() seam wiring
# --------------------------------------------------------------------------- #


def test_package_without_polisher_uses_plain_summary():
    m = pp.build_manifest("Foxtrot", [("app.py", 1)], summary="plain summary")
    plan = pp.package(m, "ship_out")
    portfolio = next(f for f in plan.files if f.target == "portfolio")
    assert "plain summary" in portfolio.content


def test_package_with_polisher_replaces_summary():
    m = pp.build_manifest("Foxtrot", [("app.py", 1)], summary="plain summary")
    fake = ScriptedPolisher(reply="POLISHED!!")
    plan = pp.package(m, "ship_out", polisher=fake)
    portfolio = next(f for f in plan.files if f.target == "portfolio")
    assert "POLISHED!!" in portfolio.content
    # the seam saw the manifest summary and a draft
    assert len(fake.calls) == 1
    assert fake.calls[0][0] == "plain summary"
    assert "## What it does" in fake.calls[0][1]


# --------------------------------------------------------------------------- #
# read_poc / write_plan (isolated impure edges) — use tmp_path, no network
# --------------------------------------------------------------------------- #


def test_read_poc_scans_and_ignores(tmp_path):
    (tmp_path / "app.py").write_text("print('hi')")
    (tmp_path / "requirements.txt").write_text("requests")
    junk = tmp_path / "__pycache__"
    junk.mkdir()
    (junk / "x.pyc").write_text("nope")
    (tmp_path / "secret.env").write_text("KEY=1")
    m = pp.read_poc(str(tmp_path), name="ScanMe", summary="scanned")
    names = {f.relpath for f in m.files}
    assert "app.py" in names
    assert "requirements.txt" in names
    assert not any(n.endswith(".pyc") for n in names)
    assert "secret.env" not in names
    assert m.has_requirements is True
    assert m.entrypoint == "app.py"
    assert m.name == "ScanMe"


def test_read_poc_missing_dir_raises():
    with pytest.raises(FileNotFoundError):
        pp.read_poc("/no/such/poc/dir")


def test_write_plan_creates_all_files(tmp_path):
    m = pp.build_manifest("Golf", [("app.py", 1)], summary="golf")
    plan = pp.build_plan(m, str(tmp_path / "out"))
    written = pp.write_plan(plan)
    assert len(written) == 5
    out = tmp_path / "out"
    assert (out / "cloudflare" / "wrangler.toml").exists()
    assert (out / "cloudflare" / "public" / "index.html").exists()
    assert (out / "huggingface" / "README.md").exists()
    assert (out / "huggingface" / "app.py").exists()
    assert (out / "PORTFOLIO_README.md").exists()


def test_write_plan_rejects_traversal(tmp_path):
    m = pp.build_manifest("H", [("app.py", 1)])
    plan = pp.build_plan(m, str(tmp_path / "out"))
    plan.files.append(pp.RenderedFile("evil", "../escape.txt", "nope"))
    with pytest.raises(ValueError):
        pp.write_plan(plan)


# --------------------------------------------------------------------------- #
# CLI paths (subprocess, offline)
# --------------------------------------------------------------------------- #


def _cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, "package_poc.py", *args],
        cwd=cwd or os.path.dirname(os.path.abspath(__file__)),
        capture_output=True,
        text=True,
    )


def test_cli_help_runs():
    r = _cli("--help")
    assert r.returncode == 0
    assert "Turn a POC folder" in r.stdout


def test_cli_missing_dir_errors():
    r = _cli("/no/such/dir")
    assert r.returncode == 2
    assert "error:" in r.stderr


def test_cli_dry_run(tmp_path):
    poc = tmp_path / "poc"
    poc.mkdir()
    (poc / "app.py").write_text("print('x')")
    r = _cli(str(poc), "--summary", "demo", "--dry-run")
    assert r.returncode == 0
    assert "Plan ->" in r.stdout
    assert "[cloudflare]" in r.stdout
    # dry-run writes nothing
    assert not (tmp_path / "ship_out").exists()


def test_cli_polish_without_key_errors(tmp_path, monkeypatch):
    poc = tmp_path / "poc"
    poc.mkdir()
    (poc / "app.py").write_text("print('x')")
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    r = subprocess.run(
        [sys.executable, "package_poc.py", str(poc), "--polish", "--dry-run"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 1
    assert "ANTHROPIC_API_KEY" in r.stderr
