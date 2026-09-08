"""
Natural-language chat over the ServiceNow REST API.

Claude answers the user's question by running one read-only CLI, `snow.py`,
which issues GET requests to this project's REST API. That is the same shape as
running Claude Code against the repo by hand, driven from the backend so the
answer lands in the web UI.

No Model Context Protocol is involved. Claude gets exactly one tool - Bash - and
a permission callback that refuses every command except `python snow.py ...`,
so the tool surface is that one CLI and nothing else.

Reads stay read-only against ServiceNow. `snow.py export` does write locally -
an Excel, PDF or CSV file under exports/, served back by GET /exports/<file> so
the answer can carry a download link - but it still only reads the instance.

Credentials never reach the browser: ServiceNow credentials stay in the backend
process, and Claude authenticates through the Claude Code CLI already installed
on this machine (a subscription login, or ANTHROPIC_API_KEY when one is set).
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKError,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)

logger = logging.getLogger(__name__)

# Repository root: the folder that holds snow.py.
ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "snow.py"

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "medium"
MAX_TURNS = 12
MAX_MESSAGE_CHARS = 4000

# The only command shape the agent may run. Anything else is denied.
ALLOWED_COMMAND = re.compile(r"^\s*python\s+snow\.py(\s|$)")
# An optional leading "cd <root> &&" that the CLI prepends by itself.
CD_PREFIX = re.compile(r"^\s*cd\s+(?P<path>\"[^\"]+\"|'[^']+'|\S+)\s*&&\s*")

# Shell metacharacters that could chain a second command onto an allowed one.
# Checked only OUTSIDE quotes: ServiceNow encoded queries legitimately contain
# < and > (priority<=2, sys_created_on>=javascript:gs...), and those are always
# inside a quoted -q argument, where the shell never interprets them.
SHELL_CHAINING = re.compile(r"[;&|`$><\n]")
QUOTED = re.compile(r"\"[^\"]*\"|'[^']*'")


def outside_quotes(command: str) -> str:
    """The command with every quoted run blanked out, for metacharacter checks."""
    return QUOTED.sub(lambda m: " " * len(m.group(0)), command)

# NOTE: this is a str.format() template, so every literal brace must be doubled
# ({{ and }}). An un-doubled one in a code example raises KeyError at chat time,
# not at import - see the _options() call below.
SYSTEM_PROMPT = """You are a ServiceNow assistant embedded in a chat UI. You answer questions about \
the ServiceNow instance {instance} by reading live data.

You have exactly one tool: Bash, and the only command you may run is the CLI `snow.py`. \
Every other command is refused. Never try to call ServiceNow another way.

    python snow.py health
    python snow.py tools    [-q TEXT] [--all]
    python snow.py schema   <operation>
    python snow.py call     <operation> [-p name=value ...] [--format table|csv|json]
    python snow.py incident <NUMBER> [-f "field,field"]
    python snow.py count    <table> [-q "ENCODED_QUERY"]
    python snow.py stats    <table> <group_by_field> [-q "ENCODED_QUERY"]
    python snow.py query    <table> [-q "ENCODED_QUERY"] [-f "field,field"] [-l N] [--format table|csv|json]
    python snow.py fields   <table>
    python snow.py datasets [-q TEXT]
    python snow.py dataset  <name>
    python snow.py export   <table>  --to xlsx|pdf|csv [-q QUERY] [-f "field,field"] [-l N] [--title TEXT]
    python snow.py export   <name>   --dataset --to xlsx|pdf|csv     export a saved dataset
    python snow.py export   <table>  --group-by <field> --to pdf     export grouped counts
    python snow.py exports  [-q TEXT]                                list files already exported
{write_commands}
How to work:
- ALWAYS run `snow.py datasets` first. If a saved dataset answers the question and was captured recently, read it with `snow.py dataset <name>` rather than querying ServiceNow again.
- Re-query live when the user says now/today/currently/latest, or when the dataset is over an hour old. Tell the user which you used: "from a snapshot taken at 09:14" or "read live just now".
- Every read is cached to datasets/ automatically.
- Prefer a named operation (`snow.py tools -q incident` lists them) over a raw table query. \
Use `query <table>` only when no operation fits.
- Name fields with -f on table queries; a bare query returns every column.
- `count` is exact and instant (ServiceNow Aggregate API). Never page through records to count them.
- For "how many X by Y", use `stats <table> <field>` - one call returns the grouped counts. Do not fetch rows and tally them yourself.
- Use `schema <operation>` or `fields <table>` when unsure - discover, do not guess.
- Encoded queries use ^ for AND, ^OR for OR, LIKE, STARTSWITH, ISEMPTY, IN, ORDERBYDESC, and \
gs date functions such as javascript:gs.beginningOfLast30Days().

