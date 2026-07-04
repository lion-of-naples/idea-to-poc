"""package_poc.py — turn a working POC folder into deploy-ready, portfolio-ready artifacts.

You have a POC that runs on your machine. Chapter 9's job is the last mile:
getting it *hosted*, *documented*, and *shareable* without hand-rolling the same
boilerplate every time.

This tool takes a POC directory and produces:

  * a Cloudflare artifact set  -> wrangler.toml + a static index.html landing page
  * a Hugging Face Space set   -> app.py stub + README.md with the Space header
  * a portfolio README         -> the "what/why/how to run/how it's hosted" writeup

Architecture (same house style as the rest of the book):

  * PURE CORE  — scan_manifest, render_wrangler_toml, render_pages_index,
                 render_space_readme, render_space_app, render_portfolio_readme,
                 build_plan. These take plain data in and return plain strings /
                 dataclasses out. No disk, no network, no key. Fully unit-testable.
  * IMPURE EDGE — read_poc (reads the folder from disk) and write_plan (writes the
                 rendered files to disk) are the only functions that touch the
                 filesystem, and they are tiny and isolated.
  * INJECTABLE SEAM — the optional README polish step takes a `polisher` callable.
                 Tests pass a scripted fake; the real CLI path builds one that
                 imports `anthropic` LOCALLY, so nothing here needs a key to import
                 or to test.

Nothing is ever eval'd. Paths are validated so a POC can't write outside its target.
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
# Guardrails
# ---------------------------------------------------------------------------

MAX_FILES = 500                     # a POC folder should not be enormous
MAX_BYTES_PER_FILE = 1_000_000      # skip reading giant blobs into the manifest
DEFAULT_MODEL = "claude-sonnet-4-5"

# Files/dirs we never treat as part of the shippable POC.
IGNORE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".ruff_cache", "node_modules", ".idea", "dist", "build",
    "ship_out", ".mypy_cache",
}
IGNORE_SUFFIXES = (".pyc", ".pyo", ".env", ".key", ".pem")

# Text extensions we're happy to sniff for entry-point detection.
CODE_SUFFIXES = (".py", ".js", ".ts", ".html")

# The seam: given a spec + a draft, return polished prose. Injectable.
Polisher = Callable[[str, str], str]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class PocFile:
    """One file discovered inside the POC folder."""
    relpath: str
    size: int


@dataclass
class Manifest:
    """What we learned about the POC by scanning it."""
    name: str
    files: list[PocFile] = field(default_factory=list)
    entrypoint: Optional[str] = None      # e.g. "app.py"
    has_requirements: bool = False
    summary: str = ""                     # one-line human summary (optional)

    @property
    def file_count(self) -> int:
        return len(self.files)


@dataclass
class RenderedFile:
    """One artifact the packager will emit, keyed by target host."""
    target: str          # "cloudflare" | "huggingface" | "portfolio"
    relpath: str         # path relative to the chosen output dir
    content: str


@dataclass
class Plan:
    """The full set of artifacts to write, plus where they go."""
    out_dir: str
    files: list[RenderedFile] = field(default_factory=list)

    @property
    def targets(self) -> list[str]:
        seen: list[str] = []
        for f in self.files:
            if f.target not in seen:
                seen.append(f.target)
        return seen


# ---------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------


def slugify(name: str) -> str:
    """Turn an arbitrary POC name into a safe, lowercase, hyphenated slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower())
    slug = slug.strip("-")
    return slug or "poc"


def _safe_relpath(relpath: str) -> str:
    """Reject absolute paths and any '..' traversal. Returns a normalized relpath.

    This is the same guard the orchestrator in Chapter 8 uses: an artifact must
    land *inside* the chosen output directory, never above it.
    """
    if not relpath or not relpath.strip():
        raise ValueError("empty path")
    p = relpath.strip().replace("\\", "/")
    if p.startswith("/") or (len(p) > 1 and p[1] == ":"):
        raise ValueError(f"absolute path not allowed: {relpath!r}")
    parts = [seg for seg in p.split("/") if seg not in ("", ".")]
    if any(seg == ".." for seg in parts):
        raise ValueError(f"path traversal not allowed: {relpath!r}")
    return "/".join(parts)


