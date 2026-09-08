# Incident Management

This document describes the incident management functionality provided by the ServiceNow REST API.

> **How to call these operations**
>
> Every operation on this page is an HTTP endpoint on the local REST API
> (`http://127.0.0.1:8095` by default, or `/api` through the web UI's dev proxy).
> Reads accept query parameters, writes take a JSON body:
>
> ```bash
> curl "http://127.0.0.1:8095/tools/<operation>/call?limit=5"          # read
> curl -X POST http://127.0.0.1:8095/tools/<operation> \
>   -H "Content-Type: application/json" -d '{"field": "value"}'        # write
> ```
>
> `GET /tools/<operation>` returns the full JSON schema for its parameters.
> See [rest_api.md](rest_api.md) for the complete generated reference.

## Overview

The incident management module lets you work with ServiceNow incidents over REST. It provides endpoints for querying incident data and for creating, updating, and resolving incidents.

## Read operations

### List Incidents

Retrieves a list of incidents from ServiceNow.

**Operation:** `list_incidents`

**Parameters:**
- `limit` (int, default: 10): Maximum number of incidents to return
- `offset` (int, default: 0): Offset for pagination
- `state` (string, optional): Filter by incident state
- `assigned_to` (string, optional): Filter by assigned user
- `category` (string, optional): Filter by category
- `query` (string, optional): Search query for incidents

**Example:**
```bash
curl "http://127.0.0.1:8095/tools/list_incidents/call?limit=5&state=1&category=Software"
```

### Get Incident

Retrieves a specific incident from ServiceNow by ID or number.

**Operation:** `get_incident_by_number`

**Parameters:**
- `incident_id` (string): Incident ID or sys_id

**Example:**
```bash
curl "http://127.0.0.1:8095/incidents/INC0010001"
```

## Tools

### Create Incident

Creates a new incident in ServiceNow.

**Operation:** `create_incident`

**Parameters:**
- `short_description` (string, required): Short description of the incident
- `description` (string, optional): Detailed description of the incident
- `caller_id` (string, optional): User who reported the incident
- `category` (string, optional): Category of the incident
- `subcategory` (string, optional): Subcategory of the incident
- `priority` (string, optional): Priority of the incident
- `impact` (string, optional): Impact of the incident
- `urgency` (string, optional): Urgency of the incident
- `assigned_to` (string, optional): User assigned to the incident
- `assignment_group` (string, optional): Group assigned to the incident

**Example:**
```bash
curl -X POST http://127.0.0.1:8095/tools/create_incident \
  -H "Content-Type: application/json" \
  -d '{
    "short_description": "Email service is down",
    "description": "Users are unable to send or receive emails.",
    "category": "Software",
    "priority": "1"
  }'
```

### Update Incident

Updates an existing incident in ServiceNow.

**Operation:** `update_incident`

**Parameters:**
- `incident_id` (string, required): Incident ID or sys_id
- `short_description` (string, optional): Short description of the incident
- `description` (string, optional): Detailed description of the incident
- `state` (string, optional): State of the incident
- `category` (string, optional): Category of the incident
- `subcategory` (string, optional): Subcategory of the incident
- `priority` (string, optional): Priority of the incident
- `impact` (string, optional): Impact of the incident
- `urgency` (string, optional): Urgency of the incident
- `assigned_to` (string, optional): User assigned to the incident
- `assignment_group` (string, optional): Group assigned to the incident
- `work_notes` (string, optional): Work notes to add to the incident
- `close_notes` (string, optional): Close notes to add to the incident
- `close_code` (string, optional): Close code for the incident

**Example:**
```bash
curl -X POST http://127.0.0.1:8095/tools/update_incident \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "INC0010001",
    "priority": "2",
    "assigned_to": "admin",
    "work_notes": "Investigating the issue."
  }'
```

### Add Comment

Adds a comment to an incident in ServiceNow.

**Operation:** `add_comment`

**Parameters:**
- `incident_id` (string, required): Incident ID or sys_id
- `comment` (string, required): Comment to add to the incident
- `is_work_note` (boolean, default: false): Whether the comment is a work note

**Example:**
```bash
curl -X POST http://127.0.0.1:8095/tools/add_comment \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "INC0010001",
    "comment": "The issue is being investigated by the network team.",
    "is_work_note": "true"
  }'
```

### Resolve Incident

Resolves an incident in ServiceNow.

**Operation:** `resolve_incident`

**Parameters:**
- `incident_id` (string, required): Incident ID or sys_id
- `resolution_code` (string, required): Resolution code for the incident
- `resolution_notes` (string, required): Resolution notes for the incident

**Example:**
```bash
curl -X POST http://127.0.0.1:8095/tools/resolve_incident \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "INC0010001",
    "resolution_code": "Solved (Permanently)",
    "resolution_notes": "The email service has been restored."
  }'
```

## State Values

ServiceNow incident states are represented by numeric values:

- `1`: New
- `2`: In Progress
- `3`: On Hold
- `4`: Resolved
- `5`: Closed
- `6`: Canceled

## Priority Values

ServiceNow incident priorities are represented by numeric values:

- `1`: Critical
- `2`: High
- `3`: Moderate
- `4`: Low
- `5`: Planning

## Testing

You can test the incident management functionality using the provided test script:

```bash
python examples/test_incidents.py
```

Make sure to set the required environment variables in your `.env` file:

```
SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
SERVICENOW_USERNAME=your-username
SERVICENOW_PASSWORD=your-password
SERVICENOW_AUTH_TYPE=basic
``` 