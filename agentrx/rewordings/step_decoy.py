"""Generate step-decoy trajectories for AgentRx, review them, and freeze accepted cases.

A decoy is a short run of inserted events that should distract a root-cause
judge without changing the real cause. The model adds up to three of each kind:
noise replays an earlier exchange unchanged; a red herring inserts a failed
attempt (one value slipped, an error response) directly before an exchange, so
the original reads as the corrected retry.

Nothing here is specific to one domain. --domain selects the policy and the
tool or agent descriptions from AgentRx's domain registry, the input can be any
trajectory JSON layout AgentRx reads, and the model decides which exchanges are
safe to replay or fail. Python copies and edits events, enforces structure
learned from the input (role transitions, call-ID shape, step counters), and
writes each variant back in its input's layout. No IR conversion is used.
Labels number steps by 1-based event position, as in the AgentRx baselines.
"""

import argparse
import hashlib
import json
import random
import re
import string
import subprocess
import tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path

from agentrx.invariants.domain_registry import get_domain_config, list_domains
from agentrx.rewordings import copilot

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / "data/benchmark_versions"
TEMPLATE = Path(__file__).with_name("step_decoy_prompt.txt")
# Release folders of the existing baselines; other domains use their own name.
DATASETS = {"tau": "tau_retail", "magentic": "magentic_one"}
# The layouts AgentRx's loader accepts (agentrx/ir/trajectory_ir.py), re-implemented
# here so each file's own layout can be written back unchanged.
EVENT_KEYS = ("traj", "events", "messages", "trajectory", "spans")
ID_KEYS = ("trajectory_id", "task_id", "traceId")
ROLE_KEYS = ("role", "source", "speaker", "agent", "name")
CONTENT_KEYS = ("content", "message", "text", "output")
CALL_ID_KEYS = ("id", "tool_call_id", "call_id")  # links a tool call to its result in chat formats
ERROR_TEXT = re.compile(r"\b(error|exception|traceback|not found|failed|denied|invalid|404)\b", re.I)
# The generator model comes from $STEP_DECOY_COPILOT_MODEL (default claude-sonnet-5.5)
# and is run through the GitHub Copilot CLI, as AgentRx's judge is; see copilot.py.
VARIANT = "step_decoy"
PROVIDER = copilot.PROVIDER
MAX_PER_KIND = 3  # decoys of each kind per trajectory
MAX_SPAN = 3  # consecutive events one decoy copies
# The template carries the instructions and <<PLACEHOLDER>> slots for domain data.
SYSTEM = ("You design step decoys for evaluating root-cause localization in agent trajectories. "
          "Follow the instructions in the user message and answer only through the structured output.")
# The schema is flat (no top-level anyOf), so copilot.check_schema() checks only types
# and enums; Python checks which fields each decision and decoy kind requires.
DECOY = {"type": "object", "additionalProperties": False, "required": ["kind"], "properties": {
    "kind": {"type": "string", "enum": ["noise", "red_herring"]},
    "source_start": {"type": "integer"}, "source_end": {"type": "integer"},
    "insert_after_step": {"type": "integer"},
    "find": {"type": "string"}, "replace_with": {"type": "string"}, "response": {"type": "string"}}}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["decision"], "properties": {
    "decision": {"type": "string", "enum": ["INSERT", "NO_VALID_DECOY"]},
    "insertions": {"type": "array", "items": DECOY},
    "rationale": {"type": "string"}, "distinguishing_evidence": {"type": "string"},
    "reason": {"type": "string"}}}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stored(path):
    """Record a path relative to the project when possible, so configs are portable."""
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def safe_name(tid):
    return re.sub(r"[^A-Za-z0-9._-]", "_", tid)


# ---------- Input layouts ----------

def events_key(obj):
    return next((k for k in EVENT_KEYS if isinstance(obj.get(k), list)), None)


def first_id(obj):
    if isinstance(obj, dict):
        for key in ID_KEYS:
            if obj.get(key) is not None and str(obj[key]).strip():
                return str(obj[key]).strip()
    return None


