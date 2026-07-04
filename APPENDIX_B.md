# Appendix B — API Keys & Environment Variables

*From the book* **Idea to POC: Shipping Real Software with AI Tools and Agents**

From Chapter 2 onward, every live run in this book starts the same way:

```bash
export SOMETHING_API_KEY="..."
python3 the_tool.py
```

Two things are assumed there that this book never actually explains: what an **API key** is, and what `export` does. This appendix fills both gaps from zero, then walks you through getting a key from each of the five providers the book uses. You do not need to read it front to back — get one key working (say OpenAI or Google), and the rest follow the same shape.

One reassuring fact first: **you never need a key to run the tests.** Every chapter's test suite is offline by design — no key, no network, no vendor SDK. Keys are only for the "make it real" step, where the tool talks to a live model. If you just want to see the code work, skip straight to `pytest`.

---

## B.1 What an API key is

An **API** (Application Programming Interface) is how one program talks to another over the internet. When your `triage.py` "calls OpenAI," it sends an HTTPS request to OpenAI's servers and gets a response back. The server needs to know *who is asking* — both to check you are allowed and to bill the request to the right account. That is what an **API key** is: a long secret string, unique to your account, that you attach to each request to prove it is you.

Think of it as a password that is meant for programs instead of humans. It usually looks like a prefix plus a long random tail:

| Provider | Key looks like | Environment variable this book uses |
|---|---|---|
| OpenAI | `sk-...` | `OPENAI_API_KEY` |
| Anthropic | `sk-ant-...` | `ANTHROPIC_API_KEY` |
| Perplexity | `pplx-...` | `PERPLEXITY_API_KEY` |
| Google AI (Gemini) | (long random string) | `GEMINI_API_KEY` |
| Hugging Face | `hf_...` | `HF_TOKEN` |

Because a key is a password, two rules matter from the very start: **never share it, and never commit it to Git** (B.6–B.7). Anyone who has your key can spend your money.

---

## B.2 What an environment variable is (and what `export` does)

An **environment variable** is a named value that lives in your terminal session and that any program you launch can read. `PATH`, which tells your shell where to find programs, is one you already rely on. We use environment variables to hand a key to a program *without writing the key into the code* — because code gets committed to Git, and keys must not.

The command that sets one, on macOS and Linux, is `export`:

```bash
export OPENAI_API_KEY="sk-...your key here..."
```

That line puts the value into your current terminal session. Now any program you start *from that same terminal* can read it. In Python, the tools in this book read it like so:

```python
import os
key = os.environ.get("OPENAI_API_KEY")   # returns the string you exported
```

That is the whole handshake: you `export` the key into the terminal; the program reads it from the environment with `os.environ`. The key never appears in a source file.

To check what you have set (without revealing the whole value):

```bash
echo ${OPENAI_API_KEY:0:7}    # prints just the first 7 characters, e.g. sk-proj
```

> **Windows note.** In **PowerShell**, the syntax differs: `` $env:OPENAI_API_KEY="sk-..." `` sets it for the session, and `$env:OPENAI_API_KEY` reads it. If you installed **Git Bash** (Appendix A), you can use the `export` syntax exactly as written throughout the book.

---

## B.3 The catch: `export` only lasts for one terminal session

This trips up everyone once. An `export` lives only in the terminal window where you ran it. Close that window — or open a second one — and the variable is gone. That is why re-running a chapter's live command in a fresh terminal sometimes fails with "API key not set" even though "it worked yesterday."

You have three ways to deal with this, from most casual to most robust:

1. **Re-export each session.** Fine for a quick one-off. Paste the `export` line again whenever you open a new terminal.
2. **Add it to your shell profile — persists across sessions.** Append the `export` line to the file your shell reads on startup — `~/.zshrc` on modern macOS, `~/.bashrc` on most Linux and Git Bash. Then run `source ~/.zshrc` (or open a new terminal) and it is set automatically every time. Good for a key you use constantly.
3. **Use a `.env` file — best for projects (recommended).** Keep the keys in a file *next to the project* and load them on demand. This is the approach we recommend for the book; the next section shows it.

---

## B.4 The `.env` file pattern (recommended)

Create a plain-text file named `.env` in the project folder:

```
OPENAI_API_KEY=sk-...your key...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
```

(No `export`, no quotes needed, one `KEY=value` per line.)

Then, in the same terminal, load every line into your environment with one command:

```bash
set -a && source .env && set +a      # export everything defined in .env
python3 the_tool.py                  # now the tool can read the keys
```

`set -a` tells the shell "auto-export anything I define next," `source .env` runs the file, and `set +a` turns that behavior back off. The keys are now in your environment for that session.

**The non-negotiable rule:** add `.env` to your `.gitignore` *before you ever commit* (see Appendix A.3). A `.env` file full of live keys committed to a public repo is the single most common way people leak credentials. Every chapter's `.gitignore` in this repo already lists `.env` for exactly this reason.

---

## B.5 Getting a key from each provider

All five follow the same shape: sign in, find the API-keys page, click *create*, copy the key immediately (most show it only once), and set a spend limit if the provider offers one. Exact button labels drift over time; the URLs below are the stable entry points.

### OpenAI — `OPENAI_API_KEY` (Chapter 3)

