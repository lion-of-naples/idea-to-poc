# Chapter 9 — Ship, Host, and Share

Turn a working POC folder into **deploy-ready** and **portfolio-ready** artifacts
for two hosts at once: **Cloudflare Pages** and a **Hugging Face Space**.

A POC that only runs on your laptop is invisible. This chapter's tool closes the
last mile: it scans your POC, then renders the boilerplate every host wants —
`wrangler.toml` + a static landing page for Cloudflare, an `app.py` + Space
`README.md` for Hugging Face, and a portfolio README that explains what you built,
how to run it, and where it's hosted.

## What's here

| File | What it is |
| --- | --- |
| `package_poc.py` | The packager: pure core + isolated disk edges + injectable polish seam + CLI |
| `test_package_poc.py` | 31 offline tests (no key, no network, no third-party SDK) |
| `deploy_cloudflare.sh` | Documented live deploy: `wrangler pages deploy` |
| `deploy_huggingface.sh` | Documented live deploy: create Space + upload files |
| `sample_poc/` | A tiny sample POC (reverse a string) to package |
| `requirements.txt` | `anthropic` (optional `--polish` only) + `pytest` |

## Run the tests (offline)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Everything runs offline. The optional model-polish path imports `anthropic`
**locally**, only when you pass `--polish` with a real key, so it is never touched
by the tests.

## Package a POC

```bash
python package_poc.py sample_poc --summary "Reverses a string." --out ship_out
```

That writes:

```
ship_out/
  cloudflare/wrangler.toml
  cloudflare/public/index.html
  huggingface/README.md
  huggingface/app.py
  PORTFOLIO_README.md
```

Preview without writing anything:

```bash
python package_poc.py sample_poc --dry-run
python package_poc.py sample_poc --trace --dry-run   # manifest JSON to stderr
```

## Optional: polish the README with a model (live)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python package_poc.py sample_poc --summary "Reverses a string." --polish
```

Without a key, `--polish` exits cleanly with a message — it never crashes and the
tests never need it.

## Ship it for real (documented live paths)

**Cloudflare Pages** (needs `npm install -g wrangler` + `wrangler login`):

```bash
./deploy_cloudflare.sh ship_out my-first-poc
```

**Hugging Face Space** (needs a write token from
https://huggingface.co/settings/tokens):

```bash
export HF_TOKEN="hf_..."
./deploy_huggingface.sh ship_out <your-username> my-first-poc
```

## Design notes

- **Pure core** — `build_manifest`, `render_*`, `build_plan`, `render_plan`,
  `slugify`, `detect_entrypoint`, `_safe_relpath` take plain data and return
  strings/dataclasses. No disk, no network.
- **Isolated impure edges** — only `read_poc` (reads the folder) and `write_plan`
  (writes artifacts) touch the filesystem, and both validate every path so nothing
  can escape the output directory.
- **Injectable seam** — `package(manifest, out, polisher=...)` takes a
  `polisher(summary, draft) -> str`. Tests inject a scripted fake; the CLI builds a
  real one that imports `anthropic` locally only with `--polish`.

## Swap the host

The renderers are independent functions. Want Vercel or Fly.io instead of
Cloudflare? Add a `render_vercel_json` alongside `render_wrangler_toml` and append
it to `build_plan`. The manifest, the seam, and the tests don't change.
