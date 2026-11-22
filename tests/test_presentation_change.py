"""Exercise presentation-change editing, generation, review gates, release and comparison
on the frozen Tau baseline. Mirrors tests/test_step_decoy.py: the Claude Code CLI is
replaced by a fake subprocess.run, so no model is called and the real ask_claude
(isolation flags, envelope and model checks) is exercised too."""
import json
import shutil
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agentrx.rewordings import presentation_change as pc
from agentrx.rewordings import step_decoy

DATA = pc.ROOT / "data/benchmark_versions"
TAU = DATA / "tau_retail/baseline/v1.0.0/tau_dataset_failed.json"
TAU_GT = DATA / "tau_retail/baseline/v1.0.0/tau_ground_truth.json"
MODEL = "claude-sonnet-5-5"

_, CASES, LABELS, _ = pc.load_dataset(TAU, TAU_GT)
TAU_ROLES = pc.resolve_roles("tau")  # assistant prose, system policy
EVENTS = CASES["2"]["events"]

# Tau task 2: root failure at step 7 (the assistant says 11 T-shirts; the answer is 10),
# other failure at step 3 (product lookup before authentication).
WORDING = dict(step=7, kind="wording", reason="paraphrase, count kept",
               text="Right now our online store offers 11 T-shirt options, each varying by color, size, "
                    "material, and style. Let me know if you'd like more details about any specific option!")
EMPHASIS = dict(step=9, kind="emphasis", reason="bold the request", text="**" + EVENTS[8]["content"] + "**")
FORMAT_RESULT = dict(step=6, kind="formatting", layout="indented", key_order="sorted", reason="re-layout")
FORMAT_ARGS = dict(step=5, kind="formatting", layout="spaced", key_order="original", reason="re-layout")
PROPOSAL = dict(decision="EDIT", edits=[WORDING, EMPHASIS, FORMAT_RESULT, FORMAT_ARGS],
                rationale="Edits around both failures.",
                preservation_evidence="Step 3 still looks up products first; step 7 still says 11.")


def fake_claude(answer, model=MODEL):
    """Stand in for the Claude Code CLI: answer --version and each -p generation call.
    `answer` is a proposal, or a function from the prompt to a proposal."""
    def run(cmd, **kwargs):
        if cmd[1:] == ["--version"]:
            return SimpleNamespace(returncode=0, stdout="9.9.9 (Claude Code)\n", stderr="")
        proposal = answer(kwargs["input"]) if callable(answer) else answer
        envelope = dict(type="result", is_error=False, num_turns=1, session_id="s", duration_ms=1,
                        total_cost_usd=0.01, structured_output=proposal, result=json.dumps(proposal),
                        modelUsage={model: {"outputTokens": 1}})
        return SimpleNamespace(returncode=0, stdout=json.dumps(envelope), stderr="")
    return run


def generate_args(work, **overrides):
    return Namespace(**{**dict(domain="tau", trajectories=TAU, ground_truth=TAU_GT, policy=None, work=work,
                               ids=["2"], model="sonnet", effort="medium", claude_bin="claude", timeout=10,
                               regenerate=None, max_attempts=3, prose_roles=None, policy_roles=None),
                         **overrides})


def edit(**item):
    return dict(PROPOSAL, edits=[dict(reason="r", **item)])


def valid_proposal_for(tid):
    """A legal proposal for any Tau case: emphasis on the first prose step and a
    re-layout of the first JSON step, built from the case itself."""
    case, label = CASES[tid], LABELS[tid]
    allowed, edits = pc.editable_steps(case, label, TAU_ROLES), []
    prose = [n for n, kinds in allowed.items() if "emphasis" in kinds]
    if prose:
        edits.append(dict(step=prose[0], kind="emphasis", reason="bold",
                          text="**" + case["events"][prose[0] - 1]["content"] + "**"))
    fmt = [n for n, kinds in allowed.items() if "formatting" in kinds]
    if fmt:
        event, is_result = case["events"][fmt[0] - 1], fmt[0] in pc.tool_results(case["events"])
        layout, order = next((l, o) for l in pc.LAYOUTS for o in pc.KEY_ORDERS
                             if any(pc.serialize(v, l, o) != pc.get_path(event, p)
                                    for p, v in pc.payloads(event, is_result)))
        edits.append(dict(step=fmt[0], kind="formatting", layout=layout, key_order=order, reason="re-layout"))
    return dict(PROPOSAL, edits=edits)


def case_of(prompt):
    """Which trajectory a prompt is for: the longest task instruction it contains
    (task 71's instruction is a substring of task 72's)."""
    return max((t for t in CASES if pc.instruction(CASES[t]) in prompt), key=lambda t: len(pc.instruction(CASES[t])))


