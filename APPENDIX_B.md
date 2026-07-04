# Appendix B — Git & GitHub for People Who Skipped Them

*From the book* **Idea to POC: Shipping Real Software with AI Tools and Agents**

Every chapter in this book ends the same way: with a `git commit`. Chapter 1 runs `git init`; later chapters tell you to "clone the repo" or "push it to your companion GitHub org." If those instructions felt like they assumed something you were never taught, this appendix is for you. You do not need to be a Git expert to finish this book — you need about six commands and one mental model. That is all this appendix teaches, in the order you will actually need them.

If you already commit and push comfortably, skip this. If your palms sweat when someone says "just rebase it," you are exactly who this is for — and the good news is you can ignore rebasing entirely and still ship everything in this book.

---

## B.1 The one mental model

**Git** is a program that runs on your computer and records snapshots of a folder over time. Each snapshot is called a **commit**. A folder that Git is tracking is called a **repository** (**repo** for short). That is the whole idea: a repo is a folder with a memory.

**GitHub** is a website that stores a *copy* of your repo in the cloud so other people (and other machines) can get it. Git is the tool; GitHub is one place to keep repos. They are not the same thing, and you can use Git for years without ever touching GitHub. In this book we use both: Git to record your work, GitHub to share it and to run the automated tests (the green **CI** badge on the repo's front page).

The flow you will repeat all book long is short:

```
edit files → git add → git commit  → (occasionally) git push → GitHub
                     └── local, on your machine ──┘   └── cloud ──┘
```

Everything before `push` happens entirely on your laptop, offline. `push` is the only step that talks to GitHub.

---

## B.2 Install Git (once per machine)

Check whether you already have it. Open a terminal (on macOS, the **Terminal** app; on Windows, **PowerShell** or the **Git Bash** shell you are about to install; on Linux, your usual terminal) and type:

```bash
git --version
```

If you see something like `git version 2.43.0`, you are done — skip to B.3. If you get "command not found," install it:

- **macOS** — the simplest path is to run `git --version` once; macOS offers to install the Xcode Command Line Tools, which include Git. Or, if you use [Homebrew](https://brew.sh), run `brew install git`.
- **Windows** — download and run the installer from [git-scm.com/download/win](https://git-scm.com/download/win). Accept the defaults; this also gives you the **Git Bash** terminal, which behaves like the macOS/Linux examples in this book.
- **Linux** — `sudo apt install git` (Debian/Ubuntu) or `sudo dnf install git` (Fedora).

Run `git --version` again to confirm.

Then tell Git who you are — it stamps this onto every commit. Do this once:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

Use the same email you will use for GitHub (B.4); it links your commits to your account.

---

## B.3 Your first repo: the six commands you actually need

This is the loop from Chapter 1, spelled out. Suppose you have a project folder:

```bash
cd my-project              # move into the folder
git init                   # start tracking it — creates a hidden .git/ folder
```

`git init` is the one-time step that turns an ordinary folder into a repo. You will not run it again for this project.

Now the loop you repeat forever:

```bash
git status                 # 1. what have I changed? (safe; changes nothing)
git add -A                 # 2. stage everything for the next snapshot
git commit -m "message"    # 3. take the snapshot, with a note
```

- **`git status`** is your most-used command. It never changes anything — it just tells you what is modified, what is staged, and what is untracked. When confused, run it.
- **`git add -A`** stages your changes. "Staging" means "these are the files I want in my next commit." The `-A` means *all* changed files.
- **`git commit -m "..."`** records the snapshot. The message should say what changed, e.g. `git commit -m "ch03: add triage CLI + tests"`. That is the exact style every chapter uses.

To see your history:

```bash
git log --oneline          # a compact list of past commits
```

That is genuinely most of Git. Six commands — `init`, `status`, `add`, `commit`, `log`, and (next) `clone` — carry you through the entire book.

> **The `.gitignore` file — the one thing beginners forget.** Some files should *never* be committed: your virtual environment (`.venv/`), Python caches (`__pycache__/`), and — critically — anything with a secret in it (`.env`). Create a plain-text file named `.gitignore` in the repo root listing them, one per line:
>
> ```
> .venv/
> __pycache__/
> .pytest_cache/
> .env
> ```
>
> Git will then pretend those files do not exist for commit purposes. Every chapter's repo ships a `.gitignore`; if you start a fresh project, write one *before* your first commit. Appendix C explains why committing a `.env` can leak an API key to the whole internet.

---

## B.4 Create a GitHub account and get the book's code

Getting the companion code onto your machine does not require an account at all — the repo is public:

```bash
git clone https://github.com/lion-of-naples/idea-to-poc.git
cd idea-to-poc
```

`git clone` downloads a full copy of the repo, history and all, into a new folder. This is how you follow along: clone once, then `cd` into each chapter's folder.

You only need a **GitHub account** when you want to *push your own* work to the cloud (the optional stretch goals, and anything you build after the book). To make one:

1. Go to [github.com](https://github.com) and click **Sign up**. Use the same email you put in `git config` (B.2).
2. Pick a username — this becomes part of your repo URLs (`github.com/<username>/<repo>`), so choose something you would put on a résumé.
3. Verify your email when GitHub sends the confirmation.

That is it. A free account is all you need for everything in this book.

---

## B.5 Push your own work to GitHub

Say you have built something locally and want it in the cloud. First create an empty repo on the website:

1. On [github.com](https://github.com), click the **+** in the top-right → **New repository**.
2. Give it a name. Leave **Public** or **Private** as you prefer (public is fine for portfolio work; private keeps it to yourself).
3. **Do not** check "Add a README" if you already have local files — it avoids a first-push conflict.
4. Click **Create repository**. GitHub then shows you a URL like `https://github.com/<you>/<repo>.git`.

Back in your terminal, connect your local repo to that URL and push:

```bash
git remote add origin https://github.com/<you>/<repo>.git
git branch -M main
git push -u origin main
```

- **`git remote add origin <url>`** tells your local repo where "the cloud copy" lives. `origin` is just the conventional nickname for it.
- **`git push`** uploads your commits. The `-u origin main` part sets `main` as the default so that, from then on, you can push with a bare `git push`.

After the first setup, your daily rhythm is simply: `git add -A`, `git commit -m "..."`, `git push`.

---

## B.6 Authentication: the part that trips everyone up

The first time you `git push`, GitHub needs to know it is really you. **GitHub no longer accepts your account password on the command line** — this surprises everyone. You have two good options; pick one.

**Option 1 — GitHub CLI (easiest).** Install the official `gh` tool from [cli.github.com](https://cli.github.com), then run:

```bash
gh auth login
```

Answer the prompts (choose **GitHub.com**, **HTTPS**, and **Login with a web browser**). It opens a browser, you approve once, and Git will authenticate automatically from then on. This is the least fiddly path and the one we recommend.

**Option 2 — a Personal Access Token (PAT).** If you push over HTTPS without `gh`, Git will ask for a "password." That password is not your account password — it is a token you generate:

1. On GitHub, go to **Settings → Developer settings → Personal access tokens → Tokens (classic)** — or open [github.com/settings/tokens](https://github.com/settings/tokens).
2. Click **Generate new token (classic)**, give it a name, set an expiry, and check the **`repo`** scope.
3. Click **Generate token** and **copy it now** — GitHub shows it only once.
4. When `git push` asks for your password, paste the token instead. Your OS keychain will usually remember it after the first time.

Treat a PAT exactly like an API key (Appendix C): it is a secret, it grants access to your repos, and you should never paste it into a file you might commit.

---

## B.7 The five ways you will get stuck, and the fixes

- **"fatal: not a git repository."** You are not inside a repo folder. `cd` into the project, or run `git init` if it is a brand-new folder.
- **"Authentication failed" on push.** You used your account password instead of a token, or you have not run `gh auth login`. See B.6.
- **You committed a `.venv/` or a `.env` by accident.** Add it to `.gitignore`, then run `git rm -r --cached .venv` (or the filename) and commit again. If a *secret* was committed, treat it as leaked: rotate the key immediately (Appendix C.7).
- **"Your branch is behind."** The cloud copy has commits you do not have locally (common when you edit on two machines). Run `git pull` to bring them down, then push.
- **You are simply lost.** Run `git status`. It almost always tells you the next move. Nothing you can do with `add`, `commit`, and `push` will lose committed work — commits are snapshots, and Git keeps them.

---

## B.8 What you can safely ignore (for now)

Git is enormous, and most of it is optional for shipping POCs. You do **not** need branching, merging, rebasing, stashing, cherry-picking, or pull requests to complete this book. They are powerful once you collaborate with others, and worth learning later — but if you only ever `add`, `commit`, `push`, and occasionally `pull`, you can ship every project in these ten chapters. Learn the rest when a real need for it shows up, not before.

---

*Further reading:*

- *Git — the official book (free):* [git-scm.com/book](https://git-scm.com/book/en/v2)
- *GitHub's own quickstart:* [docs.github.com/get-started](https://docs.github.com/en/get-started/quickstart)
- *GitHub CLI:* [cli.github.com](https://cli.github.com)
- *Personal access tokens:* [docs.github.com — managing PATs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- *Companion repo:* [github.com/lion-of-naples/idea-to-poc](https://github.com/lion-of-naples/idea-to-poc)
