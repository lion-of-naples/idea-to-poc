#!/usr/bin/env python3
"""triage — a pile of messages in, a sorted action list out.

Chapter 3 of *Idea to POC*. This turns the OpenAI primer notebook into a
standalone task-doing assistant. Point it at a stack of unstructured items
(support tickets, emails, backlog notes, "reply to these" messages) and it
does the boring first pass a human would otherwise do by hand:

    1. CLASSIFY  — put each item in a category (bug, billing, feature, ...).
    2. PRIORITIZE — score urgency (P1 urgent ... P4 low) with a reason.
    3. SUMMARIZE  — one-line gist, plus a suggested next action.

It leans on OpenAI *structured outputs*: we hand the model a JSON schema and
get back rows that always have the same fields, so the render step is dumb
and reliable. Output is a clean Markdown triage board you can paste anywhere.

Usage:
    export OPENAI_API_KEY="sk-..."
    python3 triage.py inbox.txt                 # one item per non-blank line
    python3 triage.py inbox.txt --sep "---"      # split on a delimiter instead
    python3 triage.py inbox.txt --model gpt-4.1 -o board.md
    echo "card reader is down at register 3" | python3 triage.py -

The core logic (payload build, response parse, Markdown render, sorting) is
pure and unit-tested, so the project's tests run in CI with no API key and no
network. Only `call_openai` touches the wire.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from typing import Any

DEFAULT_MODEL = "gpt-4.1-mini"

# Priority buckets, most to least urgent. Used for sorting + validation.
PRIORITY_ORDER = ["P1", "P2", "P3", "P4"]

# Categories the model is asked to choose from. Keep this list short and
# swappable — this is the one line most readers will edit for their own domain.
CATEGORIES = ["bug", "billing", "feature_request", "question", "urgent_ops", "other"]

# The structured shape we require back for EACH item, so rendering is trivial.
_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "integer", "description": "1-based index of the input item"},
        "category": {"type": "string", "enum": CATEGORIES},
        "priority": {"type": "string", "enum": PRIORITY_ORDER},
        "summary": {"type": "string", "description": "one concise sentence"},
        "suggested_action": {"type": "string", "description": "the next concrete step"},
        "reason": {"type": "string", "description": "why this priority"},
    },
    "required": [
        "id", "category", "priority", "summary", "suggested_action", "reason",
    ],
    "additionalProperties": False,
}

TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": _ITEM_SCHEMA},
    },
    "required": ["items"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You are a fast, decisive triage assistant. You receive a numbered list of "
    "raw items (support tickets, emails, or tasks). For EACH item return one "
    "row with: `id` (echo the item's number), `category` (one of the allowed "
    "values), `priority` (P1=drop-everything ... P4=whenever), `summary` (one "
    "sentence), `suggested_action` (the next concrete step someone should "
    "take), and `reason` (why that priority). Be conservative with P1 — reserve "
    "it for outages, security, or money actively being lost. Do not invent "
    "details that are not in the item."
)


def split_items(text: str, sep: str | None = None) -> list[str]:
    """Turn raw input text into a list of item strings. Pure function.

    Default: one item per non-blank line. With `sep`, split on that delimiter
    (each fragment stripped, blanks dropped) — handy for multi-line items.
    """
    if sep:
        chunks = text.split(sep)
    else:
        chunks = text.splitlines()
    return [c.strip() for c in chunks if c.strip()]


def build_payload(items: list[str], model: str = DEFAULT_MODEL) -> dict[str, Any]:
    """Build the request payload for the OpenAI Responses API. Pure function.

    We embed the items as a numbered list and require the triage JSON schema
    with strict decoding, so every row comes back with all fields present.
    """
    numbered = "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))
    return {
        "model": model,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Triage these {len(items)} items:\n\n{numbered}"},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "triage_board",
                "schema": TRIAGE_SCHEMA,
                "strict": True,
            }
        },
    }


def call_openai(payload: dict[str, Any], api_key: str, timeout: int = 90) -> dict[str, Any]:
    """POST to the OpenAI Responses endpoint and return the parsed JSON.

    Imported lazily so the module (and its tests) load without the SDK or any
    network. This is the ONLY function in the file that touches the wire.
    """
    from openai import OpenAI  # local import keeps offline unit tests dep-free

    client = OpenAI(api_key=api_key, timeout=timeout)
    resp = client.responses.create(**payload)
    # `.model_dump()` gives us a plain dict identical in shape to the raw API,
    # so parse_response can be tested against fixture dicts with no SDK present.
    return resp.model_dump()


def _extract_output_text(raw: dict[str, Any]) -> str:
    """Pull the model's text out of a Responses-API dict. Pure helper.

    The SDK exposes a convenience `output_text`, but the raw dict nests the
    text under output -> content -> text. Handle both so tests can use either.
    """
    if isinstance(raw.get("output_text"), str) and raw["output_text"].strip():
        return raw["output_text"]
    parts: list[str] = []
    for block in raw.get("output") or []:
        for piece in block.get("content") or []:
            if piece.get("type") in ("output_text", "text") and piece.get("text"):
                parts.append(piece["text"])
    return "".join(parts)


def parse_response(raw: dict[str, Any], n_items: int) -> list[dict[str, Any]]:
    """Turn an OpenAI response dict into a clean list of triage rows.

    Pure function — unit-tested against fixture data. Fills sane defaults for
    any missing/garbled row so the renderer never crashes on live data.
    """
    text = _extract_output_text(raw)
    try:
        data = json.loads(text) if text else {}
    except (json.JSONDecodeError, TypeError):
        data = {}

    rows = data.get("items") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        rows = []

    cleaned: list[dict[str, Any]] = []
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        priority = row.get("priority")
        if priority not in PRIORITY_ORDER:
            priority = "P3"
        category = row.get("category")
        if category not in CATEGORIES:
            category = "other"
        cleaned.append({
            "id": int(row.get("id") or i),
            "category": category,
            "priority": priority,
            "summary": str(row.get("summary") or "").strip(),
            "suggested_action": str(row.get("suggested_action") or "").strip(),
            "reason": str(row.get("reason") or "").strip(),
        })
    return cleaned


def sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort rows most-urgent-first, stable within a priority. Pure function."""
    rank = {p: i for i, p in enumerate(PRIORITY_ORDER)}
    return sorted(rows, key=lambda r: (rank.get(r["priority"], len(rank)), r["id"]))


