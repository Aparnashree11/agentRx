"""Exercise layouts, generation, review and comparison on the frozen baselines."""
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agentrx.rewordings import step_decomposition as decomp

DATA = decomp.ROOT / "data/benchmark_versions"
TAU = DATA / "tau_retail/baseline/v1.0.0/tau_dataset_failed.json"
TAU_GT = DATA / "tau_retail/baseline/v1.0.0/tau_ground_truth.json"
MAGENTIC = DATA / "magentic_one/baseline/v1.0.0/trajectories"
MAGENTIC_GT = DATA / "magentic_one/baseline/v1.0.0/magentic_one_ground_truth.json"

# Tau task 4: the assistant text at step 15 miscounts the available T-shirts. Split
# it into three same-actor messages, the last of which still states the wrong count.
PROPOSAL = dict(
    decision="DECOMPOSE",
    substeps=[
        {"content": "Let me go through the T-shirt listing I just pulled up."},
        {"content": "I am looking at the available variants now."},
        {"content": "Currently, there are 11 available T-shirt options in our online store."},
    ],
    error_substeps=[3],
    rationale="A lead-in, a look at the listing, then the same wrong count reads naturally.",
    distinguishing_evidence="The third smaller step still says 11, the miscount from the tool output.")


MODEL = "claude-haiku-5.5"


def setUpModule():
    """Pin this rewording's model and effort, so a local .env cannot change the tests."""
    global _env
    _env = patch.dict(os.environ, {"STEP_DECOMPOSITION_COPILOT_MODEL": MODEL, "STEP_DECOMPOSITION_COPILOT_REASONING_EFFORT": "medium"})
    _env.start()


def tearDownModule():
    _env.stop()



def fake_copilot(proposal, model=MODEL, effort="medium"):
    """Stand in for the GitHub Copilot CLI: answer --version and each generation call
    with the JSON-lines events copilot.ask() reads."""
    def run(cmd, **kwargs):
        if cmd[1:] == ["--version"]:
            return SimpleNamespace(returncode=0, stdout="GitHub Copilot CLI 9.9.9.\n", stderr="")
        events = [dict(type="session.start", data=dict(sessionId="s", selectedModel=model, reasoningEffort=effort)),
                  dict(type="assistant.message", data=dict(content=json.dumps(proposal))),
                  dict(type="result", sessionId="s", exitCode=0,
                       usage=dict(premiumRequests=1, sessionDurationMs=1, totalApiDurationMs=1))]
        return SimpleNamespace(returncode=0, stdout="\n".join(map(json.dumps, events)), stderr="")
    return run


def generate_args(work, **overrides):
    return Namespace(**{**dict(domain="tau", trajectories=TAU, ground_truth=TAU_GT, policy=None, work=work,
                               ids=["4"], copilot_bin="copilot", timeout=10),
                        **overrides})


def tau_case(tid="4"):
    _, cases, labels, _ = decomp.load_dataset(TAU, TAU_GT)
    return cases[tid], labels[tid], decomp.transitions(cases)


class LayoutTest(unittest.TestCase):
    def test_every_agentrx_layout_round_trips(self):
        rows = json.loads(TAU.read_text())[:2]
        layouts = {
            "object.json": (json.dumps(rows[0]), [str(rows[0]["task_id"])]),
            "events.json": (json.dumps(rows[0]["traj"]), ["events"]),
            "wrappers.json": (json.dumps(rows), [str(r["task_id"]) for r in rows]),
            "wrappers.jsonl": ("\n".join(json.dumps(r) for r in rows), [str(r["task_id"]) for r in rows]),
            "events.jsonl": ("\n".join(json.dumps(e) for e in rows[0]["traj"]), ["events"]),
        }
        with tempfile.TemporaryDirectory() as tmp:
            for name, (text, ids) in layouts.items():
                with self.subTest(layout=name):
                    path = Path(tmp) / name
                    path.write_text(text)
                    source, trajectories = decomp.parse_source(path)
                    self.assertEqual([t["id"] for t in trajectories], ids)
                    source["trajectories"] = trajectories
                    again = Path(tmp) / ("again_" + name)
                    again.write_text(decomp.dump_source(source, {t["id"]: t["events"] for t in trajectories}))
                    self.assertEqual(decomp.parse_source(again)[0]["data"], source["data"])
            bad = Path(tmp) / "notes.json"
            bad.write_text("# Conversation\n\nuser: hi")
            with self.assertRaises(ValueError):
                decomp.parse_source(bad)


