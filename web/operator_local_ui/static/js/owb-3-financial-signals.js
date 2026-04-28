/**
 * owb-3-financial-signals.js — Load order: 3 of 4.
 * MoM comparison block, analysis hero / metrics / workbench presentation (class names may retain historical "signals" tokens).
 */
function renderMom219128Block(mom) {
  if (!mom || mom.available === false) {
    if (!mom || !mom.error) return null;
    const err = document.createElement("p");
    err.className = "subtle small mom-219128-unavailable";
    err.textContent = "Feb→Mar 219128 comparison unavailable: " + String(mom.error);
    return err;
  }
  const d0 = mom.deltas || {};
  const tecDelta = d0.total_extended_project_costs;
  const u0 = mom.unchanged_headline_components || {};
  const root = document.createElement("section");
  root.className = "analysis-section-card mom-219128-section";
  root.setAttribute("aria-label", "219128 February to March comparison");
  const box = document.createElement("div");
  box.className = "mom-219128-block";
  const h = document.createElement("h3");
  h.className = "analysis-section-title";
  h.textContent = "219128 Feb → Mar comparison";
  const lede = document.createElement("p");
  lede.className = "analysis-section-lede";
  lede.textContent =
    "Deterministic month-over-month. Extended project cost Δ (Mar−Feb) " +
    (tecDelta == null ? "—" : fmtUsd(tecDelta)) +
    ". " +
    [
      u0.cm_fee_unchanged ? "CM fee steady." : "CM fee moved.",
      u0.prior_system_profit_unchanged ? "Prior-system profit steady." : "Prior-system moved.",
      u0.pco_profit_unchanged ? "PCO steady." : "PCO moved.",
    ].join(" ");
  const psubD = document.createElement("details");
  psubD.className = "details-inline mom-meta-details";
  const psubS = document.createElement("summary");
  psubS.className = "subtle small mom-meta-summary";
  psubS.textContent = "How this compare is computed";
  const psub = document.createElement("p");
  psub.className = "subtle small";
  psub.textContent =
    "Sourced from server-side comparison (same as scripts/compare_219128_profit_mom.py and GET /api/local/financial/219128_feb_mar_mom).";
  psubD.appendChild(psubS);
  psubD.appendChild(psub);
  box.appendChild(h);
  box.appendChild(lede);
  box.appendChild(psubD);

  const sfeb = mom.summary_feb || {};
  const smar = mom.summary_mar || {};
  const d = d0;
  const tbl = document.createElement("table");
  tbl.className = "mom-summary-table data-table";
  const cap = document.createElement("caption");
  cap.className = "visually-hidden";
  cap.textContent = "219128 February vs March summary (USD for dollar rows)";
  tbl.appendChild(cap);
  const thead = document.createElement("thead");
  const thr = document.createElement("tr");
  ["Field", "February", "March", "Delta (Mar − Feb)"].forEach((t) => {
    const c = document.createElement("th");
    c.setAttribute("scope", "col");
    c.textContent = t;
    thr.appendChild(c);
  });
  thead.appendChild(thr);
  tbl.appendChild(thead);
  const tb = document.createElement("tbody");
  const addRow = (label, key, isCount) => {
    const a = sfeb[key];
    const b = smar[key];
    const dlt = d[key];
    const tr = document.createElement("tr");
    const thL = document.createElement("th");
    thL.setAttribute("scope", "row");
    thL.textContent = label;
    tr.appendChild(thL);
    const t1 = isCount ? String(a) : fmtUsd(a);
    const t2 = isCount ? String(b) : fmtUsd(b);
    const t3 = isCount
      ? (dlt >= 0 ? "+" : "") + String(dlt)
      : dlt == null
        ? "—"
        : fmtUsd(dlt);
    [t1, t2, t3].forEach((txt) => {
      const c = document.createElement("td");
      c.textContent = txt;
      tr.appendChild(c);
    });
    tb.appendChild(tr);
  };
  addRow("CM fee", "cm_fee", false);
  addRow("Prior-system profit", "prior_system_profit", false);
  addRow("PCO profit", "pco_profit", false);
  addRow("Total original project costs", "total_original_project_costs", false);
  addRow("Total extended project costs", "total_extended_project_costs", false);
  addRow("Owner change orders (count)", "owner_change_orders_count", true);
  addRow("Owner change orders (value)", "owner_change_orders_value", false);
  addRow("CM change orders (count)", "cm_change_orders_count", true);
  addRow("CM change orders (value)", "cm_change_orders_value", false);
  tbl.appendChild(tb);
  const sumWrap = document.createElement("div");
  sumWrap.className = "mom-summary-table-wrap";
  sumWrap.appendChild(tbl);
  box.appendChild(sumWrap);

  const badgeRow = document.createElement("div");
  badgeRow.className = "mom-unch-badges";
  [
    ["CM fee", u0.cm_fee_unchanged],
    ["Prior-system", u0.prior_system_profit_unchanged],
    ["PCO profit", u0.pco_profit_unchanged],
  ].forEach(([lab, ok]) => {
    const s = document.createElement("span");
    s.className = "mom-unch-badge" + (ok ? " mom-unch-badge--ok" : " mom-unch-badge--warn");
    s.textContent = ok ? "✓ " + lab + " unchanged" : "△ " + lab + " — see table";
    badgeRow.appendChild(s);
  });
  box.appendChild(badgeRow);

  const trio = document.createElement("div");
  trio.className = "mom-driver-trio";
  [
    { label: "Extended project costs (Δ)", v: d0.total_extended_project_costs },
    { label: "Owner CO (value Δ)", v: d0.owner_change_orders_value },
    { label: "CM CO (value Δ)", v: d0.cm_change_orders_value },
  ].forEach((row) => {
    const c = document.createElement("div");
    c.className = "mom-driver-delta";
    const lab = document.createElement("span");
    lab.className = "mom-driver-delta-label";
    lab.textContent = row.label;
    const val = document.createElement("span");
    val.className = "mom-driver-delta-value";
    val.textContent = row.v == null ? "—" : fmtUsd(row.v);
    c.appendChild(lab);
    c.appendChild(val);
    trio.appendChild(c);
  });
  box.appendChild(trio);

  const ex = mom.explanations || {};
  const addEx = (title, block, target) => {
    if (!block) return;
    const h4 = document.createElement("h4");
    h4.className = "signals-subh";
    h4.textContent = title;
    target.appendChild(h4);
    if (block.headline_delta != null) {
      const p = document.createElement("p");
      p.className = "subtle";
      p.textContent = "Net change (server): " + fmtUsd(block.headline_delta);
      target.appendChild(p);
    }
    if (block.headline_value_delta != null) {
      const p = document.createElement("p");
      p.className = "subtle";
      p.textContent =
        "Value delta " +
        fmtUsd(block.headline_value_delta) +
        (block.headline_count_delta != null ? ", count delta " + String(block.headline_count_delta) : "");
      target.appendChild(p);
    }
    const uu = document.createElement("ul");
    uu.className = "assistant-response-list";
    (block.top_driver_rows || []).slice(0, 20).forEach((r) => {
      const li = document.createElement("li");
      const name = (r.raw_cost_code || "—") + " · " + (r.cost_code_name || "—");
      const mr = r.excel_row_mar != null ? " · Mar row " + r.excel_row_mar : "";
      li.textContent = name + " — Δ " + fmtUsd(r.delta_ucb) + mr;
      uu.appendChild(li);
    });
    target.appendChild(uu);
  };
  const driversDet = document.createElement("details");
  driversDet.className = "details-panel disclosure-panel mom-drivers-collapse";
  const driversS = document.createElement("summary");
  driversS.textContent = "Top drivers (extended cost, owner CO, CM CO)";
  const driversBody = document.createElement("div");
  driversBody.className = "details-inner";
  addEx("Extended cost increase (top n_prefixed UCB move)", ex.extended_cost_increase, driversBody);
  addEx("Owner change order increase (top lines)", ex.owner_co_increase, driversBody);
  addEx("CM change order increase (top lines)", ex.cm_co_increase, driversBody);
  driversDet.appendChild(driversS);
  driversDet.appendChild(driversBody);
  box.appendChild(driversDet);

  const drillDet = document.createElement("details");
  drillDet.className = "details-panel disclosure-panel mom-drill-outer";
  const drillS = document.createElement("summary");
  drillS.textContent = "Row-level drill (precomputed; all lines) — display only";
  const drillInner = document.createElement("div");
  drillInner.className = "details-inner";
  const wrap = document.createElement("div");
  wrap.className = "mom-drill-wrap";
  const rt = document.createElement("table");
  rt.className = "mom-drill-table data-table";
  rt.setAttribute("aria-label", "February to March row-level comparison");
  const rthead = document.createElement("thead");
  const rthr = document.createElement("tr");
  [
    "section",
    "kind",
    "raw",
    "display",
    "name",
    "role",
    "namespace",
    "Feb UCB",
    "Mar UCB",
    "delta",
    "Feb row",
    "Mar row",
  ].forEach((t) => {
    const c = document.createElement("th");
    c.textContent = t;
    rthr.appendChild(c);
  });
  rthead.appendChild(rthr);
  rt.appendChild(rthead);
  const rtb = document.createElement("tbody");
  (mom.row_drill || []).forEach((r) => {
    const tr = document.createElement("tr");
    const cells = [
      r.section,
      r.change_kind,
      r.raw_cost_code,
      r.display_cost_code,
      r.cost_code_name,
      r.component_role,
      r.cost_code_namespace,
      r.update_current_budget_feb,
      r.update_current_budget_mar,
      r.delta_ucb,
      r.excel_row_feb,
      r.excel_row_mar,
    ];
    cells.forEach((v, j) => {
      const td = document.createElement("td");
      if (j === 7 || j === 8 || j === 9) {
        td.textContent = v == null ? "—" : fmtUsd(v);
      } else {
        td.textContent = v == null || v === "" ? "—" : String(v);
      }
      tr.appendChild(td);
    });
    rtb.appendChild(tr);
  });
  rt.appendChild(rtb);
  wrap.appendChild(rt);
  drillInner.appendChild(wrap);
  drillDet.appendChild(drillS);
  drillDet.appendChild(drillInner);
  box.appendChild(drillDet);
  root.appendChild(box);
  return root;
}

