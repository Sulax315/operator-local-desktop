PYTHON ?= python3

.PHONY: operator operator-init-run operator-validate-run operator-phase1-gate operator-run-index operator-test operator-run-workflow operator-ci-summary operator-check-entrypoints operator-regression

operator:
	@if [ -z "$(CMD)" ]; then echo "Usage: make operator CMD='compare a.md b.md'"; exit 1; fi
	$(PYTHON) scripts/operator_run.py $(CMD)

operator-init-run:
	@if [ -z "$(RUN_ID)" ]; then echo "Usage: make operator-init-run RUN_ID=test_004 [WORKFLOW=manual_task]"; exit 1; fi
	$(PYTHON) scripts/init_operator_run.py --run-id "$(RUN_ID)" --workflow-name "$(or $(WORKFLOW),manual_task)" --phase "Phase 1"

operator-validate-run:
	@if [ -z "$(RUN_DIR)" ]; then echo "Usage: make operator-validate-run RUN_DIR=runs/test_001"; exit 1; fi
	$(PYTHON) scripts/validate_operator_run.py --run-dir "$(RUN_DIR)"

operator-phase1-gate:
	$(PYTHON) scripts/check_phase1_gate.py --runs-root runs --output runs/phase1_gate_report.json

operator-run-index:
	$(PYTHON) scripts/build_run_index.py --runs-root runs --output runs/index.json

operator-test:
	$(PYTHON) -m unittest discover -s scripts/tests -p "test_*.py"

operator-run-workflow:
	@if [ -z "$(RUN_DIR)" ] || [ -z "$(WORKFLOW)" ]; then echo "Usage: make operator-run-workflow RUN_DIR=runs/test_005 WORKFLOW=wf_summarize_markdown INPUTS='docs/a.md'"; exit 1; fi
	$(PYTHON) scripts/run_workflow.py --workflow "$(WORKFLOW)" --run-dir "$(RUN_DIR)" $(foreach f,$(INPUTS),--input "$(f)") --force

operator-ci-summary:
	$(PYTHON) scripts/operator_emit_ci_summary.py --force

operator-check-entrypoints:
	$(PYTHON) scripts/check_operator_entrypoints.py --repo-root "$(CURDIR)"

operator-regression:
	$(PYTHON) scripts/run_full_regression.py
