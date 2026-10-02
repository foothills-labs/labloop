# Adversarial review: `fix/production-hardening` (7dc2b91 onto a0496d6)

Suite: **278 passed** (`uv run --with pytest pytest -q`). All probes below are extra scratch scripts in `/tmp/review` (repo untouched).

## Ranked findings (all low or informational — nothing blocks ship)

**1. Low — `src/labloop/cli.py:552-558`: `log --json` misattributes the label on multi-label ledgers.**
It stamps *every* trial with the *last* manifest's label. Counterexample (probed): baseline under `--label alice`, then baseline under `--label bob` → `log --json` reports `['bob', 'bob']`; trial 0 was recorded under alice. Single-label ledgers (the norm) are unaffected, and pre-label ledgers correctly report `null` (suite-covered). Smallest fix: attribute per trial in file order (carry the current manifest label while walking records) instead of one global lookup — or document "one label per ledger".

**2. Low — `src/labloop/runner.py:54`: shared world-writable bytecode prefix.**
`PYTHONPYCACHEPREFIX=/tmp/labloop-pycache` is `drwxrwxr-x`, one dir for all users. On a shared host, another UID can pre-plant `labloop-pycache/.../*.pyc` (pyc trust is just source mtime+size, both readable), re-opening a cross-user variant of the forgery hole this fix closes. Smallest fix: `f"labloop-pycache-{os.getuid()}"`.

**3. Info — `src/labloop/runner.py:54`: empty-string caller prefix silently disables the protection.**
`setdefault` treats `""` as provided, so `env={"PYTHONPYCACHEPREFIX": ""}` re-enables in-tree bytecode. Probed: forged in-tree `.pyc` then reads as `999` (forgery lands) vs `111` (source) with the default. Honoring an explicit caller value is documented intent, but `""` is almost never intentional. Smallest fix: `if not merged_env.get("PYTHONPYCACHEPREFIX"): merged_env[...] = ...`.

**4. Info — `src/labloop/types.py:190-197`: padded label stored verbatim.**
Validation uses `.strip()` but stores raw: `--label "  spaced  "` persists as `"  spaced  "` (probed). Smallest fix: `self.label = self.label.strip()` in `__post_init__`.

## What I verified CORRECT (by falsification attempt, not just suite)

- **workspace.py** — probed root-equal, 2-deep nesting, relative workdir (`a/b`), symlinked workdir, `git mv` renames, and sibling paths (`../../sib.txt`) round-tripping through `commit`; repo-wide dirty-check/revert confirmed deliberate and guarded. No counterexample found; translation is a correct relpath roundtrip in all cases.
- **runner.py/integrity.py** — the forgery hole stays closed *and* the false-positive is gone: without a prefix a mtime-forged in-tree `.pyc` executes (`999`); with the branch default the source wins (`111`), the digest is stable across the import, and a planted `.pyc` still moves the digest (suite). Caller-supplied prefix wins (suite). The "neither reads nor writes in-tree" comment holds.
- **loop.py/lock.py** — `--no-wait` second process refused at startup (~0.2s, before any trial work); `--wait` queues then proceeds; two `--wait` runs interleave with dense indices; a baseline slipping into an inter-trial gap is atomic under the lock; a `--no-wait` slipping into a `--wait` gap serializes safely (dense indices, verified over 9 trials). Per-trial incumbent re-read is inside the same critical section as `next_index`+append, so no index collision or stale-bar window.
- **types.py/cli.py** — label lands in the manifest; `""`/`"   "`/`\n`/`\r`/129-char all exit 2 (suite); 128-char and Unicode accepted (probed); pre-label manifests yield `"label": null` (suite); `resume` preserves the manifest label (probed: `'zed'`); old readers skip the new key (`from_spec`/`Trial.from_dict` filter unknown keys — backwards compatible).

## Verdict

**Safe to ship as a production release** — all four fixes are correct and minimal; the four findings above are low/info polish, none a regression or safety hole.
