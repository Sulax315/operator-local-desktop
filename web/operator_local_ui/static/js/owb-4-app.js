/**
 * owb-4-app.js — Load order: 4 of 4 (last). Depends on functions from owb-1..3 in global scope.
 * Workspace init, report builder POST, result workspace, assistant query plumbing, run history, driver UI.
 */
function scrollPrimaryAnalysisOutputIntoView() {
  const embed = document.getElementById("financial-workbench-embed");
  if (embed && embed.querySelector(".financial-workbench")) {
    embed.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  const cmd = document.getElementById("fin-command-center");
  const surface = document.getElementById("financial-command-surface");
  if (
    cmd &&
    surface &&
    !surface.hasAttribute("hidden") &&
    !cmd.hasAttribute("hidden")
  ) {
    cmd.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  const rw = document.getElementById("result-workspace");
  const fs = document.getElementById("financial-signals");
  const runHidden =
    !rw || rw.classList.contains("hidden") || rw.getAttribute("aria-hidden") === "true";
  if (!runHidden) {
    const hero = document.getElementById("answer-hero");
    const target = hero || rw;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (fs && !fs.hasAttribute("hidden") && fs.innerHTML && fs.innerHTML.trim()) {
    const parent = fs.closest("#financial-command-surface") || fs;
    parent.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

async function runReportBuilderGenerate() {
  const statusEl = document.getElementById("status");
  const sel = document.getElementById("analysis-type-select");
  const runBtn = document.getElementById("generate-signals-btn");
  if (!sel || !sel.value) return;
  const paths = Array.from(reportPathSelection);
  const body = {
    report_builder: true,
    contract: "generate_financial_signals",
    task_payload: {
      project_id: reportBuilderProjectId,
      analysis_type: sel.value,
      selected_paths: paths,
    },
    workspace_root: operatorWorkspaceRoot,
    query: "Report Builder",
  };
  if (statusEl) statusEl.textContent = "Running analysis…";
  if (runBtn) runBtn.setAttribute("aria-busy", "true");
  try {
    const resp = await fetch("/api/local/assistant/task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || data.message || "Request failed");
    if (data.status === "failed" || data.status === "no_candidates" || data.status === "insufficient_data") {
      if (statusEl) statusEl.textContent = data.answer || data.status;
      return;
    }
    const fs = data.result && data.result.financial_signals;
    if (fs) renderFinancialSignalsBlock(fs);
    let runLoaded = true;
    if (data.result && data.result.run_payload && data.result.run_payload.run_id) {
      runLoaded = await loadRunFromHistory(String(data.result.run_payload.run_id));
    }
    if (statusEl && runLoaded) statusEl.textContent = "Analysis ready.";
    requestAnimationFrame(() => scrollPrimaryAnalysisOutputIntoView());
  } catch (e) {
    if (statusEl) statusEl.textContent = (e && e.message) || "Error";
  } finally {
    if (runBtn) runBtn.removeAttribute("aria-busy");
  }
}

async function postWorkspaceScan() {
  const idxEl = document.getElementById("project-library-indexed");
  if (idxEl) idxEl.textContent = "Scanning…";
  try {
    const resp = await fetch("/api/local/workspace/scan", { method: "POST" });
    const body = await resp.json();
    if (!resp.ok) throw new Error(body.detail || "scan failed");
    const n = body.rows_indexed != null ? body.rows_indexed : 0;
    let line = `Indexed ${n} workbook(s)`;
    if (body.cap_reached) {
      const ex = body.files_examined != null ? body.files_examined : "";
      line += ` Showing first ${ex} Excel files (scan limit).`;
    }
    if (idxEl) idxEl.textContent = line;
  } catch (e) {
    if (idxEl) idxEl.textContent = (e && e.message) || "Scan failed";
  } finally {
    initOperatorWorkspace();
  }
}

async function initOperatorWorkspace() {
  try {
    const resp = await fetch("/api/local/workspace");
    const payload = await resp.json();
    operatorWorkspaceRoot = payload.workspace_root || "";
    const r = payload.readiness || {};
    const wb = Number(r.workbook_count || 0);
    const nIdx = Number(
      (payload.project_index && payload.project_index.indexed_workbooks) != null
        ? payload.project_index.indexed_workbooks
        : 0
    );
    renderProjectLibrary(payload);
    if (r && payload.resolvable !== false && (wb > 0 || nIdx > 0)) {
      const rh = document.getElementById("report-selector-hint");
      if (rh && !String(reportBuilderProjectId || "").trim()) {
        rh.textContent = "Start with Step 1 in the project library, then your reports will appear in this table.";
      }
    }
  } catch (_err) {
    renderProjectLibrary({ resolvable: false, message: "Failed to load workspace settings." });
  }
}

async function runOperatorTask(query, options = {}) {
  const effectiveQuery = String(query || "").trim();
  if (!effectiveQuery) return;
  const statusEl = document.getElementById("status");
    statusEl.textContent = "Working…";
  const context = {
    run_id: operatorRunId(),
    selected_files: [],
    target_file: "",
    search_query: effectiveQuery,
    selected_pair_id: operatorSelectedPairId,
    last_confirmed_pair: lastConfirmedPair,
    preferred_report_family: preferredReportFamily,
  };
  let taskPayload = null;
  try {
    const resp = await fetch("/api/local/assistant/task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workspace_root: operatorWorkspaceRoot,
        query: effectiveQuery,
        context,
        confirm: !!options.confirm,
      }),
    });
    const payload = await resp.json();
    taskPayload = payload;
    if (!resp.ok) throw new Error(
      (payload && (payload.detail || payload.message)) || JSON.stringify(payload) || "Request failed"
    );
    renderOperatorTaskEntry(payload);
    const inlineWf = document.getElementById("operator-inline-workflow");
    const leadEl = document.getElementById("operator-workflow-lead");
    if (payload.status === "needs_confirmation") {
      pendingConfirmTask = effectiveQuery;
      renderPairDisambiguation(payload.approval || {});
      if (inlineWf) {
        inlineWf.classList.remove("hidden");
        inlineWf.removeAttribute("hidden");
      }
      if (leadEl) {
        leadEl.textContent = payload.answer || "Review the staging entry, then confirm to run the compare.";
      }
      const badge = document.getElementById("operator-workflow-badge");
      const reqSel = payload.approval && payload.approval.pairing && payload.approval.pairing.requires_operator_selection;
      if (badge) badge.textContent = reqSel ? "Choose a workbook pair" : "Compare ready to run";
      statusEl.textContent = "Staged: confirm the compare in the bar above the transcript.";
    } else {
      pendingConfirmTask = null;
      if (inlineWf) {
        inlineWf.classList.add("hidden");
        inlineWf.setAttribute("hidden", "hidden");
      }
      if (leadEl) leadEl.textContent = "";
      const meta = document.getElementById("pair-disambiguation-meta");
      if (meta) meta.textContent = "";
      const pHost = document.getElementById("pair-disambiguation-options");
      if (pHost) pHost.innerHTML = "";
      operatorSelectedPairId = "";
      if (payload.status === "completed") {
        statusEl.textContent = "Done.";
      } else if (payload.status === "needs_run") {
        statusEl.textContent = "Run a compare first, then repeat this action.";
      } else if (payload.status === "needs_setup") {
        statusEl.textContent = "Workspace is not ready; scan the approved root, then try again.";
      } else if (payload.status === "no_candidates") {
        statusEl.textContent = "Add workbooks or adjust pairing, then retry.";
      } else if (payload.status === "failed") {
        statusEl.textContent = "Action did not complete. See below.";
      } else {
        statusEl.textContent = "Ready.";
      }
    }
    const memoryUpdate = payload.result && payload.result.memory_update ? payload.result.memory_update : null;
    if (memoryUpdate && typeof memoryUpdate === "object") {
      if (memoryUpdate.last_confirmed_pair) {
        lastConfirmedPair = memoryUpdate.last_confirmed_pair;
      }
      if (memoryUpdate.preferred_report_family) {
        preferredReportFamily = String(memoryUpdate.preferred_report_family || "");
      }
    }
    if (payload.result && payload.result.run_payload && payload.result.run_payload.run_id) {
      const rid = payload.result.run_payload.run_id;
      window.__postRenderDriverFocus = {
        contract: (payload.task && payload.task.contract) || "",
        result: payload.result,
        runId: rid,
      };
      loadRunFromHistory(rid);
    } else {
      window.__postRenderDriverFocus = null;
    }
  } catch (err) {
    statusEl.textContent = `Request did not complete: ${err.message || err}`;
    renderOperatorTaskEntry({
      task: { query: effectiveQuery },
      status: "error",
      answer: err.message || String(err),
      result: {},
      trace: [],
    });
  } finally {
    const c = (taskPayload && taskPayload.task && taskPayload.task.contract) || "";
    if (
      (c === "scan_workspace" || c === "list_projects") &&
      taskPayload &&
      (taskPayload.status === "completed" || taskPayload.status === "failed")
    ) {
      void initOperatorWorkspace();
    }
  }
}

function setupOperatorAssistantSurface() {
  const form = document.getElementById("operator-task-form");
  const input = document.getElementById("operator-task-input");
  const chips = document.getElementById("operator-intent-chips");
  const confirmBtn = document.getElementById("confirm-compare-btn");
  if (form && input) {
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      runOperatorTask(input.value);
    });
  }
  if (chips && input) {
    chips.addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-task-query]");
      if (!btn) return;
      const q = btn.getAttribute("data-task-query") || "";
      input.value = q;
      runOperatorTask(q);
    });
  }
  const scanPl = document.getElementById("project-library-scan");
  if (scanPl) {
    scanPl.addEventListener("click", () => postWorkspaceScan());
  }
  if (confirmBtn) {
    confirmBtn.addEventListener("click", () => {
      const q = pendingConfirmTask || (input ? input.value : "");
      if (!q) return;
      runOperatorTask(q, { confirm: true });
    });
  }
  const plSearch = document.getElementById("project-library-search");
  if (plSearch) {
    plSearch.addEventListener("input", () => {
      if (lastProjectLibraryPayload) renderProjectLibrary(lastProjectLibraryPayload);
    });
  }
  const genBtn = document.getElementById("generate-signals-btn");
  if (genBtn) {
    genBtn.addEventListener("click", () => void runReportBuilderGenerate());
  }
  const aSel = document.getElementById("analysis-type-select");
  if (aSel) {
    aSel.addEventListener("change", () => {
      const b = document.getElementById("generate-signals-btn");
      if (b) b.disabled = !aSel.value;
    });
  }
}

const VIEW_FRIENDLY = {
  wf_financial_markdown_delta: "Period-over-period financial",
  wf_compare_markdown: "Text compare",
  wf_extract_risk_lines: "Line extraction (single file)",
};

function viewLabelForName(name) {
  if (!name) return "";
  return VIEW_FRIENDLY[name] || "Custom compare";
}

function fmtMoneySigned(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  const sign = v >= 0 ? "+" : "−";
  return sign + "$" + Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function fmtMoneyPlain(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  return "$" + Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function tierClass(tier) {
  const t = (tier || "").toLowerCase();
  if (t === "high") return "tier-high";
  if (t === "medium") return "tier-medium";
  if (t === "audit") return "tier-audit";
  return "tier-low";
}

function statValueClass(key, n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "";
  const v = Number(n);
  if (key === "cost") {
    return v <= 0 ? "positive" : "negative";
  }
  return v >= 0 ? "positive" : "negative";
}

function isStructuredFinancial(so) {
  if (!so) return false;
  const ex = so.extraction_confidence;
  if (ex && ex.rollup) return true;
  if (so.summary_deltas && Object.keys(so.summary_deltas).length) return true;
  const m = so.material_diff_items && so.material_diff_items[0];
  return !!(m && "prior_value" in m);
}

function profitToneClass(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "";
  return Number(n) >= 0 ? "positive" : "negative";
}

function numOrNull(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return null;
  return Number(v);
}

/** Display-only: current_budget − original_budget; maps to current_value / prior_value. */
function rowBudgetDeltaValue(row) {
  if (!row) return 0;
  const orig = numOrNull(row.prior_value);
  const cur = numOrNull(row.current_value);
  if (orig != null && cur != null) return cur - orig;
  const d = numOrNull(row.delta);
  return d != null && !Number.isNaN(d) ? d : 0;
}

function rowBudgetDeltaPct(row) {
  const dv = rowBudgetDeltaValue(row);
  const orig = numOrNull(row.prior_value);
  if (orig == null || orig === 0) return null;
  return dv / orig;
}

function hasOriginalBudget(row) {
  return row && row.prior_value !== null && row.prior_value !== undefined && !Number.isNaN(Number(row.prior_value));
}

function driverRowKey(row) {
  if (!row) return "";
  return [row.category_label, row.category, row.prior_value, row.current_value, row.delta].join("|");
}

function absBudgetDelta(row) {
  return Math.abs(rowBudgetDeltaValue(row));
}

function tradeKeyFromRow(row) {
  const s = String((row && (row.category_label || row.category)) || "Other").trim();
  if (!s) return "Other";
  const code = s.match(/^(\d{1,3}(?:[.\-][\d]+)*)\b/);
  if (code) return String(code[1]).replace(/\./g, "-");
  const parts = s.split(/\s*[–-]\s*/);
  if (parts[0] && parts[0].length > 0 && parts[0].length <= 40) {
    return parts[0].trim();
  }
  const w = s.split(/\s+/)[0];
  return w && w.length > 0 ? w : "Other";
}

function fmtDeltaUsdCell(dv) {
  if (dv === null || dv === undefined || Number.isNaN(dv)) return "—";
  const n = Number(dv);
  const arrow = n > 0 ? "↑" : n < 0 ? "↓" : "";
  const cls = n > 0 ? "delta-cell delta-cell--up" : n < 0 ? "delta-cell delta-cell--down" : "delta-cell";
  const sign = n >= 0 ? "+" : "−";
  return (
    '<span class="' +
    cls +
    '"><span class="delta-arrow" aria-hidden="true">' +
    (arrow || "") +
    "</span> " +
    sign +
    "$" +
    Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 0 }) +
    "</span>"
  );
}

function fmtDeltaPctCell(pct) {
  if (pct == null || Number.isNaN(pct)) return "—";
  const p = Number(pct) * 100;
  const n = p;
  const arrow = n > 0 ? "↑" : n < 0 ? "↓" : "";
  const cls = n > 0 ? "delta-cell delta-cell--up" : n < 0 ? "delta-cell delta-cell--down" : "delta-cell";
  const sign = n >= 0 ? "+" : "−";
  return (
    '<span class="' +
    cls +
    '"><span class="delta-arrow" aria-hidden="true">' +
    (arrow || "") +
    "</span> " +
    sign +
    Math.abs(n).toFixed(1) +
    "%</span>"
  );
}

function sizeBadgeForDelta(dv) {
  const a = Math.abs(Number(dv) || 0);
  if (a <= 0) return "";
  if (a > 250000) return "LARGE";
  if (a > 100000) return "MEDIUM";
  return "SMALL";
}

function isRowDerivedFromDelta(row) {
  if (!row) return false;
  const o = numOrNull(row.prior_value);
  const c = numOrNull(row.current_value);
  if (o != null && c != null) return false;
  return numOrNull(row.delta) != null;
}

function attachRowDataAttrs(tr, row) {
  const o = numOrNull(row.prior_value);
  const c = numOrNull(row.current_value);
  const dv = rowBudgetDeltaValue(row);
  if (o != null) tr.dataset.orig = String(o);
  else tr.removeAttribute("data-orig");
  if (c != null) tr.dataset.cur = String(c);
  else tr.removeAttribute("data-cur");
  tr.dataset.dv = String(dv);
  tr.dataset.derived = isRowDerivedFromDelta(row) ? "1" : "0";
}

