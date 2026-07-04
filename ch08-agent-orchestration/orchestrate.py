#!/usr/bin/env python3
"""orchestrate — coordinate a team of AI agents to build a small project for you.

Chapter 8 of *Idea to POC*. Chapter 4 built ONE agent that solved a task across
many steps. This chapter goes up a level: instead of writing the code yourself,
you write a one-line **build spec** and an *orchestrator* coordinates a small
team of role-specialized agents to produce the project for you — with minimal
hand-coding.

The team (three roles, one shared model behind one seam):

    PLANNER   — reads the spec and emits a JSON build plan: a list of files,
                each with a path and a one-line description of what it must do.
    CODER     — for each planned file, writes its full contents.
    REVIEWER  — inspects the assembled project and returns a verdict:
                ACCEPT, or REJECT with concrete revision notes. On REJECT the
                orchestrator loops back to the Coder with those notes, up to a
                bounded number of rounds (the evaluator-optimizer pattern).

When the Reviewer ACCEPTs (or the round budget is hit), the orchestrator writes
the files to disk. That directory is the deliverable: agents built it for you.

Architecture (the book's house pattern, scaled to many agents):
    * The CORE is pure and deterministic: it builds each role's request from the
      running state, parses each role's reply (plan JSON, code files, review
      verdict), decides the next role, applies file revisions, and renders the
      run transcript. No network, no I/O, no disk writes. Fully unit-tested.
    * Exactly ONE function, `_call_claude`, is impure — it sends a role's
      messages to the Anthropic API and returns text. Everything routes through
      an injectable `caller` seam, so a scripted fake drives the ENTIRE
      multi-agent loop in tests with no API key and no network.
    * Writing the accepted project to disk is a second small, isolated impure
      step (`write_project`), kept out of the decision loop so the loop stays pure.

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."            # only needed for LIVE runs
    python3 orchestrate.py "a CLI todo app in one Python file with tests"
    python3 orchestrate.py --spec-file sample_spec.txt --out build_out --trace
    echo "a function that validates emails, plus pytest tests" | python3 orchestrate.py -
    python3 orchestrate.py --spec-file sample_spec.txt --dry-run    # plan + code, don't write

The tests run the full PLANNER->CODER->REVIEWER->(revise)->ACCEPT loop offline
with a scripted fake caller — no key, no network, no Anthropic SDK imported.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

DEFAULT_MODEL = "claude-sonnet-4-5"
DEFAULT_MAX_ROUNDS = 3          # code<->review revision rounds before we ship anyway
MAX_FILES = 20                 # guardrail: refuse absurdly large plans
MAX_BYTES_PER_FILE = 200_000   # guardrail: refuse absurdly large files

# The three roles. The orchestrator hands the model a different system prompt
# for each, which is what turns one model into a specialized "team member".
ROLE_PLANNER = "planner"
ROLE_CODER = "coder"
ROLE_REVIEWER = "reviewer"

SYSTEM_PROMPTS: dict[str, str] = {
    ROLE_PLANNER: (
        "You are the PLANNER on a small software team. Read the build spec and "
        "produce a minimal file-by-file plan. Reply with ONLY a JSON object of "
        'the form {"files": [{"path": "app.py", "purpose": "one line"}, ...]}. '
        "Prefer the fewest files that satisfy the spec. Always include a test "
        "file when the spec involves code. No prose, no code fences — just JSON."
    ),
    ROLE_CODER: (
        "You are the CODER on a small software team. You are given one file's "
        "path and purpose (and, on a revision, the reviewer's notes). Reply with "
        "ONLY that file's complete contents — no explanation, no Markdown fences. "
        "Write clean, runnable code that satisfies the purpose and addresses any "
        "revision notes."
    ),
    ROLE_REVIEWER: (
        "You are the REVIEWER on a small software team. You are shown the build "
        "spec and every generated file. Decide whether the project satisfies the "
        "spec and is internally consistent. Reply with ONLY a JSON object: "
        '{"verdict": "ACCEPT"} to ship, or {"verdict": "REJECT", "notes": '
        '"specific, actionable revisions"} to send it back to the coder.'
    ),
}


# --------------------------------------------------------------------------
# State: the shared object the whole team writes to across turns. Carrying an
# explicit plan, the growing file set, the review history, and a trace is what
# makes a MULTI-agent run inspectable and testable (cf. Ch.4's AgentState).
# --------------------------------------------------------------------------
@dataclass
class PlannedFile:
    path: str
    purpose: str = ""


@dataclass
class OrchestrationState:
    spec: str
    plan: list[PlannedFile] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)   # path -> contents
    round: int = 0                                        # revision rounds used
    max_rounds: int = DEFAULT_MAX_ROUNDS
    accepted: bool = False
    review_notes: list[str] = field(default_factory=list) # reviewer feedback, per round
    trace: list[dict[str, Any]] = field(default_factory=list)

    def log(self, role: str, event: str, detail: str = "") -> None:
        self.trace.append({"role": role, "event": event, "detail": detail})


# --------------------------------------------------------------------------
# Pure core: request building. Each role gets its own system prompt + a user
# message assembled purely from the current state. No network here.
# --------------------------------------------------------------------------
def build_planner_messages(state: OrchestrationState) -> list[dict[str, str]]:
    return [{"role": "user", "content": f"Build spec:\n{state.spec}"}]


def build_coder_messages(state: OrchestrationState, planned: PlannedFile) -> list[dict[str, str]]:
    parts = [
        f"Build spec:\n{state.spec}",
        f"\nWrite this file.\nPath: {planned.path}\nPurpose: {planned.purpose}",
    ]
    if state.review_notes:
        parts.append(
            "\nThe reviewer sent this file back with these revision notes:\n"
            + state.review_notes[-1]
        )
        existing = state.files.get(planned.path)
        if existing is not None:
            parts.append(f"\nYour previous version of this file was:\n{existing}")
    return [{"role": "user", "content": "\n".join(parts)}]


def build_reviewer_messages(state: OrchestrationState) -> list[dict[str, str]]:
    rendered = "\n\n".join(
        f"=== {path} ===\n{contents}" for path, contents in sorted(state.files.items())
    )
    return [{
        "role": "user",
        "content": f"Build spec:\n{state.spec}\n\nGenerated project:\n{rendered}",
    }]


# --------------------------------------------------------------------------
# Pure core: reply parsing. Each parser is defensive — models wrap JSON in
# prose or code fences, so we extract robustly and validate against guardrails.
# --------------------------------------------------------------------------
def _strip_code_fence(text: str) -> str:
    """Remove a leading/trailing ``` fence (with optional language tag)."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_+-]*\n?", "", t)
        if t.endswith("```"):
            t = t[: -3]
    return t.strip()


