# ROADMAP.md — agentctl

Delivery plan for [SPECS.md](./SPECS.md). Organized into phases; each phase is
a list of **PR-sized units of work** that can be reviewed independently by a
human in one sitting.

## How to read this

- Each `PR n.m` is intended to be a single pull request: one coherent change,
  reviewable in isolation, mergeable to `main` without breaking anything.
- **Dep** lines name the PRs that must land first.
- **Done when** is the reviewable acceptance bar — if it can't be checked from
  the diff plus a test run, it's underspecified.
- Section references (§) point at [SPECS.md](./SPECS.md).

### Conventions applied to every PR

- Tests ship in the same PR as the code (core logic is UI-free and unit
  testable per §9).
- Adapters ship with fixture directories under `tests/fixtures/<source>/` that
  mirror real on-disk layouts, so parsing is verified against realistic input.
- No PR both adds a new *read* surface and a new *write* surface. Reads land
  first, writes follow.
- Coverage gate (`fail_under = 80`) stays green; `poe format` and `poe test`
  pass.
- Any PR that changes the on-disk write behaviour must state its rollback
  story in the PR description.

---

## Phase 0 — Foundations

No harness knowledge yet. Establishes the spine everything else plugs into.
Nothing user-facing ships here; the goal is that Phase 1 PRs stay small.

### PR 0.1 — Domain model
- Pydantic models for `Extension`, `Binding`, `Conflict`, `Project`,
  `PrecedenceChain` (§8) — the v1 subset only.
- Enums for `ExtensionType`, `Harness`/`Source`, `Scope`, `SyncState`
  (including `divergent`, §7.2), `LayerStatus`
  (`consulted`/`not_consulted`/`unconfirmed`, §7.10), `LayerOrigin`
  (`registered_project`/`ancestor_dir`/`global`, §7.9), and
  `ConflictResolution` (including `keep_both_intentionally`).
- Canonical config shapes per extension type (`mcp_server`, `memory_file`,
  `skill`), each with its own normalized schema.
- **Done when**: models round-trip through JSON; invalid enum/shape combos
  raise; no filesystem or DB code in this PR.

### PR 0.2 — Storage layer (SQLite)
- Embedded DB for canonical records, bindings, sync state, projects.
- Schema migration mechanism (even a linear versioned-DDL runner) from day one.
- Repository interfaces that the core service depends on, so storage is
  swappable and mockable in tests.
- **Decided** (§14.1): harness files are authoritative; the DB holds
  orchestration metadata only. On any DB/file disagreement, disk wins and
  the DB is corrected — the difference is reported as drift, never
  reconciled away. The only DB-only state is user *decisions*
  (adopted/unmanaged marks, conflict resolutions) and canonical records not
  yet bound anywhere; everything else must be reconstructible by rescan.
- **Done when**: create/read/update/delete on every Phase-0 model; migration
  from empty DB to current schema is tested; and deleting the DB then
  rescanning reproduces the full inventory, losing only the DB-only state
  named above.
- **Dep**: 0.1

### PR 0.3 — Safe write layer
- Atomic write primitive (temp file + `os.replace`) (§7.3, §11).
- Timestamped backup before any overwrite, with a session-scoped rollback
  index (§7.11 "Rollback", §11).
- Key-scoped merge helper: update only tool-owned keys inside a shared file,
  preserving unknown keys, ordering, and (where format allows) formatting.
- **Done when**: tests cover partial-write interruption, backup+restore of an
  overwritten file, and "unrelated keys in `settings.json` survive a write".
- **Dep**: none (pure filesystem utility)

### PR 0.4 — Source adapter protocol
- `SourceAdapter` protocol with the six responsibilities from §9: locate
  global config, locate project config, parse → canonical, serialize →
  native, report precedence chain, declare capabilities.
- The precedence-chain contract carries the §7.9/§7.10 decisions: each
  adapter declares its directory walk-up behavior (how far it ascends and
  where it stops), its merge semantics (override vs. concatenate), and a
  `LayerStatus` per layer. Adapters that cannot verify a source report
  `unconfirmed` — the protocol must make that expressible rather than
  forcing a guess.
- Adapter registry + discovery; a `NullAdapter`/fake used only in tests.
- Capability declaration struct (extension types supported, scopes supported,
  workflow target forms — the last one unused until Phase 2 but declared now).