function openLineDetailSection() {
  const d = document.getElementById("details-all-lines");
  if (d) {
    d.open = true;
    d.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function buildImpactRankMap(allRows) {
  const sorted = (allRows || []).slice().sort((a, b) => absBudgetDelta(b) - absBudgetDelta(a));
  const m = new Map();
  sorted.forEach((r, i) => {
    m.set(driverRowKey(r), i + 1);
  });
  return m;
}

function getReconciliationGapDisplay(so, allRows) {
  if (so && so.reconciliation_gap != null && !Number.isNaN(Number(so.reconciliation_gap))) {
    return numOrNull(so.reconciliation_gap);
  }
  const p = so && so.summary_deltas ? numOrNull(so.summary_deltas.profit) : null;
  if (p == null) return null;
  let sumD = 0;
  (allRows || []).forEach((r) => {
    sumD += rowBudgetDeltaValue(r);
  });
  return p - sumD;
}

function wpsForCommandView(so) {
  const s = (so && typeof so === "object") || {};
  const cur = s.current_workbook_profit_summary;
  if (cur && typeof cur === "object") return cur;
  if (s.workbook_profit_summary && typeof s.workbook_profit_summary === "object") return s.workbook_profit_summary;
  return {};
}

function commandStatusChips(rollup, varAbs, netLineAbs, tppOk, wbookOk) {
  const chips = [];
  if (!tppOk) chips.push({ cls: "cmd-chip--missing", t: "TPP not in snap" });
  if (!wbookOk) chips.push({ cls: "cmd-chip--missing", t: "Workbook TPP not in snap" });
  if (tppOk && wbookOk) {
    if (varAbs < 0.5) chips.push({ cls: "cmd-chip--ok", t: "OK" });
    else chips.push({ cls: "cmd-chip--mismatch", t: "Mismatch" });
  }
  if (varAbs >= 1000) chips.push({ cls: "cmd-chip--hot", t: "Headline variance" });
  if (netLineAbs >= 250000) chips.push({ cls: "cmd-chip--hot", t: "High movement" });
  if (String(rollup).toLowerCase() === "low") chips.push({ cls: "cmd-chip--watch", t: "Watch" });
  if (chips.length === 0) chips.push({ cls: "cmd-chip--watch", t: "Watch" });
  return chips
    .map((c) => '<span class="cmd-chip ' + c.cls + '">' + escapeHtml(c.t) + "</span>")
    .join(" ");
}

/**
 * Executive command view: TPP, workbook, variance, net budget movement, drivers, reconciliation.
 */
function renderProjectFinancialCommandView(allRows, so, _execSig) {
  const host = document.getElementById("project-financial-signals-strip");
  if (!host) return;
  const wps0 = wpsForCommandView(so);
  const hasWps = wps0 && (numOrNull(wps0.total_projected_profit) != null || numOrNull(wps0.workbook_reported_total_projected_profit) != null);
  const hasLines = allRows && allRows.length > 0;
  if (!hasWps && !hasLines) {
    host.setAttribute("hidden", "hidden");
    host.innerHTML = "";
    return;
  }
  host.removeAttribute("hidden");
  const rowList = hasLines ? allRows : [];
  const wps = wps0;
  const tpp = numOrNull(wps.total_projected_profit);
  const wbook = numOrNull(wps.workbook_reported_total_projected_profit);
  const pvar = numOrNull(wps.projected_profit_variance);
  const tppOk = tpp != null;
  const wbookOk = wbook != null;
  const varAbs = pvar != null ? Math.abs(pvar) : 0;
  const net = rowList.reduce((s, r) => s + rowBudgetDeltaValue(r), 0);
  let bestPos = null;
  let worstNeg = null;
  let maxAbsPct = null;
  let maxAbsPctRow = null;
  rowList.forEach((r) => {
    const d = rowBudgetDeltaValue(r);
    const label = r.category_label || r.category || "—";
    if (d > 0 && (bestPos == null || d > bestPos.d)) bestPos = { d, label };
    if (d < 0 && (worstNeg == null || d < worstNeg.d)) worstNeg = { d, label };
    const p = rowBudgetDeltaPct(r);
    if (p != null) {
      const ap = Math.abs(p);
      if (maxAbsPct == null || ap > maxAbsPct) {
        maxAbsPct = ap;
        maxAbsPctRow = { row: r, p };
      }
    }
  });
  const tradeSwing = (function buildSwing() {
    const g = new Map();
    rowList.forEach((r) => {
      const k = tradeKeyFromRow(r);
      if (!g.has(k)) g.set(k, { orig: 0, cur: 0 });
      const o = g.get(k);
      o.orig += numOrNull(r.prior_value) != null ? Number(r.prior_value) : 0;
      o.cur += numOrNull(r.current_value) != null ? Number(r.current_value) : 0;
    });
    let bestK = "—";
    let bestNet = 0;
    let bestPct = null;
    let bestA = 0;
    g.forEach((v, k) => {
      const n = v.cur - v.orig;
      const a = Math.abs(n);
      if (a > bestA) {
        bestA = a;
        bestK = k;
        bestNet = n;
        bestPct = v.orig !== 0 ? n / v.orig : null;
      }
    });
    return { k: bestK, net: bestNet, pct: bestPct };
  })();
  const recGap = getReconciliationGapDisplay(so, rowList);
  const roll = (so && so.extraction_confidence && so.extraction_confidence.rollup) || "";
  const recStatus =
    recGap != null && !Number.isNaN(recGap)
      ? (Math.abs(recGap) < 1 ? "Tight · lines tie to summary" : "Bridge gap " + fmtMoneySigned(recGap))
      : "Line bridge not computed for this run";
  const varDisplay =
    pvar == null
      ? "— <span class='src-weak'>(no workbook bridge)</span>"
      : '<span class="command-variance-line">' + fmtMoneySigned(pvar) + "</span>";
  const chips = commandStatusChips(roll, varAbs, Math.abs(net), tppOk, wbookOk);
  const netCls = "pfs-metric__val pfs-metric__val--" + (net > 0 ? "up" : net < 0 ? "down" : "flat");
  const netArrow = net > 0 ? "↑" : net < 0 ? "↓" : "";
  const swingLine =
    maxAbsPctRow && maxAbsPctRow.p != null
      ? fmtDeltaPctCell(maxAbsPctRow.p) + " <span class='pfs-swing-line'>(" + escapeHtml(String(maxAbsPctRow.row.category_label || maxAbsPctRow.row.category || "—")) + ")</span>"
      : "—";
  host.innerHTML =
    '<div class="command-view-head">' +
    "<h2 class='command-view-title'>Project financial command view</h2>" +
    "<div class='command-chips' aria-label='Status'>" +
    chips +
    "</div></div>" +
    '<div class="pfs-grid command-prime" role="group">' +
    '<div class="pfs-metric pfs-metric--hero"><span class="pfs-metric__k">Total projected profit (formula)</span>' +
    "<span class='pfs-metric__val'>" +
    (tpp != null ? fmtMoneyPlain(tpp) : "—") +
    "</span></div>" +
    '<div class="pfs-metric pfs-metric--hero"><span class="pfs-metric__k">Workbook-reported TPP</span>' +
    "<span class='pfs-metric__val'>" +
    (wbook != null ? fmtMoneyPlain(wbook) : "—") +
    "</span></div>" +
    '<div class="pfs-metric pfs-metric--hero pfs-metric--variance"><span class="pfs-metric__k">Formula vs workbook variance</span>' +
    "<span class='pfs-metric__val pfs-metric__val--variance'>" +
    varDisplay +
    "</span></div></div>" +
    '<div class="pfs-grid" role="group" aria-label="Line-level signals">' +
    '<div class="pfs-metric"><span class="pfs-metric__k">Net budget movement (lines)</span>' +
    '<span class="' +
    netCls +
    '">' +
    (netArrow ? '<span class="pfs-arrow" aria-hidden="true">' + netArrow + "</span> " : "") +
    fmtMoneySigned(net) +
    "</span></div>" +
    '<div class="pfs-metric"><span class="pfs-metric__k">Largest positive driver (line)</span>' +
    '<span class="pfs-metric__val pfs-metric__val--up">' +
    (bestPos ? escapeHtml(bestPos.label) + " · " + fmtMoneySigned(bestPos.d) : "—") +
    "</span></div>" +
    '<div class="pfs-metric"><span class="pfs-metric__k">Largest negative driver (line)</span>' +
    '<span class="pfs-metric__val pfs-metric__val--down">' +
    (worstNeg ? escapeHtml(worstNeg.label) + " · " + fmtMoneySigned(worstNeg.d) : "—") +
    "</span></div>" +
    '<div class="pfs-metric pfs-metric--wide"><span class="pfs-metric__k">Largest trade / category swing (net $)</span>' +
    "<span class='pfs-metric__val'>" +
    escapeHtml(tradeSwing.k) +
    " · " +
    fmtDeltaUsdCell(tradeSwing.net) +
    (tradeSwing.pct != null ? " · " + fmtDeltaPctCell(tradeSwing.pct) : "") +
    "</span></div>" +
    '<div class="pfs-metric pfs-metric--wide"><span class="pfs-metric__k">Largest |Δ%| (line)</span><span class="pfs-metric__val">' +
    swingLine +
    "</span></div>" +
    '<div class="pfs-metric pfs-metric--wide"><span class="pfs-metric__k">Reconciliation / bridge</span><span class="pfs-metric__val">' +
    (recGap != null && !Number.isNaN(recGap) ? fmtMoneySigned(recGap) + " · " : "") +
    "<span class='recon-line'>" +
    escapeHtml(recStatus) +
    "</span> · <span class='src-tag'>Read: " +
    escapeHtml(roll || "—") +
    "</span></span></div>" +
    "</div>";
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function tradeGroupSignal(g) {
  const net = g.d;
  const mabs = Math.abs(net);
  const pct = g.pct;
  if (g.orig === 0 && g.cur !== 0) return "Missing base";
  if (mabs >= 250000) return "High movement";
  if (pct != null && Math.abs(pct) >= 0.2) return "Watch";
  return "OK";
}

function renderTradeSummaryHost(host, allRows) {
  if (!host) return;
  if (!allRows || allRows.length === 0) {
    host.setAttribute("hidden", "hidden");
    host.innerHTML = "";
    return;
  }
  const groups = new Map();
  allRows.forEach((r) => {
    const k = tradeKeyFromRow(r);
    const o = groups.get(k) || { orig: 0, cur: 0, n: 0 };
    o.orig += numOrNull(r.prior_value) != null ? Number(r.prior_value) : 0;
    o.cur += numOrNull(r.current_value) != null ? Number(r.current_value) : 0;
    o.n += 1;
    groups.set(k, o);
  });
  const list = Array.from(groups.entries()).map(([trade, o]) => {
    const d = o.cur - o.orig;
    const pct = o.orig !== 0 ? d / o.orig : o.orig === 0 && o.cur === 0 ? 0 : null;
    return { trade, orig: o.orig, cur: o.cur, d, pct, n: o.n, abs: Math.abs(d) };
  });
  list.sort((a, b) => b.abs - a.abs);
  let tb = "";
  list.forEach((g, i) => {
    const sig = tradeGroupSignal(g);
    const sigCls =
      sig === "High movement"
        ? "trade-sig trade-sig--hot"
        : sig === "Watch"
          ? "trade-sig trade-sig--watch"
          : sig === "Missing base"
            ? "trade-sig trade-sig--miss"
            : "trade-sig trade-sig--ok";
    tb +=
      "<tr>" +
      "<td class='num trade-rank'>" +
      String(i + 1) +
      "</td>" +
      "<td class='trade-name'>" +
      escapeHtml(g.trade) +
      "</td>" +
      "<td class='num'>" +
      fmtMoneyPlain(g.orig) +
      "</td>" +
      "<td class='num'>" +
      fmtMoneyPlain(g.cur) +
      "</td>" +
      "<td class='num'>" +
      fmtDeltaUsdCell(g.d) +
      "</td>" +
      "<td class='num'>" +
      (g.pct == null && !(g.orig === 0 && g.cur === 0) ? "—" : fmtDeltaPctCell(g.pct)) +
      "</td>" +
      "<td class='num'>" +
      String(g.n) +
      "</td>" +
      "<td><span class='" +
      sigCls +
      "'>" +
      escapeHtml(sig) +
      "</span></td>" +
      "</tr>";
  });
  const tCur = list.reduce((s, g) => s + g.cur, 0);
  const tOrig = list.reduce((s, g) => s + g.orig, 0);
  const tNet = list.reduce((s, g) => s + g.d, 0);
  const tRows = allRows.length;
  host.removeAttribute("hidden");
  host.innerHTML =
    '<h4 class="trade-summary__title">Trade / category rollup (first read)</h4>' +
    '<p class="trade-summary__lede subtle">Rolled from visible cost-code lines. Detail follows below.</p>' +
    '<div class="trade-summary__wrap table-scroll-sticky"><table class="data-table trade-summary-table trade-summary-table--rich">' +
    "<thead><tr><th>Rank</th><th>Trade / category</th><th>Original total</th><th>Current total</th><th>Net movement</th><th>Movement %</th><th>Source rows</th><th>Signal</th></tr></thead><tbody>" +
    tb +
    "</tbody><tfoot class='data-table__foot trade-summary__foot'><tr><td class='foot-label' colspan='2'>Roll-up total</td>" +
    "<td class='num'>" +
    fmtMoneyPlain(tOrig) +
    "</td><td class='num'>" +
    fmtMoneyPlain(tCur) +
    "</td><td class='num'>" +
    fmtDeltaUsdCell(tNet) +
    "</td><td class='num'>—</td><td class='num'>" +
    String(list.reduce((s, g) => s + g.n, 0)) +
    "</td><td class='foot-meta'>Groups " +
    String(list.length) +
    " · Lines " +
    String(tRows) +
    "</td></tr></tfoot></table></div>";
}

function collectVisibleDataRows(tbody) {
  const out = [];
  if (!tbody) return out;
  tbody.querySelectorAll("tr").forEach((tr) => {
    if (tr.classList.contains("driver-message-row")) return;
    if (tr.style.display === "none") return;
    if (tr.cells && tr.cells.length === 1) return;
    if (tr.dataset.dv === undefined) return;
    out.push(tr);
  });
  return out;
}

function aggregateFromDataRows(trs) {
  let soV = 0;
  let scV = 0;
  let net = 0;
  const dvs = [];
  trs.forEach((tr) => {
    const o = tr.dataset.orig != null && tr.dataset.orig !== "" ? Number(tr.dataset.orig) : 0;
    const c = tr.dataset.cur != null && tr.dataset.cur !== "" ? Number(tr.dataset.cur) : 0;
    soV += o;
    scV += c;
    const dv = Number(tr.dataset.dv) || 0;
    dvs.push(dv);
    net += dv;
  });
  return { trs, soV, scV, net, dvs, n: trs.length };
}

function setPrimaryFooterFromAgg(agg) {
  const pFoot = document.getElementById("drivers-primary-foot");
  if (!pFoot) return;
  if (agg.n === 0) {
    pFoot.removeAttribute("hidden");
    const elO = document.getElementById("foot-sum-orig");
    const elC = document.getElementById("foot-sum-cur");
    const elN = document.getElementById("foot-net-delta");
    const elP = document.getElementById("foot-net-pct");
    const elT = document.getElementById("foot-top5-pct");
    if (elO) elO.textContent = "—";
    if (elC) elC.textContent = "—";
    if (elN) elN.innerHTML = "—";
    if (elP) elP.innerHTML = "—";
    if (elT) elT.textContent = "0 visible rows";
    return;
  }
  const top5 = (function () {
    const a = (agg.dvs || []).map((d, i) => ({ d, i })).sort((u, v) => Math.abs(v.d) - Math.abs(u.d));
    return a.slice(0, 5).reduce((s, x) => s + Math.abs(x.d), 0);
  })();
  const sumAbs = (agg.dvs || []).reduce((s, d) => s + Math.abs(d), 0);
  const topShare = sumAbs > 0 ? (top5 / sumAbs) * 100 : 0;
  const netPct = agg.soV !== 0 ? (agg.scV - agg.soV) / agg.soV : null;
  const elO = document.getElementById("foot-sum-orig");
  const elC = document.getElementById("foot-sum-cur");
  const elN = document.getElementById("foot-net-delta");
  const elP = document.getElementById("foot-net-pct");
  const elT = document.getElementById("foot-top5-pct");
  if (elO) elO.textContent = fmtMoneyPlain(agg.soV);
  if (elC) elC.textContent = fmtMoneyPlain(agg.scV);
  if (elN) elN.innerHTML = fmtDeltaUsdCell(agg.net);
  if (elP) elP.innerHTML = netPct == null || Number.isNaN(netPct) ? "—" : fmtDeltaPctCell(netPct);
  if (elT)
    elT.textContent =
      String(agg.n) +
      " rows · Top 5 |Δ| share: " +
      (Number.isFinite(topShare) ? topShare.toFixed(1) : "0") +
      "%";
  pFoot.removeAttribute("hidden");
}

function setAuditFooterFromAgg(agg) {
  const aFoot = document.getElementById("drivers-audit-foot");
  if (!aFoot) return;
  if (agg.n === 0) {
    aFoot.removeAttribute("hidden");
    const elO = document.getElementById("audit-foot-sum-orig");
    const elC = document.getElementById("audit-foot-sum-cur");
    const elN = document.getElementById("audit-foot-net-delta");
    const elP = document.getElementById("audit-foot-net-pct");
    if (elO) elO.textContent = "—";
    if (elC) elC.textContent = "—";
    if (elN) elN.innerHTML = "—";
    if (elP) elP.innerHTML = "—";
    return;
  }
  const netPct = agg.soV !== 0 ? (agg.scV - agg.soV) / agg.soV : null;
  const elO = document.getElementById("audit-foot-sum-orig");
  const elC = document.getElementById("audit-foot-sum-cur");
  const elN = document.getElementById("audit-foot-net-delta");
  const elP = document.getElementById("audit-foot-net-pct");
  if (elO) elO.textContent = fmtMoneyPlain(agg.soV);
  if (elC) elC.textContent = fmtMoneyPlain(agg.scV);
  if (elN) elN.innerHTML = fmtDeltaUsdCell(agg.net);
  if (elP) elP.innerHTML = netPct == null || Number.isNaN(netPct) ? "—" : fmtDeltaPctCell(netPct);
  aFoot.removeAttribute("hidden");
}

function writeFilterBar(el, nVis, nTot, soV, scV, net) {
  if (!el) return;
  if (nTot === 0) {
    el.textContent = "";
    return;
  }
  el.textContent =
    "Showing " +
    String(nVis) +
    " of " +
    String(nTot) +
    " rows · Visible current total: " +
    fmtMoneyPlain(scV) +
    " · Visible original total: " +
    fmtMoneyPlain(soV) +
    " · Visible net movement: " +
    fmtMoneySigned(net);
}

/** Financial workbench tables: read numeric data-* from a row (presentation only). */
function financialRowMoneyData(tr, dataName) {
  if (!tr) return null;
  const raw = tr.getAttribute("data-" + dataName);
  if (raw === null || raw === "") return null;
  const n = Number(raw);
  return Number.isNaN(n) ? null : n;
}

/**
 * Visible data rows in a financial workbench table (excludes empty-state and colspan placeholders).
 */
function collectVisibleFinancialRows(tableEl) {
  const tb = tableEl && tableEl.tBodies[0];
  if (!tb) return [];
  return Array.from(tb.querySelectorAll("tr")).filter((tr) => {
    if (tr.style.display === "none") return false;
    const kind = tr.getAttribute("data-row-kind");
    if (kind === "empty" || kind === "placeholder") return false;
    if (tr.classList.contains("fin-table-empty-msg")) return false;
    const cells = tr.cells;
    if (cells && cells.length === 1 && cells[0].colSpan > 1) return false;
    return true;
  });
}

/**
 * Aggregate data-* attributes on visible rows. Mode comes from table[data-fin-mode].
 */
function aggregateVisibleFinancialRows(tableEl) {
  const mode = (tableEl && tableEl.getAttribute("data-fin-mode")) || "orig-cur";
  const rows = collectVisibleFinancialRows(tableEl);
  const out = {
    n: rows.length,
    original: 0,
    current: 0,
    delta: 0,
    total: 0,
    hasOriginal: false,
    hasCurrent: false,
    recFormula: null,
    recWorkbook: null,
    recVariance: null,
  };
  rows.forEach((tr) => {
    const o = financialRowMoneyData(tr, "original");
    const c = financialRowMoneyData(tr, "current");
    const d = financialRowMoneyData(tr, "delta");
    const t = financialRowMoneyData(tr, "total");
    const kind = tr.getAttribute("data-row-kind") || "";
    if (mode === "rec") {
      if (t != null) out.total += t;
      if (kind === "rec-tpp" && t != null) out.recFormula = t;
      if (kind === "rec-workbook" && t != null) out.recWorkbook = t;
      if (kind === "rec-variance" && t != null) out.recVariance = t;
      return;
    }
    if (mode === "orig-cur") {
      if (o != null) {
        out.original += o;
        out.hasOriginal = true;
      }
      if (c != null) {
        out.current += c;
        out.hasCurrent = true;
      }
      if (d != null) out.delta += d;
      else if (o != null && c != null) out.delta += c - o;
      return;
    }
    if (mode === "co-ucb") {
      if (c != null) {
        out.current += c;
        out.hasCurrent = true;
      }
      return;
    }
    if (mode === "lrp-total") {
      if (t != null) {
        out.total += t;
        out.hasCurrent = true;
      }
      return;
    }
    if (c != null) {
      out.current += c;
      out.hasCurrent = true;
    }
    if (t != null) {
      out.total += t;
      out.hasCurrent = true;
    }
  });
  return out;
}

function finValClass(n) {
  if (n == null || Number.isNaN(Number(n))) return "fin-val fin-val--muted";
  const v = Number(n);
  if (v > 0) return "fin-val fin-val--pos";
  if (v < 0) return "fin-val fin-val--neg";
  return "fin-val fin-val--zero";
}

function finPlainMoneyHtml(n) {
  if (n == null || Number.isNaN(Number(n))) return '<span class="fin-val fin-val--muted">—</span>';
  const v = Number(n);
  const sign = v < 0 ? "−" : "";
  const mag = "$" + Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 });
  return '<span class="' + finValClass(v) + '">' + sign + mag + "</span>";
}

function finSignedMoneyHtml(n) {
  if (n == null || Number.isNaN(Number(n))) return '<span class="fin-val fin-val--muted">—</span>';
  const v = Number(n);
  const sign = v >= 0 ? "+" : "−";
  return (
    '<span class="' +
    finValClass(v) +
    '">' +
    sign +
    "$" +
    Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 }) +
    "</span>"
  );
}

/**
 * Update summary bar + tfoot for one workbench financial table.
 * options.totalRowCount — denominator for "X of Y" (optional; else data-fin-total-rows on table).
 */
function updateFinancialTableFooter(tableEl, options) {
  if (!tableEl || !tableEl.classList.contains("fin-wb-table")) return;
  const opts = options || {};
  let y =
    opts.totalRowCount != null
      ? Number(opts.totalRowCount)
      : tableEl.dataset.finTotalRows != null
        ? Number(tableEl.dataset.finTotalRows)
        : null;
  if (y != null && Number.isNaN(y)) y = null;
  const mode = tableEl.getAttribute("data-fin-mode") || "orig-cur";
  const agg = aggregateVisibleFinancialRows(tableEl);
  const wrap = tableEl.closest(".workbench-table-wrap");
  const barEl =
    opts.summaryBarEl ||
    (wrap && wrap.previousElementSibling && wrap.previousElementSibling.classList.contains("financial-table-summary-bar")
      ? wrap.previousElementSibling
      : null);

  const x = agg.n;
  const yDisp = y != null && !Number.isNaN(y) ? y : x;
  let barText = "";
  if (mode === "orig-cur") {
    const netPct = agg.hasOriginal && agg.original !== 0 ? (agg.current - agg.original) / agg.original : null;
    barText =
      "Showing " +
      x +
      " of " +
      yDisp +
      " rows · Visible original total: " +
      fmtMoneyPlain(agg.original) +
      " · Visible current total: " +
      fmtMoneyPlain(agg.current) +
      " · Visible net movement: " +
      fmtMoneySigned(agg.delta) +
      (netPct != null && !Number.isNaN(netPct) ? " (" + (netPct * 100).toFixed(1) + "%)" : "");
  } else if (mode === "rec") {
    const parts = ["Showing " + x + " of " + yDisp + " rows"];
    if (agg.recFormula != null) parts.push("Visible formula TPP: " + fmtMoneyPlain(agg.recFormula));
    if (agg.recWorkbook != null) parts.push("Visible workbook TPP: " + fmtMoneyPlain(agg.recWorkbook));
    if (agg.recVariance != null) parts.push("Visible variance / gap: " + fmtMoneySigned(agg.recVariance));
    if (agg.recFormula == null && agg.recWorkbook == null && agg.recVariance == null && x > 0) {
      parts.push("Visible total (sum of values): " + fmtMoneyPlain(agg.total));
    }
    barText = parts.join(" · ");
  } else {
    const primary =
      mode === "lrp-total" ? agg.total : mode === "co-ucb" ? agg.current : agg.current || agg.total;
    barText =
      "Showing " +
      x +
      " of " +
      yDisp +
      " rows · Visible total: " +
      fmtMoneyPlain(primary);
  }
  if (barEl) barEl.textContent = barText;

  const foot = tableEl.tFoot;
  if (!foot || !foot.rows[0]) return;
  const tr = foot.rows[0];
  const lead = tr.querySelector(".fin-foot-lead");
  const fc = tr.querySelector(".fin-foot-cur");
  const fo = tr.querySelector(".fin-foot-orig");
  const fd = tr.querySelector(".fin-foot-delta");
  const ft = tr.querySelector(".fin-foot-total");
  if (lead) {
    lead.textContent =
      x === 0 ? "No visible rows" : "Visible totals (" + x + " row" + (x === 1 ? "" : "s") + ")";
  }
  if (mode === "orig-cur") {
    if (fc) fc.innerHTML = finPlainMoneyHtml(agg.hasOriginal || agg.hasCurrent ? agg.current : null);
    if (fo) fo.innerHTML = finPlainMoneyHtml(agg.hasOriginal ? agg.original : null);
    if (fd) {
      const netPct = agg.hasOriginal && agg.original !== 0 ? (agg.current - agg.original) / agg.original : null;
      const pctHtml =
        netPct == null || Number.isNaN(netPct) ? "" : " " + fmtDeltaPctCell(netPct);
      fd.innerHTML = finSignedMoneyHtml(agg.delta) + pctHtml;
    }
  } else if (mode === "rec") {
    if (fc) {
      const bits = [];
      if (agg.recFormula != null) {
        bits.push('<span class="fin-rec-line"><span class="fin-rec-k">Formula TPP</span> ' + finPlainMoneyHtml(agg.recFormula) + "</span>");
      }
      if (agg.recWorkbook != null) {
        bits.push('<span class="fin-rec-line"><span class="fin-rec-k">Workbook TPP</span> ' + finPlainMoneyHtml(agg.recWorkbook) + "</span>");
      }
      if (agg.recVariance != null) {
        bits.push('<span class="fin-rec-line"><span class="fin-rec-k">Variance / gap</span> ' + finSignedMoneyHtml(agg.recVariance) + "</span>");
      }
      fc.innerHTML =
        bits.length > 0
          ? '<div class="fin-rec-foot-stack">' + bits.join('<span class="fin-rec-sep"> · </span>') + "</div>"
          : '<span class="fin-val fin-val--muted">—</span>';
    }
    if (fo) fo.innerHTML = '<span class="fin-val fin-val--muted">—</span>';
  } else {
    const primary =
      mode === "lrp-total" ? agg.total : mode === "co-ucb" ? agg.current : agg.current || agg.total;
    if (fc) fc.innerHTML = finPlainMoneyHtml(primary);
  }
}

