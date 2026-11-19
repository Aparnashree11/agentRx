"""Exercise layouts, generation, review and comparison on the frozen baselines."""
import json
import re
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agentrx.rewordings import step_decoy as decoy

DATA = decoy.ROOT / "data/benchmark_versions"
TAU = DATA / "tau_retail/baseline/v1.0.0/tau_dataset_failed.json"
TAU_GT = DATA / "tau_retail/baseline/v1.0.0/tau_ground_truth.json"
MAGENTIC = DATA / "magentic_one/baseline/v1.0.0/trajectories"
MAGENTIC_GT = DATA / "magentic_one/baseline/v1.0.0/magentic_one_ground_truth.json"

# Tau task 4 (root failure at step 15): a failed product lookup before steps 13-14
# and a replay of the catalog lookup (steps 11-12) after the variant details.
HERRING = dict(kind="red_herring", source_start=13, source_end=14, find="9523456873",
               replace_with="9523456837", response="Error: product not found")
NOISE = dict(kind="noise", source_start=11, source_end=12, insert_after_step=14)
PROPOSAL = dict(decision="INSERT", insertions=[HERRING, NOISE],
                rationale="A product error right before the count and extra catalog output.",
                distinguishing_evidence="Step 14 lists the variants the assistant then miscounts.")


def fake_claude(proposal, model="claude-haiku-5-5"):
    """Stand in for the Claude Code CLI: answer --version and each -p generation call."""
    def run(cmd, **kwargs):
        if cmd[1:] == ["--version"]:
            return SimpleNamespace(returncode=0, stdout="9.9.9 (Claude Code)\n", stderr="")
        envelope = dict(type="result", is_error=False, num_turns=2, session_id="s", duration_ms=1,
                        total_cost_usd=0.01, structured_output=proposal, result=json.dumps(proposal),
                        modelUsage={model: {"outputTokens": 1}})
        return SimpleNamespace(returncode=0, stdout=json.dumps(envelope), stderr="")
    return run


def generate_args(work, **overrides):
    return Namespace(**{**dict(domain="tau", trajectories=TAU, ground_truth=TAU_GT, policy=None, work=work,
                               ids=["4"], model="haiku", effort="medium", claude_bin="claude", timeout=10),
                        **overrides})


def tau_case(tid="4"):
    _, cases, labels, _ = decoy.load_dataset(TAU, TAU_GT)
    return cases[tid], labels[tid], decoy.transitions(cases)


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
                    source, trajectories = decoy.parse_source(path)
                    self.assertEqual([t["id"] for t in trajectories], ids)
                    source["trajectories"] = trajectories
                    again = Path(tmp) / ("again_" + name)
                    again.write_text(decoy.dump_source(source, {t["id"]: t["events"] for t in trajectories}))
                    self.assertEqual(decoy.parse_source(again)[0]["data"], source["data"])
            bad = Path(tmp) / "notes.json"
            bad.write_text("# Conversation\n\nuser: hi")
            with self.assertRaises(ValueError):
                decoy.parse_source(bad)

    def test_wrapper_release_keeps_only_accepted_trajectories(self):
        rows = json.loads(TAU.read_text())[:2]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "w.json"
            path.write_text(json.dumps(rows))
            source, trajectories = decoy.parse_source(path)
            source["trajectories"] = trajectories
            kept = json.loads(decoy.dump_source(source, {"3": ["edited"]}))
            self.assertEqual([r["task_id"] for r in kept], [3])
            self.assertEqual(kept[0]["traj"], ["edited"])
            self.assertEqual(set(kept[0]), set(rows[1]))