def parse_source(path):
    """Read one file as AgentRx does; return its layout and its trajectories."""
    raw = path.read_text(encoding="utf-8-sig").strip()
    try:
        data, stream = json.loads(raw), False
    except json.JSONDecodeError:
        data, stream, i, decoder = [], True, 0, json.JSONDecoder()
        try:
            while i < len(raw):
                if raw[i].isspace():
                    i += 1
                    continue
                obj, i = decoder.raw_decode(raw, i)
                data.append(obj)
        except json.JSONDecodeError:
            raise ValueError(f"{path}: not JSON, JSONL or concatenated JSON objects")

    def trajectory(container, key, events, fallback, index):
        tid = first_id(container) or next((first_id(e) for e in events if first_id(e)), None) or fallback
        return dict(id=tid, key=key, events=events, container=container, index=index)

    if isinstance(data, dict):
        key = events_key(data)
        if key:  # one trajectory wrapped in an object
            return dict(layout="object", stream=False, data=data), [trajectory(data, key, data[key], path.stem, None)]
    elif data and all(isinstance(x, dict) for x in data):
        keys = [events_key(x) for x in data]
        if not any(keys):  # one trajectory as a bare list or stream of events
            return dict(layout="events", stream=stream, data=data), [trajectory(None, None, data, path.stem, None)]
        if all(keys):  # many trajectories, each wrapped in an object
            return dict(layout="wrappers", stream=stream, data=data), [
                trajectory(w, k, w[k], f"{path.stem}__{i + 1}", i) for i, (w, k) in enumerate(zip(data, keys))]
    raise ValueError(f"{path}: unrecognized trajectory layout (markdown is not supported)")


def dump_source(source, replaced):
    """Serialize a source in its own layout, keeping only trajectories in `replaced`."""
    data, trajectories = deepcopy(source["data"]), source["trajectories"]
    if source["layout"] == "object":
        data[trajectories[0]["key"]] = replaced[trajectories[0]["id"]]
    elif source["layout"] == "events":
        data = replaced[trajectories[0]["id"]]
    else:
        data = [{**data[t["index"]], t["key"]: replaced[t["id"]]} for t in trajectories if t["id"] in replaced]
    if source["stream"]:
        return "".join(json.dumps(obj, ensure_ascii=False) + "\n" for obj in data)
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def load_dataset(trajectories, ground_truth):
    """Load a trajectory file or folder (as run.py accepts) and its labels."""
    path = Path(trajectories).resolve()
    if path.is_dir():
        files = sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in (".json", ".jsonl"))
        base = path
    else:
        files, base = [path], path.parent
    if not files:
        raise ValueError(f"No .json or .jsonl trajectory files in {path}")
    sources, cases, hashes = {}, {}, {}
    for file in files:
        rel = file.relative_to(base).as_posix()
        source, trajectories_ = parse_source(file)
        sources[rel] = dict(source, trajectories=trajectories_)
        hashes[rel] = digest(file.read_bytes())
        for t in trajectories_:
            if t["id"] in cases:
                raise ValueError(f"Duplicate trajectory ID {t['id']} in {rel}")
            cases[t["id"]] = dict(t, source=rel)
    gt_path = Path(ground_truth).resolve()
    labels = {str(label["trajectory_id"]): label for label in read(gt_path)}
    return sources, cases, labels, dict(files=hashes, ground_truth=digest(gt_path.read_bytes()))


def root_failure(label):
    return next(f for f in label["failures"]
                if str(f["failure_id"]) == str(label["root_cause"]["failure_id"]))


def find_key(obj, key):
    """First string value under `key`, searched depth-first (how AgentRx finds instructions)."""
    if isinstance(obj, dict):
        if isinstance(obj.get(key), str) and obj[key].strip():
            return obj[key].strip()
        obj = list(obj.values())
    if isinstance(obj, list):
        return next((v for v in (find_key(x, key) for x in obj) if v), None)
    return None


