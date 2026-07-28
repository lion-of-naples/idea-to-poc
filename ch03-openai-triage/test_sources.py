"""Offline unit tests for the ch03 source adapters (file + Slack).

Every test runs with NO network, NO Slack token, and NO extra dependency. The
one function that touches the wire (`fetch_slack_messages`) is deliberately not
called here; the injectable `fetcher` seam lets us drive `read_source` with a
fake that returns fixture message dicts. This is the same discipline the triage
core uses for the OpenAI call.

Run:  pytest -q
"""

from __future__ import annotations

import pytest

import sources


# --- format_slack_messages (pure) ----------------------------------------

_RAW_SLACK = [
    {"type": "message", "user": "U1", "text": "card reader is down at register 3"},
    {"type": "message", "user": "U2", "text": "customer wants a refund on order 5512"},
    # system message (has a subtype) -> dropped
    {"type": "message", "subtype": "channel_join", "user": "U3", "text": "U3 joined"},
    # bot post -> dropped by default
    {"type": "message", "bot_id": "B9", "text": "Deploy finished :rocket:"},
    # multi-line human message -> collapsed to one line
    {"type": "message", "user": "U4", "text": "invoice looks wrong\n\ncharged twice"},
    # empty text -> dropped
    {"type": "message", "user": "U5", "text": "   "},
]


def test_format_keeps_only_human_text_items():
    items = sources.format_slack_messages(_RAW_SLACK)
    assert items == [
        "card reader is down at register 3",
        "customer wants a refund on order 5512",
        "invoice looks wrong charged twice",
    ]


def test_format_can_include_bot_messages():
    items = sources.format_slack_messages(_RAW_SLACK, skip_bots=False)
    assert "Deploy finished :rocket:" in items
    # system (subtype) messages are still dropped even when bots are kept
    assert all("joined" not in i for i in items)


def test_format_handles_empty_and_malformed():
    assert sources.format_slack_messages([]) == []
    assert sources.format_slack_messages([None, 42, {"no_text": 1}]) == []


# --- read_source with an injected fake fetcher (no network) ---------------

def _fake_fetcher(channel, token, *, limit=50):
    # Assert the seam forwards what the CLI resolved, then return fixtures.
    assert channel == "C0123456789"
    assert limit == 100
    return _RAW_SLACK


def test_read_source_slack_uses_injected_fetcher():
    text = sources.read_source(
        "slack", "C0123456789",
        fetcher=_fake_fetcher, slack_token="xoxb-test", slack_limit=100,
    )
    # Newline-joined so triage.split_items produces one item per message.
    assert text.splitlines() == [
        "card reader is down at register 3",
        "customer wants a refund on order 5512",
        "invoice looks wrong charged twice",
    ]


def test_read_source_slack_requires_channel():
    with pytest.raises(RuntimeError, match="channel ID"):
        sources.read_source("slack", None, fetcher=_fake_fetcher)


def test_read_source_rejects_unknown_source():
    with pytest.raises(RuntimeError, match="unknown source"):
        sources.read_source("carrier_pigeon", "x")


# --- read_source file path (still works, unchanged behavior) --------------

def test_read_source_file_reads_disk(tmp_path):
    p = tmp_path / "inbox.txt"
    p.write_text("line one\nline two\n", encoding="utf-8")
    assert sources.read_source("file", str(p)) == "line one\nline two\n"


def test_read_source_file_requires_path():
    with pytest.raises(RuntimeError, match="needs a path"):
        sources.read_source("file", None)
