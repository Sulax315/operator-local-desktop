# Global Operator Response Envelope (Phase 3 Control Objective)

## Problem statement

Run folders already enforce a strong artifact contract (`operator_summary.md` + trace + outputs).

The remaining architectural risk is drift in **non-run surfaces** (chat transcripts, tool outputs, UI panels) where behavior can become chat-like without durable artifacts.

## Objective

Define one mandatory response shape for **all operator-facing outputs**, regardless of surface:

- chat replies
- tool responses
- UI summaries
- email/draft outputs (when produced as operator output)

## Envelope (mandatory)

Every operator-facing response MUST include these sections, in this order:

1. **What I did**
2. **What I found**
3. **What I created** (explicit filesystem paths; use `none` if nothing)
4. **What needs review**
5. **Next actions**

## Machine-readable mirror (recommended)

For any automated channel, also emit a JSON object alongside the markdown:

Canonical implementation lives in `scripts/operator_envelope.py` (builder + validator + artifact writer).

```json
{
  "envelope_version": "1.0.0",
  "what_i_did": [],
  "what_i_found": [],
  "what_i_created": [{"path": "", "description": ""}],
  "what_needs_review": [],
  "next_actions": [],
  "run": {
    "run_id": "",
    "manifest_path": ""
  }
}
```

Rules:
- If work is run-scoped, `run.manifest_path` MUST point to `runs/{run_id}/manifest.json`.
- If work is not run-scoped, `run` may be null, but then `what_i_created` must still list any artifacts written.

## Enforcement placement (planned)

Phase 3 enforcement should exist at boundaries:

- CLI command wrappers
- local UI adapters
- any “operator agent” tool layer

Runs remain the audit system of record; the envelope ensures **everything outside runs** still remains reviewable and consistent.
