#!/usr/bin/env python3
"""agent — a multi-step Claude agent that thinks, uses tools, and keeps state.

Chapter 4 of *Idea to POC*. This turns the Anthropic primer notebook's two
most powerful cells — tool use and extended thinking — into a standalone,
runnable agent that solves a problem across MULTIPLE steps instead of one shot.

Give it a goal. The agent then loops:

    1. THINK    — Claude reasons about what to do next (extended thinking).
    2. ACT      — Claude calls one of the agent's local tools.
    3. OBSERVE  — we run the tool and feed the result back into the transcript.
    4. REPEAT   — until Claude calls `finish` with a final answer.

The loop is the product. It demonstrates the two things that separate an
*agent* from a *chatbot*:

  * **Chain-of-thought / multi-step processing** — Claude plans, acts, sees the
    result, and re-plans, one tool call at a time (the classic ReAct loop).
  * **State management** — an `AgentState` object carries the growing message
    transcript, a key/value scratchpad the agent writes to and reads from
    across steps, and a step-by-step trace you can inspect afterward.

Tools the agent can call (all local, no external services):

  * `calculator(expression)` — evaluate arithmetic safely.
  * `remember(key, value)`   — write a fact to the scratchpad (state!).
  * `recall(key)`            — read a fact back from the scratchpad.
  * `finish(answer)`         — end the run and return the final answer.

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python3 agent.py "A recipe needs 2.5 cups flour per loaf. I have 11 cups. \\
                      How many loaves, and how much flour is left over?"
    python3 agent.py --goal-file goal.txt --max-steps 8 --trace -o run.md

The core (tool registry, dispatch, state updates, response interpretation,
transcript rendering) is pure and unit-tested, so the tests run in CI with NO
API key and NO network. Only `_call_claude` touches the wire.
"""

from __future__ import annotations

import argparse
import ast
import datetime as _dt
import json
import operator
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

DEFAULT_MODEL = "claude-sonnet-4-5"
DEFAULT_MAX_STEPS = 10
THINKING_BUDGET_TOKENS = 1500

SYSTEM_PROMPT = (
    "You are a careful, methodical agent that solves problems ONE STEP AT A "
    "TIME using the tools provided. Never do arithmetic in your head — always "
    "use the `calculator` tool. When you compute an intermediate result you "
    "will need later, store it with `remember(key, value)` and read it back "
    "with `recall(key)`; this is your working memory across steps. When you "
    "have the complete answer, call `finish(answer)` with a clear, final "
    "response. Take as many steps as you need, but do not repeat work."
)


# --------------------------------------------------------------------------
# Tools: each is a pure Python function. This is the one block most readers
# will edit to give the agent new powers.
# --------------------------------------------------------------------------

# Safe arithmetic evaluator — only numbers and +-*/**()% , no names/calls.
_ALLOWED_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_ALLOWED_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval(expression: str) -> float:
    """Evaluate an arithmetic expression with no names, calls, or attributes."""
    def _ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _ev(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("only numeric literals are allowed")
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
            return _ALLOWED_BINOPS[type(node.op)](_ev(node.left), _ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
            return _ALLOWED_UNARYOPS[type(node.op)](_ev(node.operand))
        raise ValueError("unsupported expression")
    tree = ast.parse(expression, mode="eval")
    return _ev(tree)


def tool_calculator(state: "AgentState", expression: str) -> str:
    """Evaluate an arithmetic expression and return the result as a string."""
    try:
        value = _safe_eval(str(expression))
    except Exception as exc:  # noqa: BLE001 - report cleanly to the model
        return f"error: could not evaluate {expression!r} ({exc})"
    # Present whole numbers without a trailing .0 for cleaner transcripts.
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def tool_remember(state: "AgentState", key: str, value: str) -> str:
    """Write a fact into the agent's scratchpad (persistent across steps)."""
    state.scratchpad[str(key)] = str(value)
    return f"stored {key!r} = {value!r}"


def tool_recall(state: "AgentState", key: str) -> str:
    """Read a fact back from the scratchpad."""
    if str(key) in state.scratchpad:
        return state.scratchpad[str(key)]
    return f"error: no value stored under {key!r}"


def tool_finish(state: "AgentState", answer: str) -> str:
    """End the run. Records the final answer on the state."""
    state.final_answer = str(answer)
    state.done = True
    return "done"


# Registry: name -> (python function, Anthropic tool schema). Pure data.
TOOLS: dict[str, Callable[..., str]] = {
    "calculator": tool_calculator,
    "remember": tool_remember,
    "recall": tool_recall,
    "finish": tool_finish,
}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "calculator",
        "description": "Evaluate an arithmetic expression, e.g. '11 / 2.5'.",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    },
    {
        "name": "remember",
        "description": "Store a fact in your working memory for later steps.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "recall",
        "description": "Read a previously stored fact from your working memory.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },
    {
        "name": "finish",
        "description": "Provide the final answer and end the run.",
        "input_schema": {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        },
    },
]


# --------------------------------------------------------------------------
# State: everything the agent carries across steps. This is the heart of the
# "state management" story — the transcript, the scratchpad, and the trace.
# --------------------------------------------------------------------------

@dataclass
class AgentState:
    goal: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    scratchpad: dict[str, str] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)
    step: int = 0
    done: bool = False
    final_answer: str | None = None

    @classmethod
    def start(cls, goal: str) -> "AgentState":
        state = cls(goal=goal)
        state.messages.append({"role": "user", "content": goal})
        return state


