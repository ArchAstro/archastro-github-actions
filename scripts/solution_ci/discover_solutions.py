#!/usr/bin/env python3
"""Discover and filter ArchAgents Solution bundle directories."""
from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import sys
from typing import Any, Iterable

import yaml


@dataclasses.dataclass(frozen=True)
class Solution:
    root: str
    slug: str
    path: pathlib.Path
    sample_yaml: pathlib.Path
    solution_yaml: pathlib.Path
    version: str
    is_sample: bool


def parse_csv(value: str | Iterable[str]) -> list[str]:
    if isinstance(value, str):
        raw_items = value.split(",")
    else:
        raw_items = value
    return [str(item).strip() for item in raw_items if str(item).strip()]


def selected_slug_set(value: str) -> set[str] | None:
    selected = parse_csv(value)
    if not selected or selected == ["all"]:
        return None
    return set(selected)


def read_yaml(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"could not parse YAML: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"expected YAML mapping: {path}")
    return payload


def parse_sample_version(sample_yaml: pathlib.Path) -> str:
    version = read_yaml(sample_yaml).get("version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"missing string version in {sample_yaml}")
    return version


def is_sample_solution(solution_yaml: pathlib.Path) -> bool:
    if not solution_yaml.exists():
        return False
    category_keys = read_yaml(solution_yaml).get("category_keys") or []
    if not isinstance(category_keys, list):
        return False
    return "sample" in {str(item) for item in category_keys}


def discover_solutions(
    *,
    repo_root: pathlib.Path | str,
    solution_roots: str | Iterable[str] = "solutions",
    solution: str = "all",
    skip_sample_solutions: bool = False,
) -> list[Solution]:
    repo_root = pathlib.Path(repo_root)
    roots = parse_csv(solution_roots)
    selected = selected_slug_set(solution)
    found_selected: set[str] = set()
    discovered: list[Solution] = []

    for root in roots:
        root_path = repo_root / root
        if not root_path.exists():
            continue
        for candidate in sorted(root_path.iterdir(), key=lambda item: item.name):
            if not candidate.is_dir():
                continue
            sample_yaml = candidate / "sample.yaml"
            if not sample_yaml.is_file():
                continue
            slug = candidate.name
            if selected is not None and slug not in selected:
                continue

            solution_yaml = candidate / "solution.yaml"
            sample = is_sample_solution(solution_yaml)
            found_selected.add(slug)
            if skip_sample_solutions and sample:
                continue
            discovered.append(
                Solution(
                    root=root,
                    slug=slug,
                    path=candidate,
                    sample_yaml=sample_yaml,
                    solution_yaml=solution_yaml,
                    version=parse_sample_version(sample_yaml),
                    is_sample=sample,
                )
            )

    if selected is not None:
        missing = sorted(selected - found_selected)
        if missing:
            raise ValueError(f"no selected solution found: {', '.join(missing)}")

    if not discovered:
        raise ValueError("no solutions found")

    return discovered


def _solution_json(solution: Solution) -> dict[str, Any]:
    return {
        "root": solution.root,
        "slug": solution.slug,
        "path": str(solution.path),
        "sample_yaml": str(solution.sample_yaml),
        "solution_yaml": str(solution.solution_yaml),
        "version": solution.version,
        "is_sample": solution.is_sample,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--solution-roots", default="solutions")
    parser.add_argument("--solution", default="all")
    parser.add_argument("--skip-sample-solutions", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    try:
        solutions = discover_solutions(
            repo_root=args.repo_root,
            solution_roots=args.solution_roots,
            solution=args.solution,
            skip_sample_solutions=args.skip_sample_solutions,
        )
    except ValueError as exc:
        print(f"discover_solutions: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps([_solution_json(item) for item in solutions], indent=2))
    else:
        for item in solutions:
            print(item.path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
