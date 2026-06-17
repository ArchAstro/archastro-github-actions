# ArchAstro GitHub Actions

Reusable GitHub Actions for ArchAstro repositories.

The root action exposes solution CI/CD through a concise action-style
reference:

```yaml
- uses: ArchAstro/archastro-github-actions@v1
  with:
    command: verify
    solution-roots: solutions
```

## Commands

### Verify solutions

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
      - uses: ArchAstro/archastro-github-actions@v1
        with:
          command: verify
          solution-roots: solutions
```

### Check version bumps

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
      - uses: ArchAstro/archastro-github-actions@v1
        with:
          command: version-bumps
          solution-roots: solutions
```

### Release solutions

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
      - uses: ArchAstro/archastro-github-actions@v1
        with:
          command: release
          solution-roots: solutions
          github-token: ${{ github.token }}
```

### Deploy released solutions

```yaml
name: deploy released

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
      - uses: ArchAstro/archastro-github-actions@v1
        with:
          command: deploy-released
          solution-roots: solutions
          solution: ${{ inputs.solution }}
          dry-run: ${{ inputs.dry_run }}
          archastro-system-user-token: ${{ secrets.ARCHASTRO_SYSTEM_USER_TOKEN }}
          github-token: ${{ github.token }}
```

## Inputs

| Input | Default | Purpose |
| --- | --- | --- |
| `command` | `verify` | `verify`, `validate-scripts`, `version-bumps`, `release`, or `deploy-released`. |
| `solution-roots` | `solutions` | Comma-separated directories containing solution subdirectories. |
| `solution` | `all` | `all`, one slug, or comma-separated slugs. |
| `skip-sample-solutions` | `false` | Skip `solution.yaml` files whose `category_keys` include `sample`. |
| `base-ref` | empty | Base ref for version-bump checks. Empty uses `origin/${github.base_ref:-main}`. |
| `deploy-released` | `false` | With `command: release`, deploy newly released tarballs. |
| `dry-run` | `true` | Preview deployment changes where the CLI supports dry-run. |
| `allow-downgrade` | `false` | Pass downgrade allowance to solution upgrades. |
| `download-dir` | `.released-solutions` | Download location for released tarballs. |
| `archastro-system-user-token` | empty | Required for `validate-scripts`, `deploy-released`, and `release` with `deploy-released: true`. |
| `github-token` | empty | Token used by `gh release` commands. Usually `${{ github.token }}`. |

The action intentionally accepts only `ARCHASTRO_SYSTEM_USER_TOKEN` for
ArchAstro credentials. Platform URL, app ownership, and import/upgrade
semantics are owned by the CLI.
