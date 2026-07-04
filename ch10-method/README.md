# Chapter 10 — The Repeatable POC Method

The whole book, as one tool. Nine chapters each shipped a domain POC that shared
one shape: a **pure core**, an **isolated impure edge**, an **injectable seam**,
**offline tests**, and a **README**. This chapter turns that method into code with
two jobs:

- **`scaffold`** — generate a new POC skeleton that already follows the house
  pattern, so every new idea starts from the finish line.
- **`lint`** — point it at any repo/folder and score it against the method's rules,
  turning "is this shippable?" into a checklist you run.

## What's here

| File | What it is |
| --- | --- |
| `method_kit.py` | The kit: pure core (scaffold renderers + lint rules) + isolated disk edges + injectable advisor seam + CLI |
| `test_method_kit.py` | 32 offline tests (no key, no network, no third-party SDK) |
| `sample_repo/` | A tiny house-pattern POC to lint (scores 100/100) |
| `requirements.txt` | `anthropic` (optional `--advise` only) + `pytest` |

## Run the tests (offline)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Scaffold a new POC

```bash
python method_kit.py scaffold "My Cool POC" --out new_poc
python method_kit.py scaffold "My Cool POC" --dry-run   # preview, write nothing
```

The scaffold it writes **imports offline and passes its own tests immediately** —
fill in `build_prompt` / `parse_response` with your real logic, keep the SDK import
inside `_call_model`, and drive `run` through a scripted `caller` in tests.

## Lint an existing repo

```bash
python method_kit.py lint sample_repo
python method_kit.py lint sample_repo --json     # structured scorecard
```

The rules checked:

1. **has_tests** — at least one `test_*.py`
2. **has_readme** — a README is present
3. **has_requirements** — dependencies are pinned
4. **edges_isolated** — no vendor SDK imported at module top-level (edges stay local)
5. **seam_injectable** — a source function takes an injectable seam (`caller`/`sampler`/`advisor`/…)
6. **no_eval** — no `eval`/`exec`

`lint` exits `0` when every rule passes, `3` when any rule fails (so it's CI-usable),
and `2` when the path is missing.

## Optional: model-written next steps (live)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python method_kit.py lint sample_repo --advise
```

Without a key, `--advise` exits cleanly with a message — it never crashes, and the
tests never need it.

## Design notes

- **Pure core** — every `render_*`, every `check_*`, `score_repo`, `render_report`,
  `slugify`, `module_name`, `_safe_relpath`. Data in, data out. No disk, no network.
- **Isolated impure edges** — only `scan_repo` (reads a folder) and `write_scaffold`
  (writes files) touch the filesystem, and both validate every path.
- **Injectable seam** — `lint(repo, advisor=...)` takes an `advisor(report) -> str`.
  Tests inject a scripted fake; the CLI builds a real one that imports `anthropic`
  locally only with `--advise`.

The kit follows the exact method it teaches — and its own tests prove the scaffold
it emits scores 100/100 against its own rules.