class TauDecompositionTest(unittest.TestCase):
    def test_reviewed_decomposition_maps_annotations_and_predictions(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            with patch.object(decomp.subprocess, "run", side_effect=fake_copilot(PROPOSAL)) as cli:
                decomp.propose(generate_args(work))
                generations = [c for c in cli.call_args_list if "--model" in c.args[0]]
                self.assertEqual(len(generations), 1)
                cmd = generations[0].args[0]
                self.assertEqual(cmd[cmd.index("--model") + 1], MODEL)
                self.assertEqual(cmd[cmd.index("--reasoning-effort") + 1], "medium")
                self.assertEqual(cmd[-1], "--available-tools")  # an empty tool list: no tools
                message = generations[0].kwargs["input"]
                self.assertNotRegex(message, r"<<[A-Z_]+>>")
                self.assertIn("**Domain:** tau", message)
                self.assertIn("The step to decompose", message)
                self.assertIn("You are Yusuf Rossi in 19122", message)
            self.assertEqual(decomp.read(work / "4/generation.json")["copilot_version"], "GitHub Copilot CLI 9.9.9.")
            decomp.write(work / "reviews.json", {"4": dict(decision="accept", reviewer="fixture",
                                                           reason="Synthetic review for regression test")})
            args = Namespace(work=work, reviews=work / "reviews.json", version="v0.1.0", out=None)
            with patch.object(decomp, "VERSIONS", Path(tmp)):
                decomp.release(args)
                with self.assertRaises(ValueError):  # a release cannot be overwritten
                    decomp.release(args)
            target = Path(tmp) / "tau_retail/step_decomposition/v0.1.0"
            original_row = next(r for r in json.loads(TAU.read_text()) if r["task_id"] == 4)
            released, = decomp.read(target / "trajectories/tau_dataset_failed.json")
            self.assertEqual(set(released), set(original_row))  # same wrapper layout
            original, events = original_row["traj"], released["traj"]
            # Steps 1-14 and 16+ are unchanged; step 15 becomes three smaller steps 15-17.
            strip = lambda e: {k: v for k, v in e.items() if k != "index"}
            self.assertEqual([strip(e) for e in events[:14] + events[17:]],
                             [strip(e) for e in original[:14] + original[15:]])
            self.assertEqual([e["index"] for e in events], list(range(1, len(events) + 1)))
            self.assertEqual(decomp.role(events[14]), decomp.role(original[14]))  # same actor
            self.assertIn("11 available T-shirt options", events[16]["content"])  # mistake preserved
            root = decomp.root_failure(decomp.read(target / "ground_truth.json")[0])
            self.assertEqual((root["step_number"], root["original_step_number"]), (17, 15))
            manifest = decomp.read(target / "manifest.json")
            self.assertEqual((manifest["domain"], manifest["variant"]), ("tau", "step_decomposition"))
            self.assertEqual((manifest["generator"]["model"], manifest["generator"]["provider"]), (MODEL, "copilot-cli"))
            self.assertIn("trajectories/tau_dataset_failed.json", manifest["artifact_sha256"])
            record = decomp.read(target / "audit.json")["4"]
            self.assertEqual((record["decomposed_steps"], record["error_steps"]), ([15, 16, 17], [17]))
            for variant_step, expected in [(17, "found_error_substep"), (16, "drifted_within_decomposition"),
                                           (1, "other_original_event")]:
                for name, pos in [("clean", 15), ("variant", variant_step)]:
                    decomp.write(work / name, {"detailed_results": [
                        {"task_id": "4", "failures": [{"step_number": pos}]}]})
                output = StringIO()
                with redirect_stdout(output):
                    decomp.compare(Namespace(audit=target / "audit.json", clean=work/"clean", variant=work/"variant"))
                self.assertEqual(json.loads(output.getvalue())["counts"], {expected: 1})

    def test_label_without_root_cause_skips_the_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            label = {k: v for k, v in tau_case()[1].items() if k != "root_cause"}
            decomp.write(Path(tmp) / "gt.json", [label])
            with patch.object(decomp.subprocess, "run") as cli:
                decomp.propose(generate_args(Path(tmp) / "work", ground_truth=Path(tmp) / "gt.json"))
                cli.assert_not_called()
            self.assertEqual(decomp.read(Path(tmp) / "work/4/proposal.json")["decision"], "NO_VALID_DECOMPOSITION")

    def test_invalid_proposal_is_kept_for_review(self):
        bad = dict(PROPOSAL, error_substeps=[9])  # out of range for three smaller steps
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            with patch.object(decomp.subprocess, "run", side_effect=fake_copilot(bad)):
                decomp.propose(generate_args(work))
            self.assertIn("1-based positions", decomp.read(work / "4/invalid.json")["error"])
            self.assertFalse((work / "4/events.json").exists())

    def test_tool_call_root_keeps_the_call_on_the_last_smaller_step(self):
        """A root step that makes a tool call must split with the call on the LAST
        smaller step: the tool result that followed the step has to stay right after
        the call, since an "assistant text -> tool result" sequence never occurs in Tau.
        (Task 20's root at step 21 is an assistant message that makes a get_product_details
        call; its result is the next event.)"""
        case, label, allowed = tau_case("20")
        root = decomp.root_failure(label)["step_number"]
        original = case["events"][root - 1]
        self.assertTrue(original.get("tool_calls") or original.get("function_call"))  # tool-call root
        following = decomp.signature(case["events"][root])  # the tool result after it
        proposal = dict(
            PROPOSAL,
            substeps=[{"content": "Here is how I'll handle the upgrades you asked for."},
                      {"content": "These two delivered orders can be exchanged for pricier versions."},
                      {"content": "Let me pull up the most expensive option for the first product."}],
            error_substeps=[2])
        events, mapped, mapping, record = decomp.materialize(case, label, proposal, allowed)
        block = events[root - 1:root - 1 + len(proposal["substeps"])]
        has_call = lambda e: bool(e.get("tool_calls") or e.get("function_call"))
        self.assertFalse(any(has_call(e) for e in block[:-1]))       # no call on the lead-in steps
        self.assertEqual(block[-1].get("tool_calls"), original.get("tool_calls"))  # call rides the last step
        self.assertTrue(has_call(block[-1]))
        self.assertEqual(decomp.signature(events[root - 1 + len(block)]), following)  # result still follows the call
        self.assertEqual(decomp.role(block[0]), decomp.role(original))  # same actor throughout

    def test_materialize_rejects_bad_decompositions(self):
        case, label, allowed = tau_case()
        bad = {
            "one smaller step": dict(PROPOSAL, substeps=PROPOSAL["substeps"][:1], error_substeps=[1]),
            "too many smaller steps": dict(PROPOSAL, substeps=PROPOSAL["substeps"] * 2, error_substeps=[1]),
            "empty content": dict(PROPOSAL, substeps=[{"content": " "}, {"content": "x"}], error_substeps=[2]),
            "no error marked": dict(PROPOSAL, error_substeps=[]),
            "error index out of range": dict(PROPOSAL, error_substeps=[4]),
            "missing rationale": {k: v for k, v in PROPOSAL.items() if k != "rationale"},
        }
        for name, proposal in bad.items():
            with self.subTest(name), self.assertRaises(ValueError):
                decomp.materialize(case, label, proposal, allowed)
        events, mapped, mapping, record = decomp.materialize(case, label, PROPOSAL, allowed)
        self.assertEqual((mapping["15"], mapping["16"]), (17, 18))
        self.assertEqual(decomp.root_failure(mapped)["step_number"], 17)


@unittest.skipUnless(MAGENTIC.exists(), "Magentic-One baseline is not on this branch")
class MagenticDecompositionTest(unittest.TestCase):
    """The same code on a multi-agent domain: a folder of bare event lists, no tool calls."""

    def test_folder_of_event_lists(self):
        sources, cases, labels, _ = decomp.load_dataset(MAGENTIC, MAGENTIC_GT)
        self.assertEqual((len(cases), len([t for t in cases if t in labels])), (58, 44))
        allowed = decomp.transitions(cases)
        tid = next(t for t in cases if t in labels and 6 < decomp.root_failure(labels[t])["step_number"] < len(cases[t]["events"]))
        case, label = cases[tid], labels[tid]
        root = decomp.root_failure(label)["step_number"]
        original = case["events"][root - 1]
        keep = (original.get("content") or "x")[:40]
        proposal = dict(PROPOSAL, substeps=[{"content": "First, " + keep}, {"content": keep}], error_substeps=[2])
        events, mapped, mapping, record = decomp.materialize(case, label, proposal, allowed)
        self.assertEqual(len(events), len(case["events"]) + 1)  # one step became two
        self.assertEqual(decomp.role(events[root - 1]), decomp.role(original))  # same actor
        self.assertEqual(decomp.root_failure(mapped)["step_number"], root + 1)
        source = sources[case["source"]]
        self.assertEqual(source["layout"], "events")
        self.assertEqual(json.loads(decomp.dump_source(source, {tid: events})), events)


if __name__ == "__main__":
    unittest.main()
