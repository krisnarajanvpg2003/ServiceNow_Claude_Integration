#!/usr/bin/env python
"""
Generate the REST API reference and a Postman collection from the live registry.

Both outputs are derived from the tool table itself, so they cannot drift from
the code. Re-run after adding or changing a tool:

    .venv\\Scripts\\python.exe scripts\\generate_docs.py

Writes:
    docs/rest_api.md                                  complete endpoint reference
    postman/ServiceNow-REST-API.postman_collection.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from servicenow_mcp.registry import ServiceNowRegistry  # noqa: E402
from servicenow_mcp.utils.config import (  # noqa: E402
    AuthConfig,
    AuthType,
    BasicAuthConfig,
    ServerConfig,
)

# Human titles for each tool module, in the order they should appear.
MODULE_TITLES: List[Tuple[str, str]] = [
    ("incident_tools", "Incident management"),
    ("catalog_tools", "Service catalog"),
    ("catalog_variables", "Catalog variables"),
    ("catalog_optimization", "Catalog optimization"),
    ("change_tools", "Change management"),
    ("changeset_tools", "Changeset management"),
    ("knowledge_base", "Knowledge base"),
    ("user_tools", "User and group management"),
    ("workflow_tools", "Workflow management"),
    ("script_include_tools", "Script includes"),
    ("story_tools", "Agile: stories"),
    ("epic_tools", "Agile: epics"),
    ("scrum_task_tools", "Agile: scrum tasks"),
    ("project_tools", "Agile: projects"),
]

# The named convenience routes the server exposes, for the reference and Postman.
NAMED_ROUTES: List[Tuple[str, str, str]] = [
    ("Health check", "/health", "Instance reachability and tool count"),
    ("List incidents", "/incidents?limit=5", "Newest first. q, state, sort, order, created_from/to"),
    ("Get incident", "/incidents/{{incidentNumber}}", "One incident by number"),
    ("List catalog items", "/catalog/items?limit=5", "Optional q, category"),
    ("Get catalog item", "/catalog/items/{{itemSysId}}", "One catalog item by sys_id"),
    ("List catalog categories", "/catalog/categories?limit=5", "Optional q"),
    ("Catalog recommendations", "/catalog/recommendations", "Optimization analysis"),
    ("List groups", "/groups?limit=5", "Optional q"),
    ("List users", "/users?limit=5", "Optional q"),
    ("Get user by username", "/users/{{username}}", "One user by user_name"),
    ("Get user by email", "/users/by-email/{{email}}", "One user by email"),
    ("List knowledge bases", "/knowledge/bases?limit=5", "Knowledge bases"),
    ("List articles", "/knowledge/articles?limit=5", "Optional q"),
    ("Get article", "/knowledge/articles/{{articleId}}", "One article"),
    ("List change requests", "/changes?limit=5", "Change requests"),
    ("Get change request", "/changes/{{changeId}}", "One change request"),
]


def offline_registry() -> ServiceNowRegistry:
    """A registry built from placeholder credentials: no network calls are made."""
    return ServiceNowRegistry(
        ServerConfig(
            instance_url="https://example.service-now.com",
            auth=AuthConfig(
                type=AuthType.BASIC, basic=BasicAuthConfig(username="docs", password="docs")
            ),
        )
    )


def module_of(registry: ServiceNowRegistry, name: str) -> str:
    impl = registry.tool_definitions[name][0]
    return getattr(impl, "__module__", "").rsplit(".", 1)[-1]


def group_tools(registry: ServiceNowRegistry) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    for name in registry.names:
        groups.setdefault(module_of(registry, name), []).append(name)
    return groups


def field_rows(schema: Dict[str, Any]) -> List[Tuple[str, str, str, str]]:
    """(name, type, required, description) for each field in a params schema."""
    required = set(schema.get("required", []))
    rows = []
    for field, spec in (schema.get("properties") or {}).items():
        kinds = [spec.get("type")] + [
            option.get("type")
            for option in spec.get("anyOf", [])
            if isinstance(option, dict) and option.get("type") != "null"
        ]
        kind = next((k for k in kinds if k), "string")
        default = spec.get("default")
        note = spec.get("description", "") or ""
        if default is not None:
            note = (note + f" (default: `{default}`)").strip()
        rows.append((field, kind, "yes" if field in required else "no", note))
    return rows


def render_reference(registry: ServiceNowRegistry) -> str:
    groups = group_tools(registry)
    total = len(registry.names)
    read_only = sum(1 for n in registry.names if registry.is_read_only(n))

    out: List[str] = []
    w = out.append

    w("# ServiceNow REST API reference")
    w("")
    w(
        f"Auto-generated from the tool registry by `scripts/generate_docs.py`. "
        f"**{total} operations** ({read_only} read-only, {total - read_only} write). "
        "Do not edit by hand; re-run the generator instead."
    )
    w("")
    w("Every endpoint below calls the ServiceNow REST API (`/api/now/...`) from the backend.")
    w("There is no Model Context Protocol anywhere in this stack.")
    w("")
    w("Base URL: `http://127.0.0.1:8095` (through the web UI's dev proxy: `/api`).")
    w("")
    w("## Contents")
    w("")
    w("1. [Named routes](#named-routes)")
    w("2. [Generic tool endpoints](#generic-tool-endpoints)")
    w("3. [Whole-instance Table API](#whole-instance-table-api)")
    w("4. [Operations by module](#operations-by-module)")
    w("")

    # --- named routes
    w("## Named routes")
    w("")
    w("Friendly shapes for the most common reads. These are what the web UI calls.")
    w("")
    w("| Route | Notes |")
    w("| --- | --- |")
    for _title, path, notes in NAMED_ROUTES:
        # Postman uses {{var}}; the prose reads better with a single brace.
        w(f"| `GET {path.replace(chr(123)*2, chr(123)).replace(chr(125)*2, chr(125))}` | {notes} |")
    w("")
    w("```bash")
    w('curl "http://127.0.0.1:8095/incidents?limit=5&sort=created&order=desc"')
    w('curl "http://127.0.0.1:8095/incidents/INC0015571"')
    w("```")
    w("")

    # --- generic tool endpoints
    w("## Generic tool endpoints")
    w("")
    w("Every operation in this document is reachable generically, without a named route.")
    w("")
    w("| Endpoint | Purpose |")
    w("| --- | --- |")
    w("| `GET /tools` | The full catalogue with JSON schemas. `?read_only=true`, `?q=`, `?schema=false` |")
    w("| `GET /tools/{name}` | One operation's contract: description, methods, schema |")
    w("| `GET /tools/{name}/call?...` | Run a **read-only** operation with query parameters |")
    w("| `POST /tools/{name}` | Run **any** operation with a JSON body |")
    w("")
    w("Read-only operations accept both forms. Write operations are POST-only; calling")
    w("one via `GET .../call` returns `405` with a message pointing at the POST form.")
    w("")
    w("```bash")
    w('curl "http://127.0.0.1:8095/tools?read_only=true&schema=false"')
    w('curl "http://127.0.0.1:8095/tools/list_incidents/call?limit=3&state=1"')
    w('curl -X POST http://127.0.0.1:8095/tools/create_incident \\')
    w('  -H "Content-Type: application/json" \\')
    w("""  -d '{"short_description": "Laptop will not boot", "urgency": "2"}'""")
    w("```")
    w("")
    w("All tool responses share one envelope:")
    w("")
    w("```json")
    w("{")
    w('  "tool": "list_incidents",')
    w('  "arguments": { "limit": 3 },')
    w('  "ok": true,')
    w('  "result": { "success": true, "message": "Found 3 incidents", "incidents": [] }')
    w("}")
    w("```")
    w("")
    w("`ok` is `false` with HTTP `502` when ServiceNow rejects the call, `400` when the")
    w("arguments fail validation (the response then carries a `details` array), and `404`")
    w("for an unknown operation name.")
    w("")

    # --- table api
    w("## Whole-instance Table API")
    w("")
    w("A thin pass-through to the ServiceNow Table API, so any table the account can")
    w("reach is available even when no purpose-built operation exists.")
    w("")
    w("| Endpoint | Purpose |")
    w("| --- | --- |")
    w("| `GET /table/{table}` | Query a table |")
    w("| `GET /table/{table}/{sys_id}` | One record |")
    w("| `POST /table/{table}` | Create a record |")
    w("| `PATCH /table/{table}/{sys_id}` | Update a record |")
    w("| `DELETE /table/{table}/{sys_id}` | Delete a record |")
    w("")
    w("Query parameters: `q` (encoded query), `fields`, `limit`, `offset`,")
    w("`display_value`, plus any `sysparm_*` passed straight through.")
    w("")
    w("```bash")
    w('curl "http://127.0.0.1:8095/table/incident?q=active=true&fields=number,short_description&limit=5"')
    w('curl "http://127.0.0.1:8095/table/sys_user_group?limit=10"')
    w("```")
    w("")
    w("Writes depend entirely on the roles of the ServiceNow account in `.env`.")
    w("A read-only account receives ServiceNow's own `403`, reported as-is.")
    w("")

    # --- per-module reference
    w("## Operations by module")
    w("")
    seen = set()
    ordered = [(m, t) for m, t in MODULE_TITLES if m in groups]
    ordered += [(m, m.replace("_", " ").title()) for m in sorted(groups) if m not in dict(MODULE_TITLES)]

    for module, title in ordered:
        names = sorted(groups.get(module, []))
        if not names:
            continue
        seen.update(names)
        w(f"### {title}")
        w("")
        w(f"Source: `src/servicenow_mcp/tools/{module}.py`")
        w("")
        for name in names:
            info = registry.describe(name)
            verb = "GET / POST" if info["read_only"] else "POST"
            w(f"#### `{name}`")
            w("")
            w(info["description"] or "_No description._")
            w("")
            w(f"- **Methods:** {verb}")
            if info["read_only"]:
                w(f"- **Call:** `GET /tools/{name}/call?...` or `POST /tools/{name}`")
            else:
                w(f"- **Call:** `POST /tools/{name}`")
            rows = field_rows(info["schema"])
            w("")
            if rows:
                w("| Parameter | Type | Required | Notes |")
                w("| --- | --- | --- | --- |")
                for field, kind, req, note in rows:
                    w(f"| `{field}` | {kind} | {req} | {note} |")
            else:
                w("_Takes no parameters._")
            w("")
    return "\n".join(out) + "\n"


def postman_request(name: str, method: str, raw_path: str, description: str, body: Any = None):
    path_part, _, query_part = raw_path.partition("?")
    query = [
        {"key": k, "value": v}
        for k, v in (pair.split("=", 1) for pair in query_part.split("&") if "=" in pair)
    ]
    request: Dict[str, Any] = {
        "method": method,
        "header": [{"key": "Accept", "value": "application/json"}],
        "url": {
            "raw": "{{baseUrl}}" + raw_path,
            "host": ["{{baseUrl}}"],
            "path": [seg for seg in path_part.split("/") if seg],
            "query": query,
        },
        "description": description,
    }
    if body is not None:
        request["header"].append({"key": "Content-Type", "value": "application/json"})
        request["body"] = {"mode": "raw", "raw": json.dumps(body, indent=2)}
    return {
        "name": name,
        "request": request,
        "event": [
            {
                "listen": "test",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        "pm.test('HTTP 200', function () { pm.response.to.have.status(200); });",
                    ],
                },
            }
        ],
    }


def render_postman(registry: ServiceNowRegistry, base_url: str) -> Dict[str, Any]:
    groups = group_tools(registry)

    named = [
        postman_request(title, "GET", path, notes) for title, path, notes in NAMED_ROUTES
    ]

    discovery = [
        postman_request("List all operations", "GET", "/tools?schema=false", "The full catalogue"),
        postman_request("List read-only operations", "GET", "/tools?read_only=true&schema=false", "Reads only"),
        postman_request("Describe one operation", "GET", "/tools/list_incidents", "Contract + JSON schema"),
    ]

    table = [
        postman_request("Query any table", "GET", "/table/incident?limit=5&fields=number,short_description", "Table API pass-through"),
        postman_request("Get one record", "GET", "/table/incident/{{sysId}}", "One record by sys_id"),
        postman_request("Create a record", "POST", "/table/incident", "Needs a writable account", {"short_description": "Created from Postman"}),
        postman_request("Update a record", "PATCH", "/table/incident/{{sysId}}", "Needs a writable account", {"short_description": "Updated from Postman"}),
        postman_request("Delete a record", "DELETE", "/table/incident/{{sysId}}", "Needs a writable account"),
    ]

    # One folder per module, one request per operation.
    module_folders = []
    ordered = [(m, t) for m, t in MODULE_TITLES if m in groups]
    ordered += [(m, m.replace("_", " ").title()) for m in sorted(groups) if m not in dict(MODULE_TITLES)]
    for module, title in ordered:
        items = []
        for name in sorted(groups.get(module, [])):
            info = registry.describe(name)
            schema = info["schema"]
            required = schema.get("required", [])
            props = schema.get("properties") or {}
            if info["read_only"]:
                sample = "&".join(f"{f}={{{{{f}}}}}" for f in required) or "limit=5"
                items.append(
                    postman_request(
                        f"{name} (GET)", "GET", f"/tools/{name}/call?{sample}", info["description"]
                    )
                )
            else:
                body = {f: props.get(f, {}).get("default", f"<{f}>") for f in required}
                items.append(
                    postman_request(
                        f"{name} (POST)", "POST", f"/tools/{name}", info["description"], body
                    )
                )
        if items:
            module_folders.append({"name": title, "item": items})

    return {
        "info": {
            "name": "ServiceNow REST API",
            "description": (
                f"Every ServiceNow operation exposed over REST ({len(registry.names)} in total), "
                "plus the whole-instance Table API. No MCP is involved.\n\n"
                "Start the backend first:\n"
                "    .venv\\Scripts\\python.exe scripts\\rest_api.py\n\n"
                "Write requests require a ServiceNow account with the matching roles; a "
                "read-only account gets HTTP 403 back from ServiceNow."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [
            {"key": "baseUrl", "value": base_url},
            {"key": "incidentNumber", "value": "INC0015571"},
            {"key": "itemSysId", "value": "00766c3c67271200f8d0ff4f9485ef56"},
            {"key": "username", "value": "admin"},
            {"key": "email", "value": "admin@example.com"},
            {"key": "articleId", "value": ""},
            {"key": "changeId", "value": ""},
            {"key": "sysId", "value": ""},
        ],
        "item": [
            {"name": "1. Named routes", "item": named},
            {"name": "2. Discovery", "item": discovery},
            {"name": "3. Table API (whole instance)", "item": table},
            {"name": "4. Operations by module", "item": module_folders},
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate REST docs and a Postman collection")
    parser.add_argument("--base-url", default="http://127.0.0.1:8095")
    args = parser.parse_args()

    registry = offline_registry()

    reference = ROOT / "docs" / "rest_api.md"
    reference.parent.mkdir(parents=True, exist_ok=True)
    reference.write_text(render_reference(registry), encoding="utf-8")
    print(f"Wrote {reference.relative_to(ROOT)} ({len(registry.names)} operations)")

    collection_path = ROOT / "postman" / "ServiceNow-REST-API.postman_collection.json"
    collection_path.parent.mkdir(parents=True, exist_ok=True)
    collection = render_postman(registry, args.base_url)
    collection_path.write_text(json.dumps(collection, indent=2), encoding="utf-8")
    count = sum(
        len(folder.get("item", []))
        if isinstance(folder.get("item"), list) and folder["name"] != "4. Operations by module"
        else sum(len(sub.get("item", [])) for sub in folder.get("item", []))
        for folder in collection["item"]
    )
    print(f"Wrote {collection_path.relative_to(ROOT)} ({count} requests)")


if __name__ == "__main__":
    main()
