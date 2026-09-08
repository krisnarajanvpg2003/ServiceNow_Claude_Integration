# ServiceNow (read-only) via snow.py

You can read and write this ServiceNow instance through `snow.py`, a client for
the project's local REST API. Run it with the Bash tool.

Reading works out of the box. **Writing is off by default**: the `do`, `create`
and `update` commands refuse to run unless `SNOW_ALLOW_WRITE=1` is set in the
environment, and the ServiceNow account must have the matching role.

Never write your own script that calls ServiceNow directly — only use `snow.py`.

## Before anything else

`snow.py` talks to the backend on `http://127.0.0.1:8095`, so that must be
running:

    python snow.py health

If it reports it cannot reach the API, start the backend from the
`servicenow-mcp` folder with `.venv\Scripts\python.exe scripts\rest_api.py`
and try again. Do not attempt to query ServiceNow another way.

## Commands

    python snow.py health
    python snow.py tools    [-q TEXT] [--all]
    python snow.py schema   <operation>
    python snow.py call     <operation> [-p name=value ...] [--format table|csv|json]
    python snow.py incident <NUMBER> [-f "field,field"]
    python snow.py count    <table> [-q "ENCODED_QUERY"]
    python snow.py stats    <table> <group_by_field> [-q "ENCODED_QUERY"]
    python snow.py query    <table> [-q "ENCODED_QUERY"] [-f "field,field"] [-l N]
                                    [--offset N] [--format table|csv|json]
    python snow.py fields   <table>
    python snow.py datasets [-q TEXT]        list what has already been collected
    python snow.py dataset  <name>           read one saved dataset

Files (Excel / PDF / CSV):

    python snow.py export <table> --to xlsx|pdf|csv [-q QUERY] [-f "field,field"] [-l N]
                                  [--offset N] [--group-by FIELD] [--title TEXT] [--name FILE]
    python snow.py export <name>  --dataset --to pdf        export a saved dataset
    python snow.py export <op>    --call -p name=value      export an operation's result
    python snow.py exports [-q TEXT]                        list what has been exported

Writing (needs SNOW_ALLOW_WRITE=1):

    python snow.py do     <operation> [-d name=value ...]      e.g. create_incident
    python snow.py create <table>     [-d name=value ...]
    python snow.py update <table> <sys_id> [-d name=value ...]

## How to work

- **Check saved datasets first.** Run `snow.py datasets` before querying. If a dataset already
  answers the question and its `captured` time is recent enough, read it with
  `snow.py dataset <name>` instead of hitting ServiceNow again - it is far faster.
- **Re-query instead when freshness matters.** If the user says now / today / currently / latest,
  or the dataset was captured more than about an hour ago, run the real query. Say which you used:
  "from a snapshot taken at 09:14" or "read live just now".
- Every read is saved to `datasets/` automatically. Add `--no-save` to skip caching one result.

1. **Prefer a named operation over a raw table query.** `snow.py tools -q incident`
   lists what exists; those operations validate their parameters and return
   tidy results. Drop to `query <table>` only when no operation fits.
2. **Discover, don't guess.** `snow.py schema <operation>` shows the exact
   parameters; `snow.py fields <table>` shows real columns (including custom
   `u_` ones). Do this before working with something unfamiliar.
3. **Always name fields with `-f` on table queries.** A bare `query` returns
   every column and fills the context fast. Ask for what the question needs.
4. **`count` before a broad `query`**, so a filter matching thousands of rows is
   caught before pulling them. `count` uses the ServiceNow Aggregate API and is
   exact and instant - never page through records to count them.
5. **For "how many X by Y", use `stats`.** `snow.py stats incident priority`
   returns the counts grouped by that field in one call. Do not fetch rows and
   tally them yourself.
6. **Answer from the data.** Cite record numbers (INC0015571). Never invent
   records, numbers or dates; if a lookup returns nothing, say so.
