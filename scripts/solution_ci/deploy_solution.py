#!/usr/bin/env python3
"""Import or upgrade one local/released ArchAgents Solution with archagent."""
from __future__ import annotations

import argparse
import json
import pathlib
import shlex
import subprocess
import sys
import tarfile
import tempfile
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from solution_ci.discover_solutions import read_yaml


def print_command(prefix: str, args: list[str]) -> None:
    print(prefix + " " + " ".join(shlex.quote(arg) for arg in args))


def _safe_tar_member(member: str) -> bool:
    path = pathlib.PurePosixPath(member)
    return bool(member) and not path.is_absolute() and ".." not in path.parts


def extract_solution_yaml_from_tarball(tarball: pathlib.Path) -> pathlib.Path:
    metadata_dir = pathlib.Path(tempfile.mkdtemp(prefix="archagent-solution-metadata."))
    with tarfile.open(tarball, "r:gz") as archive:
        candidates = []
        for member in archive.getmembers():
            if not _safe_tar_member(member.name):
                raise ValueError(f"unsafe path in solution tarball: {member.name}")
            normalized = member.name.removeprefix("./")
            parts = pathlib.PurePosixPath(normalized).parts
            if parts and parts[-1] == "solution.yaml" and len(parts) <= 2:
                candidates.append(member)
        if len(candidates) != 1:
            raise ValueError(f"expected one solution.yaml in {tarball}, found {len(candidates)}")
        archive.extract(candidates[0], metadata_dir)
        return metadata_dir / candidates[0].name


def solution_yaml_for_input(repo_root: pathlib.Path, solution_input: str) -> tuple[pathlib.Path, pathlib.Path | None]:
    raw = pathlib.Path(solution_input)
    if raw.is_dir():
        return raw / "solution.yaml", None
    repo_candidate = repo_root / raw
    if repo_candidate.is_dir():
        return repo_candidate / "solution.yaml", None
    slug_candidate = repo_root / "solutions" / solution_input
    if slug_candidate.is_dir():
        return slug_candidate / "solution.yaml", None
    if raw.is_file() and raw.name.endswith(".tar.gz"):
        return extract_solution_yaml_from_tarball(raw), raw
    if repo_candidate.is_file() and repo_candidate.name.endswith(".tar.gz"):
        return extract_solution_yaml_from_tarball(repo_candidate), repo_candidate
    raise ValueError(f"solution directory, slug, or .tar.gz not found: {solution_input}")


def target_from_installed(
    payload: Any,
    solution_id: str,
    target_override: str,
) -> str | None:
    rows: list[dict[str, Any]]
    if isinstance(payload, dict):
        for key in ("data", "items", "results", "solutions"):
            if isinstance(payload.get(key), list):
                rows = [item for item in payload[key] if isinstance(item, dict)]
                break
        else:
            rows = [payload]
    elif isinstance(payload, list):
        rows = [item for item in payload if isinstance(item, dict)]
    else:
        rows = []

    target_fields = ("lookup_key", "lookupKey", "id", "config_id", "configId")
    for row in rows:
        if target_override:
            matched = any(str(row.get(field, "")) == target_override for field in target_fields)
        else:
            matched = str(row.get("solution_id", "")) == solution_id
        if not matched:
            continue
        return next((str(row[field]) for field in target_fields if row.get(field)), None)
    return None


def deploy_solution(
    *,
    repo_root: pathlib.Path,
    solution_input: str,
    dry_run: bool,
    allow_downgrade: bool,
    target: str,
    archagent: str,
) -> int:
    solution_yaml, tarball = solution_yaml_for_input(repo_root, solution_input)
    if not solution_yaml.is_file():
        raise ValueError(f"missing solution.yaml in {solution_input}")

    metadata = read_yaml(solution_yaml)
    solution_id = str(metadata.get("solution_id") or "")
    lookup_key = str(metadata.get("lookup_key") or "")
    local_version = str(metadata.get("solution_version") or "")
    target_key = target or ("" if solution_id else lookup_key)
    if not solution_id and not target_key:
        raise ValueError(f"could not read solution_id or lookup_key from {solution_yaml}")

    list_json = subprocess.check_output([archagent, "list", "solutions", "--json"], cwd=repo_root).decode()
    installed_target = target_from_installed(json.loads(list_json or "[]"), solution_id, target_key)

    if installed_target:
        if tarball is None:
            raise ValueError("upgrading from a directory is not supported by this reusable helper; pass a release tarball")
        args = [archagent, "upgrade", "solution"]
        if dry_run:
            args.append("--dry-run")
        if allow_downgrade:
            args.append("--allow-downgrade")
        args.extend([installed_target, str(tarball)])
        subprocess.check_call(args, cwd=repo_root)
        return 0

    import_args = [archagent, "import", "solution", str(tarball or solution_input)]
    if dry_run:
        print(
            f"no installed solution found for solution_id {solution_id or 'unknown'}; "
            f"local solution_version {local_version or 'unknown'}; import has no dry-run mode"
        )
        print_command("Would run:", import_args)
        return 0
    subprocess.check_call(import_args, cwd=repo_root)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-downgrade", action="store_true")
    parser.add_argument("--target", default="")
    parser.add_argument("--archagent", default="archagent")
    parser.add_argument("solution_input")
    args = parser.parse_args(argv)

    try:
        return deploy_solution(
            repo_root=pathlib.Path(args.repo_root),
            solution_input=args.solution_input,
            dry_run=args.dry_run,
            allow_downgrade=args.allow_downgrade,
            target=args.target,
            archagent=args.archagent,
        )
    except ValueError as exc:
        print(f"deploy_solution: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
