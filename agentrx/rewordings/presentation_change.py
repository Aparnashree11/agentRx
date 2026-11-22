"""Generate presentation-change trajectories for AgentRx, review them, and freeze accepted cases.

A presentation change alters how a failed trajectory's evidence is shown, never
what happened, so a robust root-cause judge should give the same verdict on the
variant as on the original. Three kinds of edit are allowed:
  - wording:    paraphrase a prose message (same meaning, same values);
  - emphasis:   add or remove markdown in a prose message (same words);
  - formatting: re-lay-out a JSON tool response or tool-call arguments (same keys
                and values; Python re-serializes, the model only picks the style).

Like step_decoy, nothing is tied to one layout: roles are read with its role(),
text with its content_key(), and tool results are found by call-ID links. Which
roles count as prose and which carry the policy is set per domain (DEFAULT_ROLES,
or --prose-roles / --policy-roles; Tau: assistant and system).

This mirrors agentrx/rewordings/step_decoy.py: the model decides, Python edits.
The model returns a small structured proposal (which step, which kind, the new
text or layout); Python applies it only to the field that kind may touch, so tool
names, call IDs, tool values and the policy cannot change. Policy messages, the text
of every non-prose role (Tau: user turns) and non-JSON tool responses are always
locked, and an annotated failure
step takes wording or emphasis only. A second, independent check then compares
the result with the original before anything is saved. Steps are 1-based event
positions, as in the AgentRx baselines and the step-decoy releases. No IR conversion.

Shared helpers (dataset loading, hashing, prompt rendering) are imported from
step_decoy, unchanged, so both rewordings version identically. The model call is
this file's own ask_claude: the same isolation flags as step_decoy's, but with this
rewording's system prompt and schema, so step_decoy.py is never modified.

Release follows RELEASE_PLAN.md: all labeled trajectories (29 for Tau) per
transformation, each one generated, valid and accepted by a signed review. Nothing
is excluded; a failed or rejected case is regenerated (generate --regenerate ID).
"""

import argparse
import json
import os
import re
import subprocess
import tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path

from agentrx.invariants.domain_registry import get_domain_config, list_domains
from agentrx.judge.judge import convert_to_failure_case
from agentrx.rewordings import step_decoy
from agentrx.rewordings.step_decoy import (
    CALL_ID_KEYS, DATASETS, MODELS, PROVIDER, ROOT, VERSIONS, claude_version, content_key, digest,
    domain_inputs, dump_source, instruction, lines, load_dataset, read, render, role, root_failure,
    safe_name, stored, write)

# The prompt template, with <<PLACEHOLDER>> slots filled by step_decoy.render().
TEMPLATE = ROOT / "agentrx/rewordings/presentation_change_prompt.txt"
VARIANT = "presentation_change"  # release path: <dataset>/presentation_change/<model>/vX.Y.Z
# Inside a work directory: earlier attempts of regenerated cases, kept (never deleted,
# since they were paid for) and recorded in the release audit.
SUPERSEDED = "_superseded"
# Attempts per case (the first one plus regenerations). Regenerating until a reviewer
# accepts would bias the release toward easy-to-accept edits, so the number is capped,
# locked in config.json with the other settings, and recorded in the manifest. A case
# that reaches the cap without being accepted blocks the release (RELEASE_PLAN: all
# cases), which is then a reportable outcome, not something to work around.
DEFAULT_MAX_ATTEMPTS = 3
# A review must name the exact events.json it approved, so a review written before a
# case was regenerated cannot approve the new, unseen content.
REVIEW_FIELDS = ("reviewer", "reason", "events_sha256")

# ---------- What the model may propose ----------

KINDS = ("wording", "emphasis", "formatting")
PROSE_KINDS = ("wording", "emphasis")  # replace a prose message's text content
# Roles are read with step_decoy.role() and text with step_decoy.content_key(), so any
# layout AgentRx reads works. Which roles may be reworded (prose) and which carry the
# policy is a per-domain choice, set with --prose-roles / --policy-roles and locked in
# config.json. These are the defaults; a domain not listed must pass --prose-roles.
# Every role that is neither prose nor a tool result is locked (Tau: user turns).
# Magentic-One has no default on purpose: which of its agents' messages count as
# rewordable prose (e.g. "Orchestrator (thought)") is a study decision, not a guess.
DEFAULT_ROLES = {"tau": dict(prose_roles=["assistant"], policy_roles=["system"])}
# A tool result is found from the data, not a role name: an event whose call-ID field
# names a tool call made earlier in the trajectory (step_decoy's call-ID convention).
# A bare "id" is left out because at the top level of an event it is usually the
# event's own ID, not a link to a call.
RESULT_ID_KEYS = tuple(k for k in CALL_ID_KEYS if k != "id")
# How the generator re-serializes a JSON payload for a formatting edit.
LAYOUTS = {
    "compact": dict(separators=(",", ":")),
    "spaced": dict(separators=(", ", ": ")),
    "indented": dict(indent=2),
}
KEY_ORDERS = ("original", "sorted", "reverse")

# Replaces Claude Code's default system prompt (passed through ask_claude's system=).
SYSTEM = ("You design presentation-only edits for evaluating the robustness of root-cause judgments "
          "on agent trajectories. Follow the instructions in the user message and answer only through "
          "the structured output.")

# Output schema enforced by `claude --json-schema` (passed through ask_claude's schema=).
# Like step_decoy's, it is flat (Claude Code rejects a top-level anyOf), so the CLI
# only checks types and enums; Python checks which fields each decision and kind
# needs (text for wording/emphasis, layout + key_order for formatting) and every rule.
EDIT = {"type": "object", "additionalProperties": False, "required": ["step", "kind", "reason"], "properties": {
    "step": {"type": "integer"},
    "kind": {"type": "string", "enum": list(KINDS)},
    "text": {"type": "string"},                                   # wording / emphasis only
    "layout": {"type": "string", "enum": list(LAYOUTS)},          # formatting only
    "key_order": {"type": "string", "enum": list(KEY_ORDERS)},    # formatting only
    "reason": {"type": "string"}}}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["decision"], "properties": {
    "decision": {"type": "string", "enum": ["EDIT", "NO_VALID_EDIT"]},
    "edits": {"type": "array", "items": EDIT},
    "rationale": {"type": "string"}, "preservation_evidence": {"type": "string"},
    "reason": {"type": "string"}}}


