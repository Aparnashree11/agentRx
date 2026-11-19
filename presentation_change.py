"""
presentation_change.py
======================================================================
AgentRx robustness experiment -- "PRESENTATION CHANGE" rewording.

WHAT THIS SCRIPT DOES (the big picture):
    Our team tests how robust AgentRx's verdict is. We take a *failed*
    agent trajectory and produce a reworded version that changes ONLY how
    the evidence is PRESENTED -- never WHAT happened. Then AgentRx judges
    the reworded trace. If the verdict changes when only wording/format/
    emphasis changed, that is a weakness in AgentRx.

    The three allowed presentation changes are:
        1. Wording     -- paraphrase a message/error (same meaning).
        2. Formatting  -- reorder JSON fields, compact vs. indented layout.
        3. Emphasis    -- bold text / add a heading, without changing facts.

    HARD CONSTRAINTS (never violate these):
        - the true failure step stays the same,
        - every step outcome stays the same,
        - the order of executed actions does NOT change,
        - tool names and tool results are left untouched.

HOW THE SCRIPT IS ORGANIZED (one function per job, built in order):
    0. extract_trajectory(task_id)      <-- pull a real labeled trace out of
                                            the dataset (used by --from-dataset)
    1. load_trajectory(path)            <-- this file, done
    2. load_ground_truth(trajectory_id) <-- this file, done
    3. load_policy_and_tools(domain)    <-- this file, done
    4. build_prompt(...)                <-- coming next
    5. call_model(prompt)               <-- Claude CLI (+ --dry-run fake)
    6. parse_and_validate(...)          <-- verifies the hard constraints
    7. write_outputs(...)               <-- saves reworded trace + sidecar
    8. main()                           <-- runs 1..7 in order, with --dry-run

This file currently contains ONLY functions 1-3 (the loaders). The rest
will be added step by step.
"""

# --- Standard library imports ------------------------------------------------
# json       : read/write JSON files (our trajectories and labels are JSON).
# os         : build file paths + read environment variables.
# subprocess : shell out to the `claude` command-line tool (function 5).
# argparse   : parse command-line options in main().
# sys        : set the process exit code (0 = ok, 1 = violations/errors).
import json
import os
import subprocess
import argparse
import sys


# ----------------------------------------------------------------------------
# PROJECT_ROOT: the absolute path to the top of the AgentRx repo.
#
# This script lives at the repo root (next to run.py), so the folder that
# contains THIS file IS the project root. We compute it once here so every
# function below can build correct paths to data/ files no matter where the
# user runs the script from (e.g. from a different directory).
#
#   __file__                       -> ".../agentRx/presentation_change.py"
#   os.path.abspath(__file__)      -> absolute version of that
#   os.path.dirname(...)           -> ".../agentRx"  (strips the filename)
# ----------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Default location of the FROZEN ground-truth labels for the tau-retail
# benchmark. This is our authoritative source of the "true failure" -- NOT
# anything the model says. We point at the versioned baseline copy so results
# are reproducible.
DEFAULT_GROUND_TRUTH_PATH = os.path.join(
    PROJECT_ROOT,
    "data", "benchmark_versions", "tau_retail", "baseline", "v1.0.0",
    "tau_ground_truth.json",
)

# ----------------------------------------------------------------------------
# Model-selection config for the Claude CLI (used by call_model, function 5).
#
# We reach the models through the `claude` command-line tool in "print" mode
# (`claude -p`). The --model flag accepts simple aliases: "opus", "sonnet",
# "haiku" (or full names like "claude-opus-4-8"). That lets us run the same
# experiment across all three models just by changing one value.
#
# How the model is chosen, in priority order (highest first):
#   1. an explicit model passed to call_model(...) / the --model CLI argument
#   2. the PRESENTATION_CHANGE_MODEL environment variable
#   3. DEFAULT_MODEL below
# ----------------------------------------------------------------------------
MODEL_ENV_VAR = "PRESENTATION_CHANGE_MODEL"   # env var name users can set
DEFAULT_MODEL = "sonnet"                       # fallback if nothing is set
CLAUDE_CLI_TIMEOUT = 600                        # seconds to wait for a response

# Default location of the FROZEN failed-trajectory dataset (the real labeled
# traces). Same versioned baseline folder as the ground truth above, so the
# trace and its label always come from the same release.
DEFAULT_DATASET_PATH = os.path.join(
    PROJECT_ROOT,
    "data", "benchmark_versions", "tau_retail", "baseline", "v1.0.0",
    "tau_dataset_failed.json",
)

# Where extract_trajectory() saves the events-format files it produces.
DEFAULT_EXTRACT_DIR = os.path.join(
    PROJECT_ROOT, "trajectories", "tau-retail", "from_dataset",
)


# ============================================================================
# HELPER -- extract_trajectory  (dataset record -> our events format)
# ============================================================================
def extract_trajectory(task_id, dataset_path=DEFAULT_DATASET_PATH,
                       save_dir=DEFAULT_EXTRACT_DIR):
    """
    Pull ONE real trace out of the failed-trajectory dataset by task_id and
    convert it to our events format, so the pipeline can run on it.

    The dataset file (tau_dataset_failed.json) is a LIST of records like:

        {
          "task_id": 2,
          "reward": 0.0,
          "info": { "task": { "instruction": "You are Yusuf Rossi ...", ... },
                    ... },
          "traj": [
            { "role": "system",    "content": "# Retail agent policy ...",
              "index": 1 },
            { "role": "user",      "content": "Hey! ...", "index": 2 },
            { "role": "assistant", "content": null, "tool_calls": [...],
              "refusal": null, "annotations": [], "index": 3 },
            { "role": "tool", "tool_call_id": "...", "name": "...",
              "content": "{...json string...}", "index": 4 },
            ...
          ],
          ...
        }

    We turn that into the shape load_trajectory() expects:

        {
          "trajectory_id": "2",                     <- str(task_id)
          "instruction":   info.task.instruction,   <- verbatim
          "events":        traj                     <- copied VERBATIM
        }

    Why the events are copied verbatim (nothing dropped or renamed):
        - The SYSTEM message (the policy) is kept as event 0. AgentRx numbers
          steps as (event position + 1), so keeping it is what makes the
          ground-truth step numbers line up: for task 2, ground-truth step 3
          is events[2] (the first assistant tool call), whose "index" is 3.
          Dropping the system message would silently shift every step by one.
        - Extra keys ("index", "refusal", "annotations") are harmless to our
          pipeline (parse_and_validate only checks role / name / ids / values)
          and keep the trace byte-for-byte faithful to what AgentRx judged.

    Parameters
    ----------
    task_id : str or int
        The dataset's task_id (e.g. 2). Compared as a STRING, same as
        load_ground_truth(), so "2" and 2 both work.
    dataset_path : str
        Path to the failed-trajectory dataset JSON.
    save_dir : str or None
        Folder to save the extracted file in (as task_<id>.json). Pass None
        to skip saving and just return the dict.

    Returns
    -------
    tuple (trajectory, saved_path)
        trajectory : dict      -- the events-format trajectory.
        saved_path : str|None  -- where it was written (None if not saved).
    """
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    # Find the record whose task_id matches (string comparison, see above).
    wanted = str(task_id)
    record = None
    for r in records:
        if str(r.get("task_id")) == wanted:
            record = r
            break

    if record is None:
        # Fail loudly and list what IS available, so a typo is easy to spot.
        available = ", ".join(str(r.get("task_id")) for r in records)
        raise ValueError(
            f"task_id={task_id!r} not found in {dataset_path}. "
            f"Available task_ids: {available}"
        )

    # The conversation lives under "traj"; it must be a list of messages.
    events = record.get("traj")
    if not isinstance(events, list) or not events:
        raise ValueError(
            f"Record task_id={task_id!r} has no usable 'traj' list of events."
        )

    # The task instruction (what the simulated user was told to do) lives at
    # info.task.instruction. This is the same value AgentRx's own loader
    # finds, because it searches the record for the first "instruction" key.
    instruction = (
        record.get("info", {}).get("task", {}).get("instruction")
    )
    if not isinstance(instruction, str):
        raise ValueError(
            f"Record task_id={task_id!r} has no info.task.instruction string."
        )

    trajectory = {
        "trajectory_id": wanted,   # str, so ground truth + folder names match
        "instruction": instruction,
        "events": events,          # verbatim -- see docstring for why
    }

    # Optionally save it so it can be inspected or re-run with --trajectory.
    saved_path = None
    if save_dir is not None:
        os.makedirs(save_dir, exist_ok=True)
        saved_path = os.path.join(save_dir, f"task_{_safe_name(wanted)}.json")
        with open(saved_path, "w", encoding="utf-8") as f:
            json.dump(trajectory, f, indent=2, ensure_ascii=False)

    return trajectory, saved_path


