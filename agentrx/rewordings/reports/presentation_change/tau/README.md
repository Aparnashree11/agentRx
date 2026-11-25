# Presentation change: Tau Retail review notes and findings

Review material for the Tau Retail presentation-change releases generated with
`agentrx.rewordings.presentation_change` (Claude Haiku, Sonnet and Opus 5.5 at
medium effort, one call per trajectory).

| File | Contents |
|---|---|
| [findings.md](findings.md) | Cross-model analysis: volume, edit kinds, regenerations, errors, cost, and the per-model results |
| `review_sheets/<model>-medium.md` | Per-trajectory review sheet: root failure, model rationale, each change with its automatic checks, and the full before/after of every prose edit (no suggested decision — the reviewer reads each change) |
| `reviews/<model>-medium.json` | Signed reviews used for release (reviewer Uzma Fatima) |

Releases built from these reviews:

| Model | Release | Trajectories |
|---|---|---|
| Haiku | [`tau_retail/presentation_change/haiku/v0.1.0`](../../../../../data/benchmark_versions/tau_retail/presentation_change/haiku/v0.1.0/manifest.json) | 29 / 29 |
| Sonnet | [`tau_retail/presentation_change/sonnet/v0.1.0`](../../../../../data/benchmark_versions/tau_retail/presentation_change/sonnet/v0.1.0/manifest.json) | 28 / 29 (task 28 excluded at the attempt cap) |
| Opus | [`tau_retail/presentation_change/opus/v0.1.0`](../../../../../data/benchmark_versions/tau_retail/presentation_change/opus/v0.1.0/manifest.json) | 29 / 29 |

These are copies. The originals stay in the git-ignored work folders
`runs/presentation_change/tau/<model>-medium/`, which each release's `audit.json`
cites. The review decisions and reasons are also recorded in every `audit.json`,
along with each excluded case and its reason.

Unlike the step-decoy sheets, the presentation-change review sheet suggests no
decision: Python has already checked structure and values (locked steps, tool
names, call IDs, JSON values, every digit token, and that emphasis only adds
markdown), so the review is about meaning — each paraphrase must say exactly what
the original said, and every annotated failure must stay exactly as clear and as
wrong. Prose edits are shown before and after in full, and edits on annotated
failure steps are flagged with ⚠. Each review names the exact `events_sha256` it
approved, so a review written before a regeneration is stale and refused at
release.
