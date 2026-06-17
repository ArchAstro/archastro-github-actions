#!/usr/bin/env python3
"""Create GitHub Releases for selected solution versions."""
from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from solution_ci.deploy_solution import deploy_solution
from solution_ci.discover_solutions import discover_solutions


def release_solutions(
    *,
    repo_root: pathlib.Path,
    solution_roots: str,
    solution: str,
    skip_sample_solutions: bool,
    deploy_released: bool,
    dry_run: bool,
    allow_downgrade: bool,
    archagent: str,
    deploy_cli: str,
    deploy_owners: list[str],
) -> int:
    solutions = discover_solutions(
        repo_root=repo_root,
        solution_roots=solution_roots,
        solution=solution,
        skip_sample_solutions=skip_sample_solutions,
    )
    for item in solutions:
        tag = f"{item.slug}-{item.version}"
        tarball = f"{tag}.tar.gz"
        if subprocess.run(["gh", "release", "view", tag], cwd=repo_root).returncode == 0:
            print(f"{tag} already released, skipping")
            continue

        print(f"cutting release {tag} from {item.path}")
        subprocess.check_call(
            [archagent, "package", "solution", str(item.path), "--output-dir", str(repo_root)],
            cwd=repo_root,
        )
        subprocess.check_call(
            [
                "gh",
                "release",
                "create",
                tag,
                tarball,
                "--title",
                f"{item.slug} {item.version}",
                "--notes",
                f"Released from {item.path.relative_to(repo_root)}/sample.yaml in {os.environ.get('GITHUB_SHA', 'local')}.",
                "--latest=false",
            ],
            cwd=repo_root,
        )

        if deploy_released:
            deploy_solution(
                repo_root=repo_root,
                solution_input=str(repo_root / tarball),
                dry_run=dry_run,
                allow_downgrade=allow_downgrade,
                target="",
                cli=deploy_cli,
                owners=deploy_owners,
            )
        (repo_root / tarball).unlink(missing_ok=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--solution-roots", default="solutions")
    parser.add_argument("--solution", default="all")
    parser.add_argument("--skip-sample-solutions", action="store_true")
    parser.add_argument("--deploy-released", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-downgrade", action="store_true")
    parser.add_argument("--cli", "--archagent", dest="archagent", default="archagent")
    parser.add_argument("--deploy-cli", default="archagent")
    parser.add_argument("--deploy-owner", action="append")
    args = parser.parse_args(argv)

    try:
        return release_solutions(
            repo_root=pathlib.Path(args.repo_root).resolve(),
            solution_roots=args.solution_roots,
            solution=args.solution,
            skip_sample_solutions=args.skip_sample_solutions,
            deploy_released=args.deploy_released,
            dry_run=args.dry_run,
            allow_downgrade=args.allow_downgrade,
            archagent=args.archagent,
            deploy_cli=args.deploy_cli,
            deploy_owners=args.deploy_owner or ["org"],
        )
    except ValueError as exc:
        print(f"release_solutions: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
