# Step decomposition: Tau Retail review notes and findings

Review material for the Tau Retail step-decomposition releases generated on
2026-11-21 with `agentrx.rewordings.step_decomposition` (Claude Haiku, Sonnet and
Opus 5.5 at medium effort, one call per trajectory).

| File | Contents |
|---|---|
| [findings.md](findings.md) | Cross-model analysis: what was decomposed vs. declined, placement, agreement, errors, and cost |
| `review_sheets/<model>-medium.md` | Per-trajectory review sheet: root failure, model rationale, each smaller step, the automatic check and the suggested decision |
| `reviews/<model>-medium.json` | Signed reviews used for release (reviewer Pranudeep Metuku) |

Releases built from these reviews:

| Model | Release | Trajectories |
|---|---|---|
| Haiku | [`tau_retail/step_decomposition/haiku/v0.1.0`](../../../../../data/benchmark_versions/tau_retail/step_decomposition/haiku/v0.1.0/manifest.json) | 13 (13 declined, 2 invalid, 1 rejected) |
| Sonnet | [`tau_retail/step_decomposition/sonnet/v0.1.0`](../../../../../data/benchmark_versions/tau_retail/step_decomposition/sonnet/v0.1.0/manifest.json) | 14 (13 declined, 1 invalid, 1 rejected) |
| Opus | [`tau_retail/step_decomposition/opus/v0.1.0`](../../../../../data/benchmark_versions/tau_retail/step_decomposition/opus/v0.1.0/manifest.json) | 4 (25 declined) |

These are copies. The originals stay in the git-ignored work folders
`runs/decomp/tau/<model>-medium/`, which each release's `audit.json` cites. The
review decisions and reasons are also recorded in every `audit.json`.

The automatic flags in the review sheets come from a numeric-token heuristic in a
separate review script, not from the domain-general generator. It over-flags Tau
order IDs (the digits are glued to a `W` prefix, so the word-boundary check misses
them); every flagged case was checked by hand. The one genuine reject (task 31 in
neither model; task **59** in both Haiku and Sonnet) added a rationale the original
step did not contain. The sheets' suggestions were adopted in `reviews/` except for
those hand-corrected false flags.