def _extract_json_object(text: str) -> dict[str, Any]:
    """Pull the first balanced {...} JSON object out of a possibly-noisy reply."""
    cleaned = _strip_code_fence(text)
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except (ValueError, TypeError):
        pass
    # Fall back: find the first {...} span and try to parse it.
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("no JSON object found in reply.")
    depth = 0
    for i in range(start, len(cleaned)):
        if cleaned[i] == "{":
            depth += 1
        elif cleaned[i] == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start : i + 1]
                try:
                    obj = json.loads(candidate)
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"malformed JSON object in reply: {exc}") from exc
                if not isinstance(obj, dict):
                    raise ValueError("reply JSON was not an object.")
                return obj
    raise ValueError("unbalanced JSON object in reply.")


def parse_plan(reply: str) -> list[PlannedFile]:
    """Turn the Planner's JSON reply into a validated list of PlannedFile."""
    obj = _extract_json_object(reply)
    raw = obj.get("files")
    if not isinstance(raw, list) or not raw:
        raise ValueError("plan must contain a non-empty 'files' list.")
    if len(raw) > MAX_FILES:
        raise ValueError(f"plan has too many files ({len(raw)} > {MAX_FILES}).")
    plan: list[PlannedFile] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict) or "path" not in entry:
            raise ValueError("each planned file needs a 'path'.")
        path = _safe_relpath(str(entry["path"]))
        if path in seen:
            raise ValueError(f"duplicate path in plan: {path}")
        seen.add(path)
        plan.append(PlannedFile(path=path, purpose=str(entry.get("purpose", "")).strip()))
    return plan


