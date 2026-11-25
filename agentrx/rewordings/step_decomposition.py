"""Generate step-decomposition trajectories for AgentRx, review them, and freeze accepted cases.

A decomposition splits the single annotated root-cause step into several smaller
consecutive steps by the same actor that together do exactly what it did, so the
one guilty step is spread across the finer, realistic steps an agent would take.
The mistake is preserved and left unfixed; only its position changes.

Nothing here is specific to one domain. --domain selects the policy and the
tool or agent descriptions from AgentRx's domain registry, the input can be any
trajectory JSON layout AgentRx reads, and the model proposes only the text of the
smaller steps. Python replaces the step, keeps the same actor, enforces structure
learned from the input (role transitions at the new boundaries, step counters),
renumbers the trajectory, and writes each variant back in its input's layout. No
IR conversion is used. Labels number steps by 1-based event position, as in the
AgentRx baselines, and the root failure moves onto the smaller step that carries
the mistake.
"""

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path

from agentrx.invariants.domain_registry import get_domain_config, list_domains
from agentrx.rewordings import copilot, step_decoy
from agentrx.rewordings.step_decoy import PROVIDER, check_generator, generator_settings

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / "data/benchmark_versions"
TEMPLATE = Path(__file__).with_name("step_decomposition_prompt.txt")
# Release folders of the existing baselines; other domains use their own name.
DATASETS = {"tau": "tau_retail", "magentic": "magentic_one"}
# The layouts AgentRx's loader accepts (agentrx/ir/trajectory_ir.py), re-implemented
# here so each file's own layout can be written back unchanged.
EVENT_KEYS = ("traj", "events", "messages", "trajectory", "spans")
ID_KEYS = ("trajectory_id", "task_id", "traceId")
ROLE_KEYS = ("role", "source", "speaker", "agent", "name")
CONTENT_KEYS = ("content", "message", "text", "output")
# The generator model comes from $STEP_DECOMPOSITION_COPILOT_MODEL (default
# claude-haiku-5.5) and is run through the GitHub Copilot CLI; see copilot.py.
VARIANT = "step_decomposition"
MIN_SUBSTEPS = 2
MAX_SUBSTEPS = 4  # the one step becomes this many smaller steps at most
# The template carries the instructions and <<PLACEHOLDER>> slots for domain data.
SYSTEM = ("You design step decompositions for evaluating root-cause localization in agent "
          "trajectories. Follow the instructions in the user message and answer only through "
          "the structured output.")
