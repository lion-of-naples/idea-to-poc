#!/usr/bin/env python3
"""devbox — Am I ready to build?

A tiny but real proof of concept from Chapter 1 of *Idea to POC*.
It inspects the current machine and prints a clean readiness report:
the Python version, whether common developer tools are installed, which
editor CLI is available, and which AI-provider API keys are present in
the environment.

Design rule: NEVER print the value of a secret. We only report whether a
key is *present*, never what it is.

Run it:
    python3 devbox.py

Exit code is 0 if the core build tools (Python + git) are available,
otherwise 1 — so devbox can be used in a CI check.
"""

from __future__ import annotations

import os
import shutil
import sys

# Provider API keys we care about across the book. Presence only — never values.
PROVIDER_KEYS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "PERPLEXITY_API_KEY",
    "HF_TOKEN",
    "GOOGLE_API_KEY",
]

# Developer tools we check for on the PATH.
TOOLS = ["git", "node", "docker"]


def python_version() -> str:
    """Return the running Python version as 'X.Y.Z'."""
    return ".".join(str(v) for v in sys.version_info[:3])


def tools_present() -> dict[str, bool]:
    """Return {tool: is_on_PATH} for each developer tool we check."""
    return {tool: shutil.which(tool) is not None for tool in TOOLS}


def editor_cli() -> str | None:
    """Return the first available editor CLI ('cursor' or 'code'), else None."""
    return shutil.which("cursor") or shutil.which("code")


def keys_present() -> dict[str, bool]:
    """Return {ENV_VAR: is_set_and_nonempty} for each provider key.

    Only booleans are returned. Secret values are never read into the report.
    """
    return {key: bool(os.environ.get(key)) for key in PROVIDER_KEYS}


def readiness() -> dict:
    """Assemble the full readiness snapshot as a plain dict."""
    tools = tools_present()
    return {
        "python": python_version(),
        "tools": tools,
        "editor": editor_cli(),
        "keys": keys_present(),
    }


def is_ready(report: dict) -> bool:
    """Core readiness = Python is running and git is installed."""
    return bool(report["python"]) and report["tools"].get("git", False)


def render(report: dict) -> str:
    """Render the readiness snapshot as a human-friendly report string."""
    lines: list[str] = []
    lines.append("AM I READY TO BUILD?")
    lines.append("-" * 28)
    lines.append(f"  Python : {report['python']}")

    for tool, present in report["tools"].items():
        note = ""
        if tool == "node" and not present:
            note = "  (ok for Python-only POCs)"
        if tool == "docker" and not present:
            note = "  (optional)"
        lines.append(f"  {tool:7}: {'yes' if present else 'MISSING'}{note}")

    lines.append(f"  editor : {report['editor'] or 'no code/cursor CLI on PATH'}")
    lines.append("  API keys detected:")
    for name, present in report["keys"].items():
        lines.append(f"    - {name:20} {'present' if present else '—'}")

    lines.append("-" * 28)
    verdict = "READY ✅" if is_ready(report) else "NOT READY — install git ❌"
    lines.append(f"  Verdict: {verdict}")
    return "\n".join(lines)


def main() -> int:
    report = readiness()
    print(render(report))
    return 0 if is_ready(report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
