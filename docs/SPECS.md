# SPEC.md — agentctl

**agentctl** — a local-first configuration orchestrator for AI coding
agents. Unify MCP servers, skills, plugins and memory files across every
harness you run, see which config actually wins, and version it in git.

CLI surface (see §9): `agentctl status`, `agentctl why <key>`,
`agentctl snapshot`, `agentctl restore`.

## 1. Problem Statement

Local agentic development setups (Claude Code, Codex CLI, OpenCode, Cursor, and
similar tools) each maintain their own configuration surface: MCP server
definitions, skills/plugins, slash commands, hooks, sub-agents, and
instruction/memory files (`CLAUDE.md`, `AGENTS.md`, `MEMORY.md`, `.cursorrules`, etc.).
Each tool also applies its own scope hierarchy (project / user / global /
managed) on top of its own file format (JSON, TOML, YAML, Markdown).

There is currently no tool that gives a single, editable view across **all**
of these config types and **all** of these harnesses at once. The closest
existing projects each cover a subset:

- GUI, multi-harness, but MCP + skills + slash commands only, no memory files
  or plugins (e.g. Skill Manager).
- Full breadth (rules + commands + hooks + MCP), multi-harness, but file/CLI
  based with no GUI (e.g. dot-agents).
- Full GUI breadth, but locked to a single harness (e.g. Claude Code–only
  managers).

This spec defines a tool to close that gap: **agentctl**, a local-first
configuration orchestrator with a GUI that centralizes discovery, review,
editing, and sync of every config surface across every harness a
developer actually uses.

## 2. Goals

- One place to **see** everything: which config objects exist, in which
  harness, at which scope, and whether they're in sync.
- One place to **edit**: create, update, enable/disable, and delete config
  objects without hand-editing JSON/TOML/YAML/Markdown files.
- Harness-agnostic by design — no single tool is the "hub"; each harness is
  an adapter.
- Cover the full config surface a developer actually accumulates: MCP
  servers, skills/plugins, slash commands, hooks, sub-agents, and
  memory/instruction files (CLAUDE.md, AGENTS.md, MEMORY.md, and equivalents).
- Make scope (project/user/global/managed) visible and resolvable — show
  which file a given effective setting actually comes from.
- Local-first: no required cloud account, no telemetry by default, all state
  readable as plain files or a local DB.

## 3. Non-Goals (v1)

- Not a config *format standardizer* across the industry — it translates
  between existing formats, it doesn't propose a new universal one (that's
  a much larger, separate effort — cf. `AGENTS.md`/MCP standardization
  discussions).
- Not a marketplace *host or publisher* — the tool federates existing
  per-tool registries into one browse/install surface (§7.13) but
  operates none of them, curates none of them, and publishes to none of
  them.
- Not a secrets manager — API keys/tokens are passed through, not stored or
  rotated by this tool beyond what's needed to write harness configs.
- Not a hosted multi-machine sync *service* — portability is delivered as
  a git-backed bundle the user owns and pushes wherever they like
  (§7.11). No accounts, no server, no continuous background syncing;
  snapshot and restore are explicit user actions.

## 4. Target User

A single developer running multiple AI coding agents locally (this spec's
originating case: Claude Code + Codex CLI + OpenCode, Python/FastAPI
background) who wants visibility and control without memorizing each tool's
file layout and precedence rules.

## 5. Supported Harnesses

| Harness      | Priority | MCP config              | Memory/rules file        | Skills/Plugins        | Notes |
|--------------|----------|--------------------------|---------------------------|------------------------|-------|
| Claude Code  | v1       | `~/.claude.json`, `.claude/settings.json` (`mcpServers`, JSON) | `CLAUDE.md` (project + user), `MEMORY.md` (auto-memory) | `.claude/skills/`, plugins via marketplace | 5-layer scope: managed → CLI arg → local → project → user |
| Codex CLI    | v1       | `~/.codex/config.toml` (`mcp_servers`, TOML) | `AGENTS.md` | skills under agent dirs | TOML, not JSON — needs its own parser |
| OpenCode     | v1       | `~/.config/opencode/opencode.json` (typed local/remote entries) | `AGENTS.md`-style | `~/.config/opencode/skills` | |
| Cursor       | v1       | `~/.cursor/mcp.json`, `.cursor/mcp.json` | `.cursorrules` / `.cursor/rules/` / `AGENTS.md` | `~/.cursor/skills` | Project vs user scope |
| Gemini CLI   | v2       | `~/.gemini/settings.json` | `GEMINI.md` | — | |
| Hermes Agent | v3       | YAML under `~/.hermes/config.yaml` | — | categorized skill layout | |

v1 = must-have at MVP. v2/v3 = roadmap, added via new adapters without core
changes (see §9).

### 5.1 Shared / cross-harness source: `.agents`

Beyond harness-native folders, the tool must also discover the emerging
shared convention: a `.agents/` directory (global at `~/.agents/`, and
optionally project-level at `<project>/.agents/`) plus root-level
`AGENTS.md`. This is not owned by any one harness — some tools read it
natively, some only via a symlink another tool placed there, and some
don't consult it at all. `.agents` is treated as its own **source type**,
distinct from a harness, with its own adapter that:

- discovers `.agents/` at both global and project level, independent of
  whether any harness is installed,
- reports, **per harness**, whether that harness actually consults
  `.agents`/`AGENTS.md` — one of `consulted` (natively or via symlink,
  with its rank), `not_consulted`, or `unconfirmed`. This must be
  verified against each harness's own docs, not assumed; `unconfirmed`
  is the honest answer when it cannot be, and is a first-class state
  (§7.10), not a stand-in for unfinished work,
- feeds into the precedence chain (§7.10) as one more layer, positioned
  correctly relative to each harness's native files rather than always
  assumed to be highest or lowest priority — and, when `unconfirmed`,
  shown outside the ordered stack and excluded from resolution.

## 6. Core Concepts

- **Harness** — a single AI coding tool instance (Claude Code, Codex CLI,
  etc.) with its own config file locations and formats.
- **Extension** — any managed config object: MCP server, Skill, Slash
  command, Hook, Sub-agent, or Memory file.
- **Canonical record** — the tool's own normalized representation of an
  extension, stored once, independent of harness format.
- **Harness binding** — the projection of a canonical record into a specific
  harness's file(s). One canonical record can have zero or more bindings.