class TauDecoyTest(unittest.TestCase):
    def test_reviewed_decoys_map_annotations_and_predictions(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            with patch.object(decoy.subprocess, "run", side_effect=fake_claude(PROPOSAL)) as cli:
                decoy.propose(generate_args(work))
                generations = [c for c in cli.call_args_list if "-p" in c.args[0]]
                self.assertEqual(len(generations), 1)
                cmd = generations[0].args[0]
                self.assertEqual(cmd[cmd.index("--model") + 1], "claude-haiku-5-5")
                self.assertEqual(cmd[cmd.index("--effort") + 1], "medium")
                self.assertEqual(cmd[cmd.index("--tools") + 1], "")
                message = generations[0].kwargs["input"]
                self.assertNotRegex(message, r"<<[A-Z_]+>>")
                self.assertIn("**Domain:** tau", message)
                self.assertIn("assistant+calls -> tool", message)
                self.assertIn('"content": "Error: user not found"', message)
                self.assertIn("You are Yusuf Rossi in 19122", message)
            self.assertEqual(decoy.read(work / "4/generation.json")["claude_version"], "9.9.9 (Claude Code)")
            decoy.write(work / "reviews.json", {"4": dict(decision="accept", reviewer="fixture",
                                                          reason="Synthetic review for regression test")})
            args = Namespace(work=work, reviews=work / "reviews.json", version="v0.1.0", out=None)
            with patch.object(decoy, "VERSIONS", Path(tmp)):
                decoy.release(args)
                with self.assertRaises(ValueError):
                    decoy.release(args)
            target = Path(tmp) / "tau_retail/step_decoy/haiku/v0.1.0"
            original_row = next(r for r in json.loads(TAU.read_text()) if r["task_id"] == 4)
            released, = decoy.read(target / "trajectories/tau_dataset_failed.json")
            self.assertEqual(set(released), set(original_row))  # same wrapper layout
            self.assertEqual(released["info"], original_row["info"])
            original, events = original_row["traj"], released["traj"]
            # 1-12 original, 13-14 failed product lookup, 15-16 original 13-14,
            # 17-18 replayed catalog lookup, 19+ original 15+.
            strip = lambda e: {k: v for k, v in e.items() if k != "index"}
            self.assertEqual([strip(e) for e in events[:12] + events[14:16] + events[18:]],
                             [strip(e) for e in original])
            self.assertEqual([e["index"] for e in events], list(range(1, len(events) + 1)))
            bad_call, error, retry = events[12], events[13], events[14]
            self.assertEqual(bad_call["tool_calls"][0]["function"]["arguments"], '{"product_id":"9523456837"}')
            self.assertEqual(retry["tool_calls"][0]["function"]["arguments"], '{"product_id":"9523456873"}')
            self.assertEqual(error["content"], "Error: product not found")
            self.assertEqual(events[16]["tool_calls"][0]["function"], original[10]["tool_calls"][0]["function"])
            self.assertEqual(events[17]["content"], original[11]["content"])
            for call, reply in [(bad_call, error), (events[16], events[17])]:
                call_id = call["tool_calls"][0]["id"]
                self.assertEqual(call_id, reply["tool_call_id"])
                # Same shape as the originals, e.g. call_AcUCHKveO3KNkZuU6Do7Ikbm
                self.assertRegex(call_id, r"^call_[A-Za-z0-9]{24}$")
                self.assertNotIn(call_id, json.dumps(original))
            root = decoy.root_failure(decoy.read(target / "ground_truth.json")[0])
            self.assertEqual((root["step_number"], root["original_step_number"]), (19, 15))
            manifest = decoy.read(target / "manifest.json")
            self.assertEqual((manifest["domain"], manifest["generator"]["model_id"]), ("tau", "claude-haiku-5-5"))
            self.assertIn("trajectories/tau_dataset_failed.json", manifest["artifact_sha256"])
            audit_path = target / "audit.json"
            record = decoy.read(audit_path)["4"]
            self.assertEqual([(i["kind"], i["steps"]) for i in record["insertions"]],
                             [("red_herring", [13, 14]), ("noise", [17, 18])])
            for new_step, expected, kind in [(13, "inserted_decoy", "red_herring"), (17, "inserted_decoy", "noise"),
                                             (19, "same_original_event", None), (15, "other_original_event", None)]:
                for name, pos in [("clean", 15), ("variant", new_step)]:
                    decoy.write(work / name, {"detailed_results": [
                        {"task_id": "4", "failures": [{"step_number": pos}]}]})
                output = StringIO()
                with redirect_stdout(output):
                    decoy.compare(Namespace(audit=audit_path, clean=work/"clean", variant=work/"variant"))
                result = json.loads(output.getvalue())
                self.assertEqual(result["counts"], {expected: 1})
                self.assertEqual(result["attracted_by_kind"], {kind: 1} if kind else {})

    def test_label_without_root_cause_skips_the_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            label = {k: v for k, v in tau_case()[1].items() if k != "root_cause"}
            decoy.write(Path(tmp) / "gt.json", [label])
            with patch.object(decoy.subprocess, "run") as cli:
                decoy.propose(generate_args(Path(tmp) / "work", ground_truth=Path(tmp) / "gt.json"))
                cli.assert_not_called()
            self.assertEqual(decoy.read(Path(tmp) / "work/4/proposal.json")["decision"], "NO_VALID_DECOY")

    def test_invalid_proposal_is_kept_for_review(self):
        bad = dict(PROPOSAL, insertions=[dict(HERRING, replace_with="yusuf_rossi_9620")])
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            with patch.object(decoy.subprocess, "run", side_effect=fake_claude(bad)):
                decoy.propose(generate_args(work))
            self.assertIn("appears in the trajectory", decoy.read(work / "4/invalid.json")["error"])
            self.assertFalse((work / "4/events.json").exists())

    def test_shared_insertion_point_puts_failed_attempt_last(self):
        case, label, allowed = tau_case()
        replay = dict(kind="noise", source_start=9, source_end=10, insert_after_step=12)
        events, mapped, mapping, inserted = decoy.materialize(
            case, label, dict(PROPOSAL, insertions=[HERRING, replay, NOISE]), allowed)
        self.assertEqual([(i["kind"], i["steps"]) for i in inserted],
                         [("noise", [13, 14]), ("red_herring", [15, 16]), ("noise", [19, 20])])
        self.assertEqual(events[16]["tool_calls"][0]["function"]["arguments"], '{"product_id":"9523456873"}')
        self.assertEqual((mapping["13"], mapping["15"]), (17, 21))
        self.assertEqual(decoy.root_failure(mapped)["step_number"], 21)

    def test_rejects_unsafe_decoys(self):
        case, label, allowed = tau_case()
        bad = {
            "slip already in trace": [dict(HERRING, replace_with="yusuf_rossi_9620")],
            "find not in request": [dict(HERRING, find="no such text")],
            "unchanged value": [dict(HERRING, replace_with=HERRING["find"])],
            "copies the root step": [dict(HERRING, source_start=14, source_end=15)],
            "single-event red herring": [dict(HERRING, source_end=13)],
            "noise at the root": [dict(NOISE, insert_after_step=15)],
            "noise before its source": [dict(NOISE, insert_after_step=11)],
            "breaks call/result pairing": [dict(NOISE, insert_after_step=13)],
            "span too long": [dict(NOISE, source_start=9, source_end=12)],
            "same replay twice": [NOISE, NOISE],
            "two red herrings on one exchange": [HERRING, dict(HERRING, replace_with="9523456738")],
            "empty": [],
        }
        for name, insertions in bad.items():
            with self.subTest(name), self.assertRaises(ValueError):
                decoy.materialize(case, label, dict(PROPOSAL, insertions=insertions), allowed)
        replays = [dict(kind="noise", source_start=s, source_end=s + 1, insert_after_step=a)
                   for s, a in [(9, 12), (9, 14), (11, 14)]]
        herrings = [dict(HERRING, source_start=7, source_end=8, find="19122", replace_with="19221"),
                    dict(HERRING, source_start=9, source_end=10, find="yusuf_rossi_9620",
                         replace_with="yusuf_rossi_9602", response="Error: user not found"), HERRING]
        *_, inserted = decoy.materialize(case, label, dict(PROPOSAL, insertions=replays + herrings), allowed)
        self.assertEqual(len(inserted), 6)
        for extra in [NOISE, dict(HERRING, source_start=11, source_end=12, find="{}", replace_with="{ }")]:
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, "at most 3"):
                decoy.materialize(case, label, dict(PROPOSAL, insertions=replays + herrings + [extra]), allowed)


