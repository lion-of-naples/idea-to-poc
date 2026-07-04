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
| 4 | **The Multi-Step Agent** | An agent that completes a real multi-step task | Anthropic (tool use, MCP, Agent SDK) | `ch04-anthropic-agent/` |
| 5 | **The Open-Source Deployment** | A model-backed app deployed as a public Space | Hugging Face | `ch05-huggingface-space/` |
| 6 | **The Multimodal Build** | An image/audio/text POC | Google AI (Gemini + Vertex) | `ch06-gemini-multimodal/` |
| 7 | **From Research Paper to Running Code** | A minimal working demo of a real algorithm | Blackwell survey + GenAI overview | `ch07-blackwell-paper-to-code/` |
| 8 | **Orchestrating Agents to Build For You** | An idea taken to POC with minimal hand-coding | Cursor agents + Anthropic Agent SDK | `ch08-agent-orchestration/` |
| 9 | **Ship, Host, and Share** | Deployed, documented, portfolio-ready POCs | Cloudflare + Hugging Face | `ch09-ship-host-share/` |
| 10 | **The Repeatable POC Method** | A reusable playbook you apply to your own repos | — (synthesis) | `ch10-method/` |

Chapters are added as they're written. Chapters 1, 2, and 3 are live.

---

## Start here

Chapters 1–3 are live. Begin with [`ch01-devbox/`](./ch01-devbox) — it builds the AI-native environment every later chapter depends on and ships your first POC — then work forward through [`ch02-perplexity-research-agent/`](./ch02-perplexity-research-agent) and [`ch03-openai-triage/`](./ch03-openai-triage).

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
