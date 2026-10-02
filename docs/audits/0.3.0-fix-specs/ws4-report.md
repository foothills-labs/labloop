Done — all 264 tests pass (`uv run --with pytest pytest -q`: 256 pre-existing + 8 new).

**What changed**
- `src/labloop/types.py` — `Experiment` gains `label: str | None = None`; `spec()` now includes `"label"`, and `from_spec()` loads old manifests without the key as `None` (no migration needed). `__post_init__` rejects empty/whitespace-only, multi-line (`\n`/`\r`), and >128-char labels via `UsageError` (→ CLI exit 2).
- `src/labloop/cli.py` — `--label TEXT` added to `run` and `baseline` only (not `noise`), wired into `Experiment`. `log --json` keeps its one-object-per-trial contract but each trial now carries `"label"` from the latest manifest (`null` for pre-label ledgers).
- `tests/test_cli.py` — 4 new tests: baseline `--label` recorded in manifest + visible in `log --json`; `run --label` recorded; pre-label manifest still loads/logs with `"label": null`; 5 invalid labels (`""`, whitespace, newline, CR, 129 chars) rejected with exit 2.

**Skipped:** touching `loop.py`/`ledger.py` (manifest already flows through `spec()`; per-trial label attribution across mid-ledger label changes — last-manifest label is reported; add when someone actually rotates labels mid-ledger), argparse-level validation (Experiment's `UsageError` already yields exit 2).

**Test output:** `264 passed in 20.25s`.
