#!/usr/bin/env python3
"""sources — where the triage items come from.

Chapter 3's `triage.py` turns a **list of raw item strings** into a sorted
Markdown board. It never cares *where* those strings came from — a file, stdin,
or a live service. This module is the seam that makes that true.

The default source is a local file (what the chapter builds first). This module
adds an *optional* live source, **Slack**, as a worked example of connecting the
tool to an online system. The same shape applies to email (IMAP/Gmail),
Zendesk/Freshdesk tickets, GitHub issues, or anything else: write one function
that returns `list[str]`, register it, done. The pure triage core does not move.

Design follows the book's house pattern:

  * `format_slack_messages` is a **pure** function — it turns raw Slack message
    dicts into triage items and is unit-tested offline with fixture data.
  * `fetch_slack_messages` is the **one impure edge** — it and only it touches
    the network, imports its HTTP need lazily, and is never hit by the tests.
  * `read_source` is the **injectable seam** — callers (and tests) can pass a
    fake `fetcher`, so the whole selection path runs with no token and no wire.

No new third-party dependency: the Slack call uses the standard library
(`urllib`), so `requirements.txt` and the offline test suite are unchanged.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any, Callable

# A "fetcher" takes the resolved Slack args and returns the raw list of message
# dicts (as Slack's conversations.history returns them). Injecting this is what
# keeps read_source testable offline.
SlackFetcher = Callable[..., list[dict[str, Any]]]


# --- local file (the chapter's default source) ---------------------------

def read_file(path: str) -> str:
    """Read a local items file, or stdin when path == '-'. Impure (disk/stdin),
    but trivial and dependency-free — mirrors triage._read_input so behavior is
    identical whether you call the tool the old way or via read_source."""
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


# --- Slack: the pure part ------------------------------------------------

def format_slack_messages(
    messages: list[dict[str, Any]],
    *,
    skip_bots: bool = True,
) -> list[str]:
    """Turn raw Slack `conversations.history` messages into triage items.

    PURE function — no network, unit-tested against fixture dicts. Each returned
    string is one triage item, exactly the `list[str]` shape `split_items`
    would produce from a file, so the triage core treats Slack and file input
    identically.

    We keep only real, human, text-bearing messages: we drop thread-broadcast
    noise, join/leave system messages (which carry a `subtype`), empty text, and
    — by default — bot posts. Whitespace is collapsed so each item is one clean
    line, matching the "one item per line" contract of the file reader.
    """
    items: list[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        # System messages (joins, leaves, channel_topic, etc.) carry a subtype;
        # they are not human work items, so skip them.
        if msg.get("subtype"):
            continue
        if skip_bots and (msg.get("bot_id") or msg.get("app_id")):
            continue
        text = msg.get("text")
        if not isinstance(text, str):
            continue
        # Collapse newlines/tabs/runs of spaces into a single-line item.
        cleaned = " ".join(text.split())
        if cleaned:
            items.append(cleaned)
    return items


# --- Slack: the one impure edge ------------------------------------------

def fetch_slack_messages(
    channel: str,
    token: str,
    *,
    limit: int = 50,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """Call Slack's `conversations.history` and return the raw message list.

    This is the ONLY function here that touches the network. It uses the Python
    standard library so the project gains no new dependency, and the tests never
    call it — they inject a fake fetcher instead (see read_source).

    `token` is a Slack token with `channels:history` scope; `channel` is a
    channel ID (e.g. "C0123456789"). Raises RuntimeError with Slack's own error
    string on failure so the CLI can surface a clean message.
    """
    url = "https://slack.com/api/conversations.history"
    data = urllib.parse.urlencode({"channel": channel, "limit": limit}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError(f"Slack API error: {payload.get('error', 'unknown')}")
    messages = payload.get("messages")
    return messages if isinstance(messages, list) else []


# --- the injectable seam -------------------------------------------------

def read_source(
    source: str,
    ref: str | None,
    *,
    fetcher: SlackFetcher | None = None,
    slack_token: str | None = None,
    slack_limit: int = 50,
) -> str:
    """Resolve any source down to the same raw text `triage` expects.

    `source` is "file" (default) or "slack". `ref` is the file path for "file"
    or the channel ID for "slack". For Slack we return the items joined by
    newlines so the existing `split_items(text)` step produces one item per
    message — the source stays interchangeable with a file all the way through.

    `fetcher` is the injectable seam: tests pass a fake that returns fixture
    message dicts, so this whole path runs offline with no token. In production
    it defaults to the real `fetch_slack_messages`.
    """
    if source == "file":
        if not ref:
            raise RuntimeError("file source needs a path (or '-' for stdin).")
        return read_file(ref)

    if source == "slack":
        if not ref:
            raise RuntimeError("slack source needs a channel ID, e.g. C0123456789.")
        token = slack_token or os.environ.get("SLACK_BOT_TOKEN")
        if token is None and fetcher is None:
            raise RuntimeError("Set SLACK_BOT_TOKEN to read a Slack channel.")
        fetch = fetcher or fetch_slack_messages
        messages = fetch(ref, token, limit=slack_limit)
        items = format_slack_messages(messages)
        return "\n".join(items)

    raise RuntimeError(f"unknown source: {source!r} (use 'file' or 'slack').")