# ============================================================================
# FUNCTION 1 -- load_trajectory
# ============================================================================
def load_trajectory(path):
    """
    Read one trajectory file (the OpenAI "events" format we confirmed).

    The file looks like this:

        {
          "trajectory_id": "tau_retail_walkthrough_01",
          "instruction":   "Please check order #W1234567 ...",
          "events": [
            { "role": "user",      "content": "..." },
            { "role": "assistant", "content": null, "tool_calls": [ ... ] },
            { "role": "tool",      "tool_call_id": "...", "name": "...",
              "content": "{...json string...}" },
            ...
          ]
        }

    Parameters
    ----------
    path : str
        Path to the trajectory JSON file.

    Returns
    -------
    dict
        The parsed trajectory, with keys "trajectory_id", "instruction",
        and "events".

    Why we validate:
        We fail LOUDLY and early if the file is missing required keys. A
        confusing error here is much better than a silent wrong result later
        (e.g. rewording a file that wasn't actually a trajectory).
    """
    # Give a clear error if the path is wrong, instead of a cryptic one.
    if not os.path.exists(path):
        raise FileNotFoundError(f"Trajectory file not found: {path}")

    # Open the file for reading ("r") as UTF-8 text, and parse the JSON into
    # a Python dict. The "with" block automatically closes the file for us.
    with open(path, "r", encoding="utf-8") as f:
        trajectory = json.load(f)

    # Sanity-check the shape. Every trajectory MUST have these three keys.
    # If any is missing, something is wrong with the input file.
    for required_key in ("trajectory_id", "instruction", "events"):
        if required_key not in trajectory:
            raise ValueError(
                f"Trajectory file {path} is missing required key "
                f"'{required_key}'. Is this really an events-format trace?"
            )

    # "events" must be a list -- we will loop over it later.
    if not isinstance(trajectory["events"], list):
        raise ValueError(
            f"Trajectory file {path}: 'events' must be a list, "
            f"got {type(trajectory['events']).__name__}."
        )

    return trajectory


# ============================================================================
# FUNCTION 2 -- load_ground_truth
# ============================================================================
def load_ground_truth(trajectory_id, ground_truth_path=DEFAULT_GROUND_TRUTH_PATH):
    """
    Look up the TRUE failure(s) for one trajectory from the frozen label file.

    This is our single source of truth about what actually went wrong. The
    model NEVER gets to redefine the failure -- it only rewords presentation.
    Later, parse_and_validate() compares the model's output against the
    numbers we freeze here.

    The ground-truth file (tau_ground_truth.json) is a LIST of entries like:

        {
          "trajectory_id": 2,
          "failures": [
            {
              "failure_id": 1,
              "step_number": 3,
              "step_reason": "At step 3, the assistant did not authenticate ...",
              "failure_category": "Instruction Adherence Failure",
              "category_reason": "...",
              "failed_agent": "Assistant"
            },
            ...   # a trajectory can have more than one labeled failure
          ]
        }

    Parameters
    ----------
    trajectory_id : str or int
        The id of the trajectory we are rewording. We compare it to the ids
        in the label file as STRINGS, because the label file stores numeric
        ids (e.g. 2) while trajectory files may store strings (e.g. "2" or
        "tau_retail_walkthrough_01").
    ground_truth_path : str
        Path to the frozen ground-truth JSON. Defaults to the versioned
        baseline copy.

    Returns
    -------
    dict or None
        The matching ground-truth entry (the whole {trajectory_id, failures}
        object), or None if this trajectory has no label. We return the FULL
        entry -- including ALL failures -- so nothing is silently dropped;
        the caller decides how to freeze it into the sidecar.

    Note on "not found":
        Demo traces (like the walkthrough) are not in the benchmark label
        file, so None is a normal, expected outcome there. We print a loud
        warning rather than crashing, so dry-run testing still works.
    """
    if not os.path.exists(ground_truth_path):
        raise FileNotFoundError(
            f"Ground-truth file not found: {ground_truth_path}"
        )

    # Load the whole list of labeled trajectories.
    with open(ground_truth_path, "r", encoding="utf-8") as f:
        all_labels = json.load(f)

    # Compare ids as strings so "2" (from a trace) matches 2 (from labels).
    wanted = str(trajectory_id)
    for entry in all_labels:
        if str(entry.get("trajectory_id")) == wanted:
            return entry  # found the frozen truth for this trajectory

    # No label for this trajectory id. Warn loudly but don't crash, so the
    # dry-run flow can still be exercised on demo traces.
    print(
        f"[WARNING] No ground-truth label found for trajectory_id="
        f"{trajectory_id!r} in {ground_truth_path}. "
        f"The sidecar's frozen failure cannot be filled from ground truth."
    )
    return None