Files (PDF, Excel, CSV):
- You CAN produce real files. When the user asks for a PDF, an Excel/xlsx file, a spreadsheet, \
a CSV, a report, a download or "give me this as a file", run `snow.py export`. Never say you cannot make one.
- `--to xlsx` for Excel, `--to pdf` for PDF, `--to csv` for CSV. Give `--title` a readable title.
- Export the data the user actually asked about: pass the same -q and -f you would use for `query`. \
Raise -l when they want the full list (the default is 500) - an export is meant to be complete, \
not the 25 rows you showed in chat.
- If the answer you just gave came from a saved dataset, export that dataset by name with `--dataset` \
rather than re-querying.
- `export` prints a "Download:" URL. Always end your reply with that URL on its own line so the user \
can click it. Say the row count and the format in one short sentence, e.g. \
"Excel file with 248 users:" followed by the link.
- If the user wants both PDF and Excel, run export twice and give both links.

Answering:
- Answer only from what the commands returned. Never invent records, numbers or dates. \
If a lookup returns nothing, say so plainly.
- When the user asks for specific fields, give those fields and not a full record dump.
- Cite record numbers such as INC0015571.
{write_rule}

Formatting:
- Use whatever shape shows the answer most clearly: short paragraphs, "- " bullets, \
"**Bold**" for emphasis, "### " headings to separate sections of a longer answer.
- Use a markdown table when you are showing several fields of one record, or the same \
fields across several records. Keep tables narrow - about 2 to 5 columns - and put the \
field name in the first column when describing a single record:

    | Field | Value |
    | --- | --- |
    | Number | INC0015571 |
    | Priority | 2 - High |

- Put scripts, conditions and other code in a fenced block with its language, so it can be \
copied cleanly:

    ```javascript
    (function executeRule(current, previous) {{ current.state = 2; }})(current, previous);
    ```

