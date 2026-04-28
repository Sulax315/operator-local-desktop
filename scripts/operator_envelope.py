from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ENVELOPE_VERSION = "1.0.0"

REQUIRED_MARKDOWN_SECTIONS = [
    "## What I did",
    "## What I found",
    "## What I created",
    "## What needs review",
    "## Next actions",
]

REQUIRED_JSON_KEYS = [
    "envelope_version",
    "what_i_did",
    "what_i_found",
    "what_i_created",
    "what_needs_review",
    "next_actions",
    "run",
]


@dataclass(frozen=True)
class OperatorEnvelope:
    envelope_version: str
    what_i_did: list[str]
    what_i_found: list[str]
    what_i_created: list[dict[str, str]]
    what_needs_review: list[str]
    next_actions: list[str]
    run: dict[str, Any]

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "envelope_version": self.envelope_version,
            "what_i_did": list(self.what_i_did),
            "what_i_found": list(self.what_i_found),
            "what_i_created": list(self.what_i_created),
            "what_needs_review": list(self.what_needs_review),
            "next_actions": list(self.next_actions),
            "run": self.run,
        }

    def to_markdown(self) -> str:
        created_lines: list[str] = []
        for item in self.what_i_created:
            path = item.get("path", "")
            desc = item.get("description", "")
            created_lines.append(f"- `{path}` — {desc}")
        created_body = "\n".join(created_lines) if created_lines else "- (none)"

        if not self.run:
            raise ValueError("OperatorEnvelope requires run linkage")
        rid = self.run.get("run_id", "")
        mpath = self.run.get("manifest_path", "")
        run_line = f"- run_id: `{rid}`\n- manifest: `{mpath}`\n"

        return "\n".join(
            [
                "# Operator Response",
                "",
                "## What I did",
                "\n".join(f"- {x}" for x in self.what_i_did) if self.what_i_did else "- (none)",
                "",
                "## What I found",
                "\n".join(f"- {x}" for x in self.what_i_found) if self.what_i_found else "- (none)",
                "",
                "## What I created",
                created_body,
                "",
                "## What needs review",
                "\n".join(f"- {x}" for x in self.what_needs_review) if self.what_needs_review else "- (none)",
                "",
                "## Next actions",
                "\n".join(f"- {x}" for x in self.next_actions) if self.next_actions else "- (none)",
                "",
                "## Run linkage",
                run_line,
            ]
        ).rstrip() + "\n"


def build_envelope(
    *,
    what_i_did: list[str],
    what_i_found: list[str],
    what_i_created: list[dict[str, str]],
    what_needs_review: list[str],
    next_actions: list[str],
    run: dict[str, Any],
) -> OperatorEnvelope:
    return OperatorEnvelope(
        envelope_version=ENVELOPE_VERSION,
        what_i_did=list(what_i_did),
        what_i_found=list(what_i_found),
        what_i_created=list(what_i_created),
        what_needs_review=list(what_needs_review),
        next_actions=list(next_actions),
        run=run,
    )


def validate_envelope_json(payload: dict[str, Any]) -> None:
    for key in REQUIRED_JSON_KEYS:
        if key not in payload:
            raise ValueError(f"Envelope JSON missing key: {key}")

    if str(payload.get("envelope_version", "")) != ENVELOPE_VERSION:
        raise ValueError("Envelope JSON envelope_version mismatch")

    for field in ["what_i_did", "what_i_found", "what_needs_review", "next_actions"]:
        if not isinstance(payload.get(field), list):
            raise ValueError(f"Envelope JSON field must be a list: {field}")
        if not all(isinstance(x, str) for x in payload[field]):
            raise ValueError(f"Envelope JSON list must contain only strings: {field}")

    created = payload.get("what_i_created")
    if not isinstance(created, list):
        raise ValueError("Envelope JSON what_i_created must be a list")
    for item in created:
        if not isinstance(item, dict):
            raise ValueError("Envelope JSON what_i_created items must be objects")
        if "path" not in item or "description" not in item:
            raise ValueError("Envelope JSON what_i_created items require path+description")
        if not isinstance(item["path"], str) or not isinstance(item["description"], str):
            raise ValueError("Envelope JSON what_i_created path/description must be strings")

    run = payload.get("run")
    if run is None:
        raise ValueError("Envelope JSON run must be present")
    if not isinstance(run, dict):
        raise ValueError("Envelope JSON run must be an object")
    for rk in ["run_id", "manifest_path"]:
        if rk not in run or not isinstance(run[rk], str) or not run[rk]:
            raise ValueError(f"Envelope JSON run missing string field: {rk}")


def validate_envelope_markdown(text: str) -> None:
    for heading in REQUIRED_MARKDOWN_SECTIONS:
        if heading not in text:
            raise ValueError(f"Envelope markdown missing section: {heading}")

    # Minimal structural guard: each required section should have some content after it.
    # We keep this intentionally lightweight; JSON is the strict contract.
    for heading in REQUIRED_MARKDOWN_SECTIONS:
        idx = text.find(heading)
        if idx < 0:
            continue
        after = text[idx + len(heading) :]
        if not after.strip():
            raise ValueError(f"Envelope markdown section empty: {heading}")


def write_envelope_artifacts(run_dir: Path, envelope: OperatorEnvelope) -> dict[str, str]:
    json_path = run_dir / "outputs" / "operator_envelope.json"
    md_path = run_dir / "outputs" / "operator_envelope.md"

    json_obj = envelope.to_json_obj()
    validate_envelope_json(json_obj)

    md = envelope.to_markdown()
    validate_envelope_markdown(md)

    json_path.write_text(json.dumps(json_obj, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(md, encoding="utf-8")

    return {
        "json": str(json_path.resolve()),
        "markdown": str(md_path.resolve()),
    }


def read_envelope_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_envelope_files(run_dir: Path) -> None:
    json_path = run_dir / "outputs" / "operator_envelope.json"
    md_path = run_dir / "outputs" / "operator_envelope.md"
    if not json_path.exists():
        raise FileNotFoundError(f"Missing {json_path}")
    if not md_path.exists():
        raise FileNotFoundError(f"Missing {md_path}")

    payload = read_envelope_json(json_path)
    validate_envelope_json(payload)
    validate_envelope_markdown(md_path.read_text(encoding="utf-8"))


def contract_version_at_least(manifest: dict[str, Any], minimum: str) -> bool:
    return _semverish_tuple(str(manifest.get("contract_version", "0.0.0"))) >= _semverish_tuple(minimum)


def _semverish_tuple(value: str) -> tuple[int, int, int]:
    parts = (value or "").strip().split(".")
    nums: list[int] = []
    for part in parts[:3]:
        digits = "".join(ch for ch in part if ch.isdigit())
        nums.append(int(digits) if digits else 0)
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]