# ---------- JSON payloads (what a formatting edit may touch) ----------

def json_container(text):
    """Parse text as a JSON object or array; None for prose, scalars and invalid JSON."""
    if not isinstance(text, str):
        return None
    try:
        value = json.loads(text)
    except ValueError:
        return None
    return value if isinstance(value, (dict, list)) else None


def canonical(value):
    """A strict comparison key: unlike ==, it tells 1, 1.0 and true apart."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def resolve_roles(domain, prose_roles=None, policy_roles=None):
    """The prose and policy roles for a domain: the flags if given, else DEFAULT_ROLES."""
    default = DEFAULT_ROLES.get(domain, {})
    prose = sorted(set(prose_roles or default.get("prose_roles") or []))
    policy = sorted(set(default.get("policy_roles", []) if policy_roles is None else policy_roles))
    if not prose:
        raise ValueError(f"Domain {domain!r} has no default prose roles; pass --prose-roles "
                         f"(the role names as they appear in its trajectories)")
    if set(prose) & set(policy):
        raise ValueError(f"A role cannot be both prose and policy: {sorted(set(prose) & set(policy))}")
    return dict(prose_roles=prose, policy_roles=policy)


def config_roles(config):
    """The roles a work directory was generated with. Configs written before roles were
    configurable lack the keys; only Tau was generated then, with today's defaults."""
    if "prose_roles" in config:
        return dict(prose_roles=config["prose_roles"], policy_roles=config["policy_roles"])
    return resolve_roles(config["domain"])


def tool_results(events):
    """1-based steps of events that answer a tool call made earlier in the trajectory."""
    calls, found = set(), set()
    for n, event in enumerate(events, 1):
        if any(isinstance(event.get(k), str) and event[k] in calls for k in RESULT_ID_KEYS):
            found.add(n)
        calls |= {c.get("id") for c in event.get("tool_calls") or [] if isinstance(c, dict)}
    return found


def payloads(event, is_result):
    """(path, parsed value) for each JSON payload in an event: a tool result's content
    (is_result: see tool_results), or the arguments of each tool call. A path is a
    tuple of keys/indices."""
    found = []
    key = content_key(event)
    if is_result and key:
        value = json_container(event[key])
        if value is not None:
            found.append(((key,), value))
    for i, call in enumerate(event.get("tool_calls") or []):
        value = json_container((call.get("function") or {}).get("arguments"))
        if value is not None:
            found.append((("tool_calls", i, "function", "arguments"), value))
    return found


def get_path(obj, path):
    for key in path:
        obj = obj[key]
    return obj


def set_path(obj, path, value):
    get_path(obj, path[:-1])[path[-1]] = value


def reorder(value, key_order):
    """Reorder object keys at every depth; lists keep their order (it carries meaning)."""
    if isinstance(value, dict):
        items = [(k, reorder(v, key_order)) for k, v in value.items()]
        if key_order == "sorted":
            items.sort(key=lambda kv: kv[0])
        elif key_order == "reverse":
            items.reverse()
        return dict(items)
    if isinstance(value, list):
        return [reorder(v, key_order) for v in value]
    return value


def serialize(value, layout, key_order):
    return json.dumps(reorder(value, key_order), ensure_ascii=False, **LAYOUTS[layout])


def can_format(event, is_result):
    """True if some layout/key_order would change at least one payload's text."""
    return any(serialize(value, layout, order) != get_path(event, path)
               for path, value in payloads(event, is_result) for layout in LAYOUTS for order in KEY_ORDERS)


# ---------- Prose rules (wording and emphasis) ----------

# Punctuation and markdown that may surround a value without being part of it.
EDGE = ".,;:!?()[]{}<>\"'*`"
# Markdown that emphasis may add or remove: line-start headings and bullets, then
# inline bold/italic asterisks and code backticks. Underscores are deliberately NOT
# treated as markup, because IDs such as yusuf_rossi_9620 contain them.
LINE_MARKUP = re.compile(r"(?m)^[ \t]*(?:#{1,6}[ \t]+|[-+*][ \t]+)")
INLINE_MARKUP = re.compile(r"\*+|`+")


def digit_tokens(text):
    """Every whitespace-separated token containing a digit (IDs, prices, counts, zips),
    trimmed of surrounding punctuation. Wording must keep each one verbatim, as a whole
    token: callers compare these sets, so "11" is not kept by "110" or "#W11"."""
    return {t.strip(EDGE) for t in text.split() if any(c.isdigit() for c in t)} - {""}


def plain(text):
    """The words of a message with emphasis markup removed and whitespace normalized."""
    return " ".join(INLINE_MARKUP.sub("", LINE_MARKUP.sub("", text)).split())


# ---------- Which steps may be edited ----------

def failure_steps(label):
    return {f.get("step_number") for f in label.get("failures") or []}


def editable_steps(case, label, roles):
    """{step: [kinds]} for every step that may be edited; any step not returned is locked.
    - prose (wording, emphasis): events of a prose role with text content, including
      annotated failure steps;
    - formatting: events carrying a JSON payload some layout would change, except
      annotated failure steps.
    Policy-role events, other roles' text and non-JSON tool results never qualify."""
    failing, allowed, results = failure_steps(label), {}, tool_results(case["events"])
    for n, event in enumerate(case["events"], 1):
        if role(event) in roles["policy_roles"]:
            continue
        kinds, key = [], content_key(event)
        if role(event) in roles["prose_roles"] and key and isinstance(event[key], str) and event[key].strip():
            kinds += PROSE_KINDS
        if n not in failing and can_format(event, n in results):
            kinds.append("formatting")
        if kinds:
            allowed[n] = kinds
    return allowed


# ---------- Building a variant ----------

class PreservationError(ValueError):
    """The edited trajectory failed the independent re-check; carries every violation."""

    def __init__(self, violations):
        super().__init__("Preservation check failed: " + "; ".join(violations))
        self.violations = violations