def accept_all(work, path=None, **overrides):
    """Signed accept reviews for every reviewable case, bound to its events_sha256."""
    reviews = {}
    for tid in CASES:
        validation = work / pc.safe_name(tid) / "validation.json"
        if validation.exists():
            reviews[tid] = dict(decision="accept", reviewer="fixture", reason="Synthetic review for regression test",
                                events_sha256=pc.read(validation)["events_sha256"])
    for tid, change in overrides.items():
        reviews[tid] = {**reviews.get(tid, {}), **change} if change is not None else None
    reviews = {t: r for t, r in reviews.items() if r is not None}
    pc.write(path or work / "reviews.json", reviews)
    return path or work / "reviews.json"


class EditRulesTest(unittest.TestCase):
    def test_editable_steps_lock_policy_users_and_failure_formatting(self):
        allowed = pc.editable_steps(CASES["2"], LABELS["2"], TAU_ROLES)
        self.assertNotIn(1, allowed)                     # system policy
        for n, event in enumerate(EVENTS, 1):
            if event["role"] == "user":
                self.assertNotIn(n, allowed)             # user turns are locked
        self.assertNotIn(3, allowed)                     # failure step with no prose
        self.assertEqual(allowed[7], ["wording", "emphasis"])  # root failure: prose only, no formatting
        self.assertNotIn(12, allowed)                    # non-JSON tool response 'yusuf_rossi_9620'
        self.assertEqual(allowed[6], ["formatting"])

    def test_valid_edits_apply_only_to_their_fields(self):
        events, changes = pc.apply_edits(CASES["2"], LABELS["2"], PROPOSAL, TAU_ROLES)
        self.assertEqual([(c["step"], c["kind"]) for c in changes],
                         [(5, "formatting"), (6, "formatting"), (7, "wording"), (9, "emphasis")])
        self.assertEqual(events[6]["content"], WORDING["text"])
        self.assertEqual(events[8]["content"], EMPHASIS["text"])
        self.assertEqual(events[5]["content"], json.dumps(json.loads(EVENTS[5]["content"]), indent=2,
                                                          sort_keys=True, ensure_ascii=False))
        self.assertEqual(events[4]["tool_calls"][0]["function"]["arguments"], '{"product_id": "9523456873"}')
        for n, (before, after) in enumerate(zip(EVENTS, events), 1):
            if n not in (5, 6, 7, 9):
                self.assertEqual(before, after, f"step {n} changed")
        # Formatting changes layout only: same call ids and names, same parsed values.
        self.assertEqual({k: v for k, v in events[4]["tool_calls"][0].items() if k != "function"},
                         {k: v for k, v in EVENTS[4]["tool_calls"][0].items() if k != "function"})
        self.assertEqual(json.loads(events[5]["content"]), json.loads(EVENTS[5]["content"]))
        self.assertEqual(pc.check_preserved(EVENTS, events, {5, 6, 7, 9}, TAU_ROLES), [])

    def test_rejects_rule_breaks(self):
        bad = {
            "policy (locked step 1)": (edit(step=1, kind="wording", text="A different policy"), "not editable"),
            "user turn": (edit(step=2, kind="wording", text="How many tees do you have?"), "not editable"),
            "formatting on the root failure step": (
                edit(step=7, kind="formatting", layout="indented", key_order="sorted"), "allows"),
            "formatting on the other failure step": (
                edit(step=3, kind="formatting", layout="indented", key_order="sorted"), "not editable"),
            "dropped digit ('eleven' for '11')": (
                edit(step=7, kind="wording", text="There are eleven T-shirt options."), "drops values"),
            "digit token changed ('110' contains '11')": (
                edit(step=7, kind="wording", text="There are 110 T-shirt options."), "drops values"),
            "emphasis changing words": (
                edit(step=9, kind="emphasis", text="**Happy to help with your return!**"), "changed the words"),
            "non-JSON tool response": (
                edit(step=12, kind="formatting", layout="indented", key_order="sorted"), "not editable"),
            "no-op formatting": (edit(step=5, kind="formatting", layout="compact", key_order="original"),
                                 "unchanged"),
            "text on formatting": (edit(step=6, kind="formatting", layout="indented", key_order="sorted", text="x"),
                                   "not text"),
            "layout on wording": (edit(step=9, kind="wording", text="Sure!", layout="indented"),
                                  "not layout"),
            "unchanged text": (edit(step=9, kind="wording", text=EVENTS[8]["content"]), "differs"),
            "two prose edits on one step": (dict(PROPOSAL, edits=[EMPHASIS, dict(WORDING, step=9)]),
                                            "more than one"),
            "missing reason": (dict(PROPOSAL, edits=[{k: v for k, v in EMPHASIS.items() if k != "reason"}]),
                               "missing reason"),
            "missing preservation evidence": (
                {k: v for k, v in PROPOSAL.items() if k != "preservation_evidence"}, "preservation_evidence"),
            "no edits": (dict(PROPOSAL, edits=[]), "at least one"),
        }
        for name, (proposal, message) in bad.items():
            with self.subTest(name), self.assertRaisesRegex(ValueError, message):
                pc.apply_edits(CASES["2"], LABELS["2"], proposal, TAU_ROLES)

    def test_digit_tokens_must_match_whole(self):
        case = dict(events=[dict(role="assistant", content="11 available")])
        label = dict(failures=[])
        for text in ("110 available", "#11 available", "1 available"):
            with self.subTest(text):
                with self.assertRaisesRegex(ValueError, r"drops values \['11'\]"):
                    pc.apply_edits(case, label, edit(step=1, kind="wording", text=text), TAU_ROLES)
                self.assertTrue(any("VALUE DROPPED" in v for v in pc.check_preserved(
                    case["events"], [dict(role="assistant", content=text)], {1}, TAU_ROLES)))
        # Surrounding punctuation and markdown are not part of the token.
        events, _ = pc.apply_edits(case, label, edit(step=1, kind="wording", text="Available: **11**."), TAU_ROLES)
        self.assertEqual(events[0]["content"], "Available: **11**.")

    def test_check_preserved_catches_tampering(self):
        events, _ = pc.apply_edits(CASES["2"], LABELS["2"], PROPOSAL, TAU_ROLES)
        tamper = {
            "tool name": (lambda e: e[4]["tool_calls"][0]["function"].update(name="get_item_details"),
                          "TOOL NAME/ID CHANGED"),
            "call id": (lambda e: e[4]["tool_calls"][0].update(id="call_x"), "TOOL NAME/ID CHANGED"),
            "tool result value": (lambda e: e[5].update(content=e[5]["content"].replace("50.88", "50.89", 1)),
                                  "VALUE CHANGED"),
            "value type only (number -> true)": (
                lambda e: e[5].update(content=e[5]["content"].replace("50.88", "true", 1)), "VALUE CHANGED"),
            "argument value": (lambda e: e[4]["tool_calls"][0]["function"].update(
                arguments='{"product_id": "9523456874"}'), "VALUE CHANGED"),
            "policy": (lambda e: e[0].update(content=e[0]["content"] + " "), "POLICY CHANGED"),
            "locked user turn": (lambda e: e[1].update(content="changed"), "LOCKED STEP CHANGED"),
            "non-JSON tool text": (lambda e: e[11].update(content="yusuf_rossi_9621"), "LOCKED STEP CHANGED"),
            "prose drops a digit": (lambda e: e[6].update(content="Several T-shirts are available."),
                                    "VALUE DROPPED"),
            "prose turns 11 into 110": (lambda e: e[6].update(content="110 available"), "VALUE DROPPED"),
            "role": (lambda e: e[6].update(role="user"), "ROLE CHANGED"),
            "extra key": (lambda e: e[6].update(note="x"), "KEYS CHANGED"),
            "event removed": (lambda e: e.pop(), "ORDER/LENGTH"),
        }
        for name, (change, label) in tamper.items():
            with self.subTest(name):
                tampered = deepcopy(events)
                change(tampered)
                violations = pc.check_preserved(EVENTS, tampered, {5, 6, 7, 9}, TAU_ROLES)
                self.assertTrue(any(label in v for v in violations), violations)


