from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from operator_workflows.excel_financial_extractor import load_snapshot_json

# Frozen minimal contract for Phase 5 operational JSON outputs (see decision log).
PHASE5_OPERATIONAL_OUTPUT_SCHEMA = "1.0"

# Risk extraction: suppress heading-only / token-stutter noise; require signal of substance.
_RISKISH = re.compile(r"\b(risk|mitigation|threat|vulnerability|failure|blocker|issue)\b", re.IGNORECASE)
_ACTION_RISK_HINT = re.compile(
    r"(BLOCKER|\bRisk\s*:|\bCVE\b|\bSLA\b|\bbreach\b|\boutage\b|\bdeadline\b|\bEOD\b|\bmust\b)",
    re.IGNORECASE,
)

_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_FIN_WORDS_SOFT = re.compile(r"\b(budget|actual|delta|QoQ|YoY)\b", re.IGNORECASE)
_FIN_ANCHOR_WITH_DIGIT = re.compile(
    r"\b(revenue|margin|EBITDA|guidance|forecast|cash flow|AUM|debt)\b",
    re.IGNORECASE,
)
_COMPLETION_PERCENT_NOISE = re.compile(
    r"\b\d{1,3}\s*%\s*(?:complete|done|rolled out|shipped)\b",
    re.IGNORECASE,
)

# v3: primary queue requires finance-shaped numbers (under-report bias).
_PRIMARY_NUMBER_SIGNAL = re.compile(
    r"(?:\$\s*[\d,.]+|[\d,.]+\s*%|\d+(?:\.\d+)?\s*%)",
    re.IGNORECASE,
)
_SCALE_NUMBER_SIGNAL = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:[MmBb](?:\b|$)|million|billion|bn)\b",
    re.IGNORECASE,
)