- **Done when**: a fake adapter is registered and exercised end-to-end through
  the registry; no real harness is referenced anywhere in this PR.
- **Dep**: 0.1

### PR 0.5 — Core service skeleton + app wiring
- Core service object orchestrating adapters + storage (§9), framework-agnostic.
- FastAPI app skeleton bound to localhost, health endpoint, DI wiring through
  the existing `agentctl/injections/` pattern.
- CLI entry point (`agentctl`) with subcommand scaffolding and `--json` output
  flag; no real subcommands yet.
- **Done when**: `poe dev` serves health; `agentctl --help` lists the planned
  surface; both are covered by tests.
- **Dep**: 0.2, 0.4

---

## Phase 1 — MVP (§13)

Ships the v1 promise: see everything, understand precedence, edit safely,
back it up to git. Read paths land before write paths throughout.

### 1a. Discovery (read-only)

### PR 1.1 — Claude Code adapter: read
- Locate + parse `~/.claude.json`, `~/.claude/settings.json`,
  `.claude/settings.json`, `.claude/settings.local.json`, `CLAUDE.md`
  (project + user), project auto-memory `MEMORY.md` (`~/.claude/projects/<slug>/memory/MEMORY.md`,
  `.claude/memory/MEMORY.md`), `.claude/skills/` (§15).
- Extract MCP servers, memory/instruction files, skills into canonical shape.
- Report the 5-layer precedence chain (managed → CLI arg → local → project →
  user) as ordered `PrecedenceChain.layers`, with `exists` per layer.
- Report whether Claude Code consults `.agents`/`AGENTS.md`, verified against
  current docs, not assumed (§5.1).
- **Done when**: fixtures covering "nothing installed", "global only",
  "global + project", and malformed JSON all parse or fail with a clear,
  non-fatal error.
- **Dep**: 0.4

### PR 1.2 — Codex CLI adapter: read
- TOML parsing of `~/.codex/config.toml` (`[mcp_servers.*]`) and `AGENTS.md`.
- Same canonical output + precedence reporting contract as 1.1.
- **Done when**: TOML-specific edge cases (nested tables, arrays of tables,
  comments preserved on read) are covered by fixtures.
- **Dep**: 0.4

### PR 1.3 — OpenCode adapter: read
- `~/.config/opencode/opencode.json` typed local/remote MCP entries,
  `~/.config/opencode/skills`, `AGENTS.md` memory/instruction files (§15).
- Same canonical output contract as 1.1.
- **Dep**: 0.4

### PR 1.4 — Cursor adapter: read
- Locate + parse `~/.cursor/mcp.json`, `.cursor/mcp.json`, `.cursorrules`,
  `.cursor/rules/`, `AGENTS.md`, and `~/.cursor/skills` (§15).
- Extract MCP servers, memory/instruction files, skills into canonical shape.
- Report the 2-layer precedence chain (project `.cursor/` > user `~/.cursor/`)
  and whether Cursor consults `.agents`/`AGENTS.md` natively or via symlink.
- **Done when**: fixtures for global-only, project-scoped, and combined Cursor
  configs parse into canonical models with correct precedence.
- **Dep**: 0.4

### PR 1.5 — `.agents` source adapter: read
- Discover `~/.agents/` (including `~/.agents/memory/MEMORY.md`) and `<project>/.agents/`
  (including `<project>/.agents/memory/MEMORY.md`), plus root `AGENTS.md` and `MEMORY.md`,
  independent of whether any harness is installed (§5.1).
- Per-harness consumption report: `consulted` (natively or via symlink,
  with rank) / `not_consulted` / `unconfirmed`.
- **Decided** (§14.1): `unconfirmed` layers are shown, placed outside the
  ordered stack with no `order_rank`, and carry `resolves: false` so the
  resolution engine (1.10) can never name one as a winner or let one demote
  a confirmed layer. Verification status is surfaced per adapter so a
  layer can be upgraded once confirmed.
- Symlink resolution: detect when a harness path is a symlink into `.agents`
  and record it rather than double-counting the same file.
- **Done when**: a fixture where `.agents` support is unverified produces a
  chain whose winner is computed identically with and without the
  unconfirmed layer present.
- **Dep**: 0.4