def apply_edits(case, label, proposal, roles):
    """Apply the proposed edits; return the edited events and a log of each change.
    Raises ValueError on any rule break (PreservationError if the re-check fails).
    Deterministic, so release can rebuild the same variant and refuse drift."""
    events = case["events"]
    items = proposal.get("edits")
    if not isinstance(items, list) or not items or not all(isinstance(i, dict) for i in items):
        raise ValueError("Expected at least one edit")
    for key in ("rationale", "preservation_evidence"):
        if not isinstance(proposal.get(key), str) or not proposal[key].strip():
            raise ValueError(f"Missing {key}")
    allowed, results = editable_steps(case, label, roles), tool_results(events)
    edited, done, changes = deepcopy(events), set(), []

    for item in items:
        step, kind = item.get("step"), item.get("kind")
        if type(step) is not int or step not in allowed:
            raise ValueError(f"Step {step!r} is not editable")
        if kind not in allowed[step]:
            raise ValueError(f"Step {step} allows {allowed[step]}, not {kind!r}")
        # One prose edit and one formatting edit per step at most.
        slot = "prose" if kind in PROSE_KINDS else "formatting"
        if (step, slot) in done:
            raise ValueError(f"Step {step} has more than one {slot} edit")
        done.add((step, slot))
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            raise ValueError(f"Step {step}: missing reason")
        event = edited[step - 1]

        if kind in PROSE_KINDS:
            if "layout" in item or "key_order" in item:
                raise ValueError(f"Step {step}: {kind} takes text, not layout or key_order")
            key = content_key(event)  # the field this event's text lives in
            old, new = event[key], item.get("text")
            if not isinstance(new, str) or not new.strip() or new == old:
                raise ValueError(f"Step {step}: {kind} needs new text that differs from the original")
            if kind == "wording":
                # Whole tokens, not substrings: "11" -> "110" must fail.
                lost = sorted(digit_tokens(old) - digit_tokens(new))
                if lost:
                    raise ValueError(f"Step {step}: wording drops values {lost}")
            elif plain(new) != plain(old):
                raise ValueError(f"Step {step}: emphasis changed the words, not just the markdown")
            event[key] = new
            changes.append(dict(step=step, kind=kind, fields=[key], before=old, after=new,
                                reason=item["reason"]))
        else:
            if "text" in item:
                raise ValueError(f"Step {step}: formatting takes layout and key_order, not text")
            layout, order = item.get("layout"), item.get("key_order")
            if layout not in LAYOUTS or order not in KEY_ORDERS:
                raise ValueError(f"Step {step}: formatting needs a layout and a key_order")
            fields = []
            for path, value in payloads(event, step in results):
                new = serialize(value, layout, order)
                if new != get_path(event, path):
                    set_path(event, path, new)
                    fields.append(".".join(map(str, path)))
            if not fields:
                raise ValueError(f"Step {step}: layout={layout}, key_order={order} leaves the JSON unchanged")
            changes.append(dict(step=step, kind=kind, fields=fields, layout=layout, key_order=order,
                                reason=item["reason"]))

    # Second line of defence: re-check the result against the original, independently
    # of the code above, so a bug there cannot slip a real change into a release.
    violations = check_preserved(events, edited, {s for s, _ in done}, roles)
    if violations:
        raise PreservationError(violations)
    return edited, sorted(changes, key=lambda c: (c["step"], c["kind"]))


def check_preserved(original, edited, edited_steps, roles):
    """Every way the edited events may differ from the original, as violations.
    Ported from the old parse_and_validate: same events, order and roles; the policy
    byte-identical; tool names, call IDs and JSON values unchanged. Added here: steps
    that were not edited must be identical; text of non-prose roles and non-JSON tool
    results is locked; prose keeps every digit token; values compare strictly (1, 1.0,
    true differ). Roles, text fields and tool results are found as in editable_steps,
    but from the original events only, so an edit cannot relabel its way past a check."""
    if len(original) != len(edited):
        return [f"[ORDER/LENGTH] event count changed: {len(original)} -> {len(edited)}"]
    violations, results = [], tool_results(original)
    for n, (o, e) in enumerate(zip(original, edited), 1):
        if o == e:
            continue
        who = role(o)
        if who != role(e):
            violations.append(f"[ROLE CHANGED] step {n}: {who!r} -> {role(e)!r}")
            continue
        if who in roles["policy_roles"]:
            violations.append(f"[POLICY CHANGED] step {n}: the {who}/policy message must stay byte-for-byte identical")
            continue
        if n not in edited_steps:
            violations.append(f"[LOCKED STEP CHANGED] step {n} was not edited but differs")
            continue
        if set(o) != set(e):
            violations.append(f"[KEYS CHANGED] step {n}: {sorted(set(o) ^ set(e))}")
            continue
        text = content_key(o)
        for key in o:
            if o[key] == e[key]:
                continue
            if key == text and who in roles["prose_roles"] and isinstance(e[key], str):
                lost = sorted(digit_tokens(o[key] or "") - digit_tokens(e[key]))
                if lost:
                    violations.append(f"[VALUE DROPPED] step {n}: prose lost {lost}")
            elif key == text and n in results:
                before, after = json_container(o[key]), json_container(e[key])
                if before is None:
                    violations.append(f"[TOOL TEXT CHANGED] step {n}: non-JSON tool responses are locked")
                elif after is None or canonical(before) != canonical(after):
                    violations.append(f"[VALUE CHANGED] step {n}: tool response values differ")
            elif key == "tool_calls" and isinstance(e[key], list) and len(o[key]) == len(e[key]):
                for j, (a, b) in enumerate(zip(o[key], e[key])):
                    a_rest, b_rest = deepcopy(a), deepcopy(b)
                    a_args = a_rest.get("function", {}).pop("arguments", None)
                    b_args = b_rest.get("function", {}).pop("arguments", None)
                    if a_rest != b_rest:
                        violations.append(f"[TOOL NAME/ID CHANGED] step {n} call {j}")
                    before, after = json_container(a_args), json_container(b_args)
                    if a_args != b_args and (before is None or after is None or canonical(before) != canonical(after)):
                        violations.append(f"[VALUE CHANGED] step {n} call {j}: argument values differ")
            else:
                violations.append(f"[FIELD CHANGED] step {n}: {key!r} may not change")
    return violations


