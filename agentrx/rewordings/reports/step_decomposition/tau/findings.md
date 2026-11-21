# Step decomposition on Tau Retail: cross-model findings

Three Claude models (Haiku, Sonnet, Opus 5.5) each took the 29 Tau Retail baseline
trajectories and tried to split the one annotated root-cause step into two to four
smaller steps by the same actor, keeping the mistake unfixed. One Claude Code call
per trajectory, medium effort, same prompt and generator code. This report
compares what they produced.

## Volume

| Model | Accepted | Declined (`NO_VALID`) | Invalid | Rejected in review | Cost |
|---|---|---|---|---|---|
| Haiku | 13 | 13 | 2 | 1 | $0.17 |
| Sonnet | 14 | 13 | 1 | 1 | $2.15 |
| Opus | 4 | 25 | 0 | 0 | $4.37 |

"Invalid" means the split broke a structural rule and was kept for review, not
released. "Rejected" means the candidate was valid but a reviewer declined it.

## What can be decomposed, and what cannot

The dividing line is the same for every model: **decomposition applies to a step
whose content is text, and not to a step that is a single tool call.**

- A text root cause — an assistant's wrong claim ("there are 11 options"), a
  user's underspecified or off-task request — splits cleanly into smaller
  same-actor messages.
- An atomic tool call — `cancel_pending_order`, `calculate`,
  `modify_pending_order_items`, `exchange_delivered_order_items`,
  `transfer_to_human_agents` — is declined. The mistake *is* the call; splitting it
  would need an invented extra message or a second call, and the dataset's turn
  structure (a tool call must be followed by its result; an assistant text turn is
  followed by the user) leaves no room for a same-actor split. Every model reaches
  this conclusion on its own and states it in its `NO_VALID_DECOMPOSITION` reason.

Among the labeled steps, 13 of the 29 Tau root causes are atomic tool calls, which
puts a hard ceiling near 16 on how many any model can decompose.

## The models differ in conservatism

Splitting by the actor of the root step:

| Model | Decomposed (assistant / user) | Declined (assistant / user) |
|---|---|---|
| Haiku | 8 / 8 | 12 / 1 |
| Sonnet | 8 / 8 | 12 / 1 |
| Opus | 4 / 0 | 16 / 9 |

Haiku and Sonnet behave almost identically: they split every text step, assistant
or user, and decline the tool calls. **Opus is far more conservative.** It declined
all nine user turns and most assistant text, accepting only four. Its reason is
consistent: splitting a user turn into consecutive user messages would create a
`user -> user` boundary, which does not occur in the dataset, so it refuses — even
though the generator only enforces that rule at the entry and exit of the split,
not inside it. Opus holds itself to a stricter reading of the turn structure than
the task requires.

This is the clearest signal for the project's model axis: on the *same* input, the
generator model changes the attack surface from 14 trajectories to 4.

## Agreement

- All three models decomposed **tasks 2, 3 and 39** (and task 104 for Sonnet and
  Opus; Haiku declined 104). Tasks 2/3 are the shared T-shirt miscount.
- Haiku and Sonnet agree on all 13 of Haiku's accepted trajectories; Sonnet adds
  104.
- Every model declines the same tool-call steps (12, 28, 31, 34, 38, 41, 47, 72,
  74, 98, 99, 105), so the decline set is a property of the data, not the model.

## Placement and shape

Accepted decompositions are short: 2.2–2.6 smaller steps on average, adding 1.2–1.6
events to the trajectory. The mistake lands on the last one or two smaller steps —
the renumbered ground truth points there, and `audit.json` records the exact
`decomposed_steps` and `error_steps`. The lead-in steps are narration ("let me go
through the listing", "I've pulled up the order"), which the task's own example
endorses and which adds no new facts.

## Errors

- **Two invalid Haiku cases (20, 34) and one Sonnet case (20):** the split left a
  step whose exit boundary became `assistant -> tool`, which does not match the
  original turn — a tool-call step dressed up as text. The generator caught these
  and wrote `invalid.json`; they were not released.
- **One genuine review reject (task 59, Haiku and Sonnet):** both models added a
  rationale to the user's cancellation — "since you can't confirm the order will be
  processed within the next 5 days" — that is not in the original turn and
  mischaracterizes the annotated failure (the user wrongly assuming one order is
  older). This is the one case where a model changed the step instead of
  reorganizing it. Opus declined task 59 outright.
- The automatic numeric-token check in the review script over-flagged five Haiku
  and five Sonnet cases whose mistake is an order ID (`#W…`): the digit run is glued
  to the `W`, so a word-boundary match misses it. All were confirmed valid by hand.

## Cost

Cost tracks model size and inversely tracks acceptance: Opus cost $4.37 to produce
4 usable trajectories ($1.09 each), Sonnet $2.15 for 14 ($0.15 each), Haiku $0.17
for 13 ($0.01 each). For this transformation Haiku is both the cheapest and among
the most productive.

## Case study: task 2 (the T-shirt miscount)

The agent read a tool result listing ten available T-shirts and told the customer
there were eleven. All three models split the single reply the same way: a narration
step ("let me go through the variants"), then the wrong count of 11 verbatim, then
the closing offer. The miscount is untouched, the actor stays `assistant`, and the
surrounding tool call (step 5) and tool result (step 6) are unchanged. The root
failure moves from step 7 to step 8 or 9, and the renumbered ground truth follows.
This is the model case for the transformation: a one-line mistake becomes a
three-line passage that a localization judge must still trace back to the same
sentence.
