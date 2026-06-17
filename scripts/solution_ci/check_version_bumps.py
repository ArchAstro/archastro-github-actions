#!/usr/bin/env python3
"""Fail when changed solution directories did not bump sample.yaml version."""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
from typing import Optional

import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from solution_ci.discover_solutions import parse_csv, selected_slug_set

SAMPLE_FILENAME = "sample.yaml"


def verify_ref(ref: str, repo_root: pathlib.Path | str) -> None:
    if ref.startswith("-"):
        raise ValueError(f"Refusing to use ref {ref!r}: looks like a flag, not a revision.")
    try:
        subprocess.check_output(
            ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            f"Could not resolve {ref!r} to a commit. Ensure checkout fetched the base ref."
        ) from exc


def changed_solution_paths(
    base_ref: str,
    repo_root: pathlib.Path | str,
    solution_roots: list[str],
) -> list[str]:
    out = subprocess.check_output(
        ["git", "diff", "--name-only", base_ref, "HEAD", "--", *solution_roots],
        cwd=repo_root,
    ).decode()
    prefixes = tuple(f"{root.rstrip('/')}/" for root in solution_roots)
    return [line for line in out.splitlines() if line.startswith(prefixes)]


def root_slug_pairs_for_paths(
    paths: list[str],
    solution_roots: list[str],
    solution: str,
) -> list[tuple[str, str]]:
    selected = selected_slug_set(solution)
    roots = {root.rstrip("/") for root in solution_roots}
    pairs: set[tuple[str, str]] = set()
    for path in paths:
        parts = path.split("/")
        if len(parts) < 2 or parts[0] not in roots or not parts[1]:
            continue
        if selected is not None and parts[1] not in selected:
            continue
        pairs.add((parts[0], parts[1]))
    return sorted(pairs)


def version_at(
    ref: str,
    path: str,
    repo_root: pathlib.Path | str,
) -> Optional[str]:
    try:
        text = subprocess.check_output(
            ["git", "show", f"{ref}:{path}"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
        ).decode()
    except subprocess.CalledProcessError:
        return None
    try:
        payload = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(payload, dict):
        return None
    version = payload.get("version")
    return version if isinstance(version, str) else None


def find_unbumped_solutions(
    base_ref: str,
    repo_root: pathlib.Path | str,
    solution_roots: list[str] | str,
    solution: str,
) -> list[tuple[str, str, str]]:
    repo_root = pathlib.Path(repo_root)
    roots = parse_csv(solution_roots)
    paths = changed_solution_paths(base_ref, repo_root, roots)
    unbumped: list[tuple[str, str, str]] = []
    for root, slug in root_slug_pairs_for_paths(paths, roots, solution):
        sample_path = f"{root}/{slug}/{SAMPLE_FILENAME}"
        base_version = version_at(base_ref, sample_path, repo_root)
        head_version = version_at("HEAD", sample_path, repo_root)
        if base_version is None or head_version is None:
            continue
        if base_version == head_version:
            unbumped.append((root, slug, head_version))
    return unbumped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--solution-roots", default="solutions")
    parser.add_argument("--solution", default="all")
    args = parser.parse_args(argv)

    try:
        verify_ref(args.base_ref, args.repo_root)
        unbumped = find_unbumped_solutions(
            args.base_ref,
            args.repo_root,
            args.solution_roots,
            args.solution,
        )
    except ValueError as exc:
        print(f"check_version_bumps: {exc}", file=sys.stderr)
        return 2

    if not unbumped:
        roots = parse_csv(args.solution_roots)
        changed = root_slug_pairs_for_paths(
            changed_solution_paths(args.base_ref, args.repo_root, roots),
            roots,
            args.solution,
        )
        if changed:
            print(f"OK: all {len(changed)} touched solution(s) have version bumps.")
        else:
            print("No selected solution directories touched.")
        return 0

    print("Version-bump check FAILED:", file=sys.stderr)
    print("", file=sys.stderr)
    for root, slug, version in unbumped:
        print(
            f"  {root}/{slug}: files changed but sample.yaml version is unchanged at {version}.\n"
            f"    Bump version: in {root}/{slug}/sample.yaml so release automation\n"
            f"    cuts a new tarball with your changes. Keep solution.yaml\n"
            f"    solution_version in sync; validation will fail if they differ.",
            file=sys.stderr,
        )
        print("", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