# ============================================================================
# FUNCTION 3 -- load_policy_and_tools
# ============================================================================
def load_policy_and_tools(domain):
    """
    Load the domain POLICY text and TOOL LIST -- the SAME sources AgentRx uses.

    These are injected into the rewording prompt purely as GUARDRAILS: they
    tell the model the real vocabulary (real tool names, real field names,
    real domain rules) so that when it paraphrases, it keeps using correct
    terms instead of inventing new ones. We do NOT ask the model to edit the
    policy or tools -- only to respect them.

    We get everything from AgentRx's own domain registry so our guardrails
    exactly match what AgentRx itself sees. The registry gives us:
        - cfg.tools_list          : the list of real tool names (13 for tau)
        - cfg.tools_structure     : the tools' JSON schema (field names, etc.)
        - cfg.default_policy_path : where the policy .txt file lives
                                    (relative to the project root)

    Parameters
    ----------
    domain : str
        The domain key understood by the registry, e.g. "tau" for tau-retail.

    Returns
    -------
    tuple (policy_text, tools_list, tools_structure)
        policy_text     : str  -- the full policy document text.
        tools_list      : list -- real tool names.
        tools_structure : dict -- the tools' JSON schema.
    """
    # Import here (inside the function) rather than at the top of the file so
    # that the first three loaders stay easy to read in isolation, and so a
    # user only needs the agentrx package importable when they actually call
    # this function.
    from agentrx.invariants.domain_registry import get_domain_config

    # Ask AgentRx's registry for this domain's configuration. Raises
    # ValueError for an unknown domain -- which is the behavior we want.
    cfg = get_domain_config(domain)

    # ---- Load the policy text from the file the registry points to --------
    # The registry stores the path RELATIVE to the project root (e.g.
    # "data/policies/retail_policy.txt"), so we join it onto PROJECT_ROOT to
    # get an absolute path that works from any working directory.
    if not cfg.default_policy_path:
        raise ValueError(
            f"Domain '{domain}' has no default_policy_path in the registry; "
            f"cannot load a policy document."
        )
    policy_path = os.path.join(PROJECT_ROOT, cfg.default_policy_path)
    if not os.path.exists(policy_path):
        raise FileNotFoundError(f"Policy file not found: {policy_path}")
    with open(policy_path, "r", encoding="utf-8") as f:
        policy_text = f.read()

    # ---- Tools come straight from the registry (already Python objects) ----
    tools_list = cfg.tools_list
    tools_structure = cfg.tools_structure

    return policy_text, tools_list, tools_structure


# ============================================================================
# FUNCTION 4 -- build_prompt
# ============================================================================
#
# THE PROMPT TEMPLATE (AgentRx style)
# -----------------------------------
# Just like AgentRx's own invariant prompt, this is ONE long string that is
# mostly FIXED INSTRUCTIONS, with a few <<PLACEHOLDER>> tokens near the bottom
# that get filled in at run time with the live policy, tool list, tool schema,
# and the specific trajectory to reword. "Fixed rules on top, live data at the
# bottom under labeled banners."
#
# The placeholders are:
#   <<POLICY_TEXT>>       -> the domain policy document (guardrail)
#   <<TOOLS_LIST>>        -> the real tool names (vocabulary guardrail)
#   <<TOOLS_STRUCTURE>>   -> the tools' JSON schema (field-name guardrail)
#   <<TRAJECTORY_JSON>>   -> the trajectory we want reworded
# ----------------------------------------------------------------------------
PRESENTATION_CHANGE_PROMPT = """\
You are a careful trajectory editor. Your job is to produce a PRESENTATION-ONLY
rewording of a failed agent trajectory. You change HOW the evidence looks,
never WHAT happened. The reworded trajectory must lead any downstream judge to
the exact same conclusion about which step failed and why.

================================================================================
WHAT YOU ARE ALLOWED TO CHANGE (and ONLY these three things)
================================================================================
1. Wording      -- paraphrase the natural-language text inside a message or an
                   error string (same meaning, different words).
2. Formatting   -- reorder the keys inside a JSON object, or switch a JSON value
                   between compact and indented form. Same keys, same values,
                   different layout.
3. Emphasis     -- make existing evidence more or less prominent (e.g. add
                   **bold**, a markdown heading, or a bullet) WITHOUT adding,
                   removing, or altering any fact.

================================================================================
WHAT YOU MUST NEVER CHANGE (hard constraints)
================================================================================
- The TRUE FAILURE STEP -- the step where the agent actually went wrong stays
  the same step, with the same meaning.
- Any STEP OUTCOME -- a step that succeeded still reads as succeeded; a step
  that failed still reads as failed, for the same reason.
- The ORDER OF EXECUTED ACTIONS -- do not reorder, insert, merge, split, or
  delete events. (Reordering KEYS INSIDE a JSON object is fine; reordering
  EVENTS/actions is forbidden.)
- TOOL NAMES -- every tool name must appear exactly as in the input and the
  provided tool list. Do not rename, translate, or paraphrase a tool name.
  The linkage ids ("id", "tool_call_id") must also stay byte-for-byte identical.
- TOOL RESULTS / ARGUMENTS -- the values returned by tools and the arguments
  passed to them keep the same content. You may reformat their JSON layout, but
  not change any key, value, number, id, or status.
- No NEW facts and no REMOVED facts. Paraphrase must be meaning-preserving.
  Never invent, never omit.
- Leave the `instruction` field VERBATIM. If a user event echoes it, you may
  reword that user event, but keep the two consistent in meaning.
- Do NOT rewrite any policy text that appears inside the trajectory (e.g. a
  system message). The policy is the rulebook, not evidence to edit.

================================================================================
HOW TO USE THE POLICY AND TOOL LIST (provided at the bottom)
================================================================================
They are GUARDRAILS, not content to edit. Use them only to make sure your
reworded text keeps using real, correct vocabulary -- real tool names, real
field names, real domain terms. Do NOT copy the policy or tool list into your
output, and do NOT "correct" the trajectory to match them. If the agent did
something wrong per the policy, it must still read as wrong.

================================================================================
TRAJECTORY FORMAT (the shape you receive AND must return)
================================================================================
{
  "trajectory_id": "str",
  "instruction": "str",
  "events": [
    { "role": "user"|"assistant", "content": "str" },
    { "role": "assistant", "content": null,
      "tool_calls": [ { "id": "str", "type": "function",
                        "function": { "name": "str",
                                      "arguments": "<JSON string>" } } ] },
    { "role": "tool", "tool_call_id": "str", "name": "str",
      "content": "<JSON string>" }
  ]
}
- `content` on tool / tool-call events is JSON encoded AS A STRING. To reformat
  it, parse the string, re-serialize with a different layout/key order, and keep
  every key and value identical.

================================================================================
PROCEDURE
================================================================================
1. Read the trajectory and identify the failure step and its outcome (for your
   own reference -- you are PRESERVING it, not fixing it).
2. Apply only the three allowed presentation changes.
3. Re-read your output and confirm: same events, same order, same tool names,
   same results, same failure. Only wording/layout/emphasis differ.
4. Record exactly which changes you made in the sidecar (see OUTPUT below).

================================================================================
OUTPUT FORMAT (return EXACTLY one JSON object with these two top-level keys)
================================================================================
{
  "reworded_trajectory": {
    "trajectory_id": "str",            // copied UNCHANGED from input
    "instruction": "str",              // VERBATIM
    "events": [ ... ]                  // SAME length, SAME order, SAME roles;
                                       // only content text / JSON layout /
                                       // emphasis may differ; tool names, ids,
                                       // and all values unchanged
  },

  "preservation_record": {
    "trajectory_id": "str",            // copied from input
    "failure_step_index": int|null,    // YOUR best reading of the failure step
    "failure_event_index": int|null,   // 0-based index into events, if known
    "failure_category": "str|null",    // YOUR best reading of the failure type
    "failure_summary": "str",          // one sentence: what actually went wrong
    "step_outcomes": [                 // one entry per step you can identify
      { "index": int, "outcome": "success|failure|neutral" }
    ],
    "action_order": [ int, ... ],      // event indices in execution order
    "changes_applied": [               // EVERY presentation edit, itemized
      {
        "event_index": int,
        "change_type": "wording|formatting|emphasis",
        "before_excerpt": "str",       // short snippet of the original
        "after_excerpt": "str",        // the reworded/reformatted counterpart
        "note": "str"                  // why this is presentation-only
      }
    ],
    "untouched": {
      "tool_names_preserved": true,
      "tool_results_preserved": true,
      "embedded_policy_reworded": false
    }
  }
}

IMPORTANT: Return ONLY the JSON object. The `failure_*` fields are your reading
only; the experiment's authoritative failure comes from a separate ground-truth
file, so do not worry about getting the label "right" -- focus on preserving it.

================================================================================
POLICY DOCUMENT (guardrail -- do NOT edit or copy into output)
================================================================================
<<POLICY_TEXT>>

================================================================================
TOOL LIST (the only tool names that may appear -- do NOT rename any)
================================================================================
<<TOOLS_LIST>>

================================================================================
TOOL STRUCTURE (use ONLY the field names that appear here)
================================================================================
<<TOOLS_STRUCTURE>>

================================================================================
TRAJECTORY TO REWORD (return a presentation-only rewording of THIS)
================================================================================
<<TRAJECTORY_JSON>>
"""


