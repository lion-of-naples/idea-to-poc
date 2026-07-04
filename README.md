# Idea to POC

### Shipping Real Software with AI Tools and Agents

[![CI](https://github.com/lion-of-naples/idea-to-poc/actions/workflows/ci.yml/badge.svg)](https://github.com/lion-of-naples/idea-to-poc/actions/workflows/ci.yml)

The badge above turns green when every chapter's test suite passes — proof that the build-along code in this repo genuinely runs.

This repository is the living companion project to the book **_Idea to POC: Shipping Real Software with AI Tools and Agents_**. Each chapter takes an idea from a stalled notebook or repo and walks it, step by step, into a working **proof of concept (POC)** using AI and agent tooling.

The premise is simple: capable builders don't lack ideas or tools — they lack a repeatable way to close the "last mile" between an idea and a shipped, running thing. This book (and this repo) is that method, demonstrated in code. By the end you'll have shipped a stack of real POCs and internalized a build loop you can point at your own graveyard of unfinished repos.

Every chapter ends with something that **runs, is tested, and is committed** — an artifact that exists outside your head.

---

## The build loop (used in every chapter)

1. **State the intent in one sentence.**
2. **Let the AI draft; you review** (autocomplete for lines, chat for context, agents for multi-file work).
3. **Make it runnable early**, then improve — don't polish before it runs.
4. **End with a commit.** Shipping is the habit, not the finale.

---

## The 10-chapter roadmap

| # | Chapter | What you ship | Primary tool(s) | Directory |
|---|---------|---------------|-----------------|-----------|
| 1 | **Your Environment Is the First POC** | `devbox` — a CLI that reports whether a machine is ready to build | VS Code + Cursor | [`ch01-devbox/`](./ch01-devbox) |
| 2 | **The Cited-Answer Research Agent** | A mini-app that answers questions with live web citations | Perplexity (Sonar) | [`ch02-perplexity-research-agent/`](./ch02-perplexity-research-agent) |
| 3 | **The Task-Doing Assistant** | A structured-output triage / summarizer tool | OpenAI API | [`ch03-openai-triage/`](./ch03-openai-triage) |
| 4 | **The Multi-Step Agent** | An agent that completes a real multi-step task | Anthropic (tool use, MCP, Agent SDK) | [`ch04-anthropic-agent/`](./ch04-anthropic-agent) |
| 5 | **The Open-Source Deployment** | A model-backed app deployed as a public Space | Hugging Face | [`ch05-huggingface-space/`](./ch05-huggingface-space) |
| 6 | **The Multimodal Build** | An image → structured-report POC | Google AI (Gemini) | [`ch06-gemini-multimodal/`](./ch06-gemini-multimodal) |
| 7 | **From Research Paper to Running Code** | A runnable, self-verifying implementation of the Rao-Blackwell theorem | Blackwell AI survey | [`ch07-blackwell-paper-to-code/`](./ch07-blackwell-paper-to-code) |
| 8 | **Orchestrating Agents to Build For You** | A team of agents (planner/coder/reviewer) that builds a small project from a one-line spec | Anthropic (multi-agent) | [`ch08-agent-orchestration/`](./ch08-agent-orchestration) |
| 9 | **Ship, Host, and Share** | Deployed, documented, portfolio-ready POCs | Cloudflare + Hugging Face | [`ch09-ship-host-share/`](./ch09-ship-host-share) |
| 10 | **The Repeatable POC Method** | A reusable playbook you apply to your own repos | — (synthesis) | [`ch10-method/`](./ch10-method) |

**All ten chapters are live.** The book is complete: every chapter ships a runnable, tested POC, and Chapter 10 turns the method itself into a tool you can point at your own repos.

---

## Appendices

The chapters assume you are comfortable with Git and with setting an API key. If either is new to you, start with these — they teach both from zero.

| Appendix | What it covers |
|---|---|
| **A — Git & GitHub** | [`APPENDIX_A.md`](./APPENDIX_A.md) — install Git, the six commands you actually need (`init`/`status`/`add`/`commit`/`log`/`clone`), create a GitHub account, push your own work, and authenticate (`gh auth` or a personal access token). |
| **B — API Keys & Environment Variables** | [`APPENDIX_B.md`](./APPENDIX_B.md) — what an API key and an environment variable are, what `export` does, the `.env` pattern, step-by-step key creation for all five providers (OpenAI, Anthropic, Perplexity, Google AI Studio, Hugging Face), and how to keep keys safe. |

---

## Start here

All ten chapters are live. Begin with [`ch01-devbox/`](./ch01-devbox) — it builds the AI-native environment every later chapter depends on and ships your first POC — then work forward through [`ch02-perplexity-research-agent/`](./ch02-perplexity-research-agent), [`ch03-openai-triage/`](./ch03-openai-triage), [`ch04-anthropic-agent/`](./ch04-anthropic-agent), [`ch05-huggingface-space/`](./ch05-huggingface-space), [`ch06-gemini-multimodal/`](./ch06-gemini-multimodal), [`ch07-blackwell-paper-to-code/`](./ch07-blackwell-paper-to-code), [`ch08-agent-orchestration/`](./ch08-agent-orchestration), and [`ch09-ship-host-share/`](./ch09-ship-host-share), and finish with [`ch10-method/`](./ch10-method) — the whole method as a tool you point at your own repos.

```bash
git clone https://github.com/lion-of-naples/idea-to-poc.git
cd idea-to-poc/ch01-devbox
python3 devbox.py          # ch01 needs no dependencies; just run it
```

Each chapter has its own README with setup, run, and test steps. Chapters 2+ use a virtual environment and a `requirements.txt`.

---

## About the author

Dr. Napoleon Paxton is an AI and data executive, a Lecturer at UC Berkeley, and a U.S. Marine Corps veteran with 20+ years of experience taking technology from research concept to deployed, large-scale systems.

## License

MIT — see [LICENSE](./LICENSE).
