"""Offline unit tests for the ch03 triage assistant.

Every test here runs with NO OpenAI SDK installed, NO API key, and NO network.
We exercise the pure core — splitting, payload building, response parsing,
sorting, and Markdown rendering — against fixture data. The single function
that touches the wire (`call_openai`) is deliberately not tested here; it is a
thin, lazily-imported adapter.

Run:  pytest -q
"""

from __future__ import annotations

import datetime as _dt

import triage


# --- split_items ---------------------------------------------------------

def test_split_items_by_line_drops_blanks():
    text = "card reader down\n\n  refund not processed  \n\n"
    assert triage.split_items(text) == ["card reader down", "refund not processed"]


def test_split_items_with_separator():
    text = "line one\nstill item one\n---\nsecond item\n---\n\n"
    assert triage.split_items(text, sep="---") == [
        "line one\nstill item one",
        "second item",
    ]


# --- build_payload -------------------------------------------------------

def test_build_payload_numbers_items_and_sets_strict_schema():
    payload = triage.build_payload(["alpha", "beta"], model="gpt-4.1-mini")
    assert payload["model"] == "gpt-4.1-mini"
    user_msg = payload["input"][1]["content"]
    assert "1. alpha" in user_msg and "2. beta" in user_msg
    fmt = payload["text"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["strict"] is True
    assert fmt["schema"]["properties"]["items"]["type"] == "array"


def test_build_payload_uses_default_model():
    payload = triage.build_payload(["x"])
    assert payload["model"] == triage.DEFAULT_MODEL


# --- _extract_output_text ------------------------------------------------

def test_extract_prefers_convenience_field():
    raw = {"output_text": '{"items": []}', "output": []}
    assert triage._extract_output_text(raw) == '{"items": []}'


def test_extract_falls_back_to_nested_output():
    raw = {
        "output": [
            {"content": [{"type": "output_text", "text": '{"items": ['}]},
            {"content": [{"type": "output_text", "text": "]}"}]},
        ]
    }
    assert triage._extract_output_text(raw) == '{"items": []}'


# --- parse_response ------------------------------------------------------

_GOOD_RAW = {
    "output_text": (
        '{"items": ['
        '{"id": 1, "category": "urgent_ops", "priority": "P1",'
        ' "summary": "Register 3 card reader is offline.",'
        ' "suggested_action": "Dispatch a tech now.",'
        ' "reason": "Store is losing sales."},'
        '{"id": 2, "category": "billing", "priority": "P3",'
        ' "summary": "Customer asks about a duplicate charge.",'
        ' "suggested_action": "Verify and refund if duplicated.",'
        ' "reason": "Single customer, not time-critical."}'
        ']}'
    )
}


def test_parse_response_reads_clean_rows():
    rows = triage.parse_response(_GOOD_RAW, n_items=2)
    assert len(rows) == 2
    assert rows[0]["priority"] == "P1"
    assert rows[0]["category"] == "urgent_ops"
    assert rows[1]["summary"].startswith("Customer asks")


def test_parse_response_coerces_bad_enums_to_defaults():
    raw = {"output_text": '{"items": [{"id": 1, "category": "nope", '
                          '"priority": "URGENT", "summary": "x", '
                          '"suggested_action": "y", "reason": "z"}]}'}
    rows = triage.parse_response(raw, n_items=1)
    assert rows[0]["category"] == "other"   # unknown category -> other
    assert rows[0]["priority"] == "P3"       # unknown priority -> P3


def test_parse_response_survives_garbage_text():
    rows = triage.parse_response({"output_text": "not json at all"}, n_items=1)
    assert rows == []


# --- sort_rows -----------------------------------------------------------

def test_sort_rows_orders_by_priority_then_id():
    rows = [
        {"id": 5, "priority": "P3"},
        {"id": 2, "priority": "P1"},
        {"id": 9, "priority": "P1"},
        {"id": 1, "priority": "P2"},
    ]
    ordered = [(r["priority"], r["id"]) for r in triage.sort_rows(rows)]
    assert ordered == [("P1", 2), ("P1", 9), ("P2", 1), ("P3", 5)]


# --- build_markdown ------------------------------------------------------

_FIXED_NOW = _dt.datetime(2026, 7, 3, tzinfo=_dt.timezone.utc)


def test_build_markdown_renders_table_and_reasons():
    rows = triage.parse_response(_GOOD_RAW, n_items=2)
    md = triage.build_markdown(rows, model="gpt-4.1-mini", now=_FIXED_NOW)
    assert "# Triage Board" in md
    assert "2026-07-03" in md
    assert "**2 items**" in md and "P1: 1" in md
    # Table header present and P1 row sorted above the P3 row.
    assert "| # | Priority | Category | Summary | Suggested action |" in md
    assert md.index("| P1 |") < md.index("| P3 |")
    assert "## Why these priorities" in md
    assert "Store is losing sales." in md


def test_build_markdown_escapes_pipes_in_cells():
    rows = [{
        "id": 1, "category": "bug", "priority": "P2",
        "summary": "crash in a|b parser", "suggested_action": "patch a|b",
        "reason": "",
    }]
    md = triage.build_markdown(rows, now=_FIXED_NOW)
    assert "a\\|b parser" in md
    assert "patch a\\|b" in md


def test_build_markdown_handles_empty():
    md = triage.build_markdown([], now=_FIXED_NOW)
    assert "*No items to triage.*" in md
    assert "**0 items**" in md
