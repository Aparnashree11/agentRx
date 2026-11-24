# Presentation Change — Fooling the Flight Recorder

A label-preserving rewording that stress-tests AgentRx's failure attribution.
It rewrites a failed trajectory so it *looks* different but *what happened* is
unchanged. A robust root-cause judge should return the same verdict on the
variant as on the original; if the verdict moves, that is the fragility we are
measuring.

**Author:** Uzma Fatima · CS6170 AI Capstone · Track A

---

## What it does

The model proposes small, structured edits; Python applies each one only to the
field its kind allows, so tool names, call IDs, tool values and the policy can
never change. Three kinds of edit are allowed:

| Kind | What changes | Guarantee |
|---|---|---|
| **Wording** | Paraphrases a prose message (Tau: an assistant message) | Every digit token (IDs, prices, counts, zip codes) survives verbatim — "10" never becomes "ten" |
| **Emphasis** | Adds or removes markdown (bold, italics, headings, bullets, code) | The words stay exactly the same, in the same order |
| **Formatting** | Re-lays-out a JSON tool payload (response or call arguments) | Python re-serializes it, so every key and value is identical |

Some steps are always locked: policy/system messages, user turns, non-JSON tool
responses, and the arguments and results of tool calls on annotated failure
steps. A failure step may be reworded or emphasized, but it must stay exactly as
clear and as wrong. An independent `check_preserved()` re-check compares every
variant against the original before it is saved — confirming event order and
roles are unchanged, locked steps are byte-identical, tool names and call IDs
are unchanged, JSON values are strictly equal, and prose keeps every digit
token. Steps are 1-based event positions and never move, so labels need no
remapping.

The generator is domain-generic: roles and text fields are read through shared
helpers, and which roles may be reworded (prose) and which carry the policy are
set per domain with `--prose-roles` / `--policy-roles` (Tau defaults to
`assistant` / `system`).

---

## Setup

From the repo root, with the AgentRx environment active and Claude Code signed
in:

```bash
source .venv/bin/activate
# If `claude` is not on PATH, point at the binary:
export CLAUDE_BIN=~/.vscode/extensions/anthropic.claude-code-<version>/resources/native-binary/claude
```

Each generator call runs isolated (`--safe-mode`, no tools, no MCP, empty
working directory, structured JSON output). A run is refused if the model that
answers is not the one requested.

---

## 1. Generate

Generate the rewording for all three models on the Tau baseline:

```bash
base=data/benchmark_versions/tau_retail/baseline/v1.0.0
for m in haiku sonnet opus; do
  python -m agentrx.rewordings.presentation_change generate --domain tau \
    --trajectories "$base/tau_dataset_failed.json" \
    --ground-truth "$base/tau_ground_truth.json" \
    --model "$m" --effort medium \
    --work "runs/presentation_change/tau/$m-medium" &
done; wait
```

| Flag | Meaning |
|---|---|
| `--model` | `haiku` / `sonnet` / `opus` (full IDs `claude-haiku-5-5`, etc.) |
| `--ids 2` | Single-trajectory pilot (a pilot work dir can never be released) |
| `--max-attempts` | Regeneration cap, default 3 (first attempt + 2 regenerations) |
| `--prose-roles` / `--policy-roles` | Role names for a non-Tau domain (Tau defaults assistant / system) |

Each case prints `<id>: EDIT (N edits)` or `<id>: INVALID`. The work directory is
locked to its settings in `config.json`; an interrupted batch resumes with the
same command. Each valid case gets `proposal.json`, `events.json`, and a
`validation.json` listing every change plus the `events_sha256` the review must
name. An invalid proposal is kept as `invalid.json` for review, not dropped.

**Regenerate** a failed or rejected case (counts against the cap):

```bash
python -m agentrx.rewordings.presentation_change generate --domain tau \
  --trajectories "$base/tau_dataset_failed.json" \
  --ground-truth "$base/tau_ground_truth.json" \
  --model sonnet --effort medium \
  --work runs/presentation_change/tau/sonnet-medium --regenerate 28 55
```

The previous attempt is moved to `_superseded/<id>/<n>/` and recorded in the
audit. A case still not valid after the cap is excluded at release (below),
not forced through.

---

## 2. Review

Write the review sheet, then review **each case**:

```bash
python -m agentrx.rewordings.presentation_change review-sheet \
  --work runs/presentation_change/tau/sonnet-medium
```