def detect_entrypoint(filenames: list[str]) -> Optional[str]:
    """Guess the app's entry point from a list of relative filenames.

    Preference order mirrors how these hosts expect to boot an app.
    """
    lowered = {f.lower(): f for f in filenames}
    for candidate in ("app.py", "main.py", "index.html", "server.py", "server.js", "index.js"):
        if candidate in lowered:
            return lowered[candidate]
    # Fall back to the first top-level code file, if any.
    for f in filenames:
        if "/" not in f and f.lower().endswith(CODE_SUFFIXES):
            return f
    return None


# ---------------------------------------------------------------------------
# PURE CORE — manifest construction (from data, not disk)
# ---------------------------------------------------------------------------


def build_manifest(name: str, raw_files: list[tuple[str, int]], summary: str = "") -> Manifest:
    """Build a Manifest from (relpath, size) pairs.

    `read_poc` produces those pairs from disk; tests hand them in directly, so
    this function never touches the filesystem.
    """
    files: list[PocFile] = []
    names: list[str] = []
    has_reqs = False
    for relpath, size in raw_files:
        safe = _safe_relpath(relpath)
        files.append(PocFile(relpath=safe, size=size))
        names.append(safe)
        if safe.lower() == "requirements.txt":
            has_reqs = True
    files.sort(key=lambda f: f.relpath)
    return Manifest(
        name=name,
        files=files,
        entrypoint=detect_entrypoint(names),
        has_requirements=has_reqs,
        summary=summary.strip(),
    )


# ---------------------------------------------------------------------------
# PURE CORE — artifact renderers
# ---------------------------------------------------------------------------


def render_wrangler_toml(manifest: Manifest) -> str:
    """Render a Cloudflare wrangler.toml for a Pages/static project.

    We target Cloudflare Pages (static assets served from ./public), which is the
    simplest host for a portfolio POC and needs no server runtime.
    """
    slug = slugify(manifest.name)
    return (
        f'name = "{slug}"\n'
        f'compatibility_date = "2024-01-01"\n'
        f'pages_build_output_dir = "public"\n'
        f"\n"
        f"# Deploy with:  wrangler pages deploy public --project-name {slug}\n"
        f"# (install once:  npm install -g wrangler  &&  wrangler login)\n"
    )


def render_pages_index(manifest: Manifest) -> str:
    """Render a minimal static landing page for Cloudflare Pages."""
    slug = slugify(manifest.name)
    summary = manifest.summary or f"A proof-of-concept: {manifest.name}."
    entry = manifest.entrypoint or "(see the repo)"
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{manifest.name}</title>\n"
        "  <style>\n"
        "    body { font-family: system-ui, sans-serif; max-width: 40rem;\n"
        "           margin: 4rem auto; padding: 0 1rem; line-height: 1.5; }\n"
        "    code { background: #f4f4f4; padding: 0.1rem 0.3rem; border-radius: 4px; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>{manifest.name}</h1>\n"
        f"  <p>{summary}</p>\n"
        f"  <p>Entry point: <code>{entry}</code></p>\n"
        f'  <p>Project slug: <code>{slug}</code></p>\n'
        "</body>\n"
        "</html>\n"
    )


def render_space_readme(manifest: Manifest) -> str:
    """Render the README.md that a Hugging Face Space needs (with its YAML header)."""
    slug = slugify(manifest.name)
    summary = manifest.summary or f"A proof-of-concept: {manifest.name}."
    return (
        "---\n"
        f"title: {manifest.name}\n"
        f"emoji: 🚀\n"
        f"colorFrom: indigo\n"
        f"colorTo: blue\n"
        f"sdk: gradio\n"
        f"app_file: app.py\n"
        f"pinned: false\n"
        "---\n"
        "\n"
        f"# {manifest.name}\n"
        "\n"
        f"{summary}\n"
        "\n"
        f"This Space was scaffolded by the Chapter 9 packager from the POC "
        f"`{slug}`.\n"
    )


def render_space_app(manifest: Manifest) -> str:
    """Render a minimal Gradio app.py stub for the Space.

    Gradio is imported inside the launch guard so importing this file never
    requires gradio to be installed.
    """
    summary = manifest.summary or f"A proof-of-concept: {manifest.name}."
    return (
        '"""Hugging Face Space entry point (scaffold).\n'
        "\n"
        f"Replace the body of `run` with a call into your POC ({manifest.entrypoint or 'your module'}).\n"
        '"""\n'
        "\n"
        "\n"
        "def run(text: str) -> str:\n"
        '    """Wire this to your POC. For now it echoes, so the Space boots green."""\n'
        f"    return f\"{manifest.name} received: {{text}}\"\n"
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    import gradio as gr  # imported locally so this file imports without gradio\n"
        "\n"
        "    demo = gr.Interface(\n"
        "        fn=run,\n"
        '        inputs=gr.Textbox(label="Input"),\n'
        '        outputs=gr.Textbox(label="Output"),\n'
        f'        title="{manifest.name}",\n'
        f'        description="{summary}",\n'
        "    )\n"
        "    demo.launch()\n"
    )