function updateAllFinancialTableFooters() {
  document.querySelectorAll("table.fin-wb-table").forEach((t) => updateFinancialTableFooter(t));
}

function refreshDriverTableUi() {
  if (window.__driverStructOk === false) {
    const pFoot = document.getElementById("drivers-primary-foot");
    const aFoot = document.getElementById("drivers-audit-foot");
    if (pFoot) pFoot.setAttribute("hidden", "hidden");
    if (aFoot) aFoot.setAttribute("hidden", "hidden");
    const b1 = document.getElementById("driver-primary-filter-bar");
    const b2 = document.getElementById("driver-audit-filter-bar");
    if (b1) b1.textContent = "";
    if (b2) b2.textContent = "";
    return;
  }
  const pBody = document.getElementById("drivers-primary-body");
  const aBody = document.getElementById("drivers-audit-body");
  const pTotal = (window.__driverTableCounts && window.__driverTableCounts.primaryAll) || 0;
  const aTotal = (window.__driverTableCounts && window.__driverTableCounts.auditAll) || 0;
  const pTr = collectVisibleDataRows(pBody);
  const aTr = collectVisibleDataRows(aBody);
  const pAgg = aggregateFromDataRows(pTr);
  const aAgg = aggregateFromDataRows(aTr);
  setPrimaryFooterFromAgg(pAgg);
  setAuditFooterFromAgg(aAgg);
  writeFilterBar(document.getElementById("driver-primary-filter-bar"), pAgg.n, pTotal, pAgg.soV, pAgg.scV, pAgg.net);
  writeFilterBar(document.getElementById("driver-audit-filter-bar"), aAgg.n, aTotal, aAgg.soV, aAgg.scV, aAgg.net);
}

function fillTableFooterMetrics(_allRows) {
  refreshDriverTableUi();
  updateAllFinancialTableFooters();
}

function setDriverDataRowAttributes(tr, row) {
  const dv = rowBudgetDeltaValue(row);
  tr.setAttribute("data-delta-neg", dv < 0 ? "1" : "0");
  tr.dataset.driverLabel = String(row.category_label || row.category || "").toLowerCase();
  const pct = rowBudgetDeltaPct(row);
  let cls = "driver-data-row";
  if (!hasOriginalBudget(row)) cls += " driver-row--missing-orig";
  if (pct != null && Math.abs(pct) > 0.2) cls += " driver-row--pct-swing";
  const b = sizeBadgeForDelta(dv);
  if (b) cls += " driver-row--" + b.toLowerCase();
  tr.className = cls;
}

/**
 * Deterministic executive signal from structured_output + driver split only.
 * Does not invent currency values; optional fields stay null when unknown.
 */
function buildExecutiveSignal(so, structOk, isFin, driverSplit) {
  const insufficient = {
    signal_summary: {
      signal_type: "LOW_SIGNAL",
      severity: "LOW",
      direction: "NEUTRAL",
      confidence: "LOW",
      driver_clarity: "INSUFFICIENT_DATA",
    },
    driver_attribution: {
      primary_driver_label: null,
      primary_driver_amount: null,
      primary_driver_share_of_abs_movement: null,
      top_driver_count: 0,
      material_driver_count: 0,
    },
    movement_context: {
      profit_delta: null,
      revenue_delta: null,
      cost_delta: null,
      net_effect_label: "Structured compare data is not available for a full movement read.",
      cost_revenue_relationship: "INSUFFICIENT_DATA",
    },
    review_actions: [
      "Confirm workbooks use the expected tables, then re-run the compare to populate material lines.",
    ],
  };

  if (!isFin || !structOk) {
    return insufficient;
  }

  const sd = so.summary_deltas || {};
  const p = numOrNull(sd.profit);
  const r = numOrNull(sd.revenue);
  const c = numOrNull(sd.cost);

  const primary = (driverSplit && driverSplit.primary) || [];
  const audit = (driverSplit && driverSplit.audit) || [];
  const allRows = [].concat(primary, audit);
  let sumAbs = 0;
  allRows.forEach((row) => {
    sumAbs += Math.abs(Number(row && row.delta) || 0);
  });
  const primarySorted = sortedByAbsDelta(allRows);
  const top = primarySorted[0] || null;
  const pLabel = top ? String(top.category_label || top.category || "Category") : null;
  const topShare = sumAbs > 0 && top ? Math.abs(Number(top.delta) || 0) / sumAbs : null;

  let materialCount = 0;
  allRows.forEach((row) => {
    if (Math.abs(Number(row && row.delta) || 0) >= DRIVER_IMPACT_THRESHOLD) materialCount += 1;
  });

  const roll = (so.extraction_confidence && so.extraction_confidence.rollup) || "";
  const confMap = { high: "HIGH", medium: "MEDIUM", low: "LOW" };
  const confidence = confMap[String(roll).toLowerCase()] || "MEDIUM";

  const absP = p != null ? Math.abs(p) : 0;
  let severity = "LOW";
  if (p == null || Number.isNaN(absP)) severity = "LOW";
  else if (absP < 10000) severity = "LOW";
  else if (absP < 50000) severity = "MODERATE";
  else if (absP < 150000) severity = "HIGH";
  else severity = "CRITICAL";

  let direction = "NEUTRAL";
  if (p == null) direction = "NEUTRAL";
  else if (p > 0) direction = "FAVORABLE";
  else if (p < 0) direction = "UNFAVORABLE";
  else direction = "NEUTRAL";

  let costRevenueRelationship = "INSUFFICIENT_DATA";
  if (r != null && c != null) {
    if (r > 0 && c > 0) costRevenueRelationship = "COST_AND_REVENUE_BOTH_UP";
    else if (r < 0 && c < 0) costRevenueRelationship = "COST_AND_REVENUE_BOTH_DOWN";
    else if (r > 0 && c < 0) costRevenueRelationship = "REVENUE_OUTPACED_COST";
    else if (r < 0 && c > 0) costRevenueRelationship = "COST_OUTPACED_REVENUE";
    else if (r > 0 && c === 0) costRevenueRelationship = "REVENUE_OUTPACED_COST";
    else if (c > 0 && r === 0) costRevenueRelationship = "COST_OUTPACED_REVENUE";
    else costRevenueRelationship = "MIXED_MOVEMENT";
  }

  let driverClarity = "INSUFFICIENT_DATA";
  if (allRows.length === 0) driverClarity = "INSUFFICIENT_DATA";
  else if (topShare != null && topShare >= 0.55) driverClarity = "SINGLE_DRIVER";
  else if (allRows.length >= 2 && topShare != null && topShare >= 0.28) driverClarity = "MULTI_DRIVER";
  else if (allRows.length > 0) driverClarity = "DIFFUSE";

  let signalType = "MIXED_MOVEMENT";
  if (p == null) signalType = "LOW_SIGNAL";
  else if (sumAbs < 1e-9 && absP < 1000) signalType = "LOW_SIGNAL";
  else if (Math.abs(p) < 1e-9) signalType = "MIXED_MOVEMENT";
  else if (p < 0) {
    if (c != null && c > 0 && (r == null || r <= 0 || Math.abs(c) >= Math.abs(r) * 0.7)) {
      signalType = "COST_INCREASE";
    } else {
      signalType = "PROFIT_COMPRESSION";
    }
  } else {
    if (r != null && r > 0 && (c == null || c <= 0 || r >= Math.abs(c) * 0.8)) {
      signalType = "REVENUE_INCREASE";
    } else {
      signalType = "PROFIT_EXPANSION";
    }
  }

  let netEffectLabel = "Net profit movement is not available from summary deltas.";
  if (p != null) {
    if (p < 0) {
      netEffectLabel = "Net profit is " + fmtMoneyPlain(absP) + " lower than prior in the period summary.";
    } else if (p > 0) {
      netEffectLabel = "Net profit is " + fmtMoneyPlain(absP) + " higher than prior in the period summary.";
    } else {
      netEffectLabel = "Net profit is flat versus prior in the period summary.";
    }
  }

  const ctx = {
    signalType: signalType,
    crr: costRevenueRelationship,
    driverClarity: driverClarity,
    direction: direction,
    p: p,
    r: r,
    c: c,
    pLabel: pLabel,
    materialCount: materialCount,
    confidence: confidence,
  };
  const reviewActions = buildReviewActionsDeterministic(ctx);

  return {
    signal_summary: {
      signal_type: signalType,
      severity: severity,
      direction: direction,
      confidence: confidence,
      driver_clarity: driverClarity,
    },
    driver_attribution: {
      primary_driver_label: pLabel,
      primary_driver_amount: top != null ? Number(top.delta) : null,
      primary_driver_share_of_abs_movement: topShare,
      top_driver_count: allRows.length,
      material_driver_count: materialCount,
    },
    movement_context: {
      profit_delta: p,
      revenue_delta: r,
      cost_delta: c,
      net_effect_label: netEffectLabel,
      cost_revenue_relationship: costRevenueRelationship,
    },
    review_actions: reviewActions,
  };
}

function crrLabel(key) {
  const map = {
    INSUFFICIENT_DATA: "Insufficient revenue/cost summary",
    COST_AND_REVENUE_BOTH_UP: "Revenue and cost both up",
    COST_AND_REVENUE_BOTH_DOWN: "Revenue and cost both down",
    REVENUE_OUTPACED_COST: "Revenue outpaced cost",
    COST_OUTPACED_REVENUE: "Cost outpaced revenue",
    MIXED_MOVEMENT: "Mixed revenue/cost pattern",
  };
  return map[key] || key;
}

function buildReviewActionsDeterministic(ctx) {
  const out = [];
  const st = ctx.signalType;
  const crr = ctx.crr;
  const dc = ctx.driverClarity;

  if (crr === "COST_OUTPACED_REVENUE" || st === "COST_INCREASE") {
    out.push("Review cost codes with the largest unfavorable movement before accepting the forecast.");
  }
  if (st === "PROFIT_COMPRESSION" || (ctx.p != null && ctx.p < 0)) {
    out.push("Confirm whether movement is one-time, timing, or structural using supporting schedules.");
  }
  if (crr === "COST_AND_REVENUE_BOTH_UP" || crr === "REVENUE_OUTPACED_COST") {
    out.push("Validate whether revenue gain is timing-based or supported by approved owner changes.");
  }
  if (st === "REVENUE_INCREASE" || st === "PROFIT_EXPANSION") {
    out.push("Validate whether the gain is recurring before you carry it into the forecast.");
  }
  if (dc === "SINGLE_DRIVER" && ctx.pLabel) {
    out.push("Pressure-test the single largest driver line (" + ctx.pLabel + ") against the summary roll-up.");
  }
  if (dc === "MULTI_DRIVER" || dc === "DIFFUSE") {
    out.push("Compare several top categories in the line table; avoid attributing the period to a single line.");
  }
  if (ctx.materialCount >= 3) {
    out.push("Triage the material-threshold lines first; small rows can wait until the headline story is stable.");
  }
  if (ctx.confidence === "LOW") {
    out.push("Treat line dollars as directional until extraction confidence improves.");
  }
  const dedup = [];
  const seen = new Set();
  (out || []).forEach((x) => {
    if (x && !seen.has(x)) {
      seen.add(x);
      dedup.push(x);
    }
  });
  if (dedup.length < 2) {
    dedup.push("Review the line detail table and reconcile the largest |Δ| rows to your internal profit bridge.");
  }
  return dedup.slice(0, 5);
}

function buildWhyMattersLines(sig) {
  if (!sig || !sig.movement_context) return ["Run a structured compare to anchor guidance to this period."];
  const m = sig.movement_context;
  const lines = [];
  const crr = m.cost_revenue_relationship;
  if (crr === "COST_OUTPACED_REVENUE" || crr === "COST_AND_REVENUE_BOTH_UP") {
    lines.push("When cost growth competes with revenue, margin pressure shows up in profit before job narratives settle.");
  }
  if (crr === "REVENUE_OUTPACED_COST") {
    lines.push(
      "Revenue is ahead of cost in the period summary; confirm that is consistent with the job's burn and accrual timing.",
    );
  }
  if (sig.signal_summary && sig.signal_summary.severity === "CRITICAL" && m.profit_delta != null) {
    lines.push("The profit delta is large in absolute terms—small misclassification in one bucket can change the story.");
  }
  if (lines.length < 2 && m.net_effect_label) {
    lines.push(m.net_effect_label);
  }
  if (lines.length < 1) {
    lines.push("Period movement should tie to a small set of line items you can trace in the file.");
  }
  return lines.slice(0, 4);
}

function buildPrimaryConcernLine(sig) {
  if (!sig || !sig.signal_summary) return "No structured compare is loaded yet.";
  const sm = sig.signal_summary;
  const p = sig.movement_context && sig.movement_context.profit_delta;
  if (p == null) {
    return "No profit delta in the summary; focus on the largest |Δ| lines in the table.";
  }
  if (p < 0) {
    return "Priority: explain the " + fmtMoneyPlain(Math.abs(p)) + " period profit shortfall—start with " + (sm.driver_clarity === "SINGLE_DRIVER" ? "the single largest" : "the top few") + " line moves.";
  }
  if (p > 0) {
    return "Priority: pressure-test a " + fmtMoneyPlain(p) + " period gain so forecast math does not assume it recurring.";
  }
  return "Priority: reconcile flat profit with the categories that still moved materially.";
}

function buildGuidanceFromSignalAndRun(sig, av) {
  const checks = (sig && sig.review_actions) || [];
  const confNotes = [];
  if (sig && sig.signal_summary) {
    confNotes.push("Signal read: " + String(sig.signal_summary.signal_type).replace(/_/g, " ") + ".");
    confNotes.push("Driver clarity: " + String(sig.signal_summary.driver_clarity).replace(/_/g, " ") + ".");
  }
  (av && av.extraction_notes
    ? av.extraction_notes
    : []).forEach((n) => confNotes.push(String(n)));
  if (confNotes.length < 2) {
    confNotes.push("Extraction quality still matters—cross-check the trust panel for row coverage.");
  }
  return {
    primary: [buildPrimaryConcernLine(sig)],
    why: buildWhyMattersLines(sig),
    checks: checks.slice(0, 5),
    confNotes: confNotes.slice(0, 6),
  };
}

function setExecHeroBadges(badgesHost, sm) {
  if (!badgesHost) return;
  badgesHost.innerHTML = "";
  if (!sm) return;
  const rows = [
    { key: "Direction", v: sm.direction, mod: "exec-pill--dir" },
    { key: "Severity", v: sm.severity, mod: "exec-pill--sev" },
    { key: "Confidence", v: sm.confidence, mod: "exec-pill--conf" },
  ];
  rows.forEach((r) => {
    const s = document.createElement("span");
    s.className = "exec-pill " + r.mod;
    s.textContent = (r.v || "—").replace(/_/g, " ");
    s.setAttribute("title", r.key);
    badgesHost.appendChild(s);
  });
}

function buildExecHeroSentence(p, pLabel) {
  if (p == null || Number.isNaN(Number(p))) {
    return "This period does not surface a clear profit change in the summary; use material lines to anchor the review.";
  }
  const n = Number(p);
  if (n < 0) {
    return pLabel
      ? "Profit compressed by " + fmtMoneyPlain(Math.abs(n)) + " vs prior, with the largest line movement in " + pLabel + "."
      : "Profit compressed by " + fmtMoneyPlain(Math.abs(n)) + " vs prior, with no single line dominating the material list.";
  }
  if (n > 0) {
    return pLabel
      ? "Profit expanded by " + fmtMoneyPlain(n) + " vs prior, with the largest line movement in " + pLabel + "."
      : "Profit expanded by " + fmtMoneyPlain(n) + " vs prior, with movement spread across material categories.";
  }
  return pLabel
    ? "Profit is flat vs prior; the largest line movement shown is in " + pLabel + "."
    : "Profit is flat vs prior; triage the lines that still move in the table.";
}

function renderSignalClassificationRow(sig, structOk, isFin) {
  const el = document.getElementById("signal-classification-row");
  if (!el) return;
  el.innerHTML = "";
  if (!isFin || !structOk || !sig || !sig.signal_summary) {
    el.setAttribute("hidden", "hidden");
    return;
  }
  el.removeAttribute("hidden");
  const sm = sig.signal_summary;
  const m = sig.movement_context || {};
  const chips = [
    ["Type", String(sm.signal_type).replace(/_/g, " ")],
    ["Severity", sm.severity],
    ["Clarity", String(sm.driver_clarity).replace(/_/g, " ")],
    ["Confidence", sm.confidence],
    ["Revenue & cost", crrLabel(m.cost_revenue_relationship)],
  ];
  chips.forEach((pair) => {
    const c = document.createElement("div");
    c.className = "signal-chip";
    const k = document.createElement("span");
    k.className = "signal-chip__k";
    k.textContent = pair[0];
    const v = document.createElement("span");
    v.className = "signal-chip__v";
    v.textContent = pair[1];
    c.appendChild(k);
    c.appendChild(v);
    el.appendChild(c);
  });
}

function renderReviewActionsList(sig) {
  const u = document.getElementById("review-actions-list");
  if (!u) return;
  u.innerHTML = "";
  (sig && sig.review_actions ? sig.review_actions : []).forEach((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    u.appendChild(li);
  });
}

function renderDriverAttributionList(items, execSig) {
  const list = document.getElementById("driver-attribution-list");
  if (!list) return;
  list.innerHTML = "";
  const share =
    execSig && execSig.driver_attribution && execSig.driver_attribution.primary_driver_share_of_abs_movement;
  const rows = (items || []).slice().sort((a, b) => absBudgetDelta(b) - absBudgetDelta(a));
  rows.forEach((row, i) => {
    const d = rowBudgetDeltaValue(row);
    const li = document.createElement("li");
    li.className =
      "driver-attrib-item driver-attrib-item--compact" + (d < 0 ? " driver-attrib-item--neg" : " driver-attrib-item--pos");
    const rank = document.createElement("span");
    rank.className = "driver-attrib-rank";
    rank.textContent = String(i + 1);
    const one = document.createElement("div");
    one.className = "driver-attrib-one";
    const lab = document.createElement("span");
    lab.className = "driver-attrib-label";
    lab.textContent = String(row.category_label || row.category || "Category");
    const arr = document.createElement("span");
    arr.className = "driver-attrib-dir";
    arr.setAttribute("aria-hidden", "true");
    arr.textContent = d > 0 ? "↑" : d < 0 ? "↓" : "·";
    const amt = document.createElement("span");
    amt.className = "driver-attrib-amt " + (d >= 0 ? "positive" : "negative");
    amt.textContent = fmtMoneySigned(d);
    if (i === 0 && share != null) {
      lab.title = (Math.round(share * 1000) / 10) + "% of Σ|Δ| (material set)";
    }
    one.appendChild(lab);
    one.appendChild(arr);
    one.appendChild(amt);
    li.appendChild(rank);
    li.appendChild(one);
    list.appendChild(li);
  });
  if (list.children.length === 0) {
    const li = document.createElement("li");
    li.className = "driver-attrib-empty subtle";
    li.textContent = "No line-level drivers for this pass.";
    list.appendChild(li);
  }
}

