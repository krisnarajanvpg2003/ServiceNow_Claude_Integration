#!/usr/bin/env python3
"""
snow.py - command line client for the local ServiceNow REST API.

It talks to the backend in servicenow-mcp (default http://127.0.0.1:8095),
which in turn calls the ServiceNow REST API.

Read-only by default. The write commands (do / create / update / post / delete)
refuse to run unless SNOW_ALLOW_WRITE=1 is set in the environment, so nothing
can change ServiceNow by accident.

Standard library only. Nothing to install.

Configuration:
    SNOW_API           base URL of the backend  (default http://127.0.0.1:8095)
    SNOW_ALLOW_WRITE   set to 1 to enable the write commands (default: off)

Commands:
    python snow.py health
    python snow.py tools  [-q TEXT] [--all]
    python snow.py schema <operation>
    python snow.py call   <operation> [-p name=value ...] [--format table|csv|json]
    python snow.py get    <table> <sys_id> [-f "field,field"] [--format table|csv|json]
    python snow.py incident <NUMBER> [-f "field,field"]
    python snow.py count  <table> [-q ENCODED_QUERY]
    python snow.py stats  <table> <group_by_field> [-q ENCODED_QUERY]
    python snow.py query  <table> [-q ENCODED_QUERY] [-f FIELDS] [-l LIMIT]
                                  [--offset N] [--format table|csv|json]
    python snow.py fields <table>

Writing (requires SNOW_ALLOW_WRITE=1 and a ServiceNow account with the rights):
    python snow.py do     <operation> [-d name=value ...]
    python snow.py post   <table>     [-d name=value ...]   (alias for create)
    python snow.py create <table>     [-d name=value ...]
    python snow.py update <table> <sys_id> [-d name=value ...]
    python snow.py delete <table> <sys_id> [--force]
"""

import argparse
import csv
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

class Forbidden(Exception):
    """The account may not read this table."""


TIMEOUT = 60
DEFAULT_API = "http://127.0.0.1:8095"


def base_url():
    return os.environ.get("SNOW_API", DEFAULT_API).rstrip("/")


def get_json(path, params=None):
    """Issue one GET against the backend and return the parsed JSON body."""
    url = base_url() + path
    qs = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")})
    if qs:
        url = url + "?" + qs
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        if e.code == 403 and "sys_dictionary" in url:
            raise Forbidden()
        try:
            payload = json.loads(detail)
            message = payload.get("error") or payload.get("result", {}).get("message") or detail
        except (json.JSONDecodeError, AttributeError):
            message = detail
        sys.exit("error: backend returned HTTP %d\n%s" % (e.code, message))
    except urllib.error.URLError as e:
        sys.exit(
            "error: could not reach the REST API at %s (%s).\n"
            "Start it with:  .venv\\Scripts\\python.exe scripts\\rest_api.py\n"
            "  (run that from the servicenow-mcp folder)" % (base_url(), e.reason)
        )


def rows_of(result):
    """Pull the list of records out of a tool envelope, whatever its key is."""
    if isinstance(result, list):
        return result
    if not isinstance(result, dict):
        return []
    for key in ("incidents", "items", "categories", "groups", "users", "articles",
                "knowledge_bases", "change_requests", "records", "results", "recommendations"):
        value = result.get(key)
        if isinstance(value, list):
            return value
    # A single record returned under a singular key.
    for key in ("incident", "item", "user", "article", "change_request", "record"):
        value = result.get(key)
        if isinstance(value, dict):
            return [value]
    return []


def flat(value):
    """Reference fields arrive as {display_value, link}; keep the readable half."""
    if isinstance(value, dict):
        return value.get("display_value") or value.get("value") or ""
    return value


def emit(rows, columns=None, fmt="table", empty="(no records matched)"):
    """Print rows as an aligned table, CSV or JSON."""
    if not rows:
        print(empty)
        return
    rows = [{k: flat(v) for k, v in r.items()} for r in rows]
    cols = columns or list(rows[0].keys())

    if fmt == "json":
        print(json.dumps(rows, indent=2))
        return

    text = [{c: "" if r.get(c) is None else str(r.get(c, "")) for c in cols} for r in rows]

    if fmt == "csv":
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(text)
        print(out.getvalue().rstrip())
        return

    # table: clip long cells so one wide column cannot swamp the output
    def cell(value):
        value = value.replace("\n", " ").strip()
        return value if len(value) <= 60 else value[:57] + "..."

    text = [{c: cell(r[c]) for c in cols} for r in text]
    widths = {c: max(len(c), *(len(r[c]) for r in text)) for c in cols}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    print("  ".join("-" * widths[c] for c in cols))
    for r in text:
        print("  ".join(r[c].ljust(widths[c]) for c in cols))
    print("\n%d row(s)." % len(text))


