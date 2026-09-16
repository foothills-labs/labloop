## Report

**What changed** — `GitWorkspace` now resolves the repository toplevel once (`git rev-parse --show-toplevel`) and runs **all** git commands there, so `status` paths and `add` paths share one base. Paths crossing the public API are translated to/from the workdir, so the loop's workdir-relative history file and `changed_paths()` (git reports from the repo root) both resolve in the same commit.

Concretely:
- `_run` / `_git` run from the cached toplevel.
- `changed_paths()` runs `status --porcelain -z` at the toplevel, then maps each name back to a workdir-relative path (`_from_toplevel`).
- `commit()` maps caller paths up to toplevel-relative before `git add`, and `_is_ignored()` checks the same translated path.
- `revert()`/`is_dirty()`/`require_clean()` now operate repo-wide (previously `git clean` from a subdir only cleaned the subtree), matching the interlock's repo-wide scope. The `Workspace` Protocol is unchanged.

**Files**
- `src/labloop/workspace.py` — the fix.
- `tests/test_workspace.py` — 8 new regression tests: subdir `changed_paths`, commit/record, committing the workdir history file, revert, repo-wide dirty check, repo-wide revert, ignored-path refusal, and an end-to-end CLI keep with `--workdir sub`.

**Why** — `git status --porcelain` is always repo-root-relative, but `commit()` ran `git add` from the workdir; in `sub/` the pathspec `sub/train.py` didn't resolve, raising `fatal: pathspec ... did not match`, so an improved trial could never be kept. Resolving one toplevel and translating at the boundary removes the second path base.

**Verification** — reverted `workspace.py` temporarily and the new tests failed with the exact reported error (`improved but could not be committed: ... pathspec 'sub/train.py' did not match any files`). With the fix:

```
uv run --with pytest pytest -q
264 passed in 20.79s
```

(256 pre-existing + 8 new; `ruff check`/`format` clean.)

Skipped: no new dependency or abstraction — `os.path.relpath` and the existing `subprocess` calls.
