"""
ServiceNow REST tool registry.

Replaces the old MCP server module. There is no Model Context Protocol here:
this holds the instance config, the auth manager and the table of tool
functions, and calls those functions directly. Every tool function issues an
HTTPS request to the ServiceNow REST API (/api/now/...).

    registry = ServiceNowRegistry(config_from_env())
    result = registry.run("list_incidents", limit=5)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Union

from pydantic import BaseModel

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.knowledge_base import create_category as create_kb_category_tool
from servicenow_mcp.tools.knowledge_base import list_categories as list_kb_categories_tool
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.utils.tool_utils import get_tool_definitions

logger = logging.getLogger(__name__)

# Tools whose name implies they only read. Used to decide which HTTP verb a
# generated route accepts and to power ?read_only=true filtering on /tools.
READ_PREFIXES = ("list_", "get_", "search_", "find_")


def serialize_tool_output(result: Any, tool_name: str) -> str:
    """Serialize a tool's return value to a JSON string where possible."""
    try:
        if isinstance(result, str):
            try:
                return json.dumps(json.loads(result), indent=2)
            except json.JSONDecodeError:
                return result
        if isinstance(result, dict):
            return json.dumps(result, indent=2)
        if hasattr(result, "model_dump_json"):
            try:
                return result.model_dump_json(indent=2)
            except TypeError:
                return json.dumps(result.model_dump(), indent=2)
        if hasattr(result, "model_dump"):
            return json.dumps(result.model_dump(), indent=2)
        if hasattr(result, "dict"):
            return json.dumps(result.dict(), indent=2)
        logger.warning("Falling back to str() for tool %r (type %s)", tool_name, type(result))
        return str(result)
    except Exception as exc:  # noqa: BLE001 - serialization must never crash a request
        logger.error("Serialization failed for %r: %s", tool_name, exc, exc_info=True)
        return json.dumps({"error": f"Serialization failed for {tool_name}", "details": str(exc)})


def as_json(text: str) -> Any:
    """Best-effort parse of a serialized tool result back into JSON."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


class ServiceNowRegistry:
    """The full ServiceNow tool surface, callable over plain Python / REST."""

    def __init__(self, config: Union[Dict, ServerConfig]):
        self.config = config if isinstance(config, ServerConfig) else ServerConfig(**config)
        self.auth_manager = AuthManager(self.config.auth, self.config.instance_url)
        self.tool_definitions = get_tool_definitions(create_kb_category_tool, list_kb_categories_tool)
        logger.info("Loaded %d ServiceNow REST tools", len(self.tool_definitions))

    # ----- introspection --------------------------------------------------

    @property
    def names(self) -> List[str]:
        return sorted(self.tool_definitions)

    def is_read_only(self, name: str) -> bool:
        return name.startswith(READ_PREFIXES)

    def params_model(self, name: str) -> type[BaseModel]:
        return self.tool_definitions[name][1]

    def describe(self, name: str) -> Dict[str, Any]:
        """One tool's REST contract: description, verb and JSON schema of its body."""
        _impl, params_model, _ret, description, _ser = self.tool_definitions[name]
        read_only = self.is_read_only(name)
        return {
            "tool": name,
            "description": description,
            "read_only": read_only,
            "methods": ["GET", "POST"] if read_only else ["POST"],
            "path": f"/tools/{name}",
            "schema": params_model.model_json_schema(),
        }

    def catalog(self) -> List[Dict[str, Any]]:
        return [self.describe(name) for name in self.names]

    # ----- invocation -----------------------------------------------------

    def run(self, name: str, **arguments: Any) -> Any:
        """Validate arguments, call the tool function, return parsed JSON."""
        impl, params_model, _ret, _description, _ser = self.tool_definitions[name]
        params = params_model(**arguments)
        raw = impl(self.config, self.auth_manager, params)
        return as_json(serialize_tool_output(raw, name))