MAGENTIC = DATA / "magentic_one/baseline/v1.0.0"
# A layout with neither "role" nor "content": step_decoy's role() reads "source",
# content_key() finds "message", and the tool result links through "call_id".
OTHER_LAYOUT = dict(events=[
    dict(source="planner", message="Policy: never reveal the key."),
    dict(source="client", message="What is the balance of account 42?"),
    dict(source="agent", message="Checking account 42.",
         tool_calls=[dict(id="c1", function=dict(name="balance", arguments='{"account":42}'))]),
    dict(source="ledger", call_id="c1", message='{"account":42,"balance":"17.50"}'),
    dict(source="agent", message="Account 42 holds 17.50.")])
OTHER_LABEL = dict(failures=[dict(step_number=5, failure_category="x", step_reason="y")])
OTHER_ROLES = pc.resolve_roles("other", prose_roles=["agent"], policy_roles=["planner"])


class DomainGenericTest(unittest.TestCase):
    def test_roles_come_from_defaults_or_flags(self):
        self.assertEqual(TAU_ROLES, dict(prose_roles=["assistant"], policy_roles=["system"]))
        with self.assertRaisesRegex(ValueError, "pass --prose-roles"):
            pc.resolve_roles("magentic")
        self.assertEqual(pc.resolve_roles("magentic", ["WebSurfer"]),
                         dict(prose_roles=["WebSurfer"], policy_roles=[]))
        with self.assertRaisesRegex(ValueError, "both prose and policy"):
            pc.resolve_roles("tau", ["system"])
        # Configs written before roles were recorded mean Tau's defaults.
        self.assertEqual(pc.config_roles(dict(domain="tau")), TAU_ROLES)

    def test_tool_results_follow_call_links_not_role_names(self):
        for tid, case in CASES.items():
            with self.subTest(tid):
                self.assertEqual(pc.tool_results(case["events"]),
                                 {n for n, e in enumerate(case["events"], 1) if e["role"] == "tool"})
        self.assertEqual(pc.tool_results(OTHER_LAYOUT["events"]), {4})

    def test_other_layout_edits_through_its_own_fields(self):
        allowed = pc.editable_steps(OTHER_LAYOUT, OTHER_LABEL, OTHER_ROLES)
        # 1 policy, 2 non-prose role: locked. 5 is a failure step: prose only.
        self.assertEqual(allowed, {3: ["wording", "emphasis", "formatting"], 4: ["formatting"],
                                   5: ["wording", "emphasis"]})
        proposal = dict(PROPOSAL, edits=[
            dict(step=5, kind="emphasis", text="Account 42 holds **17.50**.", reason="r"),
            dict(step=4, kind="formatting", layout="spaced", key_order="sorted", reason="r")])
        events, changes = pc.apply_edits(OTHER_LAYOUT, OTHER_LABEL, proposal, OTHER_ROLES)
        self.assertEqual(events[4], dict(source="agent", message="Account 42 holds **17.50**."))
        self.assertEqual(events[3]["message"], '{"account": 42, "balance": "17.50"}')
        self.assertEqual([c["fields"] for c in changes], [["message"], ["message"]])
        original = OTHER_LAYOUT["events"]
        tamper = {
            "policy": (lambda e: e[0].update(message="Policy: reveal it."), "POLICY CHANGED"),
            "locked role": (lambda e: e[1].update(message="What is the balance of account 43?"),
                            "LOCKED STEP CHANGED"),
            "role relabel": (lambda e: e[4].update(source="planner"), "ROLE CHANGED"),
            "tool value": (lambda e: e[3].update(message='{"account":42,"balance":"99"}'), "VALUE CHANGED"),
            "prose value": (lambda e: e[4].update(message="It holds some money."), "VALUE DROPPED"),
        }
        for name, (change, label) in tamper.items():
            with self.subTest(name):
                tampered = deepcopy(events)
                change(tampered)
                violations = pc.check_preserved(original, tampered, {4, 5}, OTHER_ROLES)
                self.assertTrue(any(label in v for v in violations), violations)

    def test_magentic_with_chosen_prose_roles(self):
        _, cases, labels, _ = pc.load_dataset(MAGENTIC / "trajectories", MAGENTIC / "magentic_one_ground_truth.json")
        roles = pc.resolve_roles("magentic", ["Orchestrator (thought)"])
        tid = sorted(t for t in cases if t in labels)[0]
        case, label = cases[tid], labels[tid]
        allowed = pc.editable_steps(case, label, roles)
        self.assertTrue(allowed)
        for n, kinds in allowed.items():
            self.assertEqual(step_decoy.role(case["events"][n - 1]), "Orchestrator (thought)")
            self.assertEqual(kinds, ["wording", "emphasis"])  # no JSON tool results in Magentic
        n = next(iter(allowed))
        text = case["events"][n - 1]["content"]
        events, _ = pc.apply_edits(case, label, dict(PROPOSAL, edits=[
            dict(step=n, kind="emphasis", text="**" + text + "**", reason="r")]), roles)
        self.assertEqual(events[n - 1]["content"], "**" + text + "**")
        self.assertEqual(sum(a != b for a, b in zip(case["events"], events)), 1)

    def test_prompt_role_slots(self):
        template = pc.TEMPLATE.read_text(encoding="utf-8")
        for name in ("assistant", "user messages", "system messages"):
            self.assertNotIn(name, template)                 # the template names no role itself
        slots = pc.role_slots(CASES, TAU_ROLES)
        self.assertEqual(slots, dict(
            PROSE_MESSAGE="an assistant message", TOOL_CALL_MESSAGE="an assistant message",
            LOCKED_STEPS="system messages (the policy), user messages and tool responses that are not JSON"))
        filled = pc.fill_role_slots(template, slots)
        # Tau's filled prompt is the earlier hand-written one, so prompt_sha256 is unchanged.
        self.assertIn("Paraphrase the natural-language content of an assistant message.", filled)
        self.assertIn("the arguments of the tool calls an assistant message makes.", filled)
        self.assertTrue(pc.digest((pc.SYSTEM + "\n" + filled).encode()).startswith("5fd8b3fb1768"))
        _, cases, _, _ = pc.load_dataset(MAGENTIC / "trajectories", MAGENTIC / "magentic_one_ground_truth.json")
        slots = pc.role_slots(cases, pc.resolve_roles("magentic", ["Orchestrator (thought)", "Assistant"]))
        self.assertEqual(slots["PROSE_MESSAGE"], "an Assistant or Orchestrator (thought) message")
        self.assertEqual(slots["TOOL_CALL_MESSAGE"], "a message")        # Magentic makes no tool calls
        self.assertTrue(slots["LOCKED_STEPS"].startswith("ComputerTerminal, FileSurfer, "))
        self.assertTrue(slots["LOCKED_STEPS"].endswith("WebSurfer and human messages and tool responses that are not JSON"))
        self.assertEqual(pc.role_slots({"x": OTHER_LAYOUT}, OTHER_ROLES), dict(
            PROSE_MESSAGE="an agent message", TOOL_CALL_MESSAGE="an agent message",
            LOCKED_STEPS="planner messages (the policy), client messages and tool responses that are not JSON"))
        with self.assertRaisesRegex(ValueError, "may not contain"):
            pc.fill_role_slots(template, dict(slots, PROSE_MESSAGE="a <<POLICY>> message"))
        with self.assertRaisesRegex(ValueError, "every role slot"):
            pc.fill_role_slots(template.replace("<<LOCKED_STEPS>>", "x"), slots)

    def test_generate_locks_roles_in_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            with patch("subprocess.run", fake_claude(PROPOSAL)), redirect_stdout(StringIO()):
                pc.generate(generate_args(work))
                config = pc.read(work / "config.json")
                self.assertEqual((config["prose_roles"], config["policy_roles"]), (["assistant"], ["system"]))
                with self.assertRaisesRegex(ValueError, "different configuration"):
                    pc.generate(generate_args(work, prose_roles=["assistant", "user"]))
                # A config from before roles were recorded still resumes with Tau's defaults...
                pc.write(work / "config.json", {k: v for k, v in config.items() if not k.endswith("_roles")})
                pc.generate(generate_args(work))
                # ...but not with different roles.
                with self.assertRaisesRegex(ValueError, "different configuration"):
                    pc.generate(generate_args(work, policy_roles=[]))