This writes `review_sheet.md` and `reviews.template.json`. For each case the
sheet shows the attempt number, the root and other failures, the model's
rationale, and every change with its checks. Prose edits appear in full,
before and after; edits on annotated failure steps are flagged with ⚠.

Python has already checked structure and values, so the review is about
**meaning**: each paraphrase must say exactly what the original said, and every
annotated failure must stay exactly as clear and as wrong. Fill `decision`,
`reviewer` and `reason` in the template and save it as `reviews.json`. Keep
`events_sha256` as written — it ties the review to the exact events you read, so
a review written before a regeneration is stale and refused.

```json
{
  "4": {"decision": "accept", "reviewer": "<your name>",
        "reason": "<what in the trace supports your decision>",
        "events_sha256": "<copied from the template>"}
}
```

---

## 3. Release

Release each reviewed work directory with a fresh version. AgentRx then runs on
it like any other release:

```bash
python -m agentrx.rewordings.presentation_change release \
  --work runs/presentation_change/tau/sonnet-medium \
  --reviews runs/presentation_change/tau/sonnet-medium/reviews.json \
  --version v0.1.0

release_dir=data/benchmark_versions/tau_retail/presentation_change/sonnet/v0.1.0
python run.py "$release_dir/trajectories" --domain tau \
  --ground-truth "$release_dir/ground_truth.json" --run-name tau_pc_sonnet
```

**Every case must be accounted for.** Following `RELEASE_PLAN.md`, a release
covers all labeled trajectories (29 for Tau), each generated, valid and
accepted — unless it is excluded at the attempt cap. Release refuses, with one
message listing every case that needs attention, when:

- the work directory does not cover every labeled trajectory;
- a case is missing;
- a case with attempts left is invalid, has no edit, or was rejected;
- a review is missing, unsigned, or stale;
- the inputs changed since generation;
- a rebuilt case differs from its saved events;
- the version already exists.

A case still not releasable at the cap is **excluded**, as step-decoy left out
its task 31: left out of `trajectories/` and `ground_truth.json`, and documented
with its reason in the manifest's `excluded_ids` / `excluded` and in the audit
(which keeps every attempt). Only stuck cases are excluded; attempts-left,
stale review, or drift still block the release.

Each release contains:

- `trajectories/` — the accepted cases in the baseline layout, each record
  identical to the baseline except its `traj`.
- `ground_truth.json` — the baseline labels plus `original_step_number`
  (equal to `step_number`, since steps never move).
- `audit.json` — each case's proposal, generation metadata, attempt number,
  superseded attempts, review, applied changes, root failure, and any
  exclusion reason.
- `manifest.json` — the step-decoy keys plus `helpers_sha256`, `regenerated`,
  `excluded_ids` / `excluded`; `attempted_count` counts every case.

---

## 4. Compare

Measure how much the verdict moved, using clean and variant judge reports from
the same judge configuration (one decision per case):

```bash
python -m agentrx.rewordings.presentation_change compare \
  --audit "$release_dir/audit.json" \
  --clean runs/tau_baseline_v1/judge_output/runs/run1.json \
  --variant runs/tau_pc_sonnet/judge_output/runs/run1.json
```

Paired cases are those the clean run localized correctly. Each is classified as
`same_step_same_category`, `step_moved`, `category_changed` (same step), or
`step_and_category_changed`. The **verdict-flip rate** is the fraction of paired
cases with any change (a category change at the same step counts).
`verdict_flip_rate_fully_correct` repeats it on cases whose clean category also
matched the annotation. Missing predictions and clean misses are counted
separately; `predictions` lists the root, clean and variant verdict for every
case.

---

## Tests

```bash
python -m pytest tests/test_presentation_change.py
```

The suite mocks the Claude Code CLI (no model is called) and covers the edit
rules, `check_preserved()` tampering checks, generation and the regeneration
cap, the release gates (including exclusion), and the compare classification.

---

## Notes

- **Confidential / gated.** This is a high-risk project. The generator, its
  prompts and the reworded trajectories stay inside the team until the
  coordinated-disclosure window (see `RELEASE_PLAN.md`).
- **Shared code.** The generator imports dataset loading, layouts, hashing and
  prompt rendering from `step_decoy` unchanged; `step_decoy.py` is never
  modified.
- **Full dataset-versioning notes:** `data/benchmark_versions/README.md`.
