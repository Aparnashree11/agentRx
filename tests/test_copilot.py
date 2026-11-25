"""The shared GitHub Copilot CLI call used by the three rewording generators."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agentrx.rewordings import copilot

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["decision"], "properties": {
    "decision": {"type": "string", "enum": ["EDIT", "NO_VALID_EDIT"]},
    "edits": {"type": "array", "items": {"type": "object", "required": ["step"],
                                         "properties": {"step": {"type": "integer"}}}}}}


def stream(*events, code=0):
    return SimpleNamespace(returncode=code, stdout="\n".join(json.dumps(e) for e in events), stderr="")


def session(model="claude-opus-5.5", effort="medium", content='{"decision": "NO_VALID_EDIT"}', extra=()):
    return stream(dict(type="session.start", data=dict(sessionId="s", selectedModel=model, reasoningEffort=effort)),
                  *extra,
                  dict(type="assistant.message", data=dict(content=content)),
                  dict(type="result", exitCode=0, usage=dict(premiumRequests=2, sessionDurationMs=5)))


def ask(result, model="claude-opus-5.5"):
    with patch.object(copilot.subprocess, "run", return_value=result) as run:
        answer = copilot.ask("copilot", model, "medium", "SYSTEM", SCHEMA, "MESSAGE", 10)
    return answer, run.call_args


class SettingsTest(unittest.TestCase):
    def test_each_rewording_has_its_own_model_and_medium_effort(self):
        clean = {k: v for k, v in os.environ.items() if "_COPILOT_" not in k}
        with patch.dict(os.environ, clean, clear=True):
            self.assertEqual({r: copilot.model_for(r) for r in copilot.MODEL_DEFAULTS}, {
                "step_decomposition": "claude-haiku-5.5", "step_decoy": "claude-sonnet-5.5",
                "presentation_change": "claude-opus-5.5"})
            self.assertEqual({copilot.effort_for(r) for r in copilot.MODEL_DEFAULTS}, {"medium"})

    def test_environment_overrides_one_rewording_only(self):
        with patch.dict(os.environ, {"STEP_DECOY_COPILOT_MODEL": "gpt-6.1-sol",
                                     "STEP_DECOY_COPILOT_REASONING_EFFORT": "high",
                                     "STEP_DECOMPOSITION_COPILOT_MODEL": "",
                                     "STEP_DECOMPOSITION_COPILOT_REASONING_EFFORT": ""}):
            self.assertEqual((copilot.model_for("step_decoy"), copilot.effort_for("step_decoy")),
                             ("gpt-6.1-sol", "high"))
            self.assertEqual((copilot.model_for("step_decomposition"), copilot.effort_for("step_decomposition")),
                             ("claude-haiku-5.5", "medium"))
        with patch.dict(os.environ, {"PRESENTATION_CHANGE_COPILOT_REASONING_EFFORT": "huge"}):
            with self.assertRaisesRegex(ValueError, "PRESENTATION_CHANGE_COPILOT_REASONING_EFFORT"):
                copilot.effort_for("presentation_change")

    def test_command_is_isolated_and_disables_user_mcp_servers(self):
        with tempfile.TemporaryDirectory() as home:
            Path(home, "mcp-config.json").write_text(json.dumps({"mcpServers": {"Sanity": {}, "Other": {}}}))
            with patch.dict(os.environ, {"COPILOT_HOME": home}):
                cmd = copilot.command("copilot", "claude-haiku-5.5", "medium")
        self.assertEqual(cmd[cmd.index("--model") + 1], "claude-haiku-5.5")
        self.assertEqual(cmd[cmd.index("--reasoning-effort") + 1], "medium")
        self.assertEqual(cmd[cmd.index("--output-format") + 1], "json")
        for flag in ("--no-ask-user", "--no-custom-instructions", "--disable-builtin-mcps"):
            self.assertIn(flag, cmd)
        self.assertEqual([cmd[i + 1] for i, a in enumerate(cmd) if a == "--disable-mcp-server"], ["Other", "Sanity"])
        self.assertEqual(cmd[-1], "--available-tools")
        self.assertNotIn("--allow-all", cmd)


class AskTest(unittest.TestCase):
    def test_answer_is_parsed_validated_and_recorded(self):
        (answer, meta), call = ask(session(content='Here it is:\n```json\n{"decision": "EDIT", "edits": [{"step": 3}]}\n```'))
        self.assertEqual(answer, {"decision": "EDIT", "edits": [{"step": 3}]})
        self.assertEqual((meta["model"], meta["effort"], meta["premium_requests"], meta["session_id"]),
                         ("claude-opus-5.5", "medium", 2, "s"))
        prompt = call.kwargs["input"]
        self.assertTrue(prompt.startswith("SYSTEM\n\nMESSAGE"))
        self.assertEqual(json.loads(prompt.split(copilot.ANSWER_FORMAT)[1]), SCHEMA)

    def test_refusals(self):
        cases = {
            "Copilot CLI failed: .*not available": stream(
                dict(type="session.start", data=dict(selectedModel="claude-opus-5.5")),
                dict(type="session.error", data=dict(message='Model "claude-opus-5.5" is not available.')),
                dict(type="result", exitCode=1), code=1),
            "Requested claude-opus-5.5 but the session used": session(model="claude-haiku-5.5"),
            "used \\['claude-haiku-5.5', 'claude-opus-5.5'\\]": session(
                extra=[dict(type="assistant.usage", data=dict(model="claude-haiku-5.5"))]),
            "Requested effort medium": session(effort="high"),
            "no assistant message": stream(dict(type="session.start", data=dict(selectedModel="claude-opus-5.5")),
                                           dict(type="result", exitCode=0)),
            "not JSON": session(content="I cannot help with that."),
            "answer.decision should be one of": session(content='{"decision": "MAYBE"}'),
            "answer has unexpected fields": session(content='{"decision": "EDIT", "extra": 1}'),
            "answer.edits\\[0\\].step should be integer": session(content='{"decision": "EDIT", "edits": [{"step": "3"}]}'),
            "no JSON events": SimpleNamespace(returncode=1, stdout="", stderr="boom"),
        }
        for pattern, result in cases.items():
            with self.subTest(pattern), self.assertRaisesRegex(ValueError, pattern):
                ask(result)


if __name__ == "__main__":
    unittest.main()