function renderAnswerHero(so, structOk, isFin, execSig) {
  const root = document.getElementById("answer-hero");
  const kicker = document.getElementById("answer-hero-kicker");
  const elProfit = document.getElementById("answer-profit");
  const lineDr = document.getElementById("answer-driver-line");
  const lineIm = document.getElementById("answer-implication");
  const badges = document.getElementById("exec-hero-badges");
  const sent = document.getElementById("exec-hero-sentence");
  const sm = execSig && execSig.signal_summary;

  function clearExecChrome() {
    if (badges) badges.innerHTML = "";
    if (sent) {
      sent.textContent = "";
      sent.setAttribute("hidden", "hidden");
    }
  }

  if (!isFin) {
    clearExecChrome();
    root.classList.add("muted-answer");
    kicker.textContent = "Bottom line";
    elProfit.innerHTML = "<span class='amount'>—</span>";
    lineDr.textContent = "This compare type is not a period financial; open details for specifics.";
    lineIm.textContent = "Use the lists below to decide what to do next.";
    return;
  }
  if (!structOk) {
    clearExecChrome();
    root.classList.add("muted-answer");
    kicker.textContent = "Bottom line (limited)";
    elProfit.innerHTML = "<span class='amount'>—</span><span class='unit'>no structured P&amp;L delta</span>";
    lineDr.textContent =
      "Not enough table structure in this file pair to name a clean profit change from snapshots.";
    lineIm.textContent = "Open what changed below, or re-export with the usual profit rows exposed.";
    return;
  }
  if (sm) {
    setExecHeroBadges(badges, sm);
  } else {
    clearExecChrome();
  }

  const primLabel = execSig && execSig.driver_attribution && execSig.driver_attribution.primary_driver_label;
  const sd = so.summary_deltas || {};
  const p = sd.profit;
  if (p === undefined || p === null || Number.isNaN(Number(p))) {
    root.classList.add("muted-answer");
    kicker.textContent = "Bottom line";
    elProfit.innerHTML = "<span class='amount'>—</span>";
    if (sent) {
      sent.textContent = buildExecHeroSentence(null, primLabel);
      sent.removeAttribute("hidden");
    }
    lineDr.classList.add("subtle-hero");
    lineDr.textContent = "Largest line moves still help triage, even when summary profit is missing.";
    lineIm.textContent = "Tie revenue and cost lines to the job narrative before you lock the view.";
  } else {
    root.classList.remove("muted-answer");
    kicker.textContent = "Period profit (vs prior)";
    const n = Number(p);
    const tone = profitToneClass(n);
    const amt = document.createElement("span");
    amt.className = "amount " + (tone || "");
    amt.textContent = fmtMoneySigned(n);
    const unit = document.createElement("span");
    unit.className = "unit";
    unit.textContent = " vs prior";
    elProfit.replaceChildren(amt, document.createTextNode(" "), unit);
    if (sent) {
      sent.textContent = buildExecHeroSentence(n, primLabel);
      sent.removeAttribute("hidden");
    }
    lineDr.classList.add("subtle-hero");
    const prim = (so.material_diff_items && so.material_diff_items[0]) || null;
    if (prim) {
      const label = prim.category_label || prim.category || "Primary category";
      const d = Number(prim.delta);
      const dir = d === 0 ? "flat" : d > 0 ? "up" : "down";
      lineDr.textContent =
        "Largest table-ranked move: " + String(label) + " " + dir + " (" + fmtMoneySigned(d) + ").";
    } else {
      lineDr.textContent = "No single line leads the table—ranking below is by |Δ| in the full material set.";
    }
    if (n < 0) {
      lineIm.textContent =
        "Tie the shortfall to cost vs revenue and one-offs before reforecasting.";
    } else if (n > 0) {
      lineIm.textContent = "Check that the gain is recurring before you carry it to forecast.";
    } else {
      lineIm.textContent = "Net P&L is flat—focus on the lines that still move.";
    }
  }
}

function openDetailsScroll(id) {
  const d = document.getElementById(id);
  if (d) {
    d.open = true;
    d.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function renderExtractionConfidence(so) {
  const el = document.getElementById("extraction-confidence-block");
  const ex = (so && so.extraction_confidence) || null;
  if (!ex || !ex.rollup) {
    el.innerHTML = "<p class='subtle'>No table metadata for this compare. Treat line dollars as directionally only.</p>";
    return;
  }
  const p = ex.prior || {};
  const c = ex.current || {};
  const rollup = ex.rollup;
  const badgeClass = "conf-" + String(rollup).toLowerCase();
  el.innerHTML = `
    <div class="confidence-strip">
      <span class="conf-badge ${badgeClass}">Read: ${rollup}</span>
      <span class="subtle">Prior <strong>${p.confidence || "—"}</strong> · current <strong>${
    c.confidence || "—"
  }</strong></span>
    </div>
    <details class="evidence-collapse">
      <summary>Full read metadata</summary>
      <div class="conf-grid conf-grid--dense">
        <div>
          <h4 class="subhead">Prior</h4>
          <ul class="compact-list">
            <li>Sheets: ${(p.sheets_scanned || []).join(", ") || "—"}</li>
            <li>Categories: ${p.category_count != null ? p.category_count : "—"}</li>
            <li>Summary keys: ${(p.summary_keys_found || []).join(", ") || "—"}</li>
          </ul>
        </div>
        <div>
          <h4 class="subhead">Current</h4>
          <ul class="compact-list">
            <li>Sheets: ${(c.sheets_scanned || []).join(", ") || "—"}</li>
            <li>Categories: ${c.category_count != null ? c.category_count : "—"}</li>
            <li>Summary keys: ${(c.summary_keys_found || []).join(", ") || "—"}</li>
          </ul>
        </div>
      </div>
    </details>
  `;
}

function renderExtractionPerSide(so) {
  const host = document.getElementById("extraction-per-side");
  const ex = (so && so.extraction_confidence) || {};
  const p = ex.prior || {};
  const c = ex.current || {};
  if (!ex.rollup) {
    host.innerHTML = "<p class='subtle'>Structured per-file readouts when both sides are valid Excel snapshots.</p>";
    return;
  }
  const side = (label, o) => {
    const ev = (o.evidence || []).slice(0, 8);
    const nts = o.notes || [];
    return `<div class="ex-side ex-side--compact"><h4 class="subhead">${label}</h4>
      <p class="ex-kicker"><strong>Trust:</strong> ${o.confidence || "—"}</p>
      <details class="evidence-collapse"><summary>Evidence trail &amp; flags</summary>
      <p class="ex-sub"><strong>Trail</strong></p><ul class="compact-list ex-list">${ev.map((e) => `<li>${e}</li>`).join("") || "<li>—</li>"}
      </ul>
      <p class="ex-sub"><strong>Flags</strong></p><ul class="compact-list ex-list">${nts.map((n) => `<li>${n}</li>`).join("") || "<li>—</li>"}
      </ul></details></div>`;
  };
  host.innerHTML = side("Prior", p) + side("Current", c);
}

function parseDriverDeltaAbs(row) {
  return absBudgetDelta(row);
}

function mergeAndSplitDriverRows(primaryFromEngine, auditFromEngine) {
  const raw = []
    .concat(Array.isArray(primaryFromEngine) ? primaryFromEngine : [])
    .concat(Array.isArray(auditFromEngine) ? auditFromEngine : []);
  const seen = new Set();
  const deduped = [];
  raw.forEach((row) => {
    if (!row || typeof row !== "object") return;
    const key = [row.category_label, row.category, row.prior_value, row.current_value, row.delta].join("|");
    if (seen.has(key)) return;
    seen.add(key);
    deduped.push(row);
  });
  const total = deduped.length;
  if (total === 0) {
    return { primary: [], audit: [], total: 0, primaryCount: 0, auditCount: 0 };
  }
  const scored = deduped.map((row) => ({ row, absd: parseDriverDeltaAbs(row) }));
  scored.sort((a, b) => b.absd - a.absd);
  const inPrimary = new Set();
  scored.slice(0, DRIVER_PRIMARY_TOP_N).forEach((s) => inPrimary.add(s.row));
  scored.forEach((s) => {
    if (s.absd >= DRIVER_IMPACT_THRESHOLD) inPrimary.add(s.row);
  });
  const primary = deduped.filter((r) => inPrimary.has(r));
  primary.sort((a, b) => parseDriverDeltaAbs(b) - parseDriverDeltaAbs(a));
  const audit = deduped.filter((r) => !inPrimary.has(r));
  audit.sort((a, b) => parseDriverDeltaAbs(b) - parseDriverDeltaAbs(a));
  return {
    primary,
    audit,
    total,
    primaryCount: primary.length,
    auditCount: audit.length,
  };
}

function applyOperatorTaskDriverFocus(contract, result) {
  const lines = document.getElementById("details-all-lines");
  if (lines) lines.open = true;
  const section = document.getElementById("section-drivers");
  if (section) section.scrollIntoView({ behavior: "smooth", block: "start" });
  const found = (result && result.found) || {};
  const wf = found.workflow_output || {};
  const filterEl = document.getElementById("driver-filter");
  const negEl = document.getElementById("negatives-only");
  if (contract === "compare_and_show_labor_deltas") {
    if (filterEl) filterEl.value = "labor";
    if (negEl) negEl.checked = false;
  } else if (contract === "assess_cost_vs_revenue") {
    const sig = String((found.signal != null ? found.signal : wf.cost_vs_revenue && wf.cost_vs_revenue.signal) || "");
    if (filterEl) {
      if (sig.indexOf("revenue") >= 0) filterEl.value = "revenue";
      else if (sig.indexOf("cost") >= 0) filterEl.value = "cost";
      else filterEl.value = "";
    }
    if (negEl) negEl.checked = false;
  } else {
    return;
  }
  applyDriverFilter();
  document.querySelectorAll("#drivers-primary-body tr, #drivers-audit-body tr").forEach((tr) => {
    if (tr.classList && tr.classList.contains("driver-message-row")) return;
    if (tr.style.display === "none") return;
    tr.classList.add("assistant-driver-highlight");
    setTimeout(() => tr.classList.remove("assistant-driver-highlight"), 2200);
  });
  const wrap = document.getElementById("drivers-primary");
  if (wrap) {
    wrap.classList.add("assistant-linked");
    setTimeout(() => wrap.classList.remove("assistant-linked"), 1600);
  }
}

function applyDriverFilter() {
  const q = (document.getElementById("driver-filter").value || "").toLowerCase();
  const neg = document.getElementById("negatives-only").checked;
  const filterTools = document.getElementById("driver-tools");
  const active = q.length > 0 || neg;
  if (filterTools) filterTools.classList.toggle("driver-filter-active", active);
  const total = (window.__driverSplitMeta && window.__driverSplitMeta.total) || 0;
  const pTot = (window.__driverTableCounts && window.__driverTableCounts.primaryAll) || 0;
  const aTot = (window.__driverTableCounts && window.__driverTableCounts.auditAll) || 0;
  let visP = 0;
  let visA = 0;
  const walk = (tbody, onVis) => {
    if (!tbody) return;
    tbody.querySelectorAll("tr").forEach((tr) => {
      if (tr.classList && tr.classList.contains("driver-message-row")) {
        tr.style.display = "";
        return;
      }
      if (tr.cells && tr.cells.length === 1) {
        tr.style.display = "";
        return;
      }
      const t = (tr.textContent || "").toLowerCase();
      const isNeg = tr.getAttribute("data-delta-neg") === "1";
      const matchQ = !q || t.indexOf(q) >= 0;
      const matchN = !neg || isNeg;
      const show = matchQ && matchN;
      tr.style.display = show ? "" : "none";
      if (show) onVis();
    });
  };
  walk(document.getElementById("drivers-primary-body"), () => {
    visP += 1;
  });
  walk(document.getElementById("drivers-audit-body"), () => {
    visA += 1;
  });
  const st = document.getElementById("driver-filter-status");
  const fe = document.getElementById("driver-filter-empty");
  if (st) {
    if (total > 0) {
      st.classList.remove("hidden");
      st.textContent = active
        ? "Primary " +
          visP +
          "/" +
          pTot +
          " · Audit " +
          visA +
          "/" +
          aTot +
          " (filter on) · Total material " +
          total
        : "Primary " + visP + "/" + pTot + " · Audit " + visA + "/" + aTot + " · Total material " + total;
    } else {
      st.textContent = "";
      st.classList.add("hidden");
    }
  }
  if (fe) {
    const showEmpty = total > 0 && visP + visA === 0;
    fe.classList.toggle("hidden", !showEmpty);
  }
  const pe = document.getElementById("driver-primary-empty");
  if (pe) {
    const showP = pTot > 0 && visP === 0;
    pe.classList.toggle("hidden", !showP);
    if (showP) pe.textContent = "No rows match the current filters in this table.";
  }
  const ae = document.getElementById("driver-audit-empty");
  if (ae) {
    const showA = aTot > 0 && visA === 0;
    ae.classList.toggle("hidden", !showA);
    if (showA) ae.textContent = "No rows match the current filters in this table.";
  }
  refreshDriverTableUi();
}

function shortConfidence(rollup, narrative) {
  if (narrative && String(narrative).trim() && String(narrative) !== "—") {
    const parts = String(narrative)
      .split(".")
      .map((p) => p.trim())
      .filter(Boolean);
    return parts.slice(0, 2).join(". ") + (parts.length ? "." : "");
  }
  if (rollup) return "File read: " + rollup + ".";
  return "—";
}

function fillList(id, items) {
  const u = document.getElementById(id);
  u.innerHTML = "";
  (items || []).forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    u.appendChild(li);
  });
}

function driverCategoryLabel(row) {
  return String(row.category_label || row.category || "").toLowerCase();
}

const ASSISTANT_INTENTS = {
  summary: "summary",
  top_changes: "top_changes",
  category_filter: "category_filter",
  cost_vs_revenue: "cost_vs_revenue",
  profit_driver: "profit_driver",
  risk: "risk",
  review_first: "review_first",
  confidence: "confidence",
  comparison_overview: "comparison_overview",
};

function deriveRiskSignals(executed) {
  const risks = [];
  const so2 = (executed && executed.structured_output) || {};
  const roll = so2.extraction_confidence || null;
  if (roll && String(roll.rollup || "").toLowerCase() === "low") {
    risks.push("File read is thin; line dollars are suggestive, not final.");
  }
  if (
    executed &&
    executed.workflow === "wf_financial_markdown_delta" &&
    isStructuredFinancial(so2) &&
    (so2.material_diff_line_count || 0) === 0
  ) {
    risks.push("No line cleared the material bar—widen the view in line detail or check the book.");
  }
  if (risks.length === 0) {
    risks.push("Table read looks usable—still eyeball the heaviest lines in the book.");
  }
  return risks;
}

