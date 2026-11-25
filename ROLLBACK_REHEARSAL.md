# Rollback rehearsal record

A rehearsal of the rollback procedure in [`RELEASE_PLAN.md`](RELEASE_PLAN.md) Section 4.
The rehearsal runs entirely in a throwaway clone under `/tmp` and never pushes; the
script is [`scripts/rollback_rehearsal.sh`](scripts/rollback_rehearsal.sh).

| Field | What was recorded |
|---|---|
| Date and time | 2026-11-24, 21:15:53–21:15:56 EST (before the merge at 21:34) |
| Run by | Pranudeep Metuku (rollback owner) |
| Current version | Rehearsed from `7016575` (pre-merge `main`). `main` is now `32ed483` (Merge PR #32 `framework-development`): `step-decomposition`, `step-decoy` and `baseline-results` merged; `presentation-change-v2` release data is on `main` unchanged, but 5 of its doc commits are not. `tau_retail` now holds `baseline` v1.0.0 plus 9 rewording releases (decomposition, decoy, presentation change × haiku/sonnet/opus), all v0.1.0. No `week11-release` tag yet. Judge version string: `gpt-6.1-sol` (Copilot CLI 1.0.102). |
| Target | `ac01913` / `tau_retail/baseline/v1.0.0`. Checkout succeeded; still reachable from `main` after the merge. |
| Time to switch | 1 s (step 1 to end of step 4, scripted); 2 s for the whole rehearsal |
| Steps done by hand | In the procedure: clearing `/tmp`, comparing numbers by eye, editing the README and changelog. Scripted in this rehearsal. |
| Known input → output | 29 trajectories, 3 sol runs → step 0.4138 ×3; category 0.3448 / 0.2759 / 0.3103. Read from the scorer's output files, not the headline. **Matched: yes.** |
| Problems found | 1. Rehearsed before the merge; the merge isn't tagged, so repeat from `week11-release`. 2. The reproducer hides scorer errors and reads fixed `/tmp` files: with the scorer deleted and stale files present, it printed the right numbers and exited 0. Still true on `32ed483`. 3. The headline line is hard-coded. 4. File paths at `ac01913` differ from `main` (`results/track_a/baseline/` vs `results/baseline/`); hashes match, so use the script at `ac01913`. 5. No previous version for single-release rollback (all nine releases are v0.1.0). 6. No changelog file at `main` or `ac01913`. 7. Only scoring is rolled back, not a live judge. 8. The judge version isn't pinned (`gpt-6.1-sol` only). Hash check worked: a 1-byte change aborted with `HASH CHECK FAILED`, exit 1. |