def parse_code(reply: str) -> str:
    """Turn the Coder's reply into file contents (strip any accidental fence)."""
    code = _strip_code_fence(reply)
    if len(code.encode("utf-8")) > MAX_BYTES_PER_FILE:
        raise ValueError("generated file exceeds size guardrail.")
    return code


@dataclass
class Review:
    accepted: bool
    notes: str = ""


def parse_review(reply: str) -> Review:
    """Turn the Reviewer's JSON verdict into a Review."""
    obj = _extract_json_object(reply)
    verdict = str(obj.get("verdict", "")).strip().upper()
    if verdict == "ACCEPT":
        return Review(accepted=True)
    if verdict == "REJECT":
        return Review(accepted=False, notes=str(obj.get("notes", "")).strip())
    raise ValueError(f"reviewer verdict must be ACCEPT or REJECT, got {verdict!r}.")


def _safe_relpath(path: str) -> str:
    """Reject absolute paths and parent-directory escapes; normalize separators."""
    p = path.strip().replace("\\", "/")
    if not p:
        raise ValueError("file path is empty.")
    pure = Path(p)
    if pure.is_absolute() or any(part == ".." for part in pure.parts):
        raise ValueError(f"unsafe file path: {path!r}")
    return pure.as_posix()


# --------------------------------------------------------------------------
# The one impure function: the model call. Imports the SDK LOCALLY so tests
# never need it. This is the ONLY thing in the module that touches the network.
# --------------------------------------------------------------------------
def _call_claude(messages: list[dict[str, str]], *, system: str,
                 model: str = DEFAULT_MODEL, api_key: str | None = None) -> str:
    """Send one role's messages to Claude and return the text reply (LIVE)."""
    import anthropic  # local import -> offline tests need no SDK

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it, or run the tests, which "
            "use a scripted fake and need no key."
        )
    client = anthropic.Anthropic(api_key=key)
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=messages,
    )
    # Concatenate any text blocks in the reply.
    return "".join(getattr(block, "text", "") for block in resp.content).strip()


# The caller seam: (messages, system) -> reply text. Live runs bind the real
# `_call_claude`; tests inject a scripted fake. This one seam makes the entire
# multi-agent loop testable offline.
Caller = Callable[..., str]


def _default_caller(model: str, api_key: str | None) -> Caller:
    def caller(messages: list[dict[str, str]], *, system: str) -> str:
        return _call_claude(messages, system=system, model=model, api_key=api_key)
    return caller


# --------------------------------------------------------------------------
# Orchestration: pure decision loop + injected caller. This is the heart of the
# chapter — one lead coordinating three role-specialized agents to a verdict.
# --------------------------------------------------------------------------
def orchestrate(spec: str, *, caller: Caller, max_rounds: int = DEFAULT_MAX_ROUNDS) -> OrchestrationState:
    """Run PLANNER -> CODER(all files) -> REVIEWER -> (revise) until ACCEPT/budget.

    `caller` is the injectable model seam. The loop itself is pure orchestration:
    it decides which role runs next and folds each reply into the state.
    """
    if not spec.strip():
        raise ValueError("build spec is empty.")

    state = OrchestrationState(spec=spec.strip(), max_rounds=max_rounds)

    # --- 1. PLANNER: spec -> file plan ---
    plan_reply = caller(build_planner_messages(state), system=SYSTEM_PROMPTS[ROLE_PLANNER])
    state.plan = parse_plan(plan_reply)
    state.log(ROLE_PLANNER, "planned", f"{len(state.plan)} file(s): "
              + ", ".join(f.path for f in state.plan))

    # --- 2 & 3. CODER writes every file, then REVIEWER judges; loop on REJECT ---
    while True:
        for planned in state.plan:
            code = parse_code(
                caller(build_coder_messages(state, planned), system=SYSTEM_PROMPTS[ROLE_CODER])
            )
            state.files[planned.path] = code
            state.log(ROLE_CODER, "wrote", planned.path)

        review = parse_review(
            caller(build_reviewer_messages(state), system=SYSTEM_PROMPTS[ROLE_REVIEWER])
        )
        if review.accepted:
            state.accepted = True
            state.log(ROLE_REVIEWER, "accept", "project accepted")
            break

        state.review_notes.append(review.notes)
        state.log(ROLE_REVIEWER, "reject", review.notes)
        state.round += 1
        if state.round >= state.max_rounds:
            state.log(ROLE_REVIEWER, "budget", f"stopped after {state.round} revision round(s)")
            break
        # else: loop back — the Coder rewrites every file with the notes in hand.

    return state