1. Sign in at [platform.openai.com](https://platform.openai.com) (the *developer platform*, which is separate from ChatGPT).
2. Open **API keys** from the left sidebar, or go straight to [platform.openai.com/api-keys](https://platform.openai.com/api-keys).
3. Click **Create new secret key**, name it, and **copy it now** — it starts with `sk-` and is shown only once.
4. API usage is pay-as-you-go and requires a payment method under **Settings → Billing**; set a monthly **usage limit** there while you are at it.

```bash
export OPENAI_API_KEY="sk-..."
```

### Anthropic — `ANTHROPIC_API_KEY` (Chapters 4, 8, 9, 10)

1. Sign in at [console.anthropic.com](https://console.anthropic.com) (a *developer* account, separate from a Claude.ai chat subscription).
2. Open **API keys** (under the account menu / settings), or [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys).
3. Click **Create Key**, name it, and **copy it now** — it starts with `sk-ant-`.
4. Add credits under **Billing**; you can set spend limits there.

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Perplexity — `PERPLEXITY_API_KEY` (Chapter 2)

1. Sign in at [perplexity.ai](https://www.perplexity.ai) and open the **API** developer portal at [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api).
2. Add a payment method / buy credits (the Sonar API is billed separately from a Perplexity Pro subscription).
3. Click **Generate** (or "Create API Key") and **copy it** — it starts with `pplx-`.

```bash
export PERPLEXITY_API_KEY="pplx-..."
```

### Google AI Studio — `GEMINI_API_KEY` (Chapter 6)

The friendliest of the five: it has a genuinely free tier, so you can run Chapter 6 at no cost.

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and sign in with a Google account.
2. Click **Create API key** (you may be asked to pick or create a Google Cloud project — accept the default).
3. **Copy the key.** It is a long random string with no fixed prefix.

```bash
export GEMINI_API_KEY="..."
```

### Hugging Face — `HF_TOKEN` (Chapter 5)

Hugging Face calls its key an **access token**, and the *type* matters for this book.

1. Create a free account at [huggingface.co](https://huggingface.co) and sign in.
2. Go to **Settings → Access Tokens**, or [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
3. Click **Create new token**. Choose the **Write** type — Chapter 5 *deploys* a Space, which needs write access (a read-only token will fail at deploy time). Name it and **copy it** — it starts with `hf_`.

```bash
export HF_TOKEN="hf_..."      # must be a WRITE token for ch05
```

---

## B.6 Keeping keys safe — the short list

- **Never commit a key.** Put `.env` in `.gitignore` before your first commit (Appendix A.3). Never paste a key directly into a `.py` file.
- **Never paste a key into a chat, screenshot, issue, or Slack message.** If it lands anywhere others can read it, consider it burned.
- **Set a spend limit** wherever the provider allows one (OpenAI, Anthropic). It caps the damage from a runaway loop or a leaked key.
- **One key per purpose,** named clearly ("book-ch03", "laptop") so you can revoke a single one without breaking everything else.
- **Prefer the least privilege that works** — e.g. a Hugging Face *read* token for pulling models, and a *write* token only where you actually deploy.

---

## B.7 If you leak a key (it happens — fix it fast)

Committed a `.env` to a public repo? Pasted a key in a screenshot? Do not panic, but do act immediately, because bots scan public GitHub for keys within *minutes*.

1. **Revoke / delete the key** in the provider's dashboard (the same API-keys page where you made it). This instantly makes the leaked value useless — this is the step that actually protects you.
2. **Generate a new key** and update your `.env` (or `export`).
3. **Remove the file from the repo** and add it to `.gitignore`: `git rm --cached .env && git commit -m "remove leaked .env"`. Note that the old value still lives in Git *history*, which is exactly why step 1 (revocation) is the one that matters — rewriting history is optional once the key is dead.
4. **Check your usage/billing** for anything you did not do.

Revoking is fast and free. When in doubt, revoke and reissue — it costs you thirty seconds and a copy-paste.

---

## B.8 Quick reference

```bash
# set for this terminal session (macOS / Linux / Git Bash)
export OPENAI_API_KEY="sk-..."

# persist across sessions (add to your shell profile, then reopen the terminal)
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.zshrc     # or ~/.bashrc

# recommended: a .env file next to the project (and .gitignore'd)
set -a && source .env && set +a

# confirm a key is set, without printing the whole thing
echo ${OPENAI_API_KEY:0:7}
```

| Provider | Get a key at | Env var | Cost note |
|---|---|---|---|
| OpenAI | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | `OPENAI_API_KEY` | Pay-as-you-go; set a limit |
| Anthropic | [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) | `ANTHROPIC_API_KEY` | Prepaid credits |
| Perplexity | [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api) | `PERPLEXITY_API_KEY` | Credits, separate from Pro |
| Google AI | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | `GEMINI_API_KEY` | Free tier available |
| Hugging Face | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) | `HF_TOKEN` | Free; use a **Write** token for ch05 |

---

*Further reading:*

- *OpenAI — API keys & safety best practices:* [platform.openai.com/docs](https://platform.openai.com/docs/quickstart)
- *Anthropic — getting started:* [docs.anthropic.com](https://docs.anthropic.com/en/docs/get-started)
- *Perplexity — API getting started:* [docs.perplexity.ai](https://docs.perplexity.ai/getting-started/quickstart)
- *Google — Gemini API keys:* [ai.google.dev/gemini-api/docs/api-key](https://ai.google.dev/gemini-api/docs/api-key)
- *Hugging Face — user access tokens:* [huggingface.co/docs — security tokens](https://huggingface.co/docs/hub/security-tokens)
- *Companion repo:* [github.com/lion-of-naples/idea-to-poc](https://github.com/lion-of-naples/idea-to-poc)
