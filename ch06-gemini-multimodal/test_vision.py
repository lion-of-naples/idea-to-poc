"""Offline tests for the Chapter 6 multimodal scene-report app.

These run with NO Gemini API key, NO network, and WITHOUT `google-genai` or
`gradio` installed — the network edge (`_call_gemini`) and the UI (`build_demo`)
import their SDKs LOCALLY, and the pure core is tested directly. The full
`analyze()` path is exercised by injecting a scripted fake `caller`.
"""

import base64
import json

import pytest

import vision


# --------------------------------------------------------------------------
# guess_mime_type
# --------------------------------------------------------------------------
def test_guess_mime_type_common_exts():
    assert vision.guess_mime_type("a.png") == "image/png"
    assert vision.guess_mime_type("b.jpg") == "image/jpeg"
    assert vision.guess_mime_type("c.jpeg") == "image/jpeg"


def test_guess_mime_type_unknown_defaults_to_jpeg():
    assert vision.guess_mime_type("mystery.dat") == "image/jpeg"


# --------------------------------------------------------------------------
# build_request — payload shape + validation
# --------------------------------------------------------------------------
def test_build_request_shape_and_b64_roundtrip():
    req = vision.build_request(b"\x89PNG-fake-bytes", "image/png", prompt="describe", model="m")
    assert req["model"] == "m"
    assert req["prompt"] == "describe"
    assert req["mime_type"] == "image/png"
    assert base64.b64decode(req["image_b64"]) == b"\x89PNG-fake-bytes"
    assert req["response_schema"]["type"] == "object"


def test_build_request_defaults_prompt_and_model():
    req = vision.build_request(b"x", "image/jpeg")
    assert req["model"] == vision.DEFAULT_MODEL
    assert req["prompt"] == vision.DEFAULT_PROMPT


def test_build_request_rejects_empty_image():
    with pytest.raises(ValueError):
        vision.build_request(b"", "image/png")


def test_build_request_rejects_empty_prompt():
    with pytest.raises(ValueError):
        vision.build_request(b"x", "image/png", prompt="   ")


# --------------------------------------------------------------------------
# parse_response — accepts a JSON string OR a dict; fills/coerces fields
# --------------------------------------------------------------------------
def test_parse_response_from_json_string():
    payload = json.dumps({
        "caption": "A dog on a couch",
        "objects": ["dog", "couch", "cushion"],
        "text_found": [],
        "notable_details": ["the dog is asleep"],
    })
    report = vision.parse_response(payload)
    assert report.caption == "A dog on a couch"
    assert report.objects == ["dog", "couch", "cushion"]
    assert report.notable_details == ["the dog is asleep"]


def test_parse_response_from_dict():
    report = vision.parse_response({"caption": "x", "objects": ["a"]})
    assert report.caption == "x"
    assert report.objects == ["a"]
    assert report.text_found == []           # missing -> empty


def test_parse_response_coerces_scalar_to_list():
    report = vision.parse_response({"caption": "x", "objects": "single"})
    assert report.objects == ["single"]


def test_parse_response_invalid_json_raises():
    with pytest.raises(ValueError):
        vision.parse_response("{not valid json")


def test_parse_response_bad_type_raises():
    with pytest.raises(ValueError):
        vision.parse_response(12345)


# --------------------------------------------------------------------------
# format_report — human-readable output
# --------------------------------------------------------------------------
def test_format_report_with_content():
    report = vision.SceneReport(caption="A cat", objects=["cat", "rug"],
                                text_found=["EXIT"], notable_details=["bright light"])
    out = vision.format_report(report)
    assert "Caption: A cat" in out
    assert "- cat" in out and "- rug" in out
    assert "- EXIT" in out
    assert "- bright light" in out


def test_format_report_empty_sections_show_none():
    out = vision.format_report(vision.SceneReport(caption="x", objects=[]))
    assert "(none)" in out


# --------------------------------------------------------------------------
# analyze / analyze_path — the FULL path, offline, via an injected caller
# --------------------------------------------------------------------------
def _scripted_caller(response):
    """Return a fake `caller` that records the request and returns `response`."""
    calls = {"n": 0}

    def caller(request, api_key):
        calls["n"] += 1
        caller.last_request = request
        caller.last_api_key = api_key
        return response

    caller.calls = calls
    return caller


def test_analyze_full_path_offline_with_json_string():
    fake = _scripted_caller(json.dumps({"caption": "A street", "objects": ["car", "sign"]}))
    report = vision.analyze(b"fake-image", mime_type="image/png",
                            prompt="what is here?", caller=fake)
    assert report.caption == "A street"
    assert report.objects == ["car", "sign"]
    assert fake.calls["n"] == 1                              # edge called exactly once
    assert fake.last_request["mime_type"] == "image/png"
    assert base64.b64decode(fake.last_request["image_b64"]) == b"fake-image"


def test_analyze_passes_api_key_to_caller():
    fake = _scripted_caller({"caption": "x", "objects": []})
    vision.analyze(b"img", api_key="gm_fake_key", caller=fake)
    assert fake.last_api_key == "gm_fake_key"


def test_analyze_path_reads_file(tmp_path):
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG-bytes")
    fake = _scripted_caller({"caption": "from file", "objects": ["thing"]})
    report = vision.analyze_path(str(img), caller=fake)
    assert report.caption == "from file"
    assert fake.last_request["mime_type"] == "image/png"


def test_analyze_validation_error_propagates():
    fake = _scripted_caller({"caption": "x", "objects": []})
    with pytest.raises(ValueError):
        vision.analyze(b"", caller=fake)                     # empty image


# --------------------------------------------------------------------------
# CLI — argument handling without touching the network
# --------------------------------------------------------------------------
def test_cli_requires_image_or_serve(capsys):
    rc = vision.main([])
    assert rc == 2
    assert "image" in capsys.readouterr().err.lower()


def test_cli_missing_file(capsys):
    rc = vision.main(["/no/such/image.png"])
    assert rc == 2
    assert "No such file" in capsys.readouterr().err


def test_cli_unsupported_ext(tmp_path, capsys):
    bad = tmp_path / "notes.txt"
    bad.write_text("hi")
    rc = vision.main([str(bad)])
    assert rc == 2
    assert "Unsupported" in capsys.readouterr().err


def test_cli_requires_key_for_valid_image(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG")
    rc = vision.main([str(img)])
    assert rc == 1
    assert "GEMINI_API_KEY" in capsys.readouterr().err
