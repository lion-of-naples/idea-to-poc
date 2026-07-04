# ch08 — Orchestrating Agents to Build For You

**A one-line build spec in, a small working project out — built by a team of agents.**

Chapter 8 of *Idea to POC*. Chapter 4 built **one** agent that solved a task
across many steps. This chapter goes up a level: instead of writing the code
yourself, you write a one-line **build spec** and an *orchestrator* coordinates a
small team of role-specialized agents to produce the project for you — with
minimal hand-coding.

## The team (three roles, one model behind one seam)

| Role | What it does |
|------|--------------|
| **Planner** | reads the spec and emits a JSON build plan — a minimal list of files, each with a path and a one-line purpose |
| **Coder** | writes the full contents of each planned file (and rewrites it when the reviewer sends notes) |
| **Reviewer** | inspects the assembled project and returns a verdict: `ACCEPT`, or `REJECT` with concrete revision notes |

On `REJECT`, the orchestrator loops back to the Coder with the notes in hand and
tries again — the classic **evaluator–optimizer** pattern — up to a bounded
number of rounds. When the Reviewer `ACCEPT`s (or the round budget is hit), the
project is written to disk. That directory is the deliverable.

## What you'll ship

A single-file CLI (`orchestrate.py`) that turns a build spec into a real project
on disk, coordinated by three agents — plus an offline test suite that runs the
**entire planner → coder → reviewer → revise → accept loop** in CI with **no API
key, no network, and without importing the Anthropic SDK** (a scripted fake
stands in for the model).

## Requirements

- **Python 3.10+**
- `pip install -r requirements.txt`
- An Anthropic API key (`ANTHROPIC_API_KEY`) — **only** for live runs; the tests run fully offline.

## Quickstart (offline: the tests)

```bash
cd ch08-agent-orchestration
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q          # 20 passed — the full multi-agent loop, no key, no network
```

## Running it live (build a real project)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."   # from https://console.anthropic.com

# Build from the included sample spec, printing the full team transcript:
python3 orchestrate.py --spec-file sample_spec.txt --trace --out build_out

# Or give a spec inline:
python3 orchestrate.py "a function that validates emails, plus pytest tests"

# Pipe a spec in on stdin:
echo "a CLI dice roller with a --sides flag and tests" | python3 orchestrate.py -

# Plan + code + review, but DON'T write files (inspect the run first):
python3 orchestrate.py --spec-file sample_spec.txt --dry-run --trace
```

A live run prints the plan and verdict, then writes the accepted files under
`--out` (default `build_out/`). With `--trace` you also see the team transcript —
who planned what, which files the coder wrote, and every review verdict,
including any revision rounds.

### Options

| Flag | Default | What it does |
|------|---------|--------------|
| `spec` | — | the build spec (quote it), or `-` to read stdin |
| `--spec-file` | — | read the build spec from a file |
| `--model` | `claude-sonnet-4-5` | any Claude model |
| `--max-rounds` | `3` | max code↔review revision rounds before shipping anyway |
| `--out` | `build_out` | output directory for the built project |
| `--dry-run` | off | run the agents but do not write files |
| `--trace` | off | print the full team transcript |

## How it's built (the 4-step loop)

1. **State the intent in one sentence.** "An orchestrator that coordinates a
   planner, a coder, and a reviewer to build a small project from a one-line
   spec, revising until the reviewer accepts."
2. **Let the AI draft; you review.** The building block is Chapter 4's tool-use
   loop; the new work is *coordination* — routing each turn to the right role and
   folding replies (plan JSON, code, verdict) back into shared state.
3. **Make it runnable early.** The whole loop is pure functions
   (`build_*_messages`, `parse_plan`/`parse_code`/`parse_review`, `orchestrate`),
   so a scripted fake caller runs the full multi-agent session with no key — which
   is exactly how the tests work.
4. **End with a commit.** Small, green, shippable.

## Architecture (the house pattern, scaled to many agents)

- **Pure core** — request building, reply parsing, the decision loop, file-write
  planning, and transcript rendering are deterministic and have no I/O.
- **One impure edge** — only `_call_claude` touches the network. Every role
  routes through a single injectable `caller` seam, so one scripted fake drives
  all three agents in tests. The Anthropic SDK is imported *locally* inside
  `_call_claude`, so offline tests never need it installed.
- **A second isolated impure step** — `write_project` writes the accepted files
  to disk, kept *out* of the decision loop so the loop itself stays pure.
- **Guardrails** — the plan is capped (`MAX_FILES`), file sizes are capped, and
  every path is checked for absolute/`..` escapes before anything is written.

## Make it yours

Add a fourth role — a **Tester** that runs the generated `pytest` and feeds
failures back as review notes — by giving it a system prompt and a branch in the
loop. Because every role goes through the same `caller` seam and the loop is
pure, the tests, the state, and the transcript rendering all stay the same. That
separation is the whole point.

## Files

| File | Purpose |
|------|---------|
| `orchestrate.py` | the CLI, the three role prompts, the pure core, and the multi-agent loop |
| `test_orchestrate.py` | offline unit tests (incl. full accept-first and revise-then-accept runs) |
| `sample_spec.txt` | an example build spec to try |
| `requirements.txt` | `anthropic` (live runtime only) + `pytest` (tests) |
| `.gitignore` | keeps `.env` / keys / generated `build_out/` out of git |

---

*Source material: builds on the multi-step agent from
[`ch04-anthropic-agent`](../ch04-anthropic-agent) and applies the widely
documented multi-agent patterns — orchestrator–workers and evaluator–optimizer —
from Anthropic's
[Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
guide. Part of the [Idea to POC](../README.md) book project.*
