# Rules as checks (written by `mstack init --makefile`).
.PHONY: lint-rules
lint-rules:
	mstack lint

# Only the files changed against the base branch; warnings fail too.
# BASE_REF overrides the base ref, STAGED=1 scans the staged files.
.PHONY: lint-rules-changed
lint-rules-changed:
	mstack lint --changed $(if $(BASE_REF),--base-ref $(BASE_REF)) $(if $(STAGED),--staged)
