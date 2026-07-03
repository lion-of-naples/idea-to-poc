#!/usr/bin/env python3
"""research_agent — topic in, cited markdown research summary out.

Chapter 2 of *Idea to POC*. This turns the Perplexity primer notebook into a
standalone tool that automates the three jobs of desk research:

    1. SOURCING   — ask Perplexity's Sonar API, which reads the live web.
    2. SYNTHESIS  — get a structured summary (overview, key findings, outlook).
    3. CITATION   — attach the real source list Sonar used, as clickable links.

The output is a clean Markdown file you can hand to anyone.

Usage:
    export PERPLEXITY_API_KEY="pplx-..."
    python3 research_agent.py "state of solid-state EV batteries in 2026"
    python3 research_agent.py "RAG best practices" --model sonar-reasoning \\
        --recency month --domains arxiv.org docs.perplexity.ai -o rag.md

The core synthesis logic (build_markdown) is pure and unit-tested, so the
project's tests run in CI with no API key and no network.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from typing import Any

BASE_URL = "https://api.perplexity.ai"
DEFAULT_MODEL = "sonar"

# The structured shape we ask Sonar to return, so synthesis is predictable.
RESEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "overview": {"type": "string"},
        "key_findings": {"type": "array", "items": {"type": "string"}},
        "outlook": {"type": "string"},
    },
    "required": ["overview", "key_findings", "outlook"],
}

SYSTEM_PROMPT = (
    "You are a rigorous research analyst. Given a topic, produce a factual, "
    "neutral briefing. Return JSON with: `overview` (2-4 sentences), "
    "`key_findings` (4-7 concise, specific bullet strings, each a standalone "
    "fact), and `outlook` (2-3 sentences on what's next). Prefer recent, "
    "authoritative sources. Do not invent facts."
)


def build_query_payload(
    topic: str,
    model: str = DEFAULT_MODEL,
    domains: list[str] | None = None,
    recency: str | None = None,
    academic: bool = False,
) -> dict[str, Any]:
    """Build the request payload for the Sonar chat completions endpoint.

    Pure function (no network) so it can be unit-tested.
    """
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Research topic: {topic}"},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"schema": RESEARCH_SCHEMA},
        },
    }
    if domains:
        payload["search_domain_filter"] = domains
    if recency:
        payload["search_recency_filter"] = recency
    if academic:
        payload["search_mode"] = "academic"
    return payload


def call_sonar(payload: dict[str, Any], api_key: str, timeout: int = 90) -> dict[str, Any]:
    """POST to the Sonar chat endpoint and return the parsed JSON response.

    Imported lazily so the module (and its tests) load without `requests`.
    """
    import requests  # local import keeps offline unit tests dependency-free

    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def parse_response(raw: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Split a Sonar response into (structured content, source list).

    Handles both `search_results` (newer) and `citations` (older) shapes.
    Pure function — unit-tested against fixture data.
    """
    content_str = raw["choices"][0]["message"]["content"]
    try:
        content = json.loads(content_str)
    except (json.JSONDecodeError, TypeError):
        # Fall back to a plain-text overview if the model didn't return JSON.
        content = {"overview": str(content_str), "key_findings": [], "outlook": ""}

    sources: list[dict[str, str]] = []
    for sr in raw.get("search_results") or []:
        sources.append({"title": sr.get("title") or sr.get("url", "source"),
                        "url": sr.get("url", "")})
    if not sources:
        for c in raw.get("citations") or []:
            if isinstance(c, str):
                sources.append({"title": c, "url": c})
            elif isinstance(c, dict):
                sources.append({"title": c.get("title") or c.get("url", "source"),
                                "url": c.get("url", "")})
    return content, sources


def build_markdown(
    topic: str,
    content: dict[str, Any],
    sources: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    now: _dt.datetime | None = None,
) -> str:
    """Render a clean Markdown research summary. Pure function — unit-tested."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    lines: list[str] = []
    lines.append(f"# Research Summary: {topic}")
    lines.append("")
    lines.append(f"*Generated {date_str} · model: `{model}` · via Perplexity Sonar*")
    lines.append("")

    overview = (content.get("overview") or "").strip()
    if overview:
        lines.append("## Overview")
        lines.append("")
        lines.append(overview)
        lines.append("")

    findings = content.get("key_findings") or []
    if findings:
        lines.append("## Key findings")
        lines.append("")
        for f in findings:
            lines.append(f"- {str(f).strip()}")
        lines.append("")

    outlook = (content.get("outlook") or "").strip()
    if outlook:
        lines.append("## Outlook")
        lines.append("")
        lines.append(outlook)
        lines.append("")

    lines.append("## Sources")
    lines.append("")
    if sources:
        for i, s in enumerate(sources, 1):
            title = s.get("title") or s.get("url") or "source"
            url = s.get("url") or ""
            lines.append(f"{i}. [{title}]({url})" if url else f"{i}. {title}")
    else:
        lines.append("*No sources returned.*")
    lines.append("")
    return "\n".join(lines)


def research(
    topic: str,
    *,
    model: str = DEFAULT_MODEL,
    domains: list[str] | None = None,
    recency: str | None = None,
    academic: bool = False,
    api_key: str | None = None,
) -> str:
    """End-to-end: topic -> cited Markdown summary (makes a network call)."""
    api_key = api_key or os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        raise RuntimeError("Set PERPLEXITY_API_KEY in your environment first.")
    payload = build_query_payload(topic, model, domains, recency, academic)
    raw = call_sonar(payload, api_key)
    content, sources = parse_response(raw)
    return build_markdown(topic, content, sources, model=model)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Topic -> cited Markdown research summary.")
    p.add_argument("topic", help="the research topic (quote multi-word topics)")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="sonar | sonar-reasoning | sonar-pro (default: sonar)")
    p.add_argument("--domains", nargs="*", default=None,
                   help="restrict search to these domains, e.g. arxiv.org")
    p.add_argument("--recency", default=None,
                   choices=["day", "week", "month", "year"],
                   help="only use sources from this recent window")
    p.add_argument("--academic", action="store_true",
                   help="use academic search mode")
    p.add_argument("-o", "--out", default=None,
                   help="write the summary to this file (default: stdout)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        md = research(
            args.topic,
            model=args.model,
            domains=args.domains,
            recency=args.recency,
            academic=args.academic,
        )
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
