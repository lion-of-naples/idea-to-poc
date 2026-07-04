#!/usr/bin/env python3
"""rao_blackwell — turn a theorem from a research paper into running, verifiable code.

Chapter 7 of *Idea to POC*. Every earlier chapter wrapped an *API*. This one is
different: the "source" is a research paper — the author's own survey,
*Blackwell's Algorithms Powering Modern AI* — and the job is to take one result
off the page and make it a thing that runs and that you can check.

We implement the **Rao-Blackwell theorem** (Blackwell, 1947). In plain terms:
take any unbiased estimator `S` of a parameter, condition it on a *sufficient
statistic* `T`, and the resulting estimator `S* = E[S | T]` is still unbiased
but has *weakly lower variance*. The theorem is not an existence result — it's a
constructive recipe for improving an estimator, and here we make that recipe
executable and then empirically confirm the variance drop it promises.

The paper gives an exact worked example (Section 3.1): estimate the probability
`theta` a coin lands heads. The naive estimator uses only the first flip,
`S = X_1` (variance `theta*(1-theta)`); the sufficient statistic is the count of
heads `T = sum(X_i)`, and Rao-Blackwellization yields `S* = T/n`, the sample
mean (variance `theta*(1-theta)/n`). We reproduce that, prove `Var(S*) <= Var(S)`
empirically, and show the same conditioning trick as the ML idea the paper
draws out (lower-variance Monte-Carlo estimates — the seed of RBPF-SLAM and
policy-gradient variance reduction).

Architecture (the house pattern from Chapters 2-6, adapted for a paper):
    * The CORE is pure math: given samples it computes the naive estimate, the
      Rao-Blackwellized estimate, and the variance statistics that verify the
      theorem. No randomness, no I/O. Unit-tested offline, fully deterministic.
    * Exactly ONE function, `_sample_experiment`, is impure — it draws random
      trials. It takes an explicit seed and returns a plain array, so tests are
      deterministic and need no network and no SDK.
    * A `sampler` seam is injected into `run_experiment`, so a scripted fake
      drives the whole path in tests — the same trick used in Chapters 4-6.

Usage:
    python3 rao_blackwell.py                          # coin demo, default settings
    python3 rao_blackwell.py --theta 0.3 --n 20 --trials 20000 --seed 7
    python3 rao_blackwell.py --demo gradient          # the ML variance-reduction demo
    python3 rao_blackwell.py --json                   # machine-readable result
    python3 rao_blackwell.py --serve                  # optional Gradio UI
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

DEFAULT_THETA = 0.5      # true probability of heads
DEFAULT_N = 10           # flips per trial (n=1 => no improvement possible)
DEFAULT_TRIALS = 50_000  # Monte-Carlo trials used to estimate the variances
DEFAULT_SEED = 0

APP_TITLE = "Rao-Blackwell: a theorem you can run"
APP_DESCRIPTION = (
    "Implements the Rao-Blackwell theorem (Blackwell, 1947): conditioning an "
    "unbiased estimator on a sufficient statistic keeps it unbiased but lowers "
    "its variance. Pick theta, n, and trials, and watch Var(S*) <= Var(S)."
)


# --------------------------------------------------------------------------
# Core (pure). Given trial data it computes both estimators and the variance
# statistics that verify the theorem. No randomness lives here, which is what
# makes the whole result deterministic and testable offline.
# --------------------------------------------------------------------------
@dataclass
class RBResult:
    """The parsed, structured outcome of one Rao-Blackwell experiment."""

    theta: float = 0.0
    n: int = 0
    trials: int = 0
    naive_mean: float = 0.0          # empirical E[S]   (should be ~ theta)
    rb_mean: float = 0.0             # empirical E[S*]  (should be ~ theta)
    naive_var: float = 0.0           # empirical Var(S)
    rb_var: float = 0.0              # empirical Var(S*)
    theory_naive_var: float = 0.0    # theta*(1-theta)
    theory_rb_var: float = 0.0       # theta*(1-theta)/n
    variance_reduction: float = 0.0  # 1 - rb_var/naive_var  (fraction removed)
    theorem_holds: bool = False      # rb_var <= naive_var (+ small tolerance)
    label: str = "coin"


def naive_estimator(samples: Any) -> Any:
    """The naive unbiased estimator S = X_1: use only the FIRST flip of each trial.

    `samples` is a (trials x n) array of 0/1 flips. Returns one estimate per
    trial (the first column). Unbiased for theta, but throws away n-1 flips.
    """
    import numpy as np
    arr = np.asarray(samples)
    if arr.ndim != 2 or arr.shape[1] < 1:
        raise ValueError("samples must be a 2-D (trials x n) array with n >= 1.")
    return arr[:, 0].astype(float)


def rao_blackwellize(samples: Any) -> Any:
    """The Rao-Blackwellized estimator S* = E[S | T] = T/n = the sample mean.

    Conditioning the first-flip estimator on the sufficient statistic
    T = sum(X_i) collapses, for the coin model, to the sample mean of each
    trial's flips (the paper's Section 3.1 result). Still unbiased, lower var.
    """
    import numpy as np
    arr = np.asarray(samples)
    if arr.ndim != 2 or arr.shape[1] < 1:
        raise ValueError("samples must be a 2-D (trials x n) array with n >= 1.")
    return arr.mean(axis=1)


def summarize(samples: Any, theta: float, *, label: str = "coin",
              tolerance: float = 1e-9) -> RBResult:
    """Compute both estimators over the trials and the variance statistics.

    This is the pure heart of the chapter: it turns raw trial data into the
    numbers that confirm (or would refute) the theorem. Population variance
    (ddof=0) matches the closed-form theory formulas.
    """
    import numpy as np
    arr = np.asarray(samples)
    n = int(arr.shape[1])
    trials = int(arr.shape[0])

    naive = naive_estimator(arr)
    rb = rao_blackwellize(arr)

    naive_var = float(np.var(naive, ddof=0))
    rb_var = float(np.var(rb, ddof=0))
    theory_naive_var = float(theta * (1.0 - theta))
    theory_rb_var = float(theta * (1.0 - theta) / n)
    reduction = 0.0 if naive_var == 0.0 else float(1.0 - rb_var / naive_var)

    return RBResult(
        theta=float(theta),
        n=n,
        trials=trials,
        naive_mean=float(np.mean(naive)),
        rb_mean=float(np.mean(rb)),
        naive_var=naive_var,
        rb_var=rb_var,
        theory_naive_var=theory_naive_var,
        theory_rb_var=theory_rb_var,
        variance_reduction=reduction,
        # The theorem: weakly lower variance. Tolerance guards float noise at n=1.
        theorem_holds=bool(rb_var <= naive_var + tolerance),
        label=label,
    )


def format_result(result: RBResult) -> str:
    """Render an `RBResult` as a compact, human-readable report."""
    pct = result.variance_reduction * 100.0
    verdict = "HOLDS" if result.theorem_holds else "VIOLATED"
    lines = [
        f"Rao-Blackwell experiment  [{result.label}]",
        f"  theta = {result.theta:.3f}   n = {result.n}   trials = {result.trials:,}",
        "",
        "  Estimator          empirical mean     empirical variance",
        f"  S  (naive, X_1)    {result.naive_mean:>10.4f}        {result.naive_var:>12.6f}",
        f"  S* (Rao-Black.)    {result.rb_mean:>10.4f}        {result.rb_var:>12.6f}",
        "",
        f"  Theory   Var(S)  = theta(1-theta)   = {result.theory_naive_var:.6f}",
        f"  Theory   Var(S*) = theta(1-theta)/n = {result.theory_rb_var:.6f}",
        "",
        f"  Variance removed by Rao-Blackwellization: {pct:.1f}%",
        f"  Theorem  Var(S*) <= Var(S):  {verdict}",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# The one impure function: the randomness edge. Draws random trials. Takes an
# explicit seed and returns a plain array, so it is fully reproducible and the
# core can be tested against fixtures with no RNG at all.
# --------------------------------------------------------------------------
def _sample_experiment(theta: float, n: int, trials: int, seed: int) -> Any:
    """Draw `trials` independent trials of `n` Bernoulli(theta) coin flips.

    Returns a (trials x n) int array of 0/1. This is the only nondeterministic
    step; everything else in the module is pure given this array.
    """
    import numpy as np
    if not (0.0 <= theta <= 1.0):
        raise ValueError("theta must be in [0, 1].")
    if n < 1:
        raise ValueError("n must be >= 1.")
    if trials < 1:
        raise ValueError("trials must be >= 1.")
    rng = np.random.default_rng(seed)
    return rng.binomial(1, theta, size=(trials, n))


def _sample_gradient(theta: float, n: int, trials: int, seed: int) -> Any:
    """The ML tie-in: the SAME conditioning trick as a Monte-Carlo estimator.

    We reuse the coin machinery to stand in for a single-sample vs.
    n-sample Monte-Carlo estimate of an expectation (the shape of REINFORCE /
    policy-gradient variance reduction the paper draws out). Structurally
    identical to the coin experiment; the label just reframes it.
    """
    return _sample_experiment(theta, n, trials, seed)


# --------------------------------------------------------------------------
# Orchestration: pure core + injected sampler. `sampler` defaults to the real
# randomness edge; tests pass a scripted fake so the whole path runs on fixtures.
# --------------------------------------------------------------------------
def run_experiment(
    *,
    theta: float = DEFAULT_THETA,
    n: int = DEFAULT_N,
    trials: int = DEFAULT_TRIALS,
    seed: int = DEFAULT_SEED,
    label: str = "coin",
    sampler: Callable[..., Any] | None = None,
) -> RBResult:
    """Run one Rao-Blackwell experiment end-to-end and return an `RBResult`.

    `sampler` lets tests inject a fixed array (or a fake) so the whole path is
    deterministic without touching the RNG. By default we use the real
    `_sample_experiment`.
    """
    sampler = sampler or _sample_experiment
    samples = sampler(theta, n, trials, seed)
    return summarize(samples, theta, label=label)


DEMOS: dict[str, Callable[..., Any]] = {
    "coin": _sample_experiment,
    "gradient": _sample_gradient,
}


# --------------------------------------------------------------------------
# Gradio UI (optional). Imported LOCALLY so tests don't need gradio.
# --------------------------------------------------------------------------
def build_demo(sampler: Callable[..., Any] | None = None):
    """Build (but do not launch) the Gradio interface."""
    import gradio as gr  # local import -> offline tests need no gradio

    def _run_ui(theta: float, n: int, trials: int, seed: int) -> str:
        try:
            result = run_experiment(theta=float(theta), n=int(n),
                                    trials=int(trials), seed=int(seed),
                                    sampler=sampler)
        except (ValueError, TypeError) as exc:
            return f"⚠️  {exc}"
        return format_result(result)

    return gr.Interface(
        fn=_run_ui,
        inputs=[
            gr.Slider(0.0, 1.0, value=DEFAULT_THETA, step=0.01, label="theta (true P[heads])"),
            gr.Slider(1, 100, value=DEFAULT_N, step=1, label="n (flips per trial)"),
            gr.Slider(1000, 200000, value=DEFAULT_TRIALS, step=1000, label="trials"),
            gr.Number(value=DEFAULT_SEED, label="seed", precision=0),
        ],
        outputs=gr.Textbox(label="Result", lines=16),
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        flagging_mode="never",
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rao_blackwell",
        description="Run the Rao-Blackwell theorem (Blackwell, 1947) as code and verify it.",
    )
    p.add_argument("--theta", type=float, default=DEFAULT_THETA, help=f"True P[heads] in [0,1] (default: {DEFAULT_THETA}).")
    p.add_argument("--n", type=int, default=DEFAULT_N, help=f"Flips per trial (default: {DEFAULT_N}).")
    p.add_argument("--trials", type=int, default=DEFAULT_TRIALS, help=f"Monte-Carlo trials (default: {DEFAULT_TRIALS}).")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"RNG seed for reproducibility (default: {DEFAULT_SEED}).")
    p.add_argument("--demo", choices=sorted(DEMOS), default="coin", help="Which experiment to run (default: coin).")
    p.add_argument("--serve", action="store_true", help="Launch the Gradio web app instead of running once.")
    p.add_argument("--json", action="store_true", help="Print the result as JSON instead of a formatted report.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.serve:
        build_demo().launch()
        return 0

    try:
        result = run_experiment(
            theta=args.theta, n=args.n, trials=args.trials, seed=args.seed,
            label=args.demo, sampler=DEMOS[args.demo],
        )
    except (ValueError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.__dict__, indent=2))
    else:
        print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
