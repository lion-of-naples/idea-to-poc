# Appendix D — Glossary

*From the book* **Idea to POC: Shipping Real Software with AI Tools and Agents**

This glossary collects every coding, AI/ML, and acronym term used across the book — the appendices and every chapter — in one alphabetized place. Each term is defined for a reader who is new to the words, not just new to the tools.

**How the links work.** The *first* time a term appears in the book, it links to the **Chapter Glossary** at the bottom of that same chapter or appendix, where it is defined in context. Every later appearance links here, to the master list. So if you meet a term mid-book and want the short definition, this is the page you will land on.

---

### .env file

A plain-text file, kept next to your project, that holds `KEY=value` lines such as your API keys. Your program loads them into the environment at run time so the secrets never appear in the source code. A `.env` file must always be listed in `.gitignore`.

### .gitignore

A plain-text file listing paths Git should ignore — never track or commit — such as `.venv/`, `__pycache__/`, and `.env`. Writing one before your first commit is how you keep secrets and clutter out of a repository.

### access token

Another name for a secret credential that grants a program access to a service. Hugging Face calls its API key an *access token*, and its type (read vs. write) controls what the token is allowed to do.

### agent

An AI system that can take multiple steps on its own toward a goal — reading files, running tools, and making follow-up decisions — rather than answering a single prompt. In current Cursor builds the default chat mode, **Composer**, is the agent: it can create and edit several files (and run terminal commands) while you review and accept the changes. Its read-only counterpart, **Ask**, only explains and suggests code without touching your files.

### API

Short for **Application Programming Interface** — the agreed-upon way one program talks to another. When your code "calls an API," it sends a request (usually an HTTPS request over the internet) and gets a structured response back. In this book, calling a model provider's API is how your tool reaches a live AI model.

### API key

A long secret string, unique to your account, that you attach to each API request to prove it is you — a password meant for programs rather than humans. It both authorizes the request and tells the provider whom to bill. Because it is a secret, you never share it and never commit it to Git.

### argparse

Python's built-in library for building a **command-line interface**. It reads the arguments and flags a user types after the program name (like `--model` or `-o`) and hands them to your code as ordinary values.

### bash

The common command-line **shell** on macOS, Linux, and Git Bash — the program that reads the commands you type in a terminal and runs them. In this book, any code block labeled `bash` is meant to be typed into the terminal, one command per line.

### CI (Continuous Integration)

A service that automatically runs your project's tests every time you push code, so breakage is caught immediately. In this book, GitHub runs each chapter's offline test suite on every push; a green **CI** badge on the repo means the code still works.

### CLI (command-line interface)

A program you drive by typing commands and flags in a terminal, rather than clicking a graphical interface. Every tool built in this book is a small CLI — you run it with `python3 the_tool.py` plus any options.

### clone

The Git command (`git clone <url>`) that downloads a full copy of a repository — its files and complete history — into a new folder on your machine. Cloning the companion repo is how you get the book's reference code to compare against and unblock with — you still build each chapter yourself.

### commit

A saved snapshot of your project at a moment in time, created with `git commit`, along with a short message describing what changed. A repository is essentially an ordered chain of commits — a folder with a memory.

### Cursor

An AI-native code editor built as a fork of VS Code. It keeps everything VS Code does and adds an AI build loop: **Tab** completion, a **Chat** box with a mode selector (the default **Composer** mode is the agent that edits files; **Ask** is read-only), and a **highlight → Add to Chat** path for refining selected code. This book standardizes on Cursor. (Older builds also offered **Cmd/Ctrl-K** inline edits; in current builds Cmd/Ctrl-K opens the command/search palette instead.)

### dependency hell

The tangle that results when many projects share one Python installation and their package versions collide — upgrading one project quietly breaks another. Virtual environments exist to prevent it.

### deploy

To put your software somewhere it runs for other people, not just on your laptop — for example a Hugging Face Space or a Cloudflare Worker. Later chapters treat "shipped" as *deployed*, reachable at a URL.

### environment variable

A named value that lives in your terminal session and that any program you launch can read (for example `PATH`, or `OPENAI_API_KEY`). It is how this book hands a key to a program without writing the key into the code.

### export

The macOS/Linux shell command that sets an environment variable for the current terminal session, e.g. `export OPENAI_API_KEY="sk-..."`. The value lasts only until you close that terminal window (in PowerShell the equivalent is `$env:NAME="..."`).

### Git

A version-control program that runs on your computer and records snapshots (commits) of a folder over time. Git is the tool that gives a project a history; it is separate from GitHub, the website that stores copies of repositories.

### GitHub

A website that stores copies of Git repositories in the cloud so other people and machines can get them, and that can run automated tests (CI) on your code. Git is the tool; GitHub is one popular place to keep repos and share them.

### GitHub Copilot

GitHub's AI coding assistant that adds Tab-style completions and chat inside stock VS Code. It is the book's free/low-cost alternative to Cursor for readers who prefer to stay in VS Code.

### HTTPS