# The schema is flat (no top-level anyOf), so copilot.check_schema() checks only types
# and enums; Python checks which fields each decision requires.
SUBSTEP = {"type": "object", "additionalProperties": False, "required": ["content"],
           "properties": {"content": {"type": "string"}}}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["decision"], "properties": {
    "decision": {"type": "string", "enum": ["DECOMPOSE", "NO_VALID_DECOMPOSITION"]},
    "substeps": {"type": "array", "items": SUBSTEP},
    "error_substeps": {"type": "array", "items": {"type": "integer"}},
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


def role_key(event):
    return next((k for k in ROLE_KEYS if isinstance(event.get(k), str)), None)


def signature(event):
    return role(event) + ("+calls" if event.get("tool_calls") or event.get("function_call") else "")


def transitions(cases):
    """Consecutive role pairs seen in the dataset; new boundaries may only create these."""
    return {(signature(a), signature(b)) for c in cases.values() for a, b in zip(c["events"], c["events"][1:])}


def content_key(event):
    return next((k for k in CONTENT_KEYS if k in event), None)


def counters(events):
    """Integer fields that number events in order (Tau's `index`); renumbered in variants."""
    if len(events) < 2:
        return {}
    return {k: v for k, v in events[0].items()
            if type(v) is int and all(type(e.get(k)) is int and e[k] == v + n for n, e in enumerate(events))}


# ---------- Building a variant ----------

def materialize(case, label, proposal, allowed):
    """Replace the root step with its smaller steps; return events, remapped label,
    step map and the decomposition record."""
    events = case["events"]
    root = root_failure(label)["step_number"]
    if proposal.get("decision") != "DECOMPOSE":
        raise ValueError("Expected a DECOMPOSE proposal")
    subs = proposal.get("substeps")
    if (not isinstance(subs, list) or not MIN_SUBSTEPS <= len(subs) <= MAX_SUBSTEPS
            or not all(isinstance(s, dict) and isinstance(s.get("content"), str) and s["content"].strip() for s in subs)):
        raise ValueError(f"Provide {MIN_SUBSTEPS} to {MAX_SUBSTEPS} smaller steps, each with non-empty content")
    for key in ("rationale", "distinguishing_evidence"):
        if not isinstance(proposal.get(key), str) or not proposal[key].strip():
            raise ValueError(f"Missing {key}")
    k = len(subs)
    err = proposal.get("error_substeps")
    if not isinstance(err, list) or not err or not all(isinstance(e, int) and 1 <= e <= k for e in err):
        raise ValueError("error_substeps must give the 1-based positions of the smaller steps that carry the mistake")
    if not 1 <= root <= len(events):
        raise ValueError(f"Root failure step {root} is outside 1..{len(events)}")

    root_event = events[root - 1]
    ckey = content_key(root_event) or "content"
    rkey = role_key(root_event)
    if rkey is None:
        raise ValueError("Root step has no recognizable actor field")
    # Clone the root step for each smaller step. Any action (a tool call) stays on the
    # LAST smaller step, not the first: the tool result that followed the original step
    # must come right after the call, and an "assistant text -> tool result" sequence
    # never occurs in the data. The earlier smaller steps are the same actor's text
    # leading up to the call, so one step still performs it.
    new_events = []
    for i, s in enumerate(subs):
        ev = deepcopy(root_event)
        ev[ckey] = s["content"].strip()
        if i != k - 1:
            ev.pop("tool_calls", None)
            ev.pop("function_call", None)
        new_events.append(ev)

    edited = deepcopy(events[:root - 1]) + new_events + deepcopy(events[root:])
    decomposed = set(range(root, root + k))  # 1-based positions of the smaller steps in `edited`

    # Only the entry and exit boundaries must match a transition seen in the dataset; the
    # internal same-actor boundaries are inherent to splitting one turn and are allowed.
    if root - 1 >= 1:
        pair = (signature(edited[root - 2]), signature(edited[root - 1]))
        if pair not in allowed:
            raise ValueError(f"Decomposition breaks the turn structure entering the step: {pair[0]} -> {pair[1]}")
    if root + k <= len(edited):
        pair = (signature(edited[root + k - 2]), signature(edited[root + k - 1]))
        if pair not in allowed:
            raise ValueError(f"Decomposition breaks the turn structure leaving the step: {pair[0]} -> {pair[1]}")

    numbering = counters(events)
    for n, event in enumerate(edited):
        event.update({ck: offset + n for ck, offset in numbering.items()})

    def bare(event):
        return {ck: v for ck, v in event.items() if ck not in numbering}
    if ([bare(e) for n, e in enumerate(edited, 1) if n not in decomposed]
            != [bare(e) for n, e in enumerate(events, 1) if n != root]):
        raise ValueError("Original events changed")

    # Steps before the root keep their number; the root moves onto the smaller step that
    # carries the mistake; everything after shifts by the steps the split added.
    e0 = min(err) - 1  # 0-based offset of the first mistake-carrying smaller step

    def remap(i):
        if i < root:
            return i
        if i == root:
            return root + e0
        return i + (k - 1)
    mapping = {str(i): remap(i) for i in range(1, len(events) + 1)}
    mapped = deepcopy(label)
    for failure in mapped["failures"]:
        failure["original_step_number"] = failure["step_number"]
        failure["step_number"] = mapping[str(failure["step_number"])]
    record = dict(root=root, substeps=k, decomposed_steps=sorted(decomposed),
                  error_steps=[root + e - 1 for e in sorted(err)])
    return edited, mapped, mapping, record


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


# ---------- Commands ----------

def domain_inputs(domain, policy_path):
    cfg = get_domain_config(domain)
    policy_path = policy_path or cfg.default_policy_path
    if not policy_path:
        raise ValueError(f"Domain {domain!r} has no default policy; pass --policy")
    return (ROOT / policy_path).read_text(encoding="utf-8"), cfg.tools_structure


def root_step_view(case, root):
    """The exact step to decompose, as one labeled JSON line."""
    return lines([{"step": root, "actor": role(case["events"][root - 1]), "event": case["events"][root - 1]}])


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
    allowed = transitions(cases)
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
        proposal = {"decision": "NO_VALID_DECOMPOSITION", "reason": "The label has no root-cause failure"}
        generation = None
        if root is not None:
            message = render(prompt, DOMAIN=args.domain, POLICY=policy, TOOLS=tools or "none provided",
                             TASK_INSTRUCTION=instruction(case) or "not provided; see the first steps",
                             ROOT_FAILURE=root,
                             TRAJECTORY=lines({"step": n, "event": e} for n, e in enumerate(case["events"], 1)),
                             ROOT_STEP=root_step_view(case, root["step_number"]),
                             ROLE_TRANSITIONS=lines(f"{a} -> {b}" for a, b in sorted(allowed)))
            binary = binary or copilot.binary(args.copilot_bin)
            version = version or copilot.version(binary)
            try:
                proposal, meta = copilot.ask(binary, settings["model"], settings["effort"], SYSTEM, SCHEMA,
                                             message, args.timeout)
            except ValueError as exc:
                raise ValueError(f"Trajectory {tid}: {exc}")
            # generator_sha256 hashes this file; helpers_sha256 the step_decoy and copilot code it uses.
            generation = dict(meta, copilot_version=version, generator_sha256=digest(Path(__file__).read_bytes()),
                              helpers_sha256=digest(Path(step_decoy.__file__).read_bytes() + Path(copilot.__file__).read_bytes()))
        with tempfile.TemporaryDirectory(dir=args.work) as tmp:
            staging = Path(tmp) / case_dir.name
            staging.mkdir()
            if generation:
                write(staging / "generation.json", generation)
            write(staging / "proposal.json", proposal)
            if proposal.get("decision") == "DECOMPOSE":
                try:
                    events, _, mapping, record = materialize(case, label, proposal, allowed)
                except ValueError as exc:
                    # Keep the model's output for review instead of failing the batch.
                    write(staging / "invalid.json", {"error": str(exc)})
                else:
                    write(staging / "events.json", events)
                    write(staging / "step_map.json", mapping)
                    write(staging / "decomposition.json", record)
            elif proposal.get("decision") != "NO_VALID_DECOMPOSITION" or not str(proposal.get("reason") or "").strip():
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
    # <dataset>/step_decomposition/vX.Y.Z; the model is recorded in the manifest.
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
        if p["decision"] == "NO_VALID_DECOMPOSITION":
            continue
        review = reviews[tid]
        if review["decision"] not in ("accept", "reject") or not all(
                isinstance(review.get(k), str) and review[k].strip() for k in ("reviewer", "reason")):
            raise ValueError(f"Expected signed accept/reject review for {tid}")
        record["review"] = review
        if review["decision"] == "accept":
            events, mapped, mapping, rec = materialize(cases[tid], labels[tid], p, allowed)
            if events != read(case_dir / "events.json") or mapping != read(case_dir / "step_map.json"):
                raise ValueError(f"Candidate changed since generation: {tid}")
            record.update(original_to_variant=mapping, decomposition=rec,
                          decomposed_steps=rec["decomposed_steps"], error_steps=rec["error_steps"],
                          original_root=root_failure(labels[tid])["step_number"])
            replaced[tid] = events
            truth.append(mapped)
    if not replaced:
        raise ValueError("No reviewed, accepted trajectories to release")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
        staging = Path(tmp) / args.version
        artifacts = {}
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
            domain=config["domain"], variant="step_decomposition", version=args.version,
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
    """Measure how often splitting the root step moves a correct localization off it."""
    clean, variant = predictions(args.clean), predictions(args.variant)
    counts, outcomes = Counter(), {}
    for tid, rec in read(args.audit).items():
        if "original_to_variant" not in rec:
            continue
        error_steps = set(rec["error_steps"])
        decomposed = set(rec["decomposed_steps"])
        if tid not in clean or tid not in variant:
            outcome = "missing_prediction"
        elif clean[tid] != rec["original_root"]:
            outcome = "clean_root_missed"
        elif variant[tid] in error_steps:
            outcome = "found_error_substep"          # judge still localizes the mistake
        elif variant[tid] in decomposed:
            outcome = "drifted_within_decomposition"  # moved onto a sibling smaller step
        elif variant[tid] in set(rec["original_to_variant"].values()):
            outcome = "other_original_event"
        else:
            outcome = "invalid_variant_step"
        outcomes[tid] = outcome
        counts[outcome] += 1
    denominator = sum(counts[k] for k in ("found_error_substep", "drifted_within_decomposition",
                                          "other_original_event", "invalid_variant_step"))
    evaded = denominator - counts["found_error_substep"]
    print(json.dumps({"counts": counts, "paired_clean_correct": denominator,
                      "decomposition_evasion_rate": (evaded / denominator) if denominator else None,
                      "drift_within_rate": (counts["drifted_within_decomposition"] / denominator) if denominator else None,
                      "cases": outcomes}, indent=2))


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
    pub.add_argument("--out", type=Path, help="Release root (default: data/benchmark_versions/<dataset>/step_decomposition)")
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
