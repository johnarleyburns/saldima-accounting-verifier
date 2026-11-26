# scenarios/multi-entity

**Status:** Implemented — `MULTI-001` (`multi-001-parent.yaml`,
`multi-001-subsidiary.yaml`) and `MULTI-002` (`multi-002-parent.yaml`,
`multi-002-subsidiary.yaml`); see `docs/plan.md` section 19 and the
scenario corpus table. This is out-of-roadmap follow-on work implemented
after Phase 7, not one of the 7 named phases in section 18.

Each file here is an ordinary, independently-loadable scenario (its own
entity, own reviewed fixtures under `expected/reviewed/`) — there is no
multi-entity scenario schema. The actual consolidation (combining an
entity pair and eliminating intercompany balances/activity) is a
separate step: see `reference/accounting/consolidation.py`,
`runner/consolidation_runner.py`, and `docs/accounting-policy.md`'s
"Multi-entity accounting and consolidation scope boundaries" section for
the consolidated fixtures and the documented scope boundaries (wholly-
owned subsidiary, cost method, no noncontrolling interest, fiscal-year-
end-only, no consolidated cash flow).
