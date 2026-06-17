#!/usr/bin/env python3
"""Unit tests for reusable solution CI version-bump checks."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
MODULE_PATH = SCRIPTS_DIR / "solution_ci" / "check_version_bumps.py"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("solution_ci_check_version_bumps", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["solution_ci_check_version_bumps"] = mod
_spec.loader.exec_module(mod)


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        stderr=subprocess.STDOUT,
    ).decode()


def _init_repo() -> Path:
    repo = Path(tempfile.mkdtemp())
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    return repo


def _write_solution(
    repo: Path,
    root: str,
    slug: str,
    version: str,
    extra_files: dict[str, str] | None = None,
) -> None:
    solution_dir = repo / root / slug
    solution_dir.mkdir(parents=True, exist_ok=True)
    (solution_dir / "sample.yaml").write_text(
        textwrap.dedent(
            f"""\
            schema_version: 2
            version: {version}
            name: "{slug}"
            tagline: "Test solution"
            steps:
              - type: deploy_solution
                solution_file: solution.yaml
            """
        ),
        encoding="utf-8",
    )
    (solution_dir / "solution.yaml").write_text(
        textwrap.dedent(
            f"""\
            kind: Solution
            lookup_key: {slug}-solution
            solution_id: 00000000-0000-0000-0000-000000000001
            solution_version: {version}
            name: "{slug}"
            category_keys: [production]
            templates: []
            """
        ),
        encoding="utf-8",
    )
    for name, content in (extra_files or {}).items():
        target = solution_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


class VersionBumpCheckTest(unittest.TestCase):
    def test_changed_solution_without_bump_is_flagged_under_custom_root(self) -> None:
        repo = _init_repo()
        _write_solution(repo, "bundles", "alpha", "v0.1.0", {"agent.yaml": "a\n"})
        _commit(repo, "initial")
        (repo / "bundles" / "alpha" / "agent.yaml").write_text("edited\n", encoding="utf-8")
        _commit(repo, "edit without bump")

        self.assertEqual(
            mod.find_unbumped_solutions("HEAD~1", repo, ["bundles"], "all"),
            [("bundles", "alpha", "v0.1.0")],
        )

    def test_changed_solution_with_bump_is_clean(self) -> None:
        repo = _init_repo()
        _write_solution(repo, "bundles", "alpha", "v0.1.0", {"agent.yaml": "a\n"})
        _commit(repo, "initial")
        _write_solution(repo, "bundles", "alpha", "v0.1.1", {"agent.yaml": "edited\n"})
        _commit(repo, "edit with bump")

        self.assertEqual(mod.find_unbumped_solutions("HEAD~1", repo, ["bundles"], "all"), [])

    def test_solution_subset_only_checks_selected_slug(self) -> None:
        repo = _init_repo()
        _write_solution(repo, "solutions", "alpha", "v0.1.0", {"agent.yaml": "a\n"})
        _write_solution(repo, "custom", "beta", "v0.2.0", {"agent.yaml": "b\n"})
        _commit(repo, "initial")
        (repo / "solutions" / "alpha" / "agent.yaml").write_text("a edited\n", encoding="utf-8")
        (repo / "custom" / "beta" / "agent.yaml").write_text("b edited\n", encoding="utf-8")
        _commit(repo, "edit both without bump")

        self.assertEqual(
            mod.find_unbumped_solutions("HEAD~1", repo, ["solutions", "custom"], "beta"),
            [("custom", "beta", "v0.2.0")],
        )

    def test_new_solution_is_skipped(self) -> None:
        repo = _init_repo()
        (repo / ".gitkeep").write_text("", encoding="utf-8")
        _commit(repo, "initial")
        _write_solution(repo, "solutions", "alpha", "v0.1.0")
        _commit(repo, "add solution")

        self.assertEqual(mod.find_unbumped_solutions("HEAD~1", repo, ["solutions"], "all"), [])

    def test_rejects_flag_shaped_base_ref(self) -> None:
        repo = _init_repo()
        _write_solution(repo, "solutions", "alpha", "v0.1.0")
        _commit(repo, "initial")

        with self.assertRaises(ValueError):
            mod.verify_ref("--exec=evil", repo)


if __name__ == "__main__":
    unittest.main()
