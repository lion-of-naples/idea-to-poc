# Chapter 1 — Friction-point screenshots

These images back the "Check your screen" callouts in Chapter 1. They are the
*expected* state at each checkpoint, so readers can confirm their setup matches
before moving on. Capture them on a clean run and keep them current when the
tooling UI changes.

| File | Callout | What to capture |
| --- | --- | --- |
| `cursor-anatomy.png` | Step 3.2, "Get your bearings" | The full Cursor window with `ch01-devbox` open, annotated for the current AI-first layout: **left rail** (New Agent / Search / Repositories — label "not the file tree"), **agent/chat panel** (center-left, the "Plan, Build…" box), **editor pane** (center, with Browser/zsh/file tabs on top), and the **file panel on the right** (`ch01-devbox` header + files). Add the labels in an image editor before committing. |
| `venv-activated.png` | Step 3.2, after `source .venv/bin/activate` | Terminal showing the prompt now prefixed with `(.venv)`. |
| `new-file-ui.png` | Step 3.2, "Where the code goes" | The right-hand file panel with the `ch01-devbox` header hovered and the **New File** button visible at its top-right. (The author's screenshot already captures this exact state.) |
| `readiness-report.png` | Step 3.4, after `python3 devbox.py` | Terminal showing the full `AM I READY TO BUILD?` report ending in `READY ✅`. |
| `ci-green.png` | Step 3.6, after the commit | The repo on GitHub showing a green passing check / Actions badge. |

Recommended: 1400px wide max, PNG, cropped tight to the relevant UI.