def send_delete(path):
    """Issue one DELETE request against the backend and return the parsed body."""
    url = base_url() + path
    req = urllib.request.Request(url, method="DELETE")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8").strip()
            return json.loads(body) if body else {"ok": True}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:800]
        try:
            payload = json.loads(detail)
        except json.JSONDecodeError:
            sys.exit("error: backend returned HTTP %d\n%s" % (e.code, detail))
        message = describe_failure(payload)
        refused = e.code == 403 or any(
            token in message for token in ("403", "ACL", "Forbidden", "security constraints")
        )
        if refused:
            sys.exit(
                "error: ServiceNow refused the delete (403).\n"
                "%s\n"
                "The account in servicenow-mcp/.env does not have delete rights." % message
            )
        sys.exit("error: %s" % message)
    except urllib.error.URLError as e:
        sys.exit(
            "error: could not reach the REST API at %s (%s).\n"
            "Start the backend with start-backend.cmd, then try again." % (base_url(), e.reason)
        )


# --------------------------------------------------------------------------
# Dataset cache. Every read is written to datasets/<slug>.md so a later question
# can be answered from the file instead of hitting ServiceNow again. The file
# records when it was captured, because incident data goes stale quickly.
# --------------------------------------------------------------------------

DATASETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets")


def slugify(parts):
    """A short, stable, filesystem-safe name for a command."""
    raw = "-".join(str(p) for p in parts if p)
    keep = [c.lower() if c.isalnum() else "-" for c in raw]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug.strip("-")[:70]
    return slug or "dataset"


def save_dataset(name, command, rows, rendered, summary=""):
    """Write one result to datasets/<name>.md. Never fatal: caching is a bonus."""
    try:
        os.makedirs(DATASETS, exist_ok=True)
        path = os.path.join(DATASETS, name + ".md")
        captured = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body = [
            "---",
            "command: %s" % command,
            "captured: %s" % captured,
            "rows: %d" % (len(rows) if rows is not None else 0),
            "summary: %s" % (summary or ""),
            "---",
            "",
            "# %s" % name.replace("-", " "),
            "",
            "Captured %s by `%s`." % (captured, command),
            "",
        ]
        if rows:
            cols = list(rows[0].keys())
            body.append("| " + " | ".join(cols) + " |")
            body.append("| " + " | ".join("---" for _ in cols) + " |")
            for r in rows:
                cells = [str(flat(r.get(c, ""))).replace("\n", " ").replace("|", "\\|") for c in cols]
                body.append("| " + " | ".join(cells) + " |")
        elif rendered:
            body.append("```")
            body.append(rendered.rstrip())
            body.append("```")
        else:
            body.append("_No rows._")
        body.append("")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(body))
        return path
    except OSError:
        return None


def read_frontmatter(path):
    """The key: value pairs from a dataset file's frontmatter."""
    meta = {}
    try:
        with open(path, encoding="utf-8") as fh:
            if fh.readline().strip() != "---":
                return meta
            for line in fh:
                if line.strip() == "---":
                    break
                key, _, value = line.partition(":")
                meta[key.strip()] = value.strip()
    except OSError:
        pass
    return meta


def cmd_datasets(args):
    """Preview what has already been collected, newest first."""
    if not os.path.isdir(DATASETS):
        print("(no datasets yet - run a query and one will be saved)")
        return
    files = [f for f in os.listdir(DATASETS) if f.endswith(".md")]
    if not files:
        print("(no datasets yet - run a query and one will be saved)")
        return
    entries = []
    for f in files:
        path = os.path.join(DATASETS, f)
        meta = read_frontmatter(path)
        entries.append({
            "dataset": f[:-3],
            "captured": meta.get("captured", ""),
            "rows": meta.get("rows", ""),
            "command": meta.get("command", ""),
        })
    needle = (args.query or "").lower()
    if needle:
        entries = [e for e in entries
                   if needle in e["dataset"].lower() or needle in e["command"].lower()]
    entries.sort(key=lambda e: e["captured"], reverse=True)
    emit(entries, ["dataset", "captured", "rows", "command"], "table",
         "(nothing matched)")
    print("Read one with:  python snow.py dataset <name>")


