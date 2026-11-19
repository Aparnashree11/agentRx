# Step-decoy generation: Haiku vs Sonnet vs Opus on Tau Retail

**Date:** 2026-11-18 · **Status:** pre-review. The numbers below describe the generated candidates and the automated plus manual audit in each `review_sheet.md`. They are not yet signed reviews or AgentRx results.

## Setup

All three runs differed only in the model. Each used one Claude Code call per trajectory.

| | |
|---|---|
| Input | `tau_retail/baseline/v1.0.0/tau_dataset_failed.json` (29 trajectories, all labeled), sha256 `17f8b335…` |
| Models | `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`, all at effort `medium` |
| Prompt / generator | prompt sha256 `6dd5d345c51d…`, generator sha256 `df8159404005…` (identical for all runs) |
| Runtime | Claude Code 2.1.327, `--safe-mode`, no tools, structured output |
| Limits | at most 3 noise + 3 red herrings per trajectory; no decoy may copy or follow the root step |
| Work folders | `runs/decoy/tau/{haiku,sonnet,opus}-medium/` |

Each model was sampled once per trajectory, with no seed control. Differences of one or two trajectories between models are within what a second run could change.

## Key findings

1. **All three produced usable decoys for almost every trajectory.** After review, 28 (Haiku), 28 (Sonnet) and 27 (Opus) of 29 are release candidates.
2. **The bigger the model, the more decoys it added:** an average of 4.3, 5.2 and 7.4 inserted events per trajectory. Only Opus ever used three red herrings in one trajectory (4 times).
3. **All three understood the domain equally well.** Every red herring fails a read-only lookup and is answered with Tau's exact short error, and every noise decoy replays a read-only call. None of them made a decoy out of a state-changing action.
4. **Each model made one disqualifying mistake, and each was a different kind:**
   - Haiku replayed a stale order status (28).
   - Sonnet placed a decoy after the failure (31).
   - Opus replayed a stale gift-card balance (31) and returned a "slip" identical to the original value (47).
5. **They often agree on where the main red herring goes, but rarely on the full set of decoys.** In 15 of 27 comparable trajectories, all three chose the same exchange for a red herring. The overlap of whole decoy sets is low (a mean of 0.17–0.24; see Method notes).
6. **The slips are formulaic.** 91 of 125 red herrings swap the last two characters of an ID. Across a dataset, that is a pattern a detector could learn.
7. **Cost varies 25-fold** ($0.19 vs $2.30 vs $4.79), and Haiku's decoys were just as valid as the others'.

## 1. Results at a glance

| | Haiku | Sonnet | Opus |
|---|---|---|---|
| Proposals with decoys | 29 / 29 | 28 / 29 | 28 / 29 |
| Invalid (refused by the generator) | 0 | 1 (31) | 1 (47) |
| Suggested reject at review | 1 (28) | 0 | 1 (31) |
| **Release candidates** | **28** | **28** | **27** |
| Red herrings / noise | 31 / 31 | 37 / 36 | 57 / 46 |
| Inserted events per trajectory (mean / max) | 4.3 / 6 | 5.2 / 8 | 7.4 / 10 |
| Rationale length (mean words) | 92 | 44 | 118 |
| Cost (total / per trajectory) | $0.19 / $0.007 | $2.30 / $0.079 | $4.79 / $0.165 |
| Mean time per call | 13.0 s | 9.1 s | 14.2 s |

**Decoys per trajectory** (red herrings + noise):

| Mix | Haiku | Sonnet | Opus |
|---|---|---|---|
| 1 + 1 | 25 | 13 | 1 |
| 1 + 2 | 2 | 6 | 2 |
| 2 + 1 | 2 | 7 | 8 |
| 2 + 2 | 0 | 2 | 13 |
| 3 + 1 | 0 | 0 | 1 |
| 3 + 2 | 0 | 0 | 3 |

Haiku almost always does the minimum, one of each. Opus usually does two of each. Sonnet falls in between.

## 2. Where all three models behaved the same