### PR 1.6 — Inventory + classification
- Scan orchestration across all registered adapters, on demand (§7.1).
- Build the inventory, tag each item with source + scope, classify as
  **Adopted** / **Needs review** / **Unmanaged**.
- Content hashing (`last_seen_hash`) for every discovered binding.
- **Done when**: a scan over a fixture home dir with four harnesses produces
  a stable, ordered inventory; repeated scans are idempotent.
- **Dep**: 1.1, 1.2, 1.3, 1.4, 1.5

### PR 1.7 — Project registration
- Register/list/unregister a project by absolute path (§7.9); unregister never
  touches files.
- Per-project source detection by asking each adapter what it finds there.
- Global vs. project scan contexts in the core service.
- **Decided** (§14.1): registration scopes *tracking*, not precedence.
  Registration state is never an input to precedence computation. Layers
  from ancestor directories appear whenever the adapter reports the harness
  reads them — including unregistered ancestors, tagged
  `origin: ancestor_dir` — and a registered ancestor the harness does not
  read from this directory does not appear.
- **Done when**: a fixture monorepo with a registered root and a registered
  sub-project yields identical precedence chains for the sub-project before
  and after the root is unregistered.
- **Dep**: 1.6

### PR 1.8 — Drift detection
- Compare `last_seen_hash` vs `last_written_hash` to mark bindings `drifted`
  (§7.2); untouched-by-tool items stay `unmanaged`, not `drifted`.
- Adopt-drift and mark-for-restore state transitions in the core service
  (the *restore* action itself is a write and lands in 1.11).
- **Dep**: 1.6

### PR 1.9 — Conflict and divergence detection
- Same logical extension with differing definitions across sources/scopes
  (§7.2) → `Conflict` records. **Structured config only** (MCP servers in
  v1), compared field by field.
- **Decided** (§14.1): memory/instruction files do **not** produce
  `Conflict` records. Same-role files are compared as text after
  normalizing line endings and trailing whitespace; any difference sets the
  binding's `sync_state` to `divergent` and is reported with a diff.
  Informational only — no resolution queue, no auto-merge, and explicitly
  no semantic "same instruction reworded" inference.
- `keep_both_intentionally` as a first-class `Conflict` resolution,
  persisted so the conflict stops reappearing. Note this is a *resolution*
  on a `Conflict`, distinct from the `divergent` *sync state* above; the
  two must not be collapsed in the model or the UI.
- **Done when**: a fixture with two memory files differing only in trailing
  whitespace compares equal; one differing in prose reports `divergent` and
  creates no `Conflict` record.
- **Dep**: 1.6

### PR 1.10 — Precedence resolution engine
- For a given (source, project, key), resolve the winning layer and expose the
  full ordered stack with winner/overridden marks (§7.6, §7.10).
- Works for structured settings and memory files; per-adapter merge semantics
  (override vs. concatenate) and walk-up behavior come from the adapter,
  never hardcoded and never inferred from the directory tree (§7.9).
- Layers with `status: unconfirmed` are carried through for display but
  excluded from resolution (§7.10, 1.5) — they can neither win nor demote a
  confirmed layer.
- Claude Code, Codex CLI, and Cursor are the required-correct targets for v1 (§13.5).
- **Done when**: given a fixture with the same MCP server at three layers, the
  engine names the winning file and the reason it wins; and a fixture whose
  top layer is `unconfirmed` resolves to the same winner as one where that
  layer is absent.
- **Dep**: 1.1, 1.2, 1.4, 1.7

### 1b. Write paths

### PR 1.11 — MCP server CRUD
- Create/edit/delete canonical MCP server records; bind to a chosen
  source + scope; propagate edits to all bindings or edit one in isolation
  (§7.3).
- Serialization through each adapter's native writer (Claude Code, Codex CLI, OpenCode, Cursor); all writes via 0.3.
- Restore-drifted-binding action (the counterpart to 1.8).
- Secrets: prefer env-var indirection where the harness format supports it;
  never persist raw secret values in the DB (§7.8).
- **Done when**: writing to a file with unrelated user keys leaves those keys
  byte-identical; every write is backed up and rollback-able.
- **Dep**: 0.3, 1.6

### PR 1.12 — Enable/disable
- Toggle a binding per source without deleting the canonical record (§7.4).
- **Dep**: 1.11

