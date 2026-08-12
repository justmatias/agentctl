# CHANGELOG


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