def build_prompt(trajectory, policy, tools, tools_structure=None):
    """
    Assemble the full presentation-change prompt from the fixed template.

    This mirrors AgentRx's own prompt builder: take the fixed template string
    and fill its <<PLACEHOLDER>> tokens with the live policy, tool list, tool
    schema, and the trajectory to reword -- using plain str.replace(), the same
    "flash-style" substitution AgentRx uses.

    Parameters
    ----------
    trajectory : dict
        The trajectory to reword (events format), from load_trajectory().
    policy : str
        The policy document text, from load_policy_and_tools().
    tools : list
        The list of real tool names, from load_policy_and_tools().
    tools_structure : dict or None
        The tools' JSON schema, from load_policy_and_tools(). Optional: if None
        we inject an empty object so the prompt still assembles. (We keep the
        3-argument call build_prompt(trajectory, policy, tools) working, while
        allowing the richer field-name guardrail when the schema is supplied.)

    Returns
    -------
    str
        The complete prompt text to hand to call_model().
    """
    # Serialize the live data to nicely-indented JSON so it is easy for the
    # model (and us) to read. ensure_ascii=False keeps real characters (e.g.
    # curly quotes) instead of \\uXXXX escapes.
    tools_list_str = json.dumps(tools or [], indent=2, ensure_ascii=False)
    tools_structure_str = json.dumps(tools_structure or {}, indent=2,
                                     ensure_ascii=False)
    trajectory_str = json.dumps(trajectory, indent=2, ensure_ascii=False)

    # Fill the blanks. Each .replace() swaps one <<PLACEHOLDER>> for its value.
    prompt = (
        PRESENTATION_CHANGE_PROMPT
        .replace("<<POLICY_TEXT>>", policy or "")
        .replace("<<TOOLS_LIST>>", tools_list_str)
        .replace("<<TOOLS_STRUCTURE>>", tools_structure_str)
        .replace("<<TRAJECTORY_JSON>>", trajectory_str)
    )
    return prompt


# ============================================================================
# HELPER for FUNCTION 5 -- reformat a JSON-encoded string (presentation only)
# ============================================================================
def _reformat_json_string(s):
    """
    Re-serialize a JSON string with a DIFFERENT layout but the SAME values.

    Several fields in a trajectory are JSON stored *as a string*, e.g. a tool
    result's "content" or a tool call's "arguments". Reformatting such a
    string (indenting it, sorting its keys) is a legal "presentation change":
    the keys and values stay identical, only the layout/key-order differs.

    Returns
    -------
    str or None
        The reformatted JSON string, or None if `s` is not valid JSON (in
        which case the caller should leave the original text untouched).
    """
    try:
        parsed = json.loads(s)
    except (ValueError, TypeError):
        return None  # not JSON (ordinary prose) -- don't touch it
    # indent=2 changes layout; sort_keys=True changes field order; neither
    # changes any key or value -> a pure presentation change.
    return json.dumps(parsed, indent=2, sort_keys=True, ensure_ascii=False)