def cmd_dataset(args):
    """Print a stored dataset."""
    path = os.path.join(DATASETS, args.name + ".md")
    if not os.path.exists(path):
        sys.exit("error: no dataset called %r. Run 'python snow.py datasets' to list them."
                 % args.name)
    with open(path, encoding="utf-8") as fh:
        sys.stdout.write(fh.read())


def cmd_health(_args):
    data = get_json("/health")
    print("backend  : %s" % base_url())
    print("instance : %s" % data.get("instance", "?"))
    print("servicenow: %s" % data.get("servicenow", "?"))
    print("operations: %s" % data.get("tools_exposed", "?"))
    print("reachable : %s" % ("yes" if data.get("ok") else "NO"))


def cmd_tools(args):
    data = get_json("/tools", {"schema": "false", "q": args.query,
                               "read_only": "false" if args.all else "true"})
    rows = [{"operation": t["tool"],
             "reads": "yes" if t["read_only"] else "no",
             "description": t["description"]}
            for t in data.get("tools", [])]
    emit(rows, ["operation", "reads", "description"], "table", "(no operations matched)")


def cmd_schema(args):
    data = get_json("/tools/" + urllib.parse.quote(args.operation))
    print("%s  (%s)" % (data["tool"], "read-only" if data["read_only"] else "write"))
    print(data.get("description", ""))
    schema = data.get("schema", {})
    required = set(schema.get("required", []))
    print("\nparameters:")
    for name, spec in (schema.get("properties") or {}).items():
        kinds = [spec.get("type")] + [
            o.get("type") for o in spec.get("anyOf", [])
            if isinstance(o, dict) and o.get("type") != "null"
        ]
        kind = next((k for k in kinds if k), "string")
        flag = " (required)" if name in required else ""
        default = spec.get("default")
        extra = "" if default is None else "  [default: %s]" % default
        print("  %-26s %-9s %s%s%s" % (name, kind, spec.get("description", ""), flag, extra))


def parse_pairs(pairs):
    """-p name=value ... -> {name: value}, with JSON values decoded when given."""
    args = {}
    for pair in pairs or []:
        if "=" not in pair:
            sys.exit("error: -p expects name=value, got %r" % pair)
        name, _, value = pair.partition("=")
        try:
            args[name.strip()] = json.loads(value)
        except json.JSONDecodeError:
            args[name.strip()] = value
    return args


def cmd_call(args):
    params = parse_pairs(args.param)
    data = get_json("/tools/%s/call" % urllib.parse.quote(args.operation), params)
    result = data.get("result", data)
    if not data.get("ok", True):
        message = result.get("message") if isinstance(result, dict) else str(result)
        sys.exit("error: %s" % message)
    rows = rows_of(result)
    if rows:
        emit(rows, None, args.format)
    else:
        print(json.dumps(result, indent=2))
    if not args.no_save:
        name = slugify(["call", args.operation] + (args.param or []))
        command = "snow.py call %s %s" % (
            args.operation, " ".join("-p " + x for x in (args.param or [])))
        if save_dataset(name, command.strip(), rows,
                        None if rows else json.dumps(result, indent=2),
                        "%d rows" % len(rows)):
            print("(saved as dataset '%s')" % name)


def cmd_incident(args):
    data = get_json("/incidents/" + urllib.parse.quote(args.number))
    result = data.get("result", {})
    incident = result.get("incident")
    if not incident:
        sys.exit("error: %s" % result.get("message", "incident not found"))
    keys = [k.strip() for k in args.fields.split(",") if k.strip()] if args.fields else None
    if keys:
        missing = [k for k in keys if k not in incident]
        if missing:
            print("(not on this record: %s)" % ", ".join(missing))
        keys = [k for k in keys if k in incident]
    else:
        keys = [k for k in sorted(incident) if str(incident.get(k) or "").strip()]
    width = max(len(k) for k in keys) if keys else 0
    for key in keys:
        value = str(incident.get(key, "")).replace("\n", "\n" + " " * (width + 3))
        print("%s : %s" % (key.ljust(width), value))


