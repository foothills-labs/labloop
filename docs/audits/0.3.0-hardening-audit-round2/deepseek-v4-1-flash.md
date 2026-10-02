# Adversarial review — `fix/production-hardening` @ `e869a14`

Read-only; all scratch under `/tmp/forge`, `/tmp/shadow`, `/tmp/ren*`. Repo left clean (`git status` empty, HEAD unchanged).

Commands requested:
- `uv run --with pytest pytest -q` → **286 passed**
- `uv run --with ruff ruff check .` → **All checks passed**

---

## Ranked findings

### 1. HIGH — The bytecode-mirror forgery is not closed, only made racy; scored end-to-end with no `harness_changed`

`runner.py:56-58` gives each invocation its own `mkdtemp` prefix and `runner.py:84` removes it. That defeats a *static* plant, but the mirror path is fully deterministic given the source path and the prefix is **discoverable by any concurrent same-user process**. A proposer can spawn a watcher that polls `/tmp/labloop-pycache-*` and writes an `UNCHECKED_HASH` `.pyc` into the run's mirror before the run imports the protected module. The mirror is outside the worktree, so `_tampering` (`loop.py:534`) — which only re-digests `experiment.protect` and the ledger — sees nothing.

I reproduced this through the real `Loop` (CLI `baseline` + `run`), `protect=("evalmod.py",)`:

- Proposal: launch detached watcher + make `run.py` sleep 2 s before `import evalmod` (run.py is **not** protected, so the proposer may edit it), which makes the race deterministic.
- Result (ledger, `/tmp/forge/drive4.out`):
  - trial 0: `kept`, metric `1.0`, harness `1d0eed8a7f0b…`
  - trial 1: **`kept`, metric `0.0`, harness `1d0eed8a7f0b…` (identical), commit `3430cb1`, no note, outcome is NOT `harness_changed`**
  - `git show HEAD`: the committed change is `run.py` (the sleep) + `proposal-touched.txt` + history; `evalmod.py` is untouched. The `0.0` came entirely from the forged out-of-tree `.pyc`.
- Watcher log confirms it planted e.g. `/tmp/labloop-pycache-d00gv4u9/tmp/forge/proj/evalmod.cpython-314.pyc`.

I also ran the *unassisted* version (watcher only, no run.py edit, 3-trial run): it won the race by trial 8 and kept `0.0` with the baseline harness digest. The naive static plant into an in-tree `__pycache__` and into the old fixed `/tmp/labloop-pycache` path is inert (trial reverted, metric `1.0`), so the fix does raise the bar — but the commit's "close it" claim and the `integrity.py` docstring overstate the guarantee.

Root cause: the only defense is unguessability of a path that is observable on the same machine, and the resulting artifact is outside the protected set that the digest inspects.

### 2. MEDIUM — Same class, deterministic and race-free: import shadowing of a protected module

With `protect=("evalmod.py",)`, a proposer that creates `evalmod/__init__.py` shadows the module in the import system. Source `evalmod.py` is byte-identical; the digest is unchanged; the run imports the package and returns the forged metric. Reproduced (`/tmp/shadow`): trial 1 `kept`, metric `0.0`, harness `1d0eed8a7f0b…`, commit `b248db9`, no `harness_changed`.

This is arguably "the user's `protect` pattern is incomplete" rather than a harness bug, but it is the same failure mode the `.pyc` fix targeted: the protected file's *behaviour* is replaced by code loaded from outside the protected set, and there is nothing the digest can see.

### 3. LOW — The security property has no end-to-end test, which is why #1 shipped

The only bytecode test (`tests/test_integrity.py::test_planted_pyc_is_still_detected`) plants an **in-tree** `.pyc` and asserts `harness_digest` moves. Nothing drives `Loop.run` against a mirror plant or a concurrent writer. The new `runner` tests only assert the prefix is fresh/removed/respects the caller. So the residual hole is untested by construction.

---

## Verified CORRECT

1. **Runner mechanics** (`runner.py:56-84`): fresh `mkdtemp` per invocation; `Popen` inside `try`, `rmtree` in `finally`; `if not merged_env.get("PYTHONPYCACHEPREFIX")` treats `""` as unset; a non-empty caller value wins. Tests pass; direct checks confirm removal. The naive planted `.pyc` (in-tree and at the old fixed mirror) is not read.
2. **`log --json` label attribution** (`ledger.py:88`, `cli.py:537`): `trial_labels()` walks raw records in order, carrying the current manifest label. Independently verified a 3-manifest ledger → `{0: None, 1: "alice", 2: "bob"}` including a trailing manifest with no trial; pre-label manifest → `None`; key always present.
3. **Pre-label manifest / lock** (`loop.py:186-190`, `loop.py:426`): `_record_manifest` injects `label: None` into an old last-manifest before comparing, so no duplicate; `require_clean()` and `_record_manifest()` are both inside `with self.lock:` in `_run`, and `baseline()` wraps `_baseline()` in the lock. Verified by inspection and the new test.
4. **Label stripping** (`types.py:197`): stored value is `.strip()`ed; whitespace-only refused; >128 / newline refused. Verified directly.
5. **Staged rename commits** (`workspace.py:174`): `_exists_or_tracked` drops the vanished rename side so `git add` doesn't fail. Verified `git mv` in a subdir workdir and an unstaged delete+add — both commit as `R100` and leave the tree clean.

---

## Verdict

**Do not ship as a production release yet.** The five smaller fixes are correct and well-tested, but the headline security fix does not close the score-forgery hole: a proposer can still forge a protected module's metric through the bytecode mirror (and via import shadowing) with the harness digest unchanged and no `harness_changed`, so the ledger's "improvement" is unearned. Randomising the prefix raises the effort from a static plant to a same-machine race, not a boundary; the run must be stopped from loading bytecode/code from outside the digested set (e.g. no-discoverable-mirror + `-B` with cache contents inside the digest, or process isolation) before this can be called hardened.
