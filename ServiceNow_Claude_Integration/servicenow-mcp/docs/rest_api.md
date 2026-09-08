# ServiceNow REST API reference

Auto-generated from the tool registry by `scripts/generate_docs.py`. **82 operations** (29 read-only, 53 write). Do not edit by hand; re-run the generator instead.

Every endpoint below calls the ServiceNow REST API (`/api/now/...`) from the backend.
There is no Model Context Protocol anywhere in this stack.

Base URL: `http://127.0.0.1:8095` (through the web UI's dev proxy: `/api`).

## Contents

1. [Named routes](#named-routes)
2. [Generic tool endpoints](#generic-tool-endpoints)
3. [Whole-instance Table API](#whole-instance-table-api)
4. [Operations by module](#operations-by-module)

## Named routes

Friendly shapes for the most common reads. These are what the web UI calls.

| Route | Notes |
| --- | --- |
| `GET /health` | Instance reachability and tool count |
| `GET /incidents?limit=5` | Newest first. q, state, sort, order, created_from/to |
| `GET /incidents/{incidentNumber}` | One incident by number |
| `GET /catalog/items?limit=5` | Optional q, category |
| `GET /catalog/items/{itemSysId}` | One catalog item by sys_id |
| `GET /catalog/categories?limit=5` | Optional q |
| `GET /catalog/recommendations` | Optimization analysis |
| `GET /groups?limit=5` | Optional q |
| `GET /users?limit=5` | Optional q |
| `GET /users/{username}` | One user by user_name |
| `GET /users/by-email/{email}` | One user by email |
| `GET /knowledge/bases?limit=5` | Knowledge bases |
| `GET /knowledge/articles?limit=5` | Optional q |
| `GET /knowledge/articles/{articleId}` | One article |
| `GET /changes?limit=5` | Change requests |
| `GET /changes/{changeId}` | One change request |

```bash
curl "http://127.0.0.1:8095/incidents?limit=5&sort=created&order=desc"
curl "http://127.0.0.1:8095/incidents/INC0015571"
```

## Generic tool endpoints

Every operation in this document is reachable generically, without a named route.

| Endpoint | Purpose |
| --- | --- |
| `GET /tools` | The full catalogue with JSON schemas. `?read_only=true`, `?q=`, `?schema=false` |
| `GET /tools/{name}` | One operation's contract: description, methods, schema |
| `GET /tools/{name}/call?...` | Run a **read-only** operation with query parameters |
| `POST /tools/{name}` | Run **any** operation with a JSON body |

Read-only operations accept both forms. Write operations are POST-only; calling
one via `GET .../call` returns `405` with a message pointing at the POST form.

```bash
curl "http://127.0.0.1:8095/tools?read_only=true&schema=false"
curl "http://127.0.0.1:8095/tools/list_incidents/call?limit=3&state=1"
curl -X POST http://127.0.0.1:8095/tools/create_incident \
  -H "Content-Type: application/json" \
  -d '{"short_description": "Laptop will not boot", "urgency": "2"}'
```

All tool responses share one envelope:

```json
{
  "tool": "list_incidents",
  "arguments": { "limit": 3 },
  "ok": true,
  "result": { "success": true, "message": "Found 3 incidents", "incidents": [] }
}
```

`ok` is `false` with HTTP `502` when ServiceNow rejects the call, `400` when the
arguments fail validation (the response then carries a `details` array), and `404`
for an unknown operation name.

## Whole-instance Table API

A thin pass-through to the ServiceNow Table API, so any table the account can
reach is available even when no purpose-built operation exists.

| Endpoint | Purpose |
| --- | --- |
| `GET /table/{table}` | Query a table |
| `GET /table/{table}/{sys_id}` | One record |
| `POST /table/{table}` | Create a record |
| `PATCH /table/{table}/{sys_id}` | Update a record |
| `DELETE /table/{table}/{sys_id}` | Delete a record |

Query parameters: `q` (encoded query), `fields`, `limit`, `offset`,
`display_value`, plus any `sysparm_*` passed straight through.

```bash
curl "http://127.0.0.1:8095/table/incident?q=active=true&fields=number,short_description&limit=5"
curl "http://127.0.0.1:8095/table/sys_user_group?limit=10"
```

Writes depend entirely on the roles of the ServiceNow account in `.env`.
A read-only account receives ServiceNow's own `403`, reported as-is.

## Operations by module

### Incident management

Source: `src/servicenow_mcp/tools/incident_tools.py`

#### `add_comment`

Add a comment to an incident in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/add_comment`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `incident_id` | string | yes | Incident ID or sys_id |
| `comment` | string | yes | Comment to add to the incident |
| `is_work_note` | boolean | no | Whether the comment is a work note (default: `False`) |

#### `create_incident`

Create a new incident in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/create_incident`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `short_description` | string | yes | Short description of the incident |
| `description` | string | no | Detailed description of the incident |
| `caller_id` | string | no | User who reported the incident |
| `category` | string | no | Category of the incident |
| `subcategory` | string | no | Subcategory of the incident |
| `priority` | string | no | Priority of the incident |
| `impact` | string | no | Impact of the incident |
| `urgency` | string | no | Urgency of the incident |
| `assigned_to` | string | no | User assigned to the incident |
| `assignment_group` | string | no | Group assigned to the incident |

#### `get_incident_by_number`

Incident details from ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/get_incident_by_number/call?...` or `POST /tools/get_incident_by_number`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `incident_number` | string | yes | The number of the incident to fetch |

#### `list_incidents`

List incidents from ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/list_incidents/call?...` or `POST /tools/list_incidents`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of incidents to return (default: `10`) |
| `offset` | integer | no | Offset for pagination (default: `0`) |
| `state` | string | no | Filter by incident state |
| `assigned_to` | string | no | Filter by assigned user |
| `category` | string | no | Filter by category |
| `query` | string | no | Search query for incidents |
| `created_after` | string | no | Only incidents created on or after this date/time (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS) |
| `created_before` | string | no | Only incidents created on or before this date/time (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS) |
| `updated_after` | string | no | Only incidents updated on or after this date/time (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS) |
| `updated_before` | string | no | Only incidents updated on or before this date/time (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS) |
| `order_by` | string | no | Sort field: sys_created_on (default), sys_updated_on, opened_at, resolved_at, closed_at, number, priority or state (default: `sys_created_on`) |
| `order_direction` | string | no | Sort direction: desc (newest first, default) or asc (default: `desc`) |

#### `resolve_incident`

Resolve an incident in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/resolve_incident`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `incident_id` | string | yes | Incident ID or sys_id |
| `resolution_code` | string | yes | Resolution code for the incident |
| `resolution_notes` | string | yes | Resolution notes for the incident |

#### `update_incident`

Update an existing incident in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/update_incident`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `incident_id` | string | yes | Incident ID or sys_id |
| `short_description` | string | no | Short description of the incident |
| `description` | string | no | Detailed description of the incident |
| `state` | string | no | State of the incident |
| `category` | string | no | Category of the incident |
| `subcategory` | string | no | Subcategory of the incident |
| `priority` | string | no | Priority of the incident |
| `impact` | string | no | Impact of the incident |
| `urgency` | string | no | Urgency of the incident |
| `assigned_to` | string | no | User assigned to the incident |
| `assignment_group` | string | no | Group assigned to the incident |
| `work_notes` | string | no | Work notes to add to the incident |
| `close_notes` | string | no | Close notes to add to the incident |
| `close_code` | string | no | Close code for the incident |

### Service catalog

Source: `src/servicenow_mcp/tools/catalog_tools.py`

#### `create_catalog_category`

Create a new service catalog category.

- **Methods:** POST
- **Call:** `POST /tools/create_catalog_category`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `title` | string | yes | Title of the category |
| `description` | string | no | Description of the category |
| `parent` | string | no | Parent category sys_id |
| `icon` | string | no | Icon for the category |
| `active` | boolean | no | Whether the category is active (default: `True`) |
| `order` | integer | no | Order of the category |

#### `get_catalog_item`

Get a specific service catalog item.

- **Methods:** GET / POST
- **Call:** `GET /tools/get_catalog_item/call?...` or `POST /tools/get_catalog_item`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `item_id` | string | yes | Catalog item ID or sys_id |

#### `list_catalog_categories`

List service catalog categories.

- **Methods:** GET / POST
- **Call:** `GET /tools/list_catalog_categories/call?...` or `POST /tools/list_catalog_categories`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of categories to return (default: `10`) |
| `offset` | integer | no | Offset for pagination (default: `0`) |
| `query` | string | no | Search query for categories |
| `active` | boolean | no | Whether to only return active categories (default: `True`) |

#### `list_catalog_items`

List service catalog items.

- **Methods:** GET / POST
- **Call:** `GET /tools/list_catalog_items/call?...` or `POST /tools/list_catalog_items`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of catalog items to return (default: `10`) |
| `offset` | integer | no | Offset for pagination (default: `0`) |
| `category` | string | no | Filter by category |
| `query` | string | no | Search query for catalog items |
| `active` | boolean | no | Whether to only return active catalog items (default: `True`) |

#### `move_catalog_items`

Move catalog items to a different category.

- **Methods:** POST
- **Call:** `POST /tools/move_catalog_items`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `item_ids` | array | yes | List of catalog item IDs to move |
| `target_category_id` | string | yes | Target category ID to move items to |

#### `update_catalog_category`

Update an existing service catalog category.

- **Methods:** POST
- **Call:** `POST /tools/update_catalog_category`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `category_id` | string | yes | Category ID or sys_id |
| `title` | string | no | Title of the category |
| `description` | string | no | Description of the category |
| `parent` | string | no | Parent category sys_id |
| `icon` | string | no | Icon for the category |
| `active` | boolean | no | Whether the category is active |
| `order` | integer | no | Order of the category |

### Catalog variables

Source: `src/servicenow_mcp/tools/catalog_variables.py`

#### `create_catalog_item_variable`

Create a new catalog item variable

- **Methods:** POST
- **Call:** `POST /tools/create_catalog_item_variable`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `catalog_item_id` | string | yes | The sys_id of the catalog item |
| `name` | string | yes | The name of the variable (internal name) |
| `type` | string | yes | The type of variable (e.g., string, integer, boolean, reference) |
| `label` | string | yes | The display label for the variable |
| `mandatory` | boolean | no | Whether the variable is required (default: `False`) |
| `help_text` | string | no | Help text to display with the variable |
| `default_value` | string | no | Default value for the variable |
| `description` | string | no | Description of the variable |
| `order` | integer | no | Display order of the variable |
| `reference_table` | string | no | For reference fields, the table to reference |
| `reference_qualifier` | string | no | For reference fields, the query to filter reference options |
| `max_length` | integer | no | Maximum length for string fields |
| `min` | integer | no | Minimum value for numeric fields |
| `max` | integer | no | Maximum value for numeric fields |

#### `list_catalog_item_variables`

List catalog item variables

- **Methods:** GET / POST
- **Call:** `GET /tools/list_catalog_item_variables/call?...` or `POST /tools/list_catalog_item_variables`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `catalog_item_id` | string | yes | The sys_id of the catalog item |
| `include_details` | boolean | no | Whether to include detailed information about each variable (default: `True`) |
| `limit` | integer | no | Maximum number of variables to return |
| `offset` | integer | no | Offset for pagination |

#### `update_catalog_item_variable`

Update a catalog item variable

- **Methods:** POST
- **Call:** `POST /tools/update_catalog_item_variable`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `variable_id` | string | yes | The sys_id of the variable to update |
| `label` | string | no | The display label for the variable |
| `mandatory` | boolean | no | Whether the variable is required |
| `help_text` | string | no | Help text to display with the variable |
| `default_value` | string | no | Default value for the variable |
| `description` | string | no | Description of the variable |
| `order` | integer | no | Display order of the variable |
| `reference_qualifier` | string | no | For reference fields, the query to filter reference options |
| `max_length` | integer | no | Maximum length for string fields |
| `min` | integer | no | Minimum value for numeric fields |
| `max` | integer | no | Maximum value for numeric fields |

### Catalog optimization

Source: `src/servicenow_mcp/tools/catalog_optimization.py`

#### `get_optimization_recommendations`

Get optimization recommendations for the service catalog.

- **Methods:** GET / POST
- **Call:** `GET /tools/get_optimization_recommendations/call?...` or `POST /tools/get_optimization_recommendations`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `recommendation_types` | array | yes |  |
| `category_id` | string | no |  |

#### `update_catalog_item`

Update a service catalog item.

- **Methods:** POST
- **Call:** `POST /tools/update_catalog_item`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `item_id` | string | yes |  |
| `name` | string | no |  |
| `short_description` | string | no |  |
| `description` | string | no |  |
| `category` | string | no |  |
| `price` | string | no |  |
| `active` | boolean | no |  |
| `order` | integer | no |  |

### Change management

Source: `src/servicenow_mcp/tools/change_tools.py`

#### `add_change_task`

Add a task to a change request

- **Methods:** POST
- **Call:** `POST /tools/add_change_task`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `change_id` | string | yes | Change request ID or sys_id |
| `short_description` | string | yes | Short description of the task |
| `description` | string | no | Detailed description of the task |
| `assigned_to` | string | no | User assigned to the task |
| `planned_start_date` | string | no | Planned start date (YYYY-MM-DD HH:MM:SS) |
| `planned_end_date` | string | no | Planned end date (YYYY-MM-DD HH:MM:SS) |

#### `approve_change`

Approve a change request

- **Methods:** POST
- **Call:** `POST /tools/approve_change`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `change_id` | string | yes | Change request ID or sys_id |
| `approver_id` | string | no | ID of the approver |
| `approval_comments` | string | no | Comments for the approval |

#### `create_change_request`

Create a new change request in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/create_change_request`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `short_description` | string | yes | Short description of the change request |
| `description` | string | no | Detailed description of the change request |
| `type` | string | yes | Type of change (normal, standard, emergency) |
| `risk` | string | no | Risk level of the change |
| `impact` | string | no | Impact of the change |
| `category` | string | no | Category of the change |
| `requested_by` | string | no | User who requested the change |
| `assignment_group` | string | no | Group assigned to the change |
| `start_date` | string | no | Planned start date (YYYY-MM-DD HH:MM:SS) |
| `end_date` | string | no | Planned end date (YYYY-MM-DD HH:MM:SS) |

#### `get_change_request_details`

Get detailed information about a specific change request

- **Methods:** GET / POST
- **Call:** `GET /tools/get_change_request_details/call?...` or `POST /tools/get_change_request_details`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `change_id` | string | yes | Change request ID or sys_id |

#### `list_change_requests`

List change requests from ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/list_change_requests/call?...` or `POST /tools/list_change_requests`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of records to return (default: `10`) |
| `offset` | integer | no | Offset to start from (default: `0`) |
| `state` | string | no | Filter by state |
| `type` | string | no | Filter by type (normal, standard, emergency) |
| `category` | string | no | Filter by category |
| `assignment_group` | string | no | Filter by assignment group |
| `timeframe` | string | no | Filter by timeframe (upcoming, in-progress, completed) |
| `query` | string | no | Additional query string |

#### `reject_change`

Reject a change request

- **Methods:** POST
- **Call:** `POST /tools/reject_change`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `change_id` | string | yes | Change request ID or sys_id |
| `approver_id` | string | no | ID of the approver |
| `rejection_reason` | string | yes | Reason for rejection |

#### `submit_change_for_approval`

Submit a change request for approval

- **Methods:** POST
- **Call:** `POST /tools/submit_change_for_approval`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `change_id` | string | yes | Change request ID or sys_id |
| `approval_comments` | string | no | Comments for the approval request |

#### `update_change_request`

Update an existing change request in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/update_change_request`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `change_id` | string | yes | Change request ID or sys_id |
| `short_description` | string | no | Short description of the change request |
| `description` | string | no | Detailed description of the change request |
| `state` | string | no | State of the change request |
| `risk` | string | no | Risk level of the change |
| `impact` | string | no | Impact of the change |
| `category` | string | no | Category of the change |
| `assignment_group` | string | no | Group assigned to the change |
| `start_date` | string | no | Planned start date (YYYY-MM-DD HH:MM:SS) |
| `end_date` | string | no | Planned end date (YYYY-MM-DD HH:MM:SS) |
| `work_notes` | string | no | Work notes to add to the change request |

### Changeset management

Source: `src/servicenow_mcp/tools/changeset_tools.py`

#### `add_file_to_changeset`

Add a file to a changeset in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/add_file_to_changeset`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `changeset_id` | string | yes | Changeset ID or sys_id |
| `file_path` | string | yes | Path of the file to add |
| `file_content` | string | yes | Content of the file |

#### `commit_changeset`

Commit a changeset in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/commit_changeset`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `changeset_id` | string | yes | Changeset ID or sys_id |
| `commit_message` | string | no | Commit message |

#### `create_changeset`

Create a new changeset in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/create_changeset`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | string | yes | Name of the changeset |
| `description` | string | no | Description of the changeset |
| `application` | string | yes | Application the changeset belongs to |
| `developer` | string | no | Developer responsible for the changeset |

#### `get_changeset_details`

Get detailed information about a specific changeset

- **Methods:** GET / POST
- **Call:** `GET /tools/get_changeset_details/call?...` or `POST /tools/get_changeset_details`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `changeset_id` | string | yes | Changeset ID or sys_id |

#### `list_changesets`

List changesets from ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/list_changesets/call?...` or `POST /tools/list_changesets`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of records to return (default: `10`) |
| `offset` | integer | no | Offset to start from (default: `0`) |
| `state` | string | no | Filter by state |
| `application` | string | no | Filter by application |
| `developer` | string | no | Filter by developer |
| `timeframe` | string | no | Filter by timeframe (recent, last_week, last_month) |
| `query` | string | no | Additional query string |

#### `publish_changeset`

Publish a changeset in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/publish_changeset`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `changeset_id` | string | yes | Changeset ID or sys_id |
| `publish_notes` | string | no | Notes for publishing |

#### `update_changeset`

Update an existing changeset in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/update_changeset`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `changeset_id` | string | yes | Changeset ID or sys_id |
| `name` | string | no | Name of the changeset |
| `description` | string | no | Description of the changeset |
| `state` | string | no | State of the changeset |
| `developer` | string | no | Developer responsible for the changeset |

### Knowledge base

Source: `src/servicenow_mcp/tools/knowledge_base.py`

#### `create_article`

Create a new knowledge article

- **Methods:** POST
- **Call:** `POST /tools/create_article`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `title` | string | yes | Title of the article |
| `text` | string | yes | The main body text for the article. Field supports html formatting and wiki markup based on the article_type. HTML is the default. |
| `short_description` | string | yes | Short description of the article |
| `knowledge_base` | string | yes | The knowledge base to create the article in |
| `category` | string | yes | Category for the article |
| `keywords` | string | no | Keywords for search |
| `article_type` | string | no | The type of article. Options are 'text' or 'wiki'. text lets the text field support html formatting. wiki lets the text field support wiki markup. (default: `html`) |

#### `create_category`

Create a new category in a knowledge base

- **Methods:** POST
- **Call:** `POST /tools/create_category`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `title` | string | yes | Title of the category |
| `description` | string | no | Description of the category |
| `knowledge_base` | string | yes | The knowledge base to create the category in |
| `parent_category` | string | no | Parent category (if creating a subcategory). Sys_id refering to the parent category or sys_id of the parent table. |
| `parent_table` | string | no | Parent table (if creating a subcategory). Sys_id refering to the table where the parent category is defined. |
| `active` | boolean | no | Whether the category is active (default: `True`) |

#### `create_knowledge_base`

Create a new knowledge base in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/create_knowledge_base`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `title` | string | yes | Title of the knowledge base |
| `description` | string | no | Description of the knowledge base |
| `owner` | string | no | The specified admin user or group |
| `managers` | string | no | Users who can manage this knowledge base |
| `publish_workflow` | string | no | Publication workflow (default: `Knowledge - Instant Publish`) |
| `retire_workflow` | string | no | Retirement workflow (default: `Knowledge - Instant Retire`) |

#### `get_article`

Get a specific knowledge article by ID

- **Methods:** GET / POST
- **Call:** `GET /tools/get_article/call?...` or `POST /tools/get_article`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `article_id` | string | yes | ID of the article to get |

#### `list_articles`

List knowledge articles

- **Methods:** GET / POST
- **Call:** `GET /tools/list_articles/call?...` or `POST /tools/list_articles`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of articles to return (default: `10`) |
| `offset` | integer | no | Offset for pagination (default: `0`) |
| `knowledge_base` | string | no | Filter by knowledge base |
| `category` | string | no | Filter by category |
| `query` | string | no | Search query for articles |
| `workflow_state` | string | no | Filter by workflow state |

#### `list_categories`

List categories in a knowledge base

- **Methods:** GET / POST
- **Call:** `GET /tools/list_categories/call?...` or `POST /tools/list_categories`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `knowledge_base` | string | no | Filter by knowledge base ID |
| `parent_category` | string | no | Filter by parent category ID |
| `limit` | integer | no | Maximum number of categories to return (default: `10`) |
| `offset` | integer | no | Offset for pagination (default: `0`) |
| `active` | boolean | no | Filter by active status |
| `query` | string | no | Search query for categories |

#### `list_knowledge_bases`

List knowledge bases from ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/list_knowledge_bases/call?...` or `POST /tools/list_knowledge_bases`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of knowledge bases to return (default: `10`) |
| `offset` | integer | no | Offset for pagination (default: `0`) |
| `active` | boolean | no | Filter by active status |
| `query` | string | no | Search query for knowledge bases |

#### `publish_article`

Publish a knowledge article

- **Methods:** POST
- **Call:** `POST /tools/publish_article`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `article_id` | string | yes | ID of the article to publish |
| `workflow_state` | string | no | The workflow state to set (default: `published`) |
| `workflow_version` | string | no | The workflow version to use |

#### `update_article`

Update an existing knowledge article

- **Methods:** POST
- **Call:** `POST /tools/update_article`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `article_id` | string | yes | ID of the article to update |
| `title` | string | no | Updated title of the article |
| `text` | string | no | Updated main body text for the article. Field supports html formatting and wiki markup based on the article_type. HTML is the default. |
| `short_description` | string | no | Updated short description |
| `category` | string | no | Updated category for the article |
| `keywords` | string | no | Updated keywords for search |

### User and group management

Source: `src/servicenow_mcp/tools/user_tools.py`

#### `add_group_members`

Add members to an existing group in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/add_group_members`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `group_id` | string | yes | Group ID or sys_id |
| `members` | array | yes | List of user sys_ids or usernames to add as members |

#### `create_group`

Create a new group in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/create_group`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | string | yes | Name of the group |
| `description` | string | no | Description of the group |
| `manager` | string | no | Manager of the group (sys_id or username) |
| `parent` | string | no | Parent group (sys_id or name) |
| `type` | string | no | Type of the group |
| `email` | string | no | Email address for the group |
| `members` | array | no | List of user sys_ids or usernames to add as members |
| `active` | boolean | no | Whether the group is active (default: `True`) |

#### `create_user`

Create a new user in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/create_user`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `user_name` | string | yes | Username for the user |
| `first_name` | string | yes | First name of the user |
| `last_name` | string | yes | Last name of the user |
| `email` | string | yes | Email address of the user |
| `title` | string | no | Job title of the user |
| `department` | string | no | Department the user belongs to |
| `manager` | string | no | Manager of the user (sys_id or username) |
| `roles` | array | no | Roles to assign to the user |
| `phone` | string | no | Phone number of the user |
| `mobile_phone` | string | no | Mobile phone number of the user |
| `location` | string | no | Location of the user |
| `password` | string | no | Password for the user account |
| `active` | boolean | no | Whether the user account is active (default: `True`) |

#### `get_user`

Get a specific user in ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/get_user/call?...` or `POST /tools/get_user`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `user_id` | string | no | User ID or sys_id |
| `user_name` | string | no | Username of the user |
| `email` | string | no | Email address of the user |

#### `list_groups`

List groups from ServiceNow with optional filtering

- **Methods:** GET / POST
- **Call:** `GET /tools/list_groups/call?...` or `POST /tools/list_groups`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of groups to return (default: `10`) |
| `offset` | integer | no | Offset for pagination (default: `0`) |
| `active` | boolean | no | Filter by active status |
| `query` | string | no | Case-insensitive search term that matches against group name or description fields. Uses ServiceNow's LIKE operator for partial matching. |
| `type` | string | no | Filter by group type |

#### `list_users`

List users in ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/list_users/call?...` or `POST /tools/list_users`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of users to return (default: `10`) |
| `offset` | integer | no | Offset for pagination (default: `0`) |
| `active` | boolean | no | Filter by active status |
| `department` | string | no | Filter by department |
| `query` | string | no | Case-insensitive search term that matches against name, username, or email fields. Uses ServiceNow's LIKE operator for partial matching. |

#### `remove_group_members`

Remove members from an existing group in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/remove_group_members`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `group_id` | string | yes | Group ID or sys_id |
| `members` | array | yes | List of user sys_ids or usernames to remove as members |

#### `update_group`

Update an existing group in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/update_group`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `group_id` | string | yes | Group ID or sys_id to update |
| `name` | string | no | Name of the group |
| `description` | string | no | Description of the group |
| `manager` | string | no | Manager of the group (sys_id or username) |
| `parent` | string | no | Parent group (sys_id or name) |
| `type` | string | no | Type of the group |
| `email` | string | no | Email address for the group |
| `active` | boolean | no | Whether the group is active |

#### `update_user`

Update an existing user in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/update_user`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `user_id` | string | yes | User ID or sys_id to update |
| `user_name` | string | no | Username for the user |
| `first_name` | string | no | First name of the user |
| `last_name` | string | no | Last name of the user |
| `email` | string | no | Email address of the user |
| `title` | string | no | Job title of the user |
| `department` | string | no | Department the user belongs to |
| `manager` | string | no | Manager of the user (sys_id or username) |
| `roles` | array | no | Roles to assign to the user |
| `phone` | string | no | Phone number of the user |
| `mobile_phone` | string | no | Mobile phone number of the user |
| `location` | string | no | Location of the user |
| `password` | string | no | Password for the user account |
| `active` | boolean | no | Whether the user account is active |

### Workflow management

Source: `src/servicenow_mcp/tools/workflow_tools.py`

#### `activate_workflow`

Activate a workflow in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/activate_workflow`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `workflow_id` | string | yes | Workflow ID or sys_id |

#### `add_workflow_activity`

Add a new activity to a workflow in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/add_workflow_activity`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `workflow_version_id` | string | yes | Workflow version ID |
| `name` | string | yes | Name of the activity |
| `description` | string | no | Description of the activity |
| `activity_type` | string | yes | Type of activity (e.g., 'approval', 'task', 'notification') |
| `attributes` | object | no | Additional attributes for the activity |

#### `create_workflow`

Create a new workflow in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/create_workflow`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | string | yes | Name of the workflow |
| `description` | string | no | Description of the workflow |
| `table` | string | no | Table the workflow applies to |
| `active` | boolean | no | Whether the workflow is active (default: `True`) |
| `attributes` | object | no | Additional attributes for the workflow |

#### `deactivate_workflow`

Deactivate a workflow in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/deactivate_workflow`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `workflow_id` | string | yes | Workflow ID or sys_id |

#### `delete_workflow_activity`

Delete an activity from a workflow

- **Methods:** POST
- **Call:** `POST /tools/delete_workflow_activity`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `activity_id` | string | yes | Activity ID or sys_id |

#### `get_workflow_activities`

Get activities for a specific workflow

- **Methods:** GET / POST
- **Call:** `GET /tools/get_workflow_activities/call?...` or `POST /tools/get_workflow_activities`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `workflow_id` | string | yes | Workflow ID or sys_id |
| `version` | string | no | Specific version to get activities for |

#### `get_workflow_details`

Get detailed information about a specific workflow

- **Methods:** GET / POST
- **Call:** `GET /tools/get_workflow_details/call?...` or `POST /tools/get_workflow_details`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `workflow_id` | string | yes | Workflow ID or sys_id |
| `include_versions` | boolean | no | Include workflow versions (default: `False`) |

#### `list_workflow_versions`

List workflow versions from ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/list_workflow_versions/call?...` or `POST /tools/list_workflow_versions`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `workflow_id` | string | yes | Workflow ID or sys_id |
| `limit` | integer | no | Maximum number of records to return (default: `10`) |
| `offset` | integer | no | Offset to start from (default: `0`) |

#### `list_workflows`

List workflows from ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/list_workflows/call?...` or `POST /tools/list_workflows`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of records to return (default: `10`) |
| `offset` | integer | no | Offset to start from (default: `0`) |
| `active` | boolean | no | Filter by active status |
| `name` | string | no | Filter by name (contains) |
| `query` | string | no | Additional query string |

#### `reorder_workflow_activities`

Reorder activities in a workflow

- **Methods:** POST
- **Call:** `POST /tools/reorder_workflow_activities`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `workflow_id` | string | yes | Workflow ID or sys_id |
| `activity_ids` | array | yes | List of activity IDs in the desired order |

#### `update_workflow`

Update an existing workflow in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/update_workflow`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `workflow_id` | string | yes | Workflow ID or sys_id |
| `name` | string | no | Name of the workflow |
| `description` | string | no | Description of the workflow |
| `table` | string | no | Table the workflow applies to |
| `active` | boolean | no | Whether the workflow is active |
| `attributes` | object | no | Additional attributes for the workflow |

#### `update_workflow_activity`

Update an existing activity in a workflow

- **Methods:** POST
- **Call:** `POST /tools/update_workflow_activity`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `activity_id` | string | yes | Activity ID or sys_id |
| `name` | string | no | Name of the activity |
| `description` | string | no | Description of the activity |
| `attributes` | object | no | Additional attributes for the activity |

### Script includes

Source: `src/servicenow_mcp/tools/script_include_tools.py`

#### `create_script_include`

Create a new script include in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/create_script_include`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | string | yes | Name of the script include |
| `script` | string | yes | Script content |
| `description` | string | no | Description of the script include |
| `api_name` | string | no | API name of the script include |
| `client_callable` | boolean | no | Whether the script include is client callable (default: `False`) |
| `active` | boolean | no | Whether the script include is active (default: `True`) |
| `access` | string | no | Access level of the script include (default: `package_private`) |

#### `delete_script_include`

Delete a script include in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/delete_script_include`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `script_include_id` | string | yes | Script include ID or name |

#### `get_script_include`

Get a specific script include from ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/get_script_include/call?...` or `POST /tools/get_script_include`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `script_include_id` | string | yes | Script include ID or name |

#### `list_script_includes`

List script includes from ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/list_script_includes/call?...` or `POST /tools/list_script_includes`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of script includes to return (default: `10`) |
| `offset` | integer | no | Offset for pagination (default: `0`) |
| `active` | boolean | no | Filter by active status |
| `client_callable` | boolean | no | Filter by client callable status |
| `query` | string | no | Search query for script includes |

#### `update_script_include`

Update an existing script include in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/update_script_include`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `script_include_id` | string | yes | Script include ID or name |
| `script` | string | no | Script content |
| `description` | string | no | Description of the script include |
| `api_name` | string | no | API name of the script include |
| `client_callable` | boolean | no | Whether the script include is client callable |
| `active` | boolean | no | Whether the script include is active |
| `access` | string | no | Access level of the script include |

### Agile: stories

Source: `src/servicenow_mcp/tools/story_tools.py`

#### `create_story`

Create a new story in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/create_story`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `short_description` | string | yes | Short description of the story |
| `acceptance_criteria` | string | yes | Acceptance criteria for the story |
| `description` | string | no | Detailed description of the story |
| `state` | string | no | State of story (-6 is Draft,-7 is Ready for Testing,-8 is Testing,1 is Ready, 2 is Work in progress, 3 is Complete, 4 is Cancelled) |
| `assignment_group` | string | no | Group assigned to the story |
| `story_points` | integer | no | Points value for the story (default: `10`) |
| `assigned_to` | string | no | User assigned to the story |
| `epic` | string | no | Epic that the story belongs to. It requires the System ID of the epic. |
| `project` | string | no | Project that the story belongs to. It requires the System ID of the project. |
| `work_notes` | string | no | Work notes to add to the story. Used for adding notes and comments to a story |

#### `create_story_dependency`

Create a dependency between two stories in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/create_story_dependency`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `dependent_story` | string | yes | Sys_id of the dependent story is required |
| `prerequisite_story` | string | yes | Sys_id that this story depends on is required |

#### `delete_story_dependency`

Delete a story dependency in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/delete_story_dependency`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `dependency_id` | string | yes | Sys_id of the dependency is required |

#### `list_stories`

List stories from ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/list_stories/call?...` or `POST /tools/list_stories`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of records to return (default: `10`) |
| `offset` | integer | no | Offset to start from (default: `0`) |
| `state` | string | no | Filter by state |
| `assignment_group` | string | no | Filter by assignment group |
| `timeframe` | string | no | Filter by timeframe (upcoming, in-progress, completed) |
| `query` | string | no | Additional query string |

#### `list_story_dependencies`

List story dependencies from ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/list_story_dependencies/call?...` or `POST /tools/list_story_dependencies`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of records to return (default: `10`) |
| `offset` | integer | no | Offset to start from (default: `0`) |
| `query` | string | no | Additional query string |
| `dependent_story` | string | no | Sys_id of the dependent story is required |
| `prerequisite_story` | string | no | Sys_id that this story depends on is required |

#### `update_story`

Update an existing story in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/update_story`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `story_id` | string | yes | Story IDNumber or sys_id. You will need to fetch the story to get the sys_id if you only have the story number |
| `short_description` | string | no | Short description of the story |
| `acceptance_criteria` | string | no | Acceptance criteria for the story |
| `description` | string | no | Detailed description of the story |
| `state` | string | no | State of story (-6 is Draft,-7 is Ready for Testing,-8 is Testing,1 is Ready, 2 is Work in progress, 3 is Complete, 4 is Cancelled) |
| `assignment_group` | string | no | Group assigned to the story |
| `story_points` | integer | no | Points value for the story |
| `assigned_to` | string | no | User assigned to the story |
| `epic` | string | no | Epic that the story belongs to. It requires the System ID of the epic. |
| `project` | string | no | Project that the story belongs to. It requires the System ID of the project. |
| `work_notes` | string | no | Work notes to add to the story. Used for adding notes and comments to a story |

### Agile: epics

Source: `src/servicenow_mcp/tools/epic_tools.py`

#### `create_epic`

Create a new epic in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/create_epic`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `short_description` | string | yes | Short description of the epic |
| `description` | string | no | Detailed description of the epic |
| `priority` | string | no | Priority of epic (1 is Critical, 2 is High, 3 is Moderate, 4 is Low, 5 is Planning) |
| `state` | string | no | State of story (-6 is Draft,1 is Ready,2 is Work in progress, 3 is Complete, 4 is Cancelled) |
| `assignment_group` | string | no | Group assigned to the epic |
| `assigned_to` | string | no | User assigned to the epic |
| `work_notes` | string | no | Work notes to add to the epic. Used for adding notes and comments to an epic |

#### `list_epics`

List epics from ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/list_epics/call?...` or `POST /tools/list_epics`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of records to return (default: `10`) |
| `offset` | integer | no | Offset to start from (default: `0`) |
| `priority` | string | no | Filter by priority |
| `assignment_group` | string | no | Filter by assignment group |
| `timeframe` | string | no | Filter by timeframe (upcoming, in-progress, completed) |
| `query` | string | no | Additional query string |

#### `update_epic`

Update an existing epic in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/update_epic`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `epic_id` | string | yes | Epic ID or sys_id |
| `short_description` | string | no | Short description of the epic |
| `description` | string | no | Detailed description of the epic |
| `priority` | string | no | Priority of epic (1 is Critical, 2 is High, 3 is Moderate, 4 is Low, 5 is Planning) |
| `state` | string | no | State of story (-6 is Draft,1 is Ready,2 is Work in progress, 3 is Complete, 4 is Cancelled) |
| `assignment_group` | string | no | Group assigned to the epic |
| `assigned_to` | string | no | User assigned to the epic |
| `work_notes` | string | no | Work notes to add to the epic. Used for adding notes and comments to an epic |

### Agile: scrum tasks

Source: `src/servicenow_mcp/tools/scrum_task_tools.py`

#### `create_scrum_task`

Create a new scrum task in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/create_scrum_task`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `story` | string | yes | Short description of the story. It requires the System ID of the story. |
| `short_description` | string | yes | Short description of the scrum task |
| `priority` | string | no | Priority of scrum task (1 is Critical, 2 is High, 3 is Moderate, 4 is Low) |
| `planned_hours` | integer | no | Planned hours for the scrum task |
| `remaining_hours` | integer | no | Remaining hours for the scrum task |
| `hours` | integer | no | Actual Hours for the scrum task |
| `description` | string | no | Detailed description of the scrum task |
| `type` | string | no | Type of scrum task (1 is Analysis, 2 is Coding, 3 is Documentation, 4 is Testing) |
| `state` | string | no | State of scrum task (-6 is Draft,1 is Ready, 2 is Work in progress, 3 is Complete, 4 is Cancelled) |
| `assignment_group` | string | no | Group assigned to the scrum task |
| `assigned_to` | string | no | User assigned to the scrum task |
| `work_notes` | string | no | Work notes to add to the scrum task |

#### `list_scrum_tasks`

List scrum tasks from ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/list_scrum_tasks/call?...` or `POST /tools/list_scrum_tasks`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of records to return (default: `10`) |
| `offset` | integer | no | Offset to start from (default: `0`) |
| `state` | string | no | Filter by state |
| `assignment_group` | string | no | Filter by assignment group |
| `timeframe` | string | no | Filter by timeframe (upcoming, in-progress, completed) |
| `query` | string | no | Additional query string |

#### `update_scrum_task`

Update an existing scrum task in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/update_scrum_task`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `scrum_task_id` | string | yes | Scrum Task ID or sys_id |
| `short_description` | string | no | Short description of the scrum task |
| `priority` | string | no | Priority of scrum task (1 is Critical, 2 is High, 3 is Moderate, 4 is Low) |
| `planned_hours` | integer | no | Planned hours for the scrum task |
| `remaining_hours` | integer | no | Remaining hours for the scrum task |
| `hours` | integer | no | Actual Hours for the scrum task |
| `description` | string | no | Detailed description of the scrum task |
| `type` | string | no | Type of scrum task (1 is Analysis, 2 is Coding, 3 is Documentation, 4 is Testing) |
| `state` | string | no | State of scrum task (-6 is Draft,1 is Ready, 2 is Work in progress, 3 is Complete, 4 is Cancelled) |
| `assignment_group` | string | no | Group assigned to the scrum task |
| `assigned_to` | string | no | User assigned to the scrum task |
| `work_notes` | string | no | Work notes to add to the scrum task |

### Agile: projects

Source: `src/servicenow_mcp/tools/project_tools.py`

#### `create_project`

Create a new project in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/create_project`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `short_description` | string | yes | Project name of the project |
| `description` | string | no | Detailed description of the project |
| `status` | string | no | Status of the project (green, yellow, red) |
| `state` | string | no | State of project (-5 is Pending,1 is Open, 2 is Work in progress, 3 is Closed Complete, 4 is Closed Incomplete, 5 is Closed Skipped) |
| `project_manager` | string | no | Project manager for the project |
| `percentage_complete` | integer | no | Percentage complete for the project |
| `assignment_group` | string | no | Group assigned to the project |
| `assigned_to` | string | no | User assigned to the project |
| `start_date` | string | no | Start date for the project |
| `end_date` | string | no | End date for the project |

#### `list_projects`

List projects from ServiceNow

- **Methods:** GET / POST
- **Call:** `GET /tools/list_projects/call?...` or `POST /tools/list_projects`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `limit` | integer | no | Maximum number of records to return (default: `10`) |
| `offset` | integer | no | Offset to start from (default: `0`) |
| `state` | string | no | Filter by state |
| `assignment_group` | string | no | Filter by assignment group |
| `timeframe` | string | no | Filter by timeframe (upcoming, in-progress, completed) |
| `query` | string | no | Additional query string |

#### `update_project`

Update an existing project in ServiceNow

- **Methods:** POST
- **Call:** `POST /tools/update_project`

| Parameter | Type | Required | Notes |
| --- | --- | --- | --- |
| `project_id` | string | yes | Project ID or sys_id |
| `short_description` | string | no | Project name of the project |
| `description` | string | no | Detailed description of the project |
| `status` | string | no | Status of the project (green, yellow, red) |
| `state` | string | no | State of project (-5 is Pending,1 is Open, 2 is Work in progress, 3 is Closed Complete, 4 is Closed Incomplete, 5 is Closed Skipped) |
| `project_manager` | string | no | Project manager for the project |
| `percentage_complete` | integer | no | Percentage complete for the project |
| `assignment_group` | string | no | Group assigned to the project |
| `assigned_to` | string | no | User assigned to the project |
| `start_date` | string | no | Start date for the project |
| `end_date` | string | no | End date for the project |