def cmd_count(args):
    """Exact count from the ServiceNow Aggregate API - no paging."""
    data = get_json("/stats/" + urllib.parse.quote(args.table), {"q": args.query})
    if not data.get("ok"):
        sys.exit("error: %s" % str(data.get("error"))[:300])
    print("%s: %d record(s) match  [query: %s]"
          % (args.table, data.get("count", 0), args.query or "(all)"))


def cmd_stats(args):
    """Counts grouped by a field, e.g. incidents by priority."""
    data = get_json("/stats/" + urllib.parse.quote(args.table),
                    {"q": args.query, "group_by": args.group_by})
    if not data.get("ok"):
        sys.exit("error: %s" % str(data.get("error"))[:300])
    groups = data.get("groups", [])
    if not groups:
        print("(nothing matched)")
        return
    emit(groups, [args.group_by, "count"], args.format)
    total = sum(g["count"] for g in groups)
    print("total: %d" % total)
    if not args.no_save:
        name = slugify(["stats", args.table, "by", args.group_by, args.query or "all"])
        command = 'snow.py stats %s %s -q "%s"' % (args.table, args.group_by, args.query)
        if save_dataset(name, command, groups, None, "total %d" % total):
            print("(saved as dataset '%s')" % name)


def cmd_query(args):
    data = get_json("/table/" + urllib.parse.quote(args.table),
                    {"q": args.query, "fields": args.fields,
                     "limit": str(args.limit), "offset": str(args.offset)})
    if not data.get("ok"):
        sys.exit("error: %s" % json.dumps(data.get("result"))[:300])
    rows = data.get("result") or []
    cols = [c.strip() for c in args.fields.split(",") if c.strip()] if args.fields else None
    emit(rows, cols, args.format)
    if not args.no_save:
        name = slugify(["query", args.table, args.query or "all"])
        command = 'snow.py query %s -q "%s" -f "%s" -l %d' % (
            args.table, args.query, args.fields, args.limit)
        saved = save_dataset(name, command, rows, None,
                             "%d rows from %s" % (len(rows), args.table))
        if saved:
            print("(saved as dataset '%s')" % name)


def fields_from_sample(table):
    """When sys_dictionary is not readable, infer columns from one record."""
    data = get_json("/table/" + urllib.parse.quote(table), {"limit": "1"})
    rows = data.get("result") or []
    if not rows:
        print("(no records in %s, so its columns cannot be sampled)" % table)
        return
    names = sorted(rows[0].keys())
    print("%s: %d column(s), sampled from one record "
          "(sys_dictionary is not readable by this account)\n" % (table, len(names)))
    populated = {k for k, v in rows[0].items() if str(flat(v)).strip()}
    for name in names:
        print("  %-32s %s" % (name, "" if name in populated else "(empty on the sampled row)"))


def cmd_fields(args):
    try:
        data = get_json("/table/sys_dictionary",
                        {"q": "name=%s^elementISNOTEMPTY^ORDERBYelement" % args.table,
                         "fields": "element,column_label,internal_type,reference,mandatory",
                         "limit": "500", "display_value": "false"})
    except Forbidden:
        return fields_from_sample(args.table)
    rows = data.get("result") or []
    if not rows:
        print("(no fields found for %s - is the table name right?)" % args.table)
        return
    print("%s: %d field(s)\n" % (args.table, len(rows)))
    for r in rows:
        ref = " -> %s" % r["reference"] if r.get("reference") else ""
        req = " (mandatory)" if str(r.get("mandatory")).lower() == "true" else ""
        print("  %-28s %-16s %s%s%s"
              % (r.get("element", ""), r.get("internal_type", ""),
                 r.get("column_label", ""), ref, req))


# --------------------------------------------------------------------------
# Writing. Everything below is refused unless SNOW_ALLOW_WRITE=1 is set, so the
# default behaviour of this file stays read-only.
# --------------------------------------------------------------------------

WRITE_ENV = "SNOW_ALLOW_WRITE"