- **Scope** — where a binding lives on disk relative to precedence:
  `managed` > `local` (project, untracked) > `project` (shared) > `user`
  (global). Exact levels/precedence order are harness-specific; the tool
  must model each harness's real hierarchy, not force one universal model.
- **Drift** — a binding whose on-disk content no longer matches what the
  tool last wrote (edited outside the tool, or another sync tool touched it).
- **Conflict** — the same logical extension (e.g. same MCP server name)
  present with different definitions across harnesses or scopes. Applies
  to structured config, which the tool can compare field by field and
  therefore ask the user to resolve.
- **Divergent** — the weaker, informational counterpart of Conflict, used
  for free-form prose (memory/instruction files): same-role files whose
  normalized text differs. Reported with a diff, never queued for
  resolution (§7.2).
- **Source** — a generalization of "harness" to also cover `.agents`
  (§5.1), which isn't a runnable tool but does hold config that harnesses
  may or may not read. Everywhere this spec says "harness" for discovery
  and precedence purposes, `.agents` counts as a source too.
- **Project** — a directory the user has explicitly registered with the
  tool (§7.9). Config discovery for project-level scopes only happens
  inside registered projects; the tool does not crawl the filesystem
  looking for projects on its own.

## 7. Functional Requirements

### 7.1 Discovery / Inventory
- Scan all configured harness paths on demand and on a manual "refresh".
- Build an inventory of extensions found per harness, tagged with scope.
- Classify each as: **Adopted** (tool manages it), **Needs review** (found
  but not yet adopted, or drifted), or **Unmanaged** (explicitly excluded).

### 7.2 Review & Conflict Resolution
- Surface a diff when the same extension differs across harnesses/scopes.
- Let the user pick a source of truth per conflict, or **keep both
  intentionally** (some settings should differ per project). That
  resolution is persisted so the conflict stops reappearing.
- Detect drift (on-disk change since last tool write) and let the user
  either adopt the drifted version or restore the tool's last-known state.
- **Structured config vs. free-form prose are treated differently.**
  Structured extensions (MCP servers) get full conflict records with the
  resolution workflow above. Memory/instruction files get the weaker
  `divergent` state instead (§6, §7.5): same-role files are compared as
  text after normalizing line endings and trailing whitespace, and any
  difference is reported informationally with a diff — no resolution
  prompt, no auto-merge, no semantic "is this the same instruction
  reworded" inference. Most memory files legitimately differ per harness;
  treating that as a conflict to resolve would be noise.
- Note the two terms are distinct: `divergent` is a *sync state* on a
  binding; "keep both intentionally" is a *resolution* applied to a
  `Conflict`.

### 7.3 CRUD
- Create a new extension from the canonical view; choose which
  harnesses/scopes to bind it to.
- Edit a canonical record; propagate to all bound harnesses, or edit one
  binding in isolation when intentional divergence is needed.
- Delete: remove a binding from one harness, or delete the canonical record
  and all its bindings.
- All writes are atomic (write temp file + rename) and only touch the
  specific keys owned by this tool — never clobber unrelated settings in a
  shared file like `settings.json`.

### 7.4 Enable/Disable
- Toggle an extension on/off per harness without deleting it (write/remove
  the binding, keep the canonical record).

### 7.5 Memory & instruction files (CLAUDE.md, AGENTS.md, MEMORY.md, etc.)
- Treat these as first-class extensions, covering two complementary categories:
  1. **Developer instruction / rule files**: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
     `.cursorrules`, and equivalents — developer-authored guidelines, coding
     standards, and repository architecture notes.
  2. **Persistent memory files**: `MEMORY.md` (e.g. Claude Code's auto-memory under
     `~/.claude/projects/<slug>/memory/MEMORY.md`, `.claude/memory/`, `.agents/memory/`,
     or project root `MEMORY.md`) — agent-accumulated notes, session context, and
     project state.
- Support: view rendered + raw Markdown, edit in-app, and diff.
- Show which scope a given memory/instruction file is (project vs user) and, where the
  harness supports it, which file wins for a given directory.

**Decision: independent files + diff in v1; composition is opt-in later.**
Each harness's memory file stays an independent file that the tool reads,
edits, and diffs in place. The tool does not compose content across files
in v1, and there is no shared-block write path to opt into yet.

A canonical "shared instructions" block — one authored block composed into
each harness's file alongside harness-specific sections — remains the more
powerful model and is deferred to Phase 2 as an **explicit opt-in**,
gated on two things: per-harness load semantics being verified by the
adapter (does the harness concatenate, override, or truncate?), and the
v1 write path (§7.3, §11) having proven itself.

When composition does ship, it must be structurally reversible: the
composed region is delimited by explicit `agentctl` begin/end markers,
everything outside the markers is preserved byte-for-byte, and removing
the block restores the file to a hand-maintained one. Rationale for not
shipping it in v1: the failure mode of composition is that a user can no
longer tell what a harness actually loaded, which is the exact problem
§7.6 and §7.10 exist to solve. Duplicated instructions across files are
an annoyance; unexplainable loaded context is a defect.

The cost is accepted openly: until composition ships, a user who wants the
same instruction in `CLAUDE.md` and `AGENTS.md` maintains it in both, with
the diff view (§10) making the divergence visible.

### 7.6 Scope visibility
- For any effective setting, show the resolved value **and** which file at
  which scope produced it — analogous to Claude Code's own `/status`
  output, but across harnesses.

### 7.7 Profiles
- Save/restore named snapshots of "which extensions are enabled where" —
  useful for switching between a minimal setup and a full one, or between
  client projects with different tool permissions.

### 7.8 Secrets
- Never display secret values in list views (masked by default).
- Never write secrets to the tool's own database if a harness file can
  hold a reference/env-var instead; prefer env-var indirection when the
  harness format supports it.

### 7.9 Project registration & Global vs. Project views
- **Global view**: on first run and always available, the tool scans
  every configured harness's user/global-scope locations (e.g.
  `~/.claude/settings.json`, `~/.codex/config.toml`, `~/.agents/`) with no
  project selected. This is "what applies everywhere unless overridden."
- **Add project**: an explicit user action — point the tool at a
  directory. The tool then scans that directory for any project-scope
  harness folders it recognizes (`.claude/`, `.codex/` if project-scoped,
  `.cursor/`, project `.agents/`, root `CLAUDE.md`/`AGENTS.md`/`MEMORY.md`, etc.) plus
  any nested harness config the adapters know to look for.