def render_portfolio_readme(manifest: Manifest, polished_summary: Optional[str] = None) -> str:
    """Render the portfolio-ready README: what it is, how to run it, how it's hosted.

    `polished_summary`, when supplied by the seam, replaces the plain summary in
    the 'What it does' section. Everything else is deterministic.
    """
    slug = slugify(manifest.name)
    summary = (polished_summary or manifest.summary or
               f"{manifest.name} is a proof-of-concept.").strip()
    run_cmd = (
        f"python {manifest.entrypoint}" if manifest.entrypoint and manifest.entrypoint.endswith(".py")
        else "see below"
    )
    reqs_line = (
        "pip install -r requirements.txt"
        if manifest.has_requirements
        else "# (no requirements.txt found — add one if the POC needs deps)"
    )
    file_list = "\n".join(f"- `{f.relpath}` ({f.size} bytes)" for f in manifest.files) or "- (none)"
    return (
        f"# {manifest.name}\n"
        "\n"
        "## What it does\n"
        "\n"
        f"{summary}\n"
        "\n"
        "## Run it locally\n"
        "\n"
        "```bash\n"
        "python -m venv .venv && source .venv/bin/activate\n"
        f"{reqs_line}\n"
        f"{run_cmd}\n"
        "```\n"
        "\n"
        "## How it's hosted\n"
        "\n"
        f"- **Cloudflare Pages** — `wrangler pages deploy public --project-name {slug}`\n"
        f"- **Hugging Face Space** — push `app.py` + `README.md` to a Gradio Space\n"
        "\n"
        "## Files\n"
        "\n"
        f"{file_list}\n"
    )


# ---------------------------------------------------------------------------
# PURE CORE — plan assembly
# ---------------------------------------------------------------------------


def build_plan(manifest: Manifest, out_dir: str, *, polished_summary: Optional[str] = None) -> Plan:
    """Assemble the full set of artifacts for both hosts + the portfolio README.

    Pure: given a manifest, returns a Plan of RenderedFiles. No disk writes here.
    """
    files = [
        RenderedFile("cloudflare", "cloudflare/wrangler.toml", render_wrangler_toml(manifest)),
        RenderedFile("cloudflare", "cloudflare/public/index.html", render_pages_index(manifest)),
        RenderedFile("huggingface", "huggingface/README.md", render_space_readme(manifest)),
        RenderedFile("huggingface", "huggingface/app.py", render_space_app(manifest)),
        RenderedFile("portfolio", "PORTFOLIO_README.md",
                     render_portfolio_readme(manifest, polished_summary=polished_summary)),
    ]
    # Validate every artifact path lands inside out_dir.
    for f in files:
        _safe_relpath(f.relpath)
    return Plan(out_dir=out_dir, files=files)