def writes_enabled():
    return os.environ.get(WRITE_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def require_write():
    if not writes_enabled():
        sys.exit(
            "error: writing is disabled.\n"
            "This CLI is read-only unless you opt in. To allow writes in THIS terminal:\n"
            '    PowerShell:  $env:%s = "1"\n'
            "    cmd.exe   :  set %s=1\n"
            "Then run the command again. The ServiceNow account also needs create/update\n"
            "rights, or ServiceNow itself will answer 403." % (WRITE_ENV, WRITE_ENV)
        )


def send_json(method, path, body):
    """Issue one write request against the backend and return the parsed body."""
    url = base_url() + path
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:800]
        try:
            payload = json.loads(detail)
        except json.JSONDecodeError:
            sys.exit("error: backend returned HTTP %d\n%s" % (e.code, detail))
        message = describe_failure(payload)
        # The backend wraps ServiceNow's 403 in a 502, so match on the text too.
        refused = e.code == 403 or any(
            token in message for token in ("403", "ACL", "Forbidden", "security constraints")
        )
        if refused:
            sys.exit(
                "error: ServiceNow refused the write (403).\n"
                "%s\n"
                "The account in servicenow-mcp/.env has read access only. Ask your\n"
                "ServiceNow admin for a role that allows this (usually itil for incidents)."
                % message
            )
        sys.exit("error: %s" % message)
    except urllib.error.URLError as e:
        sys.exit(
            "error: could not reach the REST API at %s (%s).\n"
            "Start the backend with start-backend.cmd, then try again." % (base_url(), e.reason)
        )


def describe_failure(payload):
    """Pull the most useful message out of an error envelope."""
    if not isinstance(payload, dict):
        return str(payload)[:300]
    result = payload.get("result")
    if isinstance(result, dict):
        inner = result.get("error")
        if isinstance(inner, dict):
            return "%s: %s" % (inner.get("message", ""), inner.get("detail", ""))
        if result.get("message"):
            return str(result["message"])
    if isinstance(payload.get("error"), dict):
        err = payload["error"]
        return "%s: %s" % (err.get("message", ""), err.get("detail", ""))

    message = str(payload.get("error") or "")
    details = payload.get("details")
    if isinstance(details, list) and details:
        lines = []
        for item in details:
            if isinstance(item, dict):
                where = ".".join(str(x) for x in (item.get("loc") or []))
                lines.append("    %s: %s" % (where or "?", item.get("msg", "")))
        if lines:
            return message + "\n" + "\n".join(lines)
    return (message or str(payload))[:400]


def report_write(data, what):
    """Print the outcome of a write in a readable way."""
    result = data.get("result", data)
    if not data.get("ok", True):
        message = describe_failure(data)
        if "403" in message or "ACL" in message or "Forbidden" in message:
            sys.exit(
                "error: ServiceNow refused the write (403).\n%s\n"
                "The account in servicenow-mcp/.env has read access only. Ask your\n"
                "ServiceNow admin for a role that allows this (usually itil for incidents)."
                % message
            )
        sys.exit("error: %s" % message)
    print("%s succeeded." % what)
    records = result if isinstance(result, list) else [result]
    for record in records:
        if not isinstance(record, dict):
            print("  %s" % record)
            continue
        for key in ("number", "sys_id", "short_description", "state", "priority", "message"):
            if record.get(key):
                print("  %-18s %s" % (key, flat(record[key])))


def parse_fields(pairs):
    """
    -d name=value ... -> {name: value} for writes.

    ServiceNow field values are strings ("2", not 2), so bare numbers are kept
    as text. Only obvious JSON structures and booleans are decoded.
    """
    fields = {}
    for pair in pairs or []:
        if "=" not in pair:
            sys.exit("error: -d expects name=value, got %r" % pair)
        name, _, value = pair.partition("=")
        stripped = value.strip()
        if stripped[:1] in "{[" or stripped in ("true", "false", "null"):
            try:
                fields[name.strip()] = json.loads(stripped)
                continue
            except json.JSONDecodeError:
                pass
        fields[name.strip()] = value
    return fields


def cmd_get(args):
    """Fetch one record by sys_id from any table (GET /table/<table>/<sys_id>)."""
    params = {}
    if args.fields:
        params["sysparm_fields"] = args.fields
    data = get_json(
        "/table/%s/%s" % (urllib.parse.quote(args.table), urllib.parse.quote(args.sys_id)),
        params or None,
    )
    if not data.get("ok", True):
        sys.exit("error: %s" % json.dumps(data.get("result"))[:300])
    result = data.get("result") or data
    if isinstance(result, dict) and not any(isinstance(v, dict) for v in result.values()):
        cols = [c.strip() for c in args.fields.split(",") if c.strip()] if args.fields else None
        emit([result], cols, args.format)
    else:
        rows = rows_of(result) or ([result] if isinstance(result, dict) else [])
        cols = [c.strip() for c in args.fields.split(",") if c.strip()] if args.fields else None
        emit(rows, cols, args.format)


