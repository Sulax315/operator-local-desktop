# Decision Log

## Format

- DATE:
- DECISION:
- REASON:
- IMPACT:

## Entries

DATE: 2026-04-20  
DECISION: Workflow-first architecture  
REASON: Prevent agent drift and maintain control  
IMPACT: Predictable, testable system

DATE: 2026-04-20  
DECISION: Local-first runtime  
REASON: Privacy + corporate constraints  
IMPACT: No SaaS dependency

DATE: 2026-04-20  
DECISION: Phase 2 deterministic workflow runner + registry enforcement  
REASON: Keep execution bounded, repeatable, and auditable before adding agentic autonomy  
IMPACT: Workflows become executable objects with enforced artifact contracts and CI validation

DATE: 2026-04-20  
DECISION: Digest-strict registry snapshot pinning for contract_version 1.1.0+ completed runs  
REASON: Prevent quiet reinterpretation of historical “completed” runs when registry bytes evolve  
IMPACT: Registry edits become explicit compatibility events; pinned runs are audit-stable

DATE: 2026-04-20  
DECISION: Formalize registry compatibility policy + global response envelope as immediate governance follow-ons  
REASON: Code behavior moved ahead of written operating rules; non-run surfaces still risk chat-like drift  
IMPACT: Controlled evolution policy + Phase 3 contract surface becomes unambiguous

DATE: 2026-04-20  
DECISION: Phase 3 hardening begins at `contract_version: 1.2.0` with CI-blocking envelope artifacts  
REASON: Prevent non-run/chat drift while keeping legacy runs stable under older contract lines  
IMPACT: `scripts/run_workflow.py` emits canonical envelope outputs; `scripts/validate_operator_run.py` fails CI if missing/invalid

DATE: 2026-04-21  
DECISION: Promote Phase 3 to **COMPLETE**  
REASON: All operator-facing wrappers in `scripts/operator_entrypoints.json` are either `wrapped` (canonical `operator_envelope` delegation) or explicitly `internal_only`; inventory contains **no** `active_unwrapped` entries; CI coverage bar and `scripts/check_operator_entrypoints.py` enforce delegation; snapshot, financial, and weekly guarded cycles emit durable `_operator_surface` envelope trees alongside workflow runner and CI emitter.  
IMPACT: Phase 3 is closed for narrative purposes; further wrapper work is regression-only or applies when **new** operator-facing paths are introduced.

DATE: 2026-04-21  
DECISION: Classify `make operator-init-run` / `scripts/init_operator_run.py` as **scaffolding-only** (`internal_only` in inventory)  
REASON: Init creates run directory skeleton and manifest template; it is not an operator completion surface and must not be mistaken for envelope-bearing operator output.  
IMPACT: Not counted toward Phase 3 envelope debt; no requirement to wrap init with a response envelope.

DATE: 2026-04-21  
DECISION: Any **new** operator-facing executable path must land in `scripts/operator_entrypoints.json` and satisfy the same wrapper rules (canonical envelope for completion surfaces) before being considered contract-compliant  
REASON: Prevents post–Phase-3 drift and bypass of the earned control model.  
IMPACT: New CLIs or Make targets are inventory-first; CI bar is extended when new wrapped surfaces are added.

DATE: 2026-04-21  
DECISION: **Phase 5 operational workflow pattern** — new weekly-used deterministic workflows must follow the **`wf_compare_markdown`** operational shape (registry entry, bounded inputs, deterministic handler, required artifacts including `outputs/runner.json` and envelope when run via `run_workflow.py`, integration test `init → run → validate`, ugly-input smoke) unless a **documented exception** is approved in this decision log.  
REASON: Prevents one-off workflow styles that pass validation but fracture operator habits and downstream tooling.  
IMPACT: `wf_compare_markdown` is the reference template; `wf_financial_markdown_delta` and `wf_extract_risk_lines` conform to the same runner and validation path.

DATE: 2026-04-21  
DECISION: **Phase 5 initial completion bar** — at least three weekly-used deterministic workflows with stable minimal JSON contracts (`schema_version: "1.0"` on `wf_compare_markdown`, `wf_extract_risk_lines`, `wf_financial_markdown_delta`), integration tests, and one ugly-input test per workflow; **no Phase 4 bounded broker** until those three prove repeated operational value.  
REASON: Earn agent/broker machinery only after the workflow layer carries real weekly pressure.  
IMPACT: Third workflow is `wf_financial_markdown_delta` (financial materiality lines from markdown diffs); risk extraction tightened (`extraction_rules_id: risk_lines_v2`).

DATE: 2026-04-21  
DECISION: Freeze **minimal structured_output fields** for the first three operational workflows before adding a fourth (`schema_version`, `workflow`, compare/financial geometry fields, risk `matches`/`match_count`/`truncated`/`extraction_rules_id`, financial `material_diff_*` / `signal_pattern_id`).  
REASON: Downstream tooling needs predictable JSON, not ad-hoc blobs.  
IMPACT: Handlers document `PHASE5_OPERATIONAL_OUTPUT_SCHEMA` in `scripts/operator_workflows/handlers.py`; extend only with intent and tests.

DATE: 2026-04-21  
DECISION: **Phase 5 evaluation + regression gate** — curated corpus under `build_control/operator_local/phase5_eval_corpus/`, expectations in `phase5_eval_manifest.json`, runner `scripts/run_phase5_eval_pack.py`, and unittest `scripts/tests/test_phase5_eval_regression.py` are **mandatory** before expanding workflow count or proposing Phase 4 broker work.  
REASON: Weekly usefulness and heuristic stability must be evidenced; a broker would only mask weak signal.  
IMPACT: **Reject** Phase 4 broker proposals until eval/regression stays green and operator usefulness notes are refreshed when heuristics change (`signal_pattern_id` now `financial_markdown_v3`: confidence floor splits **primary** vs **audit-only** queues; numeric-shaped reinforcement; engagement-metric pollution guard).