_FIN_WORDS_WITH_DIGIT = re.compile(
    r"\b(revenue|EBITDA|gross margin|operating margin|net margin|guidance|forecast|variance|AUM|debt|P&L|"
    r"leverage|liquidity)\b",
    re.IGNORECASE,
)
# "Operating margin" has no `\b` before `margin`; require compound or explicit `margins`.
_MARGIN_COMPOUND = re.compile(r"\b(?:gross|operating|net)\s+margin\b|\bmargins\b", re.IGNORECASE)
_NARRATIVE_FIN_PRESSURE = re.compile(
    r"\b(?:gross|operating|net)\s+margin\b.*\b(compress(?:ed|ion)?|compression|pressure|expand|erosion|"
    r"deteriorat\w*|headwinds?|tailwinds?|tighten(?:ed|ing)?|ease[sd]?|recover(?:y|ed|ing)?)\b|"
    r"\b(profitability|leverage|liquidity)\b.*\b(compress(?:ed|ion)?|compression|pressure|expand|erosion|"
    r"deteriorat\w*|headwinds?|tailwinds?|tighten(?:ed|ing)?|ease[sd]?|recover(?:y|ed|ing)?)\b",
    re.IGNORECASE,
)
_METRIC_POLLUTION = re.compile(
    r"\b(NPS|CSAT|MTTR|MTTD|IOPS|PIPELINE|UPTIME|LATENCY|p\d\d|CPU|RAM)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class WorkflowContext:
    run_dir: Path
    inputs: list[Path]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _strip_markdown_links(text: str) -> str:
    """Remove `label`(url) link targets so `$` inside URLs does not read as money."""
    return _MD_LINK.sub(r"\1", text)


def _diff_heading_touch_count(diff_lines: list[str]) -> int:
    n = 0
    for ln in diff_lines:
        if not ln or ln.startswith("@@") or ln.startswith("\\"):
            continue
        if ln[:1] not in "+-":
            continue
        if ln.startswith("+++") or ln.startswith("---"):
            continue
        body = ln[1:].lstrip()
        if body.startswith("#"):
            n += 1
    return n


def _compare_significance_tier(*, diff_empty: bool, hunk_changes: int, unified_chars: int) -> str:
    if diff_empty:
        return "none"
    if hunk_changes > 40 or unified_chars > 20000:
        return "large"
    if hunk_changes > 10 or unified_chars > 6000:
        return "medium"
    return "small"


def _risk_triage(line: str) -> str:
    if _ACTION_RISK_HINT.search(line):
        return "action_needed"
    if re.search(r"\bRisk\s*:", line, re.IGNORECASE) or re.search(r"\*\*Risk\*\*\s*:", line, re.IGNORECASE):
        return "action_needed"
    return "informational"


def _has_finance_shaped_number(vis: str) -> bool:
    return bool(_PRIMARY_NUMBER_SIGNAL.search(vis) or _SCALE_NUMBER_SIGNAL.search(vis))


def _financial_raw_score_v3(vis: str) -> int:
    """Composite materiality score (v3). Values <3 are dropped from both primary and audit queues."""
    if _COMPLETION_PERCENT_NOISE.search(vis) and not _FIN_ANCHOR_WITH_DIGIT.search(vis):
        return 0
    if _METRIC_POLLUTION.search(vis) and not _FIN_WORDS_WITH_DIGIT.search(vis):
        return 0
    score = 0
    pn = _has_finance_shaped_number(vis)
    if pn:
        score += 5
    if _FIN_WORDS_WITH_DIGIT.search(vis) or _MARGIN_COMPOUND.search(vis):
        score += 3 if pn else 1
    if _FIN_WORDS_SOFT.search(vis) and pn:
        score += 2
    if _NARRATIVE_FIN_PRESSURE.search(vis):
        score += 3
    return score


def _financial_primary_eligible(raw: int, vis: str) -> bool:
    """Confidence floor: primary queue favors money/units or strong word+number reinforcement."""
    if raw < 3:
        return False
    if _has_finance_shaped_number(vis):
        return True
    if raw >= 6 and (_FIN_WORDS_WITH_DIGIT.search(vis) or _MARGIN_COMPOUND.search(vis)):
        return True
    return False


def _financial_primary_tier(raw: int) -> str:
    if raw >= 8:
        return "high"
    if raw >= 6:
        return "medium"
    return "low"


def _fmt_money(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.0f}"


def _tier_from_abs_delta(abs_delta: float, max_abs: float) -> str:
    if max_abs <= 0:
        return "low"
    ratio = abs_delta / max_abs
    if ratio >= 0.6:
        return "high"
    if ratio >= 0.3:
        return "medium"
    return "low"


def _rollup_extraction_confidence(left_snapshot: dict, right_snapshot: dict) -> dict[str, Any]:
    pe = left_snapshot.get("extraction") if isinstance(left_snapshot.get("extraction"), dict) else {}
    ce = right_snapshot.get("extraction") if isinstance(right_snapshot.get("extraction"), dict) else {}
    rank = {"high": 2, "medium": 1, "low": 0}
    pr = str(pe.get("confidence", "low")).lower()
    cr = str(ce.get("confidence", "low")).lower()
    rollup_idx = min(rank.get(pr, 0), rank.get(cr, 0))
    rollup = {2: "high", 1: "medium", 0: "low"}[rollup_idx]
    return {"prior": pe, "current": ce, "rollup": rollup}


def _category_label(left_snapshot: dict, right_snapshot: dict, key_lower: str) -> str:
    for snap in (left_snapshot, right_snapshot):
        for row in snap.get("categories", []):
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "")).strip()
            if name.lower() == key_lower:
                return name
    return key_lower


