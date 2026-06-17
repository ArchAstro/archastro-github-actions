# Atomic Solution Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Refactor the root command-multiplexer action into atomic, chainable actions plus macro actions for common orchestration.

**Architecture:** Keep the Python `scripts/solution_ci/` command layer as shared implementation. Add subdirectory composite actions that each do one job: setup, auth, validate, lint, package, version-bump check, release, deploy, and macro verify/release-and-deploy flows. Keep root `action.yml` as a verify macro alias for concise default usage.

**Tech Stack:** GitHub composite actions, Bash, Python 3.12, PyYAML, `archagent`, `gh`, and the existing `uv run` test suite.

---

### Task 1: Metadata Tests For Atomic Actions

**Files:**
- Modify: `scripts/test_action_metadata.py`

- [x] **Step 1: Write failing tests**

Assert these action metadata files exist and are composite actions:

```text
setup-archagent/action.yml
configure-archagent/action.yml
discover-solutions/action.yml
validate-solutions/action.yml
lint-solutions/action.yml
package-solutions/action.yml
check-version-bumps/action.yml
release-solutions/action.yml
deploy-solutions/action.yml
verify-solutions/action.yml
release-and-deploy-solutions/action.yml
action.yml
```

Assert root `action.yml` and `verify-solutions/action.yml` are macros, while `deploy-solutions/action.yml` requires `archastro-system-user-token`.

- [x] **Step 2: Run RED**

Run: `uv run scripts/test_action_metadata.py`

Expected: fails because sub-actions do not exist.

### Task 2: Atomic Action Files

**Files:**
- Create: the action metadata files listed in Task 1
- Modify: `action.yml`

- [x] **Step 1: Implement action metadata**

Each action uses `runs.using: composite` and calls either the shared Python scripts or `archagent` directly.

- [x] **Step 2: Run GREEN**

Run: `uv run scripts/test_action_metadata.py`

Expected: metadata tests pass.

### Task 3: README Update

**Files:**
- Modify: `README.md`

- [x] **Step 1: Document chainable usage**

Show users how to chain:

```yaml
- uses: ArchAstro/archastro-github-actions/setup-archagent@v1
- uses: ArchAstro/archastro-github-actions/validate-solutions@v1
- uses: ArchAstro/archastro-github-actions/lint-solutions@v1
- uses: ArchAstro/archastro-github-actions/package-solutions@v1
```

Also document macro usage:

```yaml
- uses: ArchAstro/archastro-github-actions/verify-solutions@v1
- uses: ArchAstro/archastro-github-actions/deploy-solutions@v1
```

- [x] **Step 2: Run full verification**

Run:

```sh
uv run scripts/test_action_metadata.py
uv run scripts/test_solution_ci_discover.py
uv run scripts/test_solution_ci_check_version_bumps.py
uv run scripts/test_solution_ci_release_deploy.py
python3 -m py_compile scripts/solution_ci/*.py scripts/test_*.py
git diff --check
```

Expected: all commands pass.
