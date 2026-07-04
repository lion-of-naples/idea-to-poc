# ch04 — Anthropic Multi-Step Agent

**A goal in, a solved problem out — reasoned across many steps.**

Chapter 4 of *Idea to POC*. This turns the Anthropic primer notebook's two most
powerful cells — **tool use** and **extended thinking** — into a standalone
agent that solves a problem across *multiple* steps instead of one shot.

Give it a goal. The agent then loops: it **thinks** about what to do next,
**acts** by calling one of its local tools, **observes** the result, and
**repeats** until it calls `finish` with a final answer. That loop — the classic
ReAct pattern — is what separates an *agent* from a *chatbot*.

## What you'll ship

A single-file CLI (`agent.py`) that demonstrates the two things every real agent
needs:

- **Multi-step chain-of-thought** — Claude plans, acts, sees the result, and
  re-plans, one tool call at a time, with extended thinking enabled.
- **State management** — an `AgentState` object carries the growing message
  transcript, a key/value **scratchpad** the agent writes to and reads from
  across steps, and a step-by-step **trace** you can inspect afterward.

Plus an offline test suite that runs the *entire agentic loop* in CI with
**no API key and no network** (a scripted fake stands in for Claude).

## The agent's tools (all local — no external services)

| Tool | What it does |
|------|--------------|
| `calculator(expression)` | evaluate arithmetic safely (no `eval`, no code execution) |
| `remember(key, value)` | write a fact to the scratchpad — this is the agent's working memory |
| `recall(key)` | read a fact back from the scratchpad in a later step |
| `finish(answer)` | end the run and return the final answer |

## Requirements

- **Python 3.10+**
- An Anthropic API key (`ANTHROPIC_API_KEY`) — only needed to run live; the tests run offline.
- `pip install -r requirements.txt`

## Quickstart

```bash
cd ch04-anthropic-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY="sk-ant-..."   # from https://console.anthropic.com

# Run the included sample goal, with the full reasoning trace:
python3 agent.py --goal-file sample_goal.txt --trace

# Give it any goal inline and save the run:
python3 agent.py "A recipe needs 2.5 cups flour per loaf. I have 11 cups. \
                  How many loaves, and how much flour is left over?" -o run.md

# Pipe a goal in on stdin:
echo "What is 17% of 340, then doubled?" | python3 agent.py -
```

### Options

| Flag | Default | What it does |
|------|---------|--------------|
| `goal` | — | the goal (quote it), or `-` to read stdin |
| `--goal-file` | — | read the goal from a file |
| `--model` | `claude-sonnet-4-5` | any Claude model with tool use + thinking |
| `--max-steps` | `10` | safety cap so the loop can't run forever |
| `--no-thinking` | (thinking on) | disable extended thinking |
| `--trace` | off | include the step-by-step reasoning trace |
| `-o, --out` | stdout | write the run to a file |

## How it's built (the 4-step loop)

1. **State the intent in one sentence.** "An agent that solves a goal across
   multiple steps, using tools and carrying state between them."
2. **Let the AI draft; you review.** The notebook showed the tool-use protocol
   (`tool_use` blocks → run the tool → append a `tool_result` → call again). The
   work was wrapping that in a clean loop with explicit state.
3. **Make it runnable early.** The whole loop is driven by pure functions
   (`build_request`, `apply_response`, `run_tool`, `render_transcript`), so a
   scripted fake caller runs a full multi-step session with no key — which is
   exactly how the tests work.
4. **End with a commit.** Small, green, shippable.

## Make it yours

The one block most people will edit is the tool registry near the top of
`agent.py`: add a Python function, add its schema to `TOOL_SCHEMAS`, and the
agent can use it. Try adding a `web_search` or `read_file` tool — the loop, the
state, and the transcript rendering all stay the same. That separation is the
whole point: only `_call_claude` touches the network.

## Testing

```bash
pip install -r requirements.txt
pytest -q
```

The suite covers the safe calculator (including rejecting code injection), the
scratchpad tools, tool dispatch, response parsing, `build_request`, Markdown
rendering, and — most importantly — a **full four-step agentic loop** driven by
a scripted fake caller, plus a `--max-steps` runaway guard. None of it imports
the Anthropic SDK or touches the network.

## Files

| File | Purpose |
|------|---------|
| `agent.py` | the CLI, the tools, the pure core, and the agentic loop |
| `test_agent.py` | offline unit tests (incl. a full multi-step run) |
| `sample_goal.txt` | an example goal to try |
| `requirements.txt` | `anthropic` (runtime) + `pytest` (tests) |
| `.gitignore` | keeps `.env` / keys / generated runs out of git |

---

*Source material: adapted from the author's `Intro-to-Anthropic` primer notebook
(Messages API, tool use / function calling, and extended thinking), productized
here into a multi-step agent. Anthropic tool-use protocol and extended thinking
per [Anthropic's developer docs](https://docs.anthropic.com/en/docs/build-with-claude/tool-use).
Part of the [Idea to POC](../README.md) book project.*