def cmd_do(args):
    """Run any write operation from the catalogue, e.g. create_incident."""
    require_write()
    body = parse_fields(args.data)
    data = send_json("POST", "/tools/" + urllib.parse.quote(args.operation), body)
    report_write(data, args.operation)


def cmd_post(args):
    """POST (create) a record into any table — alias for create."""
    require_write()
    body = parse_fields(args.data)
    if not body:
        sys.exit("error: give at least one field, e.g. -d short_description=\"Printer down\"")
    data = send_json("POST", "/table/" + urllib.parse.quote(args.table), body)
    report_write(data, "POST (create) in %s" % args.table)


def cmd_create(args):
    """Insert a record into any table."""
    require_write()
    body = parse_fields(args.data)
    if not body:
        sys.exit("error: give at least one field, e.g. -d short_description=\"Printer down\"")
    data = send_json("POST", "/table/" + urllib.parse.quote(args.table), body)
    report_write(data, "create in %s" % args.table)


def cmd_update(args):
    """Patch one record by sys_id."""
    require_write()
    body = parse_fields(args.data)
    if not body:
        sys.exit("error: give at least one field to change, e.g. -d state=2")
    data = send_json(
        "PATCH",
        "/table/%s/%s" % (urllib.parse.quote(args.table), urllib.parse.quote(args.sys_id)),
        body,
    )
    report_write(data, "update of %s/%s" % (args.table, args.sys_id))


def cmd_delete(args):
    """Delete one record by sys_id (SNOW_ALLOW_WRITE=1 required)."""
    require_write()
    if not args.force:
        answer = input(
            "Are you sure you want to DELETE %s/%s? This cannot be undone. [yes/N] " % (
                args.table, args.sys_id
            )
        ).strip().lower()
        if answer != "yes":
            print("Aborted.")
            sys.exit(0)
    data = send_delete(
        "/table/%s/%s" % (urllib.parse.quote(args.table), urllib.parse.quote(args.sys_id))
    )
    if not data.get("ok", True):
        sys.exit("error: %s" % describe_failure(data))
    print("delete of %s/%s succeeded." % (args.table, args.sys_id))


# ----- exporting to a file (Excel / PDF / CSV) ---------------------------

EXPORTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")

EXTENSIONS = {"xlsx": "xlsx", "excel": "xlsx", "pdf": "pdf", "csv": "csv"}


def rows_from_dataset(name):
    """(rows, captured, command) read back out of a saved dataset's markdown table."""
    path = os.path.join(DATASETS, name + ".md")
    if not os.path.exists(path):
        sys.exit("error: no dataset called %r. Run 'python snow.py datasets' to list them."
                 % name)
    meta = read_frontmatter(path)
    table = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("|") and line.endswith("|"):
                table.append([c.strip().replace("\\|", "|") for c in line[1:-1].split("|")])
    if len(table) < 2:
        sys.exit("error: dataset %r holds no table of records, so there is nothing to export."
                 % name)
    header = table[0]
    rows = [dict(zip(header, cells)) for cells in table[2:]]  # table[1] is the --- rule
    return rows, meta.get("captured", ""), meta.get("command", "")


def download_url(filename):
    return "%s/exports/%s" % (base_url(), urllib.parse.quote(filename))


