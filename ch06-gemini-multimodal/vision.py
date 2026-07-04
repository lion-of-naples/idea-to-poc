#!/usr/bin/env python3
"""vision — turn an image into a STRUCTURED scene report with Gemini.

Chapter 6 of *Idea to POC*. This is the multimodal build: instead of text in /
text out, we send an *image* to Google's Gemini model and get back structured
understanding of it — a caption, a list of objects/tags, any text visible in the
image (OCR), and a few notable details — parsed into a typed object and rendered
as a clean report (and optional JSON).

It's deliberately generic: point it at ANY photo (a street, a receipt, a
whiteboard, a pet) and it describes what's there. That combines two ideas from
earlier chapters — Chapter 3's *structured output* discipline and this chapter's
new *multimodal input* — into one small tool.

Usage:
    export GEMINI_API_KEY="..."             # from https://aistudio.google.com/apikey
    python3 vision.py sample_scene.png                       # formatted report
    python3 vision.py photo.jpg --prompt "Focus on any signage" --json
    python3 vision.py --serve                                # optional Gradio UI

Architecture (the house pattern from Chapters 2-5):

    * The CORE is pure: it builds the request (text prompt + image part +
      response schema), parses the model's JSON into a `SceneReport`, and formats
      it. No network, no SDK. Unit-tested offline with NO API key.
    * Exactly ONE function, `_call_gemini`, touches the wire. It imports the SDK
      LOCALLY and returns a plain dict, so the module and its tests import fine
      without `google-genai` installed.
    * A `caller` seam is injected into `analyze()`, so a scripted fake drives the
      whole thing offline in tests — the same trick used in Chapters 4 and 5.
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

DEFAULT_MODEL = "gemini-2.5-flash"
APP_TITLE = "Image → Structured Scene Report"
APP_DESCRIPTION = (
    "Upload an image and Gemini returns a structured report — caption, objects, "
    "any visible text, and notable details. Multimodal input, structured output."
)

DEFAULT_PROMPT = (
    "Analyze this image and return a structured report. Provide a one-sentence "
    "caption, a list of the main objects or subjects visible, any text that "
    "appears in the image (verbatim), and a few notable details a careful "
    "observer would mention."
)

# The JSON shape we ask Gemini to return (Gemini "response_schema" format).
RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "caption": {"type": "string"},
        "objects": {"type": "array", "items": {"type": "string"}},
        "text_found": {"type": "array", "items": {"type": "string"}},
        "notable_details": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["caption", "objects"],
}

# Image types we accept from the command line / UI.
SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


# --------------------------------------------------------------------------
# Core (pure). Never touches the network or the SDK — this is what makes the
# whole tool unit-testable offline.
# --------------------------------------------------------------------------
@dataclass
class SceneReport:
    """The parsed, structured result of analyzing one image."""

    caption: str = ""
    objects: list[str] = field(default_factory=list)
    text_found: list[str] = field(default_factory=list)
    notable_details: list[str] = field(default_factory=list)


def guess_mime_type(path: str) -> str:
    """Return an image MIME type for a file path (defaults to image/jpeg)."""
    mime, _ = mimetypes.guess_type(path)
    if mime and mime.startswith("image/"):
        return mime
    ext = os.path.splitext(path)[1].lower()
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(ext, "image/jpeg")


def build_request(
    image_bytes: bytes,
    mime_type: str,
    prompt: str = DEFAULT_PROMPT,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """Build the payload for a multimodal, structured-output Gemini call.

    Kept pure and separate from the network so its shape can be asserted in
    tests. The image is base64-encoded here so the request is a plain,
    serializable dict; `_call_gemini` decodes it back to bytes for the SDK.
    """
    if not image_bytes:
        raise ValueError("No image data — provide an image file.")
    if not prompt or not prompt.strip():
        raise ValueError("Prompt must not be empty.")
    return {
        "model": model,
        "prompt": prompt.strip(),
        "image_b64": base64.b64encode(image_bytes).decode("ascii"),
        "mime_type": mime_type,
        "response_schema": RESPONSE_SCHEMA,
    }


def parse_response(response: Any) -> SceneReport:
    """Parse Gemini's response into a `SceneReport`.

    We accept two shapes: a plain dict (already-parsed JSON), or a string of
    JSON text (what `response.text` returns for a structured call). Missing
    fields default to empty; a non-list where a list is expected is coerced.
    """
    if isinstance(response, str):
        try:
            data = json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model did not return valid JSON: {exc}") from exc
    elif isinstance(response, dict):
        data = response
    else:
        raise ValueError("Unsupported response type from the model.")

    def _as_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(v) for v in value]
        if value in (None, ""):
            return []
        return [str(value)]

    return SceneReport(
        caption=str(data.get("caption", "")).strip(),
        objects=_as_list(data.get("objects")),
        text_found=_as_list(data.get("text_found")),
        notable_details=_as_list(data.get("notable_details")),
    )


def format_report(report: SceneReport) -> str:
    """Render a `SceneReport` as a compact, human-readable report."""
    def _section(title: str, items: list[str]) -> list[str]:
        out = [title]
        if items:
            out.extend(f"  - {item}" for item in items)
        else:
            out.append("  (none)")
        return out

    lines = [f"Caption: {report.caption or '(none)'}", ""]
    lines += _section("Objects / subjects:", report.objects)
    lines.append("")
    lines += _section("Text found in image:", report.text_found)
    lines.append("")
    lines += _section("Notable details:", report.notable_details)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# The one impure function: the network edge. Imports the SDK LOCALLY so the
# module (and its tests) load without `google-genai` installed.
# --------------------------------------------------------------------------
def _call_gemini(request: dict[str, Any], api_key: str) -> Any:
    """Call the Gemini API for a multimodal, structured-output generation.

    Returns a plain object (the JSON text) with the same shape the API returns,
    so the pure core can be tested against fixtures.
    """
    from google import genai  # local import -> offline tests need no SDK
    from google.genai import types

    client = genai.Client(api_key=api_key)
    image_bytes = base64.b64decode(request["image_b64"])
    response = client.models.generate_content(
        model=request["model"],
        contents=[
            request["prompt"],
            types.Part.from_bytes(data=image_bytes, mime_type=request["mime_type"]),
        ],
        config={
            "response_mime_type": "application/json",
            "response_schema": request["response_schema"],
        },
    )
    return response.text  # JSON string; parse_response handles it


# --------------------------------------------------------------------------
# Orchestration: pure core + injected caller. `caller` defaults to the real
# network edge; tests pass a scripted fake so the whole path runs offline.
# --------------------------------------------------------------------------
def analyze(
    image_bytes: bytes,
    *,
    mime_type: str = "image/jpeg",
    prompt: str = DEFAULT_PROMPT,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    caller: Callable[[dict[str, Any], str], Any] | None = None,
) -> SceneReport:
    """Analyze `image_bytes`, returning a structured `SceneReport`.

    `caller` lets tests inject a fake network edge; by default we use the real
    `_call_gemini`. Everything except `caller` is pure, which is why this is
    testable offline.
    """
    caller = caller or _call_gemini
    api_key = api_key or os.environ.get("GEMINI_API_KEY", "")  # unused by a scripted caller
    request = build_request(image_bytes, mime_type, prompt=prompt, model=model)
    response = caller(request, api_key or "")
    return parse_response(response)


def analyze_path(path: str, *, prompt: str = DEFAULT_PROMPT, model: str = DEFAULT_MODEL,
                 api_key: str | None = None, caller: Callable[..., Any] | None = None) -> SceneReport:
    """Convenience wrapper: read an image file and analyze it."""
    with open(path, "rb") as f:
        image_bytes = f.read()
    return analyze(image_bytes, mime_type=guess_mime_type(path), prompt=prompt,
                   model=model, api_key=api_key, caller=caller)


# --------------------------------------------------------------------------
# Gradio UI (optional). Imported LOCALLY so tests don't need gradio.
# --------------------------------------------------------------------------
def build_demo(model: str = DEFAULT_MODEL, caller: Callable[..., Any] | None = None):
    """Build (but do not launch) the Gradio interface."""
    import gradio as gr  # local import -> offline tests need no gradio

    def _analyze_ui(image_path: str, prompt: str) -> str:
        if not image_path:
            return "⚠️  Upload an image first."
        try:
            report = analyze_path(image_path, prompt=prompt or DEFAULT_PROMPT,
                                   model=model, caller=caller)
        except (ValueError, OSError) as exc:
            return f"⚠️  {exc}"
        return format_report(report)

    return gr.Interface(
        fn=_analyze_ui,
        inputs=[
            gr.Image(type="filepath", label="Image"),
            gr.Textbox(label="Prompt (optional)", value=DEFAULT_PROMPT, lines=2),
        ],
        outputs=gr.Textbox(label="Structured report", lines=14),
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        flagging_mode="never",
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vision",
        description="Turn an image into a structured scene report with Gemini.",
    )
    p.add_argument("image", nargs="?", help="Path to an image file. Omit with --serve.")
    p.add_argument("-p", "--prompt", default=DEFAULT_PROMPT, help="What to ask about the image.")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"Gemini model (default: {DEFAULT_MODEL}).")
    p.add_argument("--serve", action="store_true", help="Launch the Gradio web app instead of analyzing once.")
    p.add_argument("--json", action="store_true", help="Print the report as JSON instead of a formatted report.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.serve:
        build_demo(model=args.model).launch()
        return 0

    if not args.image:
        print("Provide an image path (or use --serve).", file=sys.stderr)
        return 2

    if not os.path.exists(args.image):
        print(f"No such file: {args.image}", file=sys.stderr)
        return 2

    ext = os.path.splitext(args.image)[1].lower()
    if ext not in SUPPORTED_EXTS:
        print(f"Unsupported image type '{ext}'. Try one of: {', '.join(sorted(SUPPORTED_EXTS))}", file=sys.stderr)
        return 2

    if not os.environ.get("GEMINI_API_KEY"):
        print("Set GEMINI_API_KEY in your environment first (https://aistudio.google.com/apikey).", file=sys.stderr)
        return 1

    try:
        report = analyze_path(args.image, prompt=args.prompt, model=args.model)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "caption": report.caption,
            "objects": report.objects,
            "text_found": report.text_found,
            "notable_details": report.notable_details,
        }, indent=2))
    else:
        print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