# ---------- Model call ----------

def ask_claude(binary, model, effort, message, timeout):
    """Run one isolated, tool-free Claude Code turn; return the structured proposal and run metadata.

    A self-contained copy of step_decoy.ask_claude's logic (same flags, same checks)
    using THIS file's SYSTEM and SCHEMA, so step_decoy.py stays untouched:
      --safe-mode             drops CLAUDE.md, memory, skills, hooks and plugins but keeps
                              the normal login (--bare would need an API key);
      --tools ""              the model can read no files and run nothing;
      --strict-mcp-config     no MCP servers;
      --disable-slash-commands, --no-session-persistence;
      --system-prompt SYSTEM  replaces Claude Code's default system prompt;
      --output-format json    a JSON envelope carrying cost, session and model usage;
      --json-schema SCHEMA    the answer must match SCHEMA (structured_output);
      empty temp cwd          the repository is not visible to the model.
    The run fails unless the requested full model ID appears in modelUsage, so the
    exact model that answered is recorded and checked rather than assumed."""
    with tempfile.TemporaryDirectory() as cwd:
        result = subprocess.run([binary, "-p", "--model", model, "--safe-mode", "--tools", "",
                                 "--strict-mcp-config", "--disable-slash-commands",
                                 "--no-session-persistence", "--system-prompt", SYSTEM,
                                 "--output-format", "json", "--json-schema", json.dumps(SCHEMA)]
                                + (["--effort", effort] if effort else []),
                                cwd=cwd, input=message, capture_output=True, text=True, timeout=timeout)
    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ValueError(f"Claude Code returned no JSON: {(result.stderr or result.stdout).strip()[:500]}")
    if result.returncode or envelope.get("is_error") or not isinstance(envelope.get("structured_output"), dict):
        raise ValueError(f"Claude Code failed: {str(envelope.get('result'))[:500]}")
    usage = envelope.get("modelUsage") or {}
    if model not in usage:
        raise ValueError(f"Requested {model} but the run used {sorted(usage)}")
    meta = {k: envelope.get(k) for k in ("session_id", "num_turns", "duration_ms", "total_cost_usd")}
    return envelope["structured_output"], {**meta, "model_usage": usage}


# ---------- Commands ----------

def generate(args):
    """Mirror of step_decoy.propose: one isolated model call per labeled trajectory,
    saved as a reviewable case folder in a work directory locked to its settings."""
    sources, cases, labels, hashes = load_dataset(args.trajectories, args.ground_truth)
    labeled = [tid for tid in cases if tid in labels]
    ids = args.ids or labeled
    if len(set(ids)) != len(ids) or set(ids) - set(labeled):
        raise ValueError("Select unique trajectory IDs that exist in the input and have labels")
    if len({safe_name(t) for t in ids}) != len(ids) or SUPERSEDED in {safe_name(t) for t in ids}:
        raise ValueError("Trajectory IDs collide as folder names")
    redo = args.regenerate or []
    if set(redo) - set(ids):
        raise ValueError("--regenerate takes IDs this run covers (rerun the same command plus --regenerate)")
    if type(args.max_attempts) is not int or args.max_attempts < 1:
        raise ValueError("--max-attempts must be at least 1")
    model = MODELS[args.model]
    roles = resolve_roles(args.domain, args.prose_roles, args.policy_roles)
    policy, tools = domain_inputs(args.domain, args.policy)
    prompt = TEMPLATE.read_text(encoding="utf-8")
    # Everything that changes what the model sees, plus the variant so a step-decoy and
    # a presentation-change work directory can never be mixed up. The code hashes and
    # Claude Code version are recorded per case instead (as in step_decoy), so a code
    # fix does not discard paid generations; release rebuilds each case and refuses drift.
    settings = dict(variant=VARIANT, provider=PROVIDER, model=args.model, model_id=model, effort=args.effort,
                    domain=args.domain, trajectories=stored(args.trajectories),
                    ground_truth=stored(args.ground_truth), inputs=hashes,
                    policy=stored(ROOT / (args.policy or get_domain_config(args.domain).default_policy_path)),
                    policy_sha256=digest(policy.encode()), prompt_sha256=digest((SYSTEM + "\n" + prompt).encode()),
                    tools_sha256=digest(json.dumps(tools, sort_keys=True).encode()),
                    output_schema_sha256=digest(json.dumps(SCHEMA, sort_keys=True).encode()),
                    max_attempts=args.max_attempts, ids=ids, **roles)
    args.work.mkdir(parents=True, exist_ok=True)
    config = args.work / "config.json"
    # config_roles fills in the roles of a config written before they were recorded.
    if config.exists() and {**read(config), **config_roles(read(config))} != settings:
        raise ValueError("Work directory belongs to a different configuration. Choose a fresh --work.")
    if not config.exists():
        write(config, settings)
    # Regeneration (RELEASE_PLAN: fix a failed or rejected case, never exclude it). The
    # settings are unchanged, so the lock above still holds; the old attempt is moved to
    # _superseded/<id>/<n>/ and the loop below generates the case afresh. Every requested
    # ID is checked against the attempt cap before anything is moved.
    capped = [tid for tid in redo if attempts_used(args.work, tid) >= args.max_attempts]
    if capped:
        raise ValueError(f"Attempt cap reached ({args.max_attempts} per case, locked in config.json) for "
                         f"{', '.join(capped)}; these cases cannot be regenerated. Report them as not "
                         f"releasable for this model rather than raising the cap.")
    for tid in redo:
        case_dir = args.work / safe_name(tid)
        if case_dir.exists():
            history = args.work / SUPERSEDED / safe_name(tid)
            history.mkdir(parents=True, exist_ok=True)
            attempt = 1 + max((int(p.name) for p in history.iterdir() if p.name.isdigit()), default=0)
            case_dir.rename(history / str(attempt))
            print(f"{tid}: previous attempt kept as {stored(history / str(attempt))}", flush=True)
    print(f"{len(cases)} trajectories, {len(labeled)} labeled, {len(ids)} selected", flush=True)
    version = None
    for tid in ids:
        case_dir = args.work / safe_name(tid)
        if case_dir.exists():  # resume: a finished case is never redone (or re-billed)
            continue
        case, label = cases[tid], labels[tid]
        try:
            root = root_failure(label)  # the label's root_cause, not simply failures[0]
        except (KeyError, StopIteration):
            root = None
        allowed = editable_steps(case, label, roles)
        generation = None
        if root is None:
            proposal = {"decision": "NO_VALID_EDIT", "reason": "The label has no root-cause failure"}
        elif not allowed:
            proposal = {"decision": "NO_VALID_EDIT", "reason": "The trajectory has no editable steps"}
        else:
            message = render(prompt, DOMAIN=args.domain, POLICY=policy, TOOLS=tools or "none provided",
                             TASK_INSTRUCTION=instruction(case) or "not provided; see the first steps",
                             ROOT_FAILURE=root,
                             OTHER_FAILURES=lines(f for f in label["failures"] if f is not root),
                             TRAJECTORY=lines({"step": n, "event": e} for n, e in enumerate(case["events"], 1)),
                             EDITABLE_STEPS=lines({"step": n, "role": role(case["events"][n - 1]), "kinds": k}
                                                  for n, k in allowed.items()))
            version = version or claude_version(args.claude_bin)
            try:
                proposal, meta = ask_claude(args.claude_bin, model, args.effort, message, args.timeout)
            except ValueError as exc:
                raise ValueError(f"Trajectory {tid}: {exc}")
            # generator_sha256 hashes this file; helpers_sha256 the step_decoy code it reuses.
            generation = dict(meta, claude_version=version, generator_sha256=digest(Path(__file__).read_bytes()),
                              helpers_sha256=digest(Path(step_decoy.__file__).read_bytes()))
        # Build the case in a staging folder and rename it into place at the end, so a
        # crash never leaves a half-written case that resume would then skip.
        with tempfile.TemporaryDirectory(dir=args.work) as tmp:
            staging = Path(tmp) / case_dir.name
            staging.mkdir()
            if generation:
                write(staging / "generation.json", generation)
            write(staging / "proposal.json", proposal)
            if proposal.get("decision") == "EDIT":
                try:
                    events, changes = apply_edits(case, label, proposal, roles)
                except ValueError as exc:
                    # Keep the model's output for review instead of failing the batch.
                    write(staging / "invalid.json", {"error": str(exc),
                                                     "violations": getattr(exc, "violations", [])})
                else:
                    write(staging / "events.json", events)
                    # The reviewer copies events_sha256 into their review (see release).
                    write(staging / "validation.json", {
                        "passed": True, "events_sha256": digest((staging / "events.json").read_bytes()),
                        "changes_applied": changes})
            elif proposal.get("decision") != "NO_VALID_EDIT" or not str(proposal.get("reason") or "").strip():
                raise ValueError(f"Invalid decision on trajectory {tid}")
            staging.rename(case_dir)
        if (case_dir / "invalid.json").exists():
            status = "INVALID"
        elif proposal["decision"] == "EDIT":
            status = f"EDIT ({len(proposal['edits'])} edits)"
        else:
            status = proposal["decision"]
        print(f"{tid}: {status}", flush=True)


