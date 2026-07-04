"""Offline tests for the Chapter 5 zero-shot classifier app.

These run with NO Hugging Face token, NO network, and WITHOUT `huggingface_hub`
or `gradio` installed — because the network edge (`_call_hf`) and the UI
(`build_demo`) import their SDKs LOCALLY, and the pure core is tested directly.
The full `classify()` path is exercised by injecting a scripted fake `caller`.
"""

import pytest

import app


# --------------------------------------------------------------------------
# parse_labels — pure string handling
# --------------------------------------------------------------------------
def test_parse_labels_splits_trims_and_dedupes():
    assert app.parse_labels(" billing, returns , support ") == ["billing", "returns", "support"]


def test_parse_labels_drops_blanks_and_case_insensitive_dupes():
    assert app.parse_labels("spam,, Spam , ham,") == ["spam", "ham"]


def test_parse_labels_empty_returns_empty_list():
    assert app.parse_labels("") == []
    assert app.parse_labels("   ,  , ") == []


# --------------------------------------------------------------------------
# build_request — payload shape + validation
# --------------------------------------------------------------------------
def test_build_request_shape():
    req = app.build_request("hello", ["a", "b"], model="some/model")
    assert req == {"text": "hello", "labels": ["a", "b"], "model": "some/model"}


def test_build_request_trims_text_and_defaults_model():
    req = app.build_request("  hi  ", ["x"])
    assert req["text"] == "hi"
    assert req["model"] == app.DEFAULT_MODEL


def test_build_request_rejects_empty_text():
    with pytest.raises(ValueError):
        app.build_request("   ", ["a"])


def test_build_request_rejects_no_labels():
    with pytest.raises(ValueError):
        app.build_request("hello", [])


# --------------------------------------------------------------------------
# parse_response — accepts both API response shapes, always ranks best-first
# --------------------------------------------------------------------------
def test_parse_response_list_of_dicts():
    resp = [
        {"label": "returns", "score": 0.82},
        {"label": "billing", "score": 0.12},
        {"label": "support", "score": 0.06},
    ]
    result = app.parse_response("return my phone", resp)
    assert result.top_label == "returns"
    assert result.labels == ["returns", "billing", "support"]
    assert result.top_score == pytest.approx(0.82)


def test_parse_response_parallel_lists_and_sorts():
    resp = {"labels": ["billing", "returns"], "scores": [0.3, 0.7]}
    result = app.parse_response("x", resp)
    assert result.labels == ["returns", "billing"]      # re-ranked best-first
    assert result.scores[0] == pytest.approx(0.7)


def test_parse_response_unparseable_raises():
    with pytest.raises(ValueError):
        app.parse_response("x", {"nope": True})
    with pytest.raises(ValueError):
        app.parse_response("x", [])


# --------------------------------------------------------------------------
# format_result — human-readable report
# --------------------------------------------------------------------------
def test_format_result_includes_top_label_and_all_labels():
    result = app.Classification(text="x", labels=["returns", "billing"], scores=[0.8, 0.2])
    out = app.format_result(result)
    assert "Top label: returns" in out
    assert "returns" in out and "billing" in out
    assert "0.80" in out


# --------------------------------------------------------------------------
# classify — the FULL path, offline, via an injected scripted caller
# --------------------------------------------------------------------------
def _scripted_caller(response):
    """Return a fake `caller` that ignores the request and returns `response`."""
    calls = {"n": 0}

    def caller(request, token):
        calls["n"] += 1
        caller.last_request = request
        caller.last_token = token
        return response

    caller.calls = calls
    return caller


def test_classify_full_path_offline():
    fake = _scripted_caller([
        {"label": "returns", "score": 0.9},
        {"label": "billing", "score": 0.1},
    ])
    result = app.classify(
        "I want to return this phone",
        ["billing", "returns"],
        caller=fake,
    )
    assert result.top_label == "returns"
    assert result.top_score == pytest.approx(0.9)
    assert fake.calls["n"] == 1                         # network edge called exactly once
    assert fake.last_request["text"] == "I want to return this phone"
    assert fake.last_request["labels"] == ["billing", "returns"]


def test_classify_passes_token_to_caller():
    fake = _scripted_caller([{"label": "a", "score": 1.0}])
    app.classify("hi", ["a"], token="hf_fake_token", caller=fake)
    assert fake.last_token == "hf_fake_token"


def test_classify_validation_errors_propagate():
    fake = _scripted_caller([{"label": "a", "score": 1.0}])
    with pytest.raises(ValueError):
        app.classify("", ["a"], caller=fake)            # empty text
    with pytest.raises(ValueError):
        app.classify("hello", [], caller=fake)          # no labels


# --------------------------------------------------------------------------
# CLI — argument handling without touching the network
# --------------------------------------------------------------------------
def test_cli_requires_text_or_serve(capsys):
    rc = app.main([])
    assert rc == 2
    assert "Provide text" in capsys.readouterr().err


def test_cli_requires_labels(capsys):
    rc = app.main(["some text"])
    assert rc == 2
    assert "label" in capsys.readouterr().err.lower()


def test_cli_requires_token_when_labels_present(capsys, monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    rc = app.main(["some text", "-l", "a,b"])
    assert rc == 1
    assert "HF_TOKEN" in capsys.readouterr().err
