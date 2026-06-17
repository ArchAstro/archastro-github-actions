# ArchAstro GitHub Actions

Reusable GitHub Actions for ArchAstro repositories.

Actions are split into small, chainable units. Use the atomic actions when
you want explicit control, or use a macro action for the common path.

Actions that run an ArchAstro CLI accept `owner`, defaulting to `org`. `org`
uses `archagent`; `system` uses `archastro`.

## Atomic Solution CI

```yaml
name: verify

on:
  pull_request:
    paths:
      - "solutions/**"

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ArchAstro/archastro-github-actions/setup-archagent@v1
      - uses: ArchAstro/archastro-github-actions/validate-solutions@v1
        with:
          solution-roots: solutions
          owner: org
      - uses: ArchAstro/archastro-github-actions/lint-solutions@v1
        with:
          solution-roots: solutions
          owner: org
      - uses: ArchAstro/archastro-github-actions/package-solutions@v1
        with:
          solution-roots: solutions
          owner: org
```

## Macro Verify

The root action is a verify macro alias. This keeps the common PR gate short:

```yaml
- uses: ArchAstro/archastro-github-actions@v1
  with:
    solution-roots: solutions
    owner: org
```

The explicit macro path is equivalent:

```yaml
- uses: ArchAstro/archastro-github-actions/verify-solutions@v1
  with:
    solution-roots: solutions
    owner: org
```

## Version Bump Check

Use `fetch-depth: 0` so the action can diff against the PR base ref.

```yaml
name: solution version bumps

on:
  pull_request:
    paths:
      - "solutions/**"

jobs:
  version-bumps:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: ArchAstro/archastro-github-actions/check-version-bumps@v1
        with:
          solution-roots: solutions
```

## Release Solutions

```yaml
name: release

on:
  push:
    branches: [main]
    paths:
      - "solutions/**"

permissions:
  contents: write

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ArchAstro/archastro-github-actions/setup-archagent@v1
      - uses: ArchAstro/archastro-github-actions/release-solutions@v1
        with:
          solution-roots: solutions
          owner: org
          github-token: ${{ github.token }}
```

## Deploy Solutions

`deploy-solutions` takes the ArchAstro system user token and deploys the
selected released solution tarballs. Run `setup-archagent` first so the latest
CLIs are available. Deployment logs in with `<cli> auth systemuser --token`.
Use `owner: org` for `archagent` org-owned deploys, or `owner: system` for
`archastro` system-owned deploys.

```yaml
name: deploy

on:
  workflow_dispatch:
    inputs:
      solution:
        type: string
        default: all
      dry_run:
        type: boolean
        default: true

permissions:
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ArchAstro/archastro-github-actions/setup-archagent@v1
      - uses: ArchAstro/archastro-github-actions/deploy-solutions@v1
        with:
          solution-roots: solutions
          solution: ${{ inputs.solution }}
          owner: org
          dry-run: ${{ inputs.dry_run }}
          archastro-system-user-token: ${{ secrets.ARCHASTRO_SYSTEM_USER_TOKEN }}
          github-token: ${{ github.token }}
```

## Release And Deploy Macro

```yaml
- uses: ArchAstro/archastro-github-actions/release-and-deploy-solutions@v1
  with:
    solution-roots: solutions
    owner: org
    archastro-system-user-token: ${{ secrets.ARCHASTRO_SYSTEM_USER_TOKEN }}
    github-token: ${{ github.token }}
```

## Action Catalog

| Action | Purpose |
| --- | --- |
| `setup-archagent` | Install the latest `archagent` and `archastro` CLIs. |
| `configure-archagent` | Configure the selected CLI with `<cli> auth systemuser --token`. |
| `discover-solutions` | Emit selected solution metadata and paths. |
| `validate-solutions` | Run `<cli> validate solution`. |
| `lint-solutions` | Run `<cli> lint solution`. |
| `package-solutions` | Run `<cli> package solution`. |
| `check-version-bumps` | Fail PRs where changed solutions did not bump `sample.yaml` version. |
| `release-solutions` | Create missing GitHub Releases for selected solution versions. |
| `deploy-solutions` | Deploy selected released solution tarballs with the selected CLI and a system user token. |
| `verify-solutions` | Macro: setup + validate + lint + package. |
| `release-and-deploy-solutions` | Macro: setup + release + deploy. |

The actions intentionally accept only `archastro-system-user-token` for
ArchAstro credentials. Any action that accepts that token authenticates with
`<cli> auth systemuser --token`; platform URL, app ownership, and
import/upgrade semantics are owned by the CLI.
