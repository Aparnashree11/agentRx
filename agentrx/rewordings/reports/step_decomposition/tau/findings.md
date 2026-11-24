# Step decomposition on Tau Retail: cross-model findings

Three Claude models (Haiku, Sonnet, Opus 5.5) each took the 29 Tau Retail baseline
trajectories and split the one annotated root-cause step into two to four smaller
steps by the same actor, keeping the mistake unfixed. One Claude Code call per
trajectory, medium effort, same prompt and generator code. This report compares
what they produced and records the review that accepted or rejected each one.

## Volume

| Model | Proposed (DECOMPOSE) | Declined | Invalid | Accepted in review | Rejected in review | Cost |
|---|---|---|---|---|---|---|
| Haiku | 29 | 0 | 0 | 16 | 13 | $0.16 |
| Sonnet | 29 | 0 | 0 | 15 | 14 | $2.21 |
| Opus | 29 | 0 | 0 | 15 | 14 | $4.49 |

With a prompt that states plainly that splitting one turn produces consecutive
same-actor messages, **every model proposes a decomposition for every trajectory**:
no declines, no structurally invalid splits. The spread is entirely in review.

## Where the line is drawn — in review, not in generation

The dividing line between a faithful decomposition and an unfaithful one is whether
the annotated step contains **the agent's own words**:

- **16 steps carry actor text** — an assistant's wrong claim ("there are 11
  options", a wrong tracking number) or a user's underspecified request. Splitting
  these just reorganizes real text into smaller same-actor messages, and the
  mistake rides along on the marked one. These are accepted.
- **12 steps are silent tool calls** (`cancel_pending_order`, `calculate`,
  `modify_pending_order_items`, `exchange_delivered_order_items`,
  `transfer_to_human_agents`, …) with no text content of their own. The model can
  only "split" them by writing a narration the agent never spoke. That narration
  restates real arguments, but it is fabricated speech, so all twelve are
  **rejected** for every model (tasks 12, 28, 31, 34, 38, 41, 47, 72, 74, 98, 99,
  105).
- **1 step (task 20) carries both text and a call** — the "Delivered Orders"
  misread that also triggers a lookup. It is accepted: the text splits faithfully
  and the call stays on the last smaller step.

So the hard ceiling on accepted decompositions is about 17 of 29, set by how many
root steps are the agent's own words. **This is the same ceiling the earlier draft
reported, but it now falls out of review rather than the model declining** — the
models will attempt anything; the reviewer holds the line.

## The models barely differ — correcting an earlier finding

An earlier version of this report concluded that *"Opus is far more conservative,"*
decomposing only 4 of 29 while Haiku and Sonnet did about 14. **That was an artifact
of the prompt, not a property of the model.** The prompt listed the dataset's
allowed role transitions (which contain no same-actor pair) without saying that the
same-actor boundaries *inside* a split are expected and allowed. Opus read the list
strictly and refused every split that would place two same-actor messages in a row;
all 25 of its declines cited exactly that. Haiku and Sonnet were not tripped by it.

Once the prompt says explicitly that the transition list governs only the outer
boundaries of a split, **Opus decomposes all 29 trajectories, the same as the other
two.** On the same inputs the three models now agree closely:

| Model | Accepted | of which assistant-text roots / user-text roots | Avg. smaller steps | Avg. steps added |
|---|---|---|---|---|
| Haiku | 16 | 8 / 8 | 2.8 | 1.8 |
| Sonnet | 15 | 8 / 7 | 2.6 | 1.6 |
| Opus | 15 | 8 / 7 | 2.2 | 1.2 |

The only behavioural difference left is verbosity: Opus uses the fewest smaller
steps (2.2 on average) and Haiku the most (2.8). The lesson for the project's model
axis is the opposite of the earlier one — for this transformation the generator
model is **not** a large lever once the prompt is unambiguous; the prompt was.

## Why the rejected cases were rejected

Every rejection is a fabrication or a lost mistake, in one of three groups:

- **Silent tool-call roots (12 per model).** No agent text to split; the narration
  is invented. See above.
- **Task 80 (all three models).** The user's final turn ends with the `###STOP`
  marker, which carries the annotated failure (execution ended prematurely). Every
  split drops that marker, so the decomposition no longer preserves the mistake.
- **Task 59 (Sonnet and Opus only).** Both add a rationale to the user's
  cancellation — "since you can't confirm the order will be processed within the
  next 5 days" — that is not in the original turn and misstates the annotated
  failure (the user wrongly assuming one order was older). Haiku split the same turn
  without inventing anything and is accepted. This is the one case where the model
  choice changes the outcome, and it is Haiku, not Opus, that comes out ahead.

## Agreement

- **15 trajectories are accepted for all three models** (2, 3, 4, 20, 21, 32, 39,
  55, 63, 71, 79, 82, 87, 91, 104). Tasks 2/3/4 are the shared T-shirt miscount.
- Sonnet and Opus accept the **identical** 15-trajectory set.
- Haiku accepts one more, task 59, because it alone split that user turn faithfully.
- All three reject the identical 12 silent tool-call steps plus task 80, so that
  reject set is a property of the data, not the model.

## Placement and shape

Accepted decompositions are short: 2.2–2.8 smaller steps on average, adding 1.2–1.8
events to the trajectory. The mistake lands on the last one or two smaller steps —
the renumbered ground truth points there, and `audit.json` records the exact
`decomposed_steps` and `error_steps`. The lead-in steps are narration ("let me go
through the listing", "I've pulled up the order") that restates context already
present in the trajectory and adds no new facts.

## Cost

Cost tracks model size, not usefulness: Opus cost $4.49 for 15 accepted
trajectories ($0.30 each), Sonnet $2.21 for 15 ($0.15 each), Haiku $0.16 for 16
($0.01 each). For this transformation Haiku is both the cheapest and the most
productive, and — on task 59 — the most faithful.

## Case study: task 2 (the T-shirt miscount)

The agent read a tool result listing ten available T-shirts and told the customer
there were eleven. All three models split the single reply the same way: a narration
step ("let me go through the variants"), then the wrong count of 11 verbatim, then
the closing offer — Haiku and Sonnet in three smaller steps, Opus in two. The
miscount is untouched, the actor stays `assistant`, and the surrounding tool call
(step 5) and tool result (step 6) are unchanged. The root failure moves from step 7
to step 8, and the renumbered ground truth follows. This is the model case for the
transformation: a one-line mistake becomes a short passage that a localization judge
must still trace back to the same sentence.