# --------------------------------------------------------------------------
# Second isolated impure step: write the accepted project to disk. Kept OUT of
# the decision loop so the loop stays pure and testable.
# --------------------------------------------------------------------------
def write_project(state: OrchestrationState, out_dir: str) -> list[str]:
    """Write every generated file under `out_dir`. Returns the paths written."""
    base = Path(out_dir)
    written: list[str] = []
    for rel, contents in sorted(state.files.items()):
        target = base / _safe_relpath(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")
        written.append(str(target))
    return written


# --------------------------------------------------------------------------
# Pure rendering: a human-readable summary of the run.
# --------------------------------------------------------------------------
def render_run(state: OrchestrationState) -> str:
    verdict = "ACCEPTED" if state.accepted else f"SHIPPED AFTER {state.round} ROUND(S) (budget hit)"
    lines = [
        "Agent orchestration run",
        f"  spec:     {state.spec}",
        f"  plan:     {len(state.plan)} file(s) -> " + ", ".join(f.path for f in state.plan),
        f"  rounds:   {state.round} revision round(s)",
        f"  verdict:  {verdict}",
        "",
        "  Team transcript:",
    ]
    for step in state.trace:
        detail = f" — {step['detail']}" if step["detail"] else ""
        lines.append(f"    [{step['role']:<8}] {step['event']}{detail}")
    lines.append("")
    lines.append("  Files:")
    for path in sorted(state.files):
        n = len(state.files[path].splitlines())
        lines.append(f"    {path}  ({n} line(s))")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _read_spec(args: argparse.Namespace) -> str:
    if args.spec_file:
        return Path(args.spec_file).read_text(encoding="utf-8")
    if args.spec == "-":
        return sys.stdin.read()
    if args.spec:
        return args.spec
    raise ValueError("no build spec given (positional, --spec-file, or '-' for stdin).")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="orchestrate",
        description="Coordinate a team of AI agents (planner/coder/reviewer) to build a small project.",
    )
    p.add_argument("spec", nargs="?", help="the build spec (quote it), or '-' to read stdin.")
    p.add_argument("--spec-file", help="read the build spec from a file.")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model (default: {DEFAULT_MODEL}).")
    p.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS,
                   help=f"max code<->review revision rounds (default: {DEFAULT_MAX_ROUNDS}).")
    p.add_argument("--out", default="build_out", help="output directory for the built project (default: build_out).")
    p.add_argument("--dry-run", action="store_true", help="run the agents but do NOT write files to disk.")
    p.add_argument("--trace", action="store_true", help="print the full team transcript.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        spec = _read_spec(args)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    caller = _default_caller(model=args.model, api_key=None)
    try:
        state = orchestrate(spec, caller=caller, max_rounds=args.max_rounds)
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.trace:
        print(render_run(state))
    else:
        verdict = "ACCEPTED" if state.accepted else f"shipped after {state.round} round(s)"
        print(f"Plan: {len(state.plan)} file(s); verdict: {verdict}")

    if args.dry_run:
        print("[dry-run] no files written.", file=sys.stderr)
        return 0

    written = write_project(state, args.out)
    print(f"Wrote {len(written)} file(s) to {args.out}/:", file=sys.stderr)
    for path in written:
        print(f"  {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
