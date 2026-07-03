# ch03 — OpenAI Triage Assistant

**A pile of messages in, a sorted action list out.**

Chapter 3 of *Idea to POC*. This turns the OpenAI primer notebook into a
standalone **task-doing assistant**: give it a stack of raw items — support
tickets, emails, backlog notes, "reply to these" messages — and it does the
tedious first pass a human would otherwise do by hand.

For each item it produces a **category**, a **priority** (P1–P4), a one-line
**summary**, a **suggested next action**, and a short **reason** for the
priority. The result is a clean Markdown triage board you can paste into a
ticket, a standup, or a doc.

The engine is OpenAI **structured outputs**: we hand the model a JSON schema
with `strict: true`, so every row comes back with the same fields and the
render step stays dumb and reliable.

## What you'll ship

A single-file CLI (`triage.py`) that:

- Reads items from a file or stdin (one per line, or split on a delimiter).
- Sends them to the OpenAI **Responses API** with a strict JSON schema.
- Sorts the results most-urgent-first and renders a Markdown board with a
  count-by-priority banner, a table, and a "why these priorities" section.

Plus an offline test suite that runs in CI with **no API key and no network**.

## Quickstart

```bash
cd ch03-openai-triage
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_API_KEY="sk-..."

# One item per non-blank line (see the included sample):
python3 triage.py sample_inbox.txt

# Multi-line items split on a delimiter, written to a file:
python3 triage.py tickets.txt --sep "---" -o board.md

# Pipe a single item in on stdin:
echo "card reader is down at register 3" | python3 triage.py -
```

### Options

| Flag | Default | What it does |
|------|---------|--------------|
| `input` | — | path to an items file, or `-` for stdin |
| `--sep` | (by line) | split items on this delimiter instead of by line |
| `--model` | `gpt-4.1-mini` | any OpenAI model that supports structured outputs |
| `-o, --out` | stdout | write the board to this file |

## How it's built (the 4-step loop)

1. **State the intent in one sentence.** "Take a pile of unstructured items and
   return a sorted, categorized action list."
2. **Let the AI draft; you review.** The notebook already showed the structured-
   outputs call; the work was shaping a schema that makes rendering trivial and
   sorting deterministic.
3. **Make it runnable early.** The core (`split_items`, `build_payload`,
   `parse_response`, `sort_rows`, `build_markdown`) is pure and tested; only
   `call_openai` touches the wire. That's why `pytest` runs with no key.
4. **End with a commit.** Small, green, shippable.

## Make it yours

The one line most people will edit is `CATEGORIES` near the top of `triage.py`.
Swap in your own buckets (`legal`, `sales`, `hr`, ...) and the schema, prompt,
and board all follow. Reserve **P1** for outages, security, or money actively
being lost — the prompt tells the model to be conservative with it.

## Testing

```bash
pip install -r requirements.txt
pytest -q
```

The tests exercise splitting, payload building, response parsing (including
malformed enums and garbage text), sorting, and Markdown rendering against
fixtures. They never import the OpenAI SDK or hit the network, so they're fast
and deterministic in CI.

## Files

| File | Purpose |
|------|---------|
| `triage.py` | the CLI + pure core |
| `test_triage.py` | offline unit tests |
| `sample_inbox.txt` | a 7-item example to try |
| `requirements.txt` | `openai` (runtime) + `pytest` (tests) |
| `.gitignore` | keeps `.env` / keys / generated boards out of git |

---

*Source material: adapted from the author's `Intro-to-OpenAI` primer notebook
(structured outputs via the Responses API). Part of the [Idea to POC](../README.md)
book project.*
