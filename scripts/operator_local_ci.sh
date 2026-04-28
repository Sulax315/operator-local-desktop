#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-/srv/operator-stack-clean}"
RUNS_DIR="${ROOT_DIR}/runs"
RUN_GLOBS=("${RUNS_DIR}"/test_*)

if [ "${#RUN_GLOBS[@]}" -eq 0 ] || [ ! -d "${RUN_GLOBS[0]}" ]; then
  echo "No run directories matching ${RUNS_DIR}/test_*"
  exit 1
fi

echo "[1/7] Validate run contracts"
for run_dir in "${RUNS_DIR}"/test_*; do
  python3 "${ROOT_DIR}/scripts/validate_operator_run.py" --run-dir "${run_dir}"
done

echo "[2/7] Run unit tests"
python3 -m unittest discover -s "${ROOT_DIR}/scripts/tests" -p "test_*.py"

echo "[2.5/7] Run full regression gate"
python3 "${ROOT_DIR}/scripts/run_full_regression.py"

echo "[3/7] Validate policy allowlist"
for run_dir in "${RUNS_DIR}"/test_*; do
  python3 "${ROOT_DIR}/scripts/check_operator_policy.py" --run-dir "${run_dir}"
done

echo "[4/7] Build run index"
python3 "${ROOT_DIR}/scripts/build_run_index.py" --runs-root "${RUNS_DIR}" --output "${RUNS_DIR}/index.json"

echo "[5/7] Evaluate phase gate (non-blocking)"
set +e
python3 "${ROOT_DIR}/scripts/check_phase1_gate.py" --runs-root "${RUNS_DIR}" --output "${RUNS_DIR}/phase1_gate_report.json"
GATE_EXIT=$?
set -e
echo "Phase gate exit code: ${GATE_EXIT}"

echo "[6/7] Build health report"
python3 "${ROOT_DIR}/scripts/operator_local_health_report.py" --index "${RUNS_DIR}/index.json" --gate "${RUNS_DIR}/phase1_gate_report.json" --output "${RUNS_DIR}/operator_local_health_report.md"

echo "[7/7] Emit CI operator surface summary (Phase 3 envelope)"
python3 "${ROOT_DIR}/scripts/operator_emit_ci_summary.py" --repo-root "${ROOT_DIR}" --force
python3 "${ROOT_DIR}/scripts/check_operator_entrypoints.py" --repo-root "${ROOT_DIR}"
python3 "${ROOT_DIR}/scripts/validate_operator_run.py" --run-dir "${RUNS_DIR}/_operator_surface/ci_last"

echo "Operator Local CI checks completed"
