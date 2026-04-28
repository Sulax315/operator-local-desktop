/**
 * owb-2-report-workbench.js — Load order: 2 of 4 (after owb-1).
 * Project library, report selection table, Report Builder controls, financial workbench table rendering.
 */
function renderProjectLibrary(payload) {
  lastProjectLibraryPayload = payload || null;
  const hint = document.getElementById("project-library-hint");
  const list = document.getElementById("project-library-list");
  const idxEl = document.getElementById("project-library-indexed");
  const staleEl = document.getElementById("project-library-stale");
  if (!list) return;
  list.innerHTML = "";
  const pi = (payload && payload.project_index) || {};
  const searchEl = document.getElementById("project-library-search");
  const qf = (searchEl && searchEl.value ? String(searchEl.value) : "").trim().toLowerCase();
  const rawProjects = Array.isArray(pi.projects) ? pi.projects : [];
  const isUnlProj = (p) => !!(p && (p.is_unlabeled || p.project_id === "__unlabeled__"));
  const labeled = rawProjects.filter((p) => !isUnlProj(p));
  const unassigned = rawProjects.filter(isUnlProj);
  const ordered = labeled.concat(unassigned);
  const showUnEl = document.getElementById("show-unassigned-toggle");
  const showUnassigned = !!(showUnEl && showUnEl.checked);
  let projects = !qf
    ? ordered
    : ordered.filter((p) => {
        const id = String(p.project_id || "");
        const dn = String(p.display_name || "").toLowerCase();
        return id.includes(qf) || dn.includes(qf);
      });
  if (!showUnassigned) {
    projects = projects.filter((p) => !isUnlProj(p));
  }
  const nIdx = Number(pi.indexed_workbooks != null ? pi.indexed_workbooks : 0);
  const liveN = Number(pi.live_workbook_count != null ? pi.live_workbook_count : 0);
  const needsScan = !!pi.needs_scan;
  const cap = pi.scan_file_cap != null ? String(pi.scan_file_cap) : "";
  const mayStale = !!pi.index_may_be_stale;
  const workspaceRoot = payload && payload.workspace_root ? String(payload.workspace_root) : "Not configured";
  if (staleEl) {
    if (mayStale) {
      staleEl.removeAttribute("hidden");
      staleEl.textContent =
        "Last scan is behind this folder: more Excel file(s) on disk than in the index. Click Scan workspace to refresh.";
    } else {
      staleEl.setAttribute("hidden", "hidden");
    }
  }
  if (hint) {
    if (payload && payload.resolvable === false) {
      hint.textContent = "No approved workspace is configured for this server. Confirm the deployment root, then scan.";
    } else if (needsScan && nIdx === 0) {
      hint.textContent = "No workbooks found in active workspace. Confirm the folder contains .xlsx/.xlsm/.xls files, then scan again.";
    } else if (projects.length > 1) {
      hint.textContent = "Multiple projects in the index — select one to load monthly reports in the Report Builder.";
    } else {
      hint.textContent = "Indexed workbooks power the Report Builder and analysis output.";
    }
  }
  if (idxEl) {
    const ia = (payload && payload.persisted && payload.persisted.indexed_at) || pi.indexed_at;
    const lastScanned = ia ? `Last scanned: ${ia}` : "Not indexed yet";
    const capBit = cap ? ` · cap ${cap} Excel files/scan` : "";
    if (nIdx > 0 && liveN > 0) {
      idxEl.textContent = `Active workspace: ${workspaceRoot} · ${lastScanned} · Indexed workbooks: ${nIdx} · ${liveN} on disk${capBit}`;
    } else if (nIdx > 0) {
      idxEl.textContent = `Active workspace: ${workspaceRoot} · ${lastScanned} · Indexed workbooks: ${nIdx}${capBit}`;
    } else if (liveN > 0) {
      idxEl.textContent = `Active workspace: ${workspaceRoot} · ${lastScanned} · Indexed workbooks: 0 · ${liveN} on disk${capBit}`;
    } else {
      idxEl.textContent = `Active workspace: ${workspaceRoot} · ${lastScanned} · Indexed workbooks: 0${capBit}`;
    }
  }
  if (projects.length === 0) {
    const li = document.createElement("li");
    li.className = "project-library-empty";
    li.textContent =
      nIdx || (payload && payload.readiness && payload.readiness.workbook_count)
        ? "No project IDs found in file paths yet. Filenames with numeric project codes (e.g. 219128) improve grouping. Unlabeled files still appear as a group when present."
        : "No workbooks found in active workspace. Confirm the folder contains .xlsx/.xlsm/.xls files, then scan again.";
    list.appendChild(li);
  } else {
    projects.forEach((p) => {
      const li = document.createElement("li");
      const isUnl = p.is_unlabeled || p.project_id === "__unlabeled__";
      const isActiveRb = p.project_id != null && String(p.project_id) === String(reportBuilderProjectId);
      li.className =
        "project-library-item" +
        (p.is_last_project ? " project-library-item-active" : "") +
        (isActiveRb ? " project-library-item-active" : "") +
        (isUnl ? " project-library-item-unassigned" : "");
      const displayTitle = isUnl
        ? "Unassigned reports (no project ID detected)"
        : p.display_name || "Project " + p.project_id;
      const title = document.createElement("div");
      title.className = "project-library-line project-library-line-title";
      if (isUnl) {
        const w = document.createElement("span");
        w.className = "project-library-warn";
        w.setAttribute("aria-hidden", "true");
        w.textContent = "⚠ ";
        title.appendChild(w);
      }
      const titleText = document.createTextNode(displayTitle);
      title.appendChild(titleText);
      li.appendChild(title);
      const meta = document.createElement("div");
      meta.className = "project-library-line project-library-line-meta";
      meta.textContent = `project_id ${p.project_id || "—"} · ${p.report_count || 0} report(s) indexed · latest ${
        p.latest_version_date || p.latest_modified_at || "n/a"
      }`;
      li.appendChild(meta);
      if (p.last_compared) {
        const s = document.createElement("span");
        s.className = "subtle";
        s.textContent = ` last compare: ${p.last_compared}`;
        s.style.display = "block";
        s.style.marginBottom = "6px";
        li.appendChild(s);
      }
      if (p.project_id) {
        li.tabIndex = 0;
        li.setAttribute("role", "button");
        li.setAttribute("aria-label", isUnl ? "Select unassigned report group" : "Select project " + p.project_id);
        li.addEventListener("click", () => {
          void selectProjectForBuilder(p);
        });
        li.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            li.click();
          }
        });
      }
      list.appendChild(li);
    });
  }
  const tgl = document.getElementById("show-unassigned-toggle");
  if (tgl && !tgl.dataset.wired) {
    tgl.dataset.wired = "1";
    tgl.addEventListener("change", () => {
      if (lastProjectLibraryPayload) renderProjectLibrary(lastProjectLibraryPayload);
    });
  }
}

function fmtUsd(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  const sign = v < 0 ? "−" : "";
  return (
    sign +
    "$" +
    Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  );
}

async function selectProjectForBuilder(p) {
  const pid = String(p.project_id || "").trim();
  if (!pid) return;
  reportBuilderProjectId = pid;
  reportPathSelection.clear();
  const need = document.getElementById("report-builder-need-project");
  const card = document.getElementById("report-builder-project-card");
  if (need) need.setAttribute("hidden", "hidden");
  if (card) card.removeAttribute("hidden");
  updateProjectHeaderFromData(p, null);
  const hint = document.getElementById("report-selector-hint");
  if (hint) hint.textContent = "Loading indexed workbooks…";
  if (lastProjectLibraryPayload) renderProjectLibrary(lastProjectLibraryPayload);
  const queryText = pid === "__unlabeled__" ? "show reports for unlabeled" : "show reports for " + pid;
  try {
    const resp = await fetch("/api/local/assistant/task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workspace_root: operatorWorkspaceRoot,
        query: queryText,
        context: {
          run_id: operatorRunId(),
          selected_files: [],
          target_file: "",
          search_query: "",
          selected_pair_id: operatorSelectedPairId,
          last_confirmed_pair: lastConfirmedPair,
          preferred_report_family: preferredReportFamily,
        },
      }),
    });
    const data = await resp.json();
    const reports = (data.result && Array.isArray(data.result.reports) && data.result.reports) || [];
    reportBuilderRows = reports;
    renderReportSelectTable();
    updateProjectHeaderFromData(p, reports);
    if (hint) {
      hint.textContent = reports.length
        ? "Step 2: select one or more reports, then Step 3–4 below."
        : "No indexed workbooks for this selection. Try Scan workspace or pick another project.";
    }
    syncReportBuilderControls();
  } catch (e) {
    reportBuilderRows = [];
    renderReportSelectTable();
    if (need) need.removeAttribute("hidden");
    if (card) card.setAttribute("hidden", "hidden");
    reportBuilderProjectId = "";
    if (hint) hint.textContent = (e && e.message) || "Could not load reports.";
    if (lastProjectLibraryPayload) renderProjectLibrary(lastProjectLibraryPayload);
    updateReportBuilderSticky();
  }
}

