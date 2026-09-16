You are a senior engineer hardening "labloop" (a keep-or-revert experiment loop) to PRODUCTION quality. Work ONLY in your assigned worktree directory. Do not touch files outside it. Do not edit files owned by another workstream. Read the code before changing it. Keep the public API and existing behavior; the repo has 256 passing tests — every one must still pass, plus new regression tests you add. Run the FULL suite with:
    uv run --with pytest pytest -q
Commit nothing (the orchestrator merges). Deliver: the change, new tests, and a short report (what changed, files, why, test output).

WORKTREE: /home/ryo/repositories/ll-ws1   (fix belongs in src/labloop/workspace.py + tests)

BUG (high): labloop fails when --workdir is a subdirectory of the git repo — it can measure but never keep.
- GitWorkspace runs every git command with cwd=self.root (the workdir). GitWorkspace.changed_paths() parses `git status --porcelain -z`, which reports paths relative to the REPOSITORY ROOT even when run from a subdirectory. commit() then runs `git add -A -- <those paths>` from the same workdir cwd, so the pathspec does not resolve and the commit fails: "improved but could not be committed: ... fatal: pathspec 'sub/prompt.txt' did not match any files".
- Reproduce: make a repo, put a project in sub/, run labloop with --workdir sub, propose a change that improves the metric → the keep fails.
EXPECTED: --workdir may be any directory inside a git repo. changed_paths(), commit(), revert(), is_dirty(), require_clean() must all behave consistently, using ONE path base.
FIX DIRECTION (recommended, minimal): resolve the repository toplevel once (git rev-parse --show-toplevel from the workdir) and run all git invocations with cwd=toplevel, so status paths and add paths share a base. require_clean() still refuses a dirty tree, so a repo-wide revert cannot destroy unrelated work. Do not change the Workspace Protocol.
TESTS (add, e.g. tests/test_workspace.py or extend tests/test_harness.py): a repo with the project in a subdirectory — GitWorkspace(subdir) sees the edit in changed_paths(), commit() succeeds and records it, revert() restores; and the workdir==toplevel case still works.
Verify: `uv run --with pytest pytest -q` all green.