- Before a create or update, show the exact values you are about to write as a table, then \
do it in the same reply. Afterwards show what was actually stored, as a table, with the \
record number.
- Be as long as the answer needs and no longer. A count is one line; a record you just \
created deserves its table.
- Today is {today}."""


def strip_claude_code_env() -> None:
    """
    Remove inherited Claude Code session variables.

    When this backend is itself launched from a Claude Code session, those
    variables would otherwise make the nested CLI try to rejoin the parent
    session instead of starting its own.
    """
    for name in list(os.environ):
        if name.startswith("CLAUDE_CODE_") or name in {"CLAUDECODE", "CLAUDE_SESSION_ID"}:
            os.environ.pop(name, None)


def _deny(reason: str) -> PermissionResultDeny:
    return PermissionResultDeny(message=reason)


def _strip_cd_prefix(command: str) -> str:
    """
    Remove a leading `cd <repo root> &&`, which the CLI adds on its own.

    Only the project root is accepted, so this cannot be used to reach another
    directory. Anything else is left intact and will fail the checks below.
    """
    match = CD_PREFIX.match(command)
    if not match:
        return command
    target = (match.group("path") or "").strip().strip('"').strip("'").rstrip("\\/")
    if os.path.normcase(os.path.abspath(target)) == os.path.normcase(str(ROOT)):
        return command[match.end():]
    return command


async def _guard(tool_name: str, input_data: Dict[str, Any], _context: Any):
    """Allow only `python snow.py ...`; refuse everything else."""
    if tool_name != "Bash":
        logger.warning("chat: denied tool %s", tool_name)
        return _deny(f"{tool_name} is not available; use the snow.py CLI.")

    command = _strip_cd_prefix(str(input_data.get("command", "")))
    if SHELL_CHAINING.search(outside_quotes(command)):
        logger.warning("chat: denied chained command %r", command)
        return _deny("Chained or redirected commands are not allowed. Run one snow.py command.")
    if not ALLOWED_COMMAND.match(command):
        logger.warning("chat: denied command %r", command)
        return _deny("Only 'python snow.py ...' may be run here.")
    return PermissionResultAllow()


class ChatAgent:
    """One agent run per chat message, yielding events for the HTTP layer."""

    def __init__(
        self,
        instance_url: str,
        model: Optional[str] = None,
        effort: str = DEFAULT_EFFORT,
        max_turns: int = MAX_TURNS,
        allow_write: bool = False,
    ):
        self.instance_url = instance_url
        # snow.py refuses its write commands unless this is passed through, so
        # the web chat is read-only unless the server was started with
        # --allow-write. Sharing the UI therefore cannot hand out write access
        # by accident.
        self.allow_write = allow_write
        self.model = model or os.getenv("CHAT_MODEL") or DEFAULT_MODEL
        self.effort = os.getenv("CHAT_EFFORT") or effort
        self.max_turns = max_turns

    # ----- status ---------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        cli = shutil.which("claude")
        reasons: List[str] = []
        if not cli:
            reasons.append("The Claude Code CLI is not installed or not on PATH.")
        if not CLI.exists():
            reasons.append(f"snow.py was not found at {CLI}.")

        api_key = bool(os.getenv("ANTHROPIC_API_KEY"))
        return {
            "available": not reasons,
            "model": self.model,
            "effort": self.effort,
            "auth": "api_key" if api_key else "claude_login",
            "billing": "api" if api_key else "subscription",
            "tool": "snow.py" + ("" if self.allow_write else " (read-only)"),
            "can_write": self.allow_write,
            "instance": self.instance_url,
            "reason": " ".join(reasons) or None,
        }

    # ----- options --------------------------------------------------------

    def _options(self, session_id: Optional[str]) -> ClaudeAgentOptions:
        from datetime import date

        return ClaudeAgentOptions(
            model=self.model,
            effort=self.effort,  # type: ignore[arg-type]
            system_prompt=SYSTEM_PROMPT.format(
                instance=self.instance_url,
                today=date.today().isoformat(),
                write_commands=(
                    "\n"
                    '    python snow.py do     <operation> [-d name=value ...]   e.g. create_incident\n'
                    "    python snow.py create <table>     [-d name=value ...]\n"
                    "    python snow.py update <table> <sys_id> [-d name=value ...]\n"
                    "    python snow.py delete <table> <sys_id> --force\n"
                    if self.allow_write
                    else ""
                ),
                write_rule=(
                    "- You CAN change data: create, update and delete. Use `do <operation>` for a "
                    "named operation (create_incident, update_incident, add_comment, "
                    "resolve_incident ...), or `create` / `update` / `delete` against a table. "
                    "Any table is reachable, not just incident - a business rule is a record in "
                    "sys_script, so you can create and edit those too.\n"
                    "- Find the sys_id first when changing a record you only know by number: "
                    "`query incident -q number=INC0015571 -f sys_id,number`.\n"
                    "- Check the field names with `schema <operation>` or `fields <table>` before "
                    "writing something unfamiliar, rather than guessing.\n"
                    "- State exactly what you are about to change, then do it in the same reply - "
                    "never ask the user to run a command themselves. Afterwards read the record "
                    "back and report the real stored value, citing the number of the record.\n"
                    "- Deleting is irreversible and needs `--force` (without it the CLI waits for a "
                    "typed confirmation that never comes and the command hangs). Only ever delete "
                    "when the user has clearly asked for that specific record to be deleted; "
                    "confirm which record you mean first, and never delete to 'clean up' on your "
                    "own initiative.\n"
                    "- If a write comes back 403 / ACL Exception, the ServiceNow account lacks the "
                    "role for that table. Say so plainly and stop - retrying will not help."
                    if self.allow_write
                    else "- The account is read-only. If asked to create, update, resolve or delete "
                    "anything, explain that this integration can only read, and offer to show the data instead."
                ),
            ),
            tools=["Bash"],  # no Read/Write/Edit/WebFetch: the CLI is the only surface
            # Deliberately NOT in allowed_tools: listing it there pre-approves every
            # Bash command and skips can_use_tool, which is the real guard.
            allowed_tools=[],
            mcp_servers={},  # no MCP anywhere in this stack
            can_use_tool=_guard,
            permission_mode="default",
            setting_sources=[],  # ignore CLAUDE.md and user settings on this machine
            max_turns=self.max_turns,
            cwd=str(ROOT),
            # Set explicitly either way: an inherited SNOW_ALLOW_WRITE from the
            # parent shell must not silently grant the web chat write access.
            env={"SNOW_ALLOW_WRITE": "1" if self.allow_write else "0"},
            resume=session_id or None,
        )

    # ----- run ------------------------------------------------------------

    async def run(
        self, message: str, session_id: Optional[str] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """Yield events: status, tool_use, tool_result, text, done, error."""
        started = time.perf_counter()
        tool_names: Dict[str, str] = {}
        finished = False

        yield {"type": "status", "text": "Reading ServiceNow..."}

        try:
            async for msg in query(prompt=message, options=self._options(session_id)):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock) and block.text.strip():
                            yield {"type": "text", "text": block.text}
                        elif isinstance(block, ToolUseBlock):
                            command = str((block.input or {}).get("command", ""))
                            tool_names[block.id] = command
                            yield {
                                "type": "tool_use",
                                "id": block.id,
                                "name": "snow.py",
                                "input": {"command": command},
                            }

                elif isinstance(msg, UserMessage):
                    blocks = msg.content if isinstance(msg.content, list) else []
                    for block in blocks:
                        if isinstance(block, ToolResultBlock):
                            content = block.content
                            if isinstance(content, list):
                                text = "\n".join(
                                    part.get("text", "")
                                    for part in content
                                    if isinstance(part, dict)
                                )
                            else:
                                text = str(content or "")
                            yield {
                                "type": "tool_result",
                                "id": block.tool_use_id,
                                "ok": not block.is_error,
                                "command": tool_names.get(block.tool_use_id, ""),
                                "result": text[:8000],
                            }

                elif isinstance(msg, ResultMessage):
                    finished = True
                    yield {
                        "type": "done",
                        "reply": getattr(msg, "result", None),
                        "subtype": getattr(msg, "subtype", "success"),
                        "is_error": bool(getattr(msg, "is_error", False)),
                        "num_turns": getattr(msg, "num_turns", None),
                        "session_id": getattr(msg, "session_id", None),
                        "cost_usd": getattr(msg, "total_cost_usd", None),
                        "model": self.model,
                        "elapsed_ms": round((time.perf_counter() - started) * 1000),
                    }

        except ClaudeSDKError as exc:
            logger.exception("chat agent failed")
            yield {"type": "error", "message": str(exc)}
            return
        except Exception as exc:  # noqa: BLE001 - never crash the HTTP stream
            logger.exception("chat agent crashed")
            yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
            return

        if not finished:
            yield {
                "type": "done",
                "reply": None,
                "subtype": "incomplete",
                "is_error": False,
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "model": self.model,
            }
