# Step decomposition: Tau Retail review notes and findings

Review material for the Tau Retail step-decomposition releases generated on
2026-11-23 with `agentrx.rewordings.step_decomposition` (Claude Haiku, Sonnet and
Opus 5.5 at medium effort, one call per trajectory).

| File | Contents |
|---|---|
| [findings.md](findings.md) | Cross-model analysis: what was accepted vs. rejected, where the models agree, placement, and cost |
| `review_sheets/<model>-medium.md` | Per-trajectory review sheet: root step, annotated cause, each smaller step, and the decision with its reason |
| `reviews/<model>-medium.json` | Signed reviews used for release (reviewer Pranudeep Metuku) |

Releases built from these reviews:

| Model | Release | Accepted | Rejected |
|---|---|---|---|
| Haiku | [`tau_retail/step_decomposition/haiku/v0.1.0`](../../../../../data/benchmark_versions/tau_retail/step_decomposition/haiku/v0.1.0/manifest.json) | 16 | 13 |
| Sonnet | [`tau_retail/step_decomposition/sonnet/v0.1.0`](../../../../../data/benchmark_versions/tau_retail/step_decomposition/sonnet/v0.1.0/manifest.json) | 15 | 14 |
| Opus | [`tau_retail/step_decomposition/opus/v0.1.0`](../../../../../data/benchmark_versions/tau_retail/step_decomposition/opus/v0.1.0/manifest.json) | 15 | 14 |

With the clarified prompt every model proposes a decomposition for all 29
trajectories (no declines, no structurally invalid splits), so the spread is
entirely in review. Every rejection is a fabrication or a lost mistake, in one of
three groups:

- **Silent tool-call roots (12, rejected for every model):** tasks 12, 28, 31, 34,
  38, 41, 47, 72, 74, 98, 99, 105. These steps are a bare tool call with no agent
  text, so any "smaller steps" are narration the agent never produced.
- **Task 80 (rejected for every model):** the user's final turn ends with the
  `###STOP` marker that carries the annotated failure (premature termination); the
  splits drop it.
- **Task 59 (rejected for Sonnet and Opus only):** both invent a "within 5 days"
  rationale absent from the user's turn. Haiku split the same turn faithfully, so it
  is the one accepted decomposition the three models disagree on.

The accepted set is the 15 trajectories whose root step is the agent's own text and
whose split preserves the mistake (Sonnet and Opus accept exactly these; Haiku adds
task 59). These are copies — the originals stay in the git-ignored work folders
`runs/decomp/tau/<model>-medium/`, which each release's `audit.json` cites, along
with the review decision and reason for every attempted trajectory.
