All green — 259 passed (256 existing + 3 new).

**What changed**
- `src/labloop/runner.py` — `run_command()` now injects `PYTHONPYCACHEPREFIX=<tmpdir>/labloop-pycache` into the child's `merged_env` via `setdefault`, so a caller-provided (or ambient) value still wins and `os.environ` is never mutated. One line + `import tempfile`; no new dirs created eagerly (Python creates the prefix dir on demand), no per-call tempdirs to leak. Skipped: excluding `.pyc`/`__pycache__` from the digest — that would reopen the score-forgery hole.
- `src/labloop/integrity.py` — module docstring now explains why bytecode stays digested (a planted `.pyc` can override unchanged source) and how the runner's cache prefix keeps honest self-checks from moving the digest.
- `tests/test_integrity.py` — 3 new tests (see below).

**Tests**
1. `test_self_check_import_leaves_the_digest_unchanged` — `delenv`s any ambient `PYTHONPYCACHEPREFIX` (explicit override handling), imports a module under a protected dir via `run_command`, asserts digest unchanged and no `__pycache__` in the tree.
2. `test_planted_pyc_is_still_detected` — a hand-written in-tree `.pyc` moves the digest and shows up in `harness_files`.
3. `test_caller_pycacheprefix_wins` — an explicit `env={"PYTHONPYCACHEPREFIX": ...}` survives `run_command` untouched.

**Verify**: `uv run --with pytest pytest -q` → `259 passed in 22.39s`. Nothing committed; only `runner.py`, `integrity.py`, `test_integrity.py` touched.