class GenerateTest(unittest.TestCase):
    def test_generate_isolates_the_call_and_records_the_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            with patch.object(pc.subprocess, "run", side_effect=fake_claude(PROPOSAL)) as cli:
                pc.generate(generate_args(work))
                calls = [c for c in cli.call_args_list if "-p" in c.args[0]]
                self.assertEqual(len(calls), 1)
                cmd, kwargs = calls[0].args[0], calls[0].kwargs
                self.assertEqual(cmd[cmd.index("--model") + 1], MODEL)        # full ID, not the alias
                self.assertEqual(cmd[cmd.index("--effort") + 1], "medium")
                self.assertEqual(cmd[cmd.index("--tools") + 1], "")
                for flag in ("--safe-mode", "--strict-mcp-config", "--disable-slash-commands",
                             "--no-session-persistence"):
                    self.assertIn(flag, cmd)
                self.assertEqual(cmd[cmd.index("--output-format") + 1], "json")
                self.assertEqual(json.loads(cmd[cmd.index("--json-schema") + 1]), pc.SCHEMA)
                self.assertEqual(cmd[cmd.index("--system-prompt") + 1], pc.SYSTEM)
                self.assertNotEqual(Path(kwargs["cwd"]).resolve(), pc.ROOT)  # an empty temp dir, not the repo
                message = kwargs["input"]
                self.assertNotRegex(message, r"<<[A-Z_]+>>")
                self.assertIn("**Domain:** tau", message)
                self.assertIn("You are Yusuf Rossi in 19122", message)
                self.assertIn('"step_number": 7', message.split("**Annotated Root Failure:**")[1][:600])
                self.assertIn('"step_number": 3', message.split("**Other Annotated Failures**")[1][:600])
                self.assertIn('{"step": 7, "role": "assistant", "kinds": ["wording", "emphasis"]}', message)
            generation = pc.read(work / "2/generation.json")
            self.assertEqual(generation["claude_version"], "9.9.9 (Claude Code)")
            self.assertIn(MODEL, generation["model_usage"])
            self.assertEqual(generation["helpers_sha256"], pc.digest(Path(step_decoy.__file__).read_bytes()))
            validation = pc.read(work / "2/validation.json")
            self.assertEqual(validation["events_sha256"], pc.digest((work / "2/events.json").read_bytes()))
            self.assertEqual(pc.read(work / "config.json")["variant"], "presentation_change")

    def test_answer_from_another_model_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(pc.subprocess, "run", side_effect=fake_claude(PROPOSAL, model="claude-haiku-5-5")):
                with self.assertRaisesRegex(ValueError, "Requested claude-sonnet-5-5"):
                    pc.generate(generate_args(Path(tmp) / "work"))

    def test_label_without_root_cause_skips_the_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            label = {k: v for k, v in LABELS["2"].items() if k != "root_cause"}
            pc.write(Path(tmp) / "gt.json", [label])
            with patch.object(pc.subprocess, "run") as cli:
                pc.generate(generate_args(Path(tmp) / "work", ground_truth=Path(tmp) / "gt.json"))
                cli.assert_not_called()
            self.assertEqual(pc.read(Path(tmp) / "work/2/proposal.json")["decision"], "NO_VALID_EDIT")

    def test_invalid_proposal_is_kept_then_regenerated_up_to_the_cap(self):
        bad = edit(step=2, kind="wording", text="How many tees?")
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            with patch.object(pc.subprocess, "run", side_effect=fake_claude(bad)) as cli:
                pc.generate(generate_args(work))
                self.assertIn("not editable", pc.read(work / "2/invalid.json")["error"])
                self.assertFalse((work / "2/events.json").exists())
                calls = len(cli.call_args_list)
                pc.generate(generate_args(work))                       # resume: nothing redone
                self.assertEqual(len(cli.call_args_list), calls)
                pc.generate(generate_args(work, regenerate=["2"]))     # attempt 2
                pc.generate(generate_args(work, regenerate=["2"]))     # attempt 3
                self.assertEqual(sorted(p.name for p in (work / pc.SUPERSEDED / "2").iterdir()), ["1", "2"])
                self.assertEqual(pc.attempts_used(work, "2"), 3)
                with self.assertRaisesRegex(ValueError, "Attempt cap reached"):
                    pc.generate(generate_args(work, regenerate=["2"]))
                self.assertTrue((work / "2/invalid.json").exists())    # nothing moved by the refusal
            with self.assertRaisesRegex(ValueError, "different configuration"):
                pc.generate(generate_args(work, max_attempts=10))      # the cap is locked
            with self.assertRaisesRegex(ValueError, "IDs this run covers"):
                pc.generate(generate_args(work, regenerate=["3"]))


