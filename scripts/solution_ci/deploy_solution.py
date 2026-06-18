#!/usr/bin/env python3
"""Import or upgrade one local/released ArchAgents Solution."""
from __future__ import annotations

import argparse
import json
import pathlib
import shlex
import subprocess
import sys
import tarfile
import tempfile

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


# Exit code the CLI's `describe solution` command uses when the Solution
# isn't installed yet (server 404 / solution_not_found), distinct from the
# generic failure exit 1. Mirrors SOLUTION_NOT_FOUND_EXIT_CODE in the CLI's
# resources/solutions.ts so we can tell "not installed" (-> import) apart
# from a transient error (-> abort).
SOLUTION_NOT_FOUND_EXIT_CODE = 4


def describe_installed_target(
    cli: str,
    identifier: str,
    repo_root: pathlib.Path,
) -> str | None:
    """Return the installed Solution's lookup_key/id, or None if not installed.

    Uses the targeted `describe solutions <id-or-lookup_key>` lookup instead
    of parsing the whole `list solutions --json` catalog. The full list
    truncates once it outgrows the CLI's stdout pipe buffer (~64KB), yielding
    unparseable JSON; a single-row describe never approaches that ceiling.
    """
    proc = subprocess.run(
        [cli, "describe", "solutions", identifier, "--json"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode == SOLUTION_NOT_FOUND_EXIT_CODE:
        return None
    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip()
        raise ValueError(
            f"describe solutions {identifier} failed "
            f"(exit {proc.returncode}): {message}"
        )
    summary = json.loads(proc.stdout or "{}")
    return str(summary.get("lookup_key") or summary.get("id") or identifier)


def deploy_solution(
    *,
    repo_root: pathlib.Path,
    solution_input: str,
    dry_run: bool,
    allow_downgrade: bool,
    target: str,
    cli: str,
    owners: list[str],
) -> int:
    solution_yaml, tarball = solution_yaml_for_input(repo_root, solution_input)
    if not solution_yaml.is_file():
        raise ValueError(f"missing solution.yaml in {solution_input}")

    metadata = read_yaml(solution_yaml)
    solution_id = str(metadata.get("solution_id") or "")
    lookup_key = str(metadata.get("lookup_key") or "")
    local_version = str(metadata.get("solution_version") or "")
    # `describe solutions` resolves an installed Solution by config id (cfg_…)
    # or lookup_key. The platform derives the installed Solution's lookup_key
    # from the bundle's solution_id as `sol-<solution_id>` (the bundle's own
    # declared lookup_key is not what the installed config is keyed by), so the
    # targeted lookup keys off an explicit --target, then `sol-<solution_id>`,
    # then the declared lookup_key as a last resort. Using the wrong key makes
    # `describe` miss an installed Solution and fall through to import, which
    # the platform refuses once the bundle's version is higher than installed
    # ("refusing import of higher solution_version; use the upgrade path").
    # Owner scope is enforced server-side by the endpoint's visibility rules.
    identifier = target or (f"sol-{solution_id}" if solution_id else lookup_key)
    if not identifier:
        raise ValueError(
            f"could not read solution_id or lookup_key from {solution_yaml}; "
            f"pass --target with the installed Solution id or lookup_key"
        )

    installed_target = describe_installed_target(cli, identifier, repo_root)

    if installed_target:
        if tarball is None:
            raise ValueError("upgrading from a directory is not supported by this reusable helper; pass a release tarball")
        args = [cli, "upgrade", "solution"]
        if dry_run:
            args.append("--dry-run")
        if allow_downgrade:
            args.append("--allow-downgrade")
        args.extend([installed_target, str(tarball)])
        subprocess.check_call(args, cwd=repo_root)
        return 0

    import_args = [cli, "import", "solution", str(tarball or solution_input)]
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
    parser.add_argument("--cli", "--archagent", dest="cli", default="archagent")
    parser.add_argument("--owner", action="append")
    parser.add_argument("solution_input")
    args = parser.parse_args(argv)

    try:
        return deploy_solution(
            repo_root=pathlib.Path(args.repo_root),
            solution_input=args.solution_input,
            dry_run=args.dry_run,
            allow_downgrade=args.allow_downgrade,
            target=args.target,
            cli=args.cli,
            owners=args.owner or ["org"],
        )
    except ValueError as exc:
        print(f"deploy_solution: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
