"""
ServiceNow REST integration.

Exposes the ServiceNow REST API (/api/now/...) through a tool registry and a
Starlette HTTP server. No Model Context Protocol is involved.
"""

from servicenow_mcp.registry import ServiceNowRegistry

__all__ = ["ServiceNowRegistry"]
