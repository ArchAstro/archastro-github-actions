#!/usr/bin/env python3
"""Tests for reusable solution CI release and deploy commands."""
from __future__ import annotations

import json
import os
import subprocess
import tarfile
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
RELEASE_SCRIPT = SCRIPTS_DIR / "solution_ci" / "release_solutions.py"
DEPLOY_RELEASED_SCRIPT = SCRIPTS_DIR / "solution_ci" / "deploy_released_solutions.py"


def _write_solution(repo: Path, slug: str, version: str = "v0.1.0") -> Path:
    solution_dir = repo / "solutions" / slug
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
    return solution_dir


def _write_solution_tarball(release_dir: Path, slug: str = "alpha", version: str = "v0.1.0") -> Path:
    release_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp())
    solution_dir = _write_solution(work, slug, version)
    tarball = release_dir / f"{slug}-{version}.tar.gz"
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(solution_dir, arcname=slug)
    return tarball


def _write_fake_bin(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _fake_env(workspace: Path) -> dict[str, str]:
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    log_path = workspace / "commands.log"
    release_root = workspace / "releases"
    _write_fake_bin(
        bin_dir,
        "archagent",
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import pathlib
            import sys

            log = pathlib.Path(os.environ["COMMAND_LOG"])
            log.write_text(log.read_text() + "archagent " + " ".join(sys.argv[1:]) + "\\n")

            if sys.argv[1:4] == ["package", "solution"]:
                solution_dir = pathlib.Path(sys.argv[4])
                output_dir = pathlib.Path(sys.argv[sys.argv.index("--output-dir") + 1])
                sample = (solution_dir / "sample.yaml").read_text()
                version = next(line.split(":", 1)[1].strip() for line in sample.splitlines() if line.startswith("version:"))
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / f"{solution_dir.name}-{version}.tar.gz").write_text("fake tarball")
                sys.exit(0)

            if sys.argv[1:3] == ["describe", "solutions"]:
                identifier = sys.argv[3]
                installed = os.environ.get("INSTALLED_SOLUTIONS", "").split(",")
                if identifier in [s for s in installed if s]:
                    print(json.dumps({"id": "cfg_" + identifier, "lookup_key": identifier, "solution_version": "v0.1.0"}))
                    sys.exit(0)
                sys.exit(4)

            sys.exit(0)
            """
        ),
    )
    _write_fake_bin(
        bin_dir,
        "archastro",
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import pathlib
            import sys

            log = pathlib.Path(os.environ["COMMAND_LOG"])
            log.write_text(log.read_text() + "archastro " + " ".join(sys.argv[1:]) + "\\n")

            if sys.argv[1:3] == ["describe", "solutions"]:
                identifier = sys.argv[3]
                installed = os.environ.get("INSTALLED_SOLUTIONS", "").split(",")
                if identifier in [s for s in installed if s]:
                    print(json.dumps({"id": "cfg_" + identifier, "lookup_key": identifier, "solution_version": "v0.1.0"}))
                    sys.exit(0)
                sys.exit(4)

            sys.exit(0)
            """
        ),
    )
    _write_fake_bin(
        bin_dir,
        "gh",
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import os
            import pathlib
            import shutil
            import sys

            log = pathlib.Path(os.environ["COMMAND_LOG"])
            log.write_text(log.read_text() + "gh " + " ".join(sys.argv[1:]) + "\\n")

            if sys.argv[1:3] == ["release", "view"]:
                sys.exit(1)

            if sys.argv[1:3] == ["release", "download"]:
                tag = sys.argv[3]
                pattern = sys.argv[sys.argv.index("--pattern") + 1]
                out_dir = pathlib.Path(sys.argv[sys.argv.index("--dir") + 1])
                out_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy(pathlib.Path(os.environ["GH_RELEASE_ROOT"]) / tag / pattern, out_dir / pattern)
                sys.exit(0)

            sys.exit(0)
            """
        ),
    )
    log_path.write_text("", encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["COMMAND_LOG"] = str(log_path)
    env["GH_RELEASE_ROOT"] = str(release_root)
    env["GITHUB_SHA"] = "local"
    return env


class ReleaseSolutionsCommandTest(unittest.TestCase):
    def test_release_creates_missing_solution_release(self) -> None:
        workspace = Path(tempfile.mkdtemp())
        repo = workspace / "repo"
        repo.mkdir()
        _write_solution(repo, "alpha", "v0.1.0")
        env = _fake_env(workspace)

        subprocess.check_call(
            [
                "python3",
                str(RELEASE_SCRIPT),
                "--repo-root",
                str(repo),
                "--solution-roots",
                "solutions",
                "--solution",
                "alpha",
            ],
            env=env,
            cwd=repo,
        )

        log = (workspace / "commands.log").read_text(encoding="utf-8")
        self.assertIn("gh release view alpha-v0.1.0", log)
        self.assertIn("archagent package solution", log)
        self.assertIn("gh release create alpha-v0.1.0 alpha-v0.1.0.tar.gz", log)
        self.assertIn("--latest=false", log)
        self.assertIn("Released from solutions/alpha/sample.yaml in local.", log)
        self.assertNotIn("${", log)


class DeployReleasedSolutionsCommandTest(unittest.TestCase):
    def test_dry_run_defaults_to_org_owner_and_archagent(self) -> None:
        workspace = Path(tempfile.mkdtemp())
        repo = workspace / "repo"
        repo.mkdir()
        _write_solution(repo, "alpha", "v0.1.0")
        env = _fake_env(workspace)
        _write_solution_tarball(workspace / "releases" / "alpha-v0.1.0", "alpha", "v0.1.0")

        completed = subprocess.run(
            [
                "python3",
                str(DEPLOY_RELEASED_SCRIPT),
                "--repo-root",
                str(repo),
                "--solution-roots",
                "solutions",
                "--solution",
                "alpha",
                "--dry-run",
                "--download-dir",
                str(workspace / "downloads"),
            ],
            env=env,
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        log = (workspace / "commands.log").read_text(encoding="utf-8")
        self.assertIn("gh release download alpha-v0.1.0", log)
        self.assertIn("archagent describe solutions alpha-solution --json", log)
        self.assertNotIn("list solutions", log)
        self.assertIn("Would run: archagent import solution", completed.stdout)
        self.assertTrue((workspace / "downloads" / "alpha-v0.1.0.tar.gz").exists())

    def test_dry_run_can_deploy_system_owner_with_archastro(self) -> None:
        workspace = Path(tempfile.mkdtemp())
        repo = workspace / "repo"
        repo.mkdir()
        _write_solution(repo, "alpha", "v0.1.0")
        env = _fake_env(workspace)
        _write_solution_tarball(workspace / "releases" / "alpha-v0.1.0", "alpha", "v0.1.0")

        completed = subprocess.run(
            [
                "python3",
                str(DEPLOY_RELEASED_SCRIPT),
                "--repo-root",
                str(repo),
                "--solution-roots",
                "solutions",
                "--solution",
                "alpha",
                "--dry-run",
                "--download-dir",
                str(workspace / "downloads"),
                "--cli",
                "archastro",
                "--owner",
                "system",
            ],
            env=env,
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        log = (workspace / "commands.log").read_text(encoding="utf-8")
        self.assertIn("gh release download alpha-v0.1.0", log)
        self.assertIn("archastro describe solutions alpha-solution --json", log)
        self.assertNotIn("list solutions", log)
        self.assertIn("Would run: archastro import solution", completed.stdout)
        self.assertTrue((workspace / "downloads" / "alpha-v0.1.0.tar.gz").exists())

    def test_upgrades_when_describe_finds_an_installed_solution(self) -> None:
        workspace = Path(tempfile.mkdtemp())
        repo = workspace / "repo"
        repo.mkdir()
        _write_solution(repo, "alpha", "v0.1.0")
        env = _fake_env(workspace)
        # The targeted describe lookup reports alpha-solution as installed, so
        # the helper must upgrade it rather than import a duplicate.
        env["INSTALLED_SOLUTIONS"] = "alpha-solution"
        _write_solution_tarball(workspace / "releases" / "alpha-v0.1.0", "alpha", "v0.1.0")

        subprocess.run(
            [
                "python3",
                str(DEPLOY_RELEASED_SCRIPT),
                "--repo-root",
                str(repo),
                "--solution-roots",
                "solutions",
                "--solution",
                "alpha",
                "--download-dir",
                str(workspace / "downloads"),
                "--cli",
                "archastro",
                "--owner",
                "system",
            ],
            env=env,
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        log = (workspace / "commands.log").read_text(encoding="utf-8")
        self.assertIn("archastro describe solutions alpha-solution --json", log)
        self.assertIn("archastro upgrade solution alpha-solution", log)
        self.assertNotIn("import solution", log)


if __name__ == "__main__":
    unittest.main()