def cmd_export(args):
    """Write a query, an operation's result or a saved dataset to a file."""
    import snow_export

    fmt = EXTENSIONS.get(args.to.lower())
    if not fmt:
        sys.exit("error: --to must be one of xlsx, pdf, csv")

    columns = [c.strip() for c in args.fields.split(",") if c.strip()] or None
    source = ""

    if args.dataset:
        rows, captured, command = rows_from_dataset(args.source)
        title = args.title or args.source.replace("-", " ").title()
        source = "dataset '%s'%s" % (args.source, (" captured %s" % captured) if captured else "")
        if command:
            source += " - %s" % command
    elif args.call:
        params = parse_pairs(args.param)
        if "limit" not in params:
            params["limit"] = str(args.limit)
        data = get_json("/tools/%s/call" % urllib.parse.quote(args.source), params)
        result = data.get("result", data)
        if not data.get("ok", True):
            message = result.get("message") if isinstance(result, dict) else str(result)
            sys.exit("error: %s" % message)
        rows = rows_of(result)
        title = args.title or args.source.replace("_", " ").title()
        source = "operation %s" % args.source
    elif args.group_by:
        data = get_json("/stats/" + urllib.parse.quote(args.source),
                        {"q": args.query, "group_by": args.group_by})
        if not data.get("ok"):
            sys.exit("error: %s" % str(data.get("error"))[:300])
        rows = data.get("groups", [])
        columns = columns or [args.group_by, "count"]
        title = args.title or "%s by %s" % (args.source, args.group_by)
        source = "%s grouped by %s%s" % (args.source, args.group_by,
                                         (" where %s" % args.query) if args.query else "")
    else:
        data = get_json("/table/" + urllib.parse.quote(args.source),
                        {"q": args.query, "fields": args.fields,
                         "limit": str(args.limit), "offset": str(args.offset)})
        if not data.get("ok"):
            sys.exit("error: %s" % json.dumps(data.get("result"))[:300])
        rows = data.get("result") or []
        title = args.title or args.source.replace("_", " ").title()
        source = args.source + ((" where %s" % args.query) if args.query else " (all records)")

    if not rows:
        sys.exit("error: nothing matched, so no file was written.")

    rows = [{k: flat(v) for k, v in r.items()} for r in rows]
    # A timestamp in the name keeps two exports of the same query side by side.
    when = __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M")
    name = args.name or slugify([title, when])
    filename = "%s.%s" % (name, fmt)
    path = os.path.join(EXPORTS, filename)

    subtitle = "%s | %d records | exported %s" % (source, len(rows), snow_export.stamp())
    written, cols, count = snow_export.write(path, fmt, rows, columns, title, subtitle)

    size = os.path.getsize(written)
    print("Wrote %s" % os.path.relpath(written, os.path.dirname(os.path.abspath(__file__))))
    print("%d row(s) x %d column(s), %.1f KB" % (count, len(cols), size / 1024.0))
    print("Columns: %s" % ", ".join(cols))
    if fmt == "pdf" and len(cols) > 12:
        print("Note: %d columns is a lot for one page, so values are clipped to fit."
              " Narrow it with -f, or use --to xlsx." % len(cols))
    print("Download: %s" % download_url(filename))


def cmd_exports(args):
    """List the files already written to exports/."""
    if not os.path.isdir(EXPORTS):
        print("No exports yet. Create one with 'python snow.py export <table> --to xlsx'.")
        return
    files = sorted(
        (f for f in os.listdir(EXPORTS) if f.rsplit(".", 1)[-1] in ("xlsx", "pdf", "csv")),
        key=lambda f: os.path.getmtime(os.path.join(EXPORTS, f)),
        reverse=True,
    )
    if args.query:
        files = [f for f in files if args.query.lower() in f.lower()]
    if not files:
        print("(no exports matched)")
        return
    for f in files[:40]:
        full = os.path.join(EXPORTS, f)
        when = __import__("datetime").datetime.fromtimestamp(
            os.path.getmtime(full)).strftime("%Y-%m-%d %H:%M")
        print("%-52s %8.1f KB  %s" % (f, os.path.getsize(full) / 1024.0, when))
        print("    %s" % download_url(f))
    print("\n%d file(s)." % len(files))