- Registered projects are listed and switchable from the UI; no
  filesystem crawling to auto-discover projects the user hasn't pointed
  the tool at.
- **Project view**: for a selected project, show the effective merged
  config (global layer + this project's layers) per harness, and clearly
  mark which extensions come from global scope vs. this project.
- Removing a project from the registry stops the tool from tracking it;
  it does not delete any files.

**Decision: registration scopes tracking, not precedence.** Registering a
project tells the tool *what to track and display*. It never changes what
the precedence stack reports. The stack always mirrors what the harness
actually does at that directory — including directory walk-up for files
like `CLAUDE.md`/`AGENTS.md` — regardless of whether the ancestor
directory happens to be registered.

Consequences, which the implementation must honor:
- A registered sub-project inside a registered monorepo shows the
  ancestor's layers in its precedence stack **if and only if** the
  harness genuinely reads them from that working directory. Registration
  state is not an input to that computation.
- An *unregistered* ancestor whose files the harness does read still
  appears in the stack, labeled as coming from outside any registered
  project, so the user can see config acting on them that the tool isn't
  otherwise tracking.
- A registered ancestor whose files the harness does *not* read from this
  directory does not appear in the stack, however tempting the hierarchy
  looks in the UI.
- Walk-up semantics are **adapter-reported** (§9), never inferred from
  the directory tree: how far a harness ascends, whether it stops at a
  git root or home directory, and whether it concatenates or overrides
  differ per tool. An adapter that cannot state its walk-up behavior
  reports those layers as `unconfirmed` under the same rule as §7.10.

Rationale: the tool's core promise is answering "which config actually
wins." A precedence view whose output changes because the user registered
or unregistered an unrelated directory would be reporting on agentctl's
bookkeeping rather than on the machine, which is the one thing it must
never do.

### 7.10 Precedence visualization
- For a selected project (or the global view) and a chosen harness, show
  an ordered stack of every source that could define config for that
  harness — e.g. managed policy, CLI/env override, project `.agents/`,
  project `.claude/settings.local.json`, project `.claude/settings.json`,
  user `~/.claude/settings.json` — top to bottom by precedence.
- The layer that currently wins for a given key is visually highlighted;
  layers that are overridden are visually de-emphasized but still shown
  (so the user can see *why* a setting they edited isn't taking effect).
- This applies to both structured settings (MCP servers, permissions) and
  memory files: if a project has both `.agents/AGENTS.md` and a
  `.cursor/`-specific rules file, the view must show, for Cursor
  specifically, which one Cursor actually loads and in what order/merge
  behavior — this is adapter-reported per §5.1, not guessed.
- Clicking any layer in the stack opens that file/source directly in the
  editor panel (§10) — precedence understanding and editing are one
  action apart, not two separate views the user has to cross-reference.

**Decision: unverified layers are shown as `unconfirmed`, outside the
ordered stack, and excluded from resolution.** When an adapter cannot
state whether its harness consults a source — the common case being
`.agents`/`AGENTS.md` (§5.1), whose support varies per tool and changes
over time — that layer:

- is displayed, so the user can see the file exists and that the tool
  looked at it rather than missing it;
- is rendered in a visually distinct `unconfirmed` region, separate from
  the ordered high-to-low stack, with no implied rank relative to the
  confirmed layers;
- **never participates in computing the winning layer.** The resolved
  value reported by §7.6 comes only from confirmed layers. An unconfirmed
  layer can never be named as the winner, and can never demote one.

The three states an adapter reports for a source are therefore
`consulted` (natively or via symlink, with its rank), `not_consulted`,
and `unconfirmed` — the last being a real, displayable state, not a
placeholder for a missing implementation.

Rationale: the two failure modes are unequal. Omitting the layer hides a
file that may well be loaded and makes the tool look like it did not
check. Guessing a rank produces a confidently wrong ordering in the one
view whose entire purpose is to be authoritative — and a user who acts on
a wrong precedence order is worse off than one who was told the tool does
not know. Showing the layer while refusing to rank it is the only option
that is both complete and honest.

An `unconfirmed` layer is a standing invitation to fix it: the UI links
to the adapter's verification status so confirming a harness's real
behavior upgrades the layer permanently.

### 7.11 Portability: bundle, version control, restore

The goal: a user can capture their whole agentic setup, keep its history,
and reproduce it on a new machine without hand-copying dotfiles.

**Bundle format.** A single directory (`agent-bundle/`) that is plain
files, git-friendly, and human-readable — not a proprietary archive or a
DB dump. Sketch:

```
agent-bundle/
  manifest.json          # schema version, tool version, created_at,
                         # source host OS, which harnesses were present
  global/
    claude-code/         # normalized copies of global-scope config
    codex-cli/
    opencode/
    dot-agents/
  projects/
    <project-slug>/
      project.json       # original path, detected sources
      claude-code/ ...   # project-scope config copies
  secrets.template.env   # placeholder keys only — never real values
  .gitignore             # pre-seeded to exclude anything secret-bearing
```

**Export.** One action produces the bundle from the current inventory.
It must:
- Normalize machine-specific values: rewrite absolute paths under the
  home directory as `${HOME}`-relative, and record the original for
  reference. A bundle full of `/Users/matias/...` is not portable.
- **Strip secrets by default.** Any value matching a secret-bearing key
  (`env` blocks in MCP servers, `*_API_KEY`, `*_TOKEN`, auth headers) is
  replaced with a named placeholder, and the key name — not the value —
  is written into `secrets.template.env` so the user knows what to supply
  on restore. Committing an API key to a backup repo is a realistic and
  serious failure mode, so it must be prevented structurally, not by a
  warning in the UI.
- Report exactly what was excluded and why, before writing anything.

**Version control.** The bundle directory is the git repo:
- `init` — create the repo, write `.gitignore`, make the first commit.
- `snapshot` — re-export and commit, with a message (auto-generated
  summary of what changed, user-editable).
- History view in the UI: list of commits, diff between any two
  snapshots, using the same diff component as conflict resolution (§7.2).
- Remote is optional and user-supplied; the tool never hosts anything
  and never pushes without an explicit action.
- Rationale for git over a bespoke snapshot store: the user already has
  git, it gives diff/blame/branch/remote for free, and the backup stays
  useful even if this tool is abandoned.

**Decision: the commit log is snapshot history, not an audit trail.** Each
commit means exactly one thing — "this was the state of your config when
you ran `snapshot`." A single commit may contain many unrelated changes
made outside the tool between snapshots, and the log says nothing about
when or why any individual change happened.

This must be stated, not merely implied:
- The bundle's generated `README.md` says it in plain words, so the
  distinction survives being read a year later by someone who wasn't
  present for this decision.
- The history UI (§10) labels the view as snapshots and dates them by
  snapshot time, never presenting a commit as a record of a change event.
- No feature may be built that depends on commits being per-change —
  notably, "who changed this and when" is not a question this history can
  answer, and the UI must not offer it.

Rationale: the honest alternative was per-change commits from tool-recorded
events, but that log could only ever cover changes made *through* agentctl.
Config edited by hand or by another tool — the common case, and the reason
drift detection exists at all — would be silently absent from something
presented as complete. A history that is accurate about being coarse beats
one that is misleading about being total.

**Restore / apply on a new host.** Restore is a *plan*, not a copy:
1. Read the bundle; detect which harnesses exist on *this* host.
2. Produce a plan: what would be written where, what will be skipped
   (harness not installed), what needs secrets supplied, what would
   overwrite an existing file.
3. Show the plan as a reviewable diff. Nothing is written until the user
   confirms.
4. Apply, with a backup of every file about to be overwritten (§11).
5. Report a summary: applied / skipped / needs attention.

Restore must degrade gracefully: a bundle exported from a host with five
harnesses restoring onto a host with two should apply the two and clearly
list the three it skipped, not fail.

**Selective restore.** The user can apply global-only, a single project,
or a single source — the common case "I only want my MCP servers on this
new machine" shouldn't require all-or-nothing.

**Rollback.** Every apply is undoable back to the pre-apply state for at
least the current session, using the same backup mechanism as ordinary
writes.

### 7.12 Authoring: portable skills and workflows

Everything above manages config that already exists. This section covers
*creating* reusable behaviour in one place and making it available in
every harness that can run it.

#### 7.12.1 Skill authoring

Skills are the most portable primitive available: `SKILL.md` is Markdown
plus frontmatter, the format is consumed by many agents, and it carries
supporting files (scripts, references) alongside the instructions. The
tool should therefore treat `SKILL.md` as the **canonical authoring
substrate**, not just something it adopts from disk.

Requirements:
- Create a skill in-app: name, description (the field that drives
  auto-invocation, so it gets its own guidance in the editor), body, and
  optional bundled files.
- Validate before saving: frontmatter schema, required fields, name
  uniqueness across the inventory, and a warning when the description is
  too vague to trigger reliably.
- Bind to any subset of harnesses (§7.4 semantics) — one canonical skill,
  linked into each harness's skill root.
- Edit once, propagates to every binding.

#### 7.12.2 Workflows

**The honest constraint first:** there is no cross-harness "workflow"
primitive. Each harness exposes some subset of skills, slash commands,
prompt files, sub-agents, and hooks — with different names, formats,
invocation syntax, and capabilities. A workflow feature that pretends
otherwise will produce something that silently does less on some tools
than others, which is worse than not offering it.

So a Workflow here is defined as **a canonical, harness-independent
definition that compiles down to whatever each target harness can
actually express**, with the losses made explicit.

A Workflow record contains:
- `name`, `description`
- `steps[]` — ordered instructions, each optionally naming a tool/command
  it expects to be available
- `inputs[]` — named parameters, rendered into each harness's argument
  convention (e.g. `$ARGUMENTS` where supported)
- `requires[]` — MCP servers or skills the workflow depends on
- `targets[]` — which harnesses to compile for

**Compilation targets** (adapter-reported, per §9):

| Target form | Notes |
|---|---|
| Skill (`SKILL.md`) | Highest fidelity and most portable. Supports multi-step instructions and bundled scripts. Default target. |
| Slash command | Good for explicit invocation with arguments; each harness has its own directory and invocation prefix. |
| Prompt file | For harnesses that expose prompts rather than commands. |
| Sub-agent | Only where supported; the richest form but least portable. |

**Capability matrix requirement.** Before compiling, the UI must show,
per target harness: which form it will compile to, which requested
features are unsupported there, and what the degradation is (e.g.
"no argument substitution on this harness — inputs will be inlined as
instructions"). No silent downgrades.

**Dependency awareness.** If a workflow declares `requires: [mcp:github]`
and the target harness has no such MCP server bound, the tool flags it
before compiling, and offers to bind the dependency in the same action.
This is the payoff of managing MCP servers and workflows in the same
tool rather than two separate ones.

**Round-tripping is one-way by design.** Compiled artefacts are outputs;
edits made directly to a compiled file are detected as drift (§7.2) and
the user is asked to either adopt the change back into the canonical
workflow or discard it. The tool does not attempt to parse arbitrary
harness command files back into structured workflow steps — that
inference is unreliable and would corrupt the canonical definition.

**Workflows travel in the bundle** (§7.11) as canonical definitions plus
their compilation targets, so a restored host regenerates rather than
copies stale artefacts.

### 7.13 Federated marketplace

**The constraint, stated plainly:** a single shared marketplace across
harnesses does not exist and this tool cannot create one — publishers
list where their users are, not where an aggregator wishes they would.
What is achievable is a **federated index**: one browse/search/install
surface that queries each ecosystem's existing sources and normalizes
the results. That is what this section specifies.

A second, sharper constraint: "plugin" is not a universal concept. Claude
Code plugins are bundles (skills + commands + sub-agents + hooks +
`.mcp.json`) installed from git-based marketplace repos. Most other
harnesses have no plugin concept at all — they have skills and MCP
servers individually. So the federated index deals in **installable
items** of several types, and plugin is one type among them, not the
organizing principle.

#### 7.13.1 Sources

Each *registry source* is an adapter (same pattern as §9):

| Source type | Example shape | Item types |
|---|---|---|
| Claude Code plugin marketplace | git repo with a marketplace manifest | plugin |
| MCP registries | public MCP server directories | mcp_server |
| Skill collections | git repos of `SKILL.md` packages | skill |
| Harness-native catalogs | whatever a given harness ships | varies |
| User-defined | any git URL the user adds | any |

Requirements:
- Ship with **zero** sources enabled by default beyond harness-native
  ones; the user adds registries explicitly. An aggregator that
  pre-trusts a list of third-party repos is making a security decision
  on the user's behalf.
- Any git URL can be added as a source — no gatekeeping, no curation by
  this tool.
- Sources are cached locally with a visible last-refreshed timestamp;
  browsing works offline against the cache.

#### 7.13.2 Normalized item model

Every source adapter maps its entries into one shape: `name`,
`description`, `type`, `source`, `author`, `repo_url`, `version`,
`install_targets[]` (which harnesses it can go to), and
`contains[]` (for bundles: the skills/commands/hooks/MCP servers inside).

Search and filter operate on the normalized model, so the user searches
once across all configured registries rather than per ecosystem.

#### 7.13.3 Install

Install routes through the appropriate mechanism per item type — the
harness's own installer where one exists, or direct file placement where
it doesn't — and then the item becomes an ordinary managed extension
(§7.1–7.4). After install it is subject to the same binding, drift, and
precedence machinery as anything else; the marketplace is an entry point,
not a parallel system.

For bundles, installing must **expand and disclose contents**: the user
sees every skill, command, hook, sub-agent, and MCP server the bundle
will add, with per-item opt-out where the harness allows partial install.

#### 7.13.4 Trust and safety — the hard part

Installing a third-party plugin is installing **executable code**: hooks
run shell commands on tool events, MCP servers are long-lived processes
with whatever access their config grants, and skills can carry scripts.
This is materially more dangerous than the config management in the rest
of this spec, and the UI must not present it with the same casualness as
toggling a setting.

Requirements:
- **Pre-install disclosure**, always: source repo, author, what will be
  written where, and specifically whether the item contains hooks,
  scripts, or MCP servers with credentials or broad filesystem access.
  Hooks in particular deserve their own warning — a hook is arbitrary
  code that runs automatically, without a prompt, on agent events.
- **No one-click install for items containing hooks or scripts.** A
  second, explicit confirmation showing the actual code.
- **Pin and record provenance**: store source URL and resolved
  commit/version, so an installed item can be audited later and
  reproduced from a bundle (§7.11).
- **Update ≠ auto-update.** Updates are surfaced but never applied
  automatically; a marketplace item changing under the user is a supply
  chain risk, and silent updates would make the drift detection in §7.2
  meaningless.
- Optional LLM-backed source review before install stays a later
  addition (§13, Phase 3) — useful, but it is a supplement to disclosure,
  not a substitute for it.

#### 7.13.5 Publishing

Out of scope. The tool consumes registries; it does not host or publish
to them. A user who wants to share a skill or workflow they authored
(§7.12) exports it to a git repo and adds that repo as a source — the
same mechanism as any other registry, no special path.

## 8. Data Model (sketch)

```
Extension
  id (canonical, tool-generated)
  type: enum [mcp_server, skill, slash_command, hook, sub_agent, memory_file]
  name
  origin_harness (provenance only, not a source-of-truth flag)
  canonical_config (JSON, normalized shape per type)
  created_at / updated_at

Binding
  extension_id -> Extension
  harness: enum [claude_code, codex_cli, opencode, cursor, ...]
  scope: enum [managed, local, project, user, global]   # harness-specific meaning
  file_path
  enabled: bool
  sync_state: enum [in_sync, drifted, conflict, divergent, unmanaged]
                          # `divergent` = informational text difference
                          # between memory files (§7.2); never queued
                          # for resolution
  last_written_hash
  last_seen_hash

Conflict                        # structured config only (§7.2)
  extension_id -> Extension
  bindings: [Binding, Binding, ...]
  resolved_source_binding_id (nullable until resolved)
  resolution: enum [unresolved, source_chosen, keep_both_intentionally]

Project
  id
  path (absolute, user-registered)
  display_name
  registered_at
  detected_sources: [source_type, ...]   # which harnesses/.agents found here

PrecedenceChain
  source: enum [claude_code, codex_cli, opencode, cursor, dot_agents, ...]
  project_id -> Project (nullable; null = global view)
  layers: [ { scope, file_path, exists: bool,
              order_rank,              # null when status = unconfirmed
              status: enum [consulted, not_consulted, unconfirmed],
              origin: enum [registered_project, ancestor_dir, global],
              resolves: bool           # false for unconfirmed layers,
                                       # which never win and never demote
            } ... ]                    # ordered high -> low precedence,
                                       # as reported by that source's adapter
    # `origin: ancestor_dir` covers harness directory walk-up (§7.9),
    # included whether or not that ancestor is a registered project

Bundle
  path (the git repo dir)
  schema_version
  created_by_tool_version
  source_host_os
  included_sources: [source_type, ...]
  included_projects: [ { slug, original_path } ... ]
  redactions: [ { file, key_path, placeholder_name } ... ]  # what was stripped

RestorePlan                     # computed, not persisted
  bundle_path
  actions: [ { source, scope, target_path,
               action: enum [create, overwrite, skip_no_harness,
                             skip_identical, needs_secret],
               diff } ... ]

Workflow
  id
  name / description
  steps: [ { order, instruction, expects_tool (nullable) } ... ]
  inputs: [ { name, description, required } ... ]
  requires: [ { type: enum [mcp_server, skill], ref } ... ]
  created_at / updated_at

WorkflowCompilation
  workflow_id -> Workflow
  harness
  target_form: enum [skill, slash_command, prompt_file, sub_agent]
  output_path
  degradations: [ { feature, reason } ... ]   # shown pre-compile, stored
  last_compiled_hash                          # for drift detection

RegistrySource
  id
  kind: enum [plugin_marketplace, mcp_registry, skill_collection,
              harness_native, user_defined]
  url
  enabled: bool
  last_refreshed_at
  cache_path

MarketplaceItem                 # normalized across all sources
  source_id -> RegistrySource
  name / description / author
  type: enum [plugin, skill, mcp_server, slash_command]
  repo_url
  version / resolved_ref
  install_targets: [harness, ...]
  contains: [ { type, name } ... ]        # for bundles
  risk_flags: [ hooks | scripts | mcp_credentials | broad_fs_access ]

InstalledFrom                   # provenance for audit + bundle reproduction
  extension_id -> Extension
  source_id -> RegistrySource
  item_name
  resolved_ref                  # pinned commit/version
  installed_at
```

## 9. Architecture

- **Adapter pattern**: one adapter module per source (harnesses, plus
  `.agents` per §5.1), responsible for (a) locating its global-scope config
  files, (b) given a registered project root, locating its project-scope
  config files there, (c) parsing them into canonical shape, (d)
  serializing canonical records back into its native format, (e) reporting
  its own ordered precedence chain (`PrecedenceChain.layers`, §8) —
  including its directory walk-up behavior (§7.9), its merge semantics
  (override vs. concatenate), and a `consulted`/`not_consulted`/
  `unconfirmed` status for `.agents`/`AGENTS.md` (§5.1) — and (f) declaring which
  workflow target forms it supports and with what limitations (§7.12.2), so
  the capability matrix is derived from adapters rather than hardcoded in
  the UI. Adding a harness = adding an adapter, not touching core logic.
- **Core service**: owns the canonical store, conflict detection, drift
  detection, and orchestrates adapters. Framework-agnostic business logic
  so it's testable without the UI.
- **Backend**: local HTTP service (suggested: Python + FastAPI, given
  existing familiarity) exposing a REST/JSON API over the core service.
  Runs on localhost only by default.
- **Storage**: local embedded DB (SQLite) for canonical records, bindings,
  and sync state — not a replacement for the harness files themselves,
  which remain the actual runtime config.

  **Decision: harness files are authoritative; the DB holds orchestration
  metadata only.** The files on disk are the single runtime truth, because
  they are what the harnesses actually read. The DB holds what the files
  cannot express: sync state, `last_written_hash`/`last_seen_hash`, the
  project registry, conflict resolutions, provenance, and canonical records
  not yet bound anywhere.

  Consequences the implementation must honor:
  - **On any disagreement, disk wins.** A difference between DB and file is
    never an error to reconcile away — it is drift (§7.2), a fact to report
    to the user, and the DB is what gets corrected.
  - **The DB is disposable.** Deleting it must lose no configuration: a
    rescan rebuilds everything except unbound canonical records and
    user decisions (adopted/unmanaged marks, conflict resolutions).
    Those are the only DB-only state, and they are annotations *about*
    config rather than config itself.
  - **The tool is uninstallable without consequence.** Removing agentctl
    leaves every harness working exactly as before, since nothing it wrote
    depends on the DB existing.
  - Reads for display always come from a scan, never from cached DB values
    presented as current.

  Rationale: the tool's core promise (§7.6, §7.10) is reporting what the
  machine actually does. A DB treated as truth would eventually report its
  own bookkeeping instead — and would make every hand-edit an error to
  reconcile rather than a fact to surface, which inverts the relationship
  the user wants.
- **Frontend**: local web dashboard (served by the backend, opened in the
  default browser) rather than a packaged desktop app for v1 — faster to
  iterate on, avoids Electron/Tauri packaging overhead, still gives a full
  "editable UI." Desktop packaging (Tauri) can wrap the same backend later
  if a native app is wanted.
- **No background daemon in v1** — scans run on-demand (button in UI) or
  via explicit refresh; avoids file-watcher complexity and surprise writes
  until the core sync logic is trustworthy.

## 10. UI/UX Requirements

- **Global / Project switcher** — persistent control, always visible;
  "Global" plus a list of registered projects (§7.9); switching re-scopes
  every other view (overview, matrix, precedence stack) to that context.
- **Overview** — counts per type/harness, "needs review" queue front and
  center (mirrors the "in use / needs review / discover" pattern that's
  proven useful in comparable tools).
- **Matrix view** — extensions as rows, harnesses as columns, cell shows
  enabled/disabled/conflict/drift at a glance.
- **Precedence stack view** — the visual home for §7.10: a vertical
  layered diagram for the selected project + source, highest precedence
  on top, winning layer highlighted, overridden layers dimmed but present,
  each layer clickable straight into its editor panel. This is the primary
  answer to "why is this setting not taking effect." Ancestor-directory
  layers (§7.9) are labeled as such, and `unconfirmed` layers sit in a
  visually separate region below the ordered stack — present and
  clickable, but carrying no rank, with a link to the adapter's
  verification status.
- **Detail/editor panel** — per-extension form matching its type; raw
  JSON/TOML/Markdown escape hatch for power-user edits.
- **Conflict resolution view** — side-by-side diff of conflicting
  bindings with a clear "keep left / keep right / keep both
  intentionally" action. Structured config only; memory files surface as
  `divergent` in the diff view below, with no resolution actions (§7.2).
- **Memory file editor** — Markdown editor with preview and section-level
  diff against other harnesses'/`.agents`' memory files. The diff is the
  v1 answer to duplicated instructions (§7.5) — it is read-only
  comparison, offering no "sync these" action until the composed-block
  model ships in Phase 2.
- **Bundle view** — export/snapshot actions, commit history with
  diff-between-snapshots, and a visible redaction report ("3 secrets
  replaced with placeholders") so the user can confirm nothing sensitive
  is about to be committed.
- **Restore planner** — the plan from §7.11 rendered as a checklist:
  each action with its target path, its diff, and a per-row toggle for
  selective restore. Confirm applies only the checked rows.
- **Skill authoring view** — form + Markdown editor for `SKILL.md`, with
  live frontmatter validation and inline guidance on the description
  field (since that field determines whether the skill actually triggers).
- **Workflow builder** — step list editor with inputs and declared
  dependencies, and a **compile preview**: target harnesses down one
  side, resulting form and any degradations down the other, with the
  generated file content viewable before it is written. The degradation
  column is not a footnote — it is the main thing the user needs to see
  before committing to a compile.
- **Marketplace browse** — unified search across configured registries,
  filterable by item type, harness compatibility, and source. Each result
  shows its source registry inline, so the user always knows where an
  item is coming from rather than seeing an undifferentiated catalog.
- **Pre-install disclosure sheet** — the gate described in §7.13.4:
  provenance, target paths, expanded bundle contents with per-item
  opt-out, and risk flags surfaced prominently. Items containing hooks
  or scripts show the actual code and require a second confirmation.
  This screen should feel heavier than the rest of the UI; that friction
  is the feature.
- **Registry sources settings** — add/remove/refresh registries, with
  last-refreshed timestamps and a clear indication that no third-party
  sources are enabled until the user adds them.

## 11. Non-Functional Requirements

- Local-first: works fully offline; the only network calls are optional
  marketplace browsing (if included) and explicit MCP server test
  connections.
- Safe writes: atomic file writes, automatic timestamped backups before
  any destructive change, one-click restore.
- No silent overwrites of files/keys this tool doesn't own.
- Cross-platform target: macOS + Linux at minimum (matches the harnesses'
  own primary support); Windows as stretch.

## 12. Security & Privacy Considerations

- Config files may contain API keys/tokens (MCP server env blocks). Mask
  in UI, avoid logging full values, avoid persisting raw secrets in the
  tool's own DB when the harness format allows an env-var reference
  instead.
- **Bundling is an exfiltration path and must be treated as one.** The
  export redaction in §7.11 is a hard requirement, not a default the
  user can casually disable: a config backup pushed to a git remote is
  exactly how credentials end up public. Requirements: redact by default;
  no "export with secrets" option in v1 at all; pre-seed the bundle's
  `.gitignore`; surface the redaction report before the first commit;
  and run a secret-pattern scan over the bundle as a final gate before
  any commit, failing loudly if something key-shaped slipped through.
- Restore reads a bundle that may have come from elsewhere. Even in the
  personal-backup case, treat bundle contents as data to be validated
  (schema check, path traversal check on every target path) rather than
  trusted input — a bundle can name arbitrary write targets.
- **Third-party marketplace items are executable code, not config.**
  Hooks run shell commands automatically on agent events; MCP servers are
  processes with whatever access their config grants; skills can bundle
  scripts. This is the highest-severity surface in the tool and the only
  place where it writes code it did not generate. Requirements are in
  §7.13.4; the principles are: disclose before installing, never
  one-click anything containing hooks or scripts, pin provenance, and
  never auto-update.
- Optional "scan skill/MCP source before adopting" step is out of scope
  for v1 but noted as a valuable later addition (comparable tools use an
  LLM-backed review pass before trusting third-party skills). It
  supplements disclosure rather than replacing it — an LLM review that
  returns "looks fine" should not be allowed to become the reason a user
  stops reading what they are installing.

## 13. MVP Scope (Phase 1)

1. Sources: Claude Code, Codex CLI, OpenCode, Cursor, plus `.agents`/`AGENTS.md`
   (§5.1) as its own source.
2. Extension types: MCP servers, memory/instruction files (`CLAUDE.md`, `AGENTS.md`, `MEMORY.md`, `.cursorrules`),
   skills.
3. Features: discovery/inventory, CRUD, enable/disable, drift detection,
   basic conflict view (manual resolution, no auto-merge).
4. Global view + project registration (§7.9) — must ship in v1, since
   without it the precedence view below has nothing to anchor to.
5. Precedence stack view (§7.10) for Claude Code, Codex CLI, and Cursor —
   this is the feature that most directly answers "which config wins,"
   so it isn't deferrable to a later phase even though it's more UI work
   than a plain CRUD table.
6. Bundle **export + git snapshot/history** (§7.11) — export is a
   read-only operation over the inventory, so it fits v1 cleanly and
   delivers backup value immediately.
7. **Skill authoring** (§7.12.1) — create/edit/validate `SKILL.md` and
   bind to harnesses. Included in v1 because skills are already a managed
   type and `SKILL.md` needs no compilation layer; authoring is mostly
   the editor plus validation on top of binding logic that already exists.
8. No profiles, no marketplace, no third-party code security scan pass, no daemon/watcher.
9. No composed shared memory block (§7.5) — memory/instruction files are
   independent files with a diff view in v1.
10. Single local user, single machine.

### Phase 2
- **Workflows** (§7.12.2) — deferred because the compilation layer and
  capability matrix depend on every v1 adapter being mature enough to
  report its own target-form support accurately. Building the compiler
  against two half-finished adapters would bake in wrong assumptions.
  Ships first with skill-only compilation (the portable case), then
  slash commands, then per-harness forms.
- Bundle **restore/apply** (§7.11) — deferred one phase behind export
  because restore is the tool's most destructive operation and should
  land only once the write path and backup/rollback machinery are proven.
  Export-without-restore is still useful on its own: the bundle is plain
  files, so a user can copy them manually in the meantime.
- **Composed shared memory block** (§7.5), opt-in — one canonical block
  written into each harness's memory file between explicit `agentctl`
  markers, with everything outside the markers preserved byte-for-byte.
  Deferred from v1 because it requires each adapter to have verified its
  harness's load semantics (concatenate vs. override vs. truncate) and
  because it is a write into files the user reads by hand.
- Gemini CLI adapter.
- **Federated marketplace, browse-only** (§7.13) — discovery, search,
  and normalized listing across registries, with install still handled
  by each harness's own CLI. Browse-only first because the index and
  normalization can be validated without owning the risk of writing
  third-party executable code to disk.
- Slash commands, hooks, sub-agents as extension types.
- Profiles (save/restore snapshots).
- Plugin support (bundles of the above, mirroring how Claude Code plugins
  package skills/commands/MCP together).

### Phase 3
- **Marketplace install** (§7.13.3–7.13.4) — installing through the tool,
  with the full disclosure/confirmation gate, provenance pinning, and
  manual-only updates. Split from browse deliberately: this is the point
  where the tool starts writing third-party executable code onto the
  user's machine, and it should not ship until the disclosure UI has been
  designed carefully rather than bolted onto a working browser.
- Optional LLM-backed security scan before adopting a third-party skill
  or plugin — a supplement to disclosure, never a replacement for it.
- Bundle sharing between people (team baseline config), which raises
  trust questions the personal-backup case doesn't — a bundle from a
  colleague is untrusted input and would need review-before-apply beyond
  what §7.11 specifies.

## 14. Decisions and Open Questions

### 14.1 Resolved

Decided; the body sections above are authoritative and these entries
record the reasoning so it isn't relitigated.

| Question | Decision | Where | Blocks |
|---|---|---|---|
| Nested registered projects: own scope, or walk up? | **Registration scopes tracking, not precedence.** The stack always mirrors real harness behavior, including directory walk-up, whether or not the ancestor is registered. Walk-up semantics are adapter-reported. | §7.9 | PR 1.7 |
| Shared memory-file model: composed block vs. independent + diff | **Independent files + diff in v1; composition is an explicit Phase 2 opt-in**, gated on verified per-harness load semantics and a proven write path, and structurally reversible via begin/end markers. | §7.5 | PR 1.13, PR 2.26–2.28 |
| Harness `.agents`/`AGENTS.md` support unknown | **Show as `unconfirmed`**, outside the ordered stack, excluded from resolution — it can never win and never demote a confirmed layer. Omitting hides a possibly-loaded file; guessing produces a confidently wrong order in the one authoritative view. | §5.1, §7.10 | PR 1.5, PR 1.10 |
| Memory-file conflict aggressiveness | **Normalized text compare → `divergent`, informational only.** No resolution prompt, no auto-merge, no semantic reworded-instruction inference. Full `Conflict` records stay for structured config. | §6, §7.2 | PR 1.9 |
| DB vs. harness files as source of truth | **Harness files authoritative; DB is orchestration metadata only.** On disagreement disk wins, the DB is disposable and rebuildable by rescan, and removing agentctl leaves every harness working. | §9 | PR 0.2 |
| Bundle history: config changes or snapshots? | **Snapshot history, stated plainly** in the bundle's generated README and in the history UI. No feature may assume commits are per-change. | §7.11 | PR 1.17 |

### 14.2 Still open

Each carries a stable `OQ-n` identifier. The PR that must resolve it
references that identifier at the point of blockage in
[ROADMAP.md](./ROADMAP.md), so a question is never rediscovered late.

**OQ-1 — Project-scope restore path mapping.** *(blocks PR 2.5, §7.11)*
Project-scope config in a bundle is ambiguous on restore: the original
project may not exist on the new host, or may live at a different path.
Prompt for a path mapping per project, restore global-only by default,
or something else? Leaning toward global-only by default with projects
opt-in and path-mapped, since that's the least surprising.

**OQ-2 — Dotfiles-repo / symlink coexistence.** *(blocks PR 2.7, §7.11)*
Many users already track `~/.claude/` in a personal dotfiles repo with
stow/symlinks. Does the bundle detect and refuse to fight that
(read-only, warn), or offer to co-exist? Writing into a symlinked path
that points at a git repo the user manages elsewhere is a real conflict
scenario worth handling explicitly rather than discovering in the field.

**OQ-3 — Workflow as its own entity vs. a Skill variant.** *(revisit at
PR 2.16, §7.12.2)* Is "Workflow" a distinct entity at all, or just a
Skill with a step list and inputs? Merging them keeps the model smaller
and leans on the most portable format; keeping them separate allows
compiling to non-skill forms (slash commands, sub-agents) where those are
a better fit. Currently specified as separate — deliberately left open
until one compiler exists, since if compilation to skills turns out to
cover 90% of real use, the extra entity is unearned complexity. Deciding
this early would be guessing.

**OQ-4 — Compiled artefacts inside tracked project scope.** *(blocks the
first compiler that targets project scope — PR 2.16 onward, §7.12.2)*
If a workflow compiles into `.claude/commands/` inside a
git-tracked project, a teammate now has a generated file whose canonical
source lives only on the author's machine. Options: mark generated files
with a header comment, refuse to compile into tracked project scope by
default, or ship the canonical definition alongside. Needs deciding
before workflows target project scope at all.

**OQ-5 — Provenance back-fill for externally installed items.** *(blocks
PR 3.4, §7.13.4)* Marketplace items installed via a harness's *own* CLI
(outside this tool) appear as unmanaged extensions with no provenance.
Attempt to back-fill by matching against known registries, or accept that
only tool-installed items are auditable? Back-filling is guesswork;
accepting the gap is honest but leaves a blind spot in the security story.

**OQ-6 — Cross-harness install targets beyond what an item declares.**
*(blocks PR 3.2, §7.13.3)* A skill from a Claude-oriented collection will
usually work anywhere `SKILL.md` is read, but a plugin bundle will not
decompose cleanly. How aggressive should the tool be about offering
install targets the item never declared? Permissive is more useful and
more likely to produce silently broken installs.

**OQ-7 — Bundle captures marketplace items as content vs. provenance.**
*(blocks PR 3.4, §7.11, §7.13)* Does bundle export capture
marketplace-installed items as *content* or as *provenance + reinstall
instruction*? Provenance is smaller and keeps upstream authorship intact,
but breaks if the source disappears; content is self-contained but
effectively vendors someone else's code into the user's backup repo.

## 15. Appendix: Known Harness Config Locations (reference)

```
Claude Code
  ~/.claude.json                 - global state incl. some MCP entries
  ~/.claude/settings.json        - user settings
  .claude/settings.json          - project settings (shared, checked in)
  .claude/settings.local.json    - project settings (local, gitignored)
  CLAUDE.md (project + ~/.claude/CLAUDE.md) - memory & instructions
  ~/.claude/projects/<slug>/memory/MEMORY.md - user auto-memory per project
  .claude/memory/MEMORY.md       - project-scoped auto-memory
  .claude/skills/                - skills
  ~/.claude/agents/               - sub-agents
  .claude/commands/               - slash commands
  Precedence: managed > CLI arg > local > project > user

Codex CLI
  ~/.codex/config.toml           - MCP servers under [mcp_servers.*], TOML
  AGENTS.md                      - memory & instructions

OpenCode
  ~/.config/opencode/opencode.json - MCP servers (typed local/remote)
  ~/.config/opencode/skills        - skills
  ~/.config/opencode/commands      - slash commands
  AGENTS.md                        - memory & instructions

Cursor
  ~/.cursor/mcp.json              - global MCP servers
  .cursor/mcp.json                - project MCP servers
  .cursorrules / .cursor/rules/ / AGENTS.md - memory & instructions
  ~/.cursor/skills                - skills
  ~/.cursor/commands              - slash commands
  Precedence: project (.cursor/) > user (~/.cursor/)

Gemini CLI
  ~/.gemini/settings.json         - MCP servers + settings
  GEMINI.md (project + user)      - memory & instructions

Shared convention (.agents)
  ~/.agents/                      - global shared rules/commands/hooks/MCP
  ~/.agents/memory/MEMORY.md      - global shared memory notes
  <project>/.agents/              - project-level equivalent
  <project>/.agents/memory/       - project-level shared memory notes
  AGENTS.md (project root)        - instruction/rule file
  MEMORY.md (project root)        - memory file
  NOTE: whether a given harness actually reads from .agents/AGENTS.md,
  vs. only its own native files, varies by tool and changes over time —
  this must be verified per adapter, not assumed uniform.
```

*(Verify current paths/formats against each tool's own docs before
implementing an adapter — these tools ship fast and file layouts do
change.)*