7. **When a file is asked for, use `export`.** PDF, Excel/xlsx, spreadsheet, CSV,
   "report" or "download" all mean `snow.py export`. Pass the same `-q` / `-f` you
   would use for `query`, and raise `-l` (default 500) so the file is the complete
   list rather than the handful of rows shown in chat. Files land in `exports/`
   and the command prints a `Download:` URL served by the backend; give the user
   that URL. Nothing is written to ServiceNow, so this needs no write access.

## Examples

    python snow.py incident INC0015548 -f "short_description,description,state"
    python snow.py call list_incidents -p limit=5 -p state=1
    python snow.py query incident -q "active=true^priority<=2" -f "number,short_description,priority" -l 20
    python snow.py count incident -q "active=true"
    python snow.py stats incident priority -q "active=true"
    python snow.py stats incident assignment_group -q "active=true"
    python snow.py query sys_user_group -f "name,description" -l 10 --format csv
    python snow.py export sys_user -f "user_name,name,email,department" -l 1000 --to xlsx
    python snow.py export incident -q "active=true" -f "number,short_description,priority" \
        --to pdf --title "Open incidents"
    python snow.py export incident --group-by priority -q "active=true" --to pdf

## Encoded query syntax (for -q on count / query)

- `^` AND, `^OR` OR — `active=true^priority=1`, `priority=1^ORpriority=2`
- `=` `!=` equals / not equals
- `LIKE` `STARTSWITH` substring / prefix match
- `>` `<` `>=` `<=` comparison (numbers and dates)
- `ISEMPTY` `ISNOTEMPTY`
- `IN` — `priorityIN1,2,3`
- `ORDERBY` `ORDERBYDESC` — `ORDERBYDESCopened_at`
- Relative dates use ServiceNow gs functions, e.g.
  `opened_at>=javascript:gs.beginningOfLast30Days()`

State and priority are stored as integers. If unsure what a value means on a
table, check with `fields` or ask rather than assuming.

## Common tables

- `incident` — incidents
- `change_request` — changes
- `sc_request` / `sc_req_item` — catalog requests / items
- `sys_user` / `sys_user_group` — users / groups
- `kb_knowledge` — knowledge articles

## Writing

Before any write:

1. **Confirm the values with the user first.** Show what you are about to create
   or change and wait for a yes. Writes are not reversible from here — there is
   no delete command.
2. **Check the schema.** `snow.py schema create_incident` lists the exact
   parameters. Field values are strings: `-d urgency=2`, not `-d urgency=2` as a
   number (the CLI keeps them as text for you).
3. **Report the result.** On success print the `number` of the new record.

    python snow.py do create_incident -d short_description="Printer down" -d urgency=2

If a write returns **403 / "ACL Exception"**, the account in
`servicenow-mcp/.env` has read access only. Say so and stop — retrying will not
help. The fix is a ServiceNow role (usually `itil` for incidents), which only an
admin can grant.

If a write is refused with **"writing is disabled"**, `SNOW_ALLOW_WRITE=1` is not
set. Tell the user how to enable it rather than trying to set it yourself:

    PowerShell:  $env:SNOW_ALLOW_WRITE = "1"

## Repository layout

- `snow.py` — the CLI (this is what you run)
- `snow_export.py` — the Excel / PDF / CSV writers used by `snow.py export`
- `exports/` — generated files, served at `http://127.0.0.1:8095/exports/<file>`
- `mcp_server.py` — MCP adapter for Claude Desktop; each tool shells out to
  `snow.py`. Not used by Claude Code — keep using the CLI here.
- `CLAUDE_DESKTOP.md` — how to set that up
- `servicenow-mcp/` — the REST API backend; `scripts/rest_api.py` is the server
- `servicenow-mcp/docs/rest_api.md` — every operation, generated from the code
- `Frontend/` — the React chat UI that calls the same REST API

The `servicenow-mcp` folder name is misleading: there is no Model Context
Protocol in the backend, the CLI or the web UI. All of that is plain REST.

The one exception is `mcp_server.py` at the root, which exists only so Claude
Desktop can reach this project — MCP is the only way that app talks to outside
tools. It is a thin adapter that runs `snow.py` for each tool call, not a second
implementation. Nothing else in the stack uses it, and you should not use it
from Claude Code: run `snow.py` directly as described above.