- **Choice of tools.** Every red herring fails a lookup (`get_*` or `find_user_id_*`), and every noise decoy replays a lookup. None of them used a write (cancel, modify, return or exchange) as a decoy. None of them was told in the code which tools are read-only; they worked it out from the policy and the tool descriptions.
- **Error wording.** All 125 red herrings use one of exactly three strings: `Error: order not found`, `Error: product not found`, `Error: user not found`. None added the failed ID. Only `user not found` actually appears in the dataset. The other two follow its pattern and match Tau's conventions, but this dataset alone can't confirm them.
- **Slip style.** Almost all slips are transposed adjacent characters: 29/31 for Haiku, 32/37 for Sonnet and 56/57 for Opus. Most swap the **last two** characters: 19/31, 29/37 and 43/57. The exceptions are a few single-character changes (`#W5490111 → #W5490101`), a doubled letter (`Patel → Patell`, Sonnet), a misspelling (`Yusuf → Yusef`, Opus) and a digit swap inside an email (Opus).
- **Noise close to the failure.** The median noise decoy sits 2–3 steps before the root step. Over 60% of noise decoys sit within 2 steps for Haiku and Sonnet, and 41% for Opus.
- **Format.** Every inserted event fits the trajectory's turn structure, and every call ID matches the original format. This is enforced by the generator, so it is the same for every model by construction.

## 3. Where the models differed

### How much they add
Opus adds about 1.7 times as many events as Haiku. That makes its variants the strongest test of distraction, but also the least natural: a trace with three failed lookups reads as an unusually clumsy agent. Haiku's single pair is the most believable but the weakest distraction.

### What they target
| Red-herring target | Haiku | Sonnet | Opus |
|---|---|---|---|
| `get_order_details` | 21 | 20 | 24 |
| `get_product_details` | 9 | 11 | 18 |
| `get_user_details` | 1 | 3 | 6 |
| Identity lookup (`find_user_id_*`) | 0 | 3 | 9 |
| **Slipped value appears in the root step or its reason** | **14 / 31 (45%)** | 9 / 37 (24%) | 13 / 57 (23%) |

- **Haiku aims at the failure most often.** Nearly half of its red herrings slip the ID of the very entity involved in the root failure. That puts a visible error on the same order or product the agent later gets wrong.
- **Opus spreads its red herrings across the trajectory,** including early identity checks. It is the only model that regularly fails the authentication lookup (9 times). That is a slip on information the user typed, which is believable but far from the failure.
- **Sonnet is in between,** with a few identity red herrings and the lowest focus on the failing entity.

### How they place noise
| Noise | Haiku | Sonnet | Opus |
|---|---|---|---|
| Replays `get_user_details` | 7 / 31 | 17 / 36 | 19 / 46 |
| Replays `get_order_details` | 16 / 31 | 12 / 36 | 20 / 46 |
| Involves the root step's entity | 7 / 31 | 7 / 36 | 14 / 46 |
| Copy placed directly after the original (back-to-back duplicate) | 1 | 2 | 5 |
| Median steps between original and copy | 8 | 8 | 6 |

- **Sonnet and Opus like to replay the user profile;** Haiku prefers order lookups.
- **Profile replays are the riskier choice.** The profile carries payment balances that writes can change, which is exactly what went wrong in Opus's trajectory 31.
- **Back-to-back duplicates are the least subtle noise.** Opus made five, two of them in trajectory 2 alone; Haiku and Sonnet made one and two.

### How they explain themselves
- **Sonnet's rationales are short** (44 words on average) and describe the intended effect.
- **Haiku's are moderate** (92 words) and usually restate the correct answer, for example "10 available, not 11".
- **Opus's are the longest** (118 words) and list every decoy individually.

For example, the rationales for trajectory 4 (the T-shirt miscount):

> **Haiku:** "The red herring adds a visible failed product lookup just before the real product-details call, so the evaluator sees a lookup error and a successful retry near the miscount…"
> **Sonnet:** "A profile re-read and a failed product lookup with a mistyped ID appear just before the T-shirt listing is read. This puts extra output and an error right before the miscount at step 15."
> **Opus:** "There are two failed lookups that are then retried. The first is a user ID with two swapped digits… The second is a T-Shirt product ID with two swapped digits…"

## 4. Errors found

| Model | Trajectory | Issue | How it was caught | Outcome |
|---|---|---|---|---|
| Haiku | 28 | Noise replays `get_order_details` for `#W7181492` after that order's return succeeded (step 25). The copy shows the order's status from before the return. | Review audit (stale replay) | Suggested reject |
| Sonnet | 31 | Red herring before steps 35–36, **after** the root failure at step 31. | Generator refused it | Invalid; no candidate |
| Opus | 31 | Noise replays the user profile after step 26. The cancellation at step 23 refunded $109.27 to `gift_card_7711863`, but the replay still shows the old balance of 44. | Review audit plus manual check | Suggested reject |
| Opus | 47 | Red herring whose "slip" equals the original value (`daiki_johnson_9532 → daiki_johnson_9532`). | Generator refused it | Invalid; no candidate |