The secure protocol web requests travel over. When your code calls a provider's API, it sends an HTTPS request to the provider's servers and receives the response back the same way.

### Hugging Face

A platform for sharing machine-learning models and for hosting small AI apps called **Spaces**. Chapter 5 deploys a Space, which requires a *write* access token.

### JSON

**JavaScript Object Notation** — a simple, widely used text format for structured data, made of key/value pairs and lists. APIs commonly send and receive JSON, and this book asks models to return JSON so results are predictable to read.

### JSON schema

A description of the exact shape JSON data must take — which fields exist and their types. Passing a schema to a model (via `response_format`) forces it to return a predictable structure instead of free-form prose you would have to parse.

### LLM (large language model)

A **large language model** — the kind of AI (such as GPT, Claude, or Gemini) trained on vast text to generate and reason over language. On its own an LLM cannot see today's web; pairing it with search is what makes grounded, cited answers possible.

### Markdown

A lightweight text formatting syntax — `#` for headings, `[text](url)` for links, `*` for emphasis — that stays readable as plain text but renders as formatted output. The research tool in Chapter 2 produces its briefing as Markdown.

### origin / remote

A **remote** is a named cloud copy of your repository that Git can push to and pull from; **origin** is the conventional nickname for the main one (usually on GitHub). You set it with `git remote add origin <url>`.

### PAT (Personal Access Token)

A **Personal Access Token** — a secret string you generate on GitHub to authenticate over HTTPS in place of your account password (which GitHub no longer accepts on the command line). Treat it exactly like an API key: never commit it.

### PATH

An environment variable listing the folders your shell searches to find programs. If a tool "is not found" even though it is installed, it usually is not on your PATH — the classic Windows fix is checking "Add python.exe to PATH" during install.

### pip

Python's package installer. Once a virtual environment is active, `pip install <package>` adds a library into it, and `pip install -r requirements.txt` installs everything a project needs in one command.

### POC (proof of concept)

A **proof of concept** — the smallest real, working version of an idea that proves it can run. This whole book is about crossing the *last mile* from idea to a shipped POC: running, tested, and committed.

### pull

The Git command (`git pull`) that downloads commits from the cloud copy that you do not have locally and merges them in — the fix for "your branch is behind," common when you edit on two machines.

### pure function

A function whose output depends only on its inputs and that has no side effects — it does not touch the network, files, or global state. Pure functions are trivial to test, which is why this book keeps the network isolated in one small impure function and everything else pure.

### push

The Git command (`git push`) that uploads your local commits to the cloud copy on GitHub. It is the only step in the everyday Git loop that talks to the network.

### pytest

The testing tool this book uses. Running `pytest -q` discovers every file named `test_*.py`, runs the test functions inside, and prints a pass/fail summary. Every chapter's tests run offline — no API key, no network.

### Python

The programming language used throughout this book. You do not need to be a Python programmer to follow along — you need to run a handful of commands with confidence. The tools target Python 3.10 or newer.

### repository (repo)

A folder that Git is tracking — "a folder with a memory." **Repo** is the everyday short form. It contains your files plus the full history of commits.

### requests

A popular Python library for making HTTP(S) requests. Chapter 2 uses plain `requests` to call the Sonar API directly, keeping the dependency surface small and the response easy to inspect.

### requirements.txt

A plain-text file listing the packages a project depends on, one per line (sometimes with versions). `pip install -r requirements.txt` recreates the exact set of packages on any machine, and `pip freeze > requirements.txt` records what you currently have.

### search_results / citations

The list of web sources an answer drew from, returned alongside the text by a search-grounded API. Perplexity's Sonar returns `search_results` (older responses used `citations`); this book renders them as numbered, clickable Markdown links so the output is verifiable.

### shell

The program that reads and runs the commands you type in a terminal — `bash` and PowerShell are two common ones. "Open a terminal" and "open a shell" mean effectively the same thing for this book.

### Sonar API

Perplexity's search-grounded model API. In one call it searches the live web, writes an answer, and returns the sources it used, so the result is groundable rather than a guess. Chapter 2's research agent is built on it.

### spending limit

A cap you set in a provider's billing dashboard on how much an account can spend. Setting one the moment you create an API key limits the damage from a runaway loop or a leaked key.

### terminal

The window where you type text commands to your computer — the macOS **Terminal** app, PowerShell or Git Bash on Windows, or the integrated terminal inside Cursor/VS Code (open it with **View → Terminal**). Any `bash` block in this book goes here.

### virtual environment (venv)

A private, throwaway copy of Python that lives inside your project folder with its own isolated set of installed packages. Creating one per project (`python3 -m venv .venv`, then activating it) keeps each project's dependencies from colliding — the fix for dependency hell.

### VS Code

**Visual Studio Code** — the most widely used code editor, providing an integrated terminal, debugger, and source control. Cursor is a fork of it, so VS Code habits and extensions carry over.

---

*Companion repo:* [github.com/lion-of-naples/idea-to-poc](https://github.com/lion-of-naples/idea-to-poc)
