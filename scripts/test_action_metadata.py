#!/usr/bin/env python3
"""Static checks for the public composite action API."""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTION_YML = REPO_ROOT / "action.yml"


class ActionMetadataTest(unittest.TestCase):
    def test_root_action_exposes_succinct_solution_ci_api(self) -> None:
        metadata = yaml.safe_load(ACTION_YML.read_text(encoding="utf-8"))

        self.assertEqual(metadata["name"], "ArchAstro GitHub Actions")
        self.assertEqual(metadata["runs"]["using"], "composite")
        self.assertIn("command", metadata["inputs"])
        self.assertIn("solution-roots", metadata["inputs"])
        self.assertIn("solution", metadata["inputs"])
        self.assertIn("archastro-system-user-token", metadata["inputs"])
        self.assertIn("github-token", metadata["inputs"])

    def test_action_invokes_solution_ci_scripts_from_action_path(self) -> None:
        text = ACTION_YML.read_text(encoding="utf-8")

        self.assertIn("$GITHUB_ACTION_PATH/scripts/solution_ci/discover_solutions.py", text)
        self.assertIn("$GITHUB_ACTION_PATH/scripts/solution_ci/check_version_bumps.py", text)
        self.assertIn("$GITHUB_ACTION_PATH/scripts/solution_ci/release_solutions.py", text)
        self.assertIn("$GITHUB_ACTION_PATH/scripts/solution_ci/deploy_released_solutions.py", text)
        self.assertIn("ARCHAGENT_RELEASE_BASE_URL: https://github.com/ArchAstro/archagents/releases/latest/download", text)

    def test_action_does_not_reintroduce_org_owned_credentials(self) -> None:
        text = ACTION_YML.read_text(encoding="utf-8")

        self.assertIn("ARCHASTRO_SYSTEM_USER_TOKEN", text)
        self.assertNotIn("ARCHASTRO_CI_APP_ID", text)
        self.assertNotIn("ARCHASTRO_PROD_SOLUTIONS_DEPLOY_ORG_ID", text)
        self.assertNotIn("ARCHASTRO_PROD_SOLUTIONS_DEPLOY_APP_ID", text)


if __name__ == "__main__":
    unittest.main()
