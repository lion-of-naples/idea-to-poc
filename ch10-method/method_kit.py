"""method_kit.py — the repeatable POC method, as a tool you point at your own repos.

Nine chapters each shipped a domain POC. They all shared one shape:

  * a PURE CORE of functions that turn data into data (no disk, no network),
  * one or two ISOLATED IMPURE EDGES that touch the outside world,
  * an INJECTABLE SEAM so the one step that calls a model can be faked in tests,
  * OFFLINE TESTS that need no key, no network, no SDK to run,
  * and a README that says what it is and how to run it.

This chapter turns that method into code with two jobs:

  scaffold  — generate a new POC skeleton that already follows the house pattern
              (pure core stub + impure edge + injectable seam + offline test +
              requirements + README). Start every new idea from the finish line.

  lint      — point it at an existing repo/folder and score it against the method's
              rules (tests present? seam injectable? edges isolated? imports offline?
              README present?). Turn "is this shippable?" into a checklist you run.

Architecture (the same one it teaches):

  * PURE CORE  — the scaffold renderers (render_*), the lint rules (check_*), and
                 score_repo / render_report. Data in, data out. Fully offline-testable.
  * IMPURE EDGE — scan_repo (reads a folder) and write_scaffold (writes files) are the
                 only functions that touch the filesystem. Both validate every path.
  * INJECTABLE SEAM — the optional "advise" step takes an `advisor` callable. Tests
                 pass a scripted fake; the CLI builds a real one that imports
                 `anthropic` LOCALLY, so nothing here needs a key to import or test.

Nothing is ever eval'd. Paths are validated so a scaffold can't write outside its target.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Guardrails / constants
# ---------------------------------------------------------------------------

MAX_FILES = 2000                    # a repo we lint should not be unbounded
MAX_BYTES_PER_FILE = 2_000_000      # skip reading giant blobs into the scan
DEFAULT_MODEL = "claude-sonnet-4-5"

IGNORE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".ruff_cache", "node_modules", ".idea", "dist", "build",
    ".mypy_cache", "scaffold_out",
}
PY_SUFFIX = ".py"

# The seam: given the scorecard text, return prose advice. Injectable.
Advisor = Callable[[str], str]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RepoFile:
    """One Python file discovered in the repo, with its text kept for rule checks."""
    relpath: str
    text: str


@dataclass
class RepoView:
    """Everything the linter needs, gathered by scan_repo (pure rules read this)."""
    name: str
    files: list[RepoFile] = field(default_factory=list)
    has_readme: bool = False
    has_requirements: bool = False

    @property
    def py_files(self) -> list[RepoFile]:
        return [f for f in self.files if f.relpath.endswith(PY_SUFFIX)]

    @property
    def test_files(self) -> list[RepoFile]:
        return [f for f in self.py_files
                if os.path.basename(f.relpath).startswith("test_")]

    @property
    def source_files(self) -> list[RepoFile]:
        return [f for f in self.py_files
                if not os.path.basename(f.relpath).startswith("test_")]


@dataclass
class CheckResult:
    """The outcome of one lint rule."""
    rule: str
    passed: bool
    detail: str


@dataclass
class Scorecard:
    """The full lint result for a repo."""
    name: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def score(self) -> int:
        """Percentage of rules passed, 0-100."""
        return round(100 * self.passed_count / self.total) if self.total else 0


@dataclass
class ScaffoldFile:
    relpath: str
    content: str


# ---------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------


def slugify(name: str) -> str:
    """Lowercase, hyphenated, safe slug for a project name."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "poc"


def module_name(name: str) -> str:
    """A valid python module name derived from the project name."""
    mod = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    if not mod:
        return "poc"
    if mod[0].isdigit():
        mod = "poc_" + mod
    return mod


def _safe_relpath(relpath: str) -> str:
    """Reject absolute paths and any '..' traversal. Returns a normalized relpath."""
    if not relpath or not relpath.strip():
        raise ValueError("empty path")
    p = relpath.strip().replace("\\", "/")
    if p.startswith("/") or (len(p) > 1 and p[1] == ":"):
        raise ValueError(f"absolute path not allowed: {relpath!r}")
    parts = [seg for seg in p.split("/") if seg not in ("", ".")]
    if any(seg == ".." for seg in parts):
        raise ValueError(f"path traversal not allowed: {relpath!r}")
    return "/".join(parts)