### PR 1.13 — Memory and instruction file management
- Read/write `CLAUDE.md`, `AGENTS.md`, `MEMORY.md`, `.cursorrules`, and `.agents` memory/instruction files as
  first-class extensions (§7.5).
- Scope reporting + "which file wins for this directory" via 1.10.
- **Decided** (§14.1): independent files + diff. Each harness's memory file
  is read, edited, and diffed **in place**; this PR ships no cross-file
  composition and no "sync these files" action. The composed canonical
  block is a Phase 2 opt-in (PR 2.x), gated on verified per-harness load
  semantics.
- Divergence between same-role files surfaces via 1.9 (`divergent`), shown
  as a read-only comparison.
- **Done when**: no write path in this PR touches more than one file per
  user action.
- **Dep**: 1.10, 1.11

### PR 1.14 — Skill management + authoring
- Adopt existing skills; create new ones in-app (§7.12.1).
- `SKILL.md` frontmatter validation: schema, required fields, name uniqueness
  across the inventory, weak-description warning.
- Bundled supporting files travel with the skill.
- Bind one canonical skill into multiple harness skill roots; edit once,
  propagate.
- **Dep**: 1.11

### 1c. Portability

### PR 1.15 — Bundle export + redaction
- Produce `agent-bundle/` in the layout from §7.11: `manifest.json`, `global/`,
  `projects/<slug>/`, `secrets.template.env`, pre-seeded `.gitignore`.
- Normalize home-relative absolute paths to `${HOME}`, recording originals.
- **Redact secrets by default, with no opt-out in v1** (§12): MCP `env` blocks,
  `*_API_KEY`, `*_TOKEN`, auth headers → named placeholders; key names only
  into `secrets.template.env`.
- Pre-write report of exactly what was excluded and why.
- **Done when**: a fixture inventory containing three planted credentials
  exports with zero secret values present anywhere in the bundle, asserted by
  a test that greps the whole output tree.
- **Dep**: 1.6

### PR 1.16 — Secret-pattern gate
- Final scan over the assembled bundle before any commit; fails loudly on
  anything key-shaped (§12).
- Deliberately separate from 1.15 so the gate is reviewed as a security
  control on its own, not buried in an exporter diff.
- **Dep**: 1.15

### PR 1.17 — Git snapshot + history
- `init` (repo + `.gitignore` + first commit), `snapshot` (re-export + commit
  with an auto-generated, user-editable message), commit listing, and diff
  between any two snapshots (§7.11).
- Commits are blocked unless 1.16's gate passes.
- **Decided** (§14.1): the bundle records *snapshot* history, not an audit
  trail of config changes. A commit means "the state of your config when
  you ran `snapshot`" and nothing more. State this in the generated README
  inside the bundle, label the history UI as snapshots, and date entries by
  snapshot time — no commit may be presented as a record of a change event.
- No feature in this or any later PR may assume commits are per-change;
  "who changed this and when" is explicitly not answerable from this
  history.
- **Done when**: the generated bundle README contains the snapshot-vs-audit
  statement, asserted by a test.
- **Dep**: 1.16

### 1d. Interfaces

### PR 1.18 — REST API for the v1 surface
- Endpoints over the core service: inventory, projects, precedence chains,
  extension CRUD, enable/disable, bundle export/snapshot/history.
- Localhost-bound by default; masked secrets in every list response (§7.8).
- OpenAPI schema checked into the repo so API changes are reviewable as a diff.
- **Dep**: 1.10, 1.14, 1.17

### PR 1.19 — CLI: `status`, `why`, and `project`
- `agentctl status` — cross-harness overview (counts per type/source, needs-
  review queue, drift/conflict summary), `--json` supported.
- `agentctl why <key>` — the precedence stack for a key, printed top to bottom,
  winner marked, overridden layers shown (§7.10 in text form).
- `agentctl project add <path>`, `agentctl project list`, `agentctl project remove <path>` —
  register, list, and unregister project paths from CLI (§7.9).
- **Dep**: 1.10

### PR 1.20 — CLI: `snapshot`
- `agentctl snapshot` — export + gate + commit, with the redaction report
  printed before anything is written.
- **Dep**: 1.17

### PR 1.21 — Web UI shell + `agentctl ui`
- Static frontend served by the FastAPI backend, launched via `agentctl ui` and opened in the default browser (§9).
- Global/Project switcher (persistent, re-scopes every view) + Overview page
  with the needs-review queue front and center (§10).
