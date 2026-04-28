# RC1 Closeout Decision

Date: 2026-04-21
Status: **NOT READY TO TAG**

## Rationale

The release gate criteria are met for behavior and evidence:

- CLI is operator-usable for compare/risk/financial.
- Envelope summaries are workflow-specific and operator-grade.
- Full regression gate is green.
- Acceptance evidence (9 runs) is recorded.

However, RC tagging criteria require a clean working tree before applying `v1.0.0-rc1`.

## Required final action

1. Clean and commit the release-candidate state.
2. Apply annotated tag:
   - `git tag -a v1.0.0-rc1 -m "Operator Local v1.0.0-rc1"`
3. Record tag + commit hash in release notes.