function normalizeQuestion(rawQuery) {
  const phraseRewrites = [
    [/\bwhat['’]s\b/g, "what is"],
    [/\bwhere should i look first\b/g, "where should i review first"],
    [/\blook into\b/g, "review"],
    [/\binvestigate\b/g, "review"],
    [/\bmain issue\b/g, "main risk"],
    [/\bwhat should worry me\b/g, "what risk should i review"],
    [/\bbiggest mover(s)?\b/g, "top changes"],
    [/\blargest mover(s)?\b/g, "top changes"],
    [/\bhurting us\b/g, "profit down"],
    [/\boffset\b/g, "offset"],
  ];
  const tokenRewrites = {
    issues: "risk",
    issue: "risk",
    problems: "risk",
    problem: "risk",
    risks: "risk",
    biggest: "top",
    largest: "top",
    mover: "change",
    movers: "change",
    movements: "movement",
    declines: "decline",
    decreases: "decrease",
    increases: "increase",
    materials: "material",
    revenues: "revenue",
    costs: "cost",
    worries: "risk",
    worried: "risk",
    review: "review",
    inspect: "review",
    check: "review",
  };
  let q = String(rawQuery || "").toLowerCase().replace(/['’]/g, "'");
  phraseRewrites.forEach(([rx, replacement]) => {
    q = q.replace(rx, replacement);
  });
  q = q.replace(/[^\w\s]/g, " ").replace(/\s+/g, " ").trim();
  const words = q
    .split(" ")
    .filter(Boolean)
    .map((w) => {
      let token = tokenRewrites[w] || w;
      if (token.endsWith("ies") && token.length > 4) token = token.slice(0, -3) + "y";
      else if (token.endsWith("s") && token.length > 4 && !token.endsWith("ss") && !token.endsWith("us")) token = token.slice(0, -1);
      return token;
    });
  return words.join(" ");
}

function sortedByAbsDelta(rows) {
  return rows.slice().sort((a, b) => Math.abs(Number(b.delta || 0)) - Math.abs(Number(a.delta || 0)));
}

function sortedByDeltaDesc(rows) {
  return rows.slice().sort((a, b) => Number(b.delta || 0) - Number(a.delta || 0));
}

function parseTopLimit(q) {
  const m1 = q.match(/\btop\s+(\d+)\b/);
  const m2 = q.match(/\b(\d+)\s+(?:top|biggest|largest|change|changes|mover|movers)\b/);
  const m3 = q.match(/\b(?:biggest|largest)\s+(\d+)\b/);
  const raw = (m1 && m1[1]) || (m2 && m2[1]) || (m3 && m3[1]);
  if (raw) return Math.min(Math.max(Number(raw) || 5, 1), 20);
  return 5;
}

function parseCategoryFilterTerm(q) {
  const explicit = q.match(/\b(?:show me|show|filter|only|just)\s+([a-z][a-z\s]{1,30})\s+only\b/);
  if (explicit && explicit[1]) return explicit[1].trim();
  const mainIssue = q.match(/\bis\s+([a-z][a-z\s]{1,30})\s+the\s+main\s+(?:issue|risk)\b/);
  if (mainIssue && mainIssue[1]) return mainIssue[1].trim();
  const known = ["labor", "material", "revenue", "cost", "expense", "overhead", "payroll", "cogs"];
  const hit = known.find((k) => q.indexOf(k) >= 0);
  if (hit) return hit;
  return "";
}

function parseNegativeOnly(q) {
  const hasNegative = /\b(?:negative|decline|drop|decrease|loss|downward|hurting|hurt)\b/.test(q);
  const hasMovement = /\b(?:move|movement|change|mover|top)\b/.test(q);
  return q.indexOf("negative only") >= 0 || (hasNegative && hasMovement);
}

function classifyAssistantIntent(rawQuery) {
  const q = normalizeQuestion(rawQuery);
  if (!q) return { intent: null, confidence: 0, query: q, topN: 5, categoryTerm: "", negativeOnly: false, limits: [] };
  const topN = parseTopLimit(q);
  const categoryTerm = parseCategoryFilterTerm(q);
  const negativeOnly = parseNegativeOnly(q);
  const limits = [];

  if (
    q.indexOf("review first") >= 0 ||
    q.indexOf("what should i review first") >= 0 ||
    q.indexOf("where should i start") >= 0
  ) {
    return { intent: ASSISTANT_INTENTS.review_first, confidence: 1, query: q, topN, categoryTerm, negativeOnly, limits };
  }
  if (
    q.indexOf("how confident") >= 0 ||
    q.indexOf("confidence") >= 0 ||
    q.indexOf("can i trust") >= 0 ||
    q.indexOf("reliable") >= 0
  ) {
    return { intent: ASSISTANT_INTENTS.confidence, confidence: 1, query: q, topN, categoryTerm, negativeOnly, limits };
  }
  if (categoryTerm && (q.indexOf("main risk") >= 0 || q.indexOf("main issue") >= 0)) {
    return { intent: ASSISTANT_INTENTS.category_filter, confidence: 0.95, query: q, topN, categoryTerm, negativeOnly, limits };
  }
  if (q.indexOf("risk") >= 0 || q.indexOf("red flag") >= 0) {
    return { intent: ASSISTANT_INTENTS.risk, confidence: 1, query: q, topN, categoryTerm, negativeOnly, limits };
  }
  if (
    q.indexOf("revenue issue or cost issue") >= 0 ||
    q.indexOf("revenue vs cost") >= 0 ||
    q.indexOf("cost vs revenue") >= 0 ||
    q.indexOf("revenue offset cost growth") >= 0 ||
    q.indexOf("revenue offset the cost growth") >= 0
  ) {
    return { intent: ASSISTANT_INTENTS.cost_vs_revenue, confidence: 1, query: q, topN, categoryTerm, negativeOnly, limits };
  }
  if (
    q.indexOf("profit driver") >= 0 ||
    q.indexOf("why did profit") >= 0 ||
    q.indexOf("profit drop") >= 0 ||
    q.indexOf("profit down") >= 0 ||
    q.indexOf("hurting us most") >= 0
  ) {
    return { intent: ASSISTANT_INTENTS.profit_driver, confidence: 1, query: q, topN, categoryTerm, negativeOnly, limits };
  }
  if (
    q.indexOf("top") >= 0 ||
    q.indexOf("changed most") >= 0 ||
    q.indexOf("biggest changes") >= 0 ||
    q.indexOf("largest changes") >= 0 ||
    q.indexOf("biggest movers") >= 0 ||
    (negativeOnly && (q.indexOf("movement") >= 0 || q.indexOf("change") >= 0))
  ) {
    return { intent: ASSISTANT_INTENTS.top_changes, confidence: 1, query: q, topN, categoryTerm, negativeOnly, limits };
  }
  if (
    categoryTerm ||
    q.indexOf("cost increase") >= 0 ||
    q.indexOf("cost increases") >= 0 ||
    q.indexOf("show me") >= 0 ||
    q.indexOf("main issue") >= 0
  ) {
    if (!categoryTerm) limits.push("I detected a category filter request but no clear category token.");
    return {
      intent: ASSISTANT_INTENTS.category_filter,
      confidence: categoryTerm ? 1 : 0.72,
      query: q,
      topN,
      categoryTerm,
      negativeOnly,
      limits,
    };
  }
  if (q.indexOf("comparison overview") >= 0 || q.indexOf("overall comparison") >= 0 || q.indexOf("what happened overall") >= 0) {
    return { intent: ASSISTANT_INTENTS.comparison_overview, confidence: 1, query: q, topN, categoryTerm, negativeOnly, limits };
  }
  if (q.indexOf("summary") >= 0 || q.indexOf("summarize") >= 0 || q.indexOf("quick recap") >= 0) {
    return { intent: ASSISTANT_INTENTS.summary, confidence: 1, query: q, topN, categoryTerm, negativeOnly, limits };
  }
  if (q.indexOf("what changed") >= 0 || q.indexOf("what moved") >= 0) {
    return { intent: ASSISTANT_INTENTS.top_changes, confidence: 0.8, query: q, topN, categoryTerm, negativeOnly, limits };
  }
  return { intent: null, confidence: 0, query: q, topN, categoryTerm, negativeOnly, limits };
}

function buildEvidence(items, maxItems) {
  const out = (items || []).filter(Boolean).slice(0, Math.min(maxItems || 4, 4));
  while (out.length < 2) {
    out.push("No additional deterministic evidence is available for this question.");
  }
  return out;
}

function supportedQuestionExamples() {
  return [
    "why did profit drop",
    "what changed most",
    "show me labor only",
    "top 10 changes",
    "show only negative movements",
    "is labor the main issue",
    "did revenue offset the cost growth",
    "what should worry me",
  ];
}

function buildUnsupportedResponse(limitText) {
  const limitLine = limitText ? "Limit: " + limitText : "Limit: this phrasing does not map cleanly to a supported question pattern.";
  return {
    intent: "unsupported",
    directAnswer:
      "I can only answer supported question types for the active run, and this question was not specific enough.",
    evidence: buildEvidence(
      [
        limitLine,
        "Supported patterns: summary, top changes, category filter, cost vs revenue, profit driver, risk, review first, confidence, comparison overview.",
        "Numeric drilldowns: top 3, top 5, top 10.",
        "Category drilldowns: show me labor only, is labor the main issue.",
      ],
      4
    ),
    nextLook: "Ask one concrete question type so the answer ties directly to this run's evidence.",
    listTitle: "Supported question types",
    listItems: supportedQuestionExamples(),
  };
}

function buildPartiallyUnderstoodResponse(route, executed) {
  const base = buildIntentResponse({ ...route, confidence: 1 }, executed);
  const limit = (route.limits && route.limits[0]) || "I matched part of your question but not every detail.";
  base.evidence = buildEvidence([limit].concat(base.evidence || []), 4);
  base.nextLook = "Refine with a specific category for a tighter deterministic answer.";
  base.listTitle = "Useful follow-ups";
  base.listItems = supportedQuestionExamples().slice(0, 5);
  return base;
}

function normalizeForMatch(text) {
  return normalizeQuestion(text || "");
}

function categoryMatchInfo(label, term) {
  const labelNorm = normalizeForMatch(label);
  const termNorm = normalizeForMatch(term);
  if (!termNorm) return { match: false, score: 0 };
  if (labelNorm.indexOf(termNorm) >= 0) return { match: true, score: 1 };
  const termTokens = termNorm.split(" ").filter(Boolean);
  if (termTokens.length > 1 && termTokens.every((t) => labelNorm.indexOf(t) >= 0)) return { match: true, score: 0.75 };
  if (termTokens.some((t) => labelNorm.indexOf(t) >= 0)) return { match: true, score: 0.55 };
  return { match: false, score: 0 };
}

function getAssistantData(executed) {
  const so = (executed && executed.structured_output) || {};
  const rows = Array.isArray(so.material_diff_items) ? so.material_diff_items.slice() : [];
  const sd = so.summary_deltas || {};
  const roll = so.extraction_confidence || null;
  const isFin = !!executed && executed.workflow === "wf_financial_markdown_delta";
  const structOk = isFin && isStructuredFinancial(so);
  return { so, rows, sd, roll, isFin, structOk };
}

function buildSummaryResponse(executed, data) {
  const top = sortedByAbsDelta(data.rows)[0];
  const profit = data.sd.profit;
  const direct =
    profit === undefined || profit === null
      ? "Profit summary is unavailable for this run, but material line movement is available."
      : "Profit is " + fmtMoneySigned(profit) + " versus prior based on summary deltas.";
  return {
    intent: ASSISTANT_INTENTS.summary,
    directAnswer: direct,
    scopeLabel: "Summary view",
    evidence: buildEvidence([
      "Revenue delta: " + fmtMoneySigned(data.sd.revenue) + ".",
      "Cost delta: " + fmtMoneySigned(data.sd.cost) + ".",
      top ? "Largest absolute line move: " + (top.category_label || top.category || "category") + " (" + fmtMoneySigned(top.delta) + ")." : "",
      "Primary material lines: " + String(data.so.material_diff_line_count || 0) + ".",
    ], 4),
    nextLook: "Start at the top mover row in all lines, then reconcile it back to the profit direction.",
    tableRows: sortedByAbsDelta(data.rows).slice(0, 5),
    tableTitle: "Largest line movements",
  };
}

function buildComparisonOverviewResponse(data) {
  const top = sortedByAbsDelta(data.rows)[0];
  const direct =
    data.structOk
      ? "This comparison has structured tables and line-level deltas ready for review."
      : "This comparison is partially structured, so treat category deltas as directional.";
  return {
    intent: ASSISTANT_INTENTS.comparison_overview,
    directAnswer: direct,
    scopeLabel: "Comparison overview",
    evidence: buildEvidence([
      "Profit delta: " + fmtMoneySigned(data.sd.profit) + ".",
      "Revenue delta: " + fmtMoneySigned(data.sd.revenue) + "; cost delta: " + fmtMoneySigned(data.sd.cost) + ".",
      "Extraction rollup: " + (data.roll && data.roll.rollup ? data.roll.rollup : "not available") + ".",
      top ? "Largest line move: " + (top.category_label || top.category || "category") + " (" + fmtMoneySigned(top.delta) + ")." : "",
    ], 4),
    nextLook: "Scan spotlight first, then validate magnitude in the line table before closing the review.",
    tableRows: sortedByAbsDelta(data.rows).slice(0, 5),
    tableTitle: "Overview line movements",
  };
}

function buildTopChangesResponse(data, topN, negativeOnly) {
  const source = negativeOnly ? data.rows.filter((r) => Number(r.delta || 0) < 0) : data.rows.slice();
  const rows = sortedByAbsDelta(source).slice(0, topN);
  const top = rows[0];
  return {
    intent: ASSISTANT_INTENTS.top_changes,
    directAnswer: top
      ? "Largest " + (negativeOnly ? "negative " : "") + "mover is " + (top.category_label || top.category || "category") + " at " + fmtMoneySigned(top.delta) + "."
      : "No " + (negativeOnly ? "negative " : "") + "material line changes are available for this run.",
    scopeLabel: (negativeOnly ? "Top " + String(rows.length) + " negative changes" : "Top " + String(rows.length) + " changes"),
    evidence: buildEvidence([
      "Requested top count: " + String(topN) + ".",
      "Candidate rows considered: " + String(source.length) + ".",
      rows[1]
        ? "Second-largest move: " + (rows[1].category_label || rows[1].category || "category") + " (" + fmtMoneySigned(rows[1].delta) + ")."
        : "",
      "Profit delta context: " + fmtMoneySigned(data.sd.profit) + ".",
    ], 4),
    nextLook: negativeOnly
      ? "Inspect these negative lines in all lines first to confirm whether they are recurring."
      : "Validate whether the top moves are repeatable or one-off before actioning them.",
    tableRows: rows,
    tableTitle: (negativeOnly ? "Top negative changes (limit " : "Top changes (limit ") + String(topN) + ")",
  };
}

function buildCategoryFilterResponse(data, route) {
  const q = route.query;
  const byCostIncrease = q.indexOf("cost increase") >= 0 || q.indexOf("cost increases") >= 0;
  const term = route.categoryTerm || "";
  if (!byCostIncrease && !term) {
    return {
      intent: ASSISTANT_INTENTS.category_filter,
      directAnswer: "I recognized a filter-style request, but no clear category token was identified.",
      scopeLabel: "0 matching categories",
      evidence: buildEvidence([
        "Recognized pattern: category filter.",
        "Limit: category token missing (for example labor, material, cost, revenue).",
        "Material lines available: " + String(data.so.material_diff_line_count || 0) + ".",
      ], 4),
      nextLook: "Retry with a specific category phrase such as 'show me labor only'.",
      listTitle: "Try these filters",
      listItems: ["show me labor only", "is material the main issue", "show only negative movements"],
    };
  }
  let rows = data.rows.map((row) => {
    const label = row.category_label || row.category || "";
    const info = categoryMatchInfo(label, term);
    return { row, score: info.score, match: info.match };
  });
  if (byCostIncrease) {
    rows = rows.filter((entry) => {
      const label = driverCategoryLabel(entry.row);
      return (label.indexOf("cost") >= 0 || label.indexOf("expense") >= 0) && Number(entry.row.delta) > 0;
    });
  } else if (term) {
    rows = rows.filter((entry) => entry.match);
  }
  if (route.negativeOnly) {
    rows = rows.filter((entry) => Number(entry.row.delta || 0) < 0);
  }
  rows = rows
    .sort((a, b) => b.score - a.score || Math.abs(Number(b.row.delta || 0)) - Math.abs(Number(a.row.delta || 0)))
    .slice(0, 12);
  const fuzzyRows = rows.filter((entry) => entry.score > 0 && entry.score < 1).length;
  const tableRows = rows.map((entry) => entry.row);
  const scope = byCostIncrease ? "cost increases" : (term || "requested category");
  return {
    intent: ASSISTANT_INTENTS.category_filter,
    directAnswer:
      tableRows.length > 0
        ? "Found " + String(tableRows.length) + " matching categories for '" + scope + "'" + (fuzzyRows ? " (some fuzzy matches)." : ".")
        : "No material lines matched " + scope + " in this run.",
    scopeLabel: String(tableRows.length) + " matching categories",
    evidence: buildEvidence([
      byCostIncrease ? "Filter rule: cost/expense categories with positive deltas." : "Filter rule: category contains '" + scope + "'.",
      tableRows[0]
        ? "Largest match: " + (tableRows[0].category_label || tableRows[0].category || "category") + " (" + fmtMoneySigned(tableRows[0].delta) + ")."
        : "No filtered rows crossed the material list.",
      fuzzyRows ? String(fuzzyRows) + " rows are fuzzy token matches; verify labels in all lines." : "All shown matches are direct token hits.",
      "Total material lines available: " + String(data.so.material_diff_line_count || 0) + ".",
    ], 4),
    nextLook: "Use all lines filter with '" + scope + "' to confirm naming precision before drawing conclusions.",
    tableRows: tableRows,
    tableTitle: "Filtered line set: " + scope,
  };
}

function buildCostVsRevenueResponse(data) {
  const rev = Number(data.sd.revenue || 0);
  const cost = Number(data.sd.cost || 0);
  const costMagnitude = Math.abs(cost);
  const revMagnitude = Math.abs(rev);
  const side = costMagnitude > revMagnitude ? "cost-led" : revMagnitude > costMagnitude ? "revenue-led" : "balanced";
  const direct =
    side === "cost-led"
      ? "This looks more cost-driven than revenue-driven."
      : side === "revenue-led"
        ? "This looks more revenue-driven than cost-driven."
        : "Revenue and cost movement are similar in magnitude.";
  return {
    intent: ASSISTANT_INTENTS.cost_vs_revenue,
    directAnswer: direct,
    scopeLabel: side === "balanced" ? "Balanced signal" : side === "cost-led" ? "Cost-led signal" : "Revenue-led signal",
    evidence: buildEvidence([
      "Revenue delta: " + fmtMoneySigned(rev) + ".",
      "Cost delta: " + fmtMoneySigned(cost) + ".",
      "Profit delta: " + fmtMoneySigned(data.sd.profit) + ".",
      "Magnitude check: |revenue| " + fmtMoneyPlain(revMagnitude) + " vs |cost| " + fmtMoneyPlain(costMagnitude) + ".",
    ], 4),
    nextLook: "Check whether one category dominates the larger side before attributing root cause.",
    tableRows: sortedByAbsDelta(data.rows).slice(0, 6),
    tableTitle: "Largest lines behind revenue/cost movement",
  };
}

function buildProfitDriverResponse(data) {
  const profit = Number(data.sd.profit || 0);
  const rev = Number(data.sd.revenue || 0);
  const cost = Number(data.sd.cost || 0);
  const topRows = sortedByAbsDelta(data.rows);
  const top = topRows[0];
  const revenueSupports = rev > 0;
  const costSupports = cost <= 0;
  let driver = "mixed movement";
  if (profit < 0) driver = cost > 0 ? "cost increase pressure" : rev < 0 ? "revenue decline pressure" : "mixed downward pressure";
  if (profit > 0) driver = revenueSupports || costSupports ? "favorable revenue/cost mix" : "mixed upward pressure";
  return {
    intent: ASSISTANT_INTENTS.profit_driver,
    directAnswer:
      "Profit moved " + fmtMoneySigned(profit) + "; the strongest deterministic signal points to " + driver + ".",
    scopeLabel: "Profit driver view",
    evidence: buildEvidence([
      "Revenue delta: " + fmtMoneySigned(rev) + ".",
      "Cost delta: " + fmtMoneySigned(cost) + ".",
      "Largest absolute line move: " +
        ((top && (top.category_label || top.category)) || "n/a") +
        (top ? " (" + fmtMoneySigned(top.delta) + ")." : "."),
      "Structured financial availability: " + (data.structOk ? "yes" : "limited") + ".",
    ], 4),
    nextLook: "Validate this driver in source schedules to separate recurring pressure from one-off noise.",
    tableRows: topRows.slice(0, 8),
    tableTitle: "Likely profit drivers",
  };
}

function buildRiskResponse(executed, data) {
  const risks = deriveRiskSignals(executed);
  return {
    intent: ASSISTANT_INTENTS.risk,
    directAnswer: risks[0] || "No high-risk deterministic signal is currently flagged.",
    scopeLabel: String(risks.filter(Boolean).length) + " main risk signals",
    evidence: buildEvidence([
      risks[0] || "",
      risks[1] || "",
      "Extraction rollup: " + (data.roll && data.roll.rollup ? data.roll.rollup : "not available") + ".",
      "Material line count: " + String(data.so.material_diff_line_count || 0) + ".",
    ], 4),
    nextLook: "Prioritize confidence and extraction detail to verify whether read quality is amplifying risk.",
    tableRows: sortedByAbsDelta(data.rows).slice(0, 6),
    tableTitle: "Largest lines to risk-check",
  };
}

function buildReviewFirstResponse(executed, data) {
  const review = (executed && executed.what_to_review) || [];
  const changed = (executed && executed.summary) || [];
  const topRows = sortedByAbsDelta(data.rows);
  const top = topRows[0];
  return {
    intent: ASSISTANT_INTENTS.review_first,
    directAnswer:
      review.length > 0
        ? "Review priority starts with: " + String(review[0])
        : "Start with the top spotlight card, then open all lines for detail.",
    scopeLabel: String(Math.min(review.length, 6)) + " review priorities",
    evidence: buildEvidence([
      review[0] ? "Priority 1: " + String(review[0]) : "",
      review[1] ? "Priority 2: " + String(review[1]) : "",
      changed[0] ? "Context: " + String(changed[0]) : "",
      "Largest absolute line move: " +
        ((top && (top.category_label || top.category)) || "n/a") +
        (top ? " (" + fmtMoneySigned(top.delta) + ")." : "."),
    ], 4),
    nextLook: "Open 'What changed' first, then validate each priority against line deltas.",
    listTitle: "Review-first checklist",
    listItems: review.slice(0, 6),
  };
}

function buildConfidenceResponse(data) {
  const rollup = data.roll && data.roll.rollup ? String(data.roll.rollup) : "unknown";
  const direct =
    rollup.toLowerCase() === "high"
      ? "Confidence is high for this read."
      : rollup.toLowerCase() === "medium"
        ? "Confidence is medium; use normal analyst validation."
        : rollup.toLowerCase() === "low"
          ? "Confidence is low; treat this as directional only."
          : "Confidence metadata is limited for this run.";
  return {
    intent: ASSISTANT_INTENTS.confidence,
    directAnswer: direct,
    scopeLabel: "Confidence " + rollup,
    evidence: buildEvidence([
      "Extraction rollup: " + rollup + ".",
      "Structured financial availability: " + (data.structOk ? "yes" : "limited") + ".",
      "Profit delta present: " + (data.sd.profit === undefined || data.sd.profit === null ? "no" : "yes") + ".",
      "Material line count: " + String(data.so.material_diff_line_count || 0) + ".",
    ], 4),
    nextLook: "Use the trust panel before relying on small movements or low-score categories.",
  };
}

function buildIntentResponse(route, executed) {
  const data = getAssistantData(executed);
  switch (route.intent) {
    case ASSISTANT_INTENTS.summary:
      return buildSummaryResponse(executed, data);
    case ASSISTANT_INTENTS.top_changes:
      return buildTopChangesResponse(data, route.topN || 5, !!route.negativeOnly);
    case ASSISTANT_INTENTS.category_filter:
      return buildCategoryFilterResponse(data, route);
    case ASSISTANT_INTENTS.cost_vs_revenue:
      return buildCostVsRevenueResponse(data);
    case ASSISTANT_INTENTS.profit_driver:
      return buildProfitDriverResponse(data);
    case ASSISTANT_INTENTS.risk:
      return buildRiskResponse(executed, data);
    case ASSISTANT_INTENTS.review_first:
      return buildReviewFirstResponse(executed, data);
    case ASSISTANT_INTENTS.confidence:
      return buildConfidenceResponse(data);
    case ASSISTANT_INTENTS.comparison_overview:
      return buildComparisonOverviewResponse(data);
    default:
      return buildUnsupportedResponse();
  }
}

function highlightAssistantLinked(el) {
  if (!el) return;
  el.classList.add("assistant-linked");
  setTimeout(() => el.classList.remove("assistant-linked"), 1600);
}

function linkAssistantToSurface(intent) {
  if (
    intent === ASSISTANT_INTENTS.top_changes ||
    intent === ASSISTANT_INTENTS.category_filter ||
    intent === ASSISTANT_INTENTS.profit_driver ||
    intent === ASSISTANT_INTENTS.cost_vs_revenue
  ) {
    const lines = document.getElementById("details-all-lines");
    if (lines) lines.open = true;
    const section = document.getElementById("section-drivers");
    if (section) section.scrollIntoView({ behavior: "smooth", block: "start" });
    highlightAssistantLinked(document.getElementById("driver-spotlight-cards"));
    highlightAssistantLinked(document.getElementById("drivers-primary"));
    if (intent === ASSISTANT_INTENTS.cost_vs_revenue) {
      const hero = document.getElementById("answer-hero");
      if (hero) hero.scrollIntoView({ behavior: "smooth", block: "nearest" });
      highlightAssistantLinked(hero);
      highlightAssistantLinked(document.getElementById("financial-cards"));
    }
    return;
  }
  if (intent === ASSISTANT_INTENTS.confidence) {
    const trust = document.getElementById("details-trust");
    if (trust) trust.open = true;
    const extraction = document.getElementById("details-extraction");
    if (extraction) extraction.open = true;
    const block = document.getElementById("extraction-confidence-block");
    if (block) block.scrollIntoView({ behavior: "smooth", block: "nearest" });
    highlightAssistantLinked(block);
    return;
  }
  if (intent === ASSISTANT_INTENTS.risk) {
    const trust = document.getElementById("details-trust");
    if (trust) trust.open = true;
    const block = document.getElementById("assistant-rail");
    if (block) block.scrollIntoView({ behavior: "smooth", block: "nearest" });
    highlightAssistantLinked(document.getElementById("sec-why"));
    highlightAssistantLinked(document.getElementById("extraction-confidence-block"));
    return;
  }
  if (intent === ASSISTANT_INTENTS.review_first) {
    const insights = document.getElementById("details-insights");
    if (insights) insights.open = true;
    const review = document.getElementById("review-list");
    if (review) review.scrollIntoView({ behavior: "smooth", block: "nearest" });
    highlightAssistantLinked(review);
    return;
  }
  if (intent === ASSISTANT_INTENTS.summary || intent === ASSISTANT_INTENTS.comparison_overview) {
    const hero = document.getElementById("answer-hero");
    if (hero) hero.scrollIntoView({ behavior: "smooth", block: "nearest" });
    highlightAssistantLinked(hero);
    highlightAssistantLinked(document.getElementById("financial-cards"));
  }
}

function renderAssistantResponse(result) {
  const host = document.getElementById("assistant-response");
  host.innerHTML = "";
  if (!result) {
    host.classList.add("hidden");
    return;
  }
  host.classList.remove("hidden");

  const intentTag = document.createElement("p");
  intentTag.className = "assistant-response-title";
  intentTag.textContent = "Decision path: " + String(result.intent || "—");
  host.appendChild(intentTag);

  if (result.scopeLabel) {
    const scope = document.createElement("p");
    scope.className = "assistant-response-meta";
    scope.textContent = String(result.scopeLabel);
    host.appendChild(scope);
  }

  const directLabel = document.createElement("p");
  directLabel.className = "assistant-response-label";
  directLabel.textContent = "Direct answer";
  host.appendChild(directLabel);

  const direct = document.createElement("p");
  direct.className = "assistant-response-text";
  direct.textContent = result.directAnswer || "No deterministic answer available.";
  host.appendChild(direct);

  const evidenceLabel = document.createElement("p");
  evidenceLabel.className = "assistant-response-label";
  evidenceLabel.textContent = "Evidence";
  host.appendChild(evidenceLabel);

  const evidence = document.createElement("ul");
  evidence.className = "assistant-response-list";
  (result.evidence || []).slice(0, 4).forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    evidence.appendChild(li);
  });
  host.appendChild(evidence);

  const nextLabel = document.createElement("p");
  nextLabel.className = "assistant-response-label";
  nextLabel.textContent = "Next look";
  host.appendChild(nextLabel);

  const next = document.createElement("p");
  next.className = "assistant-response-next";
  next.textContent = result.nextLook || "Continue in the line table for verification.";
  host.appendChild(next);

  if (result.listItems && result.listItems.length) {
    const listTitle = document.createElement("p");
    listTitle.className = "assistant-response-label";
    listTitle.textContent = result.listTitle || "Supporting list";
    host.appendChild(listTitle);
    const supportList = document.createElement("ul");
    supportList.className = "assistant-response-list";
    result.listItems.forEach((line) => {
      const li = document.createElement("li");
      li.textContent = line;
      supportList.appendChild(li);
    });
    host.appendChild(supportList);
  }

  if (result.tableRows && result.tableRows.length) {
    const tableTitle = document.createElement("p");
    tableTitle.className = "assistant-response-label";
    tableTitle.textContent = result.tableTitle || "Supporting lines";
    host.appendChild(tableTitle);
    const wrap = document.createElement("div");
    wrap.className = "drivers-table-wrap";
    const table = document.createElement("table");
    table.className = "drivers-table assistant-response-table data-table drivers-table--decision";
    table.innerHTML = `
      <thead>
        <tr>
          <th scope="col" class="col-rank">#</th>
          <th scope="col">Line / category</th>
          <th scope="col">Original</th>
          <th scope="col">Current</th>
          <th scope="col">Δ ($)</th>
          <th scope="col">Δ (%)</th>
          <th scope="col">Tier</th>
        </tr>
      </thead>
      <tbody></tbody>
      <tfoot class="drivers-table__foot data-table__foot">
        <tr>
          <td class="foot-label" colspan="2">Total</td>
          <td class="num foot-orig">—</td>
          <td class="num foot-cur">—</td>
          <td class="num foot-d">—</td>
          <td class="num foot-p">—</td>
          <td class="foot-meta">—</td>
        </tr>
      </tfoot>
    `;
    const tbody = table.querySelector("tbody");
    const trows = result.tableRows || [];
    const rmap = buildImpactRankMap(trows);
    let so = 0;
    let sc = 0;
    let snet = 0;
    trows.forEach((row) => {
      so += numOrNull(row.prior_value) != null ? Number(row.prior_value) : 0;
      sc += numOrNull(row.current_value) != null ? Number(row.current_value) : 0;
      snet += rowBudgetDeltaValue(row);
    });
    const nPct = so !== 0 ? (sc - so) / so : null;
    trows.forEach((row) => {
      const tr = document.createElement("tr");
      setDriverDataRowAttributes(tr, row);
      const cat = row.category_label || row.category || "";
      const tier = row.tier || "";
      const dv = rowBudgetDeltaValue(row);
      const pctv = rowBudgetDeltaPct(row);
      const rk = rmap.get(driverRowKey(row)) || "—";
      tr.innerHTML = `
        <td class="col-rank"><span class="impact-rank">${String(rk)}</span></td>
        <td class="driver-line-cell">${escapeHtml(String(cat))}</td>
        <td class="num">${fmtMoneyPlain(row.prior_value)}</td>
        <td class="num">${fmtMoneyPlain(row.current_value)}</td>
        <td class="num cell-delta-usd">${fmtDeltaUsdCell(dv)}</td>
        <td class="num cell-delta-pct">${fmtDeltaPctCell(pctv)}</td>
        <td><span class="tier-pill ${tierClass(tier)}">${escapeHtml(String(tier))}</span></td>
      `;
      tbody.appendChild(tr);
    });
    const tfoot = table.querySelector("tfoot tr");
    if (tfoot && trows.length) {
      tfoot.querySelector(".foot-orig").textContent = fmtMoneyPlain(so);
      tfoot.querySelector(".foot-cur").textContent = fmtMoneyPlain(sc);
      tfoot.querySelector(".foot-d").innerHTML = fmtDeltaUsdCell(snet);
      tfoot.querySelector(".foot-p").innerHTML = nPct == null ? "—" : fmtDeltaPctCell(nPct);
      const top5 = trows.slice().sort((a, b) => absBudgetDelta(b) - absBudgetDelta(a)).slice(0, 5);
      const absSum = trows.reduce((s, r) => s + absBudgetDelta(r), 0);
      const t5 = top5.reduce((s, r) => s + absBudgetDelta(r), 0);
      const tps = absSum > 0 ? (t5 / absSum) * 100 : 0;
      tfoot.querySelector(".foot-meta").textContent = "Top 5 |Δ| share: " + tps.toFixed(1) + "%";
    } else if (tfoot) {
      tfoot.parentElement.remove();
    }
    wrap.appendChild(table);
    host.appendChild(wrap);
  }

  linkAssistantToSurface(result.intent);
}

function interpretAssistantQuery(rawQuery, executed) {
  const route = classifyAssistantIntent(rawQuery);
  if (!route.intent) return buildUnsupportedResponse();
  if (route.confidence < 0.75) return buildPartiallyUnderstoodResponse(route, executed);
  return buildIntentResponse(route, executed);
}

function setupAssistantQuery() {
  const form = document.getElementById("assistant-query-form");
  const input = document.getElementById("assistant-query-input");
  const chips = document.getElementById("assistant-prompt-chips");
  if (!form || !input) return;

  const runAssistant = (query) => {
    if (!lastRunPayload) {
      renderAssistantResponse({
        intent: "no_run",
        directAnswer: "Run a compare first before asking assistant questions.",
        evidence: ["Assistant responses are computed from the active run only.", "No backend query is made from this input."],
        nextLook: "Load files and execute compare, then retry the same question.",
      });
      return;
    }
    const result = interpretAssistantQuery(query, lastRunPayload);
    renderAssistantResponse(result);
  };

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    runAssistant(input.value);
  });

  if (chips) {
    chips.addEventListener("click", (ev) => {
      const btn = ev.target.closest("button.assistant-chip");
      if (!btn) return;
      const query = btn.dataset.query || "";
      input.value = query;
      runAssistant(query);
    });
  }
}

