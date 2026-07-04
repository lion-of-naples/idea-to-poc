# ch01-devbox — Am I ready to build?

The first proof of concept from **_Idea to POC_**, Chapter 1: *Your Environment Is the First POC*.

`devbox` is a tiny command-line tool that inspects your machine and prints a clean **"AM I READY TO BUILD?"** report — your Python version, whether common developer tools are installed, which editor CLI is available, and which AI-provider API keys are present in your environment.

It's deliberately small. The point isn't the tool — it's proving the **build loop** that every later chapter relies on: state intent → let AI draft while you review → make it runnable early → commit.

> **Privacy by design:** devbox reports only whether an API key is *present*. It never reads, prints, or logs a secret's value.

---

## What it checks

- **Python version** — the interpreter actually running the script.
- **Developer tools** — `git`, `node`, `docker` (present / missing, with notes).
- **Editor CLI** — whether `cursor` or `code` is on your `PATH`.
- **AI-provider keys** — presence of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `PERPLEXITY_API_KEY`, `HF_TOKEN`, `GOOGLE_API_KEY` (these power Chapters 2–6).

The tool exits with code `0` when the core build tools (Python + git) are available, and `1` otherwise — so you can drop `devbox` into a CI check.

---

## Requirements

- **Python 3.10+** (uses only the standard library at runtime — no external dependencies to run it; matches the versions CI tests against).
- `pytest` only if you want to run the tests (see below).

---

## Run it

```bash
# from the ch01-devbox directory
python3 devbox.py
```

Example output:

```
AM I READY TO BUILD?
----------------------------
  Python : 3.11.6
  git    : yes
  node   : yes
  docker : MISSING  (optional)
  editor : /usr/local/bin/cursor
  API keys detected:
    - OPENAI_API_KEY      present
    - ANTHROPIC_API_KEY   —
    - PERPLEXITY_API_KEY  present
    - HF_TOKEN            —
    - GOOGLE_API_KEY      —
----------------------------
  Verdict: READY ✅
```

---

## Optional: set up a virtual environment and run the tests

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q
```

You should see all tests pass, including one that proves a secret value never leaks into the report.

---

## Set API keys (optional, for later chapters)

devbox only *detects* keys; it doesn't need them to run. When you're ready for
Chapters 2–6, export the ones you have (never commit them — `.env` and `*.key`
are already git-ignored):

```bash
export PERPLEXITY_API_KEY="..."
export OPENAI_API_KEY="..."
# etc.
```

Re-run `python3 devbox.py` and watch them flip to `present`.

---

## Files

| File | Purpose |
|------|---------|
| `devbox.py` | The POC — environment readiness checker |
| `test_devbox.py` | Pytest suite (shape, booleans-only, no-secret-leak, verdict) |
| `requirements.txt` | Dev/test dependencies (runtime needs none) |
| `.gitignore` | Keeps secrets and virtual-env cruft out of git |
| `.vscode/settings.json` | Reproducible editor setup |

---

## The last-mile lesson

Setup usually becomes the project that never starts. By treating the environment itself as a shippable POC — runnable, tested, committed — you finish it in under an hour and rehearse the exact loop used to ship everything else in this book.

Next up: **Chapter 2**, where the same loop turns the Perplexity API into a cited-answer research agent.
