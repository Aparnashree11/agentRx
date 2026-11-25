"""One isolated GitHub Copilot CLI turn for the rewording generators.

The generators call the Copilot CLI the same way AgentRx's judge does
(agentrx/llm_clients/copilot_cli.py): the same binary lookup
(AGENT_VERIFY_COPILOT_BIN, then the usual npm locations, then PATH), the same .env,
and the prompt piped on stdin. On top of that, each call is isolated so that the
model sees only the prompt:
  --available-tools (empty)       no tools: the model can read no files and run nothing;
  --disable-builtin-mcps and --disable-mcp-server <name> for each user MCP server;
  --no-custom-instructions        no AGENTS.md or other instruction files;
  --no-ask-user, --stream off, --no-auto-update;
  an empty temporary working directory, so the repository is not visible.

Each rewording has its own finalized model and reasoning effort (MODEL_DEFAULTS),
which the environment can change like AGENT_VERIFY_COPILOT_MODEL does for the judge.
There is no command-line override. The model and effort used are locked in the work
directory's config.json and recorded in the release manifest.

The Copilot CLI has no JSON-schema option, so the schema is appended to the prompt,
the answer is extracted with AgentRx's own JSON extractor, and check_schema()
validates it here. The run fails unless the session used the requested model.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from agentrx.llm_clients.copilot_cli import _Completions, _find_copilot_bin

load_dotenv()  # the same .env AgentRx reads

PROVIDER = "copilot-cli"
EFFORTS = ("low", "medium", "high", "xhigh", "max")
DEFAULT_EFFORT = "medium"
# rewording -> (environment variable, default Copilot model ID). Effort is read from
# the same prefix with _COPILOT_REASONING_EFFORT, default DEFAULT_EFFORT.
MODEL_DEFAULTS = {
    "step_decomposition": ("STEP_DECOMPOSITION_COPILOT_MODEL", "claude-haiku-5.5"),
    "step_decoy": ("STEP_DECOY_COPILOT_MODEL", "claude-sonnet-5.5"),
    "presentation_change": ("PRESENTATION_CHANGE_COPILOT_MODEL", "claude-opus-5.5"),
}
TIMEOUT = int(os.getenv("AGENT_VERIFY_COPILOT_TIMEOUT", "600"))
ANSWER_FORMAT = ("## Answer format\n"
                 "Respond with ONLY one JSON object that matches this JSON Schema. "
                 "No markdown fences, no explanation, no other text.\n")


def model_for(rewording):
    """The Copilot model ID this rewording uses: its environment variable, else the default."""
    var, default = MODEL_DEFAULTS[rewording]
    return (os.getenv(var) or "").strip() or default


def effort_for(rewording):
    """The reasoning effort this rewording uses: <PREFIX>_COPILOT_REASONING_EFFORT, else medium."""
    var = MODEL_DEFAULTS[rewording][0].replace("_COPILOT_MODEL", "_COPILOT_REASONING_EFFORT")
    effort = (os.getenv(var) or "").strip() or DEFAULT_EFFORT
    if effort not in EFFORTS:
        raise ValueError(f"{var}={effort!r}; expected one of {', '.join(EFFORTS)}")
    return effort


def add_model_arguments(parser, rewording):
    """--copilot-bin and --timeout for a generate subcommand. The model and effort come
    only from the environment (model_for, effort_for); the help text names them."""
    var, default = MODEL_DEFAULTS[rewording]
    parser.epilog = (f"Model: ${var} (default {default}); reasoning effort: "
                     f"${var.replace('_COPILOT_MODEL', '_COPILOT_REASONING_EFFORT')} (default {DEFAULT_EFFORT}).")
    parser.add_argument("--copilot-bin",
                        help="Copilot CLI executable (default: $AGENT_VERIFY_COPILOT_BIN, as for AgentRx)")
    parser.add_argument("--timeout", type=int, default=TIMEOUT,
                        help="Seconds per call (default: $AGENT_VERIFY_COPILOT_TIMEOUT or 600)")


def binary(path=None):
    """The Copilot CLI to run, resolved exactly as AgentRx resolves it."""
    if path:
        return path
    try:
        return _find_copilot_bin()
    except RuntimeError as exc:
        raise ValueError(str(exc))


def version(path):
    try:
        result = subprocess.run([path, "--version"], capture_output=True, text=True,
                                stdin=subprocess.DEVNULL, timeout=60)
    except FileNotFoundError:
        raise ValueError(f"Copilot CLI not found at {path!r}. Pass --copilot-bin or set AGENT_VERIFY_COPILOT_BIN.")
    if result.returncode:
        raise ValueError(f"{path} --version failed: {result.stderr.strip()[:500]}")
    return (result.stdout.strip().splitlines() or [""])[0]


def user_mcp_servers():
    """Names of the MCP servers in the user's Copilot config, so each can be disabled."""
    home = Path(os.getenv("COPILOT_HOME") or Path.home() / ".copilot")
    try:
        config = json.loads((home / "mcp-config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    servers = config.get("mcpServers", {}) if isinstance(config, dict) else {}
    return sorted(servers) if isinstance(servers, dict) else []


def command(path, model, effort):
    cmd = [path, "--no-ask-user", "--no-custom-instructions", "--disable-builtin-mcps",
           "--no-auto-update", "--stream", "off", "--output-format", "json",
           "--model", model, "--reasoning-effort", effort]
    for name in user_mcp_servers():
        cmd += ["--disable-mcp-server", name]
    return cmd + ["--available-tools"]  # last, so its (empty) tool list takes no other argument


def check_schema(value, schema, where="answer"):
    """Validate the subset of JSON Schema the generators use (type, enum, required,
    properties, additionalProperties false, items). Raises ValueError."""
    kinds = {"object": dict, "array": list, "string": str}
    kind = schema.get("type")
    if kind == "integer":
        ok = type(value) is int
    else:
        ok = isinstance(value, kinds[kind]) if kind in kinds else True
    if not ok:
        raise ValueError(f"{where} should be {kind}, got {type(value).__name__}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{where} should be one of {schema['enum']}, got {value!r}")
    if kind == "object":
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                raise ValueError(f"{where} is missing {key!r}")
        if schema.get("additionalProperties") is False and set(value) - set(props):
            raise ValueError(f"{where} has unexpected fields {sorted(set(value) - set(props))}")
        for key, sub in props.items():
            if key in value:
                check_schema(value[key], sub, f"{where}.{key}")
    elif kind == "array" and "items" in schema:
        for i, item in enumerate(value):
            check_schema(item, schema["items"], f"{where}[{i}]")


def events(stdout):
    found = []
    for line in stdout.splitlines():
        line = line.strip()
        if line:
            try:
                found.append(json.loads(line))
            except ValueError:
                continue
    return found


def ask(path, model, effort, system, schema, message, timeout):
    """Run one isolated Copilot turn; return the validated JSON answer and run metadata."""
    prompt = f"{system}\n\n{message}\n\n{ANSWER_FORMAT}{json.dumps(schema, indent=2)}\n"
    with tempfile.TemporaryDirectory() as cwd:
        result = subprocess.run(command(path, model, effort), cwd=cwd, input=prompt, capture_output=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
    stream = events(result.stdout)
    if not stream:
        raise ValueError(f"Copilot CLI returned no JSON events: {(result.stderr or result.stdout).strip()[:500]}")
    start = next((e.get("data") or {} for e in stream if e.get("type") == "session.start"), {})
    final = next((e for e in reversed(stream) if e.get("type") == "result"), {})
    errors = [str((e.get("data") or {}).get("message")) for e in stream if e.get("type") == "session.error"]
    if result.returncode or final.get("exitCode") or errors:
        raise ValueError(f"Copilot CLI failed: {'; '.join(errors) or (result.stderr or '').strip()[:500]}")
    # The model the session ran, and any model named on later events, must be the requested one.
    used = {start.get("selectedModel")} | {(e.get("data") or {}).get("model") for e in stream
                                           if isinstance((e.get("data") or {}).get("model"), str)}
    used.discard(None)
    if used != {model}:
        raise ValueError(f"Requested {model} but the session used {sorted(used) or 'an unreported model'}")
    if start.get("reasoningEffort") not in (None, effort):
        raise ValueError(f"Requested effort {effort} but the session used {start.get('reasoningEffort')}")
    answer = next(((e.get("data") or {}).get("content") for e in reversed(stream)
                   if e.get("type") == "assistant.message"
                   and isinstance((e.get("data") or {}).get("content"), str)
                   and (e.get("data") or {}).get("content").strip()), None)
    if answer is None:
        raise ValueError("Copilot CLI produced no assistant message (events: "
                         f"{sorted({str(e.get('type')) for e in stream})})")
    try:
        proposal = json.loads(_Completions._extract_json(answer))
    except ValueError:
        raise ValueError(f"Answer is not JSON: {answer.strip()[:500]}")
    check_schema(proposal, schema)
    usage = final.get("usage") or {}
    meta = dict(session_id=start.get("sessionId") or final.get("sessionId"), model=model, effort=effort,
                premium_requests=usage.get("premiumRequests"), duration_ms=usage.get("sessionDurationMs"),
                api_duration_ms=usage.get("totalApiDurationMs"))
    return proposal, meta
