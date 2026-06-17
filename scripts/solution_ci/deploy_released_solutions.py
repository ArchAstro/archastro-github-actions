#!/usr/bin/env python3
"""Download current solution release tarballs and deploy them with archagent."""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from solution_ci.deploy_solution import deploy_solution
from solution_ci.discover_solutions import discover_solutions


def deploy_released_solutions(
    *,
    repo_root: pathlib.Path,
    solution_roots: str,
    solution: str,
    skip_sample_solutions: bool,
    download_dir: pathlib.Path,
    dry_run: bool,
    allow_downgrade: bool,
    archagent: str,
) -> int:
    solutions = discover_solutions(
        repo_root=repo_root,
        solution_roots=solution_roots,
        solution=solution,
        skip_sample_solutions=skip_sample_solutions,
    )
    download_dir.mkdir(parents=True, exist_ok=True)
    for item in solutions:
        tag = f"{item.slug}-{item.version}"
        tarball = f"{tag}.tar.gz"
        tarball_path = download_dir / tarball
        print(f"downloading {tarball} from release {tag}", file=sys.stderr)
        subprocess.check_call(
            [
                "gh",
                "release",
                "download",
                tag,
                "--pattern",
                tarball,
                "--dir",
                str(download_dir),
                "--clobber",
            ],
            cwd=repo_root,
        )
        if not tarball_path.is_file():
            raise ValueError(f"release download did not create {tarball_path}")
        deploy_solution(
            repo_root=repo_root,
            solution_input=str(tarball_path),
            dry_run=dry_run,
            allow_downgrade=allow_downgrade,
            target="",
            archagent=archagent,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--solution-roots", default="solutions")
    parser.add_argument("--solution", default="all")
    parser.add_argument("--skip-sample-solutions", action="store_true")
    parser.add_argument("--download-dir", default=".released-solutions")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-downgrade", action="store_true")
    parser.add_argument("--archagent", default="archagent")
    args = parser.parse_args(argv)

    try:
        return deploy_released_solutions(
            repo_root=pathlib.Path(args.repo_root).resolve(),
            solution_roots=args.solution_roots,
            solution=args.solution,
            skip_sample_solutions=args.skip_sample_solutions,
            download_dir=pathlib.Path(args.download_dir),
            dry_run=args.dry_run,
            allow_downgrade=args.allow_downgrade,
            archagent=args.archagent,
        )
    except ValueError as exc:
        print(f"deploy_released_solutions: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
