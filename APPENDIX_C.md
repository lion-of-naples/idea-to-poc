# Appendix C — Python & Virtual Environments

*From the book* **Idea to POC: Shipping Real Software with AI Tools and Agents**

Every chapter in this book runs the same four lines before anything interesting happens:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 the_tool.py
pytest -q
```

Chapter 1 uses them without slowing down to explain *what* a virtual environment is or *why* you make one every single time. This appendix does. Like Appendices A (Git) and B (API keys), it starts from zero: install Python, understand the four lines above, and get un-stuck when they misbehave. You do not need to be a Python programmer to follow the book — you need to run these four lines with confidence. That is all this teaches.

---

## C.1 Do you already have Python? Which one?

The book's tools target **Python 3.10 or newer** (the automated tests run on 3.10 and 3.12). Check what you have:

```bash
python3 --version
```

If you see `Python 3.10.x` or higher, you are set — skip to C.3. If you see `Python 2.7`, an "unknown command" error, or a version below 3.10, install a current Python (C.2).

> **`python` vs `python3` — the classic confusion.** On many Macs and Linux systems, the bare command `python` either does not exist or points at an ancient Python 2. The command that reliably means "modern Python" is `python3`, which is why every example in this book uses it. On Windows the command is usually just `python`. Rule of thumb: try `python3` first; if that is "not found," try `python`. Once you are *inside* an activated virtual environment (C.3), plain `python` becomes safe to use because it points at that environment's interpreter.

---

## C.2 Install Python (once per machine)

- **macOS** — the cleanest option is [Homebrew](https://brew.sh): `brew install python`. Alternatively, download the official installer from [python.org/downloads](https://www.python.org/downloads/). Avoid relying on the old system Python that ships with macOS.
- **Windows** — download from [python.org/downloads](https://www.python.org/downloads/) and run the installer. **Check the box "Add python.exe to PATH"** on the first screen — skipping it is the single most common Windows setup mistake, and it means the terminal cannot find Python afterward.
- **Linux** — you very likely already have it. If not: `sudo apt install python3 python3-venv python3-pip` (Debian/Ubuntu) or `sudo dnf install python3` (Fedora). The `python3-venv` package matters — some minimal Linux images ship Python without the `venv` module.

Confirm with `python3 --version` (or `python --version` on Windows). You want 3.10 or higher.

`pip`, Python's package installer, comes bundled with modern Python. Confirm it too:

```bash
python3 -m pip --version
```

---

## C.3 What a virtual environment is (and why every chapter makes one)

Here is the problem a virtual environment solves. Chapter 3 needs the `openai` package; Chapter 4 needs `anthropic`; Chapter 5 needs `gradio`. If you install all of those into your *system* Python, versions collide, one project's upgrade quietly breaks another, and eventually your Python is a junk drawer nobody can reason about. This is so common it has a name: "dependency hell."

A **virtual environment** (venv) is the fix: a private, throwaway copy of Python that lives *inside your project folder*, with its own isolated set of installed packages. Install `gradio` into a project's venv and it exists only there — it cannot touch your system Python or any other project. Delete the folder and every trace is gone. That is why each chapter makes a fresh one: each POC gets a clean, isolated sandbox.

**Create one:**

```bash
python3 -m venv .venv
```

This creates a folder named `.venv` in your current directory. (`-m venv` means "run Python's built-in `venv` module"; `.venv` is just the conventional folder name — the leading dot keeps it tidy and it is always `.gitignore`'d, per Appendix A.3.)

**Activate it** — this is the step beginners forget:

```bash
source .venv/bin/activate          # macOS / Linux / Git Bash
```

On **Windows PowerShell** the command is different:

```powershell
.venv\Scripts\Activate.ps1
```

You know it worked when your prompt gains a `(.venv)` prefix. From that moment, `python` and `pip` refer to the *environment's* copies, not your system's. Everything you install now lands inside `.venv/` and nowhere else.

**Deactivate** when you are done, or just close the terminal:

```bash
deactivate
```

> **Activation is per-terminal, like `export` in Appendix B.** A venv is only active in the terminal where you ran `source ... activate`, and only until you close it. Open a new terminal to work on a chapter and you must activate again first. "It says the package isn't installed, but I installed it yesterday!" almost always means: you forgot to activate the venv in this session.

---

## C.4 Installing packages with `pip` and `requirements.txt`

Once a venv is active, `pip` installs packages into it. You can install one directly:

```bash
pip install pytest
```

But every chapter pins its dependencies in a file called **`requirements.txt`** — a plain list of packages (sometimes with versions), one per line:

```
pytest
openai>=1.0
```

Installing them all at once is the standard move, and the line you will type dozens of times in this book:

```bash
pip install -r requirements.txt
```

The `-r` means "read the requirements from this file." This is how a project declares exactly what it needs so that anyone — including future you, on a different machine — can recreate the same environment with one command. When you start your own project, you create the reverse with:

```bash
pip freeze > requirements.txt      # record everything currently installed
```

To see what is installed in the active venv at any time: `pip list`.

---

## C.5 Running the tools and the tests

With the venv active and requirements installed, running a chapter's tool is just:

```bash
python3 the_tool.py --help         # most tools have a --help
python3 the_tool.py                # run it
```

And running its test suite — which needs **no API key and no network**, by design — is:

```bash
pytest -q
```

`pytest` discovers every file named `test_*.py`, runs the functions inside, and prints a summary like `31 passed in 0.4s`. A green result means the code works on your machine exactly as it does in the book's automated CI. If `pytest` reports "command not found," it is not installed in the *active* venv — run `pip install pytest` (or `pip install -r requirements.txt`) with the venv activated.

---

## C.6 The whole loop, start to finish

Putting C.3–C.5 together, here is the exact sequence for following any chapter from a fresh clone (Appendix A explains the `git clone`):

```bash
git clone https://github.com/lion-of-naples/idea-to-poc.git
cd idea-to-poc/ch03-openai-triage        # pick a chapter

