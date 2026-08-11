# ch05 — Hugging Face Space (Open-Source Deployment)

**Take a model-backed app and put it on a public URL — no local GPU, no model download.**

Chapter 5 of *Idea to POC*. Chapters 1-4 built tools that run on *your* machine.
This is the deployment pivot: the whole point of this chapter is a **public link
anyone can use**. We build a small model-backed app locally, then deploy it as a
**Hugging Face Space** that Hugging Face hosts and serves for you.

The app is a **zero-shot text classifier**: paste in some text and *your own*
candidate labels (e.g. `billing, returns, technical support`), and it ranks how
well each label fits — with confidence scores. The model runs on Hugging Face
**Inference Providers**, so there's no multi-gigabyte download and no GPU to buy.

## What you'll ship

A single file (`app.py`) that runs two ways:

- **As a Gradio web app** (`--serve`) — the exact thing a Space serves.
- **As a CLI** — great for testing and scripting.

Plus an offline test suite that runs in CI with **no Hugging Face token, no
network, and without `gradio` or `huggingface_hub` installed** (a scripted fake
stands in for the model call) — and a `push_to_space.sh` helper that deploys the
app to a public Space in one command.

## Requirements

- **Python 3.10+**
- A free Hugging Face account + a token (`HF_TOKEN`) — only needed to run *live*; the tests run offline. Get one at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens). For local runs a **read** or inference-only fine-grained token is enough — you only need a **write** token to deploy. See [Two tokens, not one](#two-tokens-not-one).
- `pip install -r requirements.txt`

## Quickstart

```bash
cd ch05-huggingface-space
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export HF_TOKEN="hf_..."   # read / inference-only is enough here

# Classify one piece of text against your own labels:
python3 app.py "I want to return this phone I bought last week" \
    -l "billing, returns, technical support"

# Read the text from stdin (or a file with `-` and a pipe):
cat sample_text.txt | python3 app.py - -l "billing, returns, technical support"

# Launch the Gradio web app locally (this is what the Space runs):
python3 app.py --serve
```

> **On Windows, run these from Git Bash**, not PowerShell. Git Bash installs with [Git for Windows](https://git-scm.com/download/win) and runs every `bash` block in this repo exactly as printed; PowerShell is a different language and rejects `&&` and `source` with *"not a valid statement separator in this version."* Activate the venv with `source .venv/Scripts/activate` on Windows — the script lives in `Scripts`, not `bin`. Details and PowerShell equivalents: [Appendix A.7](../APPENDIX_A.md#a7-windows-which-shell-to-use).

### Options

| Flag | Default | What it does |
|------|---------|--------------|
| `text` | — | text to classify (quote it), or `-` to read stdin |
| `-l, --labels` | — | comma-separated candidate labels (required unless `--serve`) |
| `-m, --model` | `facebook/bart-large-mnli` | any Hub model that supports zero-shot classification |
| `--serve` | off | launch the Gradio web app instead of classifying once |
| `--json` | off | print the result as JSON instead of a formatted report |

## Deploy it as a public Space

This is the payoff of the chapter. Two ways:

### Option A — one command (scripted)

```bash
export HF_TOKEN="hf_..."                        # a *write* token — deploy only
./push_to_space.sh <your-username> zero-shot-classifier
```

That creates a Gradio Space (if it doesn't exist), uploads `app.py` +
`requirements.txt`, and Hugging Face builds and serves it. Your app goes live at:

```
https://huggingface.co/spaces/<your-username>/zero-shot-classifier
```

Then add a Space secret named `HF_TOKEN` under **Settings → Variables and
secrets** so the deployed app can call Inference Providers — but **not** the write
token you just deployed with. See [Two tokens, not one](#two-tokens-not-one).

### Option B — by hand (the manual recipe)

1. Create a new Space at [huggingface.co/new-space](https://huggingface.co/new-space), choose the **Gradio** SDK.
2. Add two files: this `app.py` and `requirements.txt`.
3. In **Settings → Variables and secrets**, add a secret `HF_TOKEN` — a **fine-grained, inference-only** token, not a write token.
4. Push. Hugging Face builds the Space and serves it at the URL above.

### Two tokens, not one

The deploy step needs a **write** token, because it creates the Space and uploads
files. The running app does not — it only calls Inference Providers.

If you paste the same write token into the Space secret, your public web page is
holding a credential that can push to every repository you own. One bug that
echoes the environment back to a visitor is all it takes for that to become
somebody else's token.

Make two:

| Token | Scope | Where it lives |
|---|---|---|
| Deploy token | `write` | your terminal, for `push_to_space.sh` — never in the Space |
| App token | fine-grained, inference only | the Space secret named `HF_TOKEN` |

Hugging Face recommends exactly this — [fine-grained tokens for production, one
token per application](https://huggingface.co/docs/hub/en/security-tokens). A
public Space is production, even when it's a weekend project.

If a token leaks, revoke it immediately from the **Access Tokens** tab, or
`POST https://huggingface.co/api/credentials/revoke` — which works even on a
token you don't own, so you can use it on one you spot in someone's public repo.

> **Why a Space "just works":** a Gradio Space looks for an `app.py` that ends by
> launching a Gradio app. Our `app.py --serve` does exactly that, and the Space
> runs the equivalent automatically. The same file is your local dev app *and*
> your deployed app — nothing to rewrite.

## How it's built (the 4-step loop)

1. **State the intent in one sentence.** "A model-backed classifier anyone can
   use from a public URL, with no local GPU."
2. **Let the AI draft; you review.** The primer notebook showed the Gradio +
   `pipeline` Space pattern. The productizing work was swapping the local model
   for **Inference Providers** (so there's no GPU/download) and isolating that
   one network call behind an injectable seam.
3. **Make it runnable early.** The core (`parse_labels`, `build_request`,
   `parse_response`, `format_result`) is pure, so a scripted fake `caller` runs
   the whole `classify()` path offline — which is exactly how the tests work.
4. **End with a commit.** Small, green, shippable — then push to a Space.

## Make it yours

Swap the `-m/--model` for any zero-shot model on the Hub, or change the task
entirely: because only `_call_hf` touches the network and the UI is one small
`build_demo` function, you can point the app at sentiment analysis, summarization,
or a chat model with a few edits — the pure core, the tests, and the deploy
recipe all stay the same. That separation is the whole point.

## Testing

```bash
pip install -r requirements.txt
pytest -q
```

The suite covers label parsing (trim/de-dupe), request building + validation,
both model **response shapes** (a ranked list of dicts, or parallel
`labels`/`scores`), the human-readable formatter, the **full `classify()` path**
driven by a scripted fake caller, and the CLI error paths (missing text, missing
labels, missing token). None of it imports `gradio` or `huggingface_hub` or
touches the network.

## Files

| File | Purpose |
|------|---------|
| `app.py` | the pure core, the one network edge (`_call_hf`), the Gradio UI, and the CLI |
| `test_app.py` | offline unit tests (no token, no network, no SDKs) |
| `requirements.txt` | `gradio` + `huggingface_hub` (runtime) + `pytest` (tests) |
| `push_to_space.sh` | one-command deploy to a public Space |
| `sample_text.txt` | an example input to try |
| `.gitignore` | keeps `.env` / tokens / venv out of git |

---

*Source material: adapted from the author's `Intro-to-Huggingface` primer
notebook (the Hub, Transformers `pipeline`, Inference Providers, and the Gradio
Spaces section), productized here into a deployable zero-shot classifier. Spaces
+ Gradio deployment per
[Hugging Face's Spaces docs](https://huggingface.co/docs/hub/spaces-sdks-gradio),
and hosted inference per
[Inference Providers docs](https://huggingface.co/docs/inference-providers/index).
Part of the [Idea to POC](../README.md) book project.*