def render_plan(plan: Plan) -> str:
    """Human-readable dry-run rendering of a Plan."""
    lines = [f"Plan -> {plan.out_dir}", f"  targets: {', '.join(plan.targets)}"]
    for f in plan.files:
        lines.append(f"  [{f.target}] {f.relpath} ({len(f.content)} bytes)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# IMPURE EDGE 1 — read the POC folder from disk
# ---------------------------------------------------------------------------


def read_poc(poc_dir: str, *, name: Optional[str] = None, summary: str = "") -> Manifest:
    """Scan a POC directory on disk and return a Manifest.

    This is one of only two functions that touch the filesystem to read the POC.
    It skips ignored dirs/suffixes and enforces the file-count guardrail.
    """
    if not os.path.isdir(poc_dir):
        raise FileNotFoundError(f"POC directory not found: {poc_dir}")
    poc_dir = os.path.abspath(poc_dir)
    raw: list[tuple[str, int]] = []
    for root, dirs, filenames in os.walk(poc_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for fn in filenames:
            if fn.lower().endswith(IGNORE_SUFFIXES):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, poc_dir).replace("\\", "/")
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size > MAX_BYTES_PER_FILE:
                continue
            raw.append((rel, size))
            if len(raw) > MAX_FILES:
                raise ValueError(f"POC has more than {MAX_FILES} files; refusing to scan.")
    resolved_name = name or os.path.basename(poc_dir.rstrip("/")) or "poc"
    return build_manifest(resolved_name, raw, summary=summary)


# ---------------------------------------------------------------------------
# IMPURE EDGE 2 — write the plan to disk
# ---------------------------------------------------------------------------


def write_plan(plan: Plan) -> list[str]:
    """Write every RenderedFile in the plan under plan.out_dir. Returns paths written."""
    written: list[str] = []
    out_root = os.path.abspath(plan.out_dir)
    os.makedirs(out_root, exist_ok=True)
    for f in plan.files:
        safe = _safe_relpath(f.relpath)
        dest = os.path.join(out_root, safe)
        # Belt-and-braces: ensure the resolved path is still inside out_root.
        if os.path.commonpath([out_root, os.path.abspath(dest)]) != out_root:
            raise ValueError(f"refusing to write outside output dir: {f.relpath!r}")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(f.content)
        written.append(os.path.relpath(dest, out_root))
    return written


# ---------------------------------------------------------------------------
# IMPURE EDGE 3 — the optional model-backed README polish
# ---------------------------------------------------------------------------


def _polish_with_anthropic(manifest_summary: str, draft: str, *, model: str = DEFAULT_MODEL) -> str:
    """Real polisher: import anthropic LOCALLY and ask a model to tighten the summary.

    Never imported at module load, never touched by the tests. Requires ANTHROPIC_API_KEY.
    """
    import anthropic  # local import: no key/SDK needed to import this file or run tests

    client = anthropic.Anthropic()
    prompt = (
        "Rewrite the following proof-of-concept summary as one or two crisp, "
        "portfolio-quality sentences. Keep it factual and concrete.\n\n"
        f"Current summary: {manifest_summary!r}\n\n"
        f"Draft README section:\n{draft}"
    )
    msg = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts).strip() or manifest_summary


# ---------------------------------------------------------------------------
# Orchestration (pure wiring over the seam)
# ---------------------------------------------------------------------------


def package(
    manifest: Manifest,
    out_dir: str,
    *,
    polisher: Optional[Polisher] = None,
) -> Plan:
    """Build the artifact Plan for a manifest, optionally polishing the summary.

    `polisher(summary, draft) -> str` is the injectable seam. In tests it's a
    scripted fake; the CLI passes a real one only when --polish is set.
    """
    polished: Optional[str] = None
    if polisher is not None:
        draft = render_portfolio_readme(manifest)
        polished = polisher(manifest.summary, draft)
    return build_plan(manifest, out_dir, polished_summary=polished)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="package_poc",
        description="Turn a POC folder into deploy-ready (Cloudflare + Hugging Face) "
                    "and portfolio-ready artifacts.",
    )
    p.add_argument("poc_dir", help="path to the POC folder to package")
    p.add_argument("--name", default=None, help="override the project name (default: folder name)")
    p.add_argument("--summary", default="", help="one-line summary for the README/landing page")
    p.add_argument("--out", default="ship_out", help="output directory for artifacts (default: ship_out)")
    p.add_argument("--polish", action="store_true",
                   help="polish the README summary with a model (needs ANTHROPIC_API_KEY)")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"model for --polish (default: {DEFAULT_MODEL})")
    p.add_argument("--dry-run", action="store_true", help="print the plan; do not write files")
    p.add_argument("--trace", action="store_true", help="print the manifest as JSON to stderr")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    try:
        manifest = read_poc(args.poc_dir, name=args.name, summary=args.summary)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.trace:
        print(json.dumps(dataclasses.asdict(manifest), indent=2), file=sys.stderr)

    polisher: Optional[Polisher] = None
    if args.polish:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("error: --polish needs ANTHROPIC_API_KEY in the environment.", file=sys.stderr)
            return 1
        polisher = lambda summary, draft: _polish_with_anthropic(summary, draft, model=args.model)

    try:
        plan = package(manifest, args.out, polisher=polisher)
    except Exception as exc:  # noqa: BLE001 - surface any polish/render failure cleanly
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(render_plan(plan))
        return 0

    written = write_plan(plan)
    print(f"Wrote {len(written)} artifacts to {args.out}/ for: {', '.join(plan.targets)}")
    for w in written:
        print(f"  {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