def _financial_structured_delta(left: Path, right: Path, left_snapshot: dict, right_snapshot: dict) -> dict:
    left_summary = left_snapshot.get("summary", {}) if isinstance(left_snapshot.get("summary"), dict) else {}
    right_summary = right_snapshot.get("summary", {}) if isinstance(right_snapshot.get("summary"), dict) else {}

    summary_deltas: dict[str, float] = {}
    for k in ("revenue", "cost", "profit"):
        lv = left_summary.get(k)
        rv = right_summary.get(k)
        if isinstance(lv, (int, float)) and isinstance(rv, (int, float)):
            summary_deltas[k] = float(rv) - float(lv)

    left_cats = {
        str(row.get("name", "")).strip().lower(): float(row.get("value", 0.0))
        for row in left_snapshot.get("categories", [])
        if isinstance(row, dict) and str(row.get("name", "")).strip() and isinstance(row.get("value"), (int, float))
    }
    right_cats = {
        str(row.get("name", "")).strip().lower(): float(row.get("value", 0.0))
        for row in right_snapshot.get("categories", [])
        if isinstance(row, dict) and str(row.get("name", "")).strip() and isinstance(row.get("value"), (int, float))
    }
    all_keys = sorted(set(left_cats.keys()) | set(right_cats.keys()))

    deltas: list[tuple[str, float]] = []
    for key in all_keys:
        dv = right_cats.get(key, 0.0) - left_cats.get(key, 0.0)
        if abs(dv) > 0:
            deltas.append((key, dv))
    deltas.sort(key=lambda x: abs(x[1]), reverse=True)

    max_abs = max((abs(v) for _, v in deltas), default=0.0)
    primary_threshold = max(10000.0, max_abs * 0.12) if max_abs > 0 else 10000.0
    primary_rows = [(name, d) for name, d in deltas if abs(d) >= primary_threshold][:200]
    audit_rows = [(name, d) for name, d in deltas if abs(d) < primary_threshold][:80]

    def _row_item(name: str, delta: float, *, audit: bool) -> dict:
        prior_v = left_cats.get(name, 0.0)
        curr_v = right_cats.get(name, 0.0)
        label = _category_label(left_snapshot, right_snapshot, name)
        item = {
            "category": name,
            "category_label": label,
            "prior_value": prior_v,
            "current_value": curr_v,
            "delta": delta,
            "text": f"{label}: {_fmt_money(delta)}",
            "score": int(round(abs(delta))),
        }
        if audit:
            item["tier"] = "audit"
        else:
            item["tier"] = _tier_from_abs_delta(abs(delta), max_abs)
        return item

    primary_items = [_row_item(name, d, audit=False) for name, d in primary_rows]
    audit_items = [_row_item(name, d, audit=True) for name, d in audit_rows]

    report_lines = [
        "# Financial Delta (structured intake)",
        "",
        f"- Prior / left: `{left}`",
        f"- Current / right: `{right}`",
        "- Signal pack: `financial_structured_v1` (Excel snapshot deltas by summary + categories).",
        "",
        "## Summary deltas",
        "",
    ]
    if summary_deltas:
        for k in ("revenue", "cost", "profit"):
            if k in summary_deltas:
                report_lines.append(f"- {k}: `{_fmt_money(summary_deltas[k])}`")
    else:
        report_lines.append("- (summary totals unavailable in extracted snapshots)")
    report_lines.extend(["", "## Primary material drivers", ""])
    if primary_items:
        for item in primary_items[:40]:
            report_lines.append(f"- [{item['tier']}] `{item['text']}`")
    else:
        report_lines.append("- (none)")
    report_lines.extend(["", "## Audit-only drivers", ""])
    if audit_items:
        for item in audit_items[:40]:
            report_lines.append(f"- [{item['score']}] `{item['text']}`")
    else:
        report_lines.append("- (none)")
    report_lines.append("")

    prior_wps = left_snapshot.get("workbook_profit_summary") if isinstance(left_snapshot, dict) else None
    current_wps = right_snapshot.get("workbook_profit_summary") if isinstance(right_snapshot, dict) else None
    wps_deltas: dict[str, float | None] = {}
    if isinstance(prior_wps, dict) and isinstance(current_wps, dict):
        for key in (
            "labor_rate_profit_to_date",
            "total_projected_profit",
            "cm_fee",
            "pco_profit",
            "buyout_savings_realized",
            "budget_savings_overages",
            "prior_system_profit",
        ):
            a, b = prior_wps.get(key), current_wps.get(key)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                wps_deltas[key] = float(b) - float(a)
            else:
                wps_deltas[key] = None

    structured = {
        "schema_version": PHASE5_OPERATIONAL_OUTPUT_SCHEMA,
        "workflow": "wf_financial_markdown_delta",
        "left": str(left.resolve()),
        "right": str(right.resolve()),
        "diff_empty": len(deltas) == 0,
        "material_diff_line_count": len(primary_items),
        "material_diff_lines": [x["text"] for x in primary_items],
        "material_diff_items": primary_items,
        "material_diff_audit_line_count": len(audit_items),
        "material_diff_audit_lines": [x["text"] for x in audit_items],
        "material_diff_audit_items": audit_items,
        "summary_deltas": summary_deltas,
        "prior_workbook_profit_summary": prior_wps if isinstance(prior_wps, dict) else {},
        "current_workbook_profit_summary": current_wps if isinstance(current_wps, dict) else {},
        "workbook_profit_summary_deltas": wps_deltas,
        "extraction_confidence": _rollup_extraction_confidence(left_snapshot, right_snapshot),
        "signal_pattern_id": "financial_markdown_v3",
    }
    return {
        "structured_output": structured,
        "structured_report_md": "\n".join(report_lines).strip() + "\n",
        "extra_outputs": {
            "outputs/diff.unified.diff": "\n".join(
                [f"- {name}: {left_cats.get(name, 0.0):.2f}" for name in sorted(left_cats.keys())]
                + [f"+ {name}: {right_cats.get(name, 0.0):.2f}" for name in sorted(right_cats.keys())]
            )
            + "\n",
            "outputs/intake.left.snapshot.json": json.dumps(left_snapshot, indent=2) + "\n",
            "outputs/intake.right.snapshot.json": json.dumps(right_snapshot, indent=2) + "\n",
        },
    }


