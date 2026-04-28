/**
 * owb-1-entries.js — Operator Workbench UI (pass 3)
 * Load order: 1 of 4 — must run before owb-2..4 (classic scripts share global scope).
 * Owns: DRIVER_*, session state vars, operator task card rendering, pair disambiguation.
 * Shared config: window.__OWB__ (set in index.html before scripts).
 */
(function () {
  const c = window.__OWB__ || {};
  window.DRIVER_PRIMARY_TOP_N = c.DRIVER_PRIMARY_TOP_N != null ? Number(c.DRIVER_PRIMARY_TOP_N) : 5;
  window.DRIVER_IMPACT_THRESHOLD = c.DRIVER_IMPACT_THRESHOLD != null ? Number(c.DRIVER_IMPACT_THRESHOLD) : 10000;
})();
var DRIVER_PRIMARY_TOP_N = window.DRIVER_PRIMARY_TOP_N;
var DRIVER_IMPACT_THRESHOLD = window.DRIVER_IMPACT_THRESHOLD;
var lastRunPayload = null;
var operatorWorkspaceRoot = "";
var pendingConfirmTask = null;
var operatorSelectedPairId = "";
var lastConfirmedPair = {};
var preferredReportFamily = "";
var lastProjectLibraryPayload = null;
var reportBuilderProjectId = "";
var reportBuilderRows = [];
var reportPathSelection = new Set();
var workbenchViewApi = null;
function operatorRunId() {
  return lastRunPayload && lastRunPayload.run_id ? String(lastRunPayload.run_id) : "";
}

const OPERATOR_CONTRACT_LABEL = {
  find_latest_prior_reports: "Find latest and prior reports",
  compare_latest_report: "Compare latest report",
  compare_latest_prior_reports: "Compare latest vs prior",
  compare_and_show_labor_deltas: "Compare with labor deltas",
  run_weekly_review: "Weekly review",
  summarize_for_owner: "Owner summary",
  export_top_changes: "Export top changes",
  assess_cost_vs_revenue: "Cost vs revenue",
  list_current_run_artifacts: "List run artifacts",
  inspect_workbook: "Inspect workbook",
  preview_report_sheet: "Preview report sheet",
  find_report_sheets: "Find report sheets",
  scan_workspace: "Scan workspace (index)",
  list_projects: "List projects",
  show_project_reports: "Show project reports",
  trend_project_reports: "Project trend",
  compare_multi_reports: "Multi-period compare",
  generate_financial_signals: "Run financial analysis",
};

function humanTaskStatus(status) {
  if (status === "needs_confirmation") return "Waiting for your confirmation";
  if (status === "completed") return "Complete";
  if (status === "needs_setup") return "Setup required";
  if (status === "needs_run") return "Run a compare first";
  if (status === "no_candidates") return "No suitable inputs";
  if (status === "insufficient_data") return "Insufficient data";
  if (status === "failed" || status === "error") return "Did not complete";
  return status || "—";
}

function renderPairDisambiguation(approval) {
  const meta = document.getElementById("pair-disambiguation-meta");
  const host = document.getElementById("pair-disambiguation-options");
  if (!meta || !host) return;
  const pairing = (approval && approval.pairing) || {};
  const options = Array.isArray(pairing.candidate_pairs) ? pairing.candidate_pairs : [];
  host.innerHTML = "";
  if (!options.length) {
    meta.textContent = "";
    operatorSelectedPairId = "";
    return;
  }
  const conf = pairing.pairing_confidence !== undefined ? Number(pairing.pairing_confidence).toFixed(2) : "—";
  const req = pairing.requires_operator_selection
    ? "Choose one pair below, then confirm."
    : "Optional: pick a different pair, or use the preselected one.";
  meta.textContent = `How confident the automatic pairing is: ${conf} · ${req}`;
  options.forEach((pair, idx) => {
    const row = document.createElement("label");
    row.className = "pair-option-row";
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "pair-option";
    radio.value = String(pair.pair_id || "");
    const shouldCheck = operatorSelectedPairId
      ? operatorSelectedPairId === String(pair.pair_id || "")
      : idx === 0;
    radio.checked = shouldCheck;
    if (shouldCheck) operatorSelectedPairId = String(pair.pair_id || "");
    radio.addEventListener("change", () => {
      operatorSelectedPairId = String(pair.pair_id || "");
    });
    const current = pair.current || {};
    const prior = pair.prior || {};
    const col = document.createElement("span");
    col.className = "pair-option-copy";
    const line1 = document.createElement("span");
    line1.className = "pair-option-title";
    line1.textContent = `After: ${current.name || current.path || "unknown"} · Before: ${prior.name || prior.path || "unknown"}`;
    const line2 = document.createElement("span");
    line2.className = "pair-option-subtle";
    const bits = [pair.selection_reason, (pair.ranking_factors || []).slice(0, 2).join(" · ")].filter(Boolean);
    line2.textContent = bits.length ? bits.join(" — ") : "";
    col.appendChild(line1);
    if (line2.textContent) col.appendChild(line2);
    row.appendChild(radio);
    row.appendChild(col);
    host.appendChild(row);
  });
}

