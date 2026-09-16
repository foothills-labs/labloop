# Adversarial review — `fix/production-hardening` (7dc2b91 vs a0496d6)

Suite: `uv run --with pytest pytest -q` → **278 passed**. `mypy` (strict) → clean. `ruff check .` → **fails**.

## Ranked findings

### 1. CRITICAL — Fix 2 *reopens* the `.pyc` forgery hole, from the mirror side
`src/labloop/runner.py:53` sets a **fixed, world-predictable** prefix `/tmp/labloop-pycache`, shared by the propose and run child commands. Python now reads bytecode from `<prefix>/<abspath>/…`, which is **outside every protected pattern**, so the harness digest cannot see it. The original in-tree hole was caught; this one is not.

End-to-end through the real `Loop` (repo `/tmp/e2e/repo`, `--protect evals`):
- baseline (real `score()=100`) → trial 0 kept 100.
- propose plants a forged `check.cpython-314.pyc` at the mirror path (header mtime/size forged to match unchanged source) and touches an unprotected file.
- run → **`[+] trial 1 1.0 …` kept**, no `harness_changed`, commit made. `log` shows `best: 1`.
- Source untouched (`score() -> 100.0`), digest stable, and the forged pyc **persists** across later runs (plain run still prints `val=1.0`).

Base `a0496d6` with the equivalent in-tree planted pyc correctly reports:
`[H] trial 1 -- (proposal modified the harness: evals/__pycache__/check.cpython-314.pyc)`.

Smallest fix: don't use a shared constant. Create a fresh, unpredictable cache dir per invocation (e.g. `tempfile.mkdtemp(prefix="labloop-pycache-")`, removed in a `finally`) so the run command cannot read bytecode the proposal pre-planted. For defense-in-depth, fold the effective bytecode tree into `_tampering`'s digest. Test both the in-tree *and* mirror cases.

### 2. MEDIUM — CI lint fails (shippability blocker)
`ruff check .` → `E501 Line too long (104 > 100) src/labloop/runner.py:53` (exit 1). CI runs ruff. One-line wrap fixes it.

### 3. LOW — `log --json` misattributes the label
`src/labloop/cli.py:555-558` uses `last_manifest()` for **every** trial, contradicting its own comment "the label of the spec in force". Repro: baseline `--label gpt-5`, then run `--label claude`; `log --json` reports `label=claude` for trial 0 (recorded under gpt-5). Fix: walk raw records in order, carrying the current manifest's label, and emit each trial with the label in force at that point.

### 4. LOW — new version appends a redundant manifest to a pre-label ledger
`types.py:171` adds `label` to `spec()`; old manifests lack the key, so `last != spec` (`loop.py:449`) appends a duplicate on the first run. Verified: manifest count 1 → 2 after one `baseline`. Harmless but breaks the "one line per distinct spec" invariant once. Fix: compare with missing `label` normalized to `None`.

### 5. MEDIUM (pre-existing, **not** introduced) — staged renames can never be committed
`workspace.py:163-166`: `changed_paths()` returns both sides of a rename; `git add -A -- <old> <new>` fails because `<old>` is in neither index nor worktree. Verified identical failure on base and branch (`git mv`); plain deletes are fine. The branch adds nested-workdir coverage but no rename test. Not a regression, but the task called out renames and it's cheap to fix (drop paths matching neither worktree nor index).

### 6. LOW — `require_clean()` runs outside the lock for `wait=True`
`loop.py:181` executes before the first `with self.lock` (line 187), so a `--wait` process can raise a spurious `DirtyTreeError` if a peer is mid-trial in the same tree. Move it inside the first acquisition.

### 7. NOTE — same-tree `--wait` directions interleave per trial
The new per-trial lock is only safe when directions use separate worktrees (as `branch` advises). Old run-level locking also started the second direction from the first's final tree, so this is not a strict regression — just worth an explicit guard/doc.

## Verified correct
- **Fix 1**: identity at repo root; nested two-deep commit/revert; symlinked workdir; changes outside the workdir round-trip (`../sibling.txt` → `sibling.txt`) and commit; `require_clean` was already repo-wide on base; repo-wide revert is now consistent with it; ignored-only commit refused. Full suite green.
- **Fix 2** (except finding 1): a forged *in-tree* pyc is ignored under the prefix (Python 3.14 reads the mirror); caller-supplied `PYTHONPYCACHEPREFIX` wins; normal self-check imports no longer move the digest.
- **Fix 3**: lock acquired per trial (count test); two `--wait` directions over one ledger interleave with dense unique indices and per-direction incumbents; `--no-wait` still fails fast while another holds; `--wait` blocks then completes; re-entrancy intact; incumbent re-read moves the bar.
- **Fix 4**: label recorded for baseline/run; `""`/whitespace/newline/`>128` rejected; pre-label/absent label logs `null` without crashing; `resume` carries the label; `log --json` output is additive.

## Verdict
**Not safe to ship as a production release**: fix 2 trades the in-tree `.pyc` forgery hole for an easier, persistent, digest-invisible one in the shared mirror, and CI lint fails — both must be fixed first; the label issues are non-blocking.
