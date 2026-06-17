#!/usr/bin/env python3
"""Unit tests for reusable solution CI discovery helpers."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
MODULE_PATH = SCRIPTS_DIR / "solution_ci" / "discover_solutions.py"

_spec = importlib.util.spec_from_file_location("solution_ci_discover", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["solution_ci_discover"] = mod
_spec.loader.exec_module(mod)


def _write_solution(
    repo: Path,
    root: str,
    slug: str,
    version: str = "v0.1.0",
    *,
    category_keys: str = "[production]",
) -> Path:
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
            category_keys: {category_keys}
            templates: []
            """
        ),
        encoding="utf-8",
    )
    return solution_dir


class CsvParsingTest(unittest.TestCase):
    def test_parse_csv_trims_blanks(self) -> None:
        self.assertEqual(mod.parse_csv(" solutions, custom ,,"), ["solutions", "custom"])

    def test_selected_slug_set_treats_all_as_unfiltered(self) -> None:
        self.assertIsNone(mod.selected_slug_set("all"))
        self.assertIsNone(mod.selected_slug_set(""))

    def test_selected_slug_set_parses_explicit_slugs(self) -> None:
        self.assertEqual(mod.selected_slug_set("alpha,beta"), {"alpha", "beta"})


class DiscoverSolutionsTest(unittest.TestCase):
    def test_discovers_solutions_from_multiple_roots_in_stable_order(self) -> None:
        repo = Path(tempfile.mkdtemp())
        _write_solution(repo, "solutions", "alpha")
        _write_solution(repo, "custom", "beta", version="v0.2.0")
        (repo / "solutions" / "not-a-solution").mkdir(parents=True)

        discovered = mod.discover_solutions(
            repo_root=repo,
            solution_roots="solutions,custom",
            solution="all",
            skip_sample_solutions=False,
        )

        self.assertEqual([item.slug for item in discovered], ["alpha", "beta"])
        self.assertEqual(
            [item.path.relative_to(repo).as_posix() for item in discovered],
            ["solutions/alpha", "custom/beta"],
        )
        self.assertEqual([item.version for item in discovered], ["v0.1.0", "v0.2.0"])

    def test_filters_to_selected_slugs(self) -> None:
        repo = Path(tempfile.mkdtemp())
        _write_solution(repo, "solutions", "alpha")
        _write_solution(repo, "solutions", "beta")

        discovered = mod.discover_solutions(
            repo_root=repo,
            solution_roots="solutions",
            solution="beta",
            skip_sample_solutions=False,
        )

        self.assertEqual([item.slug for item in discovered], ["beta"])

    def test_detects_and_skips_sample_solutions(self) -> None:
        repo = Path(tempfile.mkdtemp())
        _write_solution(repo, "solutions", "sample", category_keys="[sample]")
        _write_solution(repo, "solutions", "real", category_keys="[production]")

        self.assertTrue(mod.is_sample_solution(repo / "solutions" / "sample" / "solution.yaml"))

        discovered = mod.discover_solutions(
            repo_root=repo,
            solution_roots="solutions",
            solution="all",
            skip_sample_solutions=True,
        )

        self.assertEqual([item.slug for item in discovered], ["real"])

    def test_missing_selected_solution_fails_clearly(self) -> None:
        repo = Path(tempfile.mkdtemp())
        _write_solution(repo, "solutions", "alpha")

        with self.assertRaisesRegex(ValueError, "no selected solution found: missing"):
            mod.discover_solutions(
                repo_root=repo,
                solution_roots="solutions",
                solution="missing",
                skip_sample_solutions=False,
            )

    def test_no_solutions_found_fails_clearly(self) -> None:
        repo = Path(tempfile.mkdtemp())
        (repo / "solutions").mkdir()

        with self.assertRaisesRegex(ValueError, "no solutions found"):
            mod.discover_solutions(
                repo_root=repo,
                solution_roots="solutions",
                solution="all",
                skip_sample_solutions=False,
            )


if __name__ == "__main__":
    unittest.main()