def attempts_used(work, tid):
    """Finished attempts at a case: the superseded ones plus the current one, if any.
    (A case folder only exists once its attempt finished; see the atomic rename.)"""
    history = work / SUPERSEDED / safe_name(tid)
    earlier = sum(1 for p in history.iterdir() if p.name.isdigit()) if history.is_dir() else 0
    return earlier + (1 if (work / safe_name(tid)).is_dir() else 0)


def superseded(work, tid):
    """Earlier attempts of a regenerated case, oldest first, for the audit."""
    history = work / SUPERSEDED / safe_name(tid)
    attempts = sorted((p for p in history.iterdir() if p.name.isdigit()), key=lambda p: int(p.name)) \
        if history.is_dir() else []
    out = []
    for path in attempts:
        record = {"attempt": int(path.name)}
        for name in ("proposal", "generation", "invalid"):
            if (path / f"{name}.json").exists():
                record[name] = read(path / f"{name}.json")
        out.append(record)
    return out


def release(args):
    """Mirror of step_decoy.release, with RELEASE_PLAN's gate: every labeled trajectory
    must be generated, valid and accepted, or nothing is released. All problems are
    reported together so one pass of regeneration/review can fix them."""
    config = read(args.work / "config.json")
    if (config.get("variant") != VARIANT or config.get("provider") != PROVIDER
            or MODELS.get(config.get("model")) != config.get("model_id")):
        raise ValueError("Work directory was not generated by the presentation-change generator")
    sources, cases, labels, hashes = load_dataset(ROOT / config["trajectories"], ROOT / config["ground_truth"])
    if hashes != config["inputs"]:
        raise ValueError("Input trajectories or labels changed since generation")
    if not re.fullmatch(r"v\d+\.\d+\.\d+", args.version):
        raise ValueError("Expected a version such as v1.0.0")
    out = args.out or VERSIONS / DATASETS.get(config["domain"], config["domain"]) / VARIANT
    # One release line per generator model: <dataset>/presentation_change/<haiku|sonnet|opus>/vX.Y.Z
    target = Path(out) / config["model"] / args.version
    if target.exists():
        raise ValueError(f"Release already exists: {target}")
    # RELEASE_PLAN: all cases per transformation. A pilot work directory (--ids subset)
    # can never be released.
    labeled = [tid for tid in cases if tid in labels]
    if set(config["ids"]) != set(labeled):
        raise ValueError(f"A release needs every labeled trajectory: this work directory covers "
                         f"{len(config['ids'])} of {len(labeled)}. Generate the full set in a fresh --work.")
    reviews, roles = read(args.reviews), config_roles(config)
    cap = config["max_attempts"]
    problems, replaced, truth, audit = [], {}, [], {}
    for tid in config["ids"]:
        case_dir = args.work / safe_name(tid)
        if not (case_dir / "proposal.json").exists():
            problems.append(f"{tid}: not generated yet; rerun generate")
            continue
        p = read(case_dir / "proposal.json")
        record = audit[tid] = {"proposal": p}
        if (case_dir / "generation.json").exists():
            record["generation"] = read(case_dir / "generation.json")
        record["superseded"] = superseded(args.work, tid)
        used = len(record["superseded"]) + 1
        record["attempt"] = used
        if used > cap:  # only possible if attempts were moved by hand
            problems.append(f"{tid}: {used} attempts exceed the cap of {cap}")
            continue
        # How to fix a blocked case: regenerate it, unless it has used every attempt.
        regen = (f"regenerate it (generate ... --regenerate {tid}; attempt {used} of {cap})" if used < cap
                 else f"attempt cap reached ({cap} of {cap}); it cannot be regenerated, so this "
                      f"model's transformation is not releasable under RELEASE_PLAN")
        if (case_dir / "invalid.json").exists():
            problems.append(f"{tid}: proposal failed validation ({read(case_dir / 'invalid.json')['error']}); {regen}")
            continue
        if p.get("decision") != "EDIT":
            problems.append(f"{tid}: {p.get('decision')} ({p.get('reason')}); {regen}")
            continue
        events_sha256 = digest((case_dir / "events.json").read_bytes())
        review = reviews.get(tid)
        if (not isinstance(review, dict) or review.get("decision") not in ("accept", "reject")
                or not all(isinstance(review.get(k), str) and review[k].strip() for k in REVIEW_FIELDS)):
            problems.append(f"{tid}: needs a signed review with decision (accept/reject), "
                            f"{', '.join(REVIEW_FIELDS)}")
            continue
        if review["events_sha256"] != events_sha256:
            problems.append(f"{tid}: the review approves different events (written before a regeneration?); "
                            f"review the current events.json ({events_sha256})")
            continue
        record["review"] = review
        if review["decision"] != "accept":
            problems.append(f"{tid}: rejected by {review['reviewer']}; {regen}")
            continue
        # Rebuild from the proposal with the current code and refuse any drift.
        try:
            events, changes = apply_edits(cases[tid], labels[tid], p, roles)
        except ValueError as exc:
            problems.append(f"{tid}: no longer valid under the current code ({exc}); {regen}")
            continue
        if events != read(case_dir / "events.json"):
            problems.append(f"{tid}: candidate changed since generation; {regen}")
            continue
        # The root failure, kept for compare (step_decoy keeps original_root the same way);
        # steps never move here, so it is both the original and the variant step.
        root = root_failure(labels[tid])
        record.update(events_sha256=events_sha256, changes_applied=changes,
                      root={"step_number": root["step_number"], "failure_category": root["failure_category"]})
        replaced[tid] = events
        # Labels are unchanged: presentation edits never move a step. original_step_number
        # is added only so the file has the same shape as a step-decoy release.
        label = deepcopy(labels[tid])
        for failure in label["failures"]:
            failure["original_step_number"] = failure["step_number"]
        truth.append(label)
    if problems:
        raise ValueError(f"Not releasable: RELEASE_PLAN requires all {len(config['ids'])} cases accepted; "
                         f"{len(problems)} need attention:\n  " + "\n  ".join(problems))

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
        staging = Path(tmp) / args.version
        artifacts = {}
        # Each input file, in its own layout and relative path, with every trajectory replaced.
        for rel, source in sources.items():
            if any(t["id"] in replaced for t in source["trajectories"]):
                path = staging / "trajectories" / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(dump_source(source, replaced), encoding="utf-8")
        for name, obj in [("ground_truth.json", truth), ("audit.json", audit)]:
            write(staging / name, obj)
        for path in sorted(p for p in staging.rglob("*") if p.is_file()):
            artifacts[path.relative_to(staging).as_posix()] = digest(path.read_bytes())
        runs = [r["generation"] for r in audit.values() if "generation" in r]
        earlier = [s["generation"] for r in audit.values() for s in r["superseded"] if "generation" in s]
        # step_decoy's manifest keys, plus helpers_sha256 (the shared code this generator
        # imports) and regenerated (attempts per regenerated case, for transparency).
        write(staging / "manifest.json", dict(
            domain=config["domain"], variant=VARIANT, version=args.version,
            parent=dict(trajectories=config["trajectories"], ground_truth=config["ground_truth"], sha256=hashes),
            generator={**config, **roles}, artifact_sha256=artifacts,
            generator_sha256=sorted({r["generator_sha256"] for r in runs}),
            helpers_sha256=sorted({r["helpers_sha256"] for r in runs}),
            claude_versions=sorted({r["claude_version"] for r in runs}),
            # Every paid attempt, superseded ones included.
            total_cost_usd=round(sum(r.get("total_cost_usd") or 0 for r in runs + earlier), 6),
            accepted_ids=list(replaced), attempted_count=len(audit),
            regenerated={tid: len(r["superseded"]) for tid, r in audit.items() if r["superseded"]}))
        staging.rename(target)
    print(target)