class ReleaseTest(unittest.TestCase):
    """One full 29-case work directory, generated once; each test copies it before changing it."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.work = Path(cls.tmp.name) / "work"
        with patch.object(pc.subprocess, "run", side_effect=fake_claude(lambda p: valid_proposal_for(case_of(p)))), \
                redirect_stdout(StringIO()):
            pc.generate(generate_args(cls.work, ids=None))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def copy(self, name):
        target = Path(self.tmp.name) / name
        shutil.copytree(self.work, target)
        return target

    def release(self, work, reviews, out, version="v0.1.0"):
        with redirect_stdout(StringIO()):
            pc.release(Namespace(work=work, reviews=reviews, version=version, out=out))
        return out / "sonnet" / version

    def test_every_case_was_generated_validly(self):
        self.assertEqual(sorted(p.name for p in self.work.iterdir() if (p / "events.json").exists()),
                         sorted(pc.safe_name(t) for t in CASES))

    def test_release_refuses_until_all_cases_are_accepted(self):
        out = Path(self.tmp.name) / "refused"

        def refused(work, reviews, message):
            with self.assertRaisesRegex(ValueError, message):
                self.release(work, reviews, out)
            self.assertFalse((out / "sonnet/v0.1.0").exists())

        with self.subTest("missing case"):
            work = self.copy("missing")
            shutil.rmtree(work / "12")
            refused(work, accept_all(work), r"12: not generated yet")
        with self.subTest("invalid case"):
            work = self.copy("invalid")
            for name in ("events.json", "validation.json"):
                (work / "31" / name).unlink()
            pc.write(work / "31/invalid.json", {"error": "Step 2 is not editable", "violations": []})
            refused(work, accept_all(work), r"31: failed validation: Step 2.*--regenerate 31; attempt 1 of 3")
        with self.subTest("stale review"):
            refused(self.work, accept_all(self.work, Path(self.tmp.name) / "stale.json",
                                          **{"4": {"events_sha256": "0" * 64}}), r"4: the review approves different events")
        with self.subTest("missing review"):
            refused(self.work, accept_all(self.work, Path(self.tmp.name) / "partial.json", **{"20": None}),
                    r"20: needs a signed review")
        with self.subTest("unsigned review"):
            refused(self.work, accept_all(self.work, Path(self.tmp.name) / "unsigned.json", **{"20": {"reviewer": ""}}),
                    r"20: needs a signed review")
        with self.subTest("rejected"):
            refused(self.work, accept_all(self.work, Path(self.tmp.name) / "rejected.json",
                                          **{"21": {"decision": "reject"}}), r"21: rejected by fixture")
        with self.subTest("events edited after generation"):
            work = self.copy("drift")
            events = pc.read(work / "28/events.json")
            events[-1]["content"] += " "
            pc.write(work / "28/events.json", events)
            reviews = accept_all(work)
            data = pc.read(reviews)
            data["28"]["events_sha256"] = pc.digest((work / "28/events.json").read_bytes())  # reviewer saw the edit
            pc.write(reviews, data)
            refused(work, reviews, r"28: candidate changed since generation")
        with self.subTest("incomplete: a pilot work directory (1 of 29)"):
            pilot = Path(self.tmp.name) / "pilot"
            with patch.object(pc.subprocess, "run", side_effect=fake_claude(PROPOSAL)), redirect_stdout(StringIO()):
                pc.generate(generate_args(pilot))
            refused(pilot, accept_all(pilot), r"covers 1 of 29")

    def capped(self, name, tid):
        """A copy of the work directory where `tid` has used all 3 attempts."""
        work = self.copy(name)
        for n in ("1", "2"):
            shutil.copytree(work / tid, work / pc.SUPERSEDED / tid / n)
        return work

    def test_capped_cases_are_excluded_with_their_reason(self):
        work = self.capped("capped", "28")
        for name in ("events.json", "validation.json"):
            (work / "28" / name).unlink()
        pc.write(work / "28/invalid.json", {"error": "Step 33 is not editable", "violations": []})
        work_rejected = self.capped("capped-rejected", "21")
        out = Path(self.tmp.name) / "excluded"
        for label, w, reviews, tid, reason in [
                ("invalid at the cap", work, accept_all(work), "28",
                 "attempt cap reached (3 of 3); final attempt failed validation: Step 33 is not editable"),
                ("rejected at the cap", work_rejected,
                 accept_all(work_rejected, **{"21": {"decision": "reject", "reason": "too loose"}}), "21",
                 "attempt cap reached (3 of 3); final attempt rejected by fixture: too loose")]:
            with self.subTest(label):
                target = self.release(w, reviews, out / tid)
                manifest = pc.read(target / "manifest.json")
                self.assertEqual(manifest["excluded_ids"], [tid])
                self.assertEqual(manifest["excluded"], {tid: reason})
                self.assertEqual(manifest["attempted_count"], 29)            # every case, as step_decoy
                self.assertEqual(len(manifest["accepted_ids"]), 28)
                self.assertNotIn(tid, manifest["accepted_ids"])
                self.assertEqual(manifest["regenerated"], {tid: 2})
                ids = {str(r["task_id"]) for r in pc.read(target / "trajectories/tau_dataset_failed.json")}
                self.assertEqual(ids, set(CASES) - {tid})
                self.assertEqual({str(l["trajectory_id"]) for l in pc.read(target / "ground_truth.json")}, ids)
                audit = pc.read(target / "audit.json")
                self.assertEqual(audit[tid]["excluded"], reason)
                self.assertEqual(len(audit[tid]["superseded"]), 2)         # every attempt documented
        # Only stuck cases are excluded: at the cap, a missing review or drift still blocks.
        with self.subTest("missing review at the cap"), self.assertRaisesRegex(ValueError, "21: needs a signed review"):
            self.release(work_rejected, accept_all(work_rejected, Path(self.tmp.name) / "r.json", **{"21": None}),
                         out / "blocked")
        with self.subTest("drift at the cap"), self.assertRaisesRegex(ValueError, "21: candidate changed"):
            events = pc.read(work_rejected / "21/events.json")
            events[-1]["content"] += " "
            pc.write(work_rejected / "21/events.json", events)
            reviews = accept_all(work_rejected, Path(self.tmp.name) / "d.json")
            data = pc.read(reviews)
            data["21"]["events_sha256"] = pc.digest((work_rejected / "21/events.json").read_bytes())
            pc.write(reviews, data)
            self.release(work_rejected, reviews, out / "blocked")
        self.assertFalse((out / "blocked").exists())

    def test_release_of_all_29(self):
        out = Path(self.tmp.name) / "released"
        target = self.release(self.work, accept_all(self.work), out)
        self.assertEqual(sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()),
                         ["audit.json", "ground_truth.json", "manifest.json", "trajectories/tau_dataset_failed.json"])
        with self.assertRaisesRegex(ValueError, "Release already exists"):
            self.release(self.work, accept_all(self.work), out)
        # Same records as the baseline apart from traj, which matches the reviewed events.
        released, baseline = pc.read(target / "trajectories/tau_dataset_failed.json"), json.loads(TAU.read_text())
        self.assertEqual(len(released), 29)
        for row, original in zip(released, baseline):
            self.assertEqual({k: v for k, v in row.items() if k != "traj"},
                             {k: v for k, v in original.items() if k != "traj"})
            self.assertEqual(row["traj"], pc.read(self.work / str(row["task_id"]) / "events.json"))
        # Labels unchanged except original_step_number (= step_number, as steps never move).
        for label in pc.read(target / "ground_truth.json"):
            for failure in label["failures"]:
                self.assertEqual(failure.pop("original_step_number"), failure["step_number"])
            self.assertEqual(label, LABELS[str(label["trajectory_id"])])
        audit = pc.read(target / "audit.json")
        self.assertEqual(audit["2"]["root"], {"step_number": 7, "failure_category": "Misinterpretation of Tool Output"})
        self.assertEqual(audit["2"]["attempt"], 1)
        manifest = pc.read(target / "manifest.json")
        self.assertEqual((manifest["variant"], manifest["generator"]["model_id"], manifest["generator"]["max_attempts"]),
                         ("presentation_change", MODEL, 3))
        self.assertEqual((manifest["excluded_ids"], manifest["excluded"], manifest["attempted_count"]), ([], {}, 29))
        self.assertEqual(len(manifest["accepted_ids"]), manifest["attempted_count"])
        self.assertEqual(manifest["parent"]["sha256"]["ground_truth"], pc.digest(TAU_GT.read_bytes()))
        for name, sha in manifest["artifact_sha256"].items():
            self.assertEqual(sha, pc.digest((target / name).read_bytes()))
        self.assertEqual(manifest["helpers_sha256"], [pc.digest(Path(step_decoy.__file__).read_bytes())])

    def test_review_sheet_reports_cases_and_review_state(self):
        work = self.copy("sheet")
        reviews = accept_all(work, **{"4": {"events_sha256": "0" * 64}, "12": None})
        with redirect_stdout(StringIO()):
            pc.review_sheet(Namespace(work=work, reviews=reviews))
        sheet = (work / "review_sheet.md").read_text()
        self.assertIn("29 ready for review, 0 invalid", sheet)
        self.assertIn("27 current, 1 stale, 1 missing", sheet)
        self.assertNotIn("Suggested", sheet)
        template = pc.read(work / "reviews.template.json")
        self.assertEqual(len(template), 29)
        self.assertEqual(template["2"], dict(decision="", reviewer="", reason="",
                                             events_sha256=pc.read(work / "2/validation.json")["events_sha256"]))


class CompareTest(unittest.TestCase):
    ROOTS = {"1": (7, "Misinterpretation of Tool Output"), "2": (5, "Underspecified User Intent"),
             "3": (9, "Intent Plan Misalignment"), "4": (3, "Invalid Invocation"),
             "5": (4, "Instruction Adherence Failure"), "6": (6, "System Failure"), "7": (8, "Intent Not Supported")}

    def run_compare(self, clean, variant):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pc.write(tmp / "audit.json", {t: {"root": {"step_number": s, "failure_category": c}}
                                          for t, (s, c) in self.ROOTS.items()})

            def report(rows):  # the judge writes the category as an integer FailureCase code
                return {"detailed_results": [{"task_id": t, "failures": [
                    {"step_number": s, "failure_case": pc.convert_to_failure_case(c).value}]} for t, (s, c) in rows.items()]}
            pc.write(tmp / "clean.json", report(clean))
            pc.write(tmp / "variant.json", report(variant))
            output = StringIO()
            with redirect_stdout(output):
                pc.compare(Namespace(audit=tmp / "audit.json", clean=tmp / "clean.json", variant=tmp / "variant.json"))
            return json.loads(output.getvalue())

    def test_classifies_each_outcome(self):
        clean = dict(self.ROOTS)
        clean["5"] = (4, "System Failure")       # right step, wrong category: paired, but not fully correct
        clean["6"] = (2, "System Failure")       # clean miss
        variant = dict(clean)
        variant["2"] = (6, "Underspecified User Intent")       # step moved
        variant["3"] = (9, "Invention of New Information")     # category changed, same step
        variant["4"] = (2, "Intent Not Supported")             # both changed
        del variant["7"]                                      # missing prediction
        result = self.run_compare(clean, variant)
        self.assertEqual(result["cases"], {"1": "same_step_same_category", "2": "step_moved", "3": "category_changed",
                                           "4": "step_and_category_changed", "5": "same_step_same_category",
                                           "6": "clean_root_missed", "7": "missing_prediction"})
        self.assertEqual(result["paired_clean_correct"], 5)
        self.assertEqual(result["flipped_by_type"], {"step_moved": 1, "category_changed": 1,
                                                     "step_and_category_changed": 1})
        self.assertAlmostEqual(result["verdict_flip_rate"], 3 / 5)
        self.assertEqual(result["paired_clean_fully_correct"], 4)  # case 5 drops out
        self.assertAlmostEqual(result["verdict_flip_rate_fully_correct"], 3 / 4)
        self.assertEqual(result["predictions"]["3"]["variant"], [9, "INVENTION_OF_NEW_INFORMATION"])

    def test_no_flips_and_no_pairs(self):
        self.assertEqual(self.run_compare(self.ROOTS, self.ROOTS)["verdict_flip_rate"], 0)
        missed = {t: (s + 1, c) for t, (s, c) in self.ROOTS.items()}
        result = self.run_compare(missed, missed)
        self.assertEqual((result["paired_clean_correct"], result["verdict_flip_rate"]), (0, None))

    def test_one_decision_per_trajectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            pc.write(Path(tmp) / "r.json", {"detailed_results": [{"task_id": "1", "failures": [
                {"step_number": 1, "failure_case": 1}, {"step_number": 2, "failure_case": 1}]}]})
            with self.assertRaisesRegex(ValueError, "one judge decision"):
                pc.predictions(Path(tmp) / "r.json")


if __name__ == "__main__":
    unittest.main()
