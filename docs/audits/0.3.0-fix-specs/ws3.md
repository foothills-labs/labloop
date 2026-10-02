You are a senior engineer hardening "labloop" (a keep-or-revert experiment loop) to PRODUCTION quality. Work ONLY in your assigned worktree directory. Do not touch files outside it. Do not edit files owned by another workstream. Read the code before changing it. Keep the public API and existing behavior; the repo has 256 passing tests — every one must still pass, plus new regression tests you add. Run the FULL suite with:
    uv run --with pytest pytest -q
Commit nothing (the orchestrator merges). Deliver: the change, new tests, and a short report (what changed, files, why, test output).

WORKTREE: /home/ryo/repositories/ll-ws3   (fix belongs in src/labloop/loop.py, maybe lock.py; tests in tests/test_directions.py)

BUG (high): the ledger lock is held for the ENTIRE multi-trial run, so two directions never interleave.
- loop.py: `with self.lock: return self._run(trials)` wraps all trials. Two processes started with --wait therefore serialize whole runs, not trials; the faster one re-acquires immediately and the other STARVES. Observed in practice: one direction ran 8 trials while the other ran 0 over 1.5 hours. So the documented "run directions round-robin" is impossible.
EXPECTED: two loops sharing one ledger interleave trials — each trial acquires and releases the lock — and neither starves. Trial indices must not collide, and each direction's incumbent must stay correct (a peer's kept trial must be visible; re-read the direction's incumbent from the ledger at the start of each trial rather than trusting a value read once before the loop). Single-loop semantics (baseline, --confirm, budgets) must not change.
FIX DIRECTION: move lock acquisition from run() to per-trial in _run() (the lock is re-entrant already), and re-read the incumbent per trial. Keep LedgerLock's contract.
TESTS (tests/test_directions.py): two directions, one shared ledger, a deliberately slow run command; drive them concurrently (threads or subprocesses) and assert both make progress (neither starves), trial indices are unique, and the final incumbents are consistent with the ledger. Follow the style of the existing direction tests.
Verify: `uv run --with pytest pytest -q` all green (watch for timing flakiness — keep the test deterministic and fast).