def summarize_markdown(ctx: WorkflowContext) -> dict:
    if len(ctx.inputs) != 1:
        raise ValueError("wf_summarize_markdown requires exactly one input file path")

    src = ctx.inputs[0]
    text = _read_text(src)
    lines = [ln.rstrip() for ln in text.splitlines()]

    headings = [ln for ln in lines if ln.startswith("#")]
    bullets = [ln for ln in lines if ln.lstrip().startswith("- ")]

    summary_lines = []
    if headings:
        summary_lines.append("## Key headings")
        summary_lines.extend(headings[:12])
        summary_lines.append("")

    if bullets:
        summary_lines.append("## Key bullets")
        summary_lines.extend(bullets[:20])
        summary_lines.append("")

    summary_lines.append("## Executive summary")
    summary_lines.append(
        "This is a deterministic extractive summary generated without a local model. "
        "It prioritizes headings and bullet lists from the source document."
    )

    structured = {
        "schema_version": PHASE5_OPERATIONAL_OUTPUT_SCHEMA,
        "workflow": "wf_summarize_markdown",
        "input": str(src.resolve()),
        "stats": {"lines": len(lines), "chars": len(text)},
        "extracted": {"headings": headings[:25], "bullets": bullets[:40]},
    }

    return {
        "structured_output": structured,
        "structured_report_md": "\n".join(summary_lines).strip() + "\n",
    }


def compare_markdown(ctx: WorkflowContext) -> dict:
    if len(ctx.inputs) != 2:
        raise ValueError("wf_compare_markdown requires exactly two input file paths")

    left, right = ctx.inputs
    a = _read_text(left).splitlines(keepends=True)
    b = _read_text(right).splitlines(keepends=True)

    diff = difflib.unified_diff(
        a,
        b,
        fromfile=str(left.resolve()),
        tofile=str(right.resolve()),
        n=3,
    )
    diff_text = "".join(diff)
    diff_lines = diff_text.splitlines()
    hunk_change_lines = sum(
        1
        for ln in diff_lines
        if ln[:1] in "+-" and not ln.startswith("+++") and not ln.startswith("---")
    )
    heading_touch = _diff_heading_touch_count(diff_lines)
    sig_tier = _compare_significance_tier(
        diff_empty=diff_text.strip() == "",
        hunk_changes=hunk_change_lines,
        unified_chars=len(diff_text),
    )

    report_lines = [
        "# Deterministic Markdown Diff",
        "",
        f"- Left: `{left}`",
        f"- Right: `{right}`",
        "",
        "## Operator triage (deterministic)",
        "",
        f"- Diff significance tier: **{sig_tier}** (from hunk change count and diff size).",
        f"- Heading lines touched in diff (`#`…): **{heading_touch}**",
        f"- Hunk change lines: **{hunk_change_lines}** · Unified diff chars: **{len(diff_text)}**",
        "",
        "## Unified diff",
        "",
        "```diff",
        diff_text if diff_text.strip() else "(no textual differences detected)",
        "```",
        "",
    ]

    structured = {
        "schema_version": PHASE5_OPERATIONAL_OUTPUT_SCHEMA,
        "workflow": "wf_compare_markdown",
        "left": str(left.resolve()),
        "right": str(right.resolve()),
        "diff_empty": diff_text.strip() == "",
        "diff_line_count": len(diff_lines),
        "diff_hunk_change_line_count": hunk_change_lines,
        "unified_diff_chars": len(diff_text),
        "diff_heading_lines_changed": heading_touch,
        "diff_significance_tier": sig_tier,
    }

    return {
        "structured_output": structured,
        "structured_report_md": "\n".join(report_lines).strip() + "\n",
        "extra_outputs": {"outputs/diff.unified.diff": diff_text},
    }