The audit also flagged **ten other replays with writes in between** (Haiku 105; Sonnet 98, 99, 104, 105; Opus 28, 98, 99, 104, 105). On a manual check, all ten were still accurate. Either the write failed, it touched a different order, or the payment went to a card or PayPal account, which the profile shows without a balance.

**The mistakes differ in kind.** The generator's rules caught both invalid proposals automatically. Both stale replays got through generation and needed domain reasoning at review. Stale-state errors are the main thing reviewers must check, whichever model is used.

## 5. Case study: trajectory 31

The annotated failure is at step 31: the agent tries to partly cancel order `#W5481803`, which the policy forbids.

| | Haiku | Sonnet | Opus |
|---|---|---|---|
| Red herring before 27–28 (`get_order_details #W5481803`) | `→ #W5481830` | `→ #W5481308` | `→ #W5481830` |
| Noise: replay 27–28 after step 30 | yes | — | yes |
| Noise: replay 13–14 after step 28 | — | yes | — |
| Noise: replay profile (7–8) after step 26 | — | — | yes (**stale**) |
| Red herring before 19–20 (`#W9373487`) | — | — | yes |
| Red herring before 35–36 (`#W7449508`) | — | yes (**after root, invalid**) | — |
| Outcome | valid | invalid | suggested reject |

**The models did not make the same mistake.**
- **Common ground:** all three chose the same core decoy, a failed lookup of the order at the heart of the failure placed just before the real lookup. Haiku and Opus even chose the same slip, `#W5481830`, and the same noise. Those decoys are valid in all three proposals.
- **Sonnet's mistake** is a placement error: an extra red herring lands after the failure.
- **Opus's mistake** is a state-tracking error: an extra profile replay comes after a refund to the gift card it displays.

In both cases, the error came from the extra decoy beyond the shared core.

## 6. Cost and speed

| | Haiku | Sonnet | Opus |
|---|---|---|---|
| Total for 29 trajectories | $0.19 | $2.30 | $4.79 |
| Per release candidate | $0.007 | $0.082 | $0.177 |
| Mean time per call | 13.0 s | 9.1 s | 14.2 s |

The time includes Claude Code startup. Sonnet was faster than Haiku in this run, so time per call is not a reliable proxy for model size here.

## 7. Implications and recommendations

- **For the AgentRx experiment,** the three releases test different things:
  - Haiku's variants test whether one well-aimed error near the failure misleads the judge.
  - Opus's variants test whether a noisier trace with several errors does.
  - Report the attraction rate per generator, and on the 15 trajectories where all three chose the same red-herring exchange, for a closer comparison.
- **Review effort grows with decoy count.** Opus's 103 decoys take about 1.7 times as much reviewing as Haiku's 62, and its profile replays need balance checks.
- **The formulaic slips could become a signature.** Most red herrings swap the last two characters of an ID. If a judge or a later detector learns that "a not-found error whose ID differs from the next call's ID in the last two characters" means a decoy, the benchmark stops testing localization. Consider asking for varied slip positions, or checking the distribution at release.
- **Regenerating the invalid cases** (Sonnet 31, Opus 47) would bring Sonnet to 29 candidates and Opus to 28, at about $0.08 and $0.17. Keep the first attempts and record the resampling in the audit.
- **Single samples.** Each model ran once per trajectory. Before drawing conclusions about the models themselves, as opposed to these releases, a second run per model would show how stable these differences are.

## Method notes

- Numbers come from each work folder's `proposal.json`, `insertions.json`, `generation.json` and `reviews.template.json`, compared against the baseline trajectories and labels.
- "Red-herring exchange agreement" means two models chose the same `source_start` for a red herring. "Same slip" additionally requires the same `find` and `replace_with`.
- The **mean overlap** of decoy sets is the size of the intersection divided by the size of the union of each model's decoy set for a trajectory (Jaccard similarity), averaged over trajectories where both models have valid proposals:

  | Pair | Trajectories | Same red-herring exchange | Same red herring and slip | Same noise decoy | Mean overlap |
  |---|---|---|---|---|---|
  | Haiku–Sonnet | 28 | 19 | 8 | 10 | 0.20 |
  | Haiku–Opus | 28 | 24 | 13 | 9 | 0.17 |
  | Sonnet–Opus | 27 | 22 | 15 | 12 | 0.24 |
  | All three | 27 | 15 | — | — | — |
- "Writes in between" and "stale" use Tau tool-name rules in the review script: `get_`, `list_` and `find_` calls, plus `think` and `calculate`, count as read-only. Those rules are not part of the domain-general generator. Every flagged case was checked by hand against the trajectory.
- Distance to the failure is measured in original step numbers, before any decoys are inserted.
