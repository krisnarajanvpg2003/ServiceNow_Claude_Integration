#!/usr/bin/env python
"""
ServiceNow REST API server.

Pure REST. There is no Model Context Protocol anywhere in this stack: every
route calls a Python tool function that issues an HTTPS request to the
ServiceNow REST API (/api/now/...).

Run (from the servicenow-mcp folder; credentials come from .env):
    .venv\\Scripts\\python.exe scripts\\rest_api.py             # http://127.0.0.1:8095
    .venv\\Scripts\\python.exe scripts\\rest_api.py --port 9000

Three layers, smallest to largest:

  1. Named routes      GET /incidents?limit=5, GET /catalog/items, GET /users/{username} ...
                       Friendly shapes used by the web UI.

  2. Every tool        GET  /tools                  the full catalogue with JSON schemas
                       GET  /tools/{name}           one tool's contract
                       GET  /tools/{name}/call?...  run a read-only tool via query params
                       POST /tools/{name}           run any tool with a JSON body
                       All tools are exposed, reads and writes alike.

  3. Whole instance    GET    /table/{table}              query any table
                       GET    /table/{table}/{sys_id}     one record
                       POST   /table/{table}              create
                       PATCH  /table/{table}/{sys_id}     update
                       DELETE /table/{table}/{sys_id}     delete
                       A thin pass-through to the ServiceNow Table API, so any
                       table the account can see is reachable.

Whether a write actually succeeds depends on the roles of the ServiceNow
account in .env. A read-only account gets HTTP 403 from ServiceNow on writes;
that is reported back as-is rather than hidden.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
import uvicorn
from dotenv import load_dotenv
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.routing import Route

from servicenow_mcp.chat_agent import ChatAgent, strip_claude_code_env
from servicenow_mcp import uploads
from servicenow_mcp.registry import ServiceNowRegistry
from servicenow_mcp.utils.config import (
    AuthConfig,
    AuthType,
    BasicAuthConfig,
    ServerConfig,
)

ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger("rest_api")

DEFAULT_RECOMMENDATION_TYPES = "inactive_items,low_usage,description_quality"

# Files written by `snow.py export`, served back for download by /exports.
EXPORTS = ROOT.parent / "exports"
EXPORT_TYPES = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pdf": "application/pdf",
    ".csv": "text/csv",
}

# Friendly ?sort= aliases for /incidents -> ServiceNow field names.
INCIDENT_SORTS = {
    "created": "sys_created_on",
    "updated": "sys_updated_on",
    "opened": "opened_at",
    "resolved": "resolved_at",
    "closed": "closed_at",
    "number": "number",
    "priority": "priority",
    "state": "state",
}


def config_from_env() -> ServerConfig:
    """Build the instance config from .env / environment (basic auth)."""
    instance_url = os.getenv("SERVICENOW_INSTANCE_URL")
    username = os.getenv("SERVICENOW_USERNAME")
    password = os.getenv("SERVICENOW_PASSWORD")
    if not (instance_url and username and password):
        raise SystemExit(
            "Set SERVICENOW_INSTANCE_URL, SERVICENOW_USERNAME and SERVICENOW_PASSWORD in .env"
        )
    return ServerConfig(
        instance_url=instance_url.rstrip("/"),
        auth=AuthConfig(
            type=AuthType.BASIC, basic=BasicAuthConfig(username=username, password=password)
        ),
        timeout=int(os.getenv("SERVICENOW_TIMEOUT", "30")),
    )


def coerce_query_params(model: Any, qp: Any) -> Dict[str, Any]:
    """
    Turn flat query-string values into kwargs for a pydantic params model.

    Query strings are all text, so list-typed fields accept a comma-separated
    value and object-typed fields accept a JSON literal. Everything else is
    left as a string for pydantic to validate and coerce.
    """
    schema = model.model_json_schema()
    properties: Dict[str, Any] = schema.get("properties", {})
    args: Dict[str, Any] = {}
    for key, value in qp.items():
        spec = properties.get(key)
        if spec is None:
            args[key] = value
            continue
        kinds = {spec.get("type")} | {
            option.get("type") for option in spec.get("anyOf", []) if isinstance(option, dict)
        }
        if "array" in kinds:
            args[key] = [part.strip() for part in value.split(",") if part.strip()]
        elif "object" in kinds:
            try:
                args[key] = json.loads(value)
            except json.JSONDecodeError:
                args[key] = value
        else:
            args[key] = value
    return args


def create_app(registry: ServiceNowRegistry, agent: "ChatAgent | None" = None) -> Starlette:
    """Build the REST application around the tool registry."""

    async def run_tool(name: str, **arguments: Any) -> Dict[str, Any]:
        """Run one tool off the event loop and wrap it in the standard envelope."""
        result = await run_in_threadpool(registry.run, name, **arguments)
        ok = result.get("success", True) if isinstance(result, dict) else True
        return {"tool": name, "arguments": arguments, "ok": bool(ok), "result": result}

    def respond(payload: Dict[str, Any]) -> JSONResponse:
        return JSONResponse(payload, status_code=200 if payload["ok"] else 502)

    async def guarded(coro) -> JSONResponse:
        try:
            return respond(await coro)
        except ValidationError as exc:
            return JSONResponse(
                {"ok": False, "error": "Invalid arguments", "details": json.loads(exc.json())}, 400
            )
        except Exception as exc:  # noqa: BLE001 - report upstream failures as 502
            logger.exception("tool failed")
            return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 502)

    def limit_of(request: Request, default: int = 5) -> int:
        try:
            return max(1, int(request.query_params.get("limit", default)))
        except ValueError:
            return default

    # ----- discovery ------------------------------------------------------

    async def index(request: Request) -> JSONResponse:
        base = str(request.base_url).rstrip("/")
        return JSONResponse(
            {
                "name": "ServiceNow REST API",
                "protocol": "REST only - no MCP",
                "instance": registry.config.instance_url,
                "tool_count": len(registry.names),
                "layers": {
                    "named_routes": [
                        base + "/incidents?limit=5",
                        base + "/incidents/{number}",
                        base + "/catalog/items?limit=5",
                        base + "/catalog/items/{sys_id}",
                        base + "/catalog/categories?limit=5",
                        base + "/catalog/recommendations",
                        base + "/groups?limit=5",
                        base + "/users?limit=5",
                        base + "/users/{username}",
                        base + "/users/by-email/{email}",
                        base + "/knowledge/bases?limit=5",
                        base + "/knowledge/articles?limit=5",
                        base + "/knowledge/articles/{article_id}",
                        base + "/changes?limit=5",
                        base + "/changes/{change_id}",
                    ],
                    "all_tools": [
                        base + "/tools",
                        base + "/tools/{name}",
                        base + "/tools/{name}/call?...",
                        "POST " + base + "/tools/{name}",
                    ],
                    "whole_instance": [
                        base + "/stats/{table}?q=          (real count)",
                        base + "/stats/{table}?group_by=priority",
                        base + "/table/{table}?q=&limit=10",
                        base + "/table/{table}/{sys_id}",
                        "POST " + base + "/table/{table}",
                        "PATCH " + base + "/table/{table}/{sys_id}",
                        "DELETE " + base + "/table/{table}/{sys_id}",
                    ],
                },
                "health": base + "/health",
            }
        )

    async def health(request: Request) -> JSONResponse:
        try:
            resp = await run_in_threadpool(
                lambda: requests.get(
                    registry.config.api_url + "/table/incident",
                    params={"sysparm_limit": 1, "sysparm_fields": "number"},
                    headers=registry.auth_manager.get_headers(),
                    timeout=registry.config.timeout,
                )
            )
            reachable, detail = resp.status_code == 200, "HTTP %d" % resp.status_code
        except Exception as exc:  # noqa: BLE001
            reachable, detail = False, str(exc)
        return JSONResponse(
            {
                "ok": reachable,
                "instance": registry.config.instance_url,
                "servicenow": detail,
                "tools_exposed": len(registry.names),
                "protocol": "REST",
            },
            status_code=200 if reachable else 502,
        )

    async def list_tools(request: Request) -> JSONResponse:
        catalog: List[Dict[str, Any]] = registry.catalog()
        if request.query_params.get("read_only") in ("1", "true", "yes"):
            catalog = [entry for entry in catalog if entry["read_only"]]
        needle = (request.query_params.get("q") or "").lower()
        if needle:
            catalog = [
                entry
                for entry in catalog
                if needle in entry["tool"] or needle in entry["description"].lower()
            ]
        if request.query_params.get("schema") in ("0", "false", "no"):
            catalog = [{k: v for k, v in entry.items() if k != "schema"} for entry in catalog]
        return JSONResponse({"ok": True, "count": len(catalog), "tools": catalog})

    async def describe_tool(request: Request) -> JSONResponse:
        name = request.path_params["name"]
        if name not in registry.tool_definitions:
            return JSONResponse({"ok": False, "error": "Unknown tool '%s'" % name}, 404)
        return JSONResponse({"ok": True, **registry.describe(name)})

    # ----- generic tool invocation ----------------------------------------

    async def call_tool_get(request: Request) -> JSONResponse:
        name = request.path_params["name"]
        if name not in registry.tool_definitions:
            return JSONResponse({"ok": False, "error": "Unknown tool '%s'" % name}, 404)
        if not registry.is_read_only(name):
            return JSONResponse(
                {
                    "ok": False,
                    "error": "'%s' changes data; POST /tools/%s with a JSON body instead."
                    % (name, name),
                },
                405,
            )
        args = coerce_query_params(registry.params_model(name), request.query_params)
        return await guarded(run_tool(name, **args))

    async def call_tool_post(request: Request) -> JSONResponse:
        name = request.path_params["name"]
        if name not in registry.tool_definitions:
            return JSONResponse({"ok": False, "error": "Unknown tool '%s'" % name}, 404)
        raw = await request.body()
        if not raw:
            body: Any = {}
        else:
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                return JSONResponse({"ok": False, "error": "Body must be a JSON object"}, 400)
        if not isinstance(body, dict):
            return JSONResponse({"ok": False, "error": "Body must be a JSON object"}, 400)
        return await guarded(run_tool(name, **body))

    # ----- whole-instance Table API ---------------------------------------

    async def table_request(
        method: str,
        table: str,
        sys_id: Optional[str],
        params: Dict[str, Any],
        body: Any,
    ) -> JSONResponse:
        url = registry.config.api_url + "/table/" + table
        if sys_id:
            url = url + "/" + sys_id
        try:
            resp = await run_in_threadpool(
                lambda: requests.request(
                    method,
                    url,
                    params=params or None,
                    json=body,
                    headers=registry.auth_manager.get_headers(),
                    timeout=registry.config.timeout,
                )
            )
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}, 502
            )

        try:
            payload = resp.json() if resp.content else {}
        except json.JSONDecodeError:
            payload = {"raw": resp.text}
        ok = resp.ok
        records = payload.get("result") if isinstance(payload, dict) else payload
        return JSONResponse(
            {
                "ok": ok,
                "table": table,
                "method": method,
                "status": resp.status_code,
                "count": len(records) if isinstance(records, list) else (1 if records else 0),
                "result": records if ok else payload,
            },
            status_code=200 if ok else resp.status_code,
        )

    def table_query_params(request: Request) -> Dict[str, Any]:
        """Map friendly names onto sysparm_* and pass any sysparm_* straight through."""
        qp = request.query_params
        params: Dict[str, Any] = {
            key: value for key, value in qp.items() if key.startswith("sysparm_")
        }
        if qp.get("q") and "sysparm_query" not in params:
            params["sysparm_query"] = qp["q"]
        if qp.get("fields") and "sysparm_fields" not in params:
            params["sysparm_fields"] = qp["fields"]
        if qp.get("offset") and "sysparm_offset" not in params:
            params["sysparm_offset"] = qp["offset"]
        params.setdefault("sysparm_limit", qp.get("limit", "10"))
        params.setdefault("sysparm_display_value", qp.get("display_value", "true"))
        params.setdefault("sysparm_exclude_reference_link", "true")
        return params

    async def table_list(request: Request) -> JSONResponse:
        return await table_request(
            "GET", request.path_params["table"], None, table_query_params(request), None
        )

    async def table_get(request: Request) -> JSONResponse:
        params: Dict[str, Any] = {
            "sysparm_display_value": request.query_params.get("display_value", "true"),
            "sysparm_exclude_reference_link": "true",
        }
        if request.query_params.get("fields"):
            params["sysparm_fields"] = request.query_params["fields"]
        return await table_request(
            "GET", request.path_params["table"], request.path_params["sys_id"], params, None
        )

    async def table_create(request: Request) -> JSONResponse:
        raw = await request.body()
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return JSONResponse({"ok": False, "error": "Body must be a JSON object"}, 400)
        return await table_request("POST", request.path_params["table"], None, {}, body)

    async def table_update(request: Request) -> JSONResponse:
        raw = await request.body()
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return JSONResponse({"ok": False, "error": "Body must be a JSON object"}, 400)
        return await table_request(
            "PATCH", request.path_params["table"], request.path_params["sys_id"], {}, body
        )

    async def table_delete(request: Request) -> JSONResponse:
        return await table_request(
            "DELETE", request.path_params["table"], request.path_params["sys_id"], {}, None
        )

    # ----- named convenience routes ---------------------------------------

    async def incidents(request: Request) -> JSONResponse:
        qp = request.query_params
        args: Dict[str, Any] = {"limit": limit_of(request)}
        if qp.get("q"):
            args["query"] = qp["q"]
        if qp.get("state"):
            args["state"] = qp["state"]
        for http_name, tool_name in (
            ("created_from", "created_after"),
            ("created_to", "created_before"),
            ("updated_from", "updated_after"),
            ("updated_to", "updated_before"),
        ):
            if qp.get(http_name):
                args[tool_name] = qp[http_name]
        sort = qp.get("sort", "created")
        args["order_by"] = INCIDENT_SORTS.get(sort, sort)
        if qp.get("order"):
            args["order_direction"] = qp["order"]
        return await guarded(run_tool("list_incidents", **args))

    async def incident(request: Request) -> JSONResponse:
        return await guarded(
            run_tool("get_incident_by_number", incident_number=request.path_params["number"])
        )

    async def catalog_items(request: Request) -> JSONResponse:
        args: Dict[str, Any] = {"limit": limit_of(request)}
        if request.query_params.get("q"):
            args["query"] = request.query_params["q"]
        if request.query_params.get("category"):
            args["category"] = request.query_params["category"]
        return await guarded(run_tool("list_catalog_items", **args))

    async def catalog_item(request: Request) -> JSONResponse:
        return await guarded(run_tool("get_catalog_item", item_id=request.path_params["sys_id"]))

    async def catalog_categories(request: Request) -> JSONResponse:
        args: Dict[str, Any] = {"limit": limit_of(request)}
        if request.query_params.get("q"):
            args["query"] = request.query_params["q"]
        return await guarded(run_tool("list_catalog_categories", **args))

    async def recommendations(request: Request) -> JSONResponse:
        types = [
            t.strip()
            for t in request.query_params.get("types", DEFAULT_RECOMMENDATION_TYPES).split(",")
            if t.strip()
        ]
        args: Dict[str, Any] = {"recommendation_types": types}
        if request.query_params.get("category"):
            args["category_id"] = request.query_params["category"]
        return await guarded(run_tool("get_optimization_recommendations", **args))

    async def groups(request: Request) -> JSONResponse:
        args: Dict[str, Any] = {"limit": limit_of(request)}
        if request.query_params.get("q"):
            args["query"] = request.query_params["q"]
        return await guarded(run_tool("list_groups", **args))

    async def users(request: Request) -> JSONResponse:
        args: Dict[str, Any] = {"limit": limit_of(request)}
        if request.query_params.get("q"):
            args["query"] = request.query_params["q"]
        return await guarded(run_tool("list_users", **args))

    async def user_by_name(request: Request) -> JSONResponse:
        return await guarded(run_tool("get_user", user_name=request.path_params["username"]))

    async def user_by_email(request: Request) -> JSONResponse:
        return await guarded(run_tool("get_user", email=request.path_params["email"]))

    async def knowledge_bases(request: Request) -> JSONResponse:
        return await guarded(run_tool("list_knowledge_bases", limit=limit_of(request)))

    async def articles(request: Request) -> JSONResponse:
        args: Dict[str, Any] = {"limit": limit_of(request)}
        if request.query_params.get("q"):
            args["query"] = request.query_params["q"]
        return await guarded(run_tool("list_articles", **args))

    async def article(request: Request) -> JSONResponse:
        return await guarded(run_tool("get_article", article_id=request.path_params["article_id"]))

    async def changes(request: Request) -> JSONResponse:
        return await guarded(run_tool("list_change_requests", limit=limit_of(request)))

    async def change(request: Request) -> JSONResponse:
        return await guarded(
            run_tool("get_change_request_details", change_id=request.path_params["change_id"])
        )

    # ----- aggregates ------------------------------------------------------

    async def table_stats(request: Request) -> JSONResponse:
        """
        Real counts via the ServiceNow Aggregate API (/api/now/stats/{table}).

        Without this a caller has to page through records to count them, which
        is slow and inexact. Supports ?group_by= for "how many X by Y".
        """
        table = request.path_params["table"]
        qp = request.query_params
        params: Dict[str, Any] = {"sysparm_count": "true", "sysparm_query": qp.get("q", "")}
        group_by = qp.get("group_by")
        if group_by:
            params["sysparm_group_by"] = group_by
            params["sysparm_display_value"] = qp.get("display_value", "true")

        url = registry.config.api_url + "/stats/" + table
        try:
            resp = await run_in_threadpool(
                lambda: requests.get(
                    url,
                    params=params,
                    headers=registry.auth_manager.get_headers(),
                    timeout=registry.config.timeout,
                )
            )
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 502)

        if not resp.ok:
            return JSONResponse(
                {"ok": False, "table": table, "status": resp.status_code, "error": resp.text[:400]},
                resp.status_code,
            )

        payload = resp.json().get("result", {})
        if group_by:
            groups = []
            for entry in payload if isinstance(payload, list) else [payload]:
                fields = entry.get("groupby_fields") or []
                label = ", ".join(str(f.get("value", "")) for f in fields) or "(none)"
                groups.append({
                    group_by: label,
                    "count": int(entry.get("stats", {}).get("count", 0)),
                })
            groups.sort(key=lambda g: g["count"], reverse=True)
            return JSONResponse(
                {"ok": True, "table": table, "group_by": group_by,
                 "query": qp.get("q", ""), "groups": groups}
            )

        count = int(payload.get("stats", {}).get("count", 0))
        return JSONResponse({"ok": True, "table": table, "query": qp.get("q", ""), "count": count})

    # ----- exported files -------------------------------------------------

    async def export_list(request: Request) -> JSONResponse:
        """The Excel/PDF/CSV files `snow.py export` has written, newest first."""
        base = str(request.base_url).rstrip("/")
        files = []
        if EXPORTS.is_dir():
            for path in EXPORTS.iterdir():
                if path.is_file() and path.suffix.lower() in EXPORT_TYPES:
                    stat = path.stat()
                    files.append({
                        "name": path.name,
                        "format": path.suffix.lstrip("."),
                        "bytes": stat.st_size,
                        "modified": int(stat.st_mtime),
                        "url": f"{base}/exports/{quote(path.name)}",
                    })
        files.sort(key=lambda f: f["modified"], reverse=True)
        return JSONResponse({"ok": True, "count": len(files), "exports": files})

    async def export_download(request: Request) -> Any:
        """Serve one exported file as a download."""
        name = request.path_params["filename"]
        # Resolve inside EXPORTS so a crafted name cannot escape the folder.
        target = (EXPORTS / name).resolve()
        try:
            inside = target.is_relative_to(EXPORTS.resolve())
        except AttributeError:  # Python < 3.9
            inside = str(target).startswith(str(EXPORTS.resolve()))
        if not inside or not target.is_file() or target.suffix.lower() not in EXPORT_TYPES:
            return JSONResponse({"ok": False, "error": f"No export called {name!r}"}, 404)
        return FileResponse(
            target,
            media_type=EXPORT_TYPES[target.suffix.lower()],
            filename=target.name,
            headers={"Content-Disposition": f'attachment; filename="{target.name}"'},
        )

    # ----- files attached to a chat message -------------------------------

    async def upload_create(request: Request) -> JSONResponse:
        """
        Take one file from the composer and keep it for the next message.

        Accepts a multipart form (field "file") or, for clients that would
        rather not build one, a JSON body of {name, data} with base64 data.
        """
        content_type = request.headers.get("content-type", "")
        try:
            if content_type.startswith("multipart/form-data"):
                form = await request.form()
                item = form.get("file")
                if item is None or not hasattr(item, "read"):
                    return JSONResponse({"ok": False, "error": "no file in the form"}, 400)
                name = getattr(item, "filename", "") or "file"
                data = await item.read()
            else:
                body = json.loads(await request.body() or b"{}")
                name = str(body.get("name", "") or "file")
                data = base64.b64decode(body.get("data", "") or "", validate=False)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            return JSONResponse({"ok": False, "error": f"could not read the upload: {exc}"}, 400)

        try:
            record = await run_in_threadpool(uploads.save, name, data)
        except uploads.UploadError as exc:
            # A refusal the user should read, not a server fault.
            return JSONResponse({"ok": False, "error": str(exc)}, 415)
        except OSError as exc:
            logger.exception("upload failed")
            return JSONResponse({"ok": False, "error": f"could not store the file: {exc}"}, 500)

        base = str(request.base_url).rstrip("/")
        record["url"] = f"{base}/uploads/{record['id']}"
        return JSONResponse({"ok": True, "upload": record})

    async def upload_read(request: Request) -> Any:
        """Serve an upload back, so the composer can show an image preview."""
        record = uploads.load(request.path_params["upload_id"])
        if not record:
            return JSONResponse({"ok": False, "error": "no such upload"}, 404)
        return FileResponse(record["path"], media_type=record["media_type"], filename=record["name"])

    # ----- natural-language chat ------------------------------------------

    async def chat_status(request: Request) -> JSONResponse:
        if agent is None:
            return JSONResponse(
                {"available": False, "reason": "Chat is disabled (started with --no-chat)."}
            )
        return JSONResponse(agent.status())

    async def chat(request: Request) -> Any:
        if agent is None:
            return JSONResponse({"ok": False, "error": "Chat is disabled on this server."}, 503)
        try:
            body = json.loads(await request.body() or b"{}")
        except json.JSONDecodeError:
            return JSONResponse({"ok": False, "error": "Body must be a JSON object"}, 400)

        message = str(body.get("message", "")).strip()
        raw_ids = body.get("attachments") or []
        if not isinstance(raw_ids, list):
            return JSONResponse({"ok": False, "error": "attachments must be a list of ids"}, 400)
        if not message and not raw_ids:
            return JSONResponse({"ok": False, "error": "message is required"}, 400)
        if len(message) > 4000:
            return JSONResponse({"ok": False, "error": "message is too long"}, 400)
        session_id = body.get("session_id") or None

        # Load each attachment's bytes here, so the agent is handed content
        # rather than paths it has no tool to open.
        attachments: List[Dict[str, Any]] = []
        for record in uploads.resolve([str(i) for i in raw_ids]):
            data = Path(record["path"]).read_bytes()
            if record["kind"] == "image":
                record["data"] = base64.b64encode(data).decode("ascii")
            else:
                record["text"] = data.decode("utf-8", "replace")
            attachments.append(record)
        if raw_ids and not attachments:
            return JSONResponse({"ok": False, "error": "those attachments have expired"}, 400)

        status = agent.status()
        if not status["available"]:
            return JSONResponse({"ok": False, "error": status["reason"]}, 503)

        async def events():
            async for event in agent.run(
                message, session_id=session_id, attachments=attachments
            ):
                yield "data: " + json.dumps(event) + "\n\n"

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return Starlette(
        routes=[
            Route("/", index),
            Route("/health", health),
            Route("/exports", export_list, methods=["GET"]),
            Route("/exports/{filename}", export_download, methods=["GET"]),
            Route("/uploads", upload_create, methods=["POST"]),
            Route("/uploads/{upload_id}", upload_read, methods=["GET"]),
            # discovery + generic invocation (all tools)
            Route("/chat/status", chat_status, methods=["GET"]),
            Route("/chat", chat, methods=["POST"]),
            Route("/tools", list_tools),
            Route("/tools/{name}", describe_tool, methods=["GET"]),
            Route("/tools/{name}", call_tool_post, methods=["POST"]),
            Route("/tools/{name}/call", call_tool_get, methods=["GET"]),
            # named convenience routes
            Route("/incidents", incidents),
            Route("/incidents/{number}", incident),
            Route("/catalog/items", catalog_items),
            Route("/catalog/items/{sys_id}", catalog_item),
            Route("/catalog/categories", catalog_categories),
            Route("/catalog/recommendations", recommendations),
            Route("/groups", groups),
            Route("/users", users),
            Route("/users/by-email/{email}", user_by_email),
            Route("/users/{username}", user_by_name),
            Route("/knowledge/bases", knowledge_bases),
            Route("/knowledge/articles", articles),
            Route("/knowledge/articles/{article_id}", article),
            Route("/changes", changes),
            Route("/changes/{change_id}", change),
            # whole-instance table access
            Route("/stats/{table}", table_stats, methods=["GET"]),
            Route("/table/{table}", table_list, methods=["GET"]),
            Route("/table/{table}", table_create, methods=["POST"]),
            Route("/table/{table}/{sys_id}", table_get, methods=["GET"]),
            Route("/table/{table}/{sys_id}", table_update, methods=["PATCH", "PUT"]),
            Route("/table/{table}/{sys_id}", table_delete, methods=["DELETE"]),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="ServiceNow REST API server (no MCP)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8095)
    parser.add_argument("--no-chat", action="store_true", help="serve REST only, no /chat")
    parser.add_argument("--allow-write", action="store_true",
                        help="let the chat create and update records (default: read-only)")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    registry = ServiceNowRegistry(config_from_env())
    agent = None
    if not args.no_chat:
        strip_claude_code_env()
        agent = ChatAgent(instance_url=registry.config.instance_url,
                          allow_write=args.allow_write)
        status = agent.status()
        logger.info("Chat: available=%s model=%s auth=%s %s",
                    status["available"], status["model"], status["auth"], status["reason"] or "")
    logger.info(
        "ServiceNow REST API on http://%s:%d - %d tools, open / for the endpoint list",
        args.host,
        args.port,
        len(registry.names),
    )
    uvicorn.run(create_app(registry, agent), host=args.host, port=args.port)


if __name__ == "__main__":
    sys.exit(main())
