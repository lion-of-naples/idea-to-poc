# ch02-perplexity-research-agent — Cited research, on demand

The second proof of concept from **_Idea to POC_**, Chapter 2: *The Cited-Answer Research Agent*.

Give it a topic; it returns a clean Markdown research summary with an **overview**, **key findings**, an **outlook**, and a numbered list of **real sources** — powered by [Perplexity's Sonar API](https://docs.perplexity.ai), which reads the live web and returns citations.

It automates the three jobs of desk research:

1. **Sourcing** — Sonar searches the live web for the topic.
2. **Synthesis** — the model returns a structured briefing (overview / findings / outlook).
3. **Citation** — the real sources Sonar used are attached as clickable links.

> Built by productizing the `Intro-to-Perplexity` notebook. The tour became a tool.

---

## Requirements

- **Python 3.10+**
- A Perplexity API key (`PERPLEXITY_API_KEY`) — only needed to run live; the tests run offline.
- `pip install -r requirements.txt`

---

## Run it

```bash
export PERPLEXITY_API_KEY="pplx-..."          # get one at https://www.perplexity.ai/settings/api

# print a summary to the terminal
python3 research_agent.py "state of solid-state EV batteries in 2026"

# save to a file, use a reasoning model, restrict to recent academic sources
python3 research_agent.py "retrieval-augmented generation best practices" \
    --model sonar-reasoning \
    --academic --recency month \
    --domains arxiv.org docs.perplexity.ai \
    -o rag_summary.md
```

### Options

| Flag | What it does |
|------|--------------|
| `--model` | `sonar` (default), `sonar-reasoning`, or `sonar-pro` |
| `--domains` | restrict search to specific domains (e.g. `arxiv.org`) |
| `--recency` | only use sources from `day` / `week` / `month` / `year` |
| `--academic` | use academic search mode |
| `-o, --out` | write the summary to a file instead of stdout |

### Example output

```markdown
# Research Summary: solid-state EV batteries in 2026

*Generated 2026-07-02 · model: `sonar` · via Perplexity Sonar*

## Overview
Solid-state EV batteries are moving from lab to pilot production...

## Key findings
- Higher energy density than today's lithium-ion cells.
- Faster charging demonstrated in pilot lines.

## Outlook
Commercial cells are expected later this decade...

## Sources
1. [Sample Report](https://example.com/report)
```

---

## Run the tests (no API key needed)

The synthesis logic is written as pure functions, so the suite runs offline in CI:

```bash
pip install -r requirements.txt
pytest -q
```

You'll see tests for payload building, response parsing (both `search_results` and legacy `citations` shapes), Markdown rendering, and the "no key set" guard.

---

## How it maps to the four-step build loop

1. **State the intent** — "a tool that takes a topic and returns a cited markdown briefing."
2. **AI drafts, you review** — the Sonar call + structured JSON schema do the heavy lifting; you shape the prompt and schema.
3. **Runnable early** — an offline render path proves the output format before spending a single API call.
4. **Commit** — code, tests, requirements, and this README ship together, and CI proves it stays green.

---

## Files

| File | Purpose |
|------|---------|
| `research_agent.py` | The POC — CLI + pure functions for payload/parse/render |
| `test_research_agent.py` | Offline pytest suite (8 tests) |
| `requirements.txt` | `requests` (runtime) + `pytest` (tests) |
| `.gitignore` | keeps secrets and generated summaries out of git |

Next up: **Chapter 3**, where the loop builds a task-doing assistant on the OpenAI API.
