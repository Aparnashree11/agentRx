# Presentation-change generation: Haiku vs Sonnet vs Opus on Tau Retail

**Date:** 2026-11-22 · **Status:** reviewed. Every case in every model's release has a signed accept review (reviewer Uzma Fatima). All three are released as `v0.1.0`: Haiku and Opus with 29/29 cases, and Sonnet with 28/29 (case 28 excluded). No AgentRx results yet.

## Setup

| | |
|---|---|
| Input | `tau_retail/baseline/v1.0.0/tau_dataset_failed.json` (29 trajectories, all labeled) |
| Models | `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`, all at effort `medium` |
| Prompt | prompt sha256 `5fd8b3fb1768…` (identical for all runs) |
| Edit kinds | wording and emphasis on assistant messages; formatting of JSON tool results and tool-call arguments. Policy, user turns and non-JSON tool results are locked; annotated failure steps take wording or emphasis only. |
| Attempt cap | 3 per case, locked per work folder |
| Work folders | `runs/presentation_change/tau/{haiku,sonnet,opus}-v2/` |

Each model was sampled once per trajectory, with no seed control.

## Results

| | Haiku | Sonnet | Opus |
|---|---|---|---|
| **Accepted cases** | **29 / 29** | **28 / 29** | **29 / 29** |
| Excluded | — | 28 (attempt cap) | — |
| Cases regenerated | 3 (31, 72, 74) | 4 (28 ×2, 39, 55, 104) | 0 |
| Model calls | 32 | 34 | 29 |
| Edits in final cases (formatting / wording / emphasis) | 84 / 34 / 59 | 83 / 27 / 34 | 131 / 67 / 48 |
| Prose edits on annotated failure steps | 8 | 7 | 9 |
| Cost, all attempts | $0.16 | $2.37 | $5.10 |
| Release | [`haiku/v0.1.0`](../../../../../data/benchmark_versions/tau_retail/presentation_change/haiku/v0.1.0/manifest.json) | [`sonnet/v0.1.0`](../../../../../data/benchmark_versions/tau_retail/presentation_change/sonnet/v0.1.0/manifest.json) | [`opus/v0.1.0`](../../../../../data/benchmark_versions/tau_retail/presentation_change/opus/v0.1.0/manifest.json) |

### Why cases were regenerated

| Model | Case | Rejected attempt(s) | Cause |
|---|---|---|---|
| Haiku | 31, 74 | 1 | Emphasis edit changed the words, not just the markdown |
| Haiku | 72 | 1 | Wording paraphrase of a numbered list dropped the list numbers "1." and "2." (step 23). Accepted at first; rejected once the digit check compared whole tokens. Attempt 2 uses emphasis and keeps the numbers. |
| Sonnet | 39, 55 | 1 | Formatting edit chose the layout the JSON already had (no-op) |
| Sonnet | 104 | 1 | Emphasis edit returned the original text unchanged (no-op) |
| Sonnet | 28 | 3 (cap) | Attempts 1 and 2 wrote the order ID possessively, `#W2575533's`, which loses the whole token `#W2575533` (step 35). Attempt 3 edited step 33, a locked step. No valid presentation-only edit was produced, so the case is excluded. |

## Findings

1. **Opus was the only model with no failed attempt.** It also made the most edits (246 in all, against 177 for Haiku and 144 for Sonnet).
2. **The models' error rates do not follow their size.** Haiku, the smallest model, released all 29 cases; Sonnet released 28 and needed the most regenerations. Their failures differed in kind: Haiku's emphasis edits changed words, while Sonnet made no-op edits and kept writing the ID as a possessive. With one sample per case, a difference of one or two cases between Haiku and Sonnet could change on a second run.
3. **The whole-token digit check caught a value change the substring check missed.** In Haiku 72, the list numbers "1" and "2" were dropped, and the substring check passed only because "1" occurs inside the order ID `#W5270061`. The same stricter check also rejects `#W2575533's` (Sonnet 28), where the ID is intact but has a possessive attached. So that one reflects how strict the rule is, rather than a lost value.
4. **Automatic checks, not review, stopped every bad attempt.** Of the 9 superseded or failed attempts, 7 were refused by validation at generation time. The other 2 (Haiku 72, Sonnet 28 attempt 1) passed at first and were invalidated when the digit check switched to whole tokens. The reviewer rejected none of the final cases.

## Notes

- The Haiku and Opus `v0.1.0` manifests predate exclusion support, so they have no `excluded_ids` field; neither excluded any case. Haiku's release holds case 72's second attempt.
- The Sonnet release carries `excluded_ids: ["28"]` with its reason, and all three attempts are recorded in its `audit.json`.
- Haiku 72's first attempt was reviewed and accepted under the substring check. The whole-token check then invalidated it, and attempt 2 was reviewed again before release.
- Numbers come from each work folder's `config.json`, `generation.json` and `validation.json`, and from the earlier attempts kept in `_superseded/`.