python3 -m venv .venv                     # 1. make an isolated environment
source .venv/bin/activate                 # 2. activate it   (prompt shows (.venv))
pip install -r requirements.txt           # 3. install this chapter's packages
pytest -q                                 # 4. prove it works offline
python3 triage.py --help                  # 5. run the tool
```

Do this once per chapter. When you move to the next chapter, `cd` into its folder and repeat — a new venv keeps each POC's dependencies cleanly separated.

---

## C.7 The five ways you will get stuck, and the fixes

- **"command not found: python3"** — Python is not installed, or (on Windows) not on your PATH. See C.2; on Windows, re-run the installer and check "Add python.exe to PATH."
- **"No module named X" even though you installed it** — you are not in an activated venv, or you are in the wrong one. Look for `(.venv)` in your prompt; if it is missing, run `source .venv/bin/activate` (C.3). This is the number-one beginner issue.
- **"externally-managed-environment" error from `pip`** — you are trying to `pip install` into the *system* Python, which modern Linux/macOS protect. The fix is the whole point of this appendix: make and activate a venv first, then `pip install` inside it.
- **`pytest: command not found`** — pytest is not installed in the active venv. `pip install -r requirements.txt` (or `pip install pytest`) with the venv active.
- **PowerShell won't run the activate script** ("running scripts is disabled") — run once, as needed: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again. Or use Git Bash (Appendix A) and the `source` syntax.

A venv is disposable. If one gets into a weird state, the fastest fix is often to delete and rebuild it: `deactivate`, `rm -rf .venv`, then repeat the four lines from C.6. You lose nothing — your code is untouched; only the installed packages are rebuilt.

---

## C.8 What you can safely ignore (for now)

The Python packaging world has many tools — `conda`, `poetry`, `pipenv`, `uv`, `pyenv`, and more. They are genuinely useful at scale, and worth exploring once you are building larger systems. But you do **not** need any of them for this book. The built-in `venv` plus `pip` plus a `requirements.txt` — the four lines at the top of this appendix — carry you through all ten chapters. Learn the fancier tools when a real need appears, not before.

---

*Further reading:*

- *Python — official downloads:* [python.org/downloads](https://www.python.org/downloads/)
- *Python — virtual environments tutorial:* [docs.python.org — venv](https://docs.python.org/3/library/venv.html)
- *Python — installing packages with pip:* [packaging.python.org tutorial](https://packaging.python.org/en/latest/tutorials/installing-packages/)
- *pytest — getting started:* [docs.pytest.org](https://docs.pytest.org/en/stable/getting-started.html)
- *Companion repo:* [github.com/lion-of-naples/idea-to-poc](https://github.com/lion-of-naples/idea-to-poc)