def predictions(path):
    """{task_id: (step, category)} from a judge run1.json report.

    As in step_decoy.predictions, each report must hold exactly one decision per
    trajectory. The judge writes the category as an integer FailureCase code under
    failure_case; it is normalized with the judge's own convert_to_failure_case, the
    same function the judge uses to read ground-truth category names, so a code and a
    name for the same category compare equal."""
    results = {}
    for row in read(path)["detailed_results"]:
        tid = str(row["task_id"])
        if tid in results or len(row["failures"]) != 1:
            raise ValueError("Expected one judge decision per trajectory in each run")
        failure = row["failures"][0]
        results[tid] = (int(failure["step_number"]), convert_to_failure_case(failure.get("failure_case")).name)
    return results


# Outcomes for a case the clean run localized correctly, by what changed in the
# variant's verdict relative to the clean verdict. Any change counts as a flip.
FLIPS = ("step_moved", "category_changed", "step_and_category_changed")


def compare(args):
    """Verdict-flip rate between a clean and a presentation-change judge run.

    Mirrors step_decoy.compare: paired cases are those the clean run localized
    correctly (clean step == annotated root step); missing predictions and clean
    misses are counted separately and left out of the rate. Steps never move in a
    presentation change, so for each paired case the variant's verdict is compared
    with the clean verdict on both step and category:
      same_step_same_category | step_moved | category_changed (same step) |
      step_and_category_changed.
    verdict_flip_rate = paired cases with any change / paired cases. A category
    change with the step unchanged is a flip too. The same rate is also reported on
    the stricter subset whose clean category also matched the annotation."""
    clean, variant = predictions(args.clean), predictions(args.variant)
    counts, outcomes, details = Counter(), {}, {}
    strict_paired = strict_flipped = 0
    for tid, rec in read(args.audit).items():
        if "root" not in rec:  # not a released case (release only writes root for accepted ones)
            continue
        root_step = rec["root"]["step_number"]
        root_category = convert_to_failure_case(rec["root"]["failure_category"]).name
        if tid not in clean or tid not in variant:
            outcome = "missing_prediction"
        elif clean[tid][0] != root_step:
            outcome = "clean_root_missed"
        else:
            step_same, category_same = variant[tid][0] == clean[tid][0], variant[tid][1] == clean[tid][1]
            outcome = ("same_step_same_category" if step_same and category_same else
                       "category_changed" if step_same else
                       "step_moved" if category_same else "step_and_category_changed")
            if clean[tid][1] == root_category:
                strict_paired += 1
                strict_flipped += outcome in FLIPS
        outcomes[tid] = outcome
        counts[outcome] += 1
        details[tid] = {"root": [root_step, root_category], "clean": clean.get(tid), "variant": variant.get(tid)}
    paired = counts["same_step_same_category"] + sum(counts[k] for k in FLIPS)
    flipped = sum(counts[k] for k in FLIPS)
    print(json.dumps({
        "counts": counts,
        "paired_clean_correct": paired,
        "verdict_flip_rate": flipped / paired if paired else None,
        "flipped_by_type": {k: counts[k] for k in FLIPS},
        "paired_clean_fully_correct": strict_paired,
        "verdict_flip_rate_fully_correct": strict_flipped / strict_paired if strict_paired else None,
        "cases": outcomes,
        "predictions": details,
    }, indent=2))


