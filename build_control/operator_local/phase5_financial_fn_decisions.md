# Phase 5 Financial FN Audit Decisions

Date: 2026-04-21
Workflow: `wf_financial_markdown_delta`
Signal pack: `financial_markdown_v3`

## Purpose

False-negative audit pass on known and targeted adversarial corpus cases. Goal is to classify pattern classes, not to chase individual lines.

## Pattern Decisions

- **Primary (include as claim)**
  - Numeric revenue/margin movement (`$`, `%`, scaled numbers with finance anchors)
  - Numeric guidance band changes

- **Audit-only (capture as possibility)**
  - Margin-pressure narrative with no figures (for example: "Operating margin compressed ...")
  - Margin + YoY phrasing without figures

- **Ignore (intentionally excluded)**
  - Qualitative guidance phrasing with no figures (for example: "Guidance cut slightly ...")
  - Revenue headwinds language without quantified movement
  - Non-finance metric narrative (`NPS`, engagement) even with `%` and `YoY`

## Outcome

- False negatives are now classified into explicit pattern buckets with expected destination (`primary` / `audit` / `ignore`).
- No additional heuristic change required from this FN pass; stop condition reached for financial at current trust boundary.