def instruction(case):
    scope = case["container"] if case["container"] is not None else case["events"]
    return find_key(scope, "instruction") or find_key(scope, "task") or ""


# ---------- Structure learned from the input ----------

def role(event):
    return next((str(event[k]) for k in ROLE_KEYS if isinstance(event.get(k), str)), "?")


def signature(event):
    return role(event) + ("+calls" if event.get("tool_calls") or event.get("function_call") else "")


def transitions(cases):
    """Consecutive role pairs seen in the dataset; insertions may only create these."""
    return {(signature(a), signature(b)) for c in cases.values() for a, b in zip(c["events"], c["events"][1:])}


def content_key(event):
    return next((k for k in CONTENT_KEYS if k in event), None)


def error_examples(cases, limit=12):
    """Short responses that report a failure, to show the model this system's error style."""
    found = {}
    for case in cases.values():
        for event in case["events"][1:]:
            text = event.get(content_key(event) or "")
            if isinstance(text, str) and ERROR_TEXT.search(text[:300]):
                found.setdefault(text.strip()[:300], role(event))
    return [dict(role=r, content=t) for t, r in sorted(found.items(), key=lambda x: (len(x[0]), x[0]))[:limit]]


def counters(events):
    """Integer fields that number events in order (Tau's `index`); renumbered in variants."""
    if len(events) < 2:
        return {}
    return {k: v for k, v in events[0].items()
            if type(v) is int and all(type(e.get(k)) is int and e[k] == v + n for n, e in enumerate(events))}


def replace_text(obj, old, new):
    """Replace text inside every string value; return the result and the number of hits."""
    if isinstance(obj, str):
        return obj.replace(old, new), obj.count(old)
    if isinstance(obj, (list, dict)):
        items = obj.items() if isinstance(obj, dict) else enumerate(obj)
        done = {k: replace_text(v, old, new) for k, v in items}
        hits = sum(n for _, n in done.values())
        return ({k: v for k, (v, _) in done.items()} if isinstance(obj, dict) else [v for v, _ in done.values()]), hits
    return obj, 0