def _risk_line_is_actionable(line: str) -> bool:
    """Filter noise: require keyword hit plus weak evidence of decision context."""
    stripped = line.strip()
    if len(stripped) < 14:
        return False
    if not _RISKISH.search(line):
        return False
    low = stripped.lower()
    # Heading-only stutter: "# Risk" or "## Blocker"
    if stripped.startswith("#") and len(stripped.split()) <= 3:
        return False
    words = stripped.split()
    if len(words) < 4 and not any(ch.isdigit() for ch in stripped) and ":" not in stripped:
        return False
    return True


def extract_risk_lines(ctx: WorkflowContext) -> dict:
    if len(ctx.inputs) != 1:
        raise ValueError("wf_extract_risk_lines requires exactly one input file path")

    src = ctx.inputs[0]
    text = _read_text(src)
    hits: list[dict] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if _risk_line_is_actionable(line):
            hits.append(
                {
                    "line": idx,
                    "text": line.rstrip(),
                    "category": "risk_signal",
                    "triage": _risk_triage(line),
                }
            )

    structured = {
        "schema_version": PHASE5_OPERATIONAL_OUTPUT_SCHEMA,
        "workflow": "wf_extract_risk_lines",
        "input": str(src.resolve()),
        "extraction_rules_id": "risk_lines_v2",
        "matches": hits[:200],
        "match_count": len(hits),
        "truncated": len(hits) > 200,
    }

    report_lines = [
        "# Deterministic Risk-ish Line Extraction",
        "",
        f"- Source: `{src}`",
        f"- Actionable matches: {len(hits)} (noise-filtered; see extraction_rules_id).",
        "",
        "## Review queue (first 50)",
        "",
        "These lines matched governance keywords **and** weak substance heuristics (length, heading guard, context).",
        "Each line includes deterministic triage: **action_needed** vs **informational**.",
        "",
    ]
    for item in hits[:50]:
        report_lines.append(f"- L{item['line']} [{item['triage']}]: {item['text']}")
    report_lines.append("")

    return {
        "structured_output": structured,
        "structured_report_md": "\n".join(report_lines).strip() + "\n",
    }


