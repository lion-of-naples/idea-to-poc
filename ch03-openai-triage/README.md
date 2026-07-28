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

## Requirements

- **Python 3.10+**
- An OpenAI API key (`OPENAI_API_KEY`) — only needed to run live; the tests run offline.
- `pip install -r requirements.txt`

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
| `input` | — | path to an items file, or `-` for stdin (with `--source slack`, a channel ID like `C0123456789`) |
| `--source` | `file` | where items come from: `file` or `slack` (see "Going live" below) |
| `--limit` | `50` | max Slack messages to pull (only with `--source slack`) |
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

## Going live: connecting real sources

The tool never cares *where* the items came from — it just needs a `list[str]`.
That's the whole reason a file and a live service are interchangeable: swap the
source, and the pure triage core (schema, prompt, parse, sort, render) doesn't
move. `sources.py` is that seam.

**Slack is included as a worked example.** Point the tool at a channel and it
triages the recent messages instead of a file:

```bash
# A Slack bot token with the channels:history scope (and the bot in the channel)
export SLACK_BOT_TOKEN="xoxb-..."
export OPENAI_API_KEY="sk-..."

python3 triage.py C0123456789 --source slack
python3 triage.py C0123456789 --source slack --limit 100 -o board.md
```

Under the hood, `sources.py` splits into the same three pieces every chapter
uses:

- `format_slack_messages` — **pure**: turns raw Slack message dicts into triage
  items (drops joins/leaves and bot posts, collapses each message to one line).
  Unit-tested offline against fixtures.
- `fetch_slack_messages` — the **one impure edge**: the only function that
  touches the network. It uses the Python standard library (`urllib`), so
  there's **no new dependency**, and the tests never call it.
- `read_source` — the **injectable seam**: pass a fake `fetcher` and the whole
  selection path runs with no token and no wire. That's how `test_sources.py`
  covers the Slack path offline.

**Adding another source is the same move.** Want a real inbox (IMAP/Gmail), a
help desk (Zendesk/Freshdesk), or GitHub issues? Write one function that returns
the messages, format them into a `list[str]`, and register a new `--source`
value in `read_source`. Nothing in `triage.py`'s core changes. Keep the file
source as the default so the offline test suite still runs with no network and
no keys — that's what keeps the project honest and CI-friendly.

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
| `sources.py` | input sources — local file + Slack example (pure format / impure fetch / injectable seam) |
| `test_triage.py` | offline unit tests for the core |
| `test_sources.py` | offline unit tests for the source adapters (Slack path via a fake fetcher) |
| `sample_inbox.txt` | a 7-item example to try |
| `requirements.txt` | `openai` (runtime) + `pytest` (tests) — the Slack source adds **no** new dependency |
| `.gitignore` | keeps `.env` / keys / generated boards out of git |

---

*Source material: adapted from the author's `Intro-to-OpenAI` primer notebook
(structured outputs via the Responses API). Part of the [Idea to POC](../README.md)
book project.*