function formatReportTableDate(iso) {
  if (!iso || String(iso).trim() === "" || String(iso) === "—") return "—";
  const s = String(iso).trim();
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return s;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function latestVersionFromReports(rows) {
  let best = "";
  if (!Array.isArray(rows)) return best;
  for (const r of rows) {
    const vd = String((r && r.version_date) || "").trim();
    if (vd && vd > best) best = vd;
  }
  return best;
}

function updateProjectHeaderFromData(p, reports) {
  const lineP = document.getElementById("report-builder-line-project");
  const lineC = document.getElementById("report-builder-line-count");
  const lineL = document.getElementById("report-builder-line-latest");
  const pid = String((p && p.project_id) || "").trim();
  const isUn = p && (p.is_unlabeled || pid === "__unlabeled__");
  if (lineP) {
    lineP.textContent = isUn ? "Unassigned reports" : "Project: " + pid;
  }
  if (lineC) {
    if (reports == null) lineC.textContent = "Loading reports…";
    else lineC.textContent = (reports.length || 0) + " reports available";
  }
  if (lineL) {
    if (reports == null) {
      lineL.textContent = "Latest: …";
    } else {
      const iso = latestVersionFromReports(reports);
      lineL.textContent = "Latest: " + (iso ? formatReportTableDate(iso) : "—");
    }
  }
  updateReportBuilderSourceSummary();
  updateReportBuilderSticky();
}

function updateReportBuilderSticky() {
  const title = document.getElementById("report-builder-sticky-project");
  const sub = document.getElementById("report-builder-sticky-sub");
  const kicker = document.getElementById("report-builder-context-kicker");
  if (!title || !sub) return;
  const pid = String(reportBuilderProjectId || "").trim();
  const lineP = document.getElementById("report-builder-line-project");
  const nIdx = Array.isArray(reportBuilderRows) ? reportBuilderRows.length : 0;
  const nSel = reportPathSelection && reportPathSelection.size ? reportPathSelection.size : 0;
  if (!pid) {
    if (kicker) kicker.textContent = "Current context";
    title.textContent = "No project selected";
    sub.textContent = "Choose a project in the library, then select workbooks.";
    return;
  }
  if (kicker) kicker.textContent = "Active project";
  title.textContent = lineP ? String(lineP.textContent || "") : "Project: " + pid;
  const latestLine = document.getElementById("report-builder-line-latest");
  const latestRaw = latestLine ? String(latestLine.textContent || "").replace(/^Latest:\s*/i, "").trim() : "";
  let line =
    nIdx + " indexed workbook(s)" +
    (latestRaw && latestRaw !== "…" && latestRaw !== "—" ? " · latest " + latestRaw : "");
  if (nSel > 0) {
    line = nSel + " selected · " + line;
  }
  sub.textContent = line;
}

function updateReportBuilderSourceSummary() {
  const sum = document.getElementById("report-builder-source-summary");
  if (!sum) return;
  const pid = String(reportBuilderProjectId || "").trim();
  if (!pid) {
    sum.textContent = "Workbooks & selection (pick a project in the library)";
    updateReportBuilderSticky();
    return;
  }
  const n = Array.isArray(reportBuilderRows) ? reportBuilderRows.length : 0;
  const latestLine = document.getElementById("report-builder-line-latest");
  const latestTxt = latestLine ? String(latestLine.textContent || "").replace(/^Latest:\s*/i, "").trim() : "";
  sum.textContent =
    "Project " +
    pid +
    " · " +
    n +
    " report(s)" +
    (latestTxt && latestTxt !== "…" && latestTxt !== "—" ? " · latest " + latestTxt : "") +
    " — expand to change workbooks";
  updateReportBuilderSticky();
}

function renderReportSelectTable() {
  const tbl = document.getElementById("report-select-table");
  const body = document.getElementById("report-select-body");
  if (!tbl || !body) return;
  body.innerHTML = "";
  if (!reportBuilderRows.length) {
    tbl.setAttribute("hidden", "hidden");
    return;
  }
  tbl.removeAttribute("hidden");
  reportBuilderRows.forEach((row, idx) => {
    const tr = document.createElement("tr");
    const path = String(row.path || "");
    const fileName = String(row.name || path.split("/").pop() || path);
    const dateRaw = row.version_date || "";
    const dateDisp = formatReportTableDate(dateRaw);
    const humanLine = dateDisp + " — " + fileName;

    const tdN = document.createElement("td");
    tdN.className = "report-row-idx subtle";
    tdN.textContent = String(idx + 1);

    const td0 = document.createElement("td");
    const cb = document.createElement("input");
    const cbId = "report-select-cb-" + idx;
    cb.type = "checkbox";
    cb.className = "report-check";
    cb.id = cbId;
    cb.setAttribute("data-path", path);
    cb.setAttribute("aria-label", "Select " + humanLine);
    cb.addEventListener("change", () => {
      if (cb.checked) reportPathSelection.add(path);
      else reportPathSelection.delete(path);
      syncReportBuilderControls();
    });
    td0.appendChild(cb);
    const td1 = document.createElement("td");
    td1.textContent = dateDisp;
    const td2 = document.createElement("td");
    td2.className = "report-filename";
    td2.textContent = fileName;
    td2.setAttribute("title", fileName);
    tr.appendChild(tdN);
    tr.appendChild(td0);
    tr.appendChild(td1);
    tr.appendChild(td2);
    body.appendChild(tr);
  });
  updateReportBuilderSourceSummary();
}

function syncReportBuilderControls() {
  const n = reportPathSelection.size;
  const sel = document.getElementById("analysis-type-select");
  const btn = document.getElementById("generate-signals-btn");
  const enHint = document.getElementById("analysis-enable-hint");
  const reasonEl = document.getElementById("generate-signals-reason");
  if (!sel || !btn) return;
  const en = (ops) => {
    Array.from(sel.querySelectorAll("option")).forEach((o) => {
      if (!o.value) return;
      o.disabled = !ops.has(o.value);
    });
  };
  btn.classList.remove("btn-generate-primary");
  if (n === 0) {
    en(new Set());
    sel.disabled = true;
    btn.disabled = true;
    if (enHint) enHint.textContent = "Select one or more monthly reports (Step 2).";
    if (reasonEl) reasonEl.textContent = "Select at least one report to enable analysis";
    updateReportBuilderSticky();
    return;
  }
  if (n === 1) {
    en(
      new Set([
        "current_profit_snapshot",
        "projected_profit_breakdown",
        "labor_rate_profit_analysis",
      ])
    );
  } else if (n === 2) {
    en(new Set(["compare_two_reports", "cost_movement_signals"]));
  } else {
    en(new Set(["trend_across_reports"]));
  }
  sel.disabled = false;
  const opt0 = Array.from(sel.querySelectorAll("option")).find((o) => o.value && !o.disabled);
  if (opt0 && (sel.value === "" || sel.querySelector(`option[value="${sel.value}"]`)?.disabled)) {
    sel.value = opt0.value;
  }
  btn.disabled = !sel.value;
  if (btn.disabled) {
    if (reasonEl) {
      reasonEl.textContent =
        n === 0
          ? "Select at least one report to enable analysis"
          : "Choose an analysis type (Step 3) to enable Run analysis";
    }
  } else {
    if (reasonEl) reasonEl.textContent = "";
    btn.classList.add("btn-generate-primary");
  }
  if (enHint) {
    if (n === 1) enHint.textContent = "One report: Current Profit, Projected Profit, or Labor Rate Profit.";
    else if (n === 2) enHint.textContent = "Two reports: compare or cost movement.";
    else enHint.textContent = "Three or more: trend, repeated movers, and watchlist (multi-period).";
  }
  updateReportBuilderSticky();
}

function workbenchComponentMap(fs) {
  const m = {};
  const wb = fs && fs.financial_workbench;
  if (wb && Array.isArray(wb.projected_profit_component_sources)) {
    wb.projected_profit_component_sources.forEach((c) => {
      if (c && c.id) m[c.id] = c;
    });
  }
  return m;
}

function financialWorkbenchHasUsefulData(wb) {
  if (wb == null || typeof wb !== "object" || Array.isArray(wb)) {
    return false;
  }
  const ppcs = wb.projected_profit_component_sources;
  if (Array.isArray(ppcs) && ppcs.length > 0) return true;
  const jtd = wb.jtd_cost_code_rows;
  if (Array.isArray(jtd) && jtd.length > 0) return true;
  const co = wb.change_order_rows;
  if (Array.isArray(co) && co.length > 0) return true;
  const lrp = wb.lrp_source_rows;
  if (Array.isArray(lrp) && lrp.length > 0) return true;
  const rec = wb.reconciliation;
  if (rec && Array.isArray(rec.lines) && rec.lines.length > 0) return true;
  return false;
}

function renderComponentDrilldown(cmp, fmtUsd) {
  const d = document.createElement("div");
  d.className = "cmp-drill";
  const p1 = document.createElement("p");
  p1.innerHTML = "<span class='subtle'>Source sheet:</span> ";
  p1.appendChild(document.createTextNode(cmp.source_sheet || "—"));
  d.appendChild(p1);
  if (cmp.cost_code) {
    const p2 = document.createElement("p");
    p2.innerHTML = "<span class='subtle'>Cost code / ref:</span> ";
    p2.appendChild(
      document.createTextNode(
        String(cmp.cost_code) + (cmp.cost_code_name ? " · " + String(cmp.cost_code_name) : "")
      )
    );
    d.appendChild(p2);
  }
  const p3 = document.createElement("p");
  p3.innerHTML = "<span class='subtle'>Extracted value:</span> ";
  p3.appendChild(document.createTextNode(fmtUsd(cmp.value)));
  d.appendChild(p3);
  if (cmp.derivation) {
    const p4 = document.createElement("p");
    p4.className = "subtle small";
    p4.textContent = String(cmp.derivation);
    d.appendChild(p4);
  }
  if (Array.isArray(cmp.limitations) && cmp.limitations.length) {
    const p5 = document.createElement("p");
    p5.className = "subtle small";
    p5.appendChild(document.createTextNode("Limitations: " + cmp.limitations.map((x) => String(x)).join(" · ")));
    d.appendChild(p5);
  }
  return d;
}

const DEFAULT_FINANCIAL_WB_STATE = {
  activePanel: "codes",
  codePrefix: "all",
  codeNamespace: "all",
  codeSearch: "",
  codeNonZero: true,
  codeSort: "ucb",
  coFilter: "all",
  coSearch: "",
  lrpSearch: "",
  recSearch: "",
  bannerText: null,
  componentLink: null,
  selectedCodeKey: null,
  selectedCoKey: null,
  selectedLrpKey: null,
};
const financialWbState = Object.assign({}, DEFAULT_FINANCIAL_WB_STATE);
function resetFinancialWbState() {
  Object.assign(financialWbState, DEFAULT_FINANCIAL_WB_STATE);
}
function workbenchCoSourceNoteText(wps) {
  if (!wps) return "—";
  const a = wps.change_order_source_notes;
  if (Array.isArray(a) && a.length) {
    return a.map((x) => String(x)).join(" · ");
  }
  const j = wps.jtd_profit_extraction && wps.jtd_profit_extraction.change_order_source_notes;
  if (Array.isArray(j) && j.length) {
    return j.map((x) => String(x)).join(" · ");
  }
  if (typeof j === "string" && j.trim()) {
    return j;
  }
  return "—";
}
function lrpRowExcelOrDerived(r) {
  if (r && r.excel_row != null && r.excel_row !== "") {
    return String(r.excel_row);
  }
  const d = r && r.derivation && String(r.derivation);
  if (!d) return "—";
  const m = d.match(/excel_row[=:]\s*(\d+)/i);
  return m ? m[1] : "—";
}
function jtdCodePrefix(c) {
  const s = String(c || "")
    .trim()
    .replace(/^N/i, "");
  return s.split(".")[0].replace(/[^0-9]/g, "");
}
function jtdRowNormFamily(r) {
  if (!r) return "";
  const n = r.normalized_cost_code;
  if (n != null && String(n).trim() !== "") {
    return jtdCodePrefix(n);
  }
  return jtdCodePrefix(r.display_cost_code || r.cost_code);
}
function workbenchRowDisplayCode(r) {
  if (!r) return "—";
  const d = (r.display_cost_code || r.cost_code || "").trim();
  return d || "—";
}
function workbenchRowHasDisplayNormalizingRaw(r) {
  if (!r) return false;
  const raw = r.raw_cost_code != null ? String(r.raw_cost_code).trim() : "";
  if (!raw) return false;
  const disp = (r.display_cost_code != null && String(r.display_cost_code).trim() !== ""
    ? String(r.display_cost_code)
    : String(r.cost_code || "")
  ).trim();
  return disp !== "" && raw !== disp;
}
function workbenchNamespaceLabel(ns) {
  if (ns === "numeric") return "Numeric (original)";
  if (ns === "n_prefixed") return "N-prefixed (extended)";
  return "—";
}
function workbenchRoleLabel(role) {
  if (role === "cm_fee") return "CM fee";
  if (role === "prior_system_profit") return "Prior-system profit";
  if (role === "pco_profit") return "PCO profit";
  if (role === "owner_change_order") return "Owner change order";
  if (role === "cm_change_order") return "CM change order";
  return "—";
}
function workbenchLrpRowCategory(r) {
  const ln = String((r && r.line) || "").toLowerCase();
  if (ln.indexOf("adjust") >= 0) return "Adjustments";
  if (ln.indexOf("billed") >= 0) return "Billed";
  if (ln.indexOf("actual") >= 0) return "Actual";
  if (ln.indexOf("labor rate profit") >= 0 || ln.indexOf("final labor") >= 0) return "LRP";
  return "—";
}
function workbenchComponentFilterHeading(st) {
  const id = st.componentLink;
  if (id === "cm_fee") {
    return "Showing JTD rows with role CM fee (component_role = cm_fee)";
  }
  if (id === "pco_profit") {
    return "Showing JTD rows with role PCO profit (component_role = pco_profit)";
  }
  if (id === "prior_system_profit") {
    return "Showing JTD rows with role Prior-system profit (component_role = prior_system_profit)";
  }
  if (id === "change_orders") {
    return "Showing JTD change-order lines contributing to Change Orders (18 / 21 family)";
  }
  if (id === "labor_rate_profit_to_date") {
    return "Showing LRP workbench lines (billed, actual, and LRP to date)";
  }
  if (id === "variance") {
    return "Showing reconciliation for Variance (formula vs workbook)";
  }
  if (id === "workbook_reported_tpp") {
    return "Showing reconciliation for workbook-reported TPP";
  }
  if (st.bannerText) {
    return "Showing: " + st.bannerText;
  }
  return null;
}
function filterJtdRowsForState(jtdRows, st) {
  const q = (st.codeSearch || "").toLowerCase().trim();
  const pr = st.codePrefix;
  const onlyNz = st.codeNonZero;
  let list = (jtdRows || []).slice();
  if (onlyNz) {
    list = list.filter((r) => Number(r.update_current_budget) !== 0);
  }
  const comp = st.componentLink;
  if (comp === "cm_fee") {
    list = list.filter((r) => r.component_role === "cm_fee");
  } else if (comp === "prior_system_profit") {
    list = list.filter((r) => r.component_role === "prior_system_profit");
  } else if (comp === "pco_profit") {
    list = list.filter((r) => r.component_role === "pco_profit");
  }
  const nsF = st.codeNamespace || "all";
  if (nsF === "numeric") {
    list = list.filter((r) => r.cost_code_namespace === "numeric");
  } else if (nsF === "n_prefixed") {
    list = list.filter((r) => r.cost_code_namespace === "n_prefixed");
  }
  if (pr && pr !== "all") {
    list = list.filter((r) => jtdRowNormFamily(r).startsWith(pr));
  }
  if (q) {
    list = list.filter(
      (r) =>
        (
          String(r.display_cost_code || r.cost_code || "") +
          " " +
          String(r.raw_cost_code || "") +
          " " +
          String(r.cost_code_name || "")
        )
          .toLowerCase()
          .indexOf(q) >= 0
    );
  }
  return list;
}
function countCoRowsForFilter(coRows, coFilter) {
  return (coRows || []).filter((r) => coFilter === "all" || r.co_type === coFilter).length;
}
function coRowsMatchingFilter(coRows, st) {
  const q = (st.coSearch || "").trim().toLowerCase();
  return (coRows || []).filter((r) => {
    if (!r) return false;
    if (st.coFilter !== "all" && r.co_type !== st.coFilter) return false;
    if (!q) return true;
    const hay = (
      String(r.cost_code_name || "") +
      " " +
      workbenchRowDisplayCode(r) +
      " " +
      String(r.co_type || "")
    ).toLowerCase();
    return hay.indexOf(q) >= 0;
  });
}
function filterJtdBaselineCount(jtdRows, st) {
  const stWide = Object.assign({}, st, {
    codeSearch: "",
    codePrefix: "all",
    codeNamespace: "all",
    codeNonZero: false,
  });
  return filterJtdRowsForState(jtdRows, stWide).length;
}
function lrpRowsMatchingFilter(lrpRows, st) {
  const q = (st.lrpSearch || "").trim().toLowerCase();
  if (!q) return (lrpRows || []).slice();
  return (lrpRows || []).filter((r) => {
    if (!r) return false;
    const hay = (
      String(r.line || "") +
      " " +
      workbenchLrpRowCategory(r) +
      " " +
      String(r.derivation || "")
    ).toLowerCase();
    return hay.indexOf(q) >= 0;
  });
}
function recLinesMatchingFilter(recLines, st) {
  const q = (st.recSearch || "").trim().toLowerCase();
  if (!q) return (recLines || []).slice();
  return (recLines || []).filter((ln) => {
    if (!ln) return false;
    const hay = (String(ln.label || "") + " " + String(ln.source || "")).toLowerCase();
    return hay.indexOf(q) >= 0;
  });
}
function workbenchRecRowKind(label) {
  const s = String(label || "");
  if (s.indexOf("Variance") >= 0) return "rec-variance";
  if (s.indexOf("Workbook-reported") >= 0) return "rec-workbook";
  if (s.indexOf("Computed total projected") >= 0) return "rec-tpp";
  return "rec-line";
}
function profitComponentWorkbenchSummary(wb, compId) {
  if (!wb || !financialWorkbenchHasUsefulData(wb)) {
    return "Workbench data is not available for this analysis type.";
  }
  const jtd = (wb && wb.jtd_cost_code_rows) || [];
  const co = (wb && wb.change_order_rows) || [];
  const lrp = (wb && wb.lrp_source_rows) || [];
  const rec = (wb && wb.reconciliation) || {};
  const nRec = (rec.lines || []).length;
  const stPreview = { codePrefix: "all", codeNamespace: "all", codeSearch: "", codeNonZero: true };
  if (compId === "labor_rate_profit_to_date") {
    return "Workbench: LRP breakdown tab · " + lrp.length + " LRP line" + (lrp.length === 1 ? "" : "s");
  }
  if (compId === "variance" || compId === "workbook_reported_tpp") {
    return "Workbench: Reconciliation tab · " + nRec + " line" + (nRec === 1 ? "" : "s");
  }
  if (compId === "change_orders") {
    return "Workbench: Change orders tab · " + co.length + " JTD line" + (co.length === 1 ? "" : "s");
  }
  if (compId === "cm_fee") {
    const n = (jtd || []).filter((r) => r && r.component_role === "cm_fee").length;
    return "Cost code detail · " + n + " row" + (n === 1 ? "" : "s") + " (CM fee role)";
  }
  if (compId === "pco_profit") {
    const n = (jtd || []).filter((r) => r && r.component_role === "pco_profit").length;
    return "Cost code detail · " + n + " row" + (n === 1 ? "" : "s") + " (PCO profit role)";
  }
  if (compId === "prior_system_profit") {
    const n = (jtd || []).filter((r) => r && r.component_role === "prior_system_profit").length;
    return "Cost code detail · " + n + " row" + (n === 1 ? "" : "s") + " (Prior-system profit role)";
  }
  const n = filterJtdRowsForState(jtd, stPreview).length;
  return "Cost code detail · " + n + " row" + (n === 1 ? "" : "s") + " (all prefixes; refine in workbench).";
}

function renderFinancialWorkbench(wb, wps) {
  const root = document.createElement("div");
  root.className = "financial-workbench";
  const st = financialWbState;
  const jtdName = (wb && wb.jtd_sheet) || "JTD";
  const lbrName = (wb && wb.lbr_sheet) || "LBR";
  const jtdRows = (wb && wb.jtd_cost_code_rows) || [];
  const coRows = (wb && wb.change_order_rows) || [];
  const lrpRows = (wb && wb.lrp_source_rows) || [];
  const lbrScan = (wb && wb.lbr_workbook_rows) || [];
  const rec = (wb && wb.reconciliation) || {};

  const h = document.createElement("h3");
  h.className = "signals-heading workbench-title";
  h.textContent = "Financial workbench";
  const banner = document.createElement("div");
  banner.className = "workbench-filter-banner";
  banner.setAttribute("role", "status");
  const bannerText = document.createElement("p");
  bannerText.className = "workbench-filter-banner-text";
  const clearF = document.createElement("button");
  clearF.type = "button";
  clearF.className = "workbench-filter-clear";
  clearF.textContent = "Clear filter";
  banner.appendChild(bannerText);
  banner.appendChild(clearF);

  const tabBar = document.createElement("div");
  tabBar.className = "workbench-tabs";
  tabBar.setAttribute("role", "tablist");
  const panelBox = document.createElement("div");
  panelBox.className = "workbench-panels workbench-panels--primary";
  const panes = [];
  const ref = { coRender: null, lrpRender: null, recRender: null, _coEls: null, _lrpEls: null, _recEls: null };

  const addTab = (id, label, build) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "workbench-tab";
    b.setAttribute("role", "tab");
    b.setAttribute("data-wb-panel", id);
    b.setAttribute("aria-selected", panes.length === 0 ? "true" : "false");
    b.textContent = label;
    const panel = document.createElement("div");
    panel.className = "workbench-panel";
    panel.setAttribute("role", "tabpanel");
    panel.setAttribute("data-wb-panel", id);
    panel.hidden = panes.length > 0;
    build(panel);
    tabBar.appendChild(b);
    panelBox.appendChild(panel);
    panes.push({ id, b, panel });
  };

  addTab("codes", "JTD Cost Codes", (panel) => {
    const blockCtl = document.createElement("div");
    blockCtl.className = "workbench-block--controls";
    const blockTbl = document.createElement("div");
    blockTbl.className = "workbench-block--table";
    const ph = document.createElement("p");
    ph.className = "subtle small workbench-hint";
    ph.textContent = "Rows from " + jtdName + " (Update Current Budget).";
    const totalsPanel = document.createElement("div");
    totalsPanel.className = "workbench-project-cost-totals subtle small";
    function updateProjectCostTotals() {
      const o = wps && wps.total_original_project_costs;
      const e = wps && wps.total_extended_project_costs;
      totalsPanel.textContent =
        "Total original project costs (numeric codes): " +
        (o != null && o !== "" ? fmtUsd(o) : "—") +
        " · Total extended project costs (N-prefixed codes): " +
        (e != null && e !== "" ? fmtUsd(e) : "—");
    }
    updateProjectCostTotals();
    const tools = document.createElement("div");
    tools.className = "workbench-tools";
    const search = document.createElement("input");
    search.type = "search";
    search.className = "workbench-search";
    search.setAttribute("autocomplete", "off");
    search.placeholder = "Filter by code or name";
    const pref = document.createElement("select");
    pref.className = "workbench-select";
    [["all", "All prefixes"], ["18", "18…"], ["21", "21…"], ["30", "30…"], ["40", "40…"]].forEach(
      ([v, t]) => {
        const o = document.createElement("option");
        o.value = v;
        o.textContent = t;
        pref.appendChild(o);
      }
    );
    const nz = document.createElement("label");
    nz.className = "workbench-cb";
    const nzIn = document.createElement("input");
    nzIn.type = "checkbox";
    nzIn.checked = true;
    nz.appendChild(nzIn);
    nz.appendChild(document.createTextNode(" Non-zero only"));
    const nsSel = document.createElement("select");
    nsSel.className = "workbench-select";
    nsSel.setAttribute("aria-label", "Filter by cost code namespace");
    [
      ["all", "Namespace: All"],
      ["numeric", "Numeric / original"],
      ["n_prefixed", "N-prefixed / extended"],
    ].forEach(([v, t]) => {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = t;
      nsSel.appendChild(o);
    });
    const sumBarCodes = document.createElement("div");
    sumBarCodes.className = "financial-table-summary-bar";
    sumBarCodes.setAttribute("role", "status");
    const tableWrap = document.createElement("div");
    tableWrap.className = "workbench-table-wrap workbench-table-wrap--codes";
    const table = document.createElement("table");
    table.className = "workbench-table data-table fin-wb-table";
    table.setAttribute("data-fin-mode", "orig-cur");
    const thead = document.createElement("thead");
    thead.innerHTML =
      "<tr><th>Code</th><th>Namespace</th><th>Role</th><th>Name</th><th>Update current budget</th><th>Original budget</th><th>Row</th></tr>";
    const tbody = document.createElement("tbody");
    const tfootCodes = document.createElement("tfoot");
    tfootCodes.className = "fin-wb-tfoot";
    const ftrCodes = document.createElement("tr");
    ftrCodes.innerHTML =
      "<td colspan='4' class='fin-foot-lead subtle'></td>" +
      "<td class='wb-num fin-foot-cur'></td>" +
      "<td class='wb-num fin-foot-orig'></td>" +
      "<td class='wb-num fin-foot-delta'></td>";
    tfootCodes.appendChild(ftrCodes);
    table.appendChild(thead);
    table.appendChild(tbody);
    table.appendChild(tfootCodes);
    tableWrap.appendChild(table);
    const sortL = document.createElement("div");
    sortL.className = "workbench-tools";
    const sortSel = document.createElement("select");
    sortSel.className = "workbench-select";
    [
      ["ucb", "Sort: UCB value"],
      ["code", "Sort: code"],
    ].forEach(([v, t]) => {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = t;
      sortSel.appendChild(o);
    });
    sortL.appendChild(sortSel);
    const rowDetail = document.createElement("div");
    rowDetail.className = "workbench-row-detail";
    rowDetail.setAttribute("hidden", "hidden");

    function showRowDetail(r) {
      rowDetail.removeAttribute("hidden");
      const src = (r && r.source_sheet) || jtdName;
      const idx = r.excel_row != null ? r.excel_row : "—";
      const ucb = r.update_current_budget;
      const ob = r.original_budget;
      rowDetail.innerHTML = "";
      const t = document.createElement("p");
      t.className = "workbench-row-detail-title";
      t.textContent = "Display: " + workbenchRowDisplayCode(r);
      const p0 = document.createElement("p");
      p0.className = "subtle small";
      p0.textContent = "Source sheet: " + src;
      const p1 = document.createElement("p");
      p1.className = "subtle small";
      p1.textContent = "Row index: " + idx;
      const p2 = document.createElement("p");
      p2.className = "workbench-row-detail-value";
      p2.appendChild(
        document.createTextNode(
          "Value breakdown — UCB: " + fmtUsd(ucb) + (ob != null ? " · Original budget: " + fmtUsd(ob) : "")
        )
      );
      rowDetail.appendChild(t);
      const pNs = document.createElement("p");
      pNs.className = "subtle small";
      pNs.textContent =
        "Namespace: " +
        workbenchNamespaceLabel(r.cost_code_namespace) +
        " · Role: " +
        workbenchRoleLabel(r.component_role);
      rowDetail.appendChild(pNs);
      if (workbenchRowHasDisplayNormalizingRaw(r)) {
        const praw = document.createElement("p");
        praw.className = "wb-excel-code-note";
        praw.textContent =
          "Excel code: " +
          String(r.raw_cost_code).trim() +
          " (display may use N-prefix for legacy consistency; namespace follows raw Excel)";
        rowDetail.appendChild(praw);
      }
      if (r.cost_code_name) {
        const p3 = document.createElement("p");
        p3.className = "subtle small";
        p3.textContent = "Name: " + r.cost_code_name;
        rowDetail.appendChild(p3);
      }
      rowDetail.appendChild(p0);
      rowDetail.appendChild(p1);
      rowDetail.appendChild(p2);
    }

    function applyCodes() {
      st.codeSearch = search.value;
      st.codePrefix = pref.value;
      st.codeNamespace = nsSel.value;
      st.codeNonZero = nzIn.checked;
      st.codeSort = sortSel.value;
      updateProjectCostTotals();
      const yBase = filterJtdBaselineCount(jtdRows, st);
      table.dataset.finTotalRows = String(yBase);
      let list = filterJtdRowsForState(jtdRows, st);
      if (st.codeSort === "code") {
        list.sort((a, b) =>
          String(workbenchRowDisplayCode(a)).localeCompare(String(workbenchRowDisplayCode(b)))
        );
      } else {
        list.sort(
          (a, b) =>
            Math.abs(Number(b.update_current_budget || 0)) - Math.abs(Number(a.update_current_budget || 0))
        );
      }
      tbody.innerHTML = "";
      if (list.length === 0) {
        const trM = document.createElement("tr");
        trM.className = "fin-table-empty-msg";
        trM.setAttribute("data-row-kind", "empty");
        trM.innerHTML =
          "<td colspan='7' class='subtle'>" +
          (jtdRows.length === 0
            ? "No JTD cost code rows in workbench extract."
            : "No rows match the current filters.") +
          "</td>";
        tbody.appendChild(trM);
      } else {
        list.forEach((r) => {
          const tr = document.createElement("tr");
          const key =
            String(r.raw_cost_code || r.cost_code || "") + "|" + String(r.excel_row != null ? r.excel_row : "");
          if (st.selectedCodeKey && st.selectedCodeKey === key) {
            tr.className = "wb-row--selected";
          }
          tr.style.cursor = "pointer";
          tr.addEventListener("click", (ev) => {
            ev.stopPropagation();
            st.selectedCodeKey = key;
            st.selectedCoKey = null;
            st.selectedLrpKey = null;
            if (ref._coEls && ref._coEls.coRowDetail) {
              ref._coEls.coRowDetail.setAttribute("hidden", "hidden");
            }
            if (ref._lrpEls && ref._lrpEls.lrpRowDetail) {
              ref._lrpEls.lrpRowDetail.setAttribute("hidden", "hidden");
            }
            showRowDetail(r);
            applyCodes();
          });
          tr.innerHTML =
            "<td class='wb-mono'>" +
            workbenchRowDisplayCode(r) +
            "</td><td class='subtle'>" +
            workbenchNamespaceLabel(r.cost_code_namespace) +
            "</td><td class='subtle'>" +
            workbenchRoleLabel(r.component_role) +
            "</td><td>" +
            (r.cost_code_name || "—") +
            "</td><td class='wb-num'>" +
            fmtUsd(r.update_current_budget) +
            "</td><td class='wb-num'>" +
            (r.original_budget != null ? fmtUsd(r.original_budget) : "—") +
            "</td><td class='subtle wb-num'>" +
            (r.excel_row != null ? r.excel_row : "—") +
            "</td>";
          const ucb = Number(r.update_current_budget) || 0;
          const ob =
            r.original_budget != null && !Number.isNaN(Number(r.original_budget))
              ? Number(r.original_budget)
              : null;
          tr.setAttribute("data-row-kind", "jtd-code");
          tr.setAttribute("data-current", String(ucb));
          if (ob != null) tr.setAttribute("data-original", String(ob));
          tr.setAttribute("data-delta", String(ob != null ? ucb - ob : ucb));
          tbody.appendChild(tr);
        });
      }
      if (typeof updateFinancialTableFooter === "function") {
        updateFinancialTableFooter(table, { totalRowCount: yBase });
      }
      updateFilterBanner();
    }

    search.addEventListener("input", () => {
      applyCodes();
    });
    pref.addEventListener("change", () => {
      applyCodes();
    });
    nsSel.addEventListener("change", () => {
      applyCodes();
    });
    nzIn.addEventListener("change", () => {
      applyCodes();
    });
    sortSel.addEventListener("change", () => {
      applyCodes();
    });
    blockCtl.appendChild(ph);
    blockCtl.appendChild(totalsPanel);
    blockCtl.appendChild(tools);
    tools.appendChild(search);
    tools.appendChild(pref);
    tools.appendChild(nsSel);
    tools.appendChild(nz);
    blockCtl.appendChild(sortL);
    blockTbl.appendChild(sumBarCodes);
    blockTbl.appendChild(tableWrap);
    blockTbl.appendChild(rowDetail);
    panel.appendChild(blockCtl);
    panel.appendChild(blockTbl);
    ref._codesEls = { search, pref, nsSel, nzIn, sortSel, applyCodes, rowDetail, showRowDetail };
  });

  addTab("co", "Change Orders", (panel) => {
    const blockCtlCo = document.createElement("div");
    blockCtlCo.className = "workbench-block--controls";
    const blockTblCo = document.createElement("div");
    blockTblCo.className = "workbench-block--table";
    const so = coRows
      .filter((r) => r && r.co_type === "Owner")
      .reduce((s, r) => s + (Number(r.update_current_budget) || 0), 0);
    const sc = coRows
      .filter((r) => r && r.co_type === "CM")
      .reduce((s, r) => s + (Number(r.update_current_budget) || 0), 0);
    const oMatch = Math.abs((Number(wps.owner_change_orders_value) || 0) - so) < 0.02;
    const cMatch = Math.abs((Number(wps.cm_change_orders_value) || 0) - sc) < 0.02;
    const ph = document.createElement("p");
    ph.className = "subtle small workbench-hint";
    ph.textContent =
      "JTD change-order lines (18 / 21 family). " +
      "Owner count " +
      (wps.owner_change_orders_count != null ? wps.owner_change_orders_count : "—") +
      ", CM count " +
      (wps.cm_change_orders_count != null ? wps.cm_change_orders_count : "—") +
      ". " +
      (oMatch && cMatch
        ? "Line sums match summary totals (within $0.02)."
        : "Reconcile with summary; floating-point or hidden rows can differ from table.");
    const fbar = document.createElement("div");
    fbar.className = "workbench-tools workbench-cofilter";
    const fAll = document.createElement("button");
    fAll.type = "button";
    fAll.className = "wb-filter-btn is-active";
    fAll.setAttribute("data-cof", "all");
    fAll.textContent = "All";
    const fO = document.createElement("button");
    fO.type = "button";
    fO.className = "wb-filter-btn";
    fO.setAttribute("data-cof", "Owner");
    fO.textContent = "Owner only";
    const fC = document.createElement("button");
    fC.type = "button";
    fC.className = "wb-filter-btn";
    fC.setAttribute("data-cof", "CM");
    fC.textContent = "CM only";
    fbar.appendChild(fAll);
    fbar.appendChild(fO);
    fbar.appendChild(fC);
    const coTools = document.createElement("div");
    coTools.className = "workbench-tools";
    const coSearchIn = document.createElement("input");
    coSearchIn.type = "search";
    coSearchIn.className = "workbench-search";
    coSearchIn.setAttribute("autocomplete", "off");
    coSearchIn.placeholder = "Filter by code or name";
    coTools.appendChild(coSearchIn);
    const coNote = workbenchCoSourceNoteText(wps);
    const sumBarCo = document.createElement("div");
    sumBarCo.className = "financial-table-summary-bar";
    sumBarCo.setAttribute("role", "status");
    const tableWrap = document.createElement("div");
    tableWrap.className = "workbench-table-wrap workbench-table-wrap--co";
    const table = document.createElement("table");
    table.className = "workbench-table data-table fin-wb-table";
    table.setAttribute("data-fin-mode", "co-ucb");
    const thead = document.createElement("thead");
    thead.innerHTML =
      "<tr><th>Type</th><th>Code</th><th>Name</th><th>Update current budget</th><th>Source</th><th>Row</th></tr>";
    const tbody = document.createElement("tbody");
    const tfootCo = document.createElement("tfoot");
    tfootCo.className = "fin-wb-tfoot";
    const ftrCo = document.createElement("tr");
    ftrCo.innerHTML =
      "<td colspan='3' class='fin-foot-lead subtle'></td>" +
      "<td class='wb-num fin-foot-cur'></td>" +
      "<td colspan='2' class='subtle fin-foot-co-meta'>Total change order UCB (visible)</td>";
    tfootCo.appendChild(ftrCo);
    table.appendChild(thead);
    table.appendChild(tbody);
    table.appendChild(tfootCo);
    tableWrap.appendChild(table);
    const coRowDetail = document.createElement("div");
    coRowDetail.className = "workbench-row-detail workbench-row-detail--co";
    coRowDetail.setAttribute("hidden", "hidden");
    function showCoRowDetail(r) {
      coRowDetail.removeAttribute("hidden");
      coRowDetail.innerHTML = "";
      const typ = (r && r.co_type) || "—";
      const title = document.createElement("p");
      title.className = "workbench-row-detail-title";
      title.textContent = "Selected change order line";
      const p1 = document.createElement("p");
      p1.className = "subtle small";
      p1.textContent = "Type: " + typ;
      const p2 = document.createElement("p");
      p2.className = "subtle small";
      p2.textContent = "Cost code: " + workbenchRowDisplayCode(r);
      const p3 = document.createElement("p");
      p3.className = "subtle small";
      p3.textContent = "Cost code name: " + (r.cost_code_name || "—");
      const p4 = document.createElement("p");
      p4.className = "workbench-row-detail-value";
      p4.appendChild(
        document.createTextNode("Update current budget: " + fmtUsd(r && r.update_current_budget))
      );
      const p5 = document.createElement("p");
      p5.className = "subtle small";
      p5.textContent = "Source sheet: " + (r && r.source_sheet ? r.source_sheet : jtdName);
      const p6 = document.createElement("p");
      p6.className = "subtle small";
      p6.textContent = "Excel row: " + (r && r.excel_row != null ? r.excel_row : "—");
      const p7 = document.createElement("p");
      p7.className = "subtle small";
      p7.appendChild(document.createTextNode("Source note: " + coNote));
      const parts = [title, p1, p2, p3, p4, p5, p6, p7];
      if (workbenchRowHasDisplayNormalizingRaw(r)) {
        const praw = document.createElement("p");
        praw.className = "wb-excel-code-note";
        praw.textContent =
          "Excel code: " +
          String(r.raw_cost_code).trim() +
          " (display normalized for legacy consistency)";
        parts.splice(3, 0, praw);
      }
      parts.forEach((el) => coRowDetail.appendChild(el));
    }
    const render = () => {
      st.coSearch = coSearchIn.value;
      const yBase = coRowsMatchingFilter(coRows, Object.assign({}, st, { coSearch: "" })).length;
      table.dataset.finTotalRows = String(yBase);
      const visibleList = coRowsMatchingFilter(coRows, st);
      tbody.innerHTML = "";
      if (visibleList.length === 0) {
        const trM = document.createElement("tr");
        trM.className = "fin-table-empty-msg";
        trM.setAttribute("data-row-kind", "empty");
        trM.innerHTML =
          "<td colspan='6' class='subtle'>" +
          (coRows.length === 0
            ? "No change order rows in workbench extract."
            : "No rows match the current filters.") +
          "</td>";
        tbody.appendChild(trM);
      } else {
        visibleList.forEach((r) => {
          const tr = document.createElement("tr");
          const ckey =
            String(r.co_type || "") +
            "|" +
            String(r.raw_cost_code || r.cost_code || "") +
            "|" +
            String(r.excel_row != null ? r.excel_row : "");
          if (st.selectedCoKey && st.selectedCoKey === ckey) {
            tr.className = "wb-row--selected";
          }
          tr.style.cursor = "pointer";
          tr.addEventListener("click", (ev) => {
            ev.stopPropagation();
            st.selectedCoKey = ckey;
            st.selectedCodeKey = null;
            st.selectedLrpKey = null;
            if (ref._codesEls && ref._codesEls.rowDetail) {
              ref._codesEls.rowDetail.setAttribute("hidden", "hidden");
            }
            if (ref._lrpEls && ref._lrpEls.lrpRowDetail) {
              ref._lrpEls.lrpRowDetail.setAttribute("hidden", "hidden");
            }
            showCoRowDetail(r);
            render();
          });
          tr.innerHTML =
            "<td>" +
            (r.co_type || "—") +
            "</td><td class='wb-mono'>" +
            workbenchRowDisplayCode(r) +
            "</td><td>" +
            (r.cost_code_name || "—") +
            "</td><td class='wb-num'>" +
            fmtUsd(r.update_current_budget) +
            "</td><td class='subtle'>" +
            (r.source_sheet || jtdName) +
            "</td><td class='subtle wb-num'>" +
            (r.excel_row != null ? r.excel_row : "—") +
            "</td>";
          const ucb = Number(r.update_current_budget) || 0;
          tr.setAttribute("data-row-kind", "co-line");
          tr.setAttribute("data-current", String(ucb));
          tr.setAttribute("data-total", String(ucb));
          tbody.appendChild(tr);
        });
      }
      if (typeof updateFinancialTableFooter === "function") {
        updateFinancialTableFooter(table, { totalRowCount: yBase });
      }
      updateFilterBanner();
    };
    coSearchIn.addEventListener("input", () => {
      render();
    });
    fbar.addEventListener("click", (ev) => {
      const t = ev.target;
      if (t.getAttribute("data-cof")) {
        st.coFilter = t.getAttribute("data-cof");
        st.selectedCoKey = null;
        if (coRowDetail) {
          coRowDetail.setAttribute("hidden", "hidden");
          coRowDetail.innerHTML = "";
        }
        fbar.querySelectorAll(".wb-filter-btn").forEach((b) => b.classList.remove("is-active"));
        t.classList.add("is-active");
        render();
      }
    });
    ref.coRender = render;
    ref._coEls = { coRowDetail, showCoRowDetail, coSearchIn };
    blockCtlCo.appendChild(ph);
    blockCtlCo.appendChild(fbar);
    blockCtlCo.appendChild(coTools);
    blockTblCo.appendChild(sumBarCo);
    blockTblCo.appendChild(tableWrap);
    blockTblCo.appendChild(coRowDetail);
    panel.appendChild(blockCtlCo);
    panel.appendChild(blockTblCo);
    render();
  });

  addTab("lrp", "LRP Breakdown", (panel) => {
    const blockCtlLrp = document.createElement("div");
    blockCtlLrp.className = "workbench-block--controls";
    const blockTblLrp = document.createElement("div");
    blockTblLrp.className = "workbench-block--table";
    const ph = document.createElement("p");
    ph.className = "subtle small workbench-hint";
    ph.textContent =
      "Billed, actual, and labor rate profit (LRP) from " +
      lbrName +
      ". Optional raw line scan is under “Additional LBR scan data” when present.";
    const lrpTools = document.createElement("div");
    lrpTools.className = "workbench-tools";
    const lrpSearchIn = document.createElement("input");
    lrpSearchIn.type = "search";
    lrpSearchIn.className = "workbench-search";
    lrpSearchIn.setAttribute("autocomplete", "off");
    lrpSearchIn.placeholder = "Filter by component or notes";
    lrpTools.appendChild(lrpSearchIn);
    const sumBarLrp = document.createElement("div");
    sumBarLrp.className = "financial-table-summary-bar";
    sumBarLrp.setAttribute("role", "status");
    const tWrap = document.createElement("div");
    tWrap.className = "workbench-table-wrap workbench-table-wrap--lrp-main";
    const table = document.createElement("table");
    table.className = "workbench-table data-table fin-wb-table";
    table.setAttribute("data-fin-mode", "lrp-total");
    const thead = document.createElement("thead");
    thead.innerHTML = "<tr><th>Component</th><th>Value</th><th>Notes</th></tr>";
    const tbody = document.createElement("tbody");
    const tfootLrp = document.createElement("tfoot");
    tfootLrp.className = "fin-wb-tfoot";
    const ftrLrp = document.createElement("tr");
    ftrLrp.innerHTML =
      "<td class='fin-foot-lead subtle'></td>" +
      "<td class='wb-num fin-foot-cur'></td>" +
      "<td class='subtle fin-foot-lrp-meta'>Total LRP line values (visible)</td>";
    tfootLrp.appendChild(ftrLrp);
    table.appendChild(thead);
    table.appendChild(tbody);
    table.appendChild(tfootLrp);
    tWrap.appendChild(table);
    const lrpRowDetail = document.createElement("div");
    lrpRowDetail.className = "workbench-row-detail workbench-row-detail--lrp";
    lrpRowDetail.setAttribute("hidden", "hidden");
    function showLrpRowDetail(r) {
      lrpRowDetail.removeAttribute("hidden");
      lrpRowDetail.innerHTML = "";
      const t0 = document.createElement("p");
      t0.className = "workbench-row-detail-title";
      t0.textContent = "LRP workbench line";
      const t1 = document.createElement("p");
      t1.className = "subtle small";
      t1.appendChild(document.createTextNode("Label: " + (r.line || "—")));
      const t2 = document.createElement("p");
      t2.className = "workbench-row-detail-value";
      t2.appendChild(
        document.createTextNode(
          "Value: " + (r.value != null && r.value !== "" ? fmtUsd(r.value) : "—")
        )
      );
      const t3 = document.createElement("p");
      t3.className = "subtle small";
      t3.textContent = "Source sheet: " + lbrName;
      const t4 = document.createElement("p");
      t4.className = "subtle small";
      t4.appendChild(
        document.createTextNode("Excel row: " + lrpRowExcelOrDerived(r))
      );
      const t5 = document.createElement("p");
      t5.className = "subtle small";
      t5.appendChild(document.createTextNode("Calculation note: " + (r.derivation || "—")));
      [t0, t1, t2, t3, t4, t5].forEach((el) => lrpRowDetail.appendChild(el));
    }
    function renderLrp() {
      st.lrpSearch = lrpSearchIn.value;
      const yBase = lrpRows.length;
      table.dataset.finTotalRows = String(yBase);
      const filtered = lrpRowsMatchingFilter(lrpRows, st);
      tbody.innerHTML = "";
      if (filtered.length === 0) {
        const tr = document.createElement("tr");
        tr.className = "fin-table-empty-msg";
        tr.setAttribute("data-row-kind", "empty");
        tr.innerHTML =
          "<td colspan='3' class='subtle'>" +
          (lrpRows.length === 0 ? "No LRP workbench rows in extract." : "No rows match the current filters.") +
          "</td>";
        tbody.appendChild(tr);
      } else {
        filtered.forEach((r) => {
          const i = lrpRows.indexOf(r);
          const lkey = "lrp|" + i;
          const tr = document.createElement("tr");
          if (st.selectedLrpKey && st.selectedLrpKey === lkey) {
            tr.className = "wb-row--selected";
          }
          tr.style.cursor = "pointer";
          tr.addEventListener("click", (ev) => {
            ev.stopPropagation();
            st.selectedLrpKey = lkey;
            st.selectedCodeKey = null;
            st.selectedCoKey = null;
            if (ref._codesEls && ref._codesEls.rowDetail) {
              ref._codesEls.rowDetail.setAttribute("hidden", "hidden");
            }
            if (ref._coEls && ref._coEls.coRowDetail) {
              ref._coEls.coRowDetail.setAttribute("hidden", "hidden");
            }
            showLrpRowDetail(r);
            renderLrp();
          });
          tr.setAttribute("data-row-kind", "lrp-line");
          if (r.value != null && r.value !== "") {
            const tv = Number(r.value);
            if (!Number.isNaN(tv)) tr.setAttribute("data-total", String(tv));
          }
          const tdC = document.createElement("td");
          tdC.textContent = workbenchLrpRowCategory(r);
          const tdV = document.createElement("td");
          tdV.className = "wb-num";
          tdV.textContent = r.value != null && r.value !== "" ? fmtUsd(r.value) : "—";
          const tdN = document.createElement("td");
          tdN.className = "subtle small";
          tdN.appendChild(document.createTextNode(r.line || "—"));
          if (r.derivation && String(r.derivation).trim() && String(r.derivation) !== String(r.line)) {
            tdN.appendChild(document.createTextNode(" · "));
            const sp = document.createElement("span");
            sp.className = "subtle";
            sp.textContent = r.derivation;
            tdN.appendChild(sp);
          }
          tr.appendChild(tdC);
          tr.appendChild(tdV);
          tr.appendChild(tdN);
          tbody.appendChild(tr);
        });
      }
      if (typeof updateFinancialTableFooter === "function") {
        updateFinancialTableFooter(table, { totalRowCount: yBase });
      }
      updateFilterBanner();
    }
    lrpSearchIn.addEventListener("input", () => {
      renderLrp();
    });
    ref.lrpRender = renderLrp;
    ref._lrpEls = { lrpRowDetail, showLrpRowDetail, lrpSearchIn };
    let lbrDetails = null;
    if (lbrScan.length) {
      lbrDetails = document.createElement("details");
      lbrDetails.className = "workbench-lbr-details";
      const sum = document.createElement("summary");
      sum.className = "workbench-lbr-details-summary";
      sum.textContent = "Additional LBR scan data (" + lbrScan.length + " row" + (lbrScan.length === 1 ? "" : "s") + ", sample " + Math.min(30, lbrScan.length) + ")";
      const t2 = document.createElement("table");
      t2.className = "workbench-table data-table";
      const thead2 = document.createElement("thead");
      thead2.innerHTML = "<tr><th>Row</th><th>Label</th><th>Values</th></tr>";
      t2.appendChild(thead2);
      const b2 = document.createElement("tbody");
      lbrScan.slice(0, 30).forEach((r) => {
        const tr = document.createElement("tr");
        tr.innerHTML =
          "<td class='subtle'>" +
          (r.excel_row != null ? r.excel_row : "—") +
          "</td><td>" +
          (r.label || "—") +
          "</td><td class='wb-mono subtle small wb-num'>" +
          (Array.isArray(r.values) && r.values.length
            ? r.values.map((x) => fmtUsd(x)).join(", ")
            : "—") +
          "</td>";
        b2.appendChild(tr);
      });
      t2.appendChild(b2);
      lbrDetails.appendChild(sum);
      lbrDetails.appendChild(t2);
    }
    blockCtlLrp.appendChild(ph);
    blockCtlLrp.appendChild(lrpTools);
    blockTblLrp.appendChild(sumBarLrp);
    blockTblLrp.appendChild(tWrap);
    blockTblLrp.appendChild(lrpRowDetail);
    panel.appendChild(blockCtlLrp);
    panel.appendChild(blockTblLrp);
    if (lbrDetails) {
      const blockExtra = document.createElement("div");
      blockExtra.className = "workbench-block--secondary";
      blockExtra.appendChild(lbrDetails);
      panel.appendChild(blockExtra);
    }
    renderLrp();
  });

  addTab("rec", "Reconciliation", (panel) => {
    const blockCtlRec = document.createElement("div");
    blockCtlRec.className = "workbench-block--controls";
    const phRec = document.createElement("p");
    phRec.className = "subtle small workbench-hint";
    phRec.textContent =
      "Formula total projected profit, workbook-reported TPP (MoM), and variance (gap). Filter narrows rows; footer reflects visible lines only.";
    const recTools = document.createElement("div");
    recTools.className = "workbench-tools";
    const recSearchIn = document.createElement("input");
    recSearchIn.type = "search";
    recSearchIn.className = "workbench-search";
    recSearchIn.setAttribute("autocomplete", "off");
    recSearchIn.placeholder = "Filter by label or source";
    recTools.appendChild(recSearchIn);
    const blockTblRec = document.createElement("div");
    blockTblRec.className = "workbench-block--table workbench-block--table--rec";
    const sumBarRec = document.createElement("div");
    sumBarRec.className = "financial-table-summary-bar";
    sumBarRec.setAttribute("role", "status");
    const recWrap = document.createElement("div");
    recWrap.className = "workbench-table-wrap workbench-table-wrap--rec";
    const recTable = document.createElement("table");
    recTable.className = "workbench-table data-table fin-wb-table";
    recTable.setAttribute("data-fin-mode", "rec");
    const recThead = document.createElement("thead");
    recThead.innerHTML = "<tr><th>Line</th><th>Value</th><th>Source</th></tr>";
    const recTbody = document.createElement("tbody");
    const recTfoot = document.createElement("tfoot");
    recTfoot.className = "fin-wb-tfoot";
    const recFtr = document.createElement("tr");
    recFtr.innerHTML =
      "<td class='fin-foot-lead subtle'></td>" +
      "<td class='wb-num fin-foot-cur' colspan='2'></td>";
    recTfoot.appendChild(recFtr);
    recTable.appendChild(recThead);
    recTable.appendChild(recTbody);
    recTable.appendChild(recTfoot);
    recWrap.appendChild(recTable);
    function renderRec() {
      st.recSearch = recSearchIn.value;
      const lines = (rec && rec.lines) || [];
      const yBase = lines.length;
      recTable.dataset.finTotalRows = String(yBase);
      const filtered = recLinesMatchingFilter(lines, st);
      recTbody.innerHTML = "";
      if (filtered.length === 0) {
        const trM = document.createElement("tr");
        trM.className = "fin-table-empty-msg";
        trM.setAttribute("data-row-kind", "empty");
        trM.innerHTML =
          "<td colspan='3' class='subtle'>" +
          (lines.length === 0
            ? "No reconciliation lines in workbench extract."
            : "No rows match the current filters.") +
          "</td>";
        recTbody.appendChild(trM);
      } else {
        filtered.forEach((ln) => {
          const tr = document.createElement("tr");
          tr.setAttribute("data-row-kind", workbenchRecRowKind(ln.label));
          const v =
            ln.value != null && ln.value !== "" && !Number.isNaN(Number(ln.value)) ? Number(ln.value) : null;
          if (v != null) tr.setAttribute("data-total", String(v));
          const td0 = document.createElement("td");
          td0.textContent = ln.label || "—";
          const td1 = document.createElement("td");
          td1.className = "wb-num";
          td1.textContent = ln.value != null && ln.value !== "" ? fmtUsd(ln.value) : "—";
          const td2 = document.createElement("td");
          td2.className = "subtle small";
          td2.textContent = ln.source || "—";
          tr.appendChild(td0);
          tr.appendChild(td1);
          tr.appendChild(td2);
          recTbody.appendChild(tr);
        });
      }
      if (typeof updateFinancialTableFooter === "function") {
        updateFinancialTableFooter(recTable, { totalRowCount: yBase });
      }
      updateFilterBanner();
    }
    recSearchIn.addEventListener("input", () => {
      renderRec();
    });
    ref.recRender = renderRec;
    ref._recEls = { recSearchIn, renderRec };
    blockCtlRec.appendChild(phRec);
    blockCtlRec.appendChild(recTools);
    blockTblRec.appendChild(sumBarRec);
    blockTblRec.appendChild(recWrap);
    panel.appendChild(blockCtlRec);
    panel.appendChild(blockTblRec);
    const u = document.createElement("h4");
    u.className = "workbench-subh";
    u.textContent = "Deterministic notes";
    panel.appendChild(u);
    (rec.deterministic_explanations || []).forEach((t) => {
      const p = document.createElement("p");
      p.className = "subtle small";
      p.textContent = t;
      panel.appendChild(p);
    });
    renderRec();
  });

  function setActivePanel(id) {
    st.activePanel = id;
    panes.forEach((x) => {
      x.b.setAttribute("aria-selected", x.id === id ? "true" : "false");
      x.panel.hidden = x.id !== id;
    });
  }

  function updateFilterBanner() {
    const isFiltered = !!(
      st.componentLink ||
      (st.codePrefix && st.codePrefix !== "all") ||
      (st.codeNamespace && st.codeNamespace !== "all") ||
      (st.codeSearch && st.codeSearch.trim()) ||
      !st.codeNonZero ||
      st.coFilter !== "all" ||
      (st.coSearch && st.coSearch.trim()) ||
      (st.lrpSearch && st.lrpSearch.trim()) ||
      (st.recSearch && st.recSearch.trim())
    );
    const showBanner = isFiltered;
    if (!showBanner) {
      banner.hidden = true;
      clearF.hidden = true;
      return;
    }
    banner.removeAttribute("hidden");
    const parts = [];
    const primaryHeading = workbenchComponentFilterHeading(st);
    if (primaryHeading) {
      parts.push(primaryHeading);
    }
    if (st.activePanel === "codes") {
      const n = filterJtdRowsForState(jtdRows, st).length;
      if (st.codePrefix && st.codePrefix !== "all") {
        parts.push("Showing " + n + " cost code row" + (n === 1 ? "" : "s") + " (prefix " + st.codePrefix + " / N" + st.codePrefix + ")");
      } else {
        parts.push("Showing " + n + " cost code row" + (n === 1 ? "" : "s"));
      }
    } else if (st.activePanel === "co") {
      const n = coRowsMatchingFilter(coRows, st).length;
      parts.push("Showing " + n + " change order row" + (n === 1 ? "" : "s") + (st.coFilter !== "all" ? " (" + st.coFilter + " only)" : ""));
    } else if (st.activePanel === "lrp") {
      const nVis = lrpRowsMatchingFilter(lrpRows, st).length;
      parts.push(
        "Showing " +
          nVis +
          " of " +
          lrpRows.length +
          " LRP line" +
          (lrpRows.length === 1 ? "" : "s") +
          (lbrScan.length ? " · full LBR scan in “Additional LBR scan data” below" : "")
      );
    } else {
      const rl = (rec.lines || []).length;
      const nVis = recLinesMatchingFilter(rec.lines || [], st).length;
      parts.push("Showing " + nVis + " of " + rl + " reconciliation line" + (rl === 1 ? "" : "s"));
    }
    bannerText.textContent = parts.join(" · ");
    const needClear = isFiltered;
    clearF.hidden = !needClear;
  }

  function syncUIFromState() {
    const cels = ref._codesEls;
    if (cels) {
      cels.search.value = st.codeSearch;
      cels.pref.value = st.codePrefix;
      if (cels.nsSel) cels.nsSel.value = st.codeNamespace || "all";
      cels.nzIn.checked = st.codeNonZero;
      cels.sortSel.value = st.codeSort;
      cels.applyCodes();
    }
    if (ref.coRender) {
      const fbar = root.querySelector(".workbench-cofilter");
      if (fbar) {
        fbar.querySelectorAll(".wb-filter-btn").forEach((b) => {
          b.classList.toggle("is-active", b.getAttribute("data-cof") === st.coFilter);
        });
      }
      if (ref._coEls && ref._coEls.coSearchIn) {
        ref._coEls.coSearchIn.value = st.coSearch;
      }
      ref.coRender();
    }
    if (ref.lrpRender) {
      if (ref._lrpEls && ref._lrpEls.lrpSearchIn) {
        ref._lrpEls.lrpSearchIn.value = st.lrpSearch;
      }
      ref.lrpRender();
    }
    if (ref.recRender) {
      if (ref._recEls && ref._recEls.recSearchIn) {
        ref._recEls.recSearchIn.value = st.recSearch;
      }
      ref.recRender();
    }
    setActivePanel(st.activePanel);
    updateFilterBanner();
    if (typeof updateAllFinancialTableFooters === "function") {
      updateAllFinancialTableFooters();
    }
  }

  function applyProfitWorkbenchLink(id) {
    st.selectedCodeKey = null;
    st.selectedCoKey = null;
    st.selectedLrpKey = null;
    const cels = ref._codesEls;
    if (id === "cm_fee") {
      st.activePanel = "codes";
      st.codePrefix = "all";
      st.coFilter = "all";
      st.bannerText = "CM fee (component_role = cm_fee)";
      st.componentLink = "cm_fee";
    } else if (id === "pco_profit") {
      st.activePanel = "codes";
      st.codePrefix = "all";
      st.coFilter = "all";
      st.bannerText = "PCO profit (component_role = pco_profit)";
      st.componentLink = "pco_profit";
    } else if (id === "prior_system_profit") {
      st.activePanel = "codes";
      st.codePrefix = "all";
      st.coFilter = "all";
      st.bannerText = "Prior-system profit (component_role = prior_system_profit)";
      st.componentLink = "prior_system_profit";
    } else if (id === "change_orders") {
      st.activePanel = "co";
      st.coFilter = "all";
      st.bannerText = "Change orders (all JTD change-order lines)";
      st.componentLink = "change_orders";
    } else if (id === "labor_rate_profit_to_date") {
      st.activePanel = "lrp";
      st.bannerText = "Labor rate profit to date (LRP breakdown)";
      st.componentLink = "labor_rate_profit_to_date";
    } else if (id === "variance") {
      st.activePanel = "rec";
      st.bannerText = "Variance (formula vs workbook, reconciliation detail)";
      st.componentLink = "variance";
    } else if (id === "workbook_reported_tpp") {
      st.activePanel = "rec";
      st.bannerText = "Workbook-reported TPP (reconciliation)";
      st.componentLink = "workbook_reported_tpp";
    } else {
      st.activePanel = "codes";
      st.codePrefix = "all";
      st.coFilter = "all";
      st.bannerText = null;
      st.componentLink = null;
      if (id === "buyout_savings_realized") st.bannerText = "Buyout savings realized";
      if (id === "budget_savings_overages") st.bannerText = "Budget savings / overages";
      if (st.bannerText) st.componentLink = id;
    }
    syncUIFromState();
    if (cels && cels.rowDetail) cels.rowDetail.setAttribute("hidden", "hidden");
    if (ref._coEls && ref._coEls.coRowDetail) {
      ref._coEls.coRowDetail.setAttribute("hidden", "hidden");
      ref._coEls.coRowDetail.innerHTML = "";
    }
    if (ref._lrpEls && ref._lrpEls.lrpRowDetail) {
      ref._lrpEls.lrpRowDetail.setAttribute("hidden", "hidden");
      ref._lrpEls.lrpRowDetail.innerHTML = "";
    }
  }

  function clearWbFilter() {
    st.codePrefix = "all";
    st.codeNamespace = "all";
    st.codeSearch = "";
    st.codeNonZero = true;
    st.coFilter = "all";
    st.coSearch = "";
    st.lrpSearch = "";
    st.recSearch = "";
    st.codeSort = "ucb";
    st.bannerText = null;
    st.componentLink = null;
    st.selectedCodeKey = null;
    st.selectedCoKey = null;
    st.selectedLrpKey = null;
    st.activePanel = "codes";
    syncUIFromState();
    const cels = ref._codesEls;
    if (cels && cels.rowDetail) {
      cels.rowDetail.setAttribute("hidden", "hidden");
      cels.rowDetail.innerHTML = "";
    }
    if (ref._coEls && ref._coEls.coRowDetail) {
      ref._coEls.coRowDetail.setAttribute("hidden", "hidden");
      ref._coEls.coRowDetail.innerHTML = "";
    }
    if (ref._lrpEls && ref._lrpEls.lrpRowDetail) {
      ref._lrpEls.lrpRowDetail.setAttribute("hidden", "hidden");
      ref._lrpEls.lrpRowDetail.innerHTML = "";
    }
  }

  workbenchViewApi = {
    root: root,
    applyComponentLink: function (id) {
      applyProfitWorkbenchLink(id);
      root.scrollIntoView({ block: "start", behavior: "smooth" });
    },
    clearFilter: function () {
      clearWbFilter();
      root.scrollIntoView({ block: "start", behavior: "smooth" });
    },
  };

  clearF.addEventListener("click", function () {
    if (workbenchViewApi) workbenchViewApi.clearFilter();
  });

  panes.forEach((p) => {
    p.b.addEventListener("click", () => {
      setActivePanel(p.id);
      if (p.id !== "codes" && ref._codesEls && ref._codesEls.rowDetail) {
        ref._codesEls.rowDetail.setAttribute("hidden", "hidden");
      }
      if (p.id !== "co" && ref._coEls && ref._coEls.coRowDetail) {
        ref._coEls.coRowDetail.setAttribute("hidden", "hidden");
      }
      if (p.id !== "lrp" && ref._lrpEls && ref._lrpEls.lrpRowDetail) {
        ref._lrpEls.lrpRowDetail.setAttribute("hidden", "hidden");
      }
      updateFilterBanner();
      if (typeof updateAllFinancialTableFooters === "function") {
        updateAllFinancialTableFooters();
      }
    });
  });

  root.appendChild(h);
  root.appendChild(banner);
  root.appendChild(tabBar);
  root.appendChild(panelBox);
  banner.hidden = true;
  clearF.hidden = true;
  syncUIFromState();
  return root;
}

window.__OWB_SCRIPT_LOAD = Object.assign({}, window.__OWB_SCRIPT_LOAD || {}, { owb2ReportWorkbench: true });