def _fabricate_dry_run_response(trajectory):
    """
    Build a realistic FAKE model response from a real trajectory, for testing.

    The point of --dry-run is to exercise the WHOLE pipeline (build_prompt ->
    call_model -> parse_and_validate -> write_outputs) without calling a model
    or spending anything. To be useful, the fake must look like what a real
    model would return AND actually obey the presentation-change rules, so
    that parse_and_validate() has something valid to check.

    What this fake does (all legal presentation changes):
        - leaves `instruction` verbatim (our agreed rule),
        - reformats every JSON-string payload (tool results + tool-call
          arguments) -> a "formatting" change with identical values,
        - wraps each assistant prose message in **bold** -> an "emphasis"
          change that preserves the text's meaning,
        - keeps every event, its order, every tool name, and every value.

    It returns a JSON string wrapped in ```json ... ``` markdown fences,
    because real models frequently wrap JSON that way -- this lets our parser
    (function 6) prove it can strip fences.
    """
    # copy module: deepcopy makes an independent copy so we never mutate the
    # caller's original trajectory while building the fake.
    import copy

    events_out = []          # the reworded events we will return
    changes_applied = []     # a log of every presentation edit we made

    for event_index, event in enumerate(trajectory["events"]):
        new_event = copy.deepcopy(event)
        role = event.get("role")
        content = event.get("content")

        # (a) tool RESULT events: "content" is a JSON string -> reformat it.
        if role == "tool" and isinstance(content, str):
            reformatted = _reformat_json_string(content)
            if reformatted is not None and reformatted != content:
                new_event["content"] = reformatted
                changes_applied.append({
                    "event_index": event_index,
                    "change_type": "formatting",
                    "note": "tool result JSON re-indented + keys sorted; "
                            "values unchanged",
                })

        # (b) assistant TOOL-CALL events: reformat each call's "arguments"
        #     (also a JSON string). Tool NAMES and ids are left untouched.
        if isinstance(new_event.get("tool_calls"), list):
            for call in new_event["tool_calls"]:
                function = call.get("function", {})
                arguments = function.get("arguments")
                if isinstance(arguments, str):
                    reformatted = _reformat_json_string(arguments)
                    if reformatted is not None and reformatted != arguments:
                        function["arguments"] = reformatted
                        changes_applied.append({
                            "event_index": event_index,
                            "change_type": "formatting",
                            "note": "tool-call arguments JSON re-indented + "
                                    "keys sorted; values unchanged",
                        })

        # (c) assistant PROSE messages: add emphasis (bold) without changing
        #     the words. (content is None on tool-call events, so we guard.)
        if role == "assistant" and isinstance(content, str) and content.strip():
            new_event["content"] = f"**{content}**"
            changes_applied.append({
                "event_index": event_index,
                "change_type": "emphasis",
                "note": "assistant message wrapped in bold; wording unchanged",
            })

        events_out.append(new_event)

    # The reworded trajectory -- EXACT same shape as the input.
    reworded_trajectory = {
        "trajectory_id": trajectory["trajectory_id"],
        "instruction": trajectory["instruction"],   # verbatim, by design
        "events": events_out,
    }

    # The sidecar. NOTE: the failure_* fields here are only the MODEL'S guess.
    # In the real flow the authoritative values come from ground truth; these
    # placeholders exist so the schema is complete for testing.
    preservation_record = {
        "trajectory_id": str(trajectory["trajectory_id"]),
        "failure_step_index": None,     # model guess (dry-run: unknown)
        "failure_event_index": None,
        "failure_category": None,
        "failure_summary": "DRY-RUN fake response; no real analysis performed.",
        "step_outcomes": [
            {"index": i, "outcome": "neutral"} for i in range(len(events_out))
        ],
        "action_order": list(range(len(events_out))),
        "changes_applied": changes_applied,
        "untouched": {
            "tool_names_preserved": True,
            "tool_results_preserved": True,
            "embedded_policy_reworded": False,
        },
    }

    response_object = {
        "reworded_trajectory": reworded_trajectory,
        "preservation_record": preservation_record,
    }

    # Wrap in markdown fences to mimic a real model's reply.
    return "```json\n" + json.dumps(response_object, indent=2, ensure_ascii=False) + "\n```"


# ============================================================================
# FUNCTION 5 -- call_model  (Claude CLI, with a --dry-run fake)
# ============================================================================
def call_model(prompt, model=None, dry_run=False, dry_run_reference=None):
    """
    Send one prompt to a Claude model and return its raw text response.

    TEAM DECISION: we reach the models through the `claude` command-line tool
    (NOT GitHub Copilot and NOT an Anthropic API key). We run it in "print"
    mode, which sends a single prompt and prints the reply, like:

        printf '%s' "$PROMPT" | claude -p --model sonnet --output-format text

    Parameters
    ----------
    prompt : str
        The full prompt text to send (built by build_prompt, function 4).
    model : str or None
        Which model to use: "opus", "sonnet", or "haiku" (aliases the CLI
        understands), or a full model name. If None, we fall back to the
        PRESENTATION_CHANGE_MODEL env var, then to DEFAULT_MODEL.
    dry_run : bool
        If True, DO NOT call any model. Return a realistic fake response so
        the rest of the pipeline can be tested for free.
    dry_run_reference : dict or None
        In dry-run mode, the original trajectory to base the fake response on
        (so the fake is valid and parse_and_validate has real data to check).

    Returns
    -------
    str
        The model's raw text reply (may contain ```json fences -- function 6
        is responsible for stripping those).
    """
    # Resolve which model to use, highest priority first:
    #   explicit arg  ->  env var  ->  default
    chosen_model = model or os.getenv(MODEL_ENV_VAR) or DEFAULT_MODEL

    # ---- DRY-RUN branch: no model call, no cost --------------------------
    if dry_run:
        print(
            f"[DRY-RUN] Skipping the real model call "
            f"(would have used model '{chosen_model}'). Returning a fake "
            f"response for testing."
        )
        if dry_run_reference is not None:
            return _fabricate_dry_run_response(dry_run_reference)
        # No reference trajectory given -> return a tiny, clearly-empty fake.
        return (
            "```json\n"
            + json.dumps(
                {"reworded_trajectory": {}, "preservation_record": {}},
                indent=2,
            )
            + "\n```"
        )

    # ---- REAL branch: shell out to the claude CLI ------------------------
    # We pass the prompt on STDIN (not as an argument) because our prompt is
    # large and stdin has no length limit.
    command = ["claude", "-p", "--model", chosen_model,
               "--output-format", "text"]
    print(
        f"[call_model] Running: {' '.join(command)}  "
        f"(prompt is {len(prompt)} chars, sent via stdin)"
    )

    try:
        result = subprocess.run(
            command,
            input=prompt,          # the prompt goes to the CLI's stdin
            capture_output=True,   # grab stdout and stderr
            text=True,             # treat streams as text (str), not bytes
            encoding="utf-8",
            timeout=CLAUDE_CLI_TIMEOUT,
        )
    except FileNotFoundError:
        # Raised if the `claude` binary isn't on PATH.
        raise RuntimeError(
            "The `claude` CLI was not found on your PATH. Install Claude Code, "
            "or run this script with --dry-run to test without a model."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"The `claude` CLI did not respond within {CLAUDE_CLI_TIMEOUT}s."
        )

    # A non-zero exit code means the CLI failed -- surface its error loudly.
    if result.returncode != 0:
        raise RuntimeError(
            f"The `claude` CLI exited with code {result.returncode}. "
            f"stderr: {(result.stderr or '').strip()[:500]}"
        )

    response_text = (result.stdout or "").strip()
    if not response_text:
        raise RuntimeError("The `claude` CLI returned an empty response.")

    return response_text


