# ch06 — Gemini Multimodal (Image → Structured Report)

**Send an image to a model and get back structured understanding — a caption, objects, any visible text, and notable details, parsed into a typed object.**

Chapter 6 of *Idea to POC*. Chapters 1-5 all moved text in and text out.
This is the **multimodal pivot**: the input is now an *image*. We send a photo
to Google's **Gemini** model and get back not a paragraph of prose but a
**structured scene report** — the same structured-output discipline from
Chapter 3, now applied to a picture instead of a prompt.

The tool is deliberately generic: point it at **any** image — a street scene, a
receipt, a whiteboard, a pet — and it returns a one-line caption, a list of
objects/subjects, any text it can read in the image (OCR), and a few notable
details.

## What you'll ship

A single file (`vision.py`) that runs two ways:

- **As a CLI** — `python3 vision.py photo.jpg` prints a formatted report (or `--json`).
- **As a Gradio web app** (`--serve`) — drag in an image, get the report in the browser.

Plus an offline test suite that runs in CI with **no API key, no network, and
without `google-genai` or `gradio` installed** — a scripted fake stands in for
the model call, so every code path is exercised for free.

## Requirements

- **Python 3.10+**
- A free Google AI Studio key (`GEMINI_API_KEY`) — only needed to run *live*; the tests run offline. Get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
- `pip install -r requirements.txt`

## Quickstart

```bash
cd ch06-gemini-multimodal
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export GEMINI_API_KEY="..."   # from https://aistudio.google.com/apikey

# Analyze the bundled sample image (formatted report):
python3 vision.py sample_scene.png

# Point it at your own photo, steer it with a prompt, and get JSON:
python3 vision.py photo.jpg --prompt "Focus on any signage" --json

# Launch the Gradio web app locally:
python3 vision.py --serve
```

### Options

| Flag | Default | What it does |
|------|---------|--------------|
| `image` | — | path to an image file (omit when using `--serve`) |
| `-p, --prompt` | a general "describe this image" prompt | what to ask about the image |
| `-m, --model` | `gemini-2.5-flash` | any multimodal Gemini model |
| `--serve` | off | launch the Gradio web app instead of analyzing once |
| `--json` | off | print the result as JSON instead of a formatted report |

Supported image types: `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp`.

## How it's built (the 4-step loop)

1. **State the intent in one sentence.** "Send any image to Gemini and get back
   a structured report — caption, objects, visible text, notable details."
2. **Let the AI draft; you review.** The primer notebook showed the multimodal
   input pattern (`types.Part.from_bytes`). The productizing work was pinning it
   to a **response schema** so the model returns typed JSON, and isolating that
   one network call behind an injectable seam.
3. **Make it runnable early.** The core (`build_request`, `parse_response`,
   `format_report`) is pure, so a scripted fake `caller` runs the whole
   `analyze()` path offline — which is exactly how the tests work.
4. **End with a commit.** Small, green, shippable.

## How it works (the multimodal part)

The one function that touches the wire, `_call_gemini`, does three things
that make this "multimodal" rather than "text in / text out":

1. **The request carries an image part.** Alongside the text prompt, we pass
   `types.Part.from_bytes(data=image_bytes, mime_type=...)` — the raw image
   bytes travel to the model, not a description of them.
2. **We ask for structured output.** The `config` sets
   `response_mime_type="application/json"` and a `response_schema`, so Gemini
   returns JSON matching our shape instead of free prose.
3. **The core stays pure.** `build_request` base64-encodes the image into a
   plain serializable dict (so its shape can be asserted in a test), and
   `_call_gemini` decodes it back to bytes for the SDK. Everything else — parse,
   coerce, format — never sees the network.

## Make it yours

Change the `RESPONSE_SCHEMA` to pull out whatever *your* images need — colors,
counts, bounding descriptions, sentiment — and the parser and formatter follow.
Swap `-m/--model` for any multimodal Gemini model, or steer a single run with
`--prompt`. Because only `_call_gemini` touches the network and the UI is one
small `build_demo` function, the pure core, the tests, and the CLI all stay the
same when you retarget it. That separation is the whole point.

## Testing

```bash
pip install -r requirements.txt
pytest -q
```

The suite covers MIME-type guessing, request building (shape, base64 roundtrip,
validation), both accepted **response shapes** (a JSON string like `response.text`
returns, or an already-parsed dict) plus scalar-to-list coercion and invalid
JSON, the human-readable formatter, the **full `analyze()` path** driven by a
scripted fake caller, `analyze_path` on a temp file, and the CLI error paths
(no image, missing file, unsupported extension, missing key). None of it imports
`google-genai` or `gradio` or touches the network.

## Files

| File | Purpose |
|------|---------|
| `vision.py` | the pure core, the one network edge (`_call_gemini`), the Gradio UI, and the CLI |
| `test_vision.py` | offline unit tests (no key, no network, no SDKs) |
| `requirements.txt` | `google-genai` + `gradio` (runtime) + `pytest` (tests) |
| `sample_scene.png` | an example image to try (a labeled desk still-life, good for OCR) |
| `.gitignore` | keeps `.env` / keys / venv out of git |

---

*Source material: adapted from the author's `Intro-to-Google-AI-Ecosystem`
primer notebook (the multimodal image-input section using
`types.Part.from_bytes`), productized here into a structured image analyzer.
Multimodal input and structured output per
[Google's Gemini API docs](https://ai.google.dev/gemini-api/docs), using the
[`google-genai` Python SDK](https://googleapis.github.io/python-genai/); API keys
from [Google AI Studio](https://aistudio.google.com/apikey). Part of the
[Idea to POC](../README.md) book project.*