function owbDebugEnabled() {
  try {
    if (new URLSearchParams(window.location.search).get("owbDebug") === "1") return true;
    if (window.localStorage && window.localStorage.getItem("owbDebug") === "1") return true;
  } catch (e) {
    /* ignore */
  }
  return false;
}

function analysisTypeExpectsWorkbench(at) {
  const a = String(at || "");
  return (
    a === "current_profit_snapshot" ||
    a === "projected_profit_breakdown" ||
    a === "labor_rate_profit_analysis" ||
    a === "compare_two_reports" ||
    a === "cost_movement_signals" ||
    a === "trend_across_reports"
  );
}

function reviewQueueSeverityRank(s) {
  const o = { CRITICAL: 0, HIGH: 1, WATCH: 2, MEDIUM: 3, LOW: 4, INFO: 5 };
  return o[String(s || "").toUpperCase()] != null ? o[String(s).toUpperCase()] : 3;
}

function buildReviewQueueItemsFromFinancialSignals(fs) {
  const items = [];
  if (!fs || typeof fs !== "object") return items;
  const wps = fs.workbook_profit_summary || {};
  const at = (fs && fs.analysis_type) || "";
  const wb = fs.financial_workbench;
  const varRaw = wps.projected_profit_variance;
  const vNum = varRaw != null && varRaw !== "" ? Number(varRaw) : NaN;
  if (Number.isFinite(vNum) && Math.abs(vNum) >= 0.02) {
    items.push({
      severity: Math.abs(vNum) >= 1000 ? "HIGH" : "WATCH",
      issue: "Formula vs workbook TPP variance is non-zero",
      why: "Headline profit in the workbook may not match rolled formula components — bridge before signing.",
      action: "reconciliation",
      actionLabel: "Open reconciliation",
    });
  }
  const tpp = numOrNull(wps.total_projected_profit);
  const wbook = numOrNull(wps.workbook_reported_total_projected_profit);
  if (tpp == null && wbook == null) {
    items.push({
      severity: "HIGH",
      issue: "Missing profit summary lines",
      why: "Total projected profit and workbook-reported TPP were not found in this extract.",
      action: "workbench",
      actionLabel: "Inspect workbench",
    });
  }
  const lim = wps.projected_profit_limitations;
  if (Array.isArray(lim) && lim.length) {
    items.push({
      severity: "WATCH",
      issue: "Profit extraction limitations",
      why: lim.slice(0, 2).join(" · "),
      action: "signals-limits",
      actionLabel: "Source notes",
    });
  }
  (fs.largest_movers || []).slice(0, 3).forEach((m) => {
    const d = numOrNull(m.delta);
    if (d != null && Math.abs(d) >= 10000) {
      items.push({
        severity: Math.abs(d) >= 250000 ? "HIGH" : "WATCH",
        issue: "High movement: " + (m.label || m.key || "cost line"),
        why: "Large period movement on a cost code warrants tie-out to JTD and CO detail.",
        action: "workbench",
        actionLabel: "JTD Cost Codes",
      });
    }
  });
  const oco = numOrNull(wps.owner_change_orders_value);
  const cco = numOrNull(wps.cm_change_orders_value);
  const wpsd = fs.workbook_profit_summary_deltas || {};
  const dOco = numOrNull(wpsd.owner_change_orders_value);
  const dCco = numOrNull(wpsd.cm_change_orders_value);
  if (dOco != null && Math.abs(dOco) >= 250000) {
    items.push({
      severity: "HIGH",
      issue: "Owner change order movement",
      why: "Owner CO dollars moved materially period-over-period — confirm scope and JTD mapping.",
      action: "change_orders",
      actionLabel: "Change Orders tab",
    });
  } else if (oco != null && analysisTypeExpectsWorkbench(at)) {
    items.push({
      severity: "MEDIUM",
      issue: "Validate owner change orders",
      why: "Owner CO balance " + fmtMoneyPlain(oco) + " — confirm against contract log.",
      action: "change_orders",
      actionLabel: "Change Orders tab",
    });
  }
  if (dCco != null && Math.abs(dCco) >= 250000) {
    items.push({
      severity: "HIGH",
      issue: "CM change order movement",
      why: "CM CO dollars moved materially — check internal vs owner-visible CO treatment.",
      action: "change_orders",
      actionLabel: "Change Orders tab",
    });
  } else if (cco != null && analysisTypeExpectsWorkbench(at)) {
    items.push({
      severity: "MEDIUM",
      issue: "Validate CM change orders",
      why: "CM CO balance " + fmtMoneyPlain(cco) + ".",
      action: "change_orders",
      actionLabel: "Change Orders tab",
    });
  }
  const dLrp = numOrNull(wpsd.labor_rate_profit_to_date);
  if (dLrp != null && Math.abs(dLrp) >= 100000) {
    items.push({
      severity: "HIGH",
      issue: "Labor rate profit movement",
      why: "LRP changed materially — billed vs actual mix may be shifting forecast.",
      action: "lrp",
      actionLabel: "LRP Breakdown tab",
    });
  }
  if (!financialWorkbenchHasUsefulData(wb) && analysisTypeExpectsWorkbench(at)) {
    items.push({
      severity: "CRITICAL",
      issue: "Workbench / extraction incomplete",
      why: "JTD, CO, LRP, or reconciliation tables did not populate — mapping or sheet layout may be missing.",
      action: "workbench",
      actionLabel: "See failure panel",
    });
  }
  const roll = (fs.extraction_confidence && fs.extraction_confidence.rollup) || "";
  if (String(roll).toLowerCase() === "low") {
    items.push({
      severity: "WATCH",
      issue: "Low extraction confidence",
      why: "Structured read quality is low — treat numbers as provisional until evidence is checked.",
      action: "extraction",
      actionLabel: "Source detail",
    });
  }
  return items;
}

function buildReviewQueueItemsFromCompare(sig, av) {
  const items = [];
  if (!sig || !sig.signal_summary) return items;
  if (sig.signal_summary.signal_type === "LOW_SIGNAL" && window.__OWB_LAST_FS) return items;
  const g = buildGuidanceFromSignalAndRun(sig, av || {});
  (g.primary || []).forEach((line) => {
    items.push({
      severity: "CRITICAL",
      issue: line,
      why: "Primary focus from the structured compare signal.",
      action: "drivers",
      actionLabel: "Line movements",
    });
  });
  (g.why || []).slice(0, 3).forEach((line) => {
    items.push({
      severity: "HIGH",
      issue: line,
      why: "Context for why the movement matters to forecast and risk.",
      action: "top",
      actionLabel: "What changed",
    });
  });
  (g.checks || []).slice(0, 5).forEach((line) => {
    items.push({
      severity: "MEDIUM",
      issue: line,
      why: "Concrete check suggested from engine review actions.",
      action: "drivers",
      actionLabel: "Open drivers",
    });
  });
  (g.confNotes || []).slice(0, 4).forEach((line) => {
    items.push({
      severity: "WATCH",
      issue: line,
      why: "Read quality and traceability note.",
      action: "extraction",
      actionLabel: "Extraction detail",
    });
  });
  (av && av.extraction_notes ? av.extraction_notes : []).forEach((line) => {
    items.push({
      severity: "WATCH",
      issue: String(line),
      why: "Extraction warning from the run envelope.",
      action: "extraction",
      actionLabel: "Evidence",
    });
  });
  return items;
}

function mergeAndSortReviewQueueItems(a, b) {
  const key = (it) => String(it.issue || "") + "|" + String(it.why || "");
  const seen = new Set();
  const out = [];
  []
    .concat(a || [], b || [])
    .forEach((it) => {
      const k = key(it);
      if (seen.has(k)) return;
      seen.add(k);
      out.push(it);
    });
  out.sort((x, y) => reviewQueueSeverityRank(x.severity) - reviewQueueSeverityRank(y.severity));
  return out;
}