# --------------------------------------------------------------------------
# Pure core: interpret a Claude response, run tools, update state. No network.
# --------------------------------------------------------------------------

def extract_blocks(response: dict[str, Any]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Split a Claude message dict into (thinking_text, text_blocks, tool_uses).

    Pure function. Works on the plain-dict shape returned by `.model_dump()`
    so tests can feed fixtures with no SDK present.
    """
    thinking_parts: list[str] = []
    text_blocks: list[dict[str, Any]] = []
    tool_uses: list[dict[str, Any]] = []
    for block in response.get("content") or []:
        btype = block.get("type")
        if btype == "thinking":
            thinking_parts.append(block.get("thinking") or "")
        elif btype == "text":
            text_blocks.append(block)
        elif btype == "tool_use":
            tool_uses.append(block)
    return "\n".join(p for p in thinking_parts if p), text_blocks, tool_uses


def run_tool(state: AgentState, name: str, tool_input: dict[str, Any]) -> str:
    """Dispatch a single tool call against the registry. Pure (mutates state)."""
    fn = TOOLS.get(name)
    if fn is None:
        return f"error: unknown tool {name!r}"
    try:
        return fn(state, **(tool_input or {}))
    except TypeError as exc:
        return f"error: bad arguments for {name!r} ({exc})"


def apply_response(state: AgentState, response: dict[str, Any]) -> AgentState:
    """Advance the agent one step given a Claude response dict. Pure core.

    Appends the assistant turn to the transcript, records a trace entry, runs
    every tool the model requested, and appends the tool results as the next
    user turn (per Anthropic's tool-use protocol). Sets `state.done` when the
    model calls `finish` or stops without requesting a tool.
    """
    state.step += 1
    thinking, text_blocks, tool_uses = extract_blocks(response)

    # 1) Record the assistant turn verbatim so the next API call has full context.
    state.messages.append({
        "role": "assistant",
        "content": response.get("content") or [],
    })

    said = " ".join(b.get("text", "") for b in text_blocks).strip()
    trace_entry: dict[str, Any] = {
        "step": state.step,
        "thinking": thinking,
        "said": said,
        "actions": [],
    }

    # 2) If Claude requested no tools, it's finished talking — end the run.
    if not tool_uses:
        trace_entry["actions"].append({"tool": "(none)", "result": "no tool call; ending"})
        state.trace.append(trace_entry)
        state.done = True
        if state.final_answer is None:
            state.final_answer = said or "(no answer produced)"
        return state

    # 3) Otherwise run each requested tool and collect tool_result blocks.
    tool_results: list[dict[str, Any]] = []
    for tu in tool_uses:
        name = tu.get("name", "")
        tool_input = tu.get("input") or {}
        result = run_tool(state, name, tool_input)
        trace_entry["actions"].append({
            "tool": name, "input": tool_input, "result": result,
        })
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": tu.get("id", ""),
            "content": result,
        })

    state.trace.append(trace_entry)

    # 4) Feed the tool results back as the next user turn so Claude can continue.
    state.messages.append({"role": "user", "content": tool_results})
    return state


def build_request(state: AgentState, model: str = DEFAULT_MODEL,
                  thinking: bool = True) -> dict[str, Any]:
    """Assemble the kwargs for `client.messages.create`. Pure function."""
    req: dict[str, Any] = {
        "model": model,
        "max_tokens": 2000,
        "system": SYSTEM_PROMPT,
        "tools": TOOL_SCHEMAS,
        "messages": state.messages,
    }
    if thinking:
        req["thinking"] = {"type": "enabled", "budget_tokens": THINKING_BUDGET_TOKENS}
    return req


def render_transcript(state: AgentState, show_trace: bool = False,
                      now: _dt.datetime | None = None) -> str:
    """Render the run as clean Markdown. Pure function — unit-tested."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    lines: list[str] = []
    lines.append("# Agent Run")
    lines.append("")
    lines.append(f"*{now.strftime('%Y-%m-%d')} · {state.step} steps · via Anthropic Claude*")
    lines.append("")
    lines.append("## Goal")
    lines.append("")
    lines.append(state.goal.strip())
    lines.append("")
    lines.append("## Final answer")
    lines.append("")
    lines.append((state.final_answer or "(run did not finish)").strip())
    lines.append("")

    if state.scratchpad:
        lines.append("## Working memory")
        lines.append("")
        for k, v in state.scratchpad.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    if show_trace and state.trace:
        lines.append("## Step-by-step trace")
        lines.append("")
        for entry in state.trace:
            lines.append(f"### Step {entry['step']}")
            if entry.get("thinking"):
                snippet = entry["thinking"].strip()
                if len(snippet) > 500:
                    snippet = snippet[:500] + " …"
                lines.append(f"- *thinking:* {snippet}")
            if entry.get("said"):
                lines.append(f"- *said:* {entry['said']}")
            for act in entry.get("actions", []):
                inp = act.get("input")
                inp_str = f" {json.dumps(inp)}" if inp else ""
                lines.append(f"- **{act['tool']}**{inp_str} → `{act['result']}`")
            lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# The one impure function: the network edge.
# --------------------------------------------------------------------------

def _call_claude(request: dict[str, Any], api_key: str, timeout: int = 120) -> dict[str, Any]:
    """POST one turn to the Anthropic Messages API; return a plain dict.

    Imported lazily so the module (and its tests) load with no SDK and no
    network. This is the ONLY function in the file that touches the wire.
    """
    from anthropic import Anthropic  # local import keeps offline tests dep-free

    client = Anthropic(api_key=api_key, timeout=timeout)
    resp = client.messages.create(**request)
    return resp.model_dump()


# --------------------------------------------------------------------------
# The agentic loop: wires the pure core to the network edge.
# --------------------------------------------------------------------------

def run_agent(
    goal: str,
    *,
    model: str = DEFAULT_MODEL,
    max_steps: int = DEFAULT_MAX_STEPS,
    thinking: bool = True,
    api_key: str | None = None,
    caller: Callable[[dict[str, Any], str], dict[str, Any]] | None = None,
) -> AgentState:
    """Run the full THINK→ACT→OBSERVE loop until `finish` or `max_steps`.

    `caller` lets tests inject a fake network edge; by default we use the real
    `_call_claude`. The loop body is pure (`build_request` + `apply_response`),
    which is exactly why the whole thing is testable offline.
    """
    if not goal.strip():
        raise RuntimeError("The agent needs a non-empty goal.")
    caller = caller or _call_claude
    if caller is _call_claude:
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Set ANTHROPIC_API_KEY in your environment first.")

    state = AgentState.start(goal)
    while not state.done and state.step < max_steps:
        request = build_request(state, model=model, thinking=thinking)
        response = caller(request, api_key or "")
        apply_response(state, response)

    if not state.done and state.final_answer is None:
        state.final_answer = "(stopped: hit the step limit before finishing)"
    return state


def _read_goal(args: argparse.Namespace) -> str:
    if args.goal_file:
        with open(args.goal_file, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    if args.goal == "-":
        return sys.stdin.read().strip()
    return args.goal


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A multi-step Claude agent with tools + state.")
    p.add_argument("goal", nargs="?", default=None,
                   help="the goal for the agent (quote it), or '-' for stdin")
    p.add_argument("--goal-file", default=None, help="read the goal from a file")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model (default: {DEFAULT_MODEL})")
    p.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS,
                   help=f"max agent steps (default: {DEFAULT_MAX_STEPS})")
    p.add_argument("--no-thinking", action="store_true",
                   help="disable extended thinking")
    p.add_argument("--trace", action="store_true",
                   help="include the step-by-step trace in the output")
    p.add_argument("-o", "--out", default=None, help="write the run to this file")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        goal = _read_goal(args)
        if not goal:
            raise RuntimeError("No goal provided. Pass a goal, --goal-file, or pipe via '-'.")
        state = run_agent(
            goal, model=args.model, max_steps=args.max_steps,
            thinking=not args.no_thinking,
        )
        md = render_transcript(state, show_trace=args.trace)
    except Exception as exc:  # noqa: BLE001 - clean CLI error
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(md)
        print(f"wrote {args.out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