class MagenticDecoyTest(unittest.TestCase):
    """The same code on a multi-agent domain with a folder of bare event lists and no tool calls."""

    def test_folder_of_event_lists(self):
        sources, cases, labels, _ = decoy.load_dataset(MAGENTIC, MAGENTIC_GT)
        self.assertEqual((len(cases), len([t for t in cases if t in labels])), (58, 44))
        allowed = decoy.transitions(cases)
        tid = next(t for t in cases if t in labels and decoy.root_failure(labels[t])["step_number"] > 6)
        case, label = cases[tid], labels[tid]
        root = decoy.root_failure(label)["step_number"]

        def first_valid(candidates):
            for item in candidates:
                try:
                    return item, decoy.materialize(case, label, dict(PROPOSAL, insertions=[item]), allowed)
                except ValueError:
                    continue
            self.fail("no valid decoy found")

        noise, (events, mapped, _, inserted) = first_valid(
            dict(kind="noise", source_start=s, source_end=s, insert_after_step=a)
            for a in range(2, root) for s in range(2, a + 1))
        self.assertEqual(decoy.root_failure(mapped)["step_number"], root + 1)
        self.assertEqual(events[inserted[0]["steps"][0] - 1], case["events"][noise["source_start"] - 1])
        herring, (events, mapped, _, inserted) = first_valid(
            dict(kind="red_herring", source_start=s, source_end=s + 1, find=case["events"][s - 1]["content"][:12],
                 replace_with="qq-unique-slip", response="Error 404")
            for s in range(2, root - 1))
        failed = events[inserted[0]["steps"][0] - 1: inserted[0]["steps"][-1]]
        self.assertIn("qq-unique-slip", failed[0]["content"])
        self.assertEqual(failed[-1], {**case["events"][herring["source_end"] - 1], "content": "Error 404"})
        self.assertEqual(decoy.root_failure(mapped)["step_number"], root + 2)
        source = sources[case["source"]]
        self.assertEqual(source["layout"], "events")
        self.assertEqual(json.loads(decoy.dump_source(source, {tid: events})), events)