def call_ids(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in CALL_ID_KEYS and isinstance(v, str):
                yield v
            else:
                yield from call_ids(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from call_ids(x)


def set_call_ids(obj, mapping):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in CALL_ID_KEYS and isinstance(v, str) and v in mapping:
                obj[k] = mapping[v]
            else:
                set_call_ids(v, mapping)
    elif isinstance(obj, list):
        for x in obj:
            set_call_ids(x, mapping)


def fresh_id(value, rng):
    """A new ID shaped like the old one (same prefix and character classes), so copies blend in."""
    head, sep, body = value.rpartition("_")
    hex_id = set(body) <= set("0123456789abcdef-") and bool(set(body) & set("abcdef"))

    def swap(ch):
        if hex_id and ch != "-":
            return rng.choice("0123456789abcdef")
        for pool in (string.digits, string.ascii_lowercase, string.ascii_uppercase):
            if ch in pool:
                return rng.choice(pool)
        return ch
    return head + sep + "".join(swap(ch) for ch in body)


# ---------- Building a variant ----------

def materialize(case, label, proposal, allowed):
    """Insert the proposed decoys; return the events, remapped label, step map and insertions."""
    events = case["events"]
    root = root_failure(label)["step_number"]
    items = proposal.get("insertions")
    if not isinstance(items, list) or not items or not all(isinstance(i, dict) for i in items):
        raise ValueError("Expected at least one decoy")
    kinds = Counter(i.get("kind") for i in items)
    if any(n > MAX_PER_KIND for n in kinds.values()):
        raise ValueError(f"Use at most {MAX_PER_KIND} decoys of each kind, got {dict(kinds)}")
    for key in ("rationale", "distinguishing_evidence"):
        if not isinstance(proposal.get(key), str) or not proposal[key].strip():
            raise ValueError(f"Missing {key}")
    trace_text = json.dumps(case["container"] if case["container"] is not None else events, ensure_ascii=False)
    taken = set(call_ids(events))

    def step(item, key):
        value = item.get(key)
        if type(value) is not int or not 1 <= value <= len(events):
            raise ValueError(f"{key} must be a step from 1 to {len(events)}")
        return value

    decoys, used = {}, set()
    for item in items:
        kind = item.get("kind")
        start, end = step(item, "source_start"), step(item, "source_end")
        if not start <= end < start + MAX_SPAN:
            raise ValueError(f"A decoy copies 1 to {MAX_SPAN} consecutive events")
        copy = deepcopy(events[start - 1:end])
        if kind == "noise":
            anchor = step(item, "insert_after_step")
            if not end <= anchor < root:
                raise ValueError("Noise replays an earlier exchange after it and before the root failure")
            position = (kind, start, end, anchor)
        elif kind == "red_herring":
            anchor = start - 1
            # Copying the root step would plant an earlier instance of the real mistake.
            if end == start or anchor < 1 or end >= root:
                raise ValueError("A red herring copies a request and its response, both before the root failure")
            find, new, response = (item.get(k) for k in ("find", "replace_with", "response"))
            if not all(isinstance(x, str) and x.strip() for x in (find, new, response)) or find == new:
                raise ValueError("A red herring needs find, a different replace_with, and a response")
            # A value already in the trace could name a real entity, so the request would not fail.
            if new in trace_text:
                raise ValueError(f"replace_with {new!r} appears in the trajectory")
            copy[:-1], hits = replace_text(copy[:-1], find, new)
            if not hits:
                raise ValueError(f"{find!r} does not occur in the request")
            key = content_key(copy[-1])
            if key is None:
                raise ValueError("The response event has no content field")
            copy[-1][key] = response
            position = (kind, start)
        else:
            raise ValueError(f"Unknown decoy kind {kind!r}")
        if position in used:
            raise ValueError("Each decoy may be used once; a red herring needs its own exchange")
        used.add(position)
        # Deterministic, so release can rebuild the same variant.
        rng, renamed = random.Random("/".join(map(str, (case["id"],) + position))), {}
        for old in dict.fromkeys(call_ids(copy)):
            new_id = fresh_id(old, rng)
            while new_id in taken:
                new_id = fresh_id(old, rng)
            taken.add(new_id)
            renamed[old] = new_id
        set_call_ids(copy, renamed)
        decoys.setdefault(anchor, []).append((kind, copy))

    edited, inserted = [], []
    for n, event in enumerate(deepcopy(events), 1):
        edited.append(event)
        # Replays first; a failed attempt sits directly before the exchange it precedes.
        for kind, copy in sorted(decoys.get(n, []), key=lambda d: d[0] == "red_herring"):
            first = len(edited) + 1
            edited += copy
            inserted.append(dict(kind=kind, after_original_step=n, steps=list(range(first, len(edited) + 1))))
    new = {s for i in inserted for s in i["steps"]}
    for n in range(1, len(edited)):
        pair = (signature(edited[n - 1]), signature(edited[n]))
        if (n in new or n + 1 in new) and pair not in allowed:
            raise ValueError(f"Insertion breaks the turn structure at step {n}: {pair[0]} -> {pair[1]}")
    numbering = counters(events)
    for n, event in enumerate(edited):
        event.update({k: offset + n for k, offset in numbering.items()})

    def bare(event):
        return {k: v for k, v in event.items() if k not in numbering}
    if [bare(e) for n, e in enumerate(edited, 1) if n not in new] != [bare(e) for e in events]:
        raise ValueError("Original events changed")
    added = {a: sum(len(c) for _, c in d) for a, d in decoys.items()}
    mapping = {str(i): i + sum(n for a, n in added.items() if a < i) for i in range(1, len(events) + 1)}
    mapped = deepcopy(label)
    for failure in mapped["failures"]:
        # Free-text reasons keep the annotators' numbering; keep the original next to it.
        failure["original_step_number"] = failure["step_number"]
        failure["step_number"] = mapping[str(failure["step_number"])]
    return edited, mapped, mapping, inserted


# ---------- Model call ----------

def lines(items):
    return "\n".join(i if isinstance(i, str) else json.dumps(i, ensure_ascii=False) for i in items) or "none"


def render(template, **values):
    """Fill <<NAME>> placeholders in one pass, so inserted data is never re-substituted."""
    def fill(match):
        value = values[match.group(1)]
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    missing = set(re.findall(r"<<([A-Z_]+)>>", template)) ^ values.keys()
    if missing:
        raise ValueError(f"Prompt placeholders and values differ: {sorted(missing)}")
    return re.sub(r"<<([A-Z_]+)>>", fill, template)


def generator_settings(variant):
    """The generation settings shared by every rewording: provider, and the rewording's
    own model and effort from copilot.model_for / effort_for."""
    return dict(variant=variant, provider=PROVIDER, model=copilot.model_for(variant),
                effort=copilot.effort_for(variant))


def check_generator(config, variant):
    """Refuse a work directory made by another rewording or by the old Claude Code generator."""
    if config.get("provider") != PROVIDER or config.get("variant", variant) != variant or not config.get("model"):
        raise ValueError(f"Work directory was not generated by the Copilot {variant} generator "
                         f"(provider {config.get('provider')!r}); generate it again in a fresh --work")


# ---------- Commands ----------

def domain_inputs(domain, policy_path):
    cfg = get_domain_config(domain)
    policy_path = policy_path or cfg.default_policy_path
    if not policy_path:
        raise ValueError(f"Domain {domain!r} has no default policy; pass --policy")
    return (ROOT / policy_path).read_text(encoding="utf-8"), cfg.tools_structure


def propose(args):
    sources, cases, labels, hashes = load_dataset(args.trajectories, args.ground_truth)
    labeled = [tid for tid in cases if tid in labels]
    ids = args.ids or labeled
    if len(set(ids)) != len(ids) or set(ids) - set(labeled):
        raise ValueError("Select unique trajectory IDs that exist in the input and have labels")
    if len({safe_name(t) for t in ids}) != len(ids):
        raise ValueError("Trajectory IDs collide as folder names")
    generator = generator_settings(VARIANT)
    policy, tools = domain_inputs(args.domain, args.policy)
    prompt = TEMPLATE.read_text(encoding="utf-8")
    # Everything that changes what the model sees. The generator code hash and the
    # Copilot CLI version are recorded per case instead, so a code fix does not
    # discard paid generations; release rebuilds each accepted case and refuses drift.
    settings = dict(**generator, domain=args.domain,
                    trajectories=stored(args.trajectories), ground_truth=stored(args.ground_truth), inputs=hashes,
                    policy=stored(ROOT / (args.policy or get_domain_config(args.domain).default_policy_path)),
                    policy_sha256=digest(policy.encode()), prompt_sha256=digest((SYSTEM + "\n" + prompt).encode()),
                    tools_sha256=digest(json.dumps(tools, sort_keys=True).encode()),
                    output_schema_sha256=digest(json.dumps(SCHEMA, sort_keys=True).encode()), ids=ids)
    args.work.mkdir(parents=True, exist_ok=True)
    config = args.work / "config.json"
    if config.exists() and read(config) != settings:
        raise ValueError("Work directory belongs to a different configuration. Choose a fresh --work.")
    if not config.exists():
        write(config, settings)
    allowed, errors = transitions(cases), error_examples(cases)
    print(f"{len(cases)} trajectories, {len(labeled)} labeled, {len(ids)} selected "
          f"(model {settings['model']}, effort {settings['effort']})", flush=True)
    version = binary = None
    for tid in ids:
        case_dir = args.work / safe_name(tid)
        if case_dir.exists():
            continue
        case, label = cases[tid], labels[tid]
        try:
            root = root_failure(label)
        except (KeyError, StopIteration):
            root = None
        proposal, generation = {"decision": "NO_VALID_DECOY", "reason": "The label has no root-cause failure"}, None
        if root is not None:
            message = render(prompt, DOMAIN=args.domain, POLICY=policy, TOOLS=tools or "none provided",
                             TASK_INSTRUCTION=instruction(case) or "not provided; see the first steps",
                             ROOT_FAILURE=root,
                             TRAJECTORY=lines({"step": n, "event": e} for n, e in enumerate(case["events"], 1)),
                             ROLE_TRANSITIONS=lines(f"{a} -> {b}" for a, b in sorted(allowed)),
                             ERROR_EXAMPLES=lines(errors))
            binary = binary or copilot.binary(args.copilot_bin)
            version = version or copilot.version(binary)
            try:
                proposal, meta = copilot.ask(binary, settings["model"], settings["effort"], SYSTEM, SCHEMA,
                                             message, args.timeout)
            except ValueError as exc:
                raise ValueError(f"Trajectory {tid}: {exc}")
            # generator_sha256 hashes this file; helpers_sha256 the copilot code it uses.
            generation = dict(meta, copilot_version=version, generator_sha256=digest(Path(__file__).read_bytes()),
                              helpers_sha256=digest(Path(copilot.__file__).read_bytes()))
        with tempfile.TemporaryDirectory(dir=args.work) as tmp:
            staging = Path(tmp) / case_dir.name
            staging.mkdir()
            if generation:
                write(staging / "generation.json", generation)
            write(staging / "proposal.json", proposal)
            if proposal.get("decision") == "INSERT":
                try:
                    events, _, mapping, inserted = materialize(case, label, proposal, allowed)
                except ValueError as exc:
                    # Keep the model's output for review instead of failing the batch.
                    write(staging / "invalid.json", {"error": str(exc)})
                else:
                    write(staging / "events.json", events)
                    write(staging / "step_map.json", mapping)
                    write(staging / "insertions.json", inserted)
            elif proposal.get("decision") != "NO_VALID_DECOY" or not str(proposal.get("reason") or "").strip():
                raise ValueError(f"Invalid decision on trajectory {tid}")
            staging.rename(case_dir)
        status = "INVALID" if (case_dir / "invalid.json").exists() else proposal["decision"]
        print(f"{tid}: {status}", flush=True)


def release(args):
    config = read(args.work / "config.json")
    check_generator(config, VARIANT)
    sources, cases, labels, hashes = load_dataset(ROOT / config["trajectories"], ROOT / config["ground_truth"])
    if hashes != config["inputs"]:
        raise ValueError("Input trajectories or labels changed since generation")
    if not re.fullmatch(r"v\d+\.\d+\.\d+", args.version):
        raise ValueError("Expected a version such as v1.0.0")
    out = args.out or VERSIONS / DATASETS.get(config["domain"], config["domain"]) / VARIANT
    # <dataset>/step_decoy/vX.Y.Z; the model is recorded in the manifest.
    target = Path(out) / args.version
    if target.exists():
        raise ValueError(f"Release already exists: {target}")
    allowed, reviews = transitions(cases), read(args.reviews)
    replaced, truth, audit = {}, [], {}
    for tid in config["ids"]:
        case_dir = args.work / safe_name(tid)
        p = read(case_dir / "proposal.json")
        record = audit[tid] = {"proposal": p}
        if (case_dir / "generation.json").exists():
            record["generation"] = read(case_dir / "generation.json")
        if (case_dir / "invalid.json").exists():
            record["invalid"] = read(case_dir / "invalid.json")["error"]
            continue
        if p["decision"] == "NO_VALID_DECOY":
            continue
        review = reviews[tid]
        if review["decision"] not in ("accept", "reject") or not all(isinstance(review.get(k), str) and review[k].strip() for k in ("reviewer", "reason")):
            raise ValueError(f"Expected signed accept/reject review for {tid}")
        record["review"] = review
        if review["decision"] == "accept":
            events, mapped, mapping, inserted = materialize(cases[tid], labels[tid], p, allowed)
            if events != read(case_dir / "events.json") or mapping != read(case_dir / "step_map.json"):
                raise ValueError(f"Candidate changed since generation: {tid}")
            record.update(original_to_variant=mapping, insertions=inserted,
                          inserted_steps=sorted(s for i in inserted for s in i["steps"]),
                          original_root=root_failure(labels[tid])["step_number"])
            replaced[tid] = events
            truth.append(mapped)
    if not replaced:
        raise ValueError("No reviewed, accepted trajectories to release")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
        staging = Path(tmp) / args.version
        artifacts = {}
        # Each input file that holds an accepted trajectory, in its own layout and relative path.
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
        write(staging / "manifest.json", dict(
            domain=config["domain"], variant="step_decoy", version=args.version,
            parent=dict(trajectories=config["trajectories"], ground_truth=config["ground_truth"], sha256=hashes),
            generator=config, artifact_sha256=artifacts,
            generator_sha256=sorted({r["generator_sha256"] for r in runs}),
            helpers_sha256=sorted({r["helpers_sha256"] for r in runs}),
            copilot_versions=sorted({r["copilot_version"] for r in runs}),
            total_premium_requests=sum(r.get("premium_requests") or 0 for r in runs),
            accepted_ids=list(replaced), attempted_count=len(audit)))
        staging.rename(target)
    print(target)


def predictions(path):
    results = {}
    for row in read(path)["detailed_results"]:
        tid = str(row["task_id"])
        if tid in results or len(row["failures"]) != 1:
            raise ValueError("Expected one judge decision per trajectory in each run")
        results[tid] = int(row["failures"][0]["step_number"])
    return results


def compare(args):
    clean, variant = predictions(args.clean), predictions(args.variant)
    counts, by_kind = Counter(), Counter()
    outcomes = {}
    for tid, rec in read(args.audit).items():
        if "original_to_variant" not in rec:
            continue
        if tid not in clean or tid not in variant:
            outcome = "missing_prediction"
        elif clean[tid] != rec["original_root"]:
            outcome = "clean_root_missed"
        elif variant[tid] == rec["original_to_variant"][str(rec["original_root"])]:
            outcome = "same_original_event"
        elif variant[tid] in rec["inserted_steps"]:
            outcome = "inserted_decoy"
            by_kind[next(i["kind"] for i in rec["insertions"] if variant[tid] in i["steps"])] += 1
        elif variant[tid] in rec["original_to_variant"].values():
            outcome = "other_original_event"
        else:
            outcome = "invalid_variant_step"
        outcomes[tid] = outcome
        counts[outcome] += 1
    denominator = sum(counts[key] for key in ("same_original_event", "inserted_decoy", "other_original_event", "invalid_variant_step"))
    rate = counts["inserted_decoy"] / denominator if denominator else None
    print(json.dumps({"counts": counts, "paired_clean_correct": denominator, "decoy_attraction_rate": rate,
                      "attracted_by_kind": by_kind, "cases": outcomes}, indent=2))


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
    gen.add_argument("--work", type=Path, required=True)
    gen.add_argument("--ids", nargs="+", help="Trajectory IDs (default: every labeled trajectory)")
    copilot.add_model_arguments(gen, VARIANT)
    pub = cmds.add_parser("release", help="Freeze reviewed candidates with remapped labels")
    pub.add_argument("--work", type=Path, required=True)
    pub.add_argument("--reviews", type=Path, required=True)
    pub.add_argument("--version", required=True)
    pub.add_argument("--out", type=Path, help="Release root (default: data/benchmark_versions/<dataset>/step_decoy)")
    cmp = cmds.add_parser("compare", help="Compare a matched pair of run1.json judge reports")
    for key in ("audit", "clean", "variant"):
        cmp.add_argument("--" + key, required=True, type=Path)
    args = parser.parse_args()
    try:
        {"generate": propose, "release": release, "compare": compare}[args.command](args)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"{args.command}: {exc}\n")


if __name__ == "__main__":
    main()
