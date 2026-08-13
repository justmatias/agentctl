# CHANGELOG


## v4.0.0 (2026-08-13)

### Features

- Breaking change detected [skip ci]
  ([`b2fa9b4`](https://github.com/justmatias/agentctl/commit/b2fa9b47c4e9dfb7336d36aa1c02852fc0f12fbf))

- **core**: Add core service skeleton and app/CLI wiring (#19)
  ([#12](https://github.com/justmatias/agentctl/pull/12),
  [`4314b1c`](https://github.com/justmatias/agentctl/commit/4314b1ccf0fda61803273db81bc0068f3120067f))

* feat(core): add core service skeleton and app/CLI wiring

CoreService (agentctl/core/service.py) is the framework-agnostic orchestration seam from SPECS.md
  §9: it owns an AdapterRegistry and a Database, with just enough behavior (registered_sources) to
  prove the wiring works. Detection logic — inventory, drift, conflicts — plugs in here starting
  Phase 1.

FastAPI app skeleton (agentctl/app.py) with a /health endpoint, wired to the existing
  agentctl/injections/ DI pattern via a new CoreService binding (agentctl/injections/core.py);
  production binds a real SQLite DB under ~/.agentctl/, tests bind an in-memory one.
  agentctl/main.py now boots this app on 127.0.0.1:8000 via uvicorn instead of printing a
  placeholder.

CLI entry point (agentctl/cli.py, wired as the `agentctl` console script) scaffolds the full planned
  surface — status, why, project add/list/remove, snapshot, restore, ui — as stubs behind a shared
  --json flag; no real subcommand logic yet.

Moves `inject` from dev-only to a real dependency (agentctl/injections now runs in production, not
  just in tests) and switches setuptools to package auto-discovery, since an explicit single-package
  list would have silently dropped every subpackage added since PR 0.1 from a real (non-editable)
  install.

ROADMAP.md PR 0.5.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

* fix(core): address automated review feedback

- Bind CoreService with bind_to_constructor instead of bind_to_provider, so it's a lazy
  process-lifetime singleton instead of re-running production_core_service()/test_core_service()
  (and opening a fresh, never-closed sqlite3 connection, and resetting the AdapterRegistry) on every
  inject.instance(CoreService) call. - CLI --json output now uses json.dumps instead of an f-string,
  so command/path/key values containing a quote or backslash no longer produce invalid JSON. - Add
  logging: CLI command dispatch and server startup. - Add a tests/core/conftest.py `database`
  fixture (matching tests/storage/conftest.py's pattern, closing the connection in a finally)
  instead of constructing Database(":memory:") inline and never closing it.

* fix(core): apply code review findings on PR #12

- Fix collection-breaking import: NullAdapter lives in agentctl.adapters.fake, not
  agentctl.adapters.testing. - Flatten TestXxx test classes in test_app.py, test_cli.py, and
  test_service.py into module-level functions, matching the no-test-classes convention applied
  elsewhere in tests/. - Log directory creation in production_core_service() so first-run setup of
  ~/.agentctl is visible in logs, matching other state-changing operations in the codebase. - Spell
  out the abbreviated `db` local as `database` in the database fixture.

* fix(injections): drop unused sample injection scaffold, hoist database fixture

The sample.py DI scaffold was only ever a template for core.py and had no remaining callers. The
  database fixture was duplicated across tests/core/conftest.py and tests/storage/conftest.py; hoist
  it to the shared tests/conftest.py since both suites need it.

* refactor(api): extract FastAPI app into api/ package with routers

Move the app factory into agentctl/api/app.py and split the /health route into
  agentctl/api/routers/health.py, mirrored by tests/api/ and tests/api/routers/. Drop the DI-wiring
  assertions from the old tests/test_app.py — they duplicated coverage the app/router split doesn't
  need — and move the shared TestClient and CliRunner setup out of test bodies into conftest
  fixtures (api_client, cli_runner).

* refactor(cli): inline not-yet-implemented stubs, drop helper indirection

Replace the shared _not_yet_implemented() helper with a direct typer.echo() (json- or text-shaped
  per --json) in each command body, and drop the incidental logger.info() call — these are stubs
  with no real behavior yet, not state-changing ops worth logging.

* fix(core): remove module docstrings, use absolute imports in api/app.py

Address PR review feedback: drop the module docstrings added in this PR and replace the
  parent-relative imports in api/app.py with absolute agentctl.* imports, keeping the single-dot
  sibling import.

---------

Co-authored-by: Claude Sonnet 5 <noreply@anthropic.com>


## v3.1.0 (2026-08-12)

### Features

- **adapters**: Add source adapter protocol and registry
  ([#11](https://github.com/justmatias/agentctl/pull/11),
  [`2a8b198`](https://github.com/justmatias/agentctl/commit/2a8b198ecc6cbf77fdce75f1c114909c36de4750))

* feat(adapters): add source adapter protocol and registry

SourceAdapter protocol capturing the six adapter responsibilities from SPECS.md §9: locate global
  config, locate project config, parse to canonical shape, serialize back to native format, report
  an ordered precedence chain, and declare capabilities. Walk-up behavior and merge semantics (§7.9)
  are exposed per extension type via a dedicated method rather than hardcoded, since different
  extension types within the same harness can walk up differently. AdapterCapabilities declares
  extension types, scopes, and workflow target forms (the last unused until Phase 2 but declared now
  per the adapter-driven capability matrix in §7.12.2).

AdapterRegistry provides register/get/list/unregister so adding a harness never touches core logic.
  NullAdapter (agentctl/adapters/testing.py) is a protocol-conformant no-op adapter for exercising
  the registry and contract end-to-end without any real harness.

ROADMAP.md PR 0.4.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

* fix(adapters): address automated review feedback

- AdapterRegistry.register() now checks isinstance(adapter, SourceAdapter) and raises TypeError for
  malformed adapters, instead of accepting anything and failing later with a confusing
  AttributeError. - register() now validates adapter.source == adapter.capabilities.source, so a
  future adapter can't register with the two out of sync. - register()/unregister() now log: info on
  a fresh registration or an unregister, warning when silently replacing an already-registered
  adapter for the same Source. - NullAdapter's unused-argument static methods use
  underscore-prefixed parameter names instead of a `del arg; return ...` shape.

* fix(adapters): align with main conventions after rebase

Rebasing onto main (domain/storage/writes now squash-merged as #8/#9/#10) surfaces conventions the
  original commits predate:

- Drop module docstrings from adapters/* to match every other module. -
  tests.factories.make_extension no longer exists on main (factories.py now only builds DB-saved
  records); switch to the extension_factory polyfactory fixture used everywhere else for in-memory
  instances. - Flatten TestXxx test classes into module-level test functions, matching the
  no-test-classes convention now applied throughout tests/. - Cover AdapterRegistry.register()'s two
  error branches (non-conforming adapter, source/capabilities.source mismatch) to restore 100%
  coverage on the new code.

* fix(adapters): follow conftest fixture conventions in adapter tests

Move MismatchedSourceAdapter out of test_registry.py into conftest.py (dropping its leading
  underscore) behind a fixture, add a shared null_adapter fixture, and collapse test_protocol.py's
  tautological no-op-method assertions into a single smoke test.

---------

Co-authored-by: Claude Sonnet 5 <noreply@anthropic.com>


## v3.0.0 (2026-08-12)

### Features

- Breaking change detected [skip ci]
  ([`a130c5a`](https://github.com/justmatias/agentctl/commit/a130c5a3e74dbdae45c1b185ddfd3ec6066adda3))

- **storage**: Add SQLite storage layer for orchestration metadata
  ([#9](https://github.com/justmatias/agentctl/pull/9),
  [`caab714`](https://github.com/justmatias/agentctl/commit/caab71495a6dd7c4cc1e0784fa4d686a5767ae78))

* feat(storage): add SQLite storage layer for orchestration metadata

Embedded DB with a linear versioned-DDL migration runner, repository Protocols the core service will
  depend on (so storage stays swappable and mockable), and SQLite-backed implementations for every
  Phase-0 model (Extension, Binding, Conflict, Project, PrecedenceChain).

Per SPECS.md §9, the DB holds orchestration metadata only — harness files stay authoritative and the
  DB is disposable, rebuildable by rescan. Since no adapter exists yet to perform a real scan (Phase
  1), that guarantee is exercised here by simulating rescan: re-inserting exactly what discovery of
  the same on-disk state would find after the DB file is deleted, and asserting only DB-only state
  (user decisions, unbound canonical records) fails to come back.

ROADMAP.md PR 0.2.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

* fix(storage): address automated review feedback

- Add a partial unique index on precedence_chains(source) WHERE project_id IS NULL, since SQLite's
  UNIQUE(source, project_id) treats NULL != NULL and previously allowed unlimited duplicate global
  chains. - Make SqlitePrecedenceChainRepository.upsert atomic: delete+insert now run inside a
  single `with self._connection:` transaction instead of composing two independently-committing
  methods, so a crash between them can no longer lose the row. - apply_migrations now wraps DDL
  application in try/except, rolling back and logging a clear "migration N failed" error instead of
  silently leaving schema_migrations unrecorded; CREATE TABLE statements are now idempotent (IF NOT
  EXISTS) so a retried migration doesn't hit "table already exists". - Add indexes on
  bindings.extension_id and conflicts.extension_id to avoid full table scans on FK lookups. -
  Replace every repository's hand-written commit() calls with `with self._connection:` transaction
  blocks, and add logging on create/update/delete/upsert/migration-apply for observability into
  storage mutations.

* fix(storage): address human review feedback on PR #9

- Remove module docstrings across the storage module (per review). - Add a generic
  SqliteRepository[ModelT] base class for the four id-keyed repositories
  (Extension/Binding/Conflict/Project), collapsing the duplicated commit+log wrapping in
  create/update/delete into one place. SqlitePrecedenceChainRepository stays separate: it's keyed by
  (source, project_id) and has upsert instead of create/update. - Fix a 3-level import in
  tests/storage/test_repositories.py to import from agentctl.storage instead of the submodule
  directly. - Simplify test_repositories.py: get/list/delete/update-mechanics are now tested once
  against the shared base (via SqliteExtensionRepository) instead of duplicated per repository; each
  repository test class keeps only its own create/update SQL round-trip plus whatever is unique to
  it. - Adapt to the upstream domain-model rebase: PrecedenceLayer is now a discriminated union
  (build ConsultedLayer directly) and tests/factories.py moved from make_extension()/make_binding()
  helpers to polyfactory fixtures (extension_factory/binding_factory).

Kept raw sqlite3 + the hand-rolled linear-migration runner as-is (no SQLAlchemy/Alembic) and
  migrations.py as a single file — the schema is small and the project has no other heavy
  dependencies yet.

* fix(storage): address second round of human review feedback on PR #9

- Remove the Database class docstring and shorten the "Phase-0" migration description to drop the
  phase reference. - Extract the schema_migrations SELECT into a named variable instead of inlining
  connection.execute() in the set comprehension. - Rename the SqliteRepository generic type var from
  ModelT to T and trim its docstring to one line. - Add a generic Repository[T] Protocol in
  repositories.py with the shared create/get/list/update/delete shape; Extension/Binding/
  Conflict/Project repositories now extend it instead of repeating the same five method signatures.
  PrecedenceChainRepository stays separate (keyed by source+project_id, not id). - Convert
  tests/storage/test_repositories.py and test_rescan_reproducibility.py from Test* classes with
  @staticmethod tests to plain module-level test_ functions, matching the rest of the test suite.

Replied inline on the three open design questions (order_by as a parameter, generic model_validate
  in _row_to_model, a service layer on top of the repositories) explaining why the current shape is
  kept for now.

* fix(storage): split sqlite_repositories.py into modules, rework storage test fixtures

- Split agentctl/storage/sqlite_repositories.py into a package with one module per concrete
  repository (base/extensions/bindings/conflicts/ projects/precedence_chains), re-exported unchanged
  from agentctl/storage/__init__.py, per reviewer follow-up on the service-layer thread. - Move
  repository instantiation and reusable entity setup out of the storage test bodies and into
  tests/storage/conftest.py fixtures: extension_repository/binding_repository/conflict_repository/
  project_repository/precedence_chain_repository, plus create_saved_extension/saved_extension,
  create_saved_binding/ saved_binding, create_saved_project, and create_consulted_layer.
  database_path is now a shared fixture too (used by test_migrations.py and
  test_rescan_reproducibility.py). - Convert test_rescan_reproducibility.py's _seed() helper into a
  proper discovered_inventory fixture instead of a plain function taking an open Database. - Convert
  tests/storage/test_migrations.py from a Test* class with @staticmethod tests to plain module-level
  test_ functions, matching the rest of the suite; use Database's context manager instead of manual
  try/finally close. - Rename the "repo"/"db" abbreviations used throughout the storage tests to
  "repository"/"database" for readability.

* fix(storage): split repository tests per module, isolate rescan seeding

- Move each repository's tests out of tests/storage/test_repositories.py into
  tests/storage/repositories/test_extensions.py, test_bindings.py, test_conflicts.py,
  test_projects.py, test_precedence_chains.py, matching the sqlite_repositories package split.
  test_repositories.py now only holds the shared SqliteRepository base's get/list/update/delete
  tests. - Replace test_rescan_reproducibility.py's monolithic _seed() with isolated per-entity
  fixtures (discovered_extension, discovered_binding, unbound_extension,
  intentionally_kept_conflict) backed by a seed_database fixture the test can close mid-test before
  deleting and reopening the file. - Use `# noqa: F401` instead of `__all__` for the re-exports in
  sqlite_repositories/__init__.py: an __all__ list here duplicated the same 5 names already listed
  in storage/__init__.py's __all__ closely enough to trip pylint's duplicate-code check, and the
  alternative (`import X as X`) trips its useless-import-alias check instead.

* fix(storage): address latest round of PR #9 review feedback

Renames sqlite_repositories/ to sqlite/ and base.py to repository.py, adds the missing __all__,
  drops the _list_order_by class attribute in favor of each repository's list() hardcoding its
  order_by when calling the shared base, simplifies _row_to_model across repositories to spread
  dict(row) instead of listing every column, and shortens the precedence chain repository's
  docstring. Test-side, replaces raw factory-callable parameters with named per-instance fixtures
  wherever a test only needed a fixed, enumerable set of created entities.

* refactor(storage): trim repository protocols to their real shapes

Drop the empty nominal subclasses (ExtensionRepository, ConflictRepository, ProjectRepository) that
  added nothing over Repository[T] — Protocols are structural and need no inheritance to be
  satisfied. Split PrecedenceChain's protocol into its own module as PrecedenceChainStore since its
  key shape and upsert semantics genuinely differ from the CRUD Repository family.

* refactor(storage): replace raw SQL with SQLAlchemy Core

Adopts SQLAlchemy Core as a thin layer over the sqlite storage module, fixing the correctness bugs
  the raw-SQL approach carried:

- Migrations run as one real transaction per migration (via the pysqlite transactional-DDL recipe),
  so a failure partway through no longer leaves earlier CREATE TABLE statements committed. -
  list()'s order_by is resolved against the table's actual columns instead of being interpolated
  into SQL, closing off injection. - extensions.id is now a real ON DELETE CASCADE foreign key for
  bindings/conflicts, instead of an uncaught IntegrityError on delete. - JSON columns
  (canonical_config, binding_ids, detected_sources, layers) serialize automatically, removing the
  hand-written json.dumps/loads and column-list duplication across repositories. - A shared
  write_in_transaction() helper replaces the duplicated transaction+logging pattern between
  SqliteRepository and SqlitePrecedenceChainRepository.

Also merges the standalone PrecedenceChainStore protocol module back into repositories.py, adds a
  ConflictFactory/precedence-chain fixture following the existing polyfactory conventions, and
  splits the rescan-reproducibility test's fixtures into their own conftest.py.

* refactor(storage): fold transaction-write helper into a shared base class

`write_in_transaction` lived in its own module only because SqliteRepository and
  SqlitePrecedenceChainRepository both needed it despite not sharing a CRUD contract. Extract
  SqliteConnectionRepository as their common base instead, and drop the "..".-relative schema
  imports across sqlite/ in favor of absolute agentctl.storage.schema imports.

* refactor(tests): split polyfactory-based and custom storage factories

tests/factories.py mixed two different kinds of factory: polyfactory ModelFactory subclasses and the
  hand-written create_saved_* fixtures that build-and-persist entities through a repository. Move
  the former to tests/polyfactory.py (its actual role) and repurpose tests/factories.py for the
  latter, pulled out of tests/storage/conftest.py to shrink it down to just the
  database/repository/instance fixtures.

* refactor(storage): integrate SQLModel and collapse repositories into one generic class

Row models replace the hand-written SQLAlchemy Core Table objects, so domain<->row conversion
  becomes model_dump/model_validate instead of a per-column .values() block in every repository. The
  five concrete repositories collapse into ~5-line declarations over a single generic
  SqliteRepository[DomainT, RowT], including the precedence-chain store, which previously couldn't
  share the base class at all. The on-disk schema is unchanged (verified byte-identical DDL), so
  migration v1 stays v1.

* fix(lint): resolve pylint and mypy findings from poe format

Simplify migrations' try/except (no-else-raise), suppress duplicate-code false positives in storage
  __init__ re-exports, quiet unused-argument warnings for pytest fixture/test-ordering dependencies,
  and use .scalar() instead of indexing a possibly-None Row in test_migrations.

* refactor(storage): type repository filter values, tidy sqlite internals

Replace the untyped `**filters: object` protocol with a FilterValue union so filter arguments are
  checked against what `_encode` actually handles, move `_encode` onto SqliteRepository as a static
  method, and drop the module-level `_emit_begin` helper in favor of an inline listener. Reflow the
  precedence-chain assertions that no longer fit the line length after the signature change.

* refactor(tests): register storage factory fixtures via pytest_plugins

Import-and-__all__ was only there to keep ruff's unused-import check quiet for fixtures pulled in
  purely for pytest's name-based lookup. Register tests.factories as a pytest plugin instead,
  matching how tests.polyfactory is already registered, so no re-export list is needed.

---------

Co-authored-by: Claude Sonnet 5 <noreply@anthropic.com>

- **writes**: Add safe write layer ([#10](https://github.com/justmatias/agentctl/pull/10),
  [`46f0595`](https://github.com/justmatias/agentctl/commit/46f059504fb675d3e46ad06edbf7ab6b2a6df28f))

* feat(writes): add safe write layer

Atomic write primitive (temp file + os.replace) so a reader never sees a partial write and a failure
  before the replace leaves the original untouched; a session-scoped RollbackIndex that timestamps a
  backup before an overwrite and can restore one file or undo the whole session; and a key-scoped
  JSON merge helper that updates only the caller-specified top-level keys, leaving unrelated keys
  and ordering in a shared file like settings.json untouched.

Pure filesystem utility — no dependency on the domain model or storage layer introduced in earlier
  Phase-0 PRs.

ROADMAP.md PR 0.3.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

* fix(writes): address automated review feedback

- RollbackIndex.backup() now writes the backup via atomic_write instead of a plain write_text, so a
  process kill mid-write can no longer leave a truncated backup that restore()/restore_all() would
  silently write back over the original. - atomic_write now preserves an existing file's permission
  bits before os.replace, instead of silently downgrading them to mkstemp's 0600 default. -
  merge_json_keys now raises a clear TypeError when the JSON root isn't an object, instead of a bare
  AttributeError from dict.update; covered by a new test. - Deduplicate the two datetime.now(UTC)
  calls in backup() into one. - Add logging (debug on the atomic_write primitive, info on
  backup/restore/restore_all/merge) for these state-changing operations.

* fix(writes): drop module docstrings, align tests with repo conventions

Remove the module docstrings in agentctl/writes/ per PR review comments — the rest of the codebase
  doesn't use them. Also convert tests/writes/ from class-grouped tests to flat test_* functions and
  extract the repeated target/RollbackIndex setup into tests/writes/conftest.py fixtures, matching
  conventions already followed elsewhere in tests/.

* refactor(writes): inline temp-write helper, extract test fixtures

Fold _write_to_temp back into atomic_write now that tests patch os.fsync directly instead of the
  helper, and move repeated write+backup and fsync-failure setup in the write tests into conftest
  fixtures.

* refactor(test): simplify backup assertion in test_repeated_backups_are_recorded_in_order

---------

Co-authored-by: Claude Sonnet 5 <noreply@anthropic.com>


## v2.1.0 (2026-08-12)

### Features

- **domain**: Add domain model ([#8](https://github.com/justmatias/agentctl/pull/8),
  [`1a43077`](https://github.com/justmatias/agentctl/commit/1a4307779b016436f6f4fd42d7ede26714a4f6ad))

* feat(domain): add Phase-0 domain model

Pydantic models for Extension, Binding, Conflict, Project, and PrecedenceChain (SPECS.md §8, v1
  subset), plus their enums and the per-extension-type canonical config shapes (mcp_server,
  memory_file, skill). Cross-field validators enforce the §7.2/§7.10 decisions inline:
  canonical_config must match Extension.type, a Conflict's resolved_binding_id is set iff resolution
  is source_chosen, and an unconfirmed PrecedenceLayer carries no order_rank and never resolves.

No filesystem or DB code — ROADMAP.md PR 0.1.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

* fix(domain): address automated review feedback

- Extension canonical-config validator now raises ValueError instead of a raw KeyError when a future
  ExtensionType has no registered config type, keeping the failure mode consistent with the rest of
  the validator (wraps into pydantic's ValidationError). - Extract a shared `extension` fixture in
  tests/domain/conftest.py for tests that only need extension.id, instead of re-invoking
  make_extension() with no overrides in four places. - Extract an assert_round_trips() helper and
  use it for the five JSON round-trip assertions that were copy-pasted across test classes.

* chore(config): clean up comments and improve code readability

* chore: simplify type validation and improve docstrings

* fix(domain): address human review feedback on PR #8

- Extension.type is now a computed field derived from canonical_config's own discriminator literal,
  so Pydantic rejects a mismatched config natively instead of a hand-rolled cross-field validator. -
  PrecedenceLayer becomes a discriminator union of ConsultedLayer / NotConsultedLayer /
  UnconfirmedLayer, so the order_rank/resolves invariants are enforced structurally instead of via
  optional fields plus manual raises. - Conflict's resolution/resolved_binding_id check collapses to
  a single if with a ternary message. - Tests: dropped the class-based layout and the ad hoc
  `extension` fixture, replaced the parametrize-on-test pattern with a parametrized fixture, and
  switched tests/factories.py to polyfactory (registered via the pytest plugin) instead of
  hand-rolled builder functions.

* fix(domain): address human review feedback on PR #8 (round 2)

- Move the canonical_config fixture from tests/domain/test_models.py into tests/domain/conftest.py —
  fixtures belong in conftest, not in test modules. - Give the polyfactory fixtures explicit names
  via @register_fixture(name=...) instead of relying on the implicit camel-to-snake conversion. -
  Add polyfactory to the pylint/mypy pre-commit hooks' additional_dependencies, matching how
  loguru/pydantic/pytest are already declared there. This let mypy actually resolve
  ModelFactory.build's real signature for the first time and surfaced a latent type error in
  agentctl/utils/settings.py (unpacking a dict[str, str] against build's `factory_use_construct:
  bool` keyword param), previously hidden because polyfactory was invisible to the hook. Fixed by
  typing the overrides dict as dict[str, Any], which is the honest type for values that get
  validated dynamically by pydantic — and dropped the type: ignore this made unused.

---------

Co-authored-by: Claude Sonnet 5 <noreply@anthropic.com>


## v2.0.0 (2026-08-12)

### Features

- Breaking change detected [skip ci]
  ([`0ea6a8a`](https://github.com/justmatias/agentctl/commit/0ea6a8a2740e8787e8150901b52e393f1129770d))


## v1.0.0 (2026-08-10)

### Chores

- Add uv.lock
  ([`c81e2d7`](https://github.com/justmatias/agentctl/commit/c81e2d73707b14d209c449d3574b1a95535bab9b))

- Project scaffold for agentctl
  ([`71056fd`](https://github.com/justmatias/agentctl/commit/71056fd4f5e5740dadb293d1854de8bdac11a102))

### Documentation

- Add phased roadmap and expand README
  ([`5ecc9d3`](https://github.com/justmatias/agentctl/commit/5ecc9d3926920d0614579f35b102478cd80cbeec))

Move SPECS.md under docs/, add docs/ROADMAP.md splitting delivery into PR-sized units across three
  phases, and rewrite README.md to describe the tool as specified.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>

- Resolve open questions and mark the rest as OQ-n
  ([#7](https://github.com/justmatias/agentctl/pull/7),
  [`09f27f2`](https://github.com/justmatias/agentctl/commit/09f27f2f4bb846c5e34a1c8c458c93f40d4add88))

* docs: resolve six open questions and mark the rest as OQ-n

Settles every open question blocking Phase 0 and Phase 1, writes each decision into the spec section
  that governs it, and gives the remaining questions stable identifiers referenced at their point of
  blockage.

Decisions (SPECS §14.1): - Nested registered projects: registration scopes tracking, not precedence.
  The stack mirrors real harness walk-up whether or not an ancestor is registered; walk-up semantics
  are adapter-reported. - Memory files: independent + diff in v1. The composed canonical block
  becomes a Phase 2 opt-in (new subsection 2g, PRs 2.26-2.28), gated on verified per-harness load
  semantics and reversible via markers. - Unverified `.agents` support: shown as `unconfirmed`,
  unranked and excluded from resolution - it can never win nor demote a confirmed layer. -
  Memory-file conflicts: normalized text compare yields an informational `divergent` sync state; no
  Conflict records for prose. - Source of truth: harness files are authoritative, the DB holds
  orchestration metadata only, is disposable, and is rebuildable by rescan. - Bundle history:
  snapshot history, stated plainly in the generated bundle README and the history UI; no feature may
  assume per-change commits.

Model changes: SyncState gains `divergent`, Conflict gains `resolution`, and PrecedenceChain layers
  gain `status`, `origin`, and `resolves`. Renamed the "intentionally divergent" conflict resolution
  to `keep_both_intentionally` so it no longer collides with the new `divergent` sync state (README
  wording updated to match).

Remaining questions are numbered OQ-1..OQ-7 in SPECS §14.2 and marked inline at each blocking PR in
  the roadmap. Nothing in Phase 0 or Phase 1 is blocked by an open question.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>

* ci: replace pipx with uvx for semantic-release and pycracks

The runner's preinstalled pipx requires uv>=0.9.17, but the setup-python-env composite action pins
  uv to 0.9.11 and puts it first on PATH, so every `pipx run` in the breaking-changes job failed the
  backend version check.

uv is already installed by the setup action and the security job already uses uvx, so drop the
  second package manager instead of bumping the pin.

* chore(config): update pre-commit hooks

---------

Co-authored-by: Claude Opus 5 <noreply@anthropic.com>

Co-authored-by: github-actions[bot] <github-actions[bot]@users.noreply.github.com>

### Features

- Breaking change detected [skip ci]
  ([`30791fb`](https://github.com/justmatias/agentctl/commit/30791fb81b73599488c118ca9377f22446cd9cbf))
