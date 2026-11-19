# Step decoys: Tau Retail review notes and findings

Review material for the Tau Retail step-decoy releases generated on 2026-11-18
with `agentrx.rewordings.step_decoy` (Claude Haiku, Sonnet and Opus 5.5 at
medium effort, one call per trajectory).

| File | Contents |
|---|---|
| [findings.md](findings.md) | Cross-model analysis: volume, targets, placement, agreement, errors, cost, and the trajectory 31 case study |
| `review_sheets/<model>-medium.md` | Per-trajectory review sheet: root failure, model rationale, each decoy, automatic checks and the suggested decision |
| `reviews/<model>-medium.json` | Signed reviews used for release (review-sheet suggestions adopted, reviewer Aparna Shree) |

Releases built from these reviews:

| Model | Release | Trajectories |
|---|---|---|
| Haiku | [`tau_retail/step_decoy/haiku/v0.1.0`](../../../../../data/benchmark_versions/tau_retail/step_decoy/haiku/v0.1.0/manifest.json) | 28 (28 rejected: stale replay) |
| Sonnet | [`tau_retail/step_decoy/sonnet/v0.1.0`](../../../../../data/benchmark_versions/tau_retail/step_decoy/sonnet/v0.1.0/manifest.json) | 28 (31 invalid) |
| Opus | [`tau_retail/step_decoy/opus/v0.1.0`](../../../../../data/benchmark_versions/tau_retail/step_decoy/opus/v0.1.0/manifest.json) | 27 (31 rejected: stale replay; 47 invalid) |

These are copies. The originals stay in the git-ignored work folders
`runs/decoy/tau/<model>-medium/`, which each release's `audit.json` cites. The
review decisions and reasons are also recorded in every `audit.json`.

The automatic flags in the review sheets come from Tau-specific tool-name rules
in a separate review script, not from the domain-general generator. Every flagged
case was checked by hand. The sheets' closing instruction to fill in
`reviews.json` has since been done; see `reviews/`.