- **Dep**: 1.18

### PR 1.22 — Matrix view
- Extensions as rows, sources as columns, cell state =
  enabled/disabled/conflict/drift (§10).
- **Dep**: 1.21

### PR 1.23 — Precedence stack view
- Vertical layered diagram, highest precedence on top, winner highlighted,
  overridden layers dimmed but present; each layer click-through opens the
  editor panel for that file (§7.10, §10).
- **Dep**: 1.21

### PR 1.24 — Detail/editor panel + raw escape hatch
- Per-type form editors, plus raw JSON/TOML/Markdown editing with validation
  before save.
- **Dep**: 1.21

### PR 1.25 — Conflict resolution view
- Side-by-side diff with keep-left / keep-right / keep-both-intentionally
  (§10). The diff component here is reused by the bundle history and, later,
  by the restore planner — build it to be reused.
- **Dep**: 1.24

### PR 1.26 — Memory file editor
- Markdown editor + preview, section-level diff against other sources' memory
  files (§7.5, §10).
- **Dep**: 1.24

### PR 1.27 — Skill authoring view
- Form + Markdown editor for `SKILL.md`, live frontmatter validation, inline
  guidance on the description field (§10).
- **Dep**: 1.24

### PR 1.28 — Bundle view
- Export/snapshot actions, commit history with snapshot diffs, and a visible
  redaction report before the first commit (§10).
- **Dep**: 1.25

### Phase 1 exit criteria
- Fresh machine → scan → see every v1 source's config, with precedence
  explained for Claude Code, Codex CLI, and Cursor.
- Edit an MCP server, a memory/instruction file, and a skill through the tool; verify no
  unrelated key in any shared file changed.
- Export a bundle containing planted credentials; confirm none leave the host.
- Not shipping in v1 (§13.8): profiles, marketplace, restore, workflows,
  daemon/watcher.

---

## Phase 2 — Breadth and restore

### 2a. Restore (§7.11)

- **PR 2.1 — Bundle reader + validation.** Schema check, path-traversal check
  on every target path, treat bundle contents as untrusted data (§12).
- **PR 2.2 — Restore planner.** Detect harnesses present on *this* host,
  compute actions (`create` / `overwrite` / `skip_no_harness` /
  `skip_identical` / `needs_secret`) with a diff per action. Pure computation,
  writes nothing — reviewable on its own.
- **PR 2.3 — Restore apply + rollback.** Confirm-then-write, backup every
  overwritten file, whole-apply undo for the session (§7.11).
- **PR 2.4 — Selective restore.** Per-row toggles: global-only, one project,
  one source.
- **PR 2.5 — Project path mapping.** Default global-only; projects opt-in with
  an explicit path mapping when the original path doesn't exist.
  **Blocked on OQ-1** (§14.2): per-project prompt vs. global-only default vs.
  something else. Current leaning — global-only default, projects opt-in and
  path-mapped — must be confirmed and recorded in the PR description before
  merge.
- **PR 2.6 — Restore planner UI + `agentctl restore` CLI.** Checklist of
  actions with diffs and per-row toggles; CLI prints the same plan and
  requires explicit confirmation.
- **PR 2.7 — Dotfiles-repo coexistence.** Detect that a target path is a
  symlink into a user-managed git repo (stow-style) and warn/refuse rather
  than writing through it. **Blocked on OQ-2** (§14.2): refuse and warn
  (read-only) vs. offer explicit co-existence. Detection is required either
  way, so it can be built before the question resolves; the *response* to a
  detected dotfiles repo is what OQ-2 decides.

### 2b. More sources

- **PR 2.8 — Gemini CLI adapter** (`~/.gemini/settings.json`, `GEMINI.md`).
- Lands as an adapter only — if it requires a core change, that change
  is a separate PR first, because §9 promises adding a harness doesn't touch
  core.

### 2c. More extension types

- **PR 2.9 — Slash commands** as a managed type across adapters that support
  them.
- **PR 2.10 — Hooks** as a managed type. Read + display before write; hooks are
  executable code and get a heavier confirmation path than settings.
- **PR 2.11 — Sub-agents** as a managed type.
- **PR 2.12 — Plugins** (Claude Code bundles: skills + commands + sub-agents +
  hooks + `.mcp.json`) as a composite managed type with expandable contents.

