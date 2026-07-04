# Sample POC

A POC scaffolded with the Chapter 10 method kit. It already follows the
house pattern: a pure core, one isolated impure edge, an injectable seam,
and offline tests.

## Run the tests (offline)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Run it (live)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python sample_poc.py "your task here"
```

## Next steps

1. Replace `build_prompt` / `parse_response` with your real logic (keep them pure).
2. Keep the SDK import inside `_call_model` (the edge stays isolated).
3. Add tests that drive `run` through the scripted `caller` (never a live key).

Project slug: `sample-poc`
