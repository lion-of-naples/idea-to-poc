"""Offline, deterministic tests for the Rao-Blackwell POC.

These tests verify the *theorem itself*, not just that the code runs:
    * both estimators are unbiased (mean ~ theta),
    * Var(S*) <= Var(S) (the Rao-Blackwell inequality),
    * the empirical variances match the paper's closed-form formulas
      theta(1-theta) and theta(1-theta)/n,
    * n == 1 gives equality (no improvement possible),
    * the full path runs on a *scripted fake sampler* with no RNG at all.

They need numpy (a real runtime dependency) but NO network and NO gradio.
Randomness is either seeded (reproducible) or replaced by a fixed fixture.
"""

import json
import subprocess
import sys

import numpy as np
import pytest

import rao_blackwell as rb


# --------------------------------------------------------------------------
# Pure core: the two estimators
# --------------------------------------------------------------------------
def test_naive_estimator_uses_only_first_flip():
    samples = np.array([[1, 0, 0, 0], [0, 1, 1, 1]])
    got = rb.naive_estimator(samples)
    assert list(got) == [1.0, 0.0]           # first column only


def test_rao_blackwellize_is_the_sample_mean():
    samples = np.array([[1, 0, 0, 0], [1, 1, 1, 1]])
    got = rb.rao_blackwellize(samples)
    assert list(got) == [0.25, 1.0]          # T/n per trial


def test_estimators_reject_bad_shapes():
    with pytest.raises(ValueError):
        rb.naive_estimator(np.array([1, 0, 1]))          # 1-D, not 2-D
    with pytest.raises(ValueError):
        rb.rao_blackwellize(np.empty((3, 0)))            # n == 0


# --------------------------------------------------------------------------
# summarize(): the numbers that verify the theorem, on a FIXED fixture
# --------------------------------------------------------------------------
def _fixed_trials():
    """A small, hand-built (trials x n) fixture — no RNG."""
    return np.array([
        [1, 1, 0, 0],
        [0, 1, 1, 0],
        [1, 0, 0, 1],
        [0, 0, 1, 1],
    ])


def test_summarize_reports_both_variances_and_theorem_holds():
    samples = _fixed_trials()
    res = rb.summarize(samples, theta=0.5)
    assert res.n == 4 and res.trials == 4
    # S = first column = [1,0,1,0] -> var 0.25 ; S* = row means = all 0.5 -> var 0
    assert res.naive_var == pytest.approx(0.25)
    assert res.rb_var == pytest.approx(0.0)
    assert res.theorem_holds is True
    assert res.variance_reduction == pytest.approx(1.0)


def test_summarize_theory_formulas_match_the_paper():
    res = rb.summarize(_fixed_trials(), theta=0.3)
    assert res.theory_naive_var == pytest.approx(0.3 * 0.7)        # theta(1-theta)
    assert res.theory_rb_var == pytest.approx(0.3 * 0.7 / 4)       # theta(1-theta)/n


# --------------------------------------------------------------------------
# The theorem, empirically, via the REAL seeded sampler (reproducible)
# --------------------------------------------------------------------------
def test_theorem_holds_empirically_and_matches_theory():
    res = rb.run_experiment(theta=0.3, n=10, trials=40_000, seed=0)
    # Unbiasedness: both estimators center on theta.
    assert res.naive_mean == pytest.approx(0.3, abs=0.02)
    assert res.rb_mean == pytest.approx(0.3, abs=0.01)
    # The Rao-Blackwell inequality.
    assert res.rb_var <= res.naive_var
    assert res.theorem_holds is True
    # Empirical variances track the closed-form theory (loose MC tolerance).
    assert res.naive_var == pytest.approx(res.theory_naive_var, abs=0.02)
    assert res.rb_var == pytest.approx(res.theory_rb_var, abs=0.005)
    # With n=10 we expect ~90% of the variance removed.
    assert res.variance_reduction == pytest.approx(0.9, abs=0.05)


def test_same_seed_is_reproducible():
    a = rb.run_experiment(theta=0.5, n=8, trials=5_000, seed=42)
    b = rb.run_experiment(theta=0.5, n=8, trials=5_000, seed=42)
    assert a.naive_var == b.naive_var and a.rb_var == b.rb_var


def test_n_equals_one_gives_equality_no_improvement():
    # With a single flip, S* == S, so variances are equal (theorem: equality case).
    res = rb.run_experiment(theta=0.5, n=1, trials=20_000, seed=1)
    assert res.rb_var == pytest.approx(res.naive_var)
    assert res.theorem_holds is True
    assert res.variance_reduction == pytest.approx(0.0, abs=1e-9)


def test_sampler_validates_inputs():
    with pytest.raises(ValueError):
        rb._sample_experiment(theta=1.5, n=4, trials=10, seed=0)   # theta out of range
    with pytest.raises(ValueError):
        rb._sample_experiment(theta=0.5, n=0, trials=10, seed=0)   # n < 1
    with pytest.raises(ValueError):
        rb._sample_experiment(theta=0.5, n=4, trials=0, seed=0)    # trials < 1


# --------------------------------------------------------------------------
# Full path via a SCRIPTED FAKE sampler — no RNG at all
# --------------------------------------------------------------------------
def _scripted_sampler(array):
    """Return a fake sampler that ignores args and returns a fixed array."""
    calls = {"n": 0}

    def sampler(theta, n, trials, seed):
        calls["n"] += 1
        sampler.last_args = (theta, n, trials, seed)
        return np.asarray(array)

    sampler.calls = calls
    return sampler


def test_run_experiment_full_path_with_scripted_sampler():
    fake = _scripted_sampler(_fixed_trials())
    res = rb.run_experiment(theta=0.5, n=4, trials=4, seed=0, sampler=fake)
    assert fake.calls["n"] == 1                     # the edge was called exactly once
    assert res.naive_var == pytest.approx(0.25)     # same fixture -> same numbers
    assert res.rb_var == pytest.approx(0.0)
    assert res.theorem_holds is True


def test_format_result_is_readable():
    res = rb.run_experiment(theta=0.5, n=4, trials=4, seed=0,
                            sampler=_scripted_sampler(_fixed_trials()))
    text = rb.format_result(res)
    assert "Rao-Blackwell experiment" in text
    assert "Var(S*) <= Var(S):  HOLDS" in text
    assert "theta(1-theta)" in text


# --------------------------------------------------------------------------
# CLI paths (run the module as a script; no network, quick trial counts)
# --------------------------------------------------------------------------
def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "rao_blackwell.py", *args],
        capture_output=True, text=True,
    )


def test_cli_default_coin_demo_runs():
    proc = _run_cli("--trials", "2000", "--seed", "0")
    assert proc.returncode == 0
    assert "Rao-Blackwell experiment" in proc.stdout
    assert "HOLDS" in proc.stdout


def test_cli_json_output_parses():
    proc = _run_cli("--trials", "2000", "--seed", "0", "--json")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["theorem_holds"] is True
    assert data["label"] == "coin"


def test_cli_gradient_demo_runs():
    proc = _run_cli("--demo", "gradient", "--trials", "2000", "--seed", "0")
    assert proc.returncode == 0
    assert "[gradient]" in proc.stdout


def test_cli_bad_theta_exits_nonzero():
    proc = _run_cli("--theta", "2.0", "--trials", "1000")
    assert proc.returncode == 2
    assert "Error:" in proc.stderr