def financial_markdown_delta(ctx: WorkflowContext) -> dict:
    """Two-period markdown notes: unified diff + primary (high-confidence) vs audit-only queues (v3)."""
    if len(ctx.inputs) != 2:
        raise ValueError("wf_financial_markdown_delta requires exactly two input file paths")

    left, right = ctx.inputs
    left_snapshot = load_snapshot_json(left)
    right_snapshot = load_snapshot_json(right)
    if left_snapshot is not None and right_snapshot is not None:
        return _financial_structured_delta(left, right, left_snapshot, right_snapshot)

    a = _read_text(left).splitlines(keepends=True)
    b = _read_text(right).splitlines(keepends=True)
    diff = difflib.unified_diff(
        a,
        b,
        fromfile=str(left.resolve()),
        tofile=str(right.resolve()),
        n=3,
    )
    diff_text = "".join(diff)

    primary_rows: list[tuple[int, str, str]] = []
    audit_rows: list[tuple[int, str, str]] = []
    for ln in diff_text.splitlines():
        if not ln or ln.startswith("@@") or ln.startswith("\\"):
            continue
        if ln[:1] not in "+-":
            continue
        if ln.startswith("+++") or ln.startswith("---"):
            continue
        body = ln[1:]
        vis = _strip_markdown_links(body)
        raw = _financial_raw_score_v3(vis)
        if raw < 3:
            continue
        text = ln.rstrip("\n")
        if _financial_primary_eligible(raw, vis):
            tier = _financial_primary_tier(raw)
            primary_rows.append((raw, tier, text))
        else:
            audit_rows.append((raw, "audit", text))

    primary_rows.sort(key=lambda t: (-t[0], t[2]))
    audit_rows.sort(key=lambda t: (-t[0], t[2]))

    material_items = [
        {"text": row[2], "tier": row[1], "score": row[0]} for row in primary_rows[:200]
    ]
    material = [item["text"] for item in material_items]
    audit_items = [{"text": row[2], "tier": row[1], "score": row[0]} for row in audit_rows[:80]]
    audit_lines = [item["text"] for item in audit_items]

    report_lines = [
        "# Financial Markdown Delta (deterministic)",
        "",
        f"- Prior / left: `{left}`",
        f"- Current / right: `{right}`",
        "- Signal pack: `financial_markdown_v3` (confidence floor: primary vs audit-only).",
        "",
        "## Primary material (high confidence)",
        "",
    ]
    if material_items:
        for tier in ("high", "medium", "low"):
            bucket = [m for m in material_items if m["tier"] == tier]
            if not bucket:
                continue
            report_lines.append(f"### Tier: {tier}")
            report_lines.extend(f"- [{m['score']}] `{m['text']}`" for m in bucket[:40])
            report_lines.append("")
        if len(material_items) > 120:
            report_lines.append("- _Truncated in report view; JSON lists up to 200 primary rows._")
            report_lines.append("")
    else:
        report_lines.append("- _(none — under-reporting bias is intentional when signals are weak.)_")
        report_lines.append("")

    report_lines.extend(
        [
            "## Audit-only (low confidence)",
            "",
            "Borderline narrative or weak reinforcement. **Skim or ignore** unless you already care about the section.",
            "",
        ]
    )
    if audit_items:
        report_lines.extend(f"- [{m['score']}] `{m['text']}`" for m in audit_items[:50])
        report_lines.append("")
    else:
        report_lines.append("- _(none)_")
        report_lines.append("")

    report_lines.extend(
        [
            "## Full unified diff",
            "",
            "```diff",
            diff_text if diff_text.strip() else "(no textual differences detected)",
            "```",
            "",
        ]
    )

    structured = {
        "schema_version": PHASE5_OPERATIONAL_OUTPUT_SCHEMA,
        "workflow": "wf_financial_markdown_delta",
        "left": str(left.resolve()),
        "right": str(right.resolve()),
        "diff_empty": diff_text.strip() == "",
        "material_diff_line_count": len(material),
        "material_diff_lines": material,
        "material_diff_items": material_items,
        "material_diff_audit_line_count": len(audit_lines),
        "material_diff_audit_lines": audit_lines,
        "material_diff_audit_items": audit_items,
        "signal_pattern_id": "financial_markdown_v3",
    }

    return {
        "structured_output": structured,
        "structured_report_md": "\n".join(report_lines).strip() + "\n",
        "extra_outputs": {"outputs/diff.unified.diff": diff_text},
    }


WORKFLOW_HANDLERS = {
    "wf_summarize_markdown": summarize_markdown,
    "wf_compare_markdown": compare_markdown,
    "wf_extract_risk_lines": extract_risk_lines,
    "wf_financial_markdown_delta": financial_markdown_delta,
}


def run_named_workflow(name: str, ctx: WorkflowContext) -> dict:
    handler = WORKFLOW_HANDLERS.get(name)
    if handler is None:
        raise KeyError(f"Unknown workflow handler: {name}")
    return handler(ctx)
