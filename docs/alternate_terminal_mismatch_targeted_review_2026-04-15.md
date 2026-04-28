# Alternate Terminal Mismatch Targeted Review (2026-04-15)

## Objective

Execute the recommended focused review on the first terminal set and highest-reach tasks, then package outputs for immediate schedule-review execution.

## Evidence Run

- Source view: `v_operator_path_comp_alt_terminal_mismatch_diag_current`
- Workshop export folder: `diagnostics/path_comparison/alternate_terminal_workshop_20260415T131522Z`
- Prior baseline folder: `diagnostics/path_comparison/alternate_terminal_mismatch_20260415T125809Z`

## Top Terminal Set Confirmed

First-pass terminal set remains:

- `37054`, `39146`, `45713`, `39160`, `45708`
- `37050`, `39283`, `39297`, `41355`, `41357`

Per-terminal workload split (same 10 terminals):

- normalization-candidate rows per terminal: `11`
- structural-candidate rows per terminal: `65` to `72`
- terminal-selection-policy rows: `0`

This indicates the same terminal neighborhood should be reviewed for both cleanup and structural validation.

## Highest-Priority Task Targets

Top tasks (all touching all 10 target terminals) include:

- `43882` Form Foundations (East #1) — reachable alternate count `123`
- `52902` Array Lower Tiebacks — `123`
- `43885` Form Foundations (East #2) — `121`
- `43888` Form Foundations (East #3) — `120`
- `43891` Form Foundations (East #4) — `119`
- `43836` Form Foundations (North #1) — `116` (normalization candidate)

The highest-reach rows are concentrated in East/North foundations and upstream framing/decking sequences, not spread randomly.

## Normalization Cleanup Targets (11 rows)

Normalization candidates still show parse/reference ambiguity concentrated in this same terminal neighborhood, led by:

- `43836` Form Foundations (North #1): `missing_reference_count=2`
- `44283` Frame P7: `missing_reference_count=1`
- `15995` CFMF & Versa Decking: `missing_reference_count=1`
- `15987` CFMF & Versa Decking: `missing_reference_count=1`, `ambiguous_reference_count=1`
- `15713` CFMF & Versa Decking: `ambiguous_reference_count=2`
- `15980` Prep & Pour Slab on Deck & Beton Walls: `ambiguous_reference_count=1`, `self_loop_count=1`

## Immediate Review Plan

1. **Cleanup pass first (11 rows):** resolve missing/ambiguous references and self-loop artifacts.
2. **Recompute/reload diagnostics after cleanup:** regenerate the same two evidence folders and compare terminal frequencies.
3. **Structural validation pass (remaining rows):** if concentration remains on the same 10 terminals, treat as true alternate finish-chain structure and review intended terminal-selection strategy.

## Export Files Produced In This Step

- `top_terminal_signal_matrix.csv`
- `high_priority_task_target_list.csv`
- `normalization_cleanup_targets.csv`