def quote(text):
    """Text as a markdown blockquote, every line prefixed so multi-line messages stay inside it."""
    return "\n".join("> " + line if line else ">" for line in str(text).split("\n"))


def cell(text):
    """Text safe inside a markdown table cell."""
    return str(text).replace("|", "\\|").replace("\n", " ")


def review_sheet(args):
    """Write <work>/review_sheet.md and <work>/reviews.template.json for the human review.

    Mirrors the step-decoy review sheets (header, then one section per trajectory with
    the root failure, the model's rationale, a table of changes and their checks), with
    one deliberate difference: no suggested decision. Python has already checked
    structure and values; what is left for a person is whether each paraphrase means
    exactly the same thing, and a pre-filled "accept" invites skipping that. Prose
    edits are shown before/after in full instead, and edits on annotated failure steps
    are flagged. The template carries each case's events_sha256, so the reviewer only
    fills decision, reviewer and reason. An existing reviews.json is never modified; the
    sheet reports which of its reviews are current, stale or missing."""
    config = read(args.work / "config.json")
    if config.get("variant") != VARIANT:
        raise ValueError("Work directory was not generated by the presentation-change generator")
    _, cases, labels, _ = load_dataset(ROOT / config["trajectories"], ROOT / config["ground_truth"])
    reviews_path = args.reviews or args.work / "reviews.json"
    on_file = read(reviews_path) if reviews_path.exists() else {}
    cap = config["max_attempts"]
    sections, template, tally = [], {}, {"ready": 0, "invalid": 0, "no edit": 0, "missing": 0}
    review_state = {"current": 0, "stale": 0, "none": 0}

    def failure_line(f):
        return f"step {f['step_number']} ({f['failure_category']}). {f['step_reason']}"

    for tid in config["ids"]:
        case_dir, out = args.work / safe_name(tid), [f"## Trajectory {tid}"]
        sections.append(out)
        if not (case_dir / "proposal.json").exists():
            out.append("**Status:** not generated yet; rerun generate.")
            tally["missing"] += 1
            continue
        label, events = labels[tid], cases[tid]["events"]
        used = attempts_used(args.work, tid)
        try:
            root = root_failure(label)
        except (KeyError, StopIteration):
            root = None
        out.append(f"**Attempt:** {used} of {cap}")
        out.append(f"**Root failure:** {failure_line(root)}" if root else "**Root failure:** none in the label")
        out += [f"**Other failure:** {failure_line(f)}" for f in label["failures"] if f is not root]
        next_step = (f"regenerate it (`generate ... --regenerate {tid}`)" if used < cap
                     else "attempt cap reached; it cannot be regenerated")
        proposal = read(case_dir / "proposal.json")
        if (case_dir / "invalid.json").exists():
            out.append(f"**Status:** INVALID, not reviewable: {read(case_dir / 'invalid.json')['error']}. "
                       f"Next: {next_step}.")
            tally["invalid"] += 1
            continue
        if proposal.get("decision") != "EDIT":
            out.append(f"**Status:** {proposal.get('decision')}, not reviewable: {proposal.get('reason')}. "
                       f"Next: {next_step}.")
            tally["no edit"] += 1
            continue
        tally["ready"] += 1
        validation = read(case_dir / "validation.json")
        sha = digest((case_dir / "events.json").read_bytes())
        failing = failure_steps(label)
        out.append(f"**Model's rationale:** {proposal['rationale']}")
        out.append(f"**Preservation evidence (model's claim):** {proposal['preservation_evidence']}")
        out += ["", "| Step | Kind | Change | Checks |", "|---|---|---|---|"]
        for c in validation["changes_applied"]:
            who = role(events[c["step"] - 1])
            if c["kind"] == "formatting":
                change = f"{', '.join(c['fields'])} re-laid out (layout `{c['layout']}`, key order `{c['key_order']}`)"
            else:
                change = f"{who} message {'paraphrased' if c['kind'] == 'wording' else 'markdown only'} (below)"
            flag = (" ⚠ **root failure step**" if root and c["step"] == root["step_number"]
                    else " ⚠ **annotated failure step**" if c["step"] in failing else "")
            out.append(f"| {c['step']} | {c['kind']} | {cell(change)} | passed{flag} |")
        for c in validation["changes_applied"]:
            if c["kind"] in PROSE_KINDS:
                out += ["", f"**Step {c['step']}, {c['kind']}.** Model's reason: {c['reason']}",
                        "", "Before:", quote(c["before"]), "", "After:", quote(c["after"])]
        review = on_file.get(tid)
        if not isinstance(review, dict):
            state, review_state["none"] = "none on file", review_state["none"] + 1
        elif review.get("events_sha256") == sha:
            state = f"current ({review.get('decision') or 'no decision'} by {review.get('reviewer') or '?'})"
            review_state["current"] += 1
        else:
            state = "**STALE**: written for different events (regenerated since?); review again"
            review_state["stale"] += 1
        out += ["", f"**events_sha256:** `{sha}`", f"**Review on file:** {state}"]
        template[tid] = {"decision": "", "reviewer": "", "reason": "", "events_sha256": sha}

    header = [
        f"# Review sheet: {stored(args.work)}", "",
        f"Model `{config['model_id']}`, effort `{config['effort']}`, domain `{config['domain']}`, "
        f"attempt cap {cap} per case.",
        f"Cases: {tally['ready']} ready for review, {tally['invalid']} invalid, {tally['no edit']} with no edit, "
        f"{tally['missing']} not generated (of {len(config['ids'])}; release needs all {len(config['ids'])} accepted).",
        f"Reviews on file ({stored(reviews_path)}): {review_state['current']} current, "
        f"{review_state['stale']} stale, {review_state['none']} missing.", "",
        "Python has already checked structure: locked steps, tool names, call IDs, JSON values, every digit "
        "token, and that emphasis only adds markdown. Your review is about meaning. For each case, check:",
        "- each paraphrase says exactly what the original said: same requests, claims, answers and mistakes;",
        "- every annotated failure (⚠ rows) is exactly as clear and as wrong as before; nothing is softened, "
        "hedged, explained or corrected;",
        "- emphasis does not make a correct step look doubtful or a wrong step look endorsed.", "",
        "Fill `decision` (accept/reject), `reviewer` and `reason` for every case in `reviews.template.json`, "
        "then save it as `reviews.json`. Keep `events_sha256` as written: it ties your review to these exact "
        "events. Blanks, stale hashes and rejections are refused at release.",
    ]
    sheet, template_path = args.work / "review_sheet.md", args.work / "reviews.template.json"
    sheet.write_text("\n".join(header) + "\n\n" + "\n\n".join("\n".join(s) for s in sections) + "\n",
                     encoding="utf-8")
    write(template_path, template)
    print(f"{sheet}\n{template_path}\n" + header[3] + "\n" + header[4])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cmds = parser.add_subparsers(dest="command", required=True)
    gen = cmds.add_parser("generate", help="Propose and save reviewable candidates")
    gen.add_argument("--domain", required=True, choices=list_domains(),
                     help="AgentRx domain; selects the policy and tool descriptions")
    gen.add_argument("--trajectories", type=Path, required=True,
                     help="Trajectory file or folder in any layout AgentRx reads")
    gen.add_argument("--ground-truth", type=Path, required=True, help="Labels with root_cause and failures")
    gen.add_argument("--policy", help="Policy file (default: the domain's policy)")
    gen.add_argument("--prose-roles", nargs="+", metavar="ROLE",
                     help="Roles whose messages may be reworded, as they appear in the trajectories "
                          "(default for tau: assistant; required for other domains); locked in config.json")
    gen.add_argument("--policy-roles", nargs="*", metavar="ROLE",
                     help="Roles that carry the policy and stay byte-identical "
                          "(default for tau: system; none otherwise); locked in config.json")
    gen.add_argument("--work", type=Path, required=True)
    gen.add_argument("--ids", nargs="+", help="Trajectory IDs (default: every labeled trajectory)")
    gen.add_argument("--model", required=True, choices=MODELS,
                     help="Generator model: " + ", ".join(f"{k}={v}" for k, v in MODELS.items()))
    gen.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"],
                     help="Claude Code effort level (default: the model's own default)")
    gen.add_argument("--claude-bin", default=os.getenv("CLAUDE_BIN", "claude"),
                     help="Claude Code executable (default: $CLAUDE_BIN or claude)")
    gen.add_argument("--timeout", type=int, default=600)
    gen.add_argument("--regenerate", nargs="+", metavar="ID",
                     help="Redo these cases (failed validation or rejected in review); "
                          "the previous attempt is kept under _superseded/")
    gen.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS,
                     help=f"Attempts allowed per case, first one included (default {DEFAULT_MAX_ATTEMPTS}); "
                          "locked in config.json")
    pub = cmds.add_parser("release", help="Freeze a fully reviewed work directory (all cases accepted)")
    pub.add_argument("--work", type=Path, required=True)
    pub.add_argument("--reviews", type=Path, required=True)
    pub.add_argument("--version", required=True)
    pub.add_argument("--out", type=Path,
                     help="Release root (default: data/benchmark_versions/<dataset>/presentation_change)")
    sheet = cmds.add_parser("review-sheet", help="Write a review sheet and a reviews template for a work directory")
    sheet.add_argument("--work", type=Path, required=True)
    sheet.add_argument("--reviews", type=Path,
                       help="Existing reviews to check for stale or missing entries (default: <work>/reviews.json)")
    cmp = cmds.add_parser("compare", help="Verdict-flip rate between matched clean and variant run1.json reports")
    for key in ("audit", "clean", "variant"):
        cmp.add_argument("--" + key, required=True, type=Path)
    args = parser.parse_args()
    try:
        {"generate": generate, "release": release, "review-sheet": review_sheet,
         "compare": compare}[args.command](args)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"{args.command}: {exc}\n")


if __name__ == "__main__":
    main()
