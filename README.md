# agentctl

Local-first control center for AI coding agents: unify MCP servers, skills, plugins and memory files, resolve precedence, snapshot to git.

> **Status: early development.** This README describes the tool as specified —
> see [docs/SPECS.md](docs/SPECS.md) for the full design and
> [docs/ROADMAP.md](docs/ROADMAP.md) for what lands in which phase. Most of what
> follows is not implemented yet.

## Why

Claude Code, Codex CLI, OpenCode, Cursor and friends each keep their own MCP
server definitions, skills, slash commands, hooks, sub-agents and memory files —
in their own formats (JSON, TOML, YAML, Markdown), at their own scopes
(managed / local / project / user), with their own precedence rules.

There is no single view across all of it. `agentctl` is that view: it discovers
every config surface on your machine, tells you which layer actually wins, lets
you edit safely, and backs the whole setup up to a git repo you own.

Local-first: no account, no server, no telemetry, no background daemon. Your
harness files stay the runtime source of truth — `agentctl` orchestrates them,
it doesn't replace them.

## What it does

- **Inventory** — one scan across every harness, tagged by source and scope,
  with a needs-review queue for anything drifted, conflicting, or not yet
  adopted.
- **Precedence, visualized** — for any setting, the ordered stack of every file
  that could define it, with the winner highlighted and the overridden layers
  still visible. The answer to "why isn't my edit taking effect."
- **Safe editing** — create, edit, enable/disable and delete MCP servers,
  skills and memory files from one place. Atomic writes, timestamped backups,
  and only the keys `agentctl` owns are ever touched.
- **Cross-harness binding** — one canonical record projected into as many
  harnesses as you want. Edit once, propagate everywhere — or keep a binding
  intentionally divergent when that's the point.
- **Drift and conflict detection** — know when a file changed outside the tool,
  and diff the same extension across harnesses side by side.
- **Skill authoring** — write `SKILL.md` once, with frontmatter validation, and
  bind it into every harness that reads skills.
- **Git-backed bundles** — export your whole setup as plain, human-readable
  files, snapshot it, diff snapshots, and restore it on a new machine as a
  reviewable plan. **Secrets are redacted on export by default, with no opt-out.**
- **Federated marketplace** *(later phase)* — browse and install skills, MCP
  servers and plugins across registries, behind a disclosure gate that shows
  exactly what executable code you're about to put on your machine.

## Supported sources

| Source | Phase | MCP config | Memory file | Skills |
|---|---|---|---|---|
| Claude Code | 1 | `~/.claude.json`, `.claude/settings.json` | `CLAUDE.md` | `.claude/skills/` |
| Codex CLI | 1 | `~/.codex/config.toml` | `AGENTS.md` | agent dirs |
| OpenCode | 1 | `~/.config/opencode/opencode.json` | `AGENTS.md`-style | `~/.config/opencode/skills` |
| `.agents` (shared convention) | 1 | `~/.agents/`, `<project>/.agents/` | `AGENTS.md` | — |
| Cursor | 2 | `~/.cursor/mcp.json` | `.cursorrules` / `AGENTS.md` | `~/.cursor/skills` |
| Gemini CLI | 2 | `~/.gemini/settings.json` | — | — |
| Hermes Agent | 3 | `~/.hermes/config.yaml` | — | categorized |

Each source is an adapter. Adding a harness means adding an adapter, not
changing core logic.

## Usage

### Dashboard

```bash
agentctl ui      # starts the local service and opens the dashboard
```

A local web dashboard (served on localhost, opened in your browser) with a
global/project switcher, overview, extension matrix, precedence stack view,
per-type editors with a raw JSON/TOML/Markdown escape hatch, conflict diffs,
a skill authoring view, and the bundle/restore screens.

### CLI

```bash
agentctl status              # what's installed, where, and what needs review
agentctl why <key>           # which layer wins for a setting, and why
agentctl snapshot            # export the bundle, redact secrets, commit
agentctl restore             # plan and apply a bundle on this machine
```

Every command takes `--json` for scripting.

### Projects

Project-scope config is only read from directories you explicitly register —
`agentctl` never crawls your filesystem looking for projects.

```bash
agentctl project add ~/repositories/agentctl
agentctl project list
```

## Bundle format

`agentctl snapshot` produces a plain-file, git-friendly directory you own:

```
agent-bundle/
  manifest.json          # schema version, tool version, host OS, sources present
  global/                # normalized global-scope config, per source
  projects/<slug>/       # project-scope config, per registered project
  secrets.template.env   # placeholder key names only — never real values
  .gitignore             # pre-seeded to exclude anything secret-bearing
```

Absolute paths under your home directory are rewritten as `${HOME}`-relative so
the bundle is portable. A secret-pattern scan runs as a final gate before any
commit and fails loudly if anything key-shaped slipped through.

Restore is a *plan*, not a copy: `agentctl` detects which harnesses exist on the
new host, shows you every write it would make as a diff, and applies only what
you confirm — with a backup of every overwritten file and a session rollback.

## Security posture

- Secret values are masked in every view and never persisted raw when the
  harness format supports an env-var reference instead.
- Bundle export redacts by default; there is no "export with secrets" option.
- Bundles read from elsewhere are treated as untrusted input (schema validation,
  path-traversal checks on every write target).
- Third-party marketplace items are executable code, not config. Nothing
  containing hooks or scripts installs in one click, provenance is pinned to a
  resolved commit, and updates are never applied automatically.

## Architecture

- **Adapters** — one per source; locate, parse, serialize, report precedence,
  declare capabilities.
- **Core service** — canonical store, drift/conflict detection, orchestration.
  Framework-agnostic and testable without the UI.
- **Backend** — Python + FastAPI over the core service, localhost only.
- **Storage** — SQLite for canonical records, bindings and sync state. Harness
  files remain authoritative at runtime.
- **Frontend** — local web dashboard served by the backend.
- **No background daemon** — scans run when you ask for them.

Requires Python 3.13+. macOS and Linux are the primary targets; Windows is a
stretch goal.

## Development

This project uses `poethepoet` for task management.

- Run the application:
  ```bash
  poe dev
  ```
- Run tests:
  ```bash
  poe test
  ```
- Format code:
  ```bash
  poe format
  ```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/ROADMAP.md](docs/ROADMAP.md).

## Authors

* Matias Gimenez <matiasgimenez.dev@gmail.com>
