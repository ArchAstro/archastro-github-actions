#!/usr/bin/env python3
"""Static checks for the public composite action APIs."""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTION_NAMES = (
    ".",
    "setup-archagent",
    "configure-archagent",
    "discover-solutions",
    "validate-solutions",
    "lint-solutions",
    "package-solutions",
    "check-version-bumps",
    "release-solutions",
    "deploy-solutions",
    "verify-solutions",
    "release-and-deploy-solutions",
)
OWNER_SCOPED_ACTIONS = (
    ".",
    "configure-archagent",
    "validate-solutions",
    "lint-solutions",
    "package-solutions",
    "release-solutions",
    "deploy-solutions",
    "verify-solutions",
    "release-and-deploy-solutions",
)


def _action_path(name: str) -> Path:
    return REPO_ROOT / "action.yml" if name == "." else REPO_ROOT / name / "action.yml"


def _metadata(name: str) -> dict:
    return yaml.safe_load(_action_path(name).read_text(encoding="utf-8"))


class ActionMetadataTest(unittest.TestCase):
    def test_all_public_actions_are_composite_actions(self) -> None:
        for name in ACTION_NAMES:
            with self.subTest(name=name):
                metadata = _metadata(name)
                self.assertEqual(metadata["runs"]["using"], "composite")

    def test_atomic_actions_have_single_purpose_names(self) -> None:
        for name in ACTION_NAMES:
            with self.subTest(name=name):
                metadata = _metadata(name)
                self.assertNotIn("command", metadata.get("inputs", {}))
        self.assertIn("Verify Solutions", _metadata(".")["name"])
        self.assertIn("Verify Solutions", _metadata("verify-solutions")["name"])

    def test_owner_scoped_actions_default_to_org(self) -> None:
        for name in OWNER_SCOPED_ACTIONS:
            inputs = _metadata(name)["inputs"]
            with self.subTest(name=name):
                self.assertEqual(inputs["owner"]["default"], "org")

    def test_deploy_action_takes_the_system_user_token(self) -> None:
        metadata = _metadata("deploy-solutions")
        inputs = metadata["inputs"]

        self.assertIn("archastro-system-user-token", inputs)
        self.assertTrue(inputs["archastro-system-user-token"]["required"])
        self.assertIn("github-token", inputs)

    def test_release_and_deploy_macro_takes_the_system_user_token(self) -> None:
        metadata = _metadata("release-and-deploy-solutions")
        inputs = metadata["inputs"]

        self.assertIn("archastro-system-user-token", inputs)
        self.assertTrue(inputs["archastro-system-user-token"]["required"])
        self.assertIn("github-token", inputs)

    def test_actions_invoke_shared_scripts_from_action_path(self) -> None:
        references = {
            "discover-solutions": "../scripts/solution_ci/discover_solutions.py",
            "check-version-bumps": "../scripts/solution_ci/check_version_bumps.py",
            "release-solutions": "../scripts/solution_ci/release_solutions.py",
            "deploy-solutions": "../scripts/solution_ci/deploy_released_solutions.py",
        }
        for name, script in references.items():
            with self.subTest(name=name):
                self.assertIn(script, _action_path(name).read_text(encoding="utf-8"))

    def test_setup_action_installs_latest_archagent_and_archastro(self) -> None:
        text = _action_path("setup-archagent").read_text(encoding="utf-8")

        self.assertIn(
            "ARCHAGENT_RELEASE_BASE_URL: https://github.com/ArchAstro/archagents/releases/latest/download",
            text,
        )
        self.assertIn(
            "ARCHASTRO_RELEASE_BASE_URL: https://github.com/ArchAstro/archastro/releases/latest/download",
            text,
        )
        self.assertIn("raw.githubusercontent.com/ArchAstro/archagents/main/install.sh", text)
        self.assertIn("raw.githubusercontent.com/ArchAstro/archastro/main/install.sh", text)
        self.assertNotIn("archagent-release-base-url", text)
        self.assertNotIn("archastro-release-base-url", text)

        for name in ACTION_NAMES:
            with self.subTest(name=name):
                self.assertNotIn("github.com/ArchAstro/archastro-cli/releases/latest/download", _action_path(name).read_text(encoding="utf-8"))

    def test_no_action_reintroduces_org_owned_credentials(self) -> None:
        forbidden = (
            "ARCHASTRO_CI_APP_ID",
            "ARCHASTRO_SYSTEM_USER_APP_ID",
            "ARCHASTRO_SYSTEM_USER_APP_NAME",
            "ARCHASTRO_PROD_SOLUTIONS_DEPLOY_ORG_ID",
            "ARCHASTRO_PROD_SOLUTIONS_DEPLOY_APP_ID",
            "set-credentials",
        )
        for name in ACTION_NAMES:
            text = _action_path(name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                for value in forbidden:
                    self.assertNotIn(value, text)

    def test_system_user_token_uses_systemuser_auth_command(self) -> None:
        expectations = {
            "configure-archagent": '"$cli" auth systemuser --token "$ARCHASTRO_SYSTEM_USER_TOKEN"',
            "deploy-solutions": '"$cli" auth systemuser --token "$ARCHASTRO_SYSTEM_USER_TOKEN"',
            "release-and-deploy-solutions": '"$cli" auth systemuser --token "$ARCHASTRO_SYSTEM_USER_TOKEN"',
        }
        for name, expected in expectations.items():
            with self.subTest(name=name):
                self.assertIn(expected, _action_path(name).read_text(encoding="utf-8"))

    def test_owner_scoped_actions_use_shared_cli_selector(self) -> None:
        for name in OWNER_SCOPED_ACTIONS:
            text = _action_path(name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertIn("cli_mode.sh", text)
                self.assertIn('cli="$(archastro_cli_for_owner "$OWNER")"', text)


if __name__ == "__main__":
    unittest.main()
