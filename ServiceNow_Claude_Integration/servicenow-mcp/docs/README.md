# ServiceNow REST API documentation

This backend exposes a ServiceNow instance over plain HTTP. Every endpoint calls
the ServiceNow REST API (`/api/now/...`) directly. There is no Model Context
Protocol in this stack.

Start the backend first:

```bash
.venv\Scripts\python.exe scripts\rest_api.py     # http://127.0.0.1:8095
```

Then `GET /` for a live endpoint list, or `GET /health` to confirm the instance
is reachable.

## Start here

| Document | What it covers |
| --- | --- |
| **[rest_api.md](rest_api.md)** | **The complete reference.** All 82 operations with parameters and JSON schemas, the named routes, and the whole-instance Table API. Generated from the code. |
| [../postman/ServiceNow-REST-API.postman_collection.json](../postman/ServiceNow-REST-API.postman_collection.json) | Postman collection covering every endpoint. Import it and set `baseUrl`. |

## By topic

These explain the ServiceNow concepts behind the endpoints — field meanings,
states, workflows and common tasks.

| Document | Topic |
| --- | --- |
| [incident_management.md](incident_management.md) | Incidents: list, get, create, update, comment, resolve |
| [catalog.md](catalog.md) | Service catalog items and categories |
| [catalog_variables.md](catalog_variables.md) | Catalog item variables (form fields) |
| [catalog_optimization_plan.md](catalog_optimization_plan.md) | Catalog optimization analysis |
| [change_management.md](change_management.md) | Change requests, tasks and approvals |
| [changeset_management.md](changeset_management.md) | Changesets (update sets) |
| [knowledge_base.md](knowledge_base.md) | Knowledge bases, categories and articles |
| [user_management.md](user_management.md) | Users and groups |
| [workflow_management.md](workflow_management.md) | Workflows, versions and activities |

## The three ways to call anything

```bash
# 1. Named route - the friendly shape the web UI uses
curl "http://127.0.0.1:8095/incidents?limit=5"

# 2. Any of the 82 operations, by name
curl "http://127.0.0.1:8095/tools/list_incidents/call?limit=5"
curl -X POST http://127.0.0.1:8095/tools/create_incident \
  -H "Content-Type: application/json" \
  -d '{"short_description": "Laptop will not boot"}'

# 3. Any table in the instance
curl "http://127.0.0.1:8095/table/incident?q=active=true&fields=number,state&limit=5"
```

Discover what is available at runtime:

```bash
curl "http://127.0.0.1:8095/tools?schema=false"       # every operation
curl "http://127.0.0.1:8095/tools?read_only=true"     # reads only
curl "http://127.0.0.1:8095/tools/list_incidents"     # one operation's schema
```

## Regenerating the reference

`rest_api.md` and the Postman collection are generated from the tool registry,
so they cannot drift from the code. After adding or changing an operation:

```bash
.venv\Scripts\python.exe scripts\generate_docs.py
```

## A note on writes

Read endpoints work with any account. Write endpoints exist for every operation,
but whether they succeed depends entirely on the roles of the ServiceNow account
in `.env`. A read-only account receives ServiceNow's own `403 Forbidden`, which
is passed back unchanged rather than hidden.
