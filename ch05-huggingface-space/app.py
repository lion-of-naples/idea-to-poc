#!/usr/bin/env python3
"""app — a model-backed classifier you can run locally and deploy as a public
Hugging Face Space.

Chapter 5 of *Idea to POC*. Chapters 1-4 built tools that run on YOUR machine.
This chapter is the deployment pivot: we take a model-backed app and put it on a
public URL that anyone can use, with no local GPU and no multi-gigabyte model
download.

The app is a **zero-shot text classifier**: give it a piece of text and your own
candidate labels (e.g. "billing, returns, technical support"), and it tells you
which label fits best, with a confidence score for each. It calls an open model
hosted on Hugging Face **Inference Providers**, so the heavy lifting happens on
Hugging Face's hardware.

Two ways to run it:

    * As a CLI (great for testing and scripting):
        export HF_TOKEN="hf_..."
        python3 app.py "I want to return this phone" -l "billing,returns,support"

    * As a Gradio web app (this is what a Space serves):
        export HF_TOKEN="hf_..."
        python3 app.py --serve        # opens a local web UI; push to a Space to go public

Architecture (the house pattern from Chapters 2-4):

    * The CORE is pure: it builds the request, parses the model's response into a
      ranked list of (label, score), and formats a human-readable result. No
      network, no SDK. This is unit-tested offline with NO token and NO network.
    * Exactly ONE function, `_call_hf`, touches the wire. It imports the SDK
      LOCALLY and returns a plain dict, so the module and its tests import fine
      without `huggingface_hub` or `gradio` installed.
    * A `caller` seam is injected into `classify()`, so a scripted fake drives the
      whole thing offline in tests — the same trick that made the Chapter 4 agent
      testable.

Deploying to a Space is then just: add this `app.py` + `requirements.txt`, push,
and Hugging Face runs it for you at a public URL. See README.md (and
`push_to_space.sh`) for the exact recipe.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

# Default open model served by Hugging Face Inference Providers for zero-shot
# classification. Swap it for any model that supports the zero-shot task.
DEFAULT_MODEL = "facebook/bart-large-mnli"
APP_TITLE = "Zero-Shot Text Classifier"
APP_DESCRIPTION = (
    "Type some text and your own comma-separated labels. A model hosted on "
    "Hugging Face Inference Providers ranks how well each label fits — no local "
    "GPU, no model download."
)


# --------------------------------------------------------------------------
# Core (pure). These functions never touch the network or the SDK, which is
# exactly why the whole app is unit-testable offline.
# --------------------------------------------------------------------------
@dataclass
class Classification:
    """The parsed, ranked result of one classification call."""

    text: str
    labels: list[str] = field(default_factory=list)      # ranked best-first
    scores: list[float] = field(default_factory=list)    # aligned with labels

    @property
    def top_label(self) -> str:
        return self.labels[0] if self.labels else ""

    @property
    def top_score(self) -> float:
        return self.scores[0] if self.scores else 0.0

    def ranked(self) -> list[tuple[str, float]]:
        return list(zip(self.labels, self.scores))


def parse_labels(raw: str) -> list[str]:
    """Turn a comma-separated label string into a clean, de-duplicated list.

    Pure string work — split on commas, trim whitespace, drop blanks, and keep
    the first occurrence of each label (order preserved).
    """
    seen: set[str] = set()
    labels: list[str] = []
    for part in (raw or "").split(","):
        label = part.strip()
        if label and label.lower() not in seen:
            seen.add(label.lower())
            labels.append(label)
    return labels


def build_request(text: str, labels: list[str], model: str = DEFAULT_MODEL) -> dict[str, Any]:
    """Build the payload for a zero-shot classification call.

    Kept separate from the network so we can assert its shape in tests. This
    mirrors the arguments `InferenceClient.zero_shot_classification` expects.
    """
    if not text or not text.strip():
        raise ValueError("Enter some text to classify.")
    if not labels:
        raise ValueError("Provide at least one candidate label.")
    return {"text": text.strip(), "labels": list(labels), "model": model}


def parse_response(text: str, response: Any) -> Classification:
    """Parse the model response into a ranked `Classification`.

    Inference Providers may return either a list of ``{"label", "score"}`` dicts
    (already ranked) or a dict with parallel ``labels``/``scores`` lists. We
    accept both shapes and always return labels sorted best-first.
    """
    pairs: list[tuple[str, float]] = []

    if isinstance(response, list):
        for item in response:
            if isinstance(item, dict) and "label" in item:
                pairs.append((str(item["label"]), float(item.get("score", 0.0))))
    elif isinstance(response, dict):
        labels = response.get("labels")
        scores = response.get("scores")
        if isinstance(labels, list) and isinstance(scores, list):
            pairs = [(str(l), float(s)) for l, s in zip(labels, scores)]

    if not pairs:
        raise ValueError("Could not parse a classification from the model response.")

    pairs.sort(key=lambda p: p[1], reverse=True)
    return Classification(
        text=text,
        labels=[label for label, _ in pairs],
        scores=[score for _, score in pairs],
    )


def format_result(result: Classification) -> str:
    """Render a `Classification` as a compact, human-readable report."""
    if not result.labels:
        return "No labels returned."
    lines = [f"Top label: {result.top_label}  ({result.top_score:.2f})", "", "All labels:"]
    for label, score in result.ranked():
        bar = "#" * round(score * 20)
        lines.append(f"  {label:<20s} {score:5.2f}  {bar}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# The one impure function: the network edge. Imports the SDK LOCALLY so the
# module (and its tests) load without `huggingface_hub` installed.
# --------------------------------------------------------------------------
def _call_hf(request: dict[str, Any], token: str) -> Any:
    """Call Hugging Face Inference Providers for zero-shot classification.

    Returns a plain Python object (list/dict) with the same shape the API
    returns, so the pure core can be tested against fixtures.
    """
    from huggingface_hub import InferenceClient  # local import -> offline tests need no SDK

    client = InferenceClient(token=token or None)
    result = client.zero_shot_classification(
        text=request["text"],
        candidate_labels=request["labels"],
        model=request["model"],
    )
    # Normalize SDK objects to plain dicts so `parse_response` stays pure.
    normalized = []
    for item in result:
        label = getattr(item, "label", None)
        score = getattr(item, "score", None)
        if label is None and isinstance(item, dict):
            label, score = item.get("label"), item.get("score")
        normalized.append({"label": label, "score": score})
    return normalized


# --------------------------------------------------------------------------
# Orchestration: pure core + injected caller. `caller` defaults to the real
# network edge; tests pass a scripted fake so the whole path runs offline.
# --------------------------------------------------------------------------
def classify(
    text: str,
    labels: list[str],
    *,
    model: str = DEFAULT_MODEL,
    token: str | None = None,
    caller: Callable[[dict[str, Any], str], Any] | None = None,
) -> Classification:
    """Classify `text` against `labels`, returning a ranked `Classification`.

    `caller` lets tests inject a fake network edge; by default we use the real
    `_call_hf`. Everything except `caller` is pure, which is why this is
    testable offline.
    """
    caller = caller or _call_hf
    token = token or os.environ.get("HF_TOKEN", "")  # unused by a scripted caller
    request = build_request(text, labels, model=model)
    response = caller(request, token or "")
    return parse_response(text, response)


# --------------------------------------------------------------------------
# Gradio UI (this is what a Space serves). Imported LOCALLY so tests don't
# need gradio installed.
# --------------------------------------------------------------------------
def build_demo(model: str = DEFAULT_MODEL, caller: Callable[..., Any] | None = None):
    """Build (but do not launch) the Gradio interface.

    Returns a `gr.Interface`. `caller` is injectable so the UI can be tested or
    demoed offline; in production it defaults to the real `_call_hf`.
    """
    import gradio as gr  # local import -> offline tests need no gradio

    def _classify_ui(text: str, raw_labels: str) -> str:
        labels = parse_labels(raw_labels)
        try:
            result = classify(text, labels, model=model, caller=caller)
        except ValueError as exc:
            return f"⚠️  {exc}"
        return format_result(result)

    return gr.Interface(
        fn=_classify_ui,
        inputs=[
            gr.Textbox(label="Text", lines=3, placeholder="I want to return this phone I bought last week."),
            gr.Textbox(label="Candidate labels (comma-separated)", placeholder="billing, returns, technical support"),
        ],
        outputs=gr.Textbox(label="Result", lines=8),
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        flagging_mode="never",
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="app",
        description="Zero-shot text classifier backed by Hugging Face Inference Providers.",
    )
    p.add_argument("text", nargs="?", help="Text to classify (or '-' to read stdin). Omit with --serve.")
    p.add_argument("-l", "--labels", default="", help="Comma-separated candidate labels.")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"Model id (default: {DEFAULT_MODEL}).")
    p.add_argument("--serve", action="store_true", help="Launch the Gradio web app instead of classifying once.")
    p.add_argument("--json", action="store_true", help="Print the result as JSON instead of a formatted report.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.serve:
        build_demo(model=args.model).launch()
        return 0

    text = args.text
    if text == "-":
        text = sys.stdin.read()
    if not text or not text.strip():
        print("Provide text to classify (positional arg or '-' for stdin), or use --serve.", file=sys.stderr)
        return 2

    labels = parse_labels(args.labels)
    if not labels:
        print("Provide at least one label with -l/--labels, e.g. -l 'billing,returns,support'.", file=sys.stderr)
        return 2

    if not os.environ.get("HF_TOKEN"):
        print("Set HF_TOKEN in your environment first (https://huggingface.co/settings/tokens).", file=sys.stderr)
        return 1

    try:
        result = classify(text, labels, model=args.model)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"text": result.text, "labels": result.labels, "scores": result.scores}, indent=2))
    else:
        print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
