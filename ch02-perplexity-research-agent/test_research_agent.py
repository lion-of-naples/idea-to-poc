"""Tests for the Chapter 2 research agent.

These run WITHOUT an API key or network: the pure functions (payload building,
response parsing, markdown rendering) are tested against fixture data.

Run with:  pytest -q
"""

import datetime as dt

import research_agent as ra


def test_build_query_payload_defaults():
    p = ra.build_query_payload("solar power")
    assert p["model"] == ra.DEFAULT_MODEL
    assert p["messages"][0]["role"] == "system"
    assert "solar power" in p["messages"][1]["content"]
    assert p["response_format"]["type"] == "json_schema"
    # No optional filters unless requested.
    assert "search_domain_filter" not in p
    assert "search_recency_filter" not in p


def test_build_query_payload_with_filters():
    p = ra.build_query_payload(
        "rag", model="sonar-reasoning",
        domains=["arxiv.org"], recency="month", academic=True,
    )
    assert p["model"] == "sonar-reasoning"
    assert p["search_domain_filter"] == ["arxiv.org"]
    assert p["search_recency_filter"] == "month"
    assert p["search_mode"] == "academic"


FIXTURE = {
    "choices": [
        {"message": {"content": '{"overview": "A concise overview.", '
                                 '"key_findings": ["Fact one.", "Fact two."], '
                                 '"outlook": "Things will improve."}'}}
    ],
    "search_results": [
        {"title": "Example Source", "url": "https://example.com/a"},
        {"title": "Second Source", "url": "https://example.com/b"},
    ],
}


def test_parse_response_extracts_content_and_sources():
    content, sources = ra.parse_response(FIXTURE)
    assert content["overview"] == "A concise overview."
    assert content["key_findings"] == ["Fact one.", "Fact two."]
    assert len(sources) == 2
    assert sources[0]["url"] == "https://example.com/a"


def test_parse_response_falls_back_to_citations():
    raw = {
        "choices": [{"message": {"content": '{"overview": "o", "key_findings": [], "outlook": ""}'}}],
        "citations": ["https://old-style.com/x"],
    }
    _content, sources = ra.parse_response(raw)
    assert sources and sources[0]["url"] == "https://old-style.com/x"


def test_parse_response_handles_nonjson_content():
    raw = {"choices": [{"message": {"content": "plain text, not json"}}]}
    content, sources = ra.parse_response(raw)
    assert content["overview"] == "plain text, not json"
    assert content["key_findings"] == []
    assert sources == []


def test_build_markdown_structure():
    content, sources = ra.parse_response(FIXTURE)
    md = ra.build_markdown(
        "My Topic", content, sources, model="sonar",
        now=dt.datetime(2026, 7, 2, tzinfo=dt.timezone.utc),
    )
    assert "# Research Summary: My Topic" in md
    assert "2026-07-02" in md
    assert "## Overview" in md
    assert "## Key findings" in md
    assert "- Fact one." in md
    assert "## Outlook" in md
    assert "## Sources" in md
    # Sources render as numbered markdown links.
    assert "1. [Example Source](https://example.com/a)" in md


def test_build_markdown_handles_no_sources():
    md = ra.build_markdown("T", {"overview": "o", "key_findings": [], "outlook": ""}, [])
    assert "*No sources returned.*" in md


def test_research_requires_api_key(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    try:
        ra.research("anything", api_key=None)
        assert False, "expected RuntimeError when no key is set"
    except RuntimeError as e:
        assert "PERPLEXITY_API_KEY" in str(e)
