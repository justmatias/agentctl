# Contributing

## Setup

```bash
uv sync --all-groups
uv run pre-commit install
```

## Workflow

1. Create a branch and make your changes.
2. Run checks locally before opening a PR:

    ```bash
    uv run poe format   # lint, format, and static analysis via pre-commit
    uv run poe test     # unit tests with coverage
    ```

3. Commit using [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, ...) — the commit message drives the PR title check and the automated changelog/version bump.
4. Open a pull request against `main`. CI must pass before merging.

## Releases

Versioning and publishing to PyPI are automated by `python-semantic-release` on merge to `main`, based on Conventional Commit messages. You should not bump the version manually.
