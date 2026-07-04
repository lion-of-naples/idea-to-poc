# ch07 — From Research Paper to Running Code (Rao-Blackwell)

**Take a theorem off the page and make it a thing that runs — and that you can check.**

Chapter 7 of *Idea to POC*. Every earlier chapter wrapped an *API*. This one is
different: the source is a **research paper** — the author's survey
*Blackwell's Algorithms Powering Modern AI* — and the deliverable is a runnable,
self-verifying implementation of one result from it: the **Rao-Blackwell
theorem** (Blackwell, 1947).

In plain terms, the theorem says: take any unbiased estimator `S` of a
parameter, condition it on a **sufficient statistic** `T`, and the new estimator
`S* = E[S | T]` is still unbiased but has **weakly lower variance**. It's not an
existence result — it's a constructive recipe for improving an estimator. This
tool makes that recipe executable and then **empirically confirms the variance
drop it promises**.

The paper's worked example (its Section 3.1) is the coin: estimate the
probability `theta` of heads. The naive estimator uses only the first flip,
`S = X_1` (variance `theta(1-theta)`); the sufficient statistic is the head
count `T = sum(X_i)`, and Rao-Blackwellization gives `S* = T/n`, the sample mean
(variance `theta(1-theta)/n`). We reproduce exactly that, and confirm the
inequality holds on real numbers.

## What you'll ship

A single file (`rao_blackwell.py`) that runs two ways:

- **As a CLI** — `python3 rao_blackwell.py` prints a report proving `Var(S*) <= Var(S)` (add `--json` for machine output).
- **As a Gradio web app** (`--serve`) — drag the sliders for `theta`, `n`, and `trials` and watch the variance collapse.

Plus a **deterministic** offline test suite that verifies the *theorem itself* —
unbiasedness, the variance inequality, the paper's closed-form formulas, and the
`n = 1` equality case — with no network and without `gradio` installed.

## Requirements

- **Python 3.10+**
- `pip install -r requirements.txt` (`numpy` is the real dependency; `gradio` is only for the optional UI; `pytest` for the tests)
- No API key, no account, no network — this is a from-paper algorithm, not an API wrapper.

## Quickstart

```bash
cd ch07-blackwell-paper-to-code
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run the coin experiment (the paper's Section 3.1 example):
python3 rao_blackwell.py --theta 0.3 --n 10 --trials 50000 --seed 0

# The ML tie-in: the same conditioning trick as a Monte-Carlo estimator:
python3 rao_blackwell.py --demo gradient

# Machine-readable output, or the Gradio web app:
python3 rao_blackwell.py --json
python3 rao_blackwell.py --serve
```

Example output:

```
Rao-Blackwell experiment  [coin]
  theta = 0.300   n = 10   trials = 50,000

  Estimator          empirical mean     empirical variance
  S  (naive, X_1)        0.2974            0.208945
  S* (Rao-Black.)        0.3008            0.020961

  Theory   Var(S)  = theta(1-theta)   = 0.210000
  Theory   Var(S*) = theta(1-theta)/n = 0.021000

  Variance removed by Rao-Blackwellization: 90.0%
  Theorem  Var(S*) <= Var(S):  HOLDS
```

### Options

| Flag | Default | What it does |
|------|---------|--------------|
| `--theta` | `0.5` | true probability of heads, in `[0, 1]` |
| `--n` | `10` | flips per trial (`n = 1` means no improvement is possible) |
| `--trials` | `50000` | Monte-Carlo trials used to estimate the variances |
| `--seed` | `0` | RNG seed — same seed gives identical numbers every run |
| `--demo` | `coin` | which experiment: `coin` (the paper's example) or `gradient` (the ML framing) |
| `--serve` | off | launch the Gradio web app instead of running once |
| `--json` | off | print the result as JSON instead of a formatted report |

## From paper to code (the mapping)

| Paper (Section 3.1) | Code |
|---|---|
| Naive estimator `S = X_1` | `naive_estimator(samples)` — the first column |
| Sufficient statistic `T = sum(X_i)` | folded into `rao_blackwellize` |
| Rao-Blackwellized `S* = E[S\|T] = T/n` | `rao_blackwellize(samples)` — the row mean |
| Claim `Var(S*) <= Var(S)` | `summarize(...).theorem_holds` |
| Formula `Var(S) = theta(1-theta)` | `RBResult.theory_naive_var` |
| Formula `Var(S*) = theta(1-theta)/n` | `RBResult.theory_rb_var` |

## How it's built (the 4-step loop)

1. **State the intent in one sentence.** "Implement the Rao-Blackwell theorem so
   it runs and so a test proves the variance actually drops."
2. **Let the AI draft; you review.** The paper supplies the exact estimators and
   the closed-form variances; the productizing work was choosing an
   *architecture that keeps the math pure and reproducible* — separating the
   deterministic core from the one random step.
3. **Make it runnable early.** The core (`naive_estimator`, `rao_blackwellize`,
   `summarize`, `format_result`) is pure, so a scripted fake `sampler` runs the
   whole `run_experiment()` path on a fixed fixture with no RNG — which is
   exactly how the tests work.
4. **End with a commit.** Small, green, and it *proves a theorem*.

## Make it yours

Change `--theta` and `--n` to see the variance reduction scale as `1/n` exactly
as the formula predicts, or switch `--demo gradient` to read the same result as
the Monte-Carlo variance-reduction idea the paper connects to RBPF-SLAM and
policy-gradient RLHF. Because only `_sample_experiment` is random (and it takes
an explicit seed) and the UI is one small `build_demo` function, you can point
the pure core at a different estimator / sufficient-statistic pair — a Poisson
rate, a Gaussian mean — and the tests, the CLI, and the report all stay the same.

## Testing

```bash
pip install -r requirements.txt
pytest -q
```

The suite verifies the **theorem**, not just that the code runs: both estimators
are unbiased (mean `~ theta`), `Var(S*) <= Var(S)`, the empirical variances match
the paper's closed-form `theta(1-theta)` and `theta(1-theta)/n`, `n = 1` gives
equality, and the same seed is reproducible. The full path also runs on a
**scripted fake sampler** with no RNG at all. None of it touches the network or
imports `gradio`.

## Files

| File | Purpose |
|------|---------|
| `rao_blackwell.py` | the pure core, the one random edge (`_sample_experiment`), the Gradio UI, and the CLI |
| `test_rao_blackwell.py` | offline, deterministic tests that verify the theorem (no network, no gradio) |
| `requirements.txt` | `numpy` (runtime) + `gradio` (optional UI) + `pytest` (tests) |
| `.gitignore` | keeps venv / caches / secrets out of git |

---

*Source material: implements the Rao-Blackwell theorem (Section 3.1, including
the coin worked example) from the author's survey
[*Blackwell's Algorithms Powering Modern AI*](https://github.com/lion-of-naples/Blackwell_AI_Survey_2026),
which traces C. R. Rao (1945) and David Blackwell (1947) to modern applications
including Rao-Blackwellized Particle Filters (RBPF-SLAM) and policy-gradient
variance reduction in RLHF. The theorem and its law-of-total-variance proof are
standard results in mathematical statistics. Part of the
[Idea to POC](../README.md) book project.*
