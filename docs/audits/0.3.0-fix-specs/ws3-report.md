Done. Here's the report.

## Report

### What changed
- **Per-trial locking for queueing runs.** `Loop.run()` no longer wraps `_run()` in the lock for `--wait` runs. `_run()` now takes the lock around the one-time manifest write and around **each trial** (`incumbent = self._incumbent()` … `_one_trial(...)`), so each trial is atomic and the lock is released between trials.
- **Incumbent re-read per trial.** The incumbent is read from the ledger inside each trial's lock instead of once before the loop, so a peer's kept trial is visible on the next trial.
- **Fail-fast behavior preserved.** For `wait_for_lock=False`, `run()` still claims the ledger for the whole run. Without this, a second `--no-wait` process could slip into the gap between trials and both would run, breaking the existing roadmap acceptance test. (This is the one deliberate qualification: `--wait` shares per trial; `--no-wait` still refuses at startup.)
- `LedgerLock` is functionally unchanged (exclusive, re-entrant, OS-released); only its docstring was corrected.

### Files
- `src/labloop/loop.py` — per-trial lock + per-trial incumbent re-read; stores `self.wait_for_lock`; docstrings.
- `src/labloop/lock.py` — docstring only.
- `tests/test_directions.py` — 3 new tests.

### Why
Root cause was `with self.lock: return self._run(trials)`: one lock hold covered all trials, so two `--wait` directions serialized whole runs and the faster could starve the other. Locking inside the loop keeps index/judge/record atomic but releases between trials; re-reading `_incumbent()` stops a stale in-memory bar.

### New tests
1. `test_the_ledger_lock_is_taken_per_trial_not_per_run` — spy lock counts acquisitions; deterministic, fails on old code (1 acquisition vs ≥3).
2. `test_a_peers_kept_trial_sets_the_bar_for_the_next_trial` — a peer keeps a better trial mid-run; the next trial must revert against it. Deterministic, fails on old code.
3. `test_two_directions_run_concurrently_over_one_ledger` — two threads, shared ledger, slow run; asserts both make progress, indices unique/dense, per-direction incumbents consistent with the ledger.

Note: `flock` handoff is not FIFO (the releaser can re-acquire before a woken waiter), so a strict "ABAB" interleaving assertion is inherently flaky — I measured serialized orders even with handshakes. Per-trial granularity is pinned deterministically by test (1); test (3) asserts the required progress/index/incumbent invariants.

Old-code verification: tests (1) and (2) fail with `loop.py` stashed; test (3) passes on both (it's a correctness guard).

### Test output
```
259 passed in 20.49s
```
256 original + 3 new. Five consecutive full-suite runs green; `ruff check` and `mypy` clean. No commits made; `uv.lock` (a `uv run` artifact) removed.