def main():
    p = argparse.ArgumentParser(
        prog="snow.py", description="Client for the local ServiceNow REST API (read-only by default)."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("health", help="backend and instance status").set_defaults(func=cmd_health)

    ds = sub.add_parser("datasets", help="list saved datasets (check here before querying)")
    ds.add_argument("-q", "--query", default="", help="filter by name or command")
    ds.set_defaults(func=cmd_datasets)

    d1 = sub.add_parser("dataset", help="print one saved dataset")
    d1.add_argument("name")
    d1.set_defaults(func=cmd_dataset)

    t = sub.add_parser("tools", help="list available operations")
    t.add_argument("-q", "--query", default="", help="filter by name or description")
    t.add_argument("--all", action="store_true", help="include write operations")
    t.set_defaults(func=cmd_tools)

    s = sub.add_parser("schema", help="parameters for one operation")
    s.add_argument("operation")
    s.set_defaults(func=cmd_schema)

    c = sub.add_parser("call", help="run a read-only operation")
    c.add_argument("operation")
    c.add_argument("-p", "--param", action="append", metavar="NAME=VALUE")
    c.add_argument("--format", choices=["table", "csv", "json"], default="table")
    c.add_argument("--no-save", action="store_true", help="do not cache this result")
    c.set_defaults(func=cmd_call)

    g = sub.add_parser("get", help="fetch one record by sys_id from any table")
    g.add_argument("table")
    g.add_argument("sys_id")
    g.add_argument("-f", "--fields", default="", help="comma separated field names")
    g.add_argument("--format", choices=["table", "csv", "json"], default="table")
    g.set_defaults(func=cmd_get)

    i = sub.add_parser("incident", help="one incident, all or selected fields")
    i.add_argument("number")
    i.add_argument("-f", "--fields", default="", help="comma separated field names")
    i.set_defaults(func=cmd_incident)

    n = sub.add_parser("count", help="how many rows match a table query")
    n.add_argument("table")
    n.add_argument("-q", "--query", default="")
    n.set_defaults(func=cmd_count)

    st = sub.add_parser("stats", help="counts grouped by a field")
    st.add_argument("table")
    st.add_argument("group_by", help="field to group by, e.g. priority")
    st.add_argument("-q", "--query", default="")
    st.add_argument("--format", choices=["table", "csv", "json"], default="table")
    st.add_argument("--no-save", action="store_true", help="do not cache this result")
    st.set_defaults(func=cmd_stats)

    q = sub.add_parser("query", help="query any table")
    q.add_argument("table")
    q.add_argument("-q", "--query", default="")
    q.add_argument("-f", "--fields", default="")
    q.add_argument("-l", "--limit", type=int, default=10)
    q.add_argument("--offset", type=int, default=0)
    q.add_argument("--format", choices=["table", "csv", "json"], default="table")
    q.add_argument("--no-save", action="store_true", help="do not cache this result")
    q.set_defaults(func=cmd_query)

    e = sub.add_parser("export", help="write records to an Excel, PDF or CSV file")
    e.add_argument("source", help="table name, or an operation/dataset name with --call/--dataset")
    e.add_argument("--to", default="xlsx", help="xlsx (Excel), pdf or csv")
    e.add_argument("-q", "--query", default="", help="encoded query, as for 'query'")
    e.add_argument("-f", "--fields", default="", help="comma separated field names")
    e.add_argument("-l", "--limit", type=int, default=500, help="max records (default 500)")
    e.add_argument("--offset", type=int, default=0)
    e.add_argument("--group-by", default="", help="export grouped counts instead of records")
    e.add_argument("--dataset", action="store_true", help="source is a saved dataset name")
    e.add_argument("--call", action="store_true", help="source is an operation name")
    e.add_argument("-p", "--param", action="append", metavar="NAME=VALUE",
                   help="parameter for --call")
    e.add_argument("--title", default="", help="document title")
    e.add_argument("--name", default="", help="output file name, without extension")
    e.set_defaults(func=cmd_export)

    ex = sub.add_parser("exports", help="list files already exported")
    ex.add_argument("-q", "--query", default="", help="filter by file name")
    ex.set_defaults(func=cmd_exports)

    f = sub.add_parser("fields", help="columns of a table, from sys_dictionary")
    f.add_argument("table")
    f.set_defaults(func=cmd_fields)

    # --- writing (needs SNOW_ALLOW_WRITE=1) ---

    po = sub.add_parser("post", help="POST (create) a record into any table (alias for create)")
    po.add_argument("table")
    po.add_argument("-d", "--data", action="append", metavar="NAME=VALUE")
    po.set_defaults(func=cmd_post)

    d = sub.add_parser("do", help="run a write operation, e.g. create_incident")
    d.add_argument("operation")
    d.add_argument("-d", "--data", action="append", metavar="NAME=VALUE")
    d.set_defaults(func=cmd_do)

    cr = sub.add_parser("create", help="insert a record into any table")
    cr.add_argument("table")
    cr.add_argument("-d", "--data", action="append", metavar="NAME=VALUE")
    cr.set_defaults(func=cmd_create)

    up = sub.add_parser("update", help="update one record by sys_id")
    up.add_argument("table")
    up.add_argument("sys_id")
    up.add_argument("-d", "--data", action="append", metavar="NAME=VALUE")
    up.set_defaults(func=cmd_update)

    dl = sub.add_parser("delete", help="delete one record by sys_id (irreversible)")
    dl.add_argument("table")
    dl.add_argument("sys_id")
    dl.add_argument("--force", action="store_true", help="skip the confirmation prompt")
    dl.set_defaults(func=cmd_delete)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
