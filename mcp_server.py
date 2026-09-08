#!/usr/bin/env python
"""
MCP server for Claude Desktop.

Claude Desktop can only reach outside tools over the Model Context Protocol, so
this file is the adapter: it speaks MCP on stdin/stdout and, for every tool
call, runs the very same `snow.py` command that the CLI and the web chat use.

Nothing about ServiceNow is reimplemented here. Each tool shells out to
snow.py, which calls the local REST API on http://127.0.0.1:8095, which holds
the ServiceNow credentials. Keeping one code path means the dataset cache, the
export writers and the write guard all behave identically in Claude Desktop,
Claude Code and the browser UI.

The REST backend must be running:  servicenow-mcp\\scripts\\rest_api.py

Writing is off unless SNOW_ALLOW_WRITE=1 is set in this process's environment,
exactly as for the CLI. Set it in the Claude Desktop config's "env" block if you
want the desktop app to be able to create and update records.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent
SNOW = ROOT / "snow.py"
TIMEOUT = 180
MAX_OUTPUT = 60_000     # keep one huge table from swamping the conversation

mcp = FastMCP(
    "servicenow",
    instructions=(
        "Read and export data from a ServiceNow instance.\n\n"
        "Work in this order: check snow_datasets for an already-captured answer; prefer a named "
        "operation (snow_operations / snow_call) over a raw table query; use snow_count and "
        "snow_stats instead of fetching rows and tallying them. Always name the fields you need "
        "on snow_query. When the user asks for a PDF, an Excel file, a spreadsheet or a download, "
        "use snow_export - it writes a real file and returns its path and a download URL. "
        "Answer only from what the tools return and cite record numbers such as INC0015571."
    ),
)


def writes_enabled() -> bool:
    return os.environ.get("SNOW_ALLOW_WRITE", "").strip() in {"1", "true", "yes", "on"}


def run(*args: str) -> str:
    """Run one snow.py command and return its output as text."""
    command = [sys.executable, str(SNOW), *[a for a in args if a is not None]]
    try:
        done = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"error: '{' '.join(args)}' took longer than {TIMEOUT}s and was stopped."
    except OSError as exc:
        return f"error: could not run snow.py ({exc})."

    output = (done.stdout or "").strip()
    problem = (done.stderr or "").strip()
    if done.returncode != 0:
        # snow.py reports its failures on stderr and exits non-zero; pass the
        # message through as-is, including the "start the backend" hint.
        return (problem or output or f"error: snow.py exited with code {done.returncode}")[:MAX_OUTPUT]
    if problem and not output:
        return problem[:MAX_OUTPUT]
    if len(output) > MAX_OUTPUT:
        return output[:MAX_OUTPUT] + "\n\n[output truncated - narrow it with -f fields or a lower limit]"
    return output or "(no output)"


def pairs(values: Optional[List[str]], flag: str) -> List[str]:
    """['a=1','b=2'] -> ['-p','a=1','-p','b=2']"""
    out: List[str] = []
    for item in values or []:
        out += [flag, item]
    return out


# ----- status and discovery ----------------------------------------------


@mcp.tool()
def snow_health() -> str:
    """
    Check that the local REST backend and the ServiceNow instance are reachable.

    Run this first if any other tool reports that it cannot reach the API.
    """
    return run("health")


@mcp.tool()
def snow_operations(search: str = "", include_writes: bool = False) -> str:
    """
    List the named ServiceNow operations available, optionally filtered.

    Prefer one of these over a raw table query: they validate their parameters
    and return tidy results.

    search: filter by name or description, e.g. "incident".
    include_writes: also list operations that change data.
    """
    args = ["tools"]
    if search:
        args += ["-q", search]
    if include_writes:
        args += ["--all"]
    return run(*args)


@mcp.tool()
def snow_operation_schema(operation: str) -> str:
    """Show the exact parameters one operation takes, e.g. "create_incident"."""
    return run("schema", operation)


@mcp.tool()
def snow_fields(table: str) -> str:
    """
    List the real columns of a table, including custom u_ fields.

    Use this before working with an unfamiliar table rather than guessing names.
    """
    return run("fields", table)


# ----- reading ------------------------------------------------------------


@mcp.tool()
def snow_call(operation: str, params: Optional[List[str]] = None, output: str = "table") -> str:
    """
    Run a named read-only operation.

    operation: a name from snow_operations, e.g. "list_incidents".
    params: "name=value" strings, e.g. ["limit=5", "state=1"].
    output: table, csv or json.
    """
    return run("call", operation, *pairs(params, "-p"), "--format", output)


@mcp.tool()
def snow_query(
    table: str,
    query: str = "",
    fields: str = "",
    limit: int = 25,
    offset: int = 0,
    output: str = "table",
) -> str:
    """
    Query any table directly. Use this only when no named operation fits.

    table: e.g. "incident", "sys_user", "change_request".
    query: an encoded query - ^ is AND, ^OR is OR, e.g. "active=true^priority<=2".
           Also LIKE, STARTSWITH, ISEMPTY, IN, ORDERBYDESCopened_at, and date
           functions like "opened_at>=javascript:gs.beginningOfLast30Days()".
    fields: comma separated field names. Always set this - a bare query returns
            every column.
    limit: maximum rows. Run snow_count first if the filter may match thousands.
    """
    args = ["query", table, "-l", str(limit), "--offset", str(offset), "--format", output]
    if query:
        args += ["-q", query]
    if fields:
        args += ["-f", fields]
    return run(*args)


@mcp.tool()
def snow_count(table: str, query: str = "") -> str:
    """
    Exactly how many rows match a query, via the ServiceNow Aggregate API.

    Instant and exact - never page through records to count them.
    """
    args = ["count", table]
    if query:
        args += ["-q", query]
    return run(*args)


@mcp.tool()
def snow_stats(table: str, group_by: str, query: str = "") -> str:
    """
    Counts grouped by a field - the answer to any "how many X by Y" question.

    e.g. table="incident", group_by="priority", query="active=true".
    One call returns every group; do not fetch rows and tally them yourself.
    """
    args = ["stats", table, group_by]
    if query:
        args += ["-q", query]
    return run(*args)


@mcp.tool()
def snow_incident(number: str, fields: str = "") -> str:
    """
    One incident by number, e.g. "INC0015548".

    fields: comma separated field names; omit for the full record.
    """
    args = ["incident", number]
    if fields:
        args += ["-f", fields]
    return run(*args)


# ----- the saved-dataset cache -------------------------------------------


@mcp.tool()
def snow_datasets(search: str = "") -> str:
    """
    List results already captured from earlier questions, newest first.

    Check here before querying: if a dataset answers the question and was
    captured recently, read it with snow_dataset instead of hitting ServiceNow
    again. Re-query live when the user says now/today/currently/latest, or when
    the dataset is more than about an hour old, and say which one you used.
    """
    args = ["datasets"]
    if search:
        args += ["-q", search]
    return run(*args)


@mcp.tool()
def snow_dataset(name: str) -> str:
    """Read one saved dataset by name, as listed by snow_datasets."""
    return run("dataset", name)


# ----- files: Excel, PDF, CSV --------------------------------------------


@mcp.tool()
def snow_export(
    source: str,
    to: str = "xlsx",
    query: str = "",
    fields: str = "",
    limit: int = 500,
    group_by: str = "",
    from_dataset: bool = False,
    operation: bool = False,
    params: Optional[List[str]] = None,
    title: str = "",
) -> str:
    """
    Write records to a real Excel, PDF or CSV file and return a download link.

    Use this whenever the user asks for a PDF, an Excel or xlsx file, a
    spreadsheet, a CSV, a report or a download.

    source: the table to export, e.g. "sys_user". With from_dataset=True it is
            a saved dataset name; with operation=True it is an operation name.
    to: "xlsx" for Excel, "pdf", or "csv".
    query / fields: as for snow_query - export the data the user actually asked
            about, and name the fields so the file has useful columns.
    limit: raise it when the user wants the whole list. An export is meant to be
            complete, not the handful of rows shown in the reply.
    group_by: export grouped counts (as snow_stats) instead of records.
    title: a readable document title, e.g. "Open incidents".

    The file is written to exports/ and served by the backend. Give the user the
    "Download:" URL from the result.
    """
    fmt = (to or "xlsx").lower()
    if fmt in {"excel", "spreadsheet", "xls"}:
        fmt = "xlsx"
    if fmt not in {"xlsx", "pdf", "csv"}:
        return "error: 'to' must be xlsx, pdf or csv."

    args = ["export", source, "--to", fmt, "-l", str(limit)]
    if query:
        args += ["-q", query]
    if fields:
        args += ["-f", fields]
    if group_by:
        args += ["--group-by", group_by]
    if from_dataset:
        args += ["--dataset"]
    if operation:
        args += ["--call", *pairs(params, "-p")]
    if title:
        args += ["--title", title]

    result = run(*args)
    if result.lower().startswith("error"):
        return result
    # The local path helps when the user would rather open the file than click.
    return result + "\n\nSaved in: %s" % (ROOT / "exports")


@mcp.tool()
def snow_exports(search: str = "") -> str:
    """List the Excel, PDF and CSV files exported so far, with their links."""
    args = ["exports"]
    if search:
        args += ["-q", search]
    return run(*args)


# ----- writing (only when SNOW_ALLOW_WRITE=1) -----------------------------


@mcp.tool()
def snow_write(
    operation: str = "",
    table: str = "",
    sys_id: str = "",
    data: Optional[List[str]] = None,
) -> str:
    """
    Create or update a record. Disabled unless the server was started with
    SNOW_ALLOW_WRITE=1, and the ServiceNow account needs the matching role.

    Confirm the exact values with the user before calling this - writes cannot
    be undone from here.

    Give either:
      operation: a named write operation, e.g. "create_incident"     (a create)
      table:     a table to insert into, e.g. "incident"             (a create)
      table + sys_id: the record to update                           (an update)
    data: "name=value" strings, e.g. ["short_description=Printer down", "urgency=2"].
    Check the parameters first with snow_operation_schema or snow_fields.
    """
    if not writes_enabled():
        return (
            "Writing is disabled. This MCP server was started without SNOW_ALLOW_WRITE=1, so it "
            "can only read. To allow writes, add \"env\": {\"SNOW_ALLOW_WRITE\": \"1\"} to this "
            "server's entry in claude_desktop_config.json and restart Claude Desktop. The "
            "ServiceNow account also needs the right role (usually 'itil' for incidents)."
        )
    if not data:
        return "error: nothing to write - pass data as [\"field=value\", ...]."

    fields = pairs(data, "-d")
    if operation:
        return run("do", operation, *fields)
    if table and sys_id:
        return run("update", table, sys_id, *fields)
    if table:
        return run("create", table, *fields)
    return "error: give an operation, a table, or a table and sys_id."


if __name__ == "__main__":
    if not SNOW.exists():
        sys.exit(f"snow.py was not found next to this file ({SNOW}).")
    mcp.run()