# ---------------------------------------------------------------------------
# PURE CORE — the lint rules (each reads a RepoView, returns a CheckResult)
# ---------------------------------------------------------------------------


def check_has_tests(repo: RepoView) -> CheckResult:
    """Rule: there is at least one test_*.py file."""
    n = len(repo.test_files)
    return CheckResult(
        rule="has_tests",
        passed=n > 0,
        detail=f"{n} test file(s) found" if n else "no test_*.py files found",
    )


def check_has_readme(repo: RepoView) -> CheckResult:
    """Rule: a README is present."""
    return CheckResult(
        rule="has_readme",
        passed=repo.has_readme,
        detail="README present" if repo.has_readme else "no README found",
    )


def check_has_requirements(repo: RepoView) -> CheckResult:
    """Rule: dependencies are pinned in a requirements file."""
    return CheckResult(
        rule="has_requirements",
        passed=repo.has_requirements,
        detail="requirements.txt present" if repo.has_requirements
        else "no requirements.txt found",
    )


def check_edges_isolated(repo: RepoView) -> CheckResult:
    """Rule: SDK imports live *inside* functions (local imports), not at module top.

    The house pattern imports vendor SDKs locally so the module imports offline.
    We approximate: if a known SDK is imported at column 0 in any source file, the
    edge isn't isolated.
    """
    sdks = ("anthropic", "openai", "google", "gradio", "huggingface_hub", "cohere")
    offenders: list[str] = []
    for f in repo.source_files:
        for line in f.text.splitlines():
            stripped = line.lstrip()
            if not stripped.startswith(("import ", "from ")):
                continue
            indented = line != stripped  # top-level imports have no indent
            if indented:
                continue
            if any(re.match(rf"(import|from)\s+{re.escape(s)}\b", stripped) for s in sdks):
                offenders.append(f.relpath)
                break
    return CheckResult(
        rule="edges_isolated",
        passed=not offenders,
        detail="no vendor SDK imported at module top-level"
        if not offenders else f"top-level SDK import in: {', '.join(sorted(set(offenders)))}",
    )


def check_seam_injectable(repo: RepoView) -> CheckResult:
    """Rule: at least one source function takes an injectable seam.

    Heuristic: a def whose signature contains a keyword-only param named like a seam
    (caller / sampler / advisor / polisher / client / fn), which is how the book wires
    the impure step so tests can pass a fake.
    """
    seam_names = ("caller", "sampler", "advisor", "polisher", "seam", "fn")
    hits: list[str] = []
    pat = re.compile(r"def\s+\w+\s*\(([^)]*)\)", re.DOTALL)
    for f in repo.source_files:
        for sig in pat.findall(f.text):
            if any(re.search(rf"\b{name}\b", sig) for name in seam_names):
                hits.append(f.relpath)
                break
    return CheckResult(
        rule="seam_injectable",
        passed=bool(hits),
        detail=f"injectable seam found in: {', '.join(sorted(set(hits)))}"
        if hits else "no injectable seam parameter found (caller/sampler/advisor/...)",
    )


def check_no_eval(repo: RepoView) -> CheckResult:
    """Rule: never eval/exec generated content."""
    offenders: list[str] = []
    for f in repo.source_files:
        if re.search(r"\beval\s*\(", f.text) or re.search(r"\bexec\s*\(", f.text):
            offenders.append(f.relpath)
    return CheckResult(
        rule="no_eval",
        passed=not offenders,
        detail="no eval/exec found" if not offenders
        else f"eval/exec used in: {', '.join(sorted(set(offenders)))}",
    )


# The ordered list of rules the method enforces.
RULES: tuple[Callable[[RepoView], CheckResult], ...] = (
    check_has_tests,
    check_has_readme,
    check_has_requirements,
    check_edges_isolated,
    check_seam_injectable,
    check_no_eval,
)


# ---------------------------------------------------------------------------
# PURE CORE — scoring + report
# ---------------------------------------------------------------------------


def score_repo(repo: RepoView) -> Scorecard:
    """Run every rule against a RepoView and collect a Scorecard. Pure."""
    checks = [rule(repo) for rule in RULES]
    return Scorecard(name=repo.name, checks=checks)