function runReviewQueueAction(action) {
  const wb = document.getElementById("financial-workbench-embed");
  if (action === "workbench" && wb) {
    wb.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (action === "reconciliation" || action === "variance") {
    if (typeof workbenchViewApi !== "undefined" && workbenchViewApi && workbenchViewApi.applyComponentLink) {
      workbenchViewApi.applyComponentLink("variance");
    }
    if (wb) wb.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (action === "change_orders") {
    if (typeof workbenchViewApi !== "undefined" && workbenchViewApi && workbenchViewApi.applyComponentLink) {
      workbenchViewApi.applyComponentLink("change_orders");
    }
    if (wb) wb.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (action === "lrp") {
    if (typeof workbenchViewApi !== "undefined" && workbenchViewApi && workbenchViewApi.applyComponentLink) {
      workbenchViewApi.applyComponentLink("labor_rate_profit_to_date");
    }
    if (wb) wb.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (action === "signals-limits") {
    const lim = document.querySelector("#financial-signals details.signals-limits");
    if (lim) {
      lim.open = true;
      lim.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    return;
  }
  if (action === "extraction") {
    openDetailsScroll("details-extraction");
    return;
  }
  if (action === "top") {
    const h = document.getElementById("details-insights");
    if (h) {
      h.open = true;
      h.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    return;
  }
  if (action === "drivers") {
    const lines = document.getElementById("details-all-lines");
    if (lines) lines.open = true;
    const sec = document.getElementById("section-drivers");
    if (sec) sec.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
}

function renderReviewQueueList(items) {
  const list = document.getElementById("review-queue-list");
  if (!list) return;
  list.innerHTML = "";
  (items || []).forEach((it) => {
    const li = document.createElement("li");
    li.className = "review-queue-item review-queue-item--" + String(it.severity || "MEDIUM").toLowerCase();
    const sev = document.createElement("span");
    sev.className = "review-queue-sev";
    sev.textContent = it.severity || "—";
    const main = document.createElement("div");
    main.className = "review-queue-main";
    const iss = document.createElement("p");
    iss.className = "review-queue-issue";
    iss.textContent = it.issue || "";
    const why = document.createElement("p");
    why.className = "review-queue-why subtle small";
    why.textContent = it.why || "";
    main.appendChild(iss);
    main.appendChild(why);
    const act = document.createElement("button");
    act.type = "button";
    act.className = "btn-ghost review-queue-action";
    act.textContent = it.actionLabel || "Go";
    act.addEventListener("click", () => runReviewQueueAction(it.action));
    li.appendChild(sev);
    li.appendChild(main);
    li.appendChild(act);
    list.appendChild(li);
  });
}

function renderActiveInvestigationFromSignals(fs, ctx) {
  const host = document.getElementById("active-investigation-body");
  if (!host || !fs) return;
  const wps = fs.workbook_profit_summary || {};
  const tpp = ctx && ctx.tpp != null ? ctx.tpp : numOrNull(wps.total_projected_profit);
  const wbook = ctx && ctx.wbook != null ? ctx.wbook : numOrNull(wps.workbook_reported_total_projected_profit);
  const pvar = ctx && ctx.pvar != null ? ctx.pvar : numOrNull(wps.projected_profit_variance);
  const severity = (ctx && ctx.sigHead) || (pvar != null && Math.abs(pvar) >= 0.02 ? "Mismatch" : "OK");
  host.innerHTML = "";

  const badgeClass = "investigation-severity investigation-severity--" + finCmdSignalToClass(severity);
  host.innerHTML =
    '<div class="active-investigation-hero">' +
    '<div class="active-investigation-kicker">Active investigation</div>' +
    '<div class="active-investigation-title-row">' +
    '<h2 class="active-investigation-title">TPP reconciliation variance</h2>' +
    `<span class="${badgeClass}">${severity}</span>` +
    "</div>" +
    '<p class="active-investigation-why">Compare the formula-built Total Projected Profit against the workbook-reported headline before relying on the forecast.</p>' +
    '<div class="investigation-kpi-strip" aria-label="TPP reconciliation metrics">' +
    `<article><span>Formula TPP</span><strong>${tpp != null ? fmtMoneyPlain(tpp) : "—"}</strong></article>` +
    `<article><span>Workbook-reported TPP</span><strong>${wbook != null ? fmtMoneyPlain(wbook) : "—"}</strong></article>` +
    `<article class="${pvar != null && Math.abs(pvar) >= 0.02 ? "is-mismatch" : "is-ok"}"><span>Variance</span><strong>${pvar != null ? fmtMoneySigned(pvar) : "—"}</strong></article>` +
    "</div>" +
    '<div class="active-investigation-actions">' +
    '<button type="button" class="btn-toolbar-primary" data-investigation-action="reconciliation">Open reconciliation</button>' +
    '<button type="button" class="btn-ghost" data-investigation-action="workbench">Go to workbench</button>' +
    "</div>" +
    "</div>";

  host.querySelectorAll("[data-investigation-action]").forEach((btn) => {
    btn.addEventListener("click", () => runReviewQueueAction(btn.getAttribute("data-investigation-action")));
  });
}

function renderActiveInvestigationFromQueue(items) {
  const host = document.getElementById("active-investigation-body");
  if (!host || window.__OWB_LAST_FS) return;
  const top = (items || [])[0];
  if (!top) return;
  host.innerHTML =
    '<div class="active-investigation-hero">' +
    '<div class="active-investigation-kicker">Active investigation</div>' +
    '<div class="active-investigation-title-row">' +
    `<h2 class="active-investigation-title">${top.issue || "Review signal"}</h2>` +
    `<span class="investigation-severity investigation-severity--${String(top.severity || "watch").toLowerCase()}">${top.severity || "WATCH"}</span>` +
    "</div>" +
    `<p class="active-investigation-why">${top.why || "Review the latest analysis output."}</p>` +
    '<div class="active-investigation-actions">' +
    `<button type="button" class="btn-toolbar-primary" data-investigation-action="${top.action || "workbench"}">${top.actionLabel || "Open evidence"}</button>` +
    "</div>" +
    "</div>";
  host.querySelectorAll("[data-investigation-action]").forEach((btn) => {
    btn.addEventListener("click", () => runReviewQueueAction(btn.getAttribute("data-investigation-action")));
  });
}

function renderEvidencePanelFromSignals(fs, ctx) {
  const host = document.getElementById("investigation-evidence-body");
  if (!host || !fs) return;
  const wps = fs.workbook_profit_summary || {};
  const selected = Array.from(reportPathSelection || []).slice(0, 3);
  const lim = Array.isArray(wps.projected_profit_limitations) ? wps.projected_profit_limitations : [];
  const roll = (fs.extraction_confidence && fs.extraction_confidence.rollup) || "—";
  const pvar = ctx && ctx.pvar != null ? ctx.pvar : numOrNull(wps.projected_profit_variance);
  host.innerHTML =
    '<div class="evidence-status-grid">' +
    `<article><span>Source status</span><strong>${roll}</strong></article>` +
    `<article><span>Variance status</span><strong>${pvar != null && Math.abs(pvar) >= 0.02 ? "Mismatch" : "Aligned"}</strong></article>` +
    "</div>" +
    '<h3 class="evidence-subhead">Selected workbook(s)</h3>' +
    `<p class="evidence-path">${selected.length ? selected.join(" · ") : "No workbook selection captured in this view."}</p>` +
    '<h3 class="evidence-subhead">Linked actions</h3>' +
    '<div class="evidence-action-row">' +
    '<button type="button" class="btn-ghost" data-evidence-action="reconciliation">Reconciliation tab</button>' +
    '<button type="button" class="btn-ghost" data-evidence-action="extraction">Source detail</button>' +
    '<button type="button" class="btn-ghost" data-evidence-action="signals-limits">Audit notes</button>' +
    "</div>" +
    '<h3 class="evidence-subhead">Audit / source notes</h3>' +
    `<ul class="evidence-notes">${lim.length ? lim.slice(0, 4).map((x) => `<li>${String(x)}</li>`).join("") : "<li>No limitation lines attached.</li>"}</ul>`;
  host.querySelectorAll("[data-evidence-action]").forEach((btn) => {
    btn.addEventListener("click", () => runReviewQueueAction(btn.getAttribute("data-evidence-action")));
  });
}

function renderAssistant(av, execSig) {
  const idle = document.getElementById("assistant-idle");
  const body = document.getElementById("assistant-body");
  const listEl = document.getElementById("review-queue-list");
  const sig = execSig || window.__executiveSignal || null;
  const fromFs = buildReviewQueueItemsFromFinancialSignals(window.__OWB_LAST_FS);
  const fromCmp = sig ? buildReviewQueueItemsFromCompare(sig, av || {}) : [];
  const items = mergeAndSortReviewQueueItems(fromFs, fromCmp);
  renderActiveInvestigationFromQueue(items);
  const lead = document.getElementById("assistant-lead");
  if (lead) lead.textContent = "";

  if (items.length === 0 && !av && !sig) {
    if (idle) idle.classList.remove("hidden");
    if (body) body.classList.add("hidden");
    return;
  }
  if (items.length === 0 && av && !sig) {
    if (idle) idle.classList.remove("hidden");
    if (body) body.classList.add("hidden");
    return;
  }
  if (idle) idle.classList.add("hidden");
  if (body) body.classList.remove("hidden");
  renderReviewQueueList(items);
  fill("assistant-did", (av && av.what_i_did) || []);
}

function fill(id, items) {
  const u = document.getElementById(id);
  u.innerHTML = "";
  (items || []).forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    u.appendChild(li);
  });
}

const WPS_COMP_LABELS = {
  total_projected_profit: "Total projected profit",
  labor_rate_profit_to_date: "Labor rate profit",
  cm_fee: "CM fee",
  pco_profit: "PCO profit",
  buyout_savings_realized: "Buyout savings",
  budget_savings_overages: "Budget savings / overages",
  prior_system_profit: "Prior-system profit",
};

function renderRankedComponentCards(so, structOk, execSig, driverSplit) {
  const cards = document.getElementById("financial-cards");
  if (!cards) return;
  cards.innerHTML = "";
  if (!structOk) return;
  const lineTotal = driverSplit.total || Number(so.material_diff_line_count || 0) || 0;
  const roll = (so.extraction_confidence && so.extraction_confidence.rollup) || "—";
  const wpsd = (so && so.workbook_profit_summary_deltas) || {};
  let entries = Object.keys(wpsd)
    .map((k) => ({ k, v: numOrNull(wpsd[k]) }))
    .filter((x) => x.v != null && !Number.isNaN(x.v));
  entries.sort((a, b) => Math.abs(b.v) - Math.abs(a.v));
  if (entries.length === 0) {
    const sd = so.summary_deltas || {};
    ["profit", "revenue", "cost"].forEach((k) => {
      const v = numOrNull(sd[k]);
      if (v != null) entries.push({ k, v });
    });
    entries.sort((a, b) => Math.abs(b.v) - Math.abs(a.v));
  }
  if (entries.length === 0 && lineTotal === 0) {
    const ph = document.createElement("p");
    ph.className = "subtle comp-card-empty";
    ph.textContent = "No workbook component deltas or summary rows in this pass.";
    cards.appendChild(ph);
  }
  entries.forEach((e, i) => {
    const label = WPS_COMP_LABELS[e.k] || (e.k === "profit" ? "Profit (summary)" : e.k === "revenue" ? "Revenue (summary)" : e.k === "cost" ? "Cost (summary)" : e.k);
    const n = e.v;
    const card = document.createElement("article");
    card.className = "comp-card comp-card--ranked";
    const st = n > 0 ? "Favorable" : n < 0 ? "Unfavorable" : "Flat";
    const stc = n > 0 ? "comp-badge--up" : n < 0 ? "comp-badge--down" : "comp-badge--zero";
    const expl = entries.length && so.workbook_profit_summary_deltas
      ? "Δ from prior vs current workbook profit snapshot, same key."
      : "Δ from period summary row (rolled compare).";
    card.innerHTML =
      '<div class="comp-card__row">' +
      '<span class="comp-card__rank">#' +
      (i + 1) +
      "</span>" +
      '<div class="comp-card__main">' +
      '<div class="comp-card__name">' +
      escapeHtml(label) +
      "</div>" +
      '<div class="comp-card__valrow"><span class="comp-card__val ' +
      (n > 0 ? "positive" : n < 0 ? "negative" : "zeroed") +
      '">' +
      fmtMoneySigned(n) +
      "</span>" +
      '<span class="comp-badge ' +
      stc +
      '">' +
      escapeHtml(st) +
      "</span></div>" +
      '<p class="comp-card__conf"><span class="comp-conf-tag">Read: ' +
      escapeHtml(String(roll)) +
      "</span> · " +
      escapeHtml(expl) +
      "</p></div></div>" +
      '<div class="comp-card__actions"><button type="button" class="btn-ghost comp-card__open" data-open-line-detail>Open detail</button></div>';
    const btn = card.querySelector("[data-open-line-detail]");
    if (btn) btn.addEventListener("click", () => openLineDetailSection());
    cards.appendChild(card);
  });
  if (lineTotal > 0 || entries.length > 0) {
    const c2 = document.createElement("div");
    c2.className = "comp-card comp-card--ranked comp-card--lines";
    c2.innerHTML =
      '<div class="comp-card__row"><div class="comp-card__main"><div class="comp-card__name">Material line count</div>' +
      '<div class="comp-card__valrow"><span class="comp-card__val value--mono">' +
      String(lineTotal) +
      "</span></div>" +
      '<p class="comp-card__conf">Lines in material diff (engine).</p></div></div>' +
      '<div class="comp-card__actions"><button type="button" class="btn-ghost comp-card__open" data-open-line-detail>See lines</button></div>';
    const b2 = c2.querySelector("[data-open-line-detail]");
    if (b2) b2.addEventListener("click", () => openLineDetailSection());
    cards.appendChild(c2);
  }
}

function renderFinancialUi(executed) {
  lastRunPayload = executed;
  const so = executed.structured_output || {};
  const isFin = executed.workflow === "wf_financial_markdown_delta";
  const structOk = isFin && isStructuredFinancial(so);
  window.__driverStructOk = structOk;
  const miss = document.getElementById("fin-structured-missing");
  if (!isFin) {
    miss.classList.add("hidden");
    document.getElementById("extraction-confidence-block").innerHTML =
      "<p class='subtle'>This layout targets period financials. What changed and source material are below.</p>";
    document.getElementById("extraction-per-side").innerHTML = "";
  } else if (!structOk) {
    miss.classList.remove("hidden");
    renderExtractionConfidence(so);
    renderExtractionPerSide(so);
  } else {
    miss.classList.add("hidden");
    renderExtractionConfidence(so);
    renderExtractionPerSide(so);
  }

  const driverSplit = structOk
    ? mergeAndSplitDriverRows(so.material_diff_items, so.material_diff_audit_items)
    : { primary: [], audit: [], total: 0, primaryCount: 0, auditCount: 0 };
  const execSig = buildExecutiveSignal(so, structOk, isFin, driverSplit);
  window.__executiveSignal = execSig;

  renderAnswerHero(so, structOk, isFin, execSig);
  renderSignalClassificationRow(execSig, structOk, isFin);
  renderReviewActionsList(execSig);

  if (structOk) {
    window.__driverSplitMeta = {
      total: driverSplit.total,
      primaryCount: driverSplit.primaryCount,
      auditCount: driverSplit.auditCount,
      primaryList: driverSplit.primary,
      auditList: driverSplit.audit,
    };
  } else {
    window.__driverSplitMeta = { total: 0, primaryCount: 0, auditCount: 0, primaryList: [], auditList: [] };
  }
  if (structOk) {
    renderRankedComponentCards(so, structOk, execSig, driverSplit);
  } else {
    document.getElementById("financial-cards").innerHTML = "";
  }

  const primaryItems = (structOk && driverSplit.primary) || [];
  renderDriverAttributionList(primaryItems, execSig);

  const pCount = document.getElementById("driver-primary-count");
  if (pCount) {
    if (structOk && driverSplit.total > 0) {
      pCount.textContent = `Top drivers (${driverSplit.primaryCount} of ${driverSplit.total})`;
      pCount.title = `Primary = top ${DRIVER_PRIMARY_TOP_N} by |Δ| or |Δ| ≥ $${DRIVER_IMPACT_THRESHOLD.toLocaleString()}`;
    } else {
      pCount.textContent = "";
      pCount.removeAttribute("title");
    }
  }
  const aCount = document.getElementById("driver-audit-count");
  const aSum = document.getElementById("audit-details-summary");
  if (aCount) {
    if (structOk && driverSplit.auditCount > 0) {
      aCount.textContent = `Smaller moves (${driverSplit.auditCount} of ${driverSplit.total})`;
    } else {
      aCount.textContent = structOk && driverSplit.total > 0 ? "Smaller moves (0) — all lines are in Top drivers" : "";
    }
  }
  if (aSum) {
    if (structOk && driverSplit.auditCount > 0) {
      aSum.textContent = `Smaller moves (${driverSplit.auditCount})`;
    } else {
      aSum.textContent = "Smaller moves (0)";
    }
  }
  const audDet = document.getElementById("audit-details");
  if (audDet) audDet.open = structOk && driverSplit.auditCount > 0;

  const primBody = document.getElementById("drivers-primary-body");
  primBody.innerHTML = "";
  const auditBody = document.getElementById("drivers-audit-body");
  const auditItems = (structOk && driverSplit.audit) || [];
  const allDriverRowsForUi = [].concat(primaryItems).concat(auditItems);
  window.__driverRows = allDriverRowsForUi;
  const impactRankMap =
    structOk && allDriverRowsForUi.length > 0 ? buildImpactRankMap(allDriverRowsForUi) : new Map();
  if (isFin) {
    renderProjectFinancialCommandView(structOk ? allDriverRowsForUi : [], so, execSig);
    if (structOk && allDriverRowsForUi.length > 0) {
      renderTradeSummaryHost(document.getElementById("trade-summary-host"), allDriverRowsForUi);
    } else {
      renderTradeSummaryHost(document.getElementById("trade-summary-host"), []);
    }
  } else {
    const st = document.getElementById("project-financial-signals-strip");
    if (st) {
      st.setAttribute("hidden", "hidden");
      st.innerHTML = "";
    }
    renderTradeSummaryHost(document.getElementById("trade-summary-host"), []);
  }
  if (!structOk) {
    const tr = document.createElement("tr");
    tr.className = "driver-message-row";
    const td = document.createElement("td");
    td.colSpan = 7;
    td.textContent = !isFin
      ? "No structured line drivers. Source material is below if you need it."
      : "Category detail not available in this pass.";
    tr.appendChild(td);
    primBody.appendChild(tr);
  } else if (primaryItems.length === 0) {
    const tr = document.createElement("tr");
    tr.className = "driver-message-row";
    const td = document.createElement("td");
    td.colSpan = 7;
    td.textContent =
      driverSplit.total > 0
        ? "All material lines are listed under “Smaller moves” below (same impact order)."
        : "No material lines in this run.";
    tr.appendChild(td);
    primBody.appendChild(tr);
  } else {
    primaryItems.forEach((row) => {
      const tr = document.createElement("tr");
      setDriverDataRowAttributes(tr, row);
      const rk = impactRankMap.get(driverRowKey(row)) || "—";
      const dv = rowBudgetDeltaValue(row);
      const pct = rowBudgetDeltaPct(row);
      const cat = row.category_label || row.category || "";
      const tier = row.tier || "";
      const bdg = sizeBadgeForDelta(dv);
      const pills = [];
      if (isRowDerivedFromDelta(row)) pills.push("<span class='row-src-pill row-src-pill--derived'>Derived</span>");
      if (!hasOriginalBudget(row) && numOrNull(row.current_value) != null) {
        pills.push("<span class='row-src-pill row-src-pill--missing'>Missing source</span>");
      }
      const pillHtml = pills.length ? "<div class='row-pills'>" + pills.join("") + "</div>" : "";
      tr.innerHTML =
        '<td class="col-rank"><span class="impact-rank">' +
        String(rk) +
        "</span>" +
        (bdg
          ? '<span class="impact-badge impact-badge--' + bdg.toLowerCase() + '">' + bdg + "</span>"
          : "") +
        "</td>" +
        "<td class='driver-line-cell'>" +
        escapeHtml(String(cat)) +
        pillHtml +
        "</td>" +
        "<td class='num'>" +
        fmtMoneyPlain(row.prior_value) +
        "</td>" +
        "<td class='num'>" +
        fmtMoneyPlain(row.current_value) +
        "</td>" +
        "<td class='num cell-delta-usd'>" +
        fmtDeltaUsdCell(dv) +
        "</td>" +
        "<td class='num cell-delta-pct'>" +
        fmtDeltaPctCell(pct) +
        "</td>" +
        "<td><span class='tier-pill " +
        tierClass(tier) +
        "'>" +
        escapeHtml(String(tier)) +
        "</span></td>";
      attachRowDataAttrs(tr, row);
      primBody.appendChild(tr);
    });
  }

  auditBody.innerHTML = "";
  if (!structOk) {
    const tr = document.createElement("tr");
    tr.className = "driver-message-row";
    const td = document.createElement("td");
    td.colSpan = 6;
    td.textContent = "—";
    tr.appendChild(td);
    auditBody.appendChild(tr);
  } else if (auditItems.length === 0) {
    const tr = document.createElement("tr");
    tr.className = "driver-message-row";
    const td = document.createElement("td");
    td.colSpan = 6;
    td.textContent =
      driverSplit.total > 0
        ? "All lines are in Top drivers, or the list is only a few rows long."
        : "No material lines.";
    tr.appendChild(td);
    auditBody.appendChild(tr);
  } else {
    auditItems.forEach((row) => {
      const tr = document.createElement("tr");
      setDriverDataRowAttributes(tr, row);
      const rk = impactRankMap.get(driverRowKey(row)) || "—";
      const dv = rowBudgetDeltaValue(row);
      const pct = rowBudgetDeltaPct(row);
      const cat = row.category_label || row.category || "";
      const bdg = sizeBadgeForDelta(dv);
      const pills = [];
      if (isRowDerivedFromDelta(row)) pills.push("<span class='row-src-pill row-src-pill--derived'>Derived</span>");
      if (!hasOriginalBudget(row) && numOrNull(row.current_value) != null) {
        pills.push("<span class='row-src-pill row-src-pill--missing'>Missing source</span>");
      }
      const pillHtml = pills.length ? "<div class='row-pills'>" + pills.join("") + "</div>" : "";
      tr.innerHTML =
        '<td class="col-rank"><span class="impact-rank">' +
        String(rk) +
        "</span>" +
        (bdg
          ? '<span class="impact-badge impact-badge--' + bdg.toLowerCase() + '">' + bdg + "</span>"
          : "") +
        "</td>" +
        "<td class='driver-line-cell'>" +
        escapeHtml(String(cat)) +
        pillHtml +
        "</td>" +
        "<td class='num'>" +
        fmtMoneyPlain(row.prior_value) +
        "</td>" +
        "<td class='num'>" +
        fmtMoneyPlain(row.current_value) +
        "</td>" +
        "<td class='num cell-delta-usd'>" +
        fmtDeltaUsdCell(dv) +
        "</td>" +
        "<td class='num cell-delta-pct'>" +
        fmtDeltaPctCell(pct) +
        "</td>";
      attachRowDataAttrs(tr, row);
      auditBody.appendChild(tr);
    });
  }
  window.__driverTableCounts = {
    primaryAll: structOk ? primaryItems.length : 0,
    auditAll: structOk ? auditItems.length : 0,
  };
  fillTableFooterMetrics();

  document.getElementById("driver-filter").value = "";
  document.getElementById("negatives-only").checked = false;
  applyDriverFilter();

  const intakeBox = document.getElementById("intake-links");
  const intakeMissing = document.getElementById("intake-missing");
  const intakeList = document.getElementById("intake-link-list");
  intakeList.innerHTML = "";
  const intakes = executed.financial_intake_artifacts || [];
  if (intakes.length === 0) {
    intakeBox.classList.add("hidden");
    intakeMissing.classList.remove("hidden");
  } else {
    intakeMissing.classList.add("hidden");
    intakeBox.classList.remove("hidden");
    intakes.forEach((ent) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `/runs/${executed.run_id}/artifacts/${ent.path}`;
      a.textContent = ent.label || ent.path;
      a.target = "_blank";
      li.appendChild(a);
      li.appendChild(document.createTextNode(" (" + ent.path + ")"));
      intakeList.appendChild(li);
    });
  }

  const summaryList = document.getElementById("summary-list");
  summaryList.innerHTML = "";
  (executed.summary || []).forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    summaryList.appendChild(li);
  });
  const reviewList = document.getElementById("review-list");
  reviewList.innerHTML = "";
  (executed.what_to_review || []).forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    reviewList.appendChild(li);
  });

  const artifactList = document.getElementById("artifact-list");
  artifactList.innerHTML = "";
  const allArts = executed.artifacts || [];
  const intakePaths = new Set((executed.financial_intake_artifacts || []).map((x) => x.path));
  allArts
    .filter((p) => p.startsWith("outputs/"))
    .forEach((artifact) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `/runs/${executed.run_id}/artifacts/${artifact}`;
      a.textContent = artifact;
      a.target = "_blank";
      li.appendChild(a);
      artifactList.appendChild(li);
    });
  allArts
    .filter((p) => p.startsWith("inputs/") && !intakePaths.has(p))
    .forEach((artifact) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `/runs/${executed.run_id}/artifacts/${artifact}`;
      a.textContent = artifact;
      a.target = "_blank";
      li.appendChild(a);
      artifactList.appendChild(li);
    });

  document.getElementById("pre-prior-snapshot").textContent = "(not loaded)";
  document.getElementById("pre-current-snapshot").textContent = "(not loaded)";
  renderAssistantResponse(null);

  renderAssistant(executed.assistant_view || null, execSig);
  document.getElementById("run-id").textContent = executed.run_id;
  const vl = viewLabelForName(executed.workflow);
  const svl = document.getElementById("session-view-label");
  svl.textContent = vl || "";

  if (
    window.__postRenderDriverFocus &&
    lastRunPayload &&
    window.__postRenderDriverFocus.runId === lastRunPayload.run_id
  ) {
    applyOperatorTaskDriverFocus(
      window.__postRenderDriverFocus.contract,
      window.__postRenderDriverFocus.result
    );
    window.__postRenderDriverFocus = null;
  }
}

async function jsonOrThrow(response) {
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || JSON.stringify(payload));
  }
  return payload;
}

async function loadRunFromHistory(runId) {
  const data = await jsonOrThrow(await fetch(`/runs/${runId}`));
  if (data.status !== "completed" || !data.structured_output) {
    document.getElementById("status").textContent = "This item cannot be opened: " + (data.error || data.status);
    window.__postRenderDriverFocus = null;
    return false;
  }
  const executed = {
    run_id: data.run_id,
    workflow: data.workflow_name,
    summary: (data.envelope && data.envelope.what_i_found) || [],
    what_to_review: (data.envelope && data.envelope.what_needs_review) || [],
    structured_output: data.structured_output,
    financial_intake_artifacts: data.financial_intake_artifacts || [],
    artifacts: data.artifacts || [],
    assistant_view: data.assistant_view,
  };
  const rw = document.getElementById("result-workspace");
  rw.classList.remove("hidden");
  rw.setAttribute("aria-hidden", "false");
  renderFinancialUi(executed);
  document.getElementById("status").textContent = "Loaded.";
  return true;
}

function finCmdSignalToClass(sig) {
  const k = String(sig || "Watch");
  if (k === "OK") return "ok";
  if (k === "Watch") return "watch";
  if (k === "Mismatch") return "mismatch";
  if (k === "Missing Source") return "missing-source";
  if (k === "High Movement") return "high-movement";
  return "watch";
}

function finCmdAppendCard(grid, opts) {
  const label = opts.label || "";
  const valueLines = opts.valueLines || [];
  const deltaText = opts.deltaText != null ? opts.deltaText : "";
  const signalLabel = opts.signalLabel || "Watch";
  const action = opts.action || null;
  const art = document.createElement("article");
  art.className = "fin-cmd-card fin-cmd-card--sig-" + finCmdSignalToClass(signalLabel);
  art.setAttribute("aria-label", label);
  const lab = document.createElement("p");
  lab.className = "fin-cmd-card__label";
  lab.textContent = label;
  const val = document.createElement("div");
  val.className = "fin-cmd-card__value";
  if (!valueLines.length) {
    const p = document.createElement("p");
    p.className = "fin-cmd-card__value-line fin-cmd-card__value-line--muted";
    p.textContent = "Not available from selected report";
    val.appendChild(p);
  } else {
    valueLines.forEach((line) => {
      const p = document.createElement("p");
      p.className = "fin-cmd-card__value-line";
      p.textContent = line;
      val.appendChild(p);
    });
  }
  const del = document.createElement("p");
  del.className = "fin-cmd-card__delta";
  del.textContent = deltaText;
  const sig = document.createElement("span");
  sig.className = "fin-cmd-card__signal";
  sig.textContent = signalLabel;
  art.appendChild(lab);
  art.appendChild(val);
  art.appendChild(del);
  art.appendChild(sig);
  if (action) {
    art.tabIndex = 0;
    art.setAttribute("role", "button");
    const go = () => runReviewQueueAction(action);
    art.addEventListener("click", go);
    art.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        go();
      }
    });
  } else {
    art.classList.add("fin-cmd-card--static");
  }
  grid.appendChild(art);
}