### 2d. Profiles

- **PR 2.13 — Profiles** (§7.7): save/restore named snapshots of "which
  extensions are enabled where"; restore reuses the enable/disable path from
  1.12, not a new write mechanism.

### 2e. Workflows (§7.12.2)

Sequenced after the v1 adapters are mature enough to report target-form
support accurately.

- **PR 2.14 — Workflow model + editor.** `steps`, `inputs`, `requires`,
  `targets`; storage + REST + builder UI. No compiler yet.
- **PR 2.15 — Capability matrix.** Per-target-harness form, unsupported
  features, and explicit degradations, derived from adapter declarations
  (§9) — never hardcoded in the UI.
- **PR 2.16 — Skill compiler.** The portable case: workflow → `SKILL.md`, with
  generated-file marking and the compile preview showing file content before
  it is written. **Blocked on OQ-4** (§14.2) *only if this compiler may write
  into project scope* — it is the first PR that generates artefacts, so the
  question goes live here and binds every later compiler. Compiling to
  user-scope only is a valid way to land this PR with OQ-4 still open;
  say which was chosen in the PR description.
  **Revisit OQ-3** (§14.2) once this lands: with one compiler working, decide
  whether Workflow stays a separate entity or collapses into Skill. The
  question was deliberately left open until exactly this point.
- **PR 2.17 — Slash-command compiler**, per-harness argument conventions.
  **Blocked on OQ-4** (§14.2) if not already resolved at 2.16.
- **PR 2.18 — Prompt-file and sub-agent compilers** where supported.
- **PR 2.19 — Compilation drift.** Edits to compiled artefacts are detected as
  drift and offered as adopt-back or discard; no reverse parsing of harness
  command files into structured steps (§7.12.2, one-way by design).
- **PR 2.20 — Dependency awareness.** `requires: [mcp:github]` unsatisfied on a
  target → flag before compiling, offer to bind in the same action.
- **PR 2.21 — Workflows in the bundle.** Canonical definitions travel;
  restored hosts regenerate rather than copy stale artefacts.
Open questions live in this section: **OQ-3** (Workflow as its own entity vs.
a Skill variant) is revisited at PR 2.16; **OQ-4** (generated files inside
git-tracked projects — header-marked, refused by default, or shipped
alongside their canonical definition) must be resolved before any compiler
targets project scope. Both are marked inline above.

### 2f. Federated marketplace — browse only (§7.13)

- **PR 2.22 — Registry source model + adapters** (`plugin_marketplace`,
  `mcp_registry`, `skill_collection`, `harness_native`, `user_defined`).
  **Zero third-party sources enabled by default.**
- **PR 2.23 — Normalized item model + local cache** with a visible
  last-refreshed timestamp; browsing works offline.
- **PR 2.24 — Search/browse UI**, filterable by type, harness compatibility,
  and source; every result names its source registry inline.
- **PR 2.25 — Registry sources settings UI**: add/remove/refresh, with an
  explicit statement that nothing third-party is enabled until the user adds it.
- Install stays out of this phase — it is handled by each harness's own CLI
  until Phase 3.

### 2g. Composed shared memory block (§7.5) — opt-in

Deferred from v1 by the §14.1 decision. Sequenced late in Phase 2 because
it writes into files users read and edit by hand, so it should land only
after the v1 write path and backup/rollback machinery have real mileage.

- **PR 2.26 — Load-semantics verification per adapter.** Each v1 adapter
  declares whether its harness concatenates, overrides, or truncates when
  multiple memory files apply, verified against current docs. No
  composition ships for an adapter that reports `unconfirmed`.
- **PR 2.27 — Composed block writer.** One canonical block written between
  explicit `agentctl` begin/end markers; everything outside the markers
  preserved byte-for-byte; removing the block leaves a normal
  hand-maintained file. Opt-in per file, never on by default.
- **PR 2.28 — Composition in the memory editor.** Show which region of each
  file is composed vs. hand-written, and which harness will actually load
  it, so the §7.6 promise still holds for composed files.
- **Done when**: a file with a composed block, hand-edited outside the
  markers, round-trips through a recompose with the hand edits byte-identical.

---

## Phase 3 — Third-party code and sharing

### 3a. Marketplace install (§7.13.3–7.13.4)