# ============================================================================
# HELPERS for FUNCTION 6 -- JSON extraction and comparison
# ============================================================================
def _extract_json_object(text):
    """
    Pull a JSON object out of a model reply and parse it.

    Real models often wrap JSON in markdown fences, like:
        ```json
        { ... }
        ```
    ...and sometimes add a sentence before or after. This helper:
        1. strips a leading ```json / ``` fence and a trailing ``` fence,
        2. tries to parse the whole thing,
        3. if that fails, falls back to the substring from the first "{" to
           the last "}" and parses that.

    Raises
    ------
    ValueError
        If no valid JSON object can be parsed. We FAIL LOUDLY here because a
        reply we cannot parse is useless downstream.
    """
    import re

    stripped = text.strip()

    # (1) Remove an opening fence like ``` or ```json (with optional newline),
    #     and a closing ``` fence at the very end.
    stripped = re.sub(r"^```[a-zA-Z0-9]*\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped).strip()

    # (2) Try to parse the cleaned-up text directly.
    try:
        return json.loads(stripped)
    except (ValueError, TypeError):
        pass  # fall through to the brace-extraction fallback

    # (3) Fallback: grab everything between the first "{" and the last "}".
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidate = stripped[first:last + 1]
        try:
            return json.loads(candidate)
        except (ValueError, TypeError):
            pass

    # Nothing worked -> fail loudly with a helpful message.
    raise ValueError(
        "Could not parse any JSON object from the model response. "
        "First 200 chars were:\n" + text[:200]
    )


def _json_or_none(s):
    """
    Parse a string as JSON, or return None if it is not valid JSON.

    Used to compare the VALUES inside tool results / tool-call arguments,
    which are stored as JSON *strings*. Comparing the parsed Python objects
    (dicts/lists) ignores layout and key order automatically, so a pure
    reformat compares as equal while any value change shows up as different.
    """
    if not isinstance(s, str):
        return None
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return None


# ============================================================================
# FUNCTION 6 -- parse_and_validate
# ============================================================================
def parse_and_validate(response, original_trajectory, ground_truth):
    """
    Parse the model's reply and ENFORCE every presentation-change rule.

    This is the safety net of the whole experiment. If the model quietly broke
    a rule (renamed a tool, changed a value, reordered events), we must catch
    it here and flag it LOUDLY -- otherwise we would feed a secretly-altered
    trajectory to AgentRx and draw a wrong conclusion.

    Steps:
      1. Parse the model JSON (fail loudly if it is not valid JSON).
      2. Structure checks: both top-level keys present; events same length,
         same order, same roles.
      3. Hard-constraint checks per event: tool names unchanged, ids /
         tool_call_ids unchanged, and tool result / argument VALUES identical
         (only layout may differ).
      4. Freeze the authoritative failure from `ground_truth` into the sidecar,
         overwriting whatever the model guessed.

    Parameters
    ----------
    response : str
        The raw text the model returned (may contain ```json fences).
    original_trajectory : dict
        The input trajectory (from load_trajectory) -- our comparison baseline.
    ground_truth : dict or None
        The frozen ground-truth entry (from load_ground_truth), or None if the
        trajectory has no label.

    Returns
    -------
    dict with keys:
        "passed"               : bool  -- True iff there were zero violations.
        "violations"           : list of str -- human-readable problems found.
        "reworded_trajectory"  : dict  -- the model's reworded trajectory.
        "preservation_record"  : dict  -- the sidecar, with the TRUE failure
                                          frozen in from ground truth.
    """
    # We collect every problem we find here instead of stopping at the first,
    # so you see the full picture in one run.
    violations = []

    # ---- Step 1: parse the model JSON (loud failure on invalid JSON) ------
    # _extract_json_object raises ValueError if it cannot parse -- we let that
    # propagate, because an unparseable reply cannot be validated at all.
    data = _extract_json_object(response)

    # ---- Step 2: structure checks ----------------------------------------
    # Both top-level keys must exist.
    if "reworded_trajectory" not in data:
        violations.append("[STRUCTURE] missing top-level key "
                          "'reworded_trajectory'.")
    if "preservation_record" not in data:
        violations.append("[STRUCTURE] missing top-level key "
                          "'preservation_record'.")

    reworded = data.get("reworded_trajectory", {}) or {}
    preservation = data.get("preservation_record", {}) or {}

    original_events = original_trajectory.get("events", [])
    reworded_events = reworded.get("events", [])

    # Events must be present and be the same length. If not, deeper per-event
    # checks are meaningless, so we record the problem and skip them.
    can_compare_events = True
    if not isinstance(reworded_events, list):
        violations.append("[STRUCTURE] reworded 'events' is missing or not a "
                          "list.")
        can_compare_events = False
    elif len(reworded_events) != len(original_events):
        violations.append(
            f"[ORDER/LENGTH] event count changed: original has "
            f"{len(original_events)}, reworded has {len(reworded_events)}. "
            f"Events must not be added, removed, merged, or split."
        )
        can_compare_events = False

    # ---- Step 3: per-event hard-constraint checks ------------------------
    if can_compare_events:
        for i, (orig, new) in enumerate(zip(original_events, reworded_events)):
            # (a) Role must be unchanged (order + identity of each event).
            if orig.get("role") != new.get("role"):
                violations.append(
                    f"[ROLE CHANGED] event {i}: role went from "
                    f"{orig.get('role')!r} to {new.get('role')!r}."
                )
                # If the role flipped, comparing the rest is not meaningful.
                continue

            role = orig.get("role")

            # (a2) SYSTEM / POLICY events must be byte-for-byte identical.
            #      This backs the "we didn't touch the rulebook" guarantee:
            #      the policy is the standard the agent is judged against, so
            #      even a meaning-preserving paraphrase is forbidden here.
            #      We key on role == "system" (not "position 0") because only
            #      real traces start with a system message -- demo traces like
            #      the walkthrough start with a user message, which IS allowed
            #      to be reworded. A system event whose role was flipped to
            #      something else is already caught by the ROLE CHANGED check.
            #      We compare the WHOLE event dict (content + every other key),
            #      not just the parsed values, because layout changes count too.
            if role == "system":
                if orig != new:
                    # Name exactly which keys differ, to make the report useful.
                    changed_keys = sorted(
                        k for k in set(orig) | set(new)
                        if orig.get(k) != new.get(k)
                    )
                    violations.append(
                        f"[POLICY CHANGED] event {i}: the system/policy message "
                        f"was modified (keys differing: {changed_keys}). The "
                        f"rulebook must stay byte-for-byte identical."
                    )
                # Nothing else to check on a system event.
                continue

            # (b) Tool RESULT events: name, tool_call_id, and VALUES frozen.
            if role == "tool":
                if orig.get("name") != new.get("name"):
                    violations.append(
                        f"[TOOL NAME CHANGED] event {i}: "
                        f"{orig.get('name')!r} -> {new.get('name')!r}."
                    )
                if orig.get("tool_call_id") != new.get("tool_call_id"):
                    violations.append(
                        f"[ID CHANGED] event {i}: tool_call_id "
                        f"{orig.get('tool_call_id')!r} -> "
                        f"{new.get('tool_call_id')!r}."
                    )
                # Compare the VALUES inside the JSON-string content.
                orig_val = _json_or_none(orig.get("content"))
                new_val = _json_or_none(new.get("content"))
                if orig_val is not None and new_val is None:
                    violations.append(
                        f"[VALUE BROKEN] event {i}: reworded tool result is no "
                        f"longer valid JSON."
                    )
                elif orig_val is not None and orig_val != new_val:
                    violations.append(
                        f"[VALUE CHANGED] event {i}: tool result values differ "
                        f"(only layout/key-order may change, not values)."
                    )

            # (c) Assistant TOOL-CALL events: per-call name, id, and arg values.
            orig_calls = orig.get("tool_calls")
            new_calls = new.get("tool_calls")
            if bool(orig_calls) != bool(new_calls):
                violations.append(
                    f"[STRUCTURE] event {i}: tool_calls present in one version "
                    f"but not the other."
                )
            elif orig_calls and new_calls:
                if len(orig_calls) != len(new_calls):
                    violations.append(
                        f"[STRUCTURE] event {i}: number of tool_calls changed "
                        f"({len(orig_calls)} -> {len(new_calls)})."
                    )
                else:
                    for j, (oc, nc) in enumerate(zip(orig_calls, new_calls)):
                        of = oc.get("function", {})
                        nf = nc.get("function", {})
                        # tool name frozen
                        if of.get("name") != nf.get("name"):
                            violations.append(
                                f"[TOOL NAME CHANGED] event {i} call {j}: "
                                f"{of.get('name')!r} -> {nf.get('name')!r}."
                            )
                        # call id frozen
                        if oc.get("id") != nc.get("id"):
                            violations.append(
                                f"[ID CHANGED] event {i} call {j}: id "
                                f"{oc.get('id')!r} -> {nc.get('id')!r}."
                            )
                        # argument VALUES frozen (layout may differ)
                        ov = _json_or_none(of.get("arguments"))
                        nv = _json_or_none(nf.get("arguments"))
                        if ov is not None and nv is None:
                            violations.append(
                                f"[VALUE BROKEN] event {i} call {j}: reworded "
                                f"arguments are no longer valid JSON."
                            )
                        elif ov is not None and ov != nv:
                            violations.append(
                                f"[VALUE CHANGED] event {i} call {j}: tool-call "
                                f"argument values differ."
                            )

    # Also freeze the instruction: we agreed it must stay verbatim.
    if reworded.get("instruction") != original_trajectory.get("instruction"):
        violations.append(
            "[INSTRUCTION CHANGED] the 'instruction' field was modified; it "
            "must be left verbatim."
        )

    # ---- Step 4: freeze the authoritative failure from ground truth ------
    # Keep a copy of what the model GUESSED, for transparency / cross-check...
    preservation["model_guess"] = {
        "failure_step_index": preservation.get("failure_step_index"),
        "failure_category": preservation.get("failure_category"),
    }
    # ...then OVERWRITE the official fields from ground truth. Ground truth,
    # not the model, is the source of truth for the real failure.
    if ground_truth and ground_truth.get("failures"):
        failures = ground_truth["failures"]
        primary = failures[0]  # the first labeled failure is the primary one
        preservation["failure_step_index"] = primary.get("step_number")
        preservation["failure_category"] = primary.get("failure_category")
        preservation["failure_summary"] = primary.get("step_reason", "")
        preservation["failure_source"] = "ground_truth"
        # Store ALL labeled failures too, so nothing is dropped if there are
        # several. (step_number here is AgentRx's IR step numbering, which is
        # why we do not try to map it onto a raw event index.)
        preservation["ground_truth_failures"] = failures
    else:
        # No label (e.g. a demo trace): we cannot freeze a real failure.
        preservation["failure_source"] = "model_guess_no_ground_truth"
        print(
            "[WARNING] No ground truth available; the sidecar's failure fields "
            "remain the model's guess and are NOT authoritative."
        )

    # Always freeze the true action order from the ORIGINAL trajectory (we know
    # it for certain), overwriting any order the model reported.
    preservation["action_order"] = list(range(len(original_events)))

    # ---- Final verdict ----------------------------------------------------
    passed = (len(violations) == 0)

    # Print a loud, human-readable summary.
    if passed:
        print(f"[parse_and_validate] PASS -- no presentation-change "
              f"violations found.")
    else:
        print(f"[parse_and_validate] FAIL -- {len(violations)} violation(s):")
        for v in violations:
            print(f"    ❌ {v}")

    return {
        "passed": passed,
        "violations": violations,
        "reworded_trajectory": reworded,
        "preservation_record": preservation,
    }


# ============================================================================
# HELPER for FUNCTION 7 -- make a string safe to use as a folder/file name
# ============================================================================
def _safe_name(value):
    """
    Turn any value into a filesystem-safe name.

    Trajectory ids and model names can contain characters that are awkward in
    paths (spaces, slashes, '#', etc.). We keep letters, digits, '-', '_', and
    '.', and replace everything else with '_'. Example: "tau/retail 2" -> "tau_retail_2".
    """
    text = str(value)
    safe_chars = []
    for ch in text:
        if ch.isalnum() or ch in "-_.":
            safe_chars.append(ch)
        else:
            safe_chars.append("_")
    return "".join(safe_chars)


# ============================================================================
# FUNCTION 7 -- write_outputs
# ============================================================================
def write_outputs(reworded_trajectory, preservation_record, out_dir,
                  trajectory_id, model, validation=None):
    """
    Save the reworded trajectory and the sidecar as SEPARATE JSON files.

    Each run gets its own folder named by trajectory id AND model, so that
    Sonnet / Haiku / Opus runs never overwrite each other -- mirroring how
    AgentRx keeps distinct run-names. For trajectory "2" run with Haiku:

        <out_dir>/2__haiku/
            reworded_trajectory.json   <- feed THIS to AgentRx
            preservation_record.json   <- the frozen-truth sidecar
            validation_report.json     <- pass/fail + any violations

    Parameters
    ----------
    reworded_trajectory : dict
        The model's reworded trajectory (events format).
    preservation_record : dict
        The sidecar, with the true failure frozen in from ground truth.
    out_dir : str
        Base output directory (e.g. "runs/presentation_change").
    trajectory_id : str or int
        Id of the trajectory, used in the run-folder name.
    model : str
        Model name used, used in the run-folder name.
    validation : dict or None
        The result dict from parse_and_validate (for the validation report).

    Returns
    -------
    str
        The path to the run folder that was created.
    """
    # Build a distinct run folder: "<id>__<model>" keeps runs separated.
    run_folder_name = f"{_safe_name(trajectory_id)}__{_safe_name(model)}"
    run_dir = os.path.join(out_dir, run_folder_name)

    # Create the folder (and any missing parents). exist_ok=True means it is
    # fine if the folder already exists -- we just overwrite the files inside.
    os.makedirs(run_dir, exist_ok=True)

    # A tiny helper to write one object to one pretty-printed JSON file.
    def _dump(obj, filename):
        path = os.path.join(run_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        return path

    # 1) the reworded trajectory (what you feed back into AgentRx)
    _dump(reworded_trajectory, "reworded_trajectory.json")
    # 2) the sidecar with the frozen true failure
    _dump(preservation_record, "preservation_record.json")
    # 3) a small validation report so the pass/fail is saved alongside
    if validation is not None:
        report = {
            "trajectory_id": str(trajectory_id),
            "model": model,
            "passed": validation.get("passed"),
            "violations": validation.get("violations", []),
        }
        _dump(report, "validation_report.json")

    return run_dir


# ============================================================================
# main() -- wire functions 1..7 together as a command-line tool
# ============================================================================
def main():
    """
    Run the whole presentation-change pipeline from the command line.

    Order of operations:
        load_trajectory -> load_ground_truth -> load_policy_and_tools
        -> build_prompt -> call_model -> parse_and_validate -> write_outputs

    Example runs:
        # free dry-run on a labeled trace
        python presentation_change.py --trajectory data/.../2.json --dry-run

        # real run with a specific model
        python presentation_change.py --trajectory <path> --model haiku

        # run straight from the labeled dataset (no manual extraction)
        python presentation_change.py --from-dataset 2 --dry-run
    """
    # ---- Define the command-line options --------------------------------
    parser = argparse.ArgumentParser(
        description="Produce a presentation-only rewording of a failed agent "
                    "trajectory and check that the true failure is preserved."
    )
    # The input comes from EXACTLY ONE of two places: a trajectory file you
    # already have, or a task_id pulled out of the labeled dataset.
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--trajectory",
        help="Path to the input trajectory JSON (events format).",
    )
    source.add_argument(
        "--from-dataset", metavar="TASK_ID",
        help="Extract this task_id from the failed-trajectory dataset "
             "(see --dataset) and run on it directly.",
    )
    parser.add_argument(
        "--dataset", default=DEFAULT_DATASET_PATH,
        help="Path to the failed-trajectory dataset used by --from-dataset.",
    )
    parser.add_argument(
        "--model", default=None,
        help="Model to use: opus | sonnet | haiku (or a full name). "
             f"If omitted, uses ${MODEL_ENV_VAR} or '{DEFAULT_MODEL}'.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Do not call any model; use a realistic fake response (free).",
    )
    parser.add_argument(
        "--out-dir", default=os.path.join("runs", "presentation_change"),
        help="Base output directory (default: runs/presentation_change).",
    )
    parser.add_argument(
        "--domain", default="tau",
        help="Domain key for the policy/tools guardrails (default: tau).",
    )
    parser.add_argument(
        "--ground-truth", default=DEFAULT_GROUND_TRUTH_PATH,
        help="Path to the frozen ground-truth labels JSON.",
    )
    args = parser.parse_args()

    # Resolve the model name ONCE here, with the same precedence call_model
    # uses, so the run-folder name matches the model actually used.
    resolved_model = args.model or os.getenv(MODEL_ENV_VAR) or DEFAULT_MODEL

    print("=" * 70)
    print("PRESENTATION-CHANGE PIPELINE")
    if args.from_dataset is not None:
        print(f"  source     : dataset task_id={args.from_dataset} "
              f"({args.dataset})")
    else:
        print(f"  trajectory : {args.trajectory}")
    print(f"  model      : {resolved_model}")
    print(f"  dry-run    : {args.dry_run}")
    print("=" * 70)

    # ---- Step 0 (only with --from-dataset): extract the trace -----------
    # Pull the trace out of the dataset and save it in events format, then
    # point the normal loader at the saved file -- so the dataset path goes
    # through the exact same validation as a hand-supplied --trajectory.
    trajectory_path = args.trajectory
    if args.from_dataset is not None:
        _, trajectory_path = extract_trajectory(args.from_dataset,
                                                args.dataset)
        print(f"[0] Extracted dataset task_id={args.from_dataset} "
              f"-> {trajectory_path}")

    # ---- Step 1: load the trajectory ------------------------------------
    trajectory = load_trajectory(trajectory_path)
    trajectory_id = trajectory["trajectory_id"]
    print(f"[1] Loaded trajectory id={trajectory_id!r} "
          f"with {len(trajectory['events'])} events.")

    # ---- Step 2: load the frozen ground-truth failure -------------------
    ground_truth = load_ground_truth(trajectory_id, args.ground_truth)
    print(f"[2] Ground truth: "
          f"{'found' if ground_truth else 'NOT found (demo trace?)'}.")

    # ---- Step 3: load policy + tools (guardrails) -----------------------
    policy, tools, tools_structure = load_policy_and_tools(args.domain)
    print(f"[3] Loaded policy ({len(policy)} chars) and "
          f"{len(tools)} tool names for domain '{args.domain}'.")

    # ---- Step 4: build the prompt ---------------------------------------
    prompt = build_prompt(trajectory, policy, tools, tools_structure)
    print(f"[4] Built prompt ({len(prompt)} chars).")

    # ---- Step 5: call the model (or the dry-run fake) -------------------
    response = call_model(
        prompt,
        model=resolved_model,
        dry_run=args.dry_run,
        dry_run_reference=trajectory,  # lets the fake mirror this trace
    )
    print(f"[5] Got model response ({len(response)} chars).")

    # ---- Step 6: parse + enforce the hard constraints -------------------
    result = parse_and_validate(response, trajectory, ground_truth)

    # ---- Step 7: write the output files ---------------------------------
    run_dir = write_outputs(
        result["reworded_trajectory"],
        result["preservation_record"],
        args.out_dir,
        trajectory_id,
        resolved_model,
        validation=result,
    )
    print(f"[7] Wrote outputs to: {run_dir}")

    # ---- Final summary ---------------------------------------------------
    pr = result["preservation_record"]
    print("=" * 70)
    print("SUMMARY")
    print(f"  validation     : {'PASS' if result['passed'] else 'FAIL'}")
    print(f"  violations     : {len(result['violations'])}")
    print(f"  frozen failure : step={pr.get('failure_step_index')} "
          f"category={pr.get('failure_category')!r} "
          f"source={pr.get('failure_source')}")
    print(f"  output folder  : {run_dir}")
    print("=" * 70)

    # Exit non-zero if validation failed, so scripts/CI can detect it.
    sys.exit(0 if result["passed"] else 1)


# Standard Python entry point: only run main() when this file is executed
# directly (python presentation_change.py ...), not when it is imported.
if __name__ == "__main__":
    main()