def render_report(card: Scorecard) -> str:
    """Human-readable scorecard. Pure."""
    lines = [f"Method scorecard for: {card.name}",
             f"  score: {card.score}/100  ({card.passed_count}/{card.total} rules)"]
    for c in card.checks:
        mark = "PASS" if c.passed else "FAIL"
        lines.append(f"  [{mark}] {c.rule}: {c.detail}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PURE CORE — the scaffold renderers (each returns file text)
# ---------------------------------------------------------------------------


def render_core_module(name: str) -> str:
    """Render a house-pattern source module: pure core + impure edge + seam."""
    mod = module_name(name)
    return (
        f'"""{mod}.py — a POC skeleton in the house pattern.\n'
        f"\n"
        f"Fill in the pure core, keep the edge isolated, drive the seam with a fake in tests.\n"
        f'"""\n'
        f"\n"
        f"from __future__ import annotations\n"
        f"\n"
        f"from typing import Callable, Optional\n"
        f"\n"
        f"# The injectable seam: the one step that could call a model/network. Fake it in tests.\n"
        f"Caller = Callable[[str], str]\n"
        f"\n"
        f"\n"
        f"def build_prompt(task: str) -> str:\n"
        f'    """PURE: turn input into a request. No I/O."""\n'
        f"    return f\"Do this task: {{task}}\"\n"
        f"\n"
        f"\n"
        f"def parse_response(text: str) -> str:\n"
        f'    """PURE: turn a raw response into your result type. No I/O."""\n'
        f"    return text.strip()\n"
        f"\n"
        f"\n"
        f"def run(task: str, *, caller: Caller) -> str:\n"
        f'    """PURE wiring over the seam: build -> call(seam) -> parse."""\n'
        f"    prompt = build_prompt(task)\n"
        f"    raw = caller(prompt)\n"
        f"    return parse_response(raw)\n"
        f"\n"
        f"\n"
        f"def _call_model(prompt: str) -> str:\n"
        f'    """IMPURE EDGE: import the SDK LOCALLY so the module imports offline."""\n'
        f"    import anthropic  # local import: no key/SDK needed to import this file\n"
        f"\n"
        f"    client = anthropic.Anthropic()\n"
        f"    msg = client.messages.create(\n"
        f'        model="{DEFAULT_MODEL}",\n'
        f"        max_tokens=1024,\n"
        f'        messages=[{{"role": "user", "content": prompt}}],\n'
        f"    )\n"
        f'    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")\n'
        f"\n"
        f"\n"
        f'if __name__ == "__main__":\n'
        f"    import sys\n"
        f"\n"
        f"    task = \" \".join(sys.argv[1:]) or \"say hello\"\n"
        f"    print(run(task, caller=_call_model))\n"
    )


def render_test_module(name: str) -> str:
    """Render an offline test that drives the seam with a scripted fake."""
    mod = module_name(name)
    return (
        f'"""Offline tests for {mod}.py — no key, no network, no SDK."""\n'
        f"\n"
        f"import {mod} as m\n"
        f"\n"
        f"\n"
        f"def scripted_caller(prompt: str) -> str:\n"
        f'    """illustrative test helper: a deterministic stand-in for the model."""\n'
        f'    return f"handled: {{prompt}}"\n'
        f"\n"
        f"\n"
        f"def test_build_prompt_is_pure():\n"
        f'    assert "task" in m.build_prompt("task").lower()\n'
        f"\n"
        f"\n"
        f"def test_parse_response_strips():\n"
        f'    assert m.parse_response("  hi  ") == "hi"\n'
        f"\n"
        f"\n"
        f"def test_run_uses_the_seam_offline():\n"
        f'    out = m.run("demo", caller=scripted_caller)\n'
        f'    assert out.startswith("handled:")\n'
    )


def render_scaffold_readme(name: str) -> str:
    """Render the scaffold's README."""
    slug = slugify(name)
    mod = module_name(name)
    return (
        f"# {name}\n"
        f"\n"
        f"A POC scaffolded with the Chapter 10 method kit. It already follows the\n"
        f"house pattern: a pure core, one isolated impure edge, an injectable seam,\n"
        f"and offline tests.\n"
        f"\n"
        f"## Run the tests (offline)\n"
        f"\n"
        f"```bash\n"
        f"python -m venv .venv && source .venv/bin/activate\n"
        f"pip install -r requirements.txt\n"
        f"pytest -q\n"
        f"```\n"
        f"\n"
        f"## Run it (live)\n"
        f"\n"
        f"```bash\n"
        f'export ANTHROPIC_API_KEY="sk-ant-..."\n'
        f"python {mod}.py \"your task here\"\n"
        f"```\n"
        f"\n"
        f"## Next steps\n"
        f"\n"
        f"1. Replace `build_prompt` / `parse_response` with your real logic (keep them pure).\n"
        f"2. Keep the SDK import inside `_call_model` (the edge stays isolated).\n"
        f"3. Add tests that drive `run` through the scripted `caller` (never a live key).\n"
        f"\n"
        f"Project slug: `{slug}`\n"
    )


def render_scaffold_requirements() -> str:
    """Render the scaffold's requirements.txt."""
    return (
        "# scaffolded POC requirements\n"
        "anthropic>=0.39,<1.0    # imported locally in the edge, only when run live\n"
        "pytest>=8.0,<9.0        # offline tests\n"
    )


def render_scaffold_gitignore() -> str:
    """Render the scaffold's .gitignore."""
    return (
        "# --- Secrets ---\n.env\n*.key\n*.pem\n"
        "# --- Python ---\n.venv/\n__pycache__/\n*.py[cod]\n.pytest_cache/\n"
        "# --- OS ---\n.DS_Store\n"
    )


def build_scaffold(name: str) -> list[ScaffoldFile]:
    """Assemble the full scaffold file set for a new POC. Pure."""
    mod = module_name(name)
    files = [
        ScaffoldFile(f"{mod}.py", render_core_module(name)),
        ScaffoldFile(f"test_{mod}.py", render_test_module(name)),
        ScaffoldFile("requirements.txt", render_scaffold_requirements()),
        ScaffoldFile("README.md", render_scaffold_readme(name)),
        ScaffoldFile(".gitignore", render_scaffold_gitignore()),
    ]
    for f in files:
        _safe_relpath(f.relpath)
    return files


def render_scaffold_plan(name: str, out_dir: str) -> str:
    """Human-readable dry-run of a scaffold. Pure."""
    files = build_scaffold(name)
    lines = [f"Scaffold '{name}' -> {out_dir}"]
    for f in files:
        lines.append(f"  {f.relpath} ({len(f.content)} bytes)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# IMPURE EDGE 1 — scan a repo from disk into a RepoView
# ---------------------------------------------------------------------------


def scan_repo(repo_dir: str, *, name: Optional[str] = None) -> RepoView:
    """Read a folder from disk and return a RepoView. One of two disk-touching functions."""
    if not os.path.isdir(repo_dir):
        raise FileNotFoundError(f"repo directory not found: {repo_dir}")
    repo_dir = os.path.abspath(repo_dir)
    files: list[RepoFile] = []
    has_readme = False
    has_requirements = False
    count = 0
    for root, dirs, filenames in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for fn in filenames:
            rel = os.path.relpath(os.path.join(root, fn), repo_dir).replace("\\", "/")
            low = fn.lower()
            if low.startswith("readme"):
                has_readme = True
            if low == "requirements.txt":
                has_requirements = True
            if not fn.endswith(PY_SUFFIX):
                continue
            full = os.path.join(root, fn)
            try:
                if os.path.getsize(full) > MAX_BYTES_PER_FILE:
                    continue
                text = open(full, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            files.append(RepoFile(relpath=_safe_relpath(rel), text=text))
            count += 1
            if count > MAX_FILES:
                raise ValueError(f"repo has more than {MAX_FILES} python files; refusing to scan.")
    resolved = name or os.path.basename(repo_dir.rstrip("/")) or "repo"
    files.sort(key=lambda f: f.relpath)
    return RepoView(name=resolved, files=files,
                    has_readme=has_readme, has_requirements=has_requirements)


# ---------------------------------------------------------------------------
# IMPURE EDGE 2 — write a scaffold to disk
# ---------------------------------------------------------------------------


def write_scaffold(name: str, out_dir: str) -> list[str]:
    """Write the scaffold file set under out_dir. Returns paths written."""
    files = build_scaffold(name)
    out_root = os.path.abspath(out_dir)
    os.makedirs(out_root, exist_ok=True)
    written: list[str] = []
    for f in files:
        safe = _safe_relpath(f.relpath)
        dest = os.path.join(out_root, safe)
        if os.path.commonpath([out_root, os.path.abspath(dest)]) != out_root:
            raise ValueError(f"refusing to write outside output dir: {f.relpath!r}")
        d = os.path.dirname(dest)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(f.content)
        written.append(os.path.relpath(dest, out_root))
    return written


# ---------------------------------------------------------------------------
# IMPURE EDGE 3 — the optional model-backed advisor
# ---------------------------------------------------------------------------


def _advise_with_anthropic(report: str, *, model: str = DEFAULT_MODEL) -> str:
    """Real advisor: import anthropic LOCALLY and ask for next steps. Never tested."""
    import anthropic  # local import: no key/SDK needed to import this file or run tests

    client = anthropic.Anthropic()
    prompt = (
        "You are a code reviewer. Given this method scorecard for a POC repo, "
        "suggest the two or three highest-leverage next steps to make it shippable. "
        "Be concrete and brief.\n\n"
        f"{report}"
    )
    msg = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()


# ---------------------------------------------------------------------------
# Orchestration (pure wiring over the seam)
# ---------------------------------------------------------------------------


def lint(repo: RepoView, *, advisor: Optional[Advisor] = None) -> tuple[Scorecard, Optional[str]]:
    """Score a repo and, if an advisor seam is supplied, attach prose advice.

    `advisor(report) -> str` is the injectable seam. Tests pass a scripted fake;
    the CLI passes a real one only with --advise.
    """
    card = score_repo(repo)
    advice: Optional[str] = None
    if advisor is not None:
        advice = advisor(render_report(card))
    return card, advice


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="method_kit",
        description="The repeatable POC method: scaffold a house-pattern POC, or "
                    "lint an existing repo against the method's rules.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sc = sub.add_parser("scaffold", help="generate a new house-pattern POC skeleton")
    sc.add_argument("name", help="project name (e.g. 'My Cool POC')")
    sc.add_argument("--out", default="new_poc", help="output directory (default: new_poc)")
    sc.add_argument("--dry-run", action="store_true", help="print the plan; write nothing")

    ln = sub.add_parser("lint", help="score an existing repo against the method rules")
    ln.add_argument("repo_dir", help="path to the repo/folder to lint")
    ln.add_argument("--name", default=None, help="override the reported project name")
    ln.add_argument("--json", action="store_true", help="emit the scorecard as JSON")
    ln.add_argument("--advise", action="store_true",
                    help="add model-written next steps (needs ANTHROPIC_API_KEY)")
    ln.add_argument("--model", default=DEFAULT_MODEL, help=f"model for --advise (default: {DEFAULT_MODEL})")
    return p


def _cmd_scaffold(args) -> int:
    if args.dry_run:
        print(render_scaffold_plan(args.name, args.out))
        return 0
    written = write_scaffold(args.name, args.out)
    print(f"Scaffolded '{args.name}' into {args.out}/ ({len(written)} files):")
    for w in written:
        print(f"  {w}")
    return 0


def _cmd_lint(args) -> int:
    try:
        repo = scan_repo(args.repo_dir, name=args.name)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    advisor: Optional[Advisor] = None
    if args.advise:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("error: --advise needs ANTHROPIC_API_KEY in the environment.", file=sys.stderr)
            return 1
        advisor = lambda report: _advise_with_anthropic(report, model=args.model)

    try:
        card, advice = lint(repo, advisor=advisor)
    except Exception as exc:  # noqa: BLE001 - surface advisor/render failure cleanly
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(dataclasses.asdict(card), indent=2))
    else:
        print(render_report(card))
        if advice:
            print("\nNext steps (model):\n" + advice)
    # Exit non-zero if the repo failed any rule, so lint is CI-usable.
    return 0 if card.passed_count == card.total else 3


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    if args.command == "scaffold":
        return _cmd_scaffold(args)
    if args.command == "lint":
        return _cmd_lint(args)
    return 2  # pragma: no cover - argparse enforces a valid subcommand


if __name__ == "__main__":
    raise SystemExit(main())
