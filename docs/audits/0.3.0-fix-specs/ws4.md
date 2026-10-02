You are a senior engineer hardening "labloop" (a keep-or-revert experiment loop) to PRODUCTION quality. Work ONLY in your assigned worktree directory. Do not touch files outside it. Do not edit files owned by another workstream. Read the code before changing it. Keep the public API and existing behavior; the repo has 256 passing tests — every one must still pass, plus new regression tests you add. Run the FULL suite with:
    uv run --with pytest pytest -q
Commit nothing (the orchestrator merges). Deliver: the change, new tests, and a short report (what changed, files, why, test output).

WORKTREE: /home/ryo/repositories/ll-ws4   (fix belongs in src/labloop/types.py and src/labloop/cli.py; ledger if needed; tests in tests/test_ledger.py or tests/test_cli.py). IMPORTANT: do NOT edit src/labloop/loop.py (another workstream owns it) — if the label can flow via the Experiment dataclass and cli, do it that way.

BUG (medium): the ledger manifest cannot record which model/proposer produced a trial.
- The manifest records the --propose command string but deliberately excludes environment variables (credentials live there). Teams therefore abuse the command string to carry identity, e.g. `PROPOSER_MODEL=x bash propose.sh`. The ledger should be able to say which setup proposed each trial.
EXPECTED: a new `--label <text>` option on `run` and `baseline`, stored in the manifest (Experiment.spec()) as e.g. `"label": "..."` and shown by `labloop log --json`. Fully backwards compatible: ledgers/manifests written before the field exists must still load and log (default null).
FIX DIRECTION: add an optional label to the Experiment dataclass (types.py), a --label flag to the CLI (cli.py) wired into the Experiment, include it in spec(), and surface it in log output. Validate/sanitize the label (a short string; no newlines) and reject absurd input.
TESTS: run a baseline with --label and assert the manifest/spec records it; assert an old-style manifest without label still loads; assert the CLI rejects an invalid label.
Verify: `uv run --with pytest pytest -q` all green.