function renderOperatorTaskEntry(payload) {
  const host = document.getElementById("operator-task-transcript");
  if (!host) return;
  const card = document.createElement("article");
  const st = payload.status || "";
  card.className = "operator-task-entry";
  if (st === "completed") card.classList.add("ote-state-complete");
  else if (st === "needs_confirmation") card.classList.add("ote-state-pending");
  else if (st === "needs_setup" || st === "needs_run") card.classList.add("ote-state-warn");
  else if (st === "no_candidates" || st === "insufficient_data") card.classList.add("ote-state-warn");
  else if (st === "failed" || st === "error") card.classList.add("ote-state-error");

  const contract = payload.task && payload.task.contract ? String(payload.task.contract) : "";
  const contractLabel = contract
    ? (OPERATOR_CONTRACT_LABEL[contract] || contract.replace(/_/g, " "))
    : "This result";

  const addSection = (kicker, bodyEl) => {
    const k = document.createElement("p");
    k.className = "ote-kicker";
    k.textContent = kicker;
    card.appendChild(k);
    if (bodyEl) card.appendChild(bodyEl);
  };

  const q = (payload.task && payload.task.query) || "(unknown)";
  const result = payload.result || {};
  if (contract === "compare_multi_reports") {
    const multi = (result.found && typeof result.found === "object") ? result.found : result;
    const summaryCard = result.summary_card || {};
    const delta = (multi.multi_period_delta && typeof multi.multi_period_delta === "object") ? multi.multi_period_delta : {};
    const actionView = (delta.action_view && typeof delta.action_view === "object") ? delta.action_view : {};
    const costDrilldown = (delta.cost_type_drilldown && typeof delta.cost_type_drilldown === "object") ? delta.cost_type_drilldown : {};
    const pairResults = Array.isArray(delta.pair_results) ? delta.pair_results : [];
    const repeatedMovers = Array.isArray(delta.repeated_movers) ? delta.repeated_movers : [];
    const largestCumulative = Array.isArray(delta.largest_cumulative_movers) ? delta.largest_cumulative_movers : [];
    const latestMovers = Array.isArray(delta.latest_period_movers) ? delta.latest_period_movers : [];
    const comparisonPairs = Array.isArray(multi.comparison_pairs) ? multi.comparison_pairs : [];
    const reportsUsed = Array.isArray(multi.reports_used) ? multi.reports_used : [];
    const pathRows = Array.isArray(summaryCard.paths) ? summaryCard.paths : [];

    const renderPlainPathItem = (path) => {
      const li = document.createElement("li");
      const code = document.createElement("code");
      code.className = "ote-path";
      code.textContent = String(path || "—");
      li.appendChild(code);
      return li;
    };
    const renderListSection = (parent, titleText, rows, amountKey) => {
      if (!Array.isArray(rows) || !rows.length) return;
      const title = document.createElement("p");
      title.className = "assistant-response-label";
      title.textContent = titleText;
      parent.appendChild(title);
      const ul = document.createElement("ul");
      ul.className = "assistant-response-list";
      rows.slice(0, 5).forEach((row) => {
        const li = document.createElement("li");
        const amount = row[amountKey] != null ? ` · ${fmtMoneySigned(row[amountKey])}` : "";
        const pairs = Array.isArray(row.pair_sequences) && row.pair_sequences.length ? ` · pairs ${row.pair_sequences.join(", ")}` : "";
        li.textContent = `${row.label || row.key || "Line item"} · ${row.movement_category || "uncategorized"}${amount}${pairs}`;
        ul.appendChild(li);
      });
      parent.appendChild(ul);
    };

    const brief = document.createElement("section");
    brief.className = "command-brief";
    const briefLabel = document.createElement("p");
    briefLabel.className = "assistant-response-label";
    briefLabel.textContent = "Analysis summary";
    brief.appendChild(briefLabel);
    const briefTitle = document.createElement("h3");
    briefTitle.textContent = "What matters right now";
    brief.appendChild(briefTitle);
    const topIssuesForBrief = Array.isArray(actionView.top_issues) ? actionView.top_issues : [];
    const ongoingForBrief = Array.isArray(actionView.ongoing_risks) ? actionView.ongoing_risks : [];
    const topIssue = topIssuesForBrief[0] || {};
    const topIssueLine = topIssue.label
      ? `${topIssue.label}${topIssue.amount != null ? " · " + fmtMoneySigned(topIssue.amount) : ""}`
      : "No top issue identified from this window.";
    const briefRows = [
      ["Finish", payload.answer || summaryCard.summary || "Multi-period comparison ready."],
      ["Driver", topIssueLine],
      ["Risks", ongoingForBrief.length ? `${ongoingForBrief.length} recurring item(s) need review.` : "No recurring risk item surfaced in the selected window."],
      ["Need", "Use cost breakdown to assign labor, material, subcontract, and uncategorized follow-up."],
      ["Doing", "Review Action View first; expand Detailed Evidence only when you need traceability."],
    ];
    const briefGrid = document.createElement("dl");
    briefGrid.className = "command-brief-grid";
    briefRows.forEach(([label, value]) => {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = value;
      briefGrid.appendChild(dt);
      briefGrid.appendChild(dd);
    });
    brief.appendChild(briefGrid);
    const briefMeta = document.createElement("p");
    briefMeta.className = "ote-meta";
    briefMeta.textContent = [
      `Project ${multi.project_filter || result.project_filter || "—"}`,
      `${multi.report_count != null ? multi.report_count : result.report_count || 0} reports`,
      `${multi.pair_count != null ? multi.pair_count : result.pair_count || 0} adjacent pairs`,
      `${multi.period_start || "—"} to ${multi.period_end || "—"}`,
    ].join(" · ");
    brief.appendChild(briefMeta);
    card.appendChild(brief);

    const actionBlock = document.createElement("section");
    actionBlock.className = "decision-section";
    const actionTitle = document.createElement("p");
    actionTitle.className = "assistant-response-label";
    actionTitle.textContent = "Action View";
    actionBlock.appendChild(actionTitle);
    const actionGrid = document.createElement("div");
    actionGrid.className = "action-card-grid";
    const renderActionCard = (label, rows) => {
      const cardEl = document.createElement("section");
      cardEl.className = "action-card";
      const h = document.createElement("h4");
      h.textContent = label;
      cardEl.appendChild(h);
      const ul = document.createElement("ul");
      ul.className = "assistant-response-list";
      (Array.isArray(rows) ? rows : []).slice(0, 5).forEach((row) => {
        const li = document.createElement("li");
        const amount = row.amount != null ? ` · ${fmtMoneySigned(row.amount)}` : "";
        const pairs = Array.isArray(row.pair_sequences) && row.pair_sequences.length ? ` · pairs ${row.pair_sequences.join(", ")}` : "";
        li.textContent = `${row.label || row.key || "Line item"} · ${row.movement_category || "uncategorized"}${amount}${pairs}`;
        ul.appendChild(li);
      });
      if (!ul.childElementCount) {
        const li = document.createElement("li");
        li.className = "empty-card-line";
        li.textContent = "No item in this bucket.";
        ul.appendChild(li);
      }
      cardEl.appendChild(ul);
      actionGrid.appendChild(cardEl);
    };
    renderActionCard("Top Issues", actionView.top_issues);
    renderActionCard("New This Period", actionView.new_this_period);
    renderActionCard("Ongoing Risks", actionView.ongoing_risks);
    renderActionCard("Watchlist", actionView.watchlist);
    actionBlock.appendChild(actionGrid);
    card.appendChild(actionBlock);

    const costBlock = document.createElement("section");
    costBlock.className = "decision-section secondary-decision";
    const costTitle = document.createElement("p");
    costTitle.className = "assistant-response-label";
    costTitle.textContent = "Cost Breakdown";
    costBlock.appendChild(costTitle);
    const costGrid = document.createElement("div");
    costGrid.className = "cost-card-grid";
    [
      ["labor", "Labor"],
      ["material", "Material"],
      ["subcontract", "Subcontract"],
      ["uncategorized", "Uncategorized"],
    ].forEach(([key, label]) => {
      const bucket = costDrilldown[key] || {};
      const count = Number(bucket.count || 0);
      if (!count) return;
      const bucketCard = document.createElement("section");
      bucketCard.className = "cost-card";
      const conf = bucket.confidence_breakdown || {};
      const heading = document.createElement("h4");
      const coverage = Array.isArray(bucket.pair_coverage) && bucket.pair_coverage.length ? ` · pairs ${bucket.pair_coverage.join(", ")}` : "";
      heading.textContent = `${label}: ${count} item(s), ${fmtMoneySigned(bucket.total_abs_movement || 0)} total · ${Number(conf.structured_count || 0)} structured / ${Number(conf.keyword_count || 0)} keyword / ${Number(conf.uncategorized_count || 0)} uncategorized${coverage}`;
      bucketCard.appendChild(heading);
      const ul = document.createElement("ul");
      ul.className = "assistant-response-list";
      (bucket.items || []).slice(0, 3).forEach((item) => {
        const li = document.createElement("li");
        const pairs = Array.isArray(item.pair_sequences) && item.pair_sequences.length ? ` · pairs ${item.pair_sequences.join(", ")}` : "";
        li.textContent = `${item.label || item.key || "Line item"} · ${fmtMoneySigned(item.cumulative_delta || 0)}${pairs}`;
        ul.appendChild(li);
      });
      bucketCard.appendChild(ul);
      costGrid.appendChild(bucketCard);
    });
    costBlock.appendChild(costGrid);
    card.appendChild(costBlock);

    const evidence = document.createElement("details");
    evidence.className = "operator-evidence";
    const summary = document.createElement("summary");
    summary.textContent = "Detailed Evidence";
    evidence.appendChild(summary);
    const inner = document.createElement("div");
    inner.className = "details-inner";
    const evIntro = document.createElement("p");
    evIntro.className = "ote-sub";
    evIntro.textContent = `${contractLabel} · ${humanTaskStatus(st)} · ${q}`;
    inner.appendChild(evIntro);
    if (result.source_line) {
      const src = document.createElement("p");
      src.className = "ote-sub";
      src.textContent = String(result.source_line);
      inner.appendChild(src);
    }
    const addEvidenceList = (titleText, rows, formatter) => {
      if (!rows.length) return;
      const title = document.createElement("p");
      title.className = "assistant-response-label";
      title.textContent = titleText;
      inner.appendChild(title);
      const ul = document.createElement("ul");
      ul.className = "assistant-response-list";
      rows.slice(0, 12).forEach((row) => ul.appendChild(formatter(row)));
      inner.appendChild(ul);
    };
    addEvidenceList("Reports Used", reportsUsed, (row) => renderPlainPathItem(row.path || row.name || ""));
    addEvidenceList("Comparison Pairs", comparisonPairs, (pair) => {
      const li = document.createElement("li");
      li.textContent = `Pair ${pair.pair_sequence || "—"}: ${(pair.from_report && pair.from_report.name) || "—"} → ${(pair.to_report && pair.to_report.name) || "—"}`;
      return li;
    });
    addEvidenceList("Pair Results", pairResults, (pair) => {
      const li = document.createElement("li");
      li.textContent = `Pair ${pair.pair_sequence || "—"}: ${pair.status || "unknown"} · top changes ${Array.isArray(pair.top_changes) ? pair.top_changes.length : 0}`;
      return li;
    });
    addEvidenceList("Repeated Movers", repeatedMovers, (row) => {
      const li = document.createElement("li");
      li.textContent = `${row.label || row.key || "Line item"} (${fmtMoneySigned(row.cumulative_delta || 0)}) · pairs ${(row.pair_sequences || []).join(", ")}`;
      return li;
    });
    addEvidenceList("Largest Cumulative Movers", largestCumulative, (row) => {
      const li = document.createElement("li");
      li.textContent = `${row.label || row.key || "Line item"} (${fmtMoneySigned(row.cumulative_delta || 0)})`;
      return li;
    });
    addEvidenceList("Latest-Period Movers", latestMovers, (row) => {
      const li = document.createElement("li");
      li.textContent = `${row.label || row.key || "Line item"} (${fmtMoneySigned(row.delta || 0)})`;
      return li;
    });
    addEvidenceList("Open Files", pathRows, (path) => renderPlainPathItem(path));
    evidence.appendChild(inner);
    card.appendChild(evidence);
    host.prepend(card);
    return;
  }
  const asked = document.createElement("p");
  asked.className = "ote-body";
  asked.textContent = q;
  addSection("You asked", asked);

  const runLine = document.createElement("p");
  runLine.className = "ote-meta";
  runLine.textContent = `${contractLabel} · ${humanTaskStatus(st)}`;
  addSection("What ran", runLine);

  const answer = document.createElement("p");
  answer.className = "operator-task-answer ote-answer";
  answer.textContent = payload.answer || "—";
  addSection("What happened", answer);

  if (result.source_line) {
    const prov = document.createElement("p");
    prov.className = "ote-sub";
    prov.textContent = String(result.source_line);
    addSection("Provenance", prov);
  }
  if (
    (contract === "summarize_for_owner" || contract === "run_weekly_review") &&
    st === "completed" &&
    result.found &&
    result.found.owner_summary &&
    result.found.owner_summary.owner_summary_text
  ) {
    const kOwner = document.createElement("p");
    kOwner.className = "ote-kicker";
    kOwner.textContent =
      contract === "run_weekly_review" ? "Copy-ready owner summary (weekly pack)" : "Copy-ready owner summary";
    card.appendChild(kOwner);
    const pre = document.createElement("pre");
    pre.className = "json-pane";
    pre.style.whiteSpace = "pre-wrap";
    pre.setAttribute("aria-label", "Owner summary text");
    pre.textContent = result.found.owner_summary.owner_summary_text;
    card.appendChild(pre);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-ghost";
    btn.textContent = "Copy summary";
    const txt = result.found.owner_summary.owner_summary_text;
    btn.addEventListener("click", () => {
      const reset = () => {
        setTimeout(() => {
          btn.textContent = "Copy summary";
        }, 1600);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard
          .writeText(txt)
          .then(() => {
            btn.textContent = "Copied";
            reset();
          })
          .catch(() => {
            pre.focus();
            const range = document.createRange();
            range.selectNodeContents(pre);
            const sel = window.getSelection();
            if (sel) {
              sel.removeAllRanges();
              sel.addRange(range);
            }
          });
      } else {
        pre.focus();
        const range = document.createRange();
        range.selectNodeContents(pre);
        const sel = window.getSelection();
        if (sel) {
          sel.removeAllRanges();
          sel.addRange(range);
        }
      }
    });
    card.appendChild(btn);
    const ownNote = document.createElement("p");
    ownNote.className = "ote-sub";
    ownNote.textContent = "Grounded in Top drivers by impact.";
    card.appendChild(ownNote);
  }
  const rs = result.readiness;
  if (rs && typeof rs === "object" && (st === "needs_setup" || st === "needs_run" || st === "no_candidates" || st === "failed")) {
    const bits = [];
    if (rs.exists === false) bits.push("Folder missing");
    else if (rs.exists === true) bits.push("Folder exists");
    if (rs.allowed === false) bits.push("Not an allowed path");
    if (typeof rs.workbook_count === "number") bits.push(`${rs.workbook_count} workbook(s) found`);
    if (rs.has_completed_run === false) bits.push("No completed compare on disk");
    if (rs.suggested_query) bits.push(`Try: ${rs.suggested_query}`);
    if (bits.length) {
      const p = document.createElement("p");
      p.className = "ote-sub";
      p.textContent = bits.join(" · ");
      addSection("Situation", p);
    }
  }
  const summaryCard = result.summary_card || {};
  if (summaryCard && summaryCard.summary) {
    const block = document.createElement("div");
    block.className = "operator-summary-card";
    const title = document.createElement("p");
    title.className = "assistant-response-label";
    title.textContent = summaryCard.title || "At a glance";
    block.appendChild(title);
    const text = document.createElement("p");
    text.className = "ote-body";
    text.textContent = summaryCard.summary;
    block.appendChild(text);
    const ko = Array.isArray(summaryCard.key_outputs) ? summaryCard.key_outputs : [];
    if (ko.length) {
      const ul = document.createElement("ul");
      ul.className = "assistant-response-list ote-keyout";
      ko.slice(0, 8).forEach((line) => {
        const li = document.createElement("li");
        li.textContent = String(line);
        ul.appendChild(li);
      });
      block.appendChild(ul);
    }
    addSection("What we found", block);
  }

  if (payload.status === "needs_confirmation" && payload.approval) {
    const approval = payload.approval;
    const wrap = document.createElement("div");
    wrap.className = "ote-compare-plan";
    const priorP = (approval.files && approval.files.prior) || "—";
    const curP = (approval.files && approval.files.current) || "—";
    const p1 = document.createElement("p");
    p1.className = "ote-body";
    p1.appendChild(document.createTextNode("Before (prior): "));
    const a1 = document.createElement("code");
    a1.className = "ote-path";
    a1.textContent = priorP;
    p1.appendChild(a1);
    wrap.appendChild(p1);
    const p2 = document.createElement("p");
    p2.className = "ote-body";
    p2.appendChild(document.createTextNode("After (current): "));
    const a2 = document.createElement("code");
    a2.className = "ote-path";
    a2.textContent = curP;
    p2.appendChild(a2);
    wrap.appendChild(p2);
    const cm = approval.compare_mode || {};
    const p3 = document.createElement("p");
    p3.className = "ote-sub";
    p3.textContent = `Compare mode: ${cm.selected_mode || "—"} · ${cm.compare_path || ""}${cm.selection_reason ? " — " + cm.selection_reason : ""}`;
    wrap.appendChild(p3);
    const ul = document.createElement("ul");
    ul.className = "assistant-response-list ote-muted-list";
    (approval.expected_outputs || []).slice(0, 8).forEach((path) => {
      const li = document.createElement("li");
      li.textContent = `Expected output: ${path}`;
      ul.appendChild(li);
    });
    if (ul.childElementCount) wrap.appendChild(ul);
    addSection("Staged compare", wrap);
  }

  const found = result.found || {};
  if (found.selected_pair && Array.isArray(found.selected_pair.ranking_factors) && found.selected_pair.ranking_factors.length) {
    const title = document.createElement("p");
    title.className = "assistant-response-label";
    title.textContent = "Why this pair";
    card.appendChild(title);
    const ul = document.createElement("ul");
    ul.className = "assistant-response-list";
    found.selected_pair.ranking_factors.slice(0, 6).forEach((factor) => {
      const li = document.createElement("li");
      li.textContent = String(factor);
      ul.appendChild(li);
    });
    card.appendChild(ul);
  }
  if (Array.isArray(found.sheets) && found.sheets.length) {
    const title = document.createElement("p");
    title.className = "assistant-response-label";
    title.textContent = "Workbook sheets";
    card.appendChild(title);
    const ul = document.createElement("ul");
    ul.className = "assistant-response-list";
    found.sheets.slice(0, 10).forEach((sheet) => {
      const li = document.createElement("li");
      li.textContent = `${sheet.name} (rows ${sheet.max_row}, cols ${sheet.max_column})`;
      ul.appendChild(li);
    });
    card.appendChild(ul);
  }

  if (Array.isArray(found.report_sheets) && found.report_sheets.length) {
    const title = document.createElement("p");
    title.className = "assistant-response-label";
    title.textContent = "Likely report sheets";
    card.appendChild(title);
    const ul = document.createElement("ul");
    ul.className = "assistant-response-list";
    found.report_sheets.slice(0, 8).forEach((sheet) => {
      const li = document.createElement("li");
      li.textContent = `${sheet.sheet_name} (score ${sheet.score})`;
      ul.appendChild(li);
    });
    card.appendChild(ul);
  }

  if (Array.isArray(found.preview_rows) && found.preview_rows.length) {
    const preTitle = document.createElement("p");
    preTitle.className = "assistant-response-label";
    preTitle.textContent = `Workbook preview: ${found.sheet_name || "sheet"}`;
    card.appendChild(preTitle);
    const pre = document.createElement("pre");
    pre.className = "json-pane";
    pre.textContent = JSON.stringify(found.preview_rows.slice(0, 10), null, 2);
    card.appendChild(pre);
  }

  const renderPathItem = (path) => {
    const li = document.createElement("li");
    const textPath = String(path || "").trim();
    if (!textPath) return li;
    if (operatorRunId() && (textPath.startsWith("inputs/") || textPath.startsWith("outputs/"))) {
      const link = document.createElement("a");
      link.href = `/runs/${operatorRunId()}/artifacts/${textPath}`;
      link.target = "_blank";
      link.textContent = textPath;
      li.appendChild(link);
      return li;
    }
    const link = document.createElement("a");
    const lowerPath = textPath.toLowerCase();
    if (lowerPath.endsWith(".xlsx") || lowerPath.endsWith(".xlsm") || lowerPath.endsWith(".xltx") || lowerPath.endsWith(".xltm")) {
      link.href = `/api/local/workbook/inspect?workspace_root=${encodeURIComponent(operatorWorkspaceRoot)}&path=${encodeURIComponent(textPath)}`;
    } else {
      link.href = `/api/local/file?workspace_root=${encodeURIComponent(operatorWorkspaceRoot)}&path=${encodeURIComponent(textPath)}`;
    }
    link.target = "_blank";
    link.textContent = textPath;
    li.appendChild(link);
    return li;
  };

  const appendCommandBrief = (titleText, metaLines) => {
    const brief = document.createElement("section");
    brief.className = "command-brief";
    const label = document.createElement("p");
    label.className = "assistant-response-label";
    label.textContent = "Analysis summary";
    brief.appendChild(label);
    const title = document.createElement("h3");
    title.textContent = titleText || payload.answer || "Completed.";
    brief.appendChild(title);
    const meta = (metaLines || []).filter(Boolean);
    if (meta.length) {
      const p = document.createElement("p");
      p.className = "ote-meta";
      p.textContent = meta.join(" · ");
      brief.appendChild(p);
    }
    card.appendChild(brief);
  };

  const appendDecisionList = (titleText, rows) => {
    if (!Array.isArray(rows) || !rows.length) return;
    const block = document.createElement("section");
    block.className = "decision-section";
    const title = document.createElement("p");
    title.className = "assistant-response-label";
    title.textContent = titleText;
    block.appendChild(title);
    const ul = document.createElement("ul");
    ul.className = "assistant-response-list ote-keyout";
    rows.slice(0, 6).forEach((line) => {
      const li = document.createElement("li");
      li.textContent = String(line);
      ul.appendChild(li);
    });
    block.appendChild(ul);
    card.appendChild(block);
  };

  const appendDetailedEvidence = (sections) => {
    const usable = (sections || []).filter((s) => s && Array.isArray(s.rows) && s.rows.length);
    if (!usable.length && !result.source_line) return;
    const details = document.createElement("details");
    details.className = "operator-evidence";
    const summary = document.createElement("summary");
    summary.textContent = "Detailed Evidence";
    details.appendChild(summary);
    const inner = document.createElement("div");
    inner.className = "details-inner";
    if (result.source_line) {
      const src = document.createElement("p");
      src.className = "ote-sub";
      src.textContent = String(result.source_line);
      inner.appendChild(src);
    }
    usable.forEach((section) => {
      const title = document.createElement("p");
      title.className = "assistant-response-label";
      title.textContent = section.title;
      inner.appendChild(title);
      const ul = document.createElement("ul");
      ul.className = "assistant-response-list";
      section.rows.slice(0, section.limit || 12).forEach((row) => {
        ul.appendChild(section.render(row));
      });
      inner.appendChild(ul);
    });
    details.appendChild(inner);
    card.appendChild(details);
  };

  const renderPlainEvidence = (text) => {
    const li = document.createElement("li");
    li.textContent = String(text || "—");
    return li;
  };

  if (contract === "show_project_reports") {
    const reports = Array.isArray(result.reports) ? result.reports : [];
    const pid = result.project_id || "";
    appendCommandBrief(payload.answer || `Project ${pid}: ${reports.length} workbook file(s).`, [
      pid ? `Project ${pid}` : "",
      `${reports.length} report(s)`,
      result.source || "",
    ]);
    appendDecisionList("Primary Findings", [
      reports.length ? `${reports.length} indexed workbook file(s) are available for this project.` : "No indexed workbooks are available for this project.",
      reports[0] && reports[0].path ? `Latest indexed path shown in evidence: ${reports[0].path}` : "",
    ].filter(Boolean));
    appendDetailedEvidence([
      {
        title: "Reports",
        rows: reports,
        limit: 40,
        render: (row) => renderPathItem((row && row.path) || "—"),
      },
      {
        title: "Where the operator looked",
        rows: result.evidence_looked ? [result.evidence_looked] : [],
        render: renderPlainEvidence,
      },
    ]);
    host.prepend(card);
    return;
  }

  if (contract === "trend_project_reports") {
    const trend = (result.found && typeof result.found === "object") ? result.found : result;
    const ownerTrend = (trend.owner_trend_summary && typeof trend.owner_trend_summary === "object") ? trend.owner_trend_summary : {};
    const trendSummary = (trend.trend_summary && typeof trend.trend_summary === "object") ? trend.trend_summary : {};
    const reportsUsed = Array.isArray(trend.reports_used) ? trend.reports_used : [];
    appendCommandBrief(payload.answer || "Project trend ready.", [
      `Project ${trend.project_filter || result.project_filter || "—"}`,
      `${trend.report_count != null ? trend.report_count : result.report_count || 0} reports`,
      `${trend.period_start || "—"} to ${trend.period_end || "—"}`,
    ]);
    appendDecisionList("Primary Findings", Array.isArray(ownerTrend.owner_lines) ? ownerTrend.owner_lines : []);
    appendDetailedEvidence([
      {
        title: "Trend Summary",
        rows: [
          trendSummary.message,
          trendSummary.basis ? `Basis: ${trendSummary.basis}` : "",
          trendSummary.ordering ? `Ordering: ${trendSummary.ordering}` : "",
        ].filter(Boolean),
        render: renderPlainEvidence,
      },
      {
        title: "Reports Used",
        rows: reportsUsed,
        render: (row) => renderPathItem((row && row.path) || "—"),
      },
    ]);
    host.prepend(card);
    return;
  }

  if (st === "completed" && (contract === "compare_latest_report" || contract === "run_weekly_review")) {
    const foundData = result.found || {};
    const workflowOutput = foundData.workflow_output || {};
    const summaryCard = result.summary_card || {};
    const owner = foundData.owner_summary || null;
    const filesUsed = (result.did && result.did.files_used) || {};
    const artifacts = Array.isArray(foundData.artifacts) ? foundData.artifacts : [];
    const keyOutputs = Array.isArray(summaryCard.key_outputs) ? summaryCard.key_outputs : [];
    appendCommandBrief(payload.answer || summaryCard.summary || "Compare completed.", [
      result.project_filter ? `Project ${result.project_filter}` : "",
      foundData.run_id ? `Run ${foundData.run_id}` : "",
      workflowOutput.confidence ? `Confidence ${workflowOutput.confidence}` : "",
    ]);
    if (owner && owner.owner_summary_text) {
      appendDecisionList("Owner Summary", owner.owner_summary_text.split("\n").filter(Boolean).slice(0, 5));
    } else {
      appendDecisionList("Primary Findings", [
        summaryCard.summary,
        ...keyOutputs,
      ].filter(Boolean));
    }
    appendDetailedEvidence([
      {
        title: "Files Used",
        rows: [filesUsed.prior, filesUsed.current].filter(Boolean),
        render: renderPathItem,
      },
      {
        title: "Artifacts",
        rows: artifacts,
        render: renderPathItem,
      },
      {
        title: "Selected Pair",
        rows: foundData.selected_pair ? [JSON.stringify(foundData.selected_pair)] : [],
        render: renderPlainEvidence,
      },
      {
        title: "Weekly Export",
        rows: result.weekly_export ? [JSON.stringify(result.weekly_export)] : [],
        render: renderPlainEvidence,
      },
    ]);
    host.prepend(card);
    return;
  }

  if (contract === "trend_project_reports") {
    const trend = (result.found && typeof result.found === "object") ? result.found : result;
    const trendSummary = (trend.trend_summary && typeof trend.trend_summary === "object") ? trend.trend_summary : {};
    const ownerTrend = (trend.owner_trend_summary && typeof trend.owner_trend_summary === "object") ? trend.owner_trend_summary : {};
    const reportsUsed = Array.isArray(trend.reports_used) ? trend.reports_used : [];

    if (ownerTrend && Array.isArray(ownerTrend.owner_lines) && ownerTrend.owner_lines.length) {
      const ownerTitle = document.createElement("p");
      ownerTitle.className = "assistant-response-label";
      ownerTitle.textContent = "Owner trend summary";
      card.appendChild(ownerTitle);

      const ownerBlock = document.createElement("div");
      ownerBlock.className = "operator-summary-card";
      const ownerList = document.createElement("ul");
      ownerList.className = "assistant-response-list ote-keyout";
      ownerTrend.owner_lines.slice(0, 5).forEach((line) => {
        const li = document.createElement("li");
        li.textContent = String(line);
        ownerList.appendChild(li);
      });
      ownerBlock.appendChild(ownerList);

      if (ownerTrend.cadence_observation) {
        const cadence = document.createElement("p");
        cadence.className = "ote-sub";
        cadence.textContent = "Cadence: " + ownerTrend.cadence_observation;
        ownerBlock.appendChild(cadence);
      }
      card.appendChild(ownerBlock);

      const refs = [
        ["Latest", ownerTrend.latest_report],
        ["Prior", ownerTrend.prior_report],
        ["Oldest", ownerTrend.oldest_report],
      ].filter(([, row]) => row && typeof row === "object");
      if (refs.length) {
        const refWrap = document.createElement("div");
        refWrap.className = "drivers-table-wrap";
        const refTable = document.createElement("table");
        refTable.className = "drivers-table assistant-response-table data-table";
        const refHead = document.createElement("thead");
        const refHeadRow = document.createElement("tr");
        ["Role", "Report", "Period", "Family"].forEach((h) => {
          const th = document.createElement("th");
          th.textContent = h;
          refHeadRow.appendChild(th);
        });
        refHead.appendChild(refHeadRow);
        refTable.appendChild(refHead);
        const refBody = document.createElement("tbody");
        refs.forEach(([role, row]) => {
          const tr = document.createElement("tr");
          const cRole = document.createElement("td");
          cRole.textContent = role;
          tr.appendChild(cRole);
          const cPath = document.createElement("td");
          const list = document.createElement("ul");
          list.className = "assistant-response-list";
          list.appendChild(renderPathItem(row.path || row.name || ""));
          cPath.appendChild(list);
          tr.appendChild(cPath);
          const cPeriod = document.createElement("td");
          cPeriod.textContent = row.period || row.version_date || row.modified_at || "—";
          tr.appendChild(cPeriod);
          const cFamily = document.createElement("td");
          cFamily.textContent = row.report_family || "unknown";
          tr.appendChild(cFamily);
          refBody.appendChild(tr);
        });
        refTable.appendChild(refBody);
        refWrap.appendChild(refTable);
        card.appendChild(refWrap);
      }
    }

    const title = document.createElement("p");
    title.className = "assistant-response-label";
    title.textContent = "Trend result";
    card.appendChild(title);

    const meta = document.createElement("ul");
    meta.className = "assistant-response-list ote-keyout";
    [
      `Project: ${trend.project_filter || result.project_filter || "—"}`,
      `Report count: ${trend.report_count != null ? trend.report_count : result.report_count || 0}`,
      `Period: ${trend.period_start || "—"} to ${trend.period_end || "—"}`,
    ].forEach((line) => {
      const li = document.createElement("li");
      li.textContent = line;
      meta.appendChild(li);
    });
    card.appendChild(meta);

    const summaryRows = [];
    if (trendSummary.message) summaryRows.push(["Summary", trendSummary.message]);
    if (trendSummary.basis) summaryRows.push(["Basis", trendSummary.basis]);
    if (trendSummary.ordering) summaryRows.push(["Ordering", trendSummary.ordering]);
    if (trendSummary.family_counts && typeof trendSummary.family_counts === "object") {
      summaryRows.push([
        "Report families",
        Object.entries(trendSummary.family_counts)
          .map(([family, count]) => `${family}: ${count}`)
          .join(", "),
      ]);
    }
    if (summaryRows.length) {
      const tableWrap = document.createElement("div");
      tableWrap.className = "drivers-table-wrap";
      const table = document.createElement("table");
      table.className = "drivers-table assistant-response-table data-table";
      const tbody = document.createElement("tbody");
      summaryRows.forEach(([label, value]) => {
        const tr = document.createElement("tr");
        const th = document.createElement("th");
        th.scope = "row";
        th.textContent = label;
        const td = document.createElement("td");
        td.textContent = value || "—";
        tr.appendChild(th);
        tr.appendChild(td);
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      tableWrap.appendChild(table);
      card.appendChild(tableWrap);
    }

    const repTitle = document.createElement("p");
    repTitle.className = "assistant-response-label";
    repTitle.textContent = "Reports used";
    card.appendChild(repTitle);
    if (reportsUsed.length) {
      const tableWrap = document.createElement("div");
      tableWrap.className = "drivers-table-wrap";
      const table = document.createElement("table");
      table.className = "drivers-table assistant-response-table data-table";
      const thead = document.createElement("thead");
      const hr = document.createElement("tr");
      ["#", "Report", "Period", "Family", "Order basis"].forEach((h) => {
        const th = document.createElement("th");
        th.textContent = h;
        hr.appendChild(th);
      });
      thead.appendChild(hr);
      table.appendChild(thead);
      const tbody = document.createElement("tbody");
      reportsUsed.slice(0, 12).forEach((row) => {
        const tr = document.createElement("tr");
        const cSeq = document.createElement("td");
        cSeq.textContent = String(row.sequence || "");
        tr.appendChild(cSeq);
        const cPath = document.createElement("td");
        const list = document.createElement("ul");
        list.className = "assistant-response-list";
        list.appendChild(renderPathItem(row.path || row.name || ""));
        cPath.appendChild(list);
        tr.appendChild(cPath);
        const cPeriod = document.createElement("td");
        cPeriod.textContent = row.version_date || row.modified_at || "—";
        tr.appendChild(cPeriod);
        const cFamily = document.createElement("td");
        cFamily.textContent = row.report_family || "unknown";
        tr.appendChild(cFamily);
        const cBasis = document.createElement("td");
        cBasis.textContent = row.order_basis || "—";
        tr.appendChild(cBasis);
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      tableWrap.appendChild(table);
      card.appendChild(tableWrap);
    } else {
      const empty = document.createElement("p");
      empty.className = "ote-sub";
      empty.textContent = "No scoped indexed reports were used.";
      card.appendChild(empty);
    }
  }

  if (contract === "compare_multi_reports") {
    const multi = (result.found && typeof result.found === "object") ? result.found : result;
    const reportsUsed = Array.isArray(multi.reports_used) ? multi.reports_used : [];
    const comparisonPairs = Array.isArray(multi.comparison_pairs) ? multi.comparison_pairs : [];
    const ownerLines = Array.isArray(multi.owner_lines) ? multi.owner_lines : [];

    if (ownerLines.length) {
      const ownerTitle = document.createElement("p");
      ownerTitle.className = "assistant-response-label";
      ownerTitle.textContent = "Owner lines";
      card.appendChild(ownerTitle);
      const ownerBlock = document.createElement("div");
      ownerBlock.className = "operator-summary-card";
      const ownerList = document.createElement("ul");
      ownerList.className = "assistant-response-list ote-keyout";
      ownerLines.slice(0, 5).forEach((line) => {
        const li = document.createElement("li");
        li.textContent = String(line);
        ownerList.appendChild(li);
      });
      ownerBlock.appendChild(ownerList);
      card.appendChild(ownerBlock);
    }

    const title = document.createElement("p");
    title.className = "assistant-response-label";
    title.textContent = "Multi-period comparison";
    card.appendChild(title);
    const meta = document.createElement("ul");
    meta.className = "assistant-response-list ote-keyout";
    [
      `Project: ${multi.project_filter || result.project_filter || "—"}`,
      `Requested reports: ${multi.requested_report_count != null ? multi.requested_report_count : result.requested_report_count || 0}`,
      `Reports selected: ${multi.report_count != null ? multi.report_count : result.report_count || 0}`,
      `Adjacent pairs: ${multi.pair_count != null ? multi.pair_count : result.pair_count || 0}`,
      `Period: ${multi.period_start || "—"} to ${multi.period_end || "—"}`,
    ].forEach((line) => {
      const li = document.createElement("li");
      li.textContent = line;
      meta.appendChild(li);
    });
    card.appendChild(meta);

    const repTitle = document.createElement("p");
    repTitle.className = "assistant-response-label";
    repTitle.textContent = "Reports used";
    card.appendChild(repTitle);
    if (reportsUsed.length) {
      const tableWrap = document.createElement("div");
      tableWrap.className = "drivers-table-wrap";
      const table = document.createElement("table");
      table.className = "drivers-table assistant-response-table data-table";
      const thead = document.createElement("thead");
      const hr = document.createElement("tr");
      ["#", "Report", "Period", "Family", "Order basis"].forEach((h) => {
        const th = document.createElement("th");
        th.textContent = h;
        hr.appendChild(th);
      });
      thead.appendChild(hr);
      table.appendChild(thead);
      const tbody = document.createElement("tbody");
      reportsUsed.slice(0, 12).forEach((row) => {
        const tr = document.createElement("tr");
        const cSeq = document.createElement("td");
        cSeq.textContent = String(row.sequence || "");
        tr.appendChild(cSeq);
        const cPath = document.createElement("td");
        const list = document.createElement("ul");
        list.className = "assistant-response-list";
        list.appendChild(renderPathItem(row.path || row.name || ""));
        cPath.appendChild(list);
        tr.appendChild(cPath);
        const cPeriod = document.createElement("td");
        cPeriod.textContent = row.version_date || row.modified_at || "—";
        tr.appendChild(cPeriod);
        const cFamily = document.createElement("td");
        cFamily.textContent = row.report_family || "unknown";
        tr.appendChild(cFamily);
        const cBasis = document.createElement("td");
        cBasis.textContent = row.order_basis || "—";
        tr.appendChild(cBasis);
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      tableWrap.appendChild(table);
      card.appendChild(tableWrap);
    }

    const delta = (multi.multi_period_delta && typeof multi.multi_period_delta === "object") ? multi.multi_period_delta : {};
    const pairResults = Array.isArray(delta.pair_results) ? delta.pair_results : [];
    const repeatedMovers = Array.isArray(delta.repeated_movers) ? delta.repeated_movers : [];
    const largestCumulative = Array.isArray(delta.largest_cumulative_movers) ? delta.largest_cumulative_movers : [];
    const latestMovers = Array.isArray(delta.latest_period_movers) ? delta.latest_period_movers : [];
    const actionItems = Array.isArray(delta.action_items) ? delta.action_items : [];
    const latestWatchlist = Array.isArray(delta.latest_period_watchlist) ? delta.latest_period_watchlist : [];
    const repeatedRiskItems = Array.isArray(delta.repeated_risk_items) ? delta.repeated_risk_items : [];
    const movementCategories = (delta.movement_categories && typeof delta.movement_categories === "object") ? delta.movement_categories : {};
    const actionView = (delta.action_view && typeof delta.action_view === "object") ? delta.action_view : {};
    const costDrilldown = (delta.cost_type_drilldown && typeof delta.cost_type_drilldown === "object") ? delta.cost_type_drilldown : {};
    const uncategorizedCount = Number(delta.uncategorized_count || 0);
    const deltaLimitations = Array.isArray(delta.limitations) ? delta.limitations : [];
    const deltaOwnerLines = Array.isArray(delta.owner_lines) ? delta.owner_lines : [];
    if (Object.keys(actionView).length || actionItems.length || latestWatchlist.length || repeatedRiskItems.length || Object.keys(movementCategories).length) {
      const actionTitle = document.createElement("p");
      actionTitle.className = "assistant-response-label";
      actionTitle.textContent = "Action view";
      card.appendChild(actionTitle);
      const actionBlock = document.createElement("div");
      actionBlock.className = "operator-summary-card";
      const renderActionSection = (label, rows) => {
        if (!rows.length) return;
        const t = document.createElement("p");
        t.className = "assistant-response-label";
        t.textContent = label;
        actionBlock.appendChild(t);
        const ul = document.createElement("ul");
        ul.className = "assistant-response-list";
        rows.slice(0, 5).forEach((row) => {
          const li = document.createElement("li");
          const amount = row.amount != null ? ` · ${fmtMoneySigned(row.amount)}` : "";
          const pairs = Array.isArray(row.pair_sequences) && row.pair_sequences.length ? ` · pairs ${row.pair_sequences.join(", ")}` : "";
          li.textContent = `${row.label || row.key || "Line item"} · ${row.movement_category || "uncategorized"}${amount}${pairs}`;
          ul.appendChild(li);
        });
        actionBlock.appendChild(ul);
      };
      renderActionSection("Top issues", Array.isArray(actionView.top_issues) ? actionView.top_issues : []);
      renderActionSection("New this period", Array.isArray(actionView.new_this_period) ? actionView.new_this_period : []);
      renderActionSection("Ongoing risks", Array.isArray(actionView.ongoing_risks) ? actionView.ongoing_risks : []);
      renderActionSection("Watchlist", Array.isArray(actionView.watchlist) ? actionView.watchlist : []);
      const cats = Object.entries(movementCategories)
        .filter(([, row]) => row && Number(row.count || 0) > 0)
        .map(([cat, row]) => `${cat}: ${row.count}`);
      if (cats.length) {
        const p = document.createElement("p");
        p.className = "ote-sub";
        p.textContent = "Movement categories: " + cats.join(", ") + (uncategorizedCount > 0 ? ` · Uncategorized: ${uncategorizedCount}` : "");
        actionBlock.appendChild(p);
      }
      card.appendChild(actionBlock);
    }
    if (Object.keys(costDrilldown).length) {
      const drillTitle = document.createElement("p");
      drillTitle.className = "assistant-response-label";
      drillTitle.textContent = "Cost breakdown (drill-down)";
      card.appendChild(drillTitle);
      const drillWrap = document.createElement("div");
      drillWrap.className = "operator-summary-card";
      const bucketLabels = [
        ["labor", "Labor"],
        ["material", "Material"],
        ["subcontract", "Subcontract"],
        ["uncategorized", "Uncategorized"],
      ];
      bucketLabels.forEach(([key, label]) => {
        const bucket = costDrilldown[key] || {};
        const count = Number(bucket.count || 0);
        if (!count && key === "uncategorized") return;
        if (!count && key !== "uncategorized") return;
        const heading = document.createElement("p");
        heading.className = "assistant-response-label";
        const coverage = Array.isArray(bucket.pair_coverage) && bucket.pair_coverage.length ? ` · pairs ${bucket.pair_coverage.join(", ")}` : "";
        const conf = bucket.confidence_breakdown || {};
        const confText = `${Number(conf.structured_count || 0)} structured / ${Number(conf.keyword_count || 0)} keyword / ${Number(conf.uncategorized_count || 0)} uncategorized`;
        heading.textContent = `${label}: ${count} item(s), ${fmtMoneySigned(bucket.total_abs_movement || 0)} total movement · ${confText}${coverage}`;
        drillWrap.appendChild(heading);
        const ul = document.createElement("ul");
        ul.className = "assistant-response-list";
        (bucket.items || []).slice(0, 10).forEach((item) => {
          const li = document.createElement("li");
          const pairs = Array.isArray(item.pair_sequences) && item.pair_sequences.length ? ` · pairs ${item.pair_sequences.join(", ")}` : "";
          li.textContent = `${item.label || item.key || "Line item"} · ${fmtMoneySigned(item.cumulative_delta || 0)}${pairs}`;
          ul.appendChild(li);
        });
        drillWrap.appendChild(ul);
      });
      card.appendChild(drillWrap);
    }
    if (pairResults.length || repeatedMovers.length || largestCumulative.length || latestMovers.length || deltaLimitations.length) {
      const deltaTitle = document.createElement("p");
      deltaTitle.className = "assistant-response-label";
      deltaTitle.textContent = "Multi-period delta";
      card.appendChild(deltaTitle);
      if (deltaOwnerLines.length) {
        const ul = document.createElement("ul");
        ul.className = "assistant-response-list ote-keyout";
        deltaOwnerLines.slice(0, 5).forEach((line) => {
          const li = document.createElement("li");
          li.textContent = String(line);
          ul.appendChild(li);
        });
        card.appendChild(ul);
      }
      const renderMoverList = (label, rows, deltaKey) => {
        if (!rows.length) return;
        const t = document.createElement("p");
        t.className = "assistant-response-label";
        t.textContent = label;
        card.appendChild(t);
        const ul = document.createElement("ul");
        ul.className = "assistant-response-list";
        rows.slice(0, 6).forEach((row) => {
          const li = document.createElement("li");
          const amount = row[deltaKey] != null ? ` (${fmtMoneySigned(row[deltaKey])})` : "";
          const pairs = Array.isArray(row.pair_sequences) && row.pair_sequences.length ? ` · pairs ${row.pair_sequences.join(", ")}` : "";
          li.textContent = `${row.label || row.key || "Line item"}${amount}${pairs}`;
          ul.appendChild(li);
        });
        card.appendChild(ul);
      };
      renderMoverList("Repeated movers", repeatedMovers, "cumulative_delta");
      renderMoverList("Largest cumulative movers", largestCumulative, "cumulative_delta");
      renderMoverList("Latest-period movers", latestMovers, "delta");
      if (pairResults.length) {
        const t = document.createElement("p");
        t.className = "assistant-response-label";
        t.textContent = "Pair results";
        card.appendChild(t);
        const ul = document.createElement("ul");
        ul.className = "assistant-response-list";
        pairResults.slice(0, 6).forEach((pair) => {
          const li = document.createElement("li");
          li.textContent = `Pair ${pair.pair_sequence || "—"}: ${pair.status || "unknown"} · top changes ${
            Array.isArray(pair.top_changes) ? pair.top_changes.length : 0
          }`;
          ul.appendChild(li);
        });
        card.appendChild(ul);
      }
      if (deltaLimitations.length) {
        const t = document.createElement("p");
        t.className = "assistant-response-label";
        t.textContent = "Limitations";
        card.appendChild(t);
        const ul = document.createElement("ul");
        ul.className = "assistant-response-list";
        deltaLimitations.slice(0, 6).forEach((line) => {
          const li = document.createElement("li");
          li.textContent = String(line);
          ul.appendChild(li);
        });
        card.appendChild(ul);
      }
    }

    const pairTitle = document.createElement("p");
    pairTitle.className = "assistant-response-label";
    pairTitle.textContent = "Comparison pairs";
    card.appendChild(pairTitle);
    if (comparisonPairs.length) {
      const tableWrap = document.createElement("div");
      tableWrap.className = "drivers-table-wrap";
      const table = document.createElement("table");
      table.className = "drivers-table assistant-response-table data-table";
      const thead = document.createElement("thead");
      const hr = document.createElement("tr");
      ["#", "From", "To", "Summary"].forEach((h) => {
        const th = document.createElement("th");
        th.textContent = h;
        hr.appendChild(th);
      });
      thead.appendChild(hr);
      table.appendChild(thead);
      const tbody = document.createElement("tbody");
      comparisonPairs.slice(0, 12).forEach((pair) => {
        const tr = document.createElement("tr");
        const cSeq = document.createElement("td");
        cSeq.textContent = String(pair.pair_sequence || "");
        tr.appendChild(cSeq);
        ["from_report", "to_report"].forEach((key) => {
          const cell = document.createElement("td");
          const row = pair[key] || {};
          const list = document.createElement("ul");
          list.className = "assistant-response-list";
          list.appendChild(renderPathItem(row.path || row.name || ""));
          cell.appendChild(list);
          const period = document.createElement("p");
          period.className = "ote-sub";
          period.textContent = row.period || row.version_date || row.modified_at || "—";
          cell.appendChild(period);
          tr.appendChild(cell);
        });
        const cSummary = document.createElement("td");
        cSummary.textContent = pair.summary || "—";
        tr.appendChild(cSummary);
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      tableWrap.appendChild(table);
      card.appendChild(tableWrap);
    } else {
      const empty = document.createElement("p");
      empty.className = "ote-sub";
      empty.textContent = "No adjacent comparison pairs were built.";
      card.appendChild(empty);
    }

  }

  const pathRows = Array.isArray(summaryCard.paths) ? summaryCard.paths : [];
  if (pathRows.length) {
    const title = document.createElement("p");
    title.className = "assistant-response-label";
    title.textContent = "Open files";
    card.appendChild(title);
    const ul = document.createElement("ul");
    ul.className = "assistant-response-list";
    pathRows.slice(0, 8).forEach((path) => {
      ul.appendChild(renderPathItem(path));
    });
    card.appendChild(ul);
  }

  if (Array.isArray(found.labor_deltas) && found.labor_deltas.length) {
    const title = document.createElement("p");
    title.className = "assistant-response-label";
    title.textContent = "Top labor deltas";
    card.appendChild(title);
    const ul = document.createElement("ul");
    ul.className = "assistant-response-list";
    found.labor_deltas.slice(0, 6).forEach((row) => {
      const li = document.createElement("li");
      li.textContent = `${row.category_label}: ${fmtMoneySigned(row.delta)}`;
      ul.appendChild(li);
    });
    card.appendChild(ul);
  }

  if (found.workflow_output && typeof found.workflow_output === "object") {
    const wo = found.workflow_output;
    const title = document.createElement("p");
    title.className = "assistant-response-label";
    title.textContent = "Key numbers";
    card.appendChild(title);
    const ul = document.createElement("ul");
    ul.className = "assistant-response-list";
    if (wo.profit_delta !== undefined) {
      const li = document.createElement("li");
      li.textContent = `Profit delta: ${fmtMoneySigned(wo.profit_delta)}`;
      ul.appendChild(li);
    }
    if (wo.cost_vs_revenue && wo.cost_vs_revenue.signal) {
      const li = document.createElement("li");
      li.textContent = `Cost vs revenue: ${wo.cost_vs_revenue.signal}`;
      ul.appendChild(li);
    }
    if (wo.confidence) {
      const li = document.createElement("li");
      li.textContent = `Confidence: ${wo.confidence}`;
      ul.appendChild(li);
    }
    (wo.risk_signals || []).slice(0, 3).forEach((risk) => {
      const li = document.createElement("li");
      li.textContent = `Risk: ${risk}`;
      ul.appendChild(li);
    });
    if (
      typeof wo.driver_table_primary_count === "number" &&
      typeof wo.driver_table_smaller_moves_count === "number" &&
      (wo.driver_table_primary_count > 0 || wo.driver_table_smaller_moves_count > 0)
    ) {
      const li = document.createElement("li");
      li.textContent = `Driver table: ${wo.driver_table_primary_count} Top drivers, ${wo.driver_table_smaller_moves_count} Smaller moves`;
      ul.appendChild(li);
    }
    const tdSmaller = Boolean(wo.top_drivers_from_smaller_moves_only);
    (wo.top_drivers || []).slice(0, 3).forEach((driver) => {
      const li = document.createElement("li");
      const lineLabel = driver.display_label || driver.category_label || driver.category || "line";
      li.textContent = `${tdSmaller ? "Smaller move" : "Top driver"}: ${lineLabel} (${fmtMoneySigned(driver.delta)})`;
      ul.appendChild(li);
    });
    card.appendChild(ul);
    if (
      typeof wo.driver_table_primary_count === "number" &&
      typeof wo.driver_table_smaller_moves_count === "number" &&
      wo.top_drivers &&
      wo.top_drivers.length
    ) {
      const pNote = document.createElement("p");
      pNote.className = "ote-sub";
      pNote.textContent =
        "Top drivers use the same ranked driver table as the owner summary and export.";
      card.appendChild(pNote);
    }
    const links = document.createElement("ul");
    links.className = "assistant-response-list";
    (wo.artifact_links || []).slice(0, 5).forEach((artifact) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = artifact.url;
      a.target = "_blank";
      a.textContent = artifact.path || "artifact";
      li.appendChild(a);
      links.appendChild(li);
    });
    (wo.workbook_preview_links || []).slice(0, 2).forEach((linkRow) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = linkRow.preview_url;
      a.target = "_blank";
      a.textContent = `Preview ${linkRow.label}: ${linkRow.path}`;
      li.appendChild(a);
      links.appendChild(li);
    });
    if (links.childElementCount) {
      card.appendChild(links);
    }
  }

  if (
    found.owner_summary &&
    typeof found.owner_summary === "object" &&
    !found.owner_summary.owner_summary_text
  ) {
    const owner = found.owner_summary;
    const title = document.createElement("p");
    title.className = "assistant-response-label";
    title.textContent = "Owner summary (legacy)";
    card.appendChild(title);
    const ul = document.createElement("ul");
    ul.className = "assistant-response-list";
    const li1 = document.createElement("li");
    li1.textContent = `Profit delta: ${fmtMoneySigned(owner.profit_delta)}`;
    ul.appendChild(li1);
    (owner.top_drivers || []).slice(0, 2).forEach((driver) => {
      const li = document.createElement("li");
      li.textContent = `Top driver: ${(driver.category_label || driver.category || "line")} (${fmtMoneySigned(driver.delta)})`;
      ul.appendChild(li);
    });
    const li2 = document.createElement("li");
    li2.textContent = `Key concern: ${owner.key_concern || "n/a"}`;
    ul.appendChild(li2);
    const li3 = document.createElement("li");
    li3.textContent = `Recommended focus: ${owner.recommended_focus || "n/a"}`;
    ul.appendChild(li3);
    card.appendChild(ul);
  }

  if (found.export_csv && typeof found.export_csv === "object") {
    const ex = found.export_csv;
    const title = document.createElement("p");
    title.className = "assistant-response-label";
    title.textContent = ex.skipped ? "Top changes export" : "Export completed";
    card.appendChild(title);
    const ul = document.createElement("ul");
    ul.className = "assistant-response-list";
    if (ex.skipped) {
      const li = document.createElement("li");
      li.textContent = ex.message || "No line-level material rows; export not created.";
      ul.appendChild(li);
    } else {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = ex.download_url || "#";
      a.target = "_blank";
      a.textContent = ex.path || "top_changes_driver_table.csv";
      li.appendChild(a);
      ul.appendChild(li);
      const c1 = document.createElement("li");
      c1.textContent = `Rows: ${ex.rows_written != null ? ex.rows_written : ex.row_count || 0} (Top drivers: ${
        ex.top_driver_count != null ? ex.top_driver_count : "—"
      }, Smaller moves: ${ex.smaller_move_count != null ? ex.smaller_move_count : "—"})`;
      ul.appendChild(c1);
      if (ex.truncated) {
        const c2 = document.createElement("li");
        c2.className = "ote-sub";
        c2.textContent = "File may be truncated at the row cap; full split counts are in the list above.";
        ul.appendChild(c2);
      }
    }
    const n = document.createElement("p");
    n.className = "ote-sub";
    n.textContent = (ex.grounding && String(ex.grounding)) || "Grounded in Top drivers by impact.";
    card.appendChild(ul);
    card.appendChild(n);
  }

  if (result.weekly_export && typeof result.weekly_export === "object") {
    const ex = result.weekly_export;
    const title = document.createElement("p");
    title.className = "assistant-response-label";
    title.textContent = ex.skipped ? "Weekly top changes" : "Weekly export";
    card.appendChild(title);
    const ul = document.createElement("ul");
    ul.className = "assistant-response-list";
    if (ex.skipped) {
      const li = document.createElement("li");
      li.textContent = ex.message || "No line-level material rows; export not created.";
      ul.appendChild(li);
    } else {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = ex.download_url || "#";
      a.target = "_blank";
      a.textContent = ex.path || "top_changes_driver_table.csv";
      li.appendChild(a);
      ul.appendChild(li);
      const c1 = document.createElement("li");
      c1.textContent = `Rows: ${ex.rows_written != null ? ex.rows_written : ex.row_count || 0} (Top drivers: ${
        ex.top_driver_count != null ? ex.top_driver_count : "—"
      }, Smaller moves: ${ex.smaller_move_count != null ? ex.smaller_move_count : "—"})`;
      ul.appendChild(c1);
    }
    const n = document.createElement("p");
    n.className = "ote-sub";
    n.textContent = (ex.grounding && String(ex.grounding)) || "Grounded in Top drivers by impact.";
    card.appendChild(ul);
    card.appendChild(n);
  }

  if (contract === "show_project_reports" && !result.source_line && result.source && typeof result.source === "string") {
    const s2 = document.createElement("p");
    s2.className = "ote-sub";
    s2.textContent = "Source: " + result.source + ".";
    card.appendChild(s2);
  }
  if (result.evidence_looked) {
    const lab = document.createElement("p");
    lab.className = "assistant-response-label";
    lab.textContent = "Where the operator looked";
    card.appendChild(lab);
    const pLook = document.createElement("p");
    pLook.className = "ote-sub";
    pLook.textContent = String(result.evidence_looked);
    card.appendChild(pLook);
  }
  if (Array.isArray(result.reports) && result.reports.length) {
    const tRep = document.createElement("p");
    tRep.className = "assistant-response-label";
    tRep.textContent = "Workbooks";
    card.appendChild(tRep);
    const uRep = document.createElement("ul");
    uRep.className = "assistant-response-list";
    result.reports.slice(0, 20).forEach((row) => {
      const li = document.createElement("li");
      const pth = (row && row.path) || "—";
      if (pth && pth !== "—" && operatorWorkspaceRoot) {
        li.appendChild(renderPathItem(pth));
      } else {
        li.textContent = pth;
      }
      uRep.appendChild(li);
    });
    card.appendChild(uRep);
  } else if (st === "completed" && contract === "show_project_reports" && Array.isArray(result.reports) && result.reports.length === 0) {
    const t0 = document.createElement("p");
    t0.className = "ote-sub";
    t0.textContent = "No workbooks listed (empty set).";
    card.appendChild(t0);
  }
  const nextSteps = Array.isArray(result.next_steps) ? result.next_steps : [];
  if (nextSteps.length) {
    const title = document.createElement("p");
    title.className = "assistant-response-label";
    title.textContent = "What to do next";
    card.appendChild(title);
    const ul = document.createElement("ul");
    ul.className = "assistant-response-list ote-next";
    nextSteps.slice(0, 4).forEach((step) => {
      const li = document.createElement("li");
      li.textContent = String(step);
      ul.appendChild(li);
    });
    card.appendChild(ul);
  }

  if (st === "completed") {
    const trust = document.createElement("p");
    trust.className = "ote-trust";
    trust.textContent = "Task finished. Review the result below or run another analysis.";
    card.appendChild(trust);
  }

  host.prepend(card);
}
