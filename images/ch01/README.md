# Chapter 1 — Friction-point screenshots

These images back the "Check your screen" callouts in Chapter 1. They are the
*expected* state at each checkpoint, so readers can confirm their setup matches
before moving on. Capture them on a clean run and keep them current when the
tooling UI changes.

| File | Callout | What to capture | Status |
| --- | --- | --- | --- |
| `cursor-anatomy.png` | Step 3.2, "Get your bearings" | The full Cursor window with `ch01-devbox` open: **left rail** (New Agent / Search / Automations / Customize / Repositories), the center **agent/chat panel** (the "Plan, Build…" box showing **Composer 2.5 Fast**), and the **Free Plan** account footer. | ✅ captured |
| `venv-activated.png` | Step 3.2, after `source .venv/bin/activate` | Terminal showing `git init` ("Reinitialized existing Git repository") followed by the venv activation — prompt now prefixed with `(.venv)`. | ✅ captured |
| `new-file-ui.png` | Step 3.2, "Where the code goes" | The right-hand file panel with the `ch01-devbox` header hovered and the **New File** button visible at its top-right. | ✅ captured (updated) |
| `usage-limit.png` | Step 3.5 sidebar, "out of usage" | Cursor showing the **"You're paused until your usage resets"** banner with **Get More Usage** — the monthly-allowance (billing) limit, distinct from the per-chat context window. | ✅ captured |
| `gh-install.png` | Step 3.7, install the GitHub CLI | Terminal running `brew install gh` (Homebrew formula download). | ✅ captured |
| `push-to-github.png` | Step 3.7, Option A push | Terminal showing the full `gh auth login` device-code flow (one-time code shown **in the terminal**) and `gh repo create … --source=. --remote=origin --push` succeeding. | ✅ captured |
| `readiness-report.png` | Step 3.4, after `python3 devbox.py` | Terminal showing the full `AM I READY TO BUILD?` report ending in `READY ✅`. | ⏳ needed |
| `ci-green.png` | Step 3.7, after CI runs | The repo on GitHub showing a green passing Actions check, or the README passing badge. | ⏳ needed |

Recommended: 1400px wide max, PNG, cropped tight to the relevant UI.