def build_markdown(
    rows: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
    now: _dt.datetime | None = None,
) -> str:
    """Render a clean Markdown triage board. Pure function — unit-tested."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    rows = sort_rows(rows)

    lines: list[str] = []
    lines.append("# Triage Board")
    lines.append("")
    lines.append(f"*Generated {date_str} · model: `{model}` · via OpenAI*")
    lines.append("")

    # A quick count-by-priority banner so the reader sees the shape at a glance.
    counts = {p: sum(1 for r in rows if r["priority"] == p) for p in PRIORITY_ORDER}
    banner = " · ".join(f"{p}: {counts[p]}" for p in PRIORITY_ORDER)
    lines.append(f"**{len(rows)} items** — {banner}")
    lines.append("")

    if not rows:
        lines.append("*No items to triage.*")
        lines.append("")
        return "\n".join(lines)

    lines.append("| # | Priority | Category | Summary | Suggested action |")
    lines.append("|---|----------|----------|---------|------------------|")
    for r in rows:
        summary = r["summary"].replace("|", "\\|")
        action = r["suggested_action"].replace("|", "\\|")
        lines.append(
            f"| {r['id']} | {r['priority']} | {r['category']} | {summary} | {action} |"
        )
    lines.append("")

    # Reasons live below the table so the board stays scannable.
    lines.append("## Why these priorities")
    lines.append("")
    for r in rows:
        if r["reason"]:
            lines.append(f"- **[{r['priority']}] #{r['id']}** — {r['reason']}")
    lines.append("")
    return "\n".join(lines)


def triage(
    items: list[str],
    *,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
) -> str:
    """End-to-end: raw items -> Markdown triage board (makes a network call)."""
    if not items:
        raise RuntimeError("No items to triage (input was empty).")
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY in your environment first.")
    payload = build_payload(items, model=model)
    raw = call_openai(payload, api_key)
    rows = parse_response(raw, len(items))
    return build_markdown(rows, model=model)


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Raw items -> Markdown triage board.")
    p.add_argument("input", help="path to an items file, or '-' to read stdin")
    p.add_argument("--sep", default=None,
                   help="split items on this delimiter instead of by line")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"OpenAI model (default: {DEFAULT_MODEL})")
    p.add_argument("-o", "--out", default=None,
                   help="write the board to this file (default: stdout)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        text = _read_input(args.input)
        items = split_items(text, sep=args.sep)
        md = triage(items, model=args.model)
    except Exception as exc:  # noqa: BLE001 - surface a clean CLI error
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
