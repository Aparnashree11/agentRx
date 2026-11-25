# AgentRx: Presentation-Change Trajectories

This branch (`presentation-change`) adds a benchmark variant for [AgentRx](https://arxiv.org/abs/2602.02475): failed agent trajectories whose **presentation is changed** but whose events are not. The wording, emphasis and JSON layout are rewritten; nothing that happened moves or changes. They test whether AgentRx's judge gives the same verdict when the same failure is written differently.

The presentation changes were generated for the 29 Tau Retail baseline trajectories by three Claude models (Haiku 5.5, Sonnet 5.5 and Opus 5.5), reviewed, and released as versioned datasets ready to run through AgentRx.

For the full AgentRx pipeline documentation, see the README on the `main` branch.

---

## What a presentation change is

The generating model proposes edits of three kinds, and Python applies each only to the field its kind allows, so tool names, call IDs, tool values and the policy can never change:

- **Wording** paraphrases a prose message with the same meaning. Every token containing a digit (IDs, prices, counts, zip codes) survives verbatim, so "10" never becomes "ten".
- **Emphasis** adds or removes markdown (bold, italics, headings, bullets, code marks) without changing the words.
- **Formatting** re-lays-out a JSON payload (a tool response or a tool call's arguments). The model only picks a layout and key order; Python re-serializes, so every key and value stays identical.

Some steps are always locked: the policy/system message, user turns, non-JSON tool responses, and the arguments and results of tool calls on annotated failure steps. A failure step may be reworded or emphasized, but it must stay exactly as clear and as wrong.

Before anything is saved, an independent `check_preserved()` re-check compares the variant with the original: event order and roles unchanged, locked steps byte-identical, tool names and call IDs unchanged, JSON values strictly equal, and prose keeps every digit token. Each case is then reviewed by hand for meaning, since only a person can confirm a paraphrase says exactly what the original said and that every failure stays as wrong.

Example from Tau task 2: the agent miscounts available T-shirts at the root failure step (11, where the data shows 10). A wording edit paraphrases the message but keeps the wrong count:

```
Before: "Currently, there are 11 available T-shirt options in our online store.
         Each option varies by color, size, material, and style."
After:  "Our online store currently has 11 T-shirt options available.
         The options differ in color, size, material, and style."
```

The "11" survives, so the miscount at the root failure step is exactly as wrong as before — only the wording changed.

---

## How it was run

Each trajectory gets a single generation attempt per model. A case whose edit is
invalid, has no edit, or is rejected in review is excluded and documented in the
release manifest (`excluded_ids`), never retried.

| Model | Release | Trajectories |
|---|---|---|
| Haiku | `tau_retail/presentation_change/haiku/v0.1.0` | 29 / 29 |
| Sonnet | `tau_retail/presentation_change/sonnet/v0.1.0` | 28 / 29 (one case excluded — no valid presentation-only edit) |
| Opus | `tau_retail/presentation_change/opus/v0.1.0` | 29 / 29 |

The generator is domain-generic: roles and text fields are read through shared
helpers, and which roles may be reworded (prose) and which carry the policy are
set per domain with `--prose-roles` / `--policy-roles` (Tau defaults to
`assistant` / `system`).

**Full how-to-run, review and compare docs:**
[`agentrx/rewordings/README.md`](agentrx/rewordings/README.md).
**Review notes, reviews and findings:**
[`agentrx/rewordings/reports/presentation_change/tau/`](agentrx/rewordings/reports/presentation_change/tau/).