function renderFinancialSignalsBlock(fs) {
  const host = document.getElementById("financial-signals");
  if (!host) return;
  host.innerHTML = "";
  host.removeAttribute("hidden");
  const sourceCollapse = document.getElementById("report-builder-source-collapse");
  if (sourceCollapse) {
    try {
      sourceCollapse.removeAttribute("open");
    } catch (e) {
      /* no-op */
    }
  }
  resetFinancialWbState();
  workbenchViewApi = null;
  const at = (fs && fs.analysis_type) || "";
  let wps = (fs && fs.workbook_profit_summary) || {};
  if (at === "trend_across_reports" && fs.multi_artifact) {
    wps = fs.multi_artifact.latest_workbook_profit_summary || wps;
  }
  const wb = fs && fs.financial_workbench;
  const cmpById = workbenchComponentMap(fs);

  const top = document.createElement("div");
  top.className = "signals-panel signals-panel-hero signals-hero";
  const heroHead = document.createElement("div");
  heroHead.className = "signals-hero-head";
  const heroTitle = document.createElement("h3");
  heroTitle.className = "signals-heading signals-hero-title";
  heroTitle.textContent = "Projected profit";
  const heroK = document.createElement("p");
  heroK.className = "signals-hero-kicker";
  heroK.textContent = "Formula result · workbook check · interpretation";
  heroHead.appendChild(heroTitle);
  heroHead.appendChild(heroK);
  const vRaw = wps.projected_profit_variance;
  const vNum = vRaw != null && vRaw !== "" ? Number(vRaw) : NaN;
  const heroGrid = document.createElement("div");
  heroGrid.className = "signals-hero-grid";
  const tppR = document.createElement("div");
  tppR.className = "signals-hero-primary";
  tppR.setAttribute("role", "group");
  tppR.setAttribute("aria-label", "Total projected profit from formula");
  tppR.innerHTML =
    '<p class="signals-tpp-label">Total projected profit (formula)</p>' +
    `<p class="signals-tpp-value">${fmtUsd(wps.total_projected_profit)}</p>`;
  const heroSide = document.createElement("div");
  heroSide.className = "signals-hero-side";
  const wBook = document.createElement("p");
  wBook.className = "signals-hero-meta-line";
  wBook.textContent = "Workbook-reported TPP: " + fmtUsd(wps.workbook_reported_total_projected_profit);
  const vLine = document.createElement("p");
  vLine.className = "signals-hero-meta-line signals-hero-variance";
  if (Number.isFinite(vNum) && vNum !== 0) {
    vLine.classList.add("signals-variance--nonzero");
  } else {
    vLine.classList.add("signals-variance--zero", "subtle");
  }
  vLine.textContent = "Variance (formula vs workbook): " + fmtUsd(wps.projected_profit_variance);
  const interP = document.createElement("p");
  interP.className = "signals-hero-status";
  if (vRaw !== "" && Number.isFinite(vNum) && vNum !== 0) {
    interP.classList.add("signals-hero-status--warn");
    interP.textContent =
      "Headline gap — often legacy profit adjustments, mapping differences, or LRP treatment vs CMiC.";
  } else {
    interP.classList.add("signals-hero-status--ok");
    interP.textContent = "Workbook and formula are aligned on the headline; components below explain the build.";
  }
  heroSide.appendChild(wBook);
  heroSide.appendChild(vLine);
  heroSide.appendChild(interP);
  heroGrid.appendChild(tppR);
  heroGrid.appendChild(heroSide);
  const pl = wps.projected_profit_limitations;
  const ppDetails = document.createElement("details");
  ppDetails.className = "signals-inline-details signals-hero-footnote";
  const ppSum = document.createElement("summary");
  ppSum.textContent = "Source / extraction notes (evidence)";
  ppDetails.appendChild(ppSum);
  const ppBody = document.createElement("div");
  ppBody.className = "details-inner subtle small";
  ppBody.textContent =
    pl && pl.length ? pl.join(" ") : "Source: JTD + LBR + MoM sheets; limitations listed in extraction.";
  ppDetails.appendChild(ppBody);
  const hr = document.createElement("div");
  hr.className = "signals-divider";
  const compLabel = document.createElement("h4");
  compLabel.className = "signals-subh signals-hero-comp-label";
  compLabel.textContent = "Projected profit — components (click to filter workbench)";
  top.appendChild(heroHead);
  top.appendChild(heroGrid);
  top.appendChild(ppDetails);
  top.appendChild(hr);
  top.appendChild(compLabel);

  const compList = document.createElement("div");
  compList.className = "signals-cmp-list signals-metric-grid";
  const midRows = [
    { id: "cm_fee", label: "CM fee" },
    { id: "buyout_savings_realized", label: "Buyout savings" },
    { id: "budget_savings_overages", label: "Budget savings / overages" },
    { id: "pco_profit", label: "PCO profit" },
    { id: "labor_rate_profit_to_date", label: "Labor rate profit" },
    { id: "prior_system_profit", label: "Prior-system profit" },
  ];
  const wKey = {
    cm_fee: "cm_fee",
    buyout_savings_realized: "buyout_savings_realized",
    budget_savings_overages: "budget_savings_overages",
    pco_profit: "pco_profit",
    labor_rate_profit_to_date: "labor_rate_profit_to_date",
    prior_system_profit: "prior_system_profit",
  };
  midRows.forEach((mr) => {
    const wk = wKey[mr.id];
    const val = wk ? wps[wk] : null;
    const row = document.createElement("div");
    row.className = "metric-tile-row cmp-row";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "cmp-toggle metric-tile";
    const ctxId = "cmp-ctx-" + mr.id;
    btn.setAttribute("aria-describedby", ctxId);
    const t1 = document.createElement("span");
    t1.className = "cmp-lab metric-tile-label";
    t1.textContent = mr.label;
    const t2 = document.createElement("span");
    t2.className = "cmp-val metric-tile-value";
    t2.textContent = fmtUsd(val);
    btn.appendChild(t1);
    btn.appendChild(t2);
    const ctx = document.createElement("p");
    ctx.id = ctxId;
    ctx.className = "cmp-wb-ctx metric-tile-hint";
    ctx.textContent = profitComponentWorkbenchSummary(wb, mr.id);
    const src = cmpById[mr.id];
    const more = document.createElement("details");
    more.className = "cmp-row-source";
    const moreS = document.createElement("summary");
    moreS.className = "subtle small cmp-row-source-summary";
    moreS.textContent = "Extraction line evidence (optional)";
    const moreB = document.createElement("div");
    moreB.className = "cmp-row-source-body";
    if (src) {
      const inner = document.createElement("div");
      inner.className = "cmp-panel";
      inner.appendChild(renderComponentDrilldown(src, fmtUsd));
      moreB.appendChild(inner);
    } else {
      const ph = document.createElement("p");
      ph.className = "subtle small";
      ph.textContent = "No line-level drill for this component.";
      moreB.appendChild(ph);
    }
    more.appendChild(moreS);
    more.appendChild(moreB);
    row.appendChild(btn);
    row.appendChild(ctx);
    row.appendChild(more);
    btn.addEventListener("click", (ev) => {
      ev.preventDefault();
      if (workbenchViewApi) {
        workbenchViewApi.applyComponentLink(mr.id);
      } else {
        const bench = document.querySelector(".financial-workbench");
        if (bench) {
          bench.scrollIntoView({ block: "start", behavior: "smooth" });
        }
      }
    });
    compList.appendChild(row);
  });
  top.appendChild(compList);
  const fwbWorkspace = document.createElement("div");
  fwbWorkspace.className = "signals-fwb-workspace";
  const fwbHero = document.createElement("div");
  fwbHero.className = "signals-fwb-hero";
  fwbHero.appendChild(top);

  const dl2 = document.createElement("dl");
  dl2.className = "signals-dl";
  [
    ["Billed to date", wps.lrp_billed_to_date],
    ["Actual cost", wps.lrp_actual_cost],
    ["LRP to date", wps.labor_rate_profit_to_date],
  ].forEach(([a, b]) => {
    const dt = document.createElement("dt");
    dt.textContent = a;
    const dd = document.createElement("dd");
    dd.textContent = fmtUsd(b);
    dl2.appendChild(dt);
    dl2.appendChild(dd);
  });

  const lbrSec = document.createElement("section");
  lbrSec.className = "analysis-section-card";
  const lbrH = document.createElement("h3");
  lbrH.className = "analysis-section-title";
  lbrH.textContent = "Labor rate profit";
  const lbrLede = document.createElement("p");
  lbrLede.className = "analysis-section-lede";
  lbrLede.textContent =
    "Billed " +
    fmtUsd(wps.lrp_billed_to_date) +
    " · actual " +
    fmtUsd(wps.lrp_actual_cost) +
    " · LRP to date " +
    fmtUsd(wps.labor_rate_profit_to_date);
  lbrSec.appendChild(lbrH);
  lbrSec.appendChild(lbrLede);
  const lbrD = document.createElement("details");
  lbrD.className = "details-panel disclosure-panel signals-secondary-collapse";
  const lbrS = document.createElement("summary");
  lbrS.className = "signals-secondary-summary";
  lbrS.textContent = "LRP line detail & workbench (evidence)";
  const lbrI = document.createElement("div");
  lbrI.className = "details-inner";
  const lbrInner = document.createElement("div");
  lbrInner.className = "signals-panel-inset";
  lbrInner.appendChild(dl2);
  if (financialWorkbenchHasUsefulData(wb)) {
    const toL = document.createElement("button");
    toL.type = "button";
    toL.className = "workbench-skip-link";
    toL.textContent = "Open LRP in workbench";
    toL.addEventListener("click", () => {
      if (workbenchViewApi) {
        workbenchViewApi.applyComponentLink("labor_rate_profit_to_date");
      }
    });
    lbrInner.appendChild(toL);
  }
  lbrI.appendChild(lbrInner);
  lbrD.appendChild(lbrS);
  lbrD.appendChild(lbrI);
  lbrSec.appendChild(lbrD);

  const dl3 = document.createElement("dl");
  dl3.className = "signals-dl";
  [
    ["Owner change orders (count)", wps.owner_change_orders_count],
    ["Owner change orders (value)", wps.owner_change_orders_value],
    ["CM change orders (count)", wps.cm_change_orders_count],
    ["CM change orders (value)", wps.cm_change_orders_value],
  ].forEach(([a, b]) => {
    const dt = document.createElement("dt");
    dt.textContent = a;
    const dd = document.createElement("dd");
    dd.textContent = a.indexOf("count") >= 0 ? String(b) : fmtUsd(b);
    dl3.appendChild(dt);
    dl3.appendChild(dd);
  });
  const csn = wps.change_order_source_notes;
  const coDetails = document.createElement("details");
  coDetails.className = "signals-inline-details";
  const coSum = document.createElement("summary");
  coSum.textContent = "Source notes (evidence)";
  coDetails.appendChild(coSum);
  const coBody = document.createElement("div");
  coBody.className = "details-inner subtle small";
  coBody.textContent =
    csn && csn.length
      ? csn.join(" ")
      : (wps.jtd_profit_extraction && wps.jtd_profit_extraction.change_order_source_notes) || "See JTD extract.";
  coDetails.appendChild(coBody);
  const ownN = wps.owner_change_orders_count;
  const cmN = wps.cm_change_orders_count;
  const coSec = document.createElement("section");
  coSec.className = "analysis-section-card";
  const coH = document.createElement("h3");
  coH.className = "analysis-section-title";
  coH.textContent = "Change orders (impact)";
  const coLede = document.createElement("p");
  coLede.className = "analysis-section-lede";
  coLede.textContent =
    "Owner " +
    (ownN != null ? String(ownN) : "—") +
    " / CM " +
    (cmN != null ? String(cmN) : "—") +
    " lines · " +
    fmtUsd(wps.owner_change_orders_value) +
    " owner · " +
    fmtUsd(wps.cm_change_orders_value) +
    " CM";
  coSec.appendChild(coH);
  coSec.appendChild(coLede);
  const coD = document.createElement("details");
  coD.className = "details-panel disclosure-panel signals-secondary-collapse";
  const coS = document.createElement("summary");
  coS.className = "signals-secondary-summary";
  coS.textContent = "CO line detail, notes & workbench (evidence)";
  const coI = document.createElement("div");
  coI.className = "details-inner";
  const coInner = document.createElement("div");
  coInner.className = "signals-panel-inset";
  coInner.appendChild(dl3);
  coInner.appendChild(coDetails);
  if (financialWorkbenchHasUsefulData(wb)) {
    const toC = document.createElement("button");
    toC.type = "button";
    toC.className = "workbench-skip-link";
    toC.textContent = "Open change orders in workbench";
    toC.addEventListener("click", () => {
      if (workbenchViewApi) {
        workbenchViewApi.applyComponentLink("change_orders");
      }
    });
    coInner.appendChild(toC);
  }
  coI.appendChild(coInner);
  coD.appendChild(coS);
  coD.appendChild(coI);
  coSec.appendChild(coD);

  const analysisStack = document.createElement("div");
  analysisStack.className = "signals-analysis-stack";
  analysisStack.appendChild(lbrSec);
  analysisStack.appendChild(coSec);

  const mom = fs.mom_219128_feb_mar;
  const momBlock = mom ? renderMom219128Block(mom) : null;

  const fwbBench = document.createElement("div");
  fwbBench.className = "signals-fwb-bench";
  const wbPayload = fs && fs.financial_workbench;
  if (wbPayload != null && typeof wbPayload === "object" && financialWorkbenchHasUsefulData(wbPayload)) {
    const wbEl = renderFinancialWorkbench(wbPayload, wps);
    if (wbEl) {
      const wbDet = document.createElement("details");
      wbDet.className = "details-panel disclosure-panel signals-fwb-details";
      const wbSum = document.createElement("summary");
      wbSum.className = "signals-fwb-details-summary";
      wbSum.textContent = "Financial workbench (evidence) — JTD cost codes, change orders, LRP, reconciliation";
      const wbIn = document.createElement("div");
      wbIn.className = "details-inner signals-fwb-details-inner";
      wbIn.appendChild(wbEl);
      wbDet.appendChild(wbSum);
      wbDet.appendChild(wbIn);
      fwbBench.appendChild(wbDet);
    }
  } else {
    const ph = document.createElement("p");
    ph.className = "subtle small fwb-bench-unavailable";
    ph.textContent = "Workbench data is not available for this analysis type.";
    fwbBench.appendChild(ph);
  }

  fwbWorkspace.appendChild(fwbHero);
  fwbWorkspace.appendChild(analysisStack);
  if (momBlock) fwbWorkspace.appendChild(momBlock);
  fwbWorkspace.appendChild(fwbBench);
  host.appendChild(fwbWorkspace);

  if (at === "cost_movement_signals" || at === "compare_two_reports") {
    const mv = document.createElement("div");
    mv.className = "signals-panel";
    const h = document.createElement("h3");
    h.className = "signals-heading";
    h.textContent = "Cost / movement (two reports)";
    mv.appendChild(h);
    const ul = document.createElement("ul");
    ul.className = "assistant-response-list";
    (fs.largest_movers || []).slice(0, 8).forEach((m) => {
      const li = document.createElement("li");
      li.textContent = (m.label || m.key) + " · " + fmtUsd(m.delta);
      ul.appendChild(li);
    });
    mv.appendChild(ul);
    host.appendChild(mv);
  }

  if (at === "trend_across_reports" && fs.multi_period_delta) {
    const tr = document.createElement("div");
    tr.className = "signals-panel";
    tr.innerHTML = "<h3 class=\"signals-heading\">Trend and cost impact</h3>";
    const ax = (fs.multi_period_delta.action_view) || {};
    const addList = (title, key) => {
      const s = document.createElement("h4");
      s.className = "signals-subh";
      s.textContent = title;
      tr.appendChild(s);
      const u = document.createElement("ul");
      u.className = "assistant-response-list";
      (ax[key] || []).forEach((it) => {
        const li = document.createElement("li");
        li.textContent = it.label || it.line || JSON.stringify(it);
        u.appendChild(li);
      });
      tr.appendChild(u);
    };
    addList("Largest movers (cumulative)", "top_issues");
    addList("New this period", "new_this_period");
    addList("Repeated / ongoing", "ongoing_risks");
    addList("Watchlist", "watchlist");
    host.appendChild(tr);
  }

  const lim = document.createElement("details");
  lim.className = "details-panel disclosure-panel signals-limits";
  lim.innerHTML = "<summary>Source notes / limitations</summary><div class=\"details-inner\" id=\"signals-limits-body\"></div>";
  host.appendChild(lim);
  const lb = document.getElementById("signals-limits-body");
  if (lb) {
    const p = document.createElement("p");
    p.className = "subtle";
    p.textContent =
      "JTD, LBR, and MoM layouts vary by workbook age. Unmapped footers, missing MoM, or N-prefix codes on non-219128 projects are called out in backend limitations.";
    lb.appendChild(p);
  }
}