- **PR 3.1 — Pre-install disclosure sheet.** Provenance, target paths, expanded
  bundle contents with per-item opt-out, risk flags (`hooks`, `scripts`,
  `mcp_credentials`, `broad_fs_access`). Ships **before** any install code
  exists, so the gate is designed first rather than bolted on.
- **PR 3.2 — Install routing.** Harness-native installer where one exists,
  direct file placement where it doesn't; installed items become ordinary
  managed extensions subject to binding/drift/precedence.
  **Blocked on OQ-6** (§14.2): how permissive to be about offering install
  targets an item never declared. Permissive is more useful and more likely
  to produce silently broken installs; decide and record before merge.
- **PR 3.3 — Hook/script second confirmation.** No one-click install for items
  containing hooks or scripts; the actual code is shown.
- **PR 3.4 — Provenance pinning** (`InstalledFrom`: source URL + resolved
  commit), so installs are auditable and reproducible from a bundle.
  **Blocked on OQ-5** (§14.2): back-fill provenance for items installed
  outside the tool by matching against known registries, or accept that only
  tool-installed items are auditable and say so plainly in the UI.
  **Blocked on OQ-7** (§14.2): whether bundle export captures
  marketplace-installed items as content or as provenance + reinstall
  instruction — this PR defines the provenance record the bundle would carry,
  so the two are decided together.
- **PR 3.5 — Manual-only updates.** Updates surfaced, never applied
  automatically.

### 3b. Optional review pass

- **PR 3.6 — LLM-backed source review** before adopting a third-party skill or
  plugin. Presented as a supplement to disclosure, never as a substitute — a
  "looks fine" verdict must not replace the disclosure sheet.

### 3c. Sharing

- **PR 3.7 — Bundle sharing between people.** A colleague's bundle is untrusted
  input: review-before-apply beyond what §7.11 specifies.

### 3d. Beyond

- Hermes Agent adapter (v3, YAML + categorized skills).
- Optional file watcher / background daemon — only once the write path has
  proven itself in real use (§9 explicitly defers this).
- Tauri desktop packaging wrapping the same backend (§9).
- Windows support (stretch, §11).

---

## Decisions

Settled; recorded here so they aren't relitigated in review. Full reasoning
in §14.1 of [SPECS.md](./SPECS.md).

| Question | Decision | Lands in |
|---|---|---|
| Nested registered projects: own scope or walk up? | Registration scopes tracking, not precedence — the stack mirrors real harness walk-up, registered or not | PR 1.7 |
| Memory files: composed canonical block vs. independent + diff | Independent + diff in v1; composed block is a Phase 2 opt-in (2g) | PR 1.13, PR 2.26–2.28 |
| `.agents` support unknown for a harness: show "unconfirmed" or omit | Show as `unconfirmed`, unranked and excluded from resolution | PR 1.5, PR 1.10 |
| Memory-file conflict aggressiveness | Normalized text compare → `divergent`, informational only; no `Conflict` records for prose | PR 1.9 |
| DB vs. harness files as source of truth | Harness files authoritative; DB is orchestration metadata, disposable and rebuildable by rescan | PR 0.2 |
| Bundle history: config changes or snapshots? | Snapshot history, stated plainly in the bundle README and the history UI | PR 1.17 |

**Nothing in Phase 0 or Phase 1 is blocked by an open question.**

## Open questions blocking specific PRs

Each carries a stable `OQ-n` identifier defined in §14.2 of
[SPECS.md](./SPECS.md), and is marked inline at the PR it blocks above. Each
must be decided before that PR merges, with the decision recorded in the PR
description.

| ID | Question | Blocks |
|---|---|---|
| OQ-1 | Project-scope restore path mapping (leaning: global-only default, projects opt-in and path-mapped) | PR 2.5 |
| OQ-2 | Dotfiles-repo/symlink coexistence: refuse and warn, or co-exist | PR 2.7 |
| OQ-3 | Workflow as its own entity vs. a Skill variant | PR 2.16 (revisit, deliberately) |
| OQ-4 | Compiled artefacts inside tracked project scope | PR 2.16 onward, if compiling to project scope |
| OQ-5 | Provenance back-fill for externally installed items | PR 3.4 |
| OQ-6 | Cross-harness install targets beyond what an item declares | PR 3.2 |
| OQ-7 | Bundle captures marketplace items as content vs. provenance | PR 3.4 |