function renderFinCommandCenterFromSignals(fs) {
  const host = document.getElementById("fin-command-center");
  const grid = document.getElementById("fin-command-center-grid");
  if (!host || !grid || !fs) return;
  grid.innerHTML = "";
  host.removeAttribute("hidden");
  const wps = fs.workbook_profit_summary || {};
  const wpsd = fs.workbook_profit_summary_deltas || {};
  const roll = (fs.extraction_confidence && fs.extraction_confidence.rollup) || "";
  const tpp = numOrNull(wps.total_projected_profit);
  const wbook = numOrNull(wps.workbook_reported_total_projected_profit);
  const pvar = numOrNull(wps.projected_profit_variance);
  const profitMv = numOrNull(wpsd.profit);
  const costMv = numOrNull(wpsd.cost);
  const ocoMv = numOrNull(wpsd.owner_change_orders_value);
  const ccoMv = numOrNull(wpsd.cm_change_orders_value);
  const lrpMv = numOrNull(wpsd.labor_rate_profit_to_date);
  const lim = wps.projected_profit_limitations;

  let sigHead = "OK";
  if (tpp == null && wbook == null) sigHead = "Missing Source";
  else if (pvar != null && Math.abs(pvar) >= 0.02) sigHead = "Mismatch";
  else if (String(roll).toLowerCase() === "low") sigHead = "Watch";

  renderActiveInvestigationFromSignals(fs, { sigHead, tpp, wbook, pvar, roll });
  renderEvidencePanelFromSignals(fs, { sigHead, pvar, roll });

  finCmdAppendCard(grid, {
    label: "Total projected profit · Workbook TPP",
    valueLines: [
      "Formula TPP: " + (tpp != null ? fmtMoneyPlain(tpp) : "—"),
      "Workbook-reported: " + (wbook != null ? fmtMoneyPlain(wbook) : "—"),
    ],
    deltaText: pvar != null ? "Variance: " + fmtMoneySigned(pvar) : "Variance: not in extract",
    signalLabel: sigHead,
    action: "reconciliation",
  });

  let pmSig = "Missing Source";
  let pmDelta = "Period movement not in this payload";
  if (profitMv != null && !Number.isNaN(profitMv)) {
    pmDelta = "Δ vs prior snapshot: " + fmtMoneySigned(profitMv);
    pmSig = Math.abs(profitMv) >= 250000 ? "High Movement" : "OK";
  }
  finCmdAppendCard(grid, {
    label: "Profit movement",
    valueLines: profitMv != null ? [fmtMoneySigned(profitMv)] : [],
    deltaText: pmDelta,
    signalLabel: pmSig,
    action: profitMv != null ? "top" : null,
  });

  let cmSig = "Missing Source";
  let cmDelta = "Cost movement not in workbook profit deltas";
  if (costMv != null && !Number.isNaN(costMv)) {
    cmDelta = "Δ vs prior: " + fmtMoneySigned(costMv);
    cmSig = Math.abs(costMv) >= 250000 ? "High Movement" : "OK";
  }
  finCmdAppendCard(grid, {
    label: "Total cost movement",
    valueLines: costMv != null ? [fmtMoneySigned(costMv)] : [],
    deltaText: cmDelta,
    signalLabel: cmSig,
    action: "drivers",
  });

  const ocoVal = numOrNull(wps.owner_change_orders_value);
  let ocoLines = [];
  if (ocoMv != null) ocoLines.push("Δ: " + fmtMoneySigned(ocoMv));
  if (ocoVal != null) ocoLines.push("Level: " + fmtMoneyPlain(ocoVal));
  let ocoSig = ocoLines.length ? (ocoMv != null && Math.abs(ocoMv) >= 250000 ? "High Movement" : "OK") : "Missing Source";
  finCmdAppendCard(grid, {
    label: "Owner change order movement",
    valueLines: ocoLines,
    deltaText: ocoMv != null ? "Period delta on owner CO" : ocoVal != null ? "Snapshot level only" : "Not in extract",
    signalLabel: ocoSig,
    action: "change_orders",
  });

  const ccoVal = numOrNull(wps.cm_change_orders_value);
  let ccoLines = [];
  if (ccoMv != null) ccoLines.push("Δ: " + fmtMoneySigned(ccoMv));
  if (ccoVal != null) ccoLines.push("Level: " + fmtMoneyPlain(ccoVal));
  let ccoSig = ccoLines.length ? (ccoMv != null && Math.abs(ccoMv) >= 250000 ? "High Movement" : "OK") : "Missing Source";
  finCmdAppendCard(grid, {
    label: "CM change order movement",
    valueLines: ccoLines,
    deltaText: ccoMv != null ? "Period delta on CM CO" : ccoVal != null ? "Snapshot level only" : "Not in extract",
    signalLabel: ccoSig,
    action: "change_orders",
  });

  const lrpVal = numOrNull(wps.labor_rate_profit_to_date);
  let lrpLines = [];
  if (lrpMv != null) lrpLines.push("Δ: " + fmtMoneySigned(lrpMv));
  if (lrpVal != null) lrpLines.push("LRP to date: " + fmtMoneyPlain(lrpVal));
  let lrpSig = lrpLines.length ? (lrpMv != null && Math.abs(lrpMv) >= 100000 ? "High Movement" : "OK") : "Missing Source";
  finCmdAppendCard(grid, {
    label: "LRP movement",
    valueLines: lrpLines,
    deltaText: lrpMv != null ? "Labor rate profit delta" : lrpVal != null ? "Snapshot LRP only" : "Not in extract",
    signalLabel: lrpSig,
    action: "lrp",
  });

  let recSig = pvar == null ? "Missing Source" : Math.abs(pvar) < 0.02 ? "OK" : "Mismatch";
  finCmdAppendCard(grid, {
    label: "Reconciliation variance",
    valueLines: pvar != null ? [fmtMoneySigned(pvar)] : [],
    deltaText: "Formula TPP vs workbook-reported bridge",
    signalLabel: recSig,
    action: "reconciliation",
  });

  const limTxt =
    Array.isArray(lim) && lim.length
      ? lim.slice(0, 2).join(" · ")
      : "No limitation lines attached";
  let exSig = "OK";
  if (String(roll).toLowerCase() === "low") exSig = "Watch";
  if (!roll && (!Array.isArray(lim) || !lim.length)) exSig = "Missing Source";
  finCmdAppendCard(grid, {
    label: "Source / extraction readiness",
    valueLines: ["Read: " + (roll || "—"), limTxt],
    deltaText: Array.isArray(lim) && lim.length ? "See limitations" : "Cross-check structured read",
    signalLabel: exSig,
    action: "signals-limits",
  });
}

function showFinWorkbenchFailurePanel(fs, meta) {
  const panel = document.getElementById("fin-workbench-failure-panel");
  const dl = document.getElementById("fin-workbench-failure-dl");
  const next = document.getElementById("fin-workbench-failure-next");
  if (!panel || !dl) return;
  panel.removeAttribute("hidden");
  dl.innerHTML = "";
  const add = (k, v) => {
    const dt = document.createElement("dt");
    dt.textContent = k;
    const dd = document.createElement("dd");
    dd.textContent = v;
    dl.appendChild(dt);
    dl.appendChild(dd);
  };
  add("Selected project", String(reportBuilderProjectId || "—"));
  add("Analysis type", String((fs && fs.analysis_type) || "—"));
  const cur = fs && fs.workbook_profit_summary && fs.workbook_profit_summary.current_workbook_profit_summary;
  const hasWps =
    fs &&
    ((cur && typeof cur === "object") ||
      (fs.workbook_profit_summary && typeof fs.workbook_profit_summary === "object"));
  add("workbook_profit_summary present", hasWps ? "yes" : "no");
  add("renderFinancialWorkbench exists", meta.renderFnOk ? "yes" : "no");
  add("fin-wb-table count (embedded host)", String(meta.nTables));
  if (next) {
    next.textContent =
      meta.wbUseful && meta.nTables === 0
        ? "Likely next check: confirm owb-2-report-workbench.js loaded (Runtime diagnostics), hard-refresh with cache disabled, then re-run analysis."
        : "Likely next check: confirm this analysis type emits financial_workbench rows; open Source notes / limitations in the analysis panel.";
  }
}

function setupInvestigationModeLayout() {
  const workspace = document.getElementById("workspace");
  if (!workspace || workspace.dataset.investigationMode === "1") return;
  workspace.dataset.investigationMode = "1";
  workspace.classList.add("investigation-mode");

  const commandBar = document.getElementById("investigation-commandbar");
  const investigationRow = document.getElementById("investigation-layout");
  const signalsZone = document.getElementById("investigation-signals");
  const active = document.getElementById("investigation-active");
  const workbench = document.getElementById("investigation-workbench");
  if (!commandBar || !investigationRow || !signalsZone || !active || !workbench) return;

  const sticky = document.getElementById("report-builder-sticky");
  const source = document.getElementById("report-builder-source-collapse");
  const status = document.getElementById("status");
  if (sticky) commandBar.appendChild(sticky);
  if (source) commandBar.appendChild(source);
  if (status) commandBar.appendChild(status);

  const signals = document.getElementById("assistant-rail");
  const library = document.getElementById("project-library");
  if (signals) {
    signals.classList.remove("rail-right", "rail-review-queue");
    signals.classList.add("signals-rail");
    const title = signals.querySelector(".rail-title");
    if (title) title.textContent = "Signals";
    if (library) signals.insertBefore(library, signals.firstChild);
    signalsZone.appendChild(signals);
  }

  const finCmd = document.getElementById("fin-command-center");
  const finSignals = document.getElementById("financial-signals");
  const wbEmbed = document.getElementById("financial-workbench-embed");
  const resultWorkspace = document.getElementById("result-workspace");
  const finSurface = document.getElementById("financial-command-surface");

  if (finCmd) {
    finCmd.classList.add("investigation-highlights");
    active.appendChild(finCmd);
  }
  if (finSignals) active.appendChild(finSignals);
  if (wbEmbed) workbench.appendChild(wbEmbed);
  if (resultWorkspace) workbench.appendChild(resultWorkspace);
  if (finSurface) finSurface.classList.add("investigation-surface-shell");
}

function refreshOwbRuntimeDiagnostics() {
  const det = document.getElementById("owb-runtime-diagnostics");
  const body = document.getElementById("owb-diagnostics-body");
  if (!det || !body) return;
  const showDiag = owbDebugEnabled() || window.__owbWorkbenchRenderFailed;
  if (!showDiag) {
    det.setAttribute("hidden", "hidden");
    return;
  }
  det.removeAttribute("hidden");
  const sel = document.getElementById("analysis-type-select");
  const embed = document.getElementById("financial-workbench-embed");
  const fs = window.__OWB_LAST_FS;
  const wps = fs && fs.workbook_profit_summary;
  const cur = wps && wps.current_workbook_profit_summary;
  const lines = [
    "owb-4-app.js loaded: yes (marker " + (window.__OWB_SCRIPT_LOAD && window.__OWB_SCRIPT_LOAD.owb4App ? "set" : "missing") + ")",
    "owb-2-report-workbench.js loaded: " + (window.__OWB_SCRIPT_LOAD && window.__OWB_SCRIPT_LOAD.owb2ReportWorkbench ? "yes" : "no"),
    "renderFinancialWorkbench: " + (typeof renderFinancialWorkbench === "function" ? "function" : "missing"),
    "updateAllFinancialTableFooters: " + (typeof updateAllFinancialTableFooters === "function" ? "function" : "missing"),
    "selected analysis mode: " + (sel && sel.value ? sel.value : "—"),
    "current_workbook_profit_summary present: " + (cur && typeof cur === "object" ? "yes" : "no"),
    "workbook_profit_summary present: " + (wps && typeof wps === "object" ? "yes" : "no"),
    "embedded financial workbench node: " + (embed && embed.querySelector(".financial-workbench") ? "yes" : "no"),
    "table.fin-wb-table count: " + (embed ? embed.querySelectorAll("table.fin-wb-table").length : 0),
    "render failure flag: " + (window.__owbWorkbenchRenderFailed ? "yes" : "no"),
  ];
  body.textContent = lines.join("\n");
}

function clearEmbeddedFinancialSurface() {
  window.__OWB_LAST_FS = null;
  window.__OWB_LAST_FS_PROJECT = "";
  window.__owbWorkbenchRenderFailed = false;
  const surface = document.getElementById("financial-command-surface");
  const embed = document.getElementById("financial-workbench-embed");
  const cmd = document.getElementById("fin-command-center");
  const grid = document.getElementById("fin-command-center-grid");
  const fail = document.getElementById("fin-workbench-failure-panel");
  const diag = document.getElementById("owb-runtime-diagnostics");
  if (embed) embed.innerHTML = "";
  if (grid) grid.innerHTML = "";
  if (cmd) cmd.setAttribute("hidden", "hidden");
  if (fail) fail.setAttribute("hidden", "hidden");
  if (diag) diag.setAttribute("hidden", "hidden");
  if (surface) surface.setAttribute("hidden", "hidden");
  const sig = document.getElementById("financial-signals");
  if (sig) {
    sig.classList.remove("financial-signals--promoted");
    sig.innerHTML = "";
    sig.setAttribute("hidden", "hidden");
  }
  workbenchViewApi = null;
  renderAssistant(null, null);
}

function refreshReportBuilderWorkbenchShell() {
  const panel = document.getElementById("operator-assistant-panel");
  if (!panel) return;
  const pid = String(reportBuilderProjectId || "").trim();
  if (
    window.__OWB_LAST_FS &&
    window.__OWB_LAST_FS_PROJECT &&
    pid &&
    String(window.__OWB_LAST_FS_PROJECT) !== pid
  ) {
    clearEmbeddedFinancialSurface();
  }
  const hasProj = !!pid;
  panel.classList.toggle("report-builder--has-project", hasProj);
  const sigEl = document.getElementById("financial-signals");
  const hasOut = !!(window.__OWB_LAST_FS && sigEl && !sigEl.hasAttribute("hidden"));
  panel.classList.toggle("report-builder--has-signals-output", hasOut);
  const det = document.getElementById("report-builder-source-collapse");
  if (det && hasProj) {
    try {
      det.removeAttribute("open");
    } catch (e) {
      /* no-op */
    }
  }
}

function integrateReportBuilderFinancialSurface(fs) {
  window.__OWB_LAST_FS = fs;
  window.__OWB_LAST_FS_PROJECT = String(reportBuilderProjectId || "").trim();
  window.__owbWorkbenchRenderFailed = false;
  const surface = document.getElementById("financial-command-surface");
  const embed = document.getElementById("financial-workbench-embed");
  const failPanel = document.getElementById("fin-workbench-failure-panel");
  const sigHost = document.getElementById("financial-signals");
  if (surface) surface.removeAttribute("hidden");
  if (embed) embed.innerHTML = "";
  if (failPanel) failPanel.setAttribute("hidden", "hidden");
  if (sigHost) sigHost.classList.add("financial-signals--promoted");

  renderFinCommandCenterFromSignals(fs);

  const wb = fs && fs.financial_workbench;
  const wbUseful = financialWorkbenchHasUsefulData(wb);
  const benchEl = sigHost ? sigHost.querySelector(".financial-workbench") : null;
  if (benchEl && embed) {
    embed.appendChild(benchEl);
  }
  if (sigHost) {
    sigHost.querySelectorAll(".signals-fwb-bench details.signals-fwb-details").forEach((d) => {
      if (!d.querySelector(".financial-workbench")) d.remove();
    });
    sigHost.querySelectorAll(".signals-fwb-workspace .signals-fwb-hero").forEach((n) => {
      n.setAttribute("hidden", "hidden");
    });
    sigHost.querySelectorAll(".signals-fwb-workspace .signals-analysis-stack").forEach((n) => {
      n.setAttribute("hidden", "hidden");
    });
  }

  const nTables = embed ? embed.querySelectorAll("table.fin-wb-table").length : 0;
  const expects = analysisTypeExpectsWorkbench(fs && fs.analysis_type);
  const renderFnOk = typeof renderFinancialWorkbench === "function";
  if (expects && (!renderFnOk || nTables === 0)) {
    window.__owbWorkbenchRenderFailed = true;
    showFinWorkbenchFailurePanel(fs, { nTables: nTables, renderFnOk: renderFnOk, wbUseful: wbUseful });
  }

  if (typeof updateAllFinancialTableFooters === "function") {
    updateAllFinancialTableFooters();
  }
  refreshOwbRuntimeDiagnostics();
  renderAssistant((lastRunPayload && lastRunPayload.assistant_view) || null, window.__executiveSignal || null);
}

(function wireOwbWorkbenchIntegration() {
  const origRb = typeof renderFinancialSignalsBlock === "function" ? renderFinancialSignalsBlock : null;
  if (origRb) {
    renderFinancialSignalsBlock = function (fs) {
      origRb(fs);
      try {
        integrateReportBuilderFinancialSurface(fs);
      } catch (e) {
        console.warn("integrateReportBuilderFinancialSurface", e);
        window.__owbWorkbenchRenderFailed = true;
        refreshOwbRuntimeDiagnostics();
      }
      refreshReportBuilderWorkbenchShell();
    };
  }
  const sp = typeof selectProjectForBuilder === "function" ? selectProjectForBuilder : null;
  if (sp) {
    selectProjectForBuilder = async function (p) {
      try {
        await sp(p);
      } finally {
        refreshReportBuilderWorkbenchShell();
      }
    };
  }
  const sync = typeof syncReportBuilderControls === "function" ? syncReportBuilderControls : null;
  if (sync) {
    syncReportBuilderControls = function () {
      sync.apply(null, arguments);
      refreshReportBuilderWorkbenchShell();
    };
  }
})();

window.__OWB_SCRIPT_LOAD = Object.assign({}, window.__OWB_SCRIPT_LOAD || {}, { owb4App: true });

function setupHistoryClicks() {
  const runList = document.getElementById("left-run-list");
  if (runList) {
    runList.addEventListener("click", (ev) => {
      const btn = ev.target.closest("button.run-item");
      if (!btn) return;
      const id = btn.dataset.runId;
      if (id) loadRunFromHistory(id);
    });
  }
  document.getElementById("btn-load-snapshots").addEventListener("click", async () => {
    if (!lastRunPayload) return;
    const rid = lastRunPayload.run_id;
    try {
      const p = await fetch(`/runs/${rid}/artifacts/inputs/prior_financial_snapshot.json`);
      const c = await fetch(`/runs/${rid}/artifacts/inputs/current_financial_snapshot.json`);
      document.getElementById("pre-prior-snapshot").textContent = p.ok
        ? JSON.stringify(await p.json(), null, 2)
        : "(missing prior snapshot)";
      document.getElementById("pre-current-snapshot").textContent = c.ok
        ? JSON.stringify(await c.json(), null, 2)
        : "(missing current snapshot)";
    } catch (e) {
      document.getElementById("pre-prior-snapshot").textContent = String(e);
    }
  });
  document.querySelectorAll("#quick-actions [data-jump]").forEach((b) => {
    b.addEventListener("click", () => {
      const t = b.getAttribute("data-jump");
      if (t === "extraction") {
        openDetailsScroll("details-extraction");
      } else if (t === "evidence" || t === "files") {
        openDetailsScroll("details-files");
      } else if (t === "workbench") {
        runReviewQueueAction("workbench");
      } else if (t === "reconciliation") {
        runReviewQueueAction("reconciliation");
      } else if (t === "top") {
        const h = document.getElementById("answer-hero");
        if (h) h.scrollIntoView({ behavior: "smooth", block: "start" });
      } else {
        const h = document.getElementById("details-insights");
        if (h) {
          h.open = true;
          h.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }
    });
  });
  document.querySelectorAll("#quick-actions [data-focus='drivers']").forEach((b) => {
    b.addEventListener("click", () => {
      const lines = document.getElementById("details-all-lines");
      if (lines) lines.open = true;
      const sec = document.getElementById("section-drivers");
      if (sec) sec.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  document.getElementById("qa-audit").addEventListener("click", () => {
    const lines = document.getElementById("details-all-lines");
    if (lines) lines.open = true;
    document.getElementById("audit-details").open = true;
    const s = document.getElementById("section-drivers");
    if (s) s.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  document.getElementById("driver-filter").addEventListener("input", applyDriverFilter);
  document.getElementById("negatives-only").addEventListener("change", applyDriverFilter);
}

setupHistoryClicks();
setupOperatorAssistantSurface();
setupInvestigationModeLayout();
initOperatorWorkspace();
refreshReportBuilderWorkbenchShell();
