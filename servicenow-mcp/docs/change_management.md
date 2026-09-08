# ServiceNow REST API Change Management Tools

This document provides information about the change management tools available in the ServiceNow REST API.

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

The change management tools expose ServiceNow's change management functionality, so you can create, update, and manage change requests over HTTP.

## Available Tools

The ServiceNow REST API provides the following change management tools:

### Core Change Request Management

1. **create_change_request** - Create a new change request in ServiceNow
   - Parameters:
     - `short_description` (required): Short description of the change request
     - `description`: Detailed description of the change request
     - `type` (required): Type of change (normal, standard, emergency)
     - `risk`: Risk level of the change
     - `impact`: Impact of the change
     - `category`: Category of the change
     - `requested_by`: User who requested the change
     - `assignment_group`: Group assigned to the change
     - `start_date`: Planned start date (YYYY-MM-DD HH:MM:SS)
     - `end_date`: Planned end date (YYYY-MM-DD HH:MM:SS)

2. **update_change_request** - Update an existing change request
   - Parameters:
     - `change_id` (required): Change request ID or sys_id
     - `short_description`: Short description of the change request
     - `description`: Detailed description of the change request
     - `state`: State of the change request
     - `risk`: Risk level of the change
     - `impact`: Impact of the change
     - `category`: Category of the change
     - `assignment_group`: Group assigned to the change
     - `start_date`: Planned start date (YYYY-MM-DD HH:MM:SS)
     - `end_date`: Planned end date (YYYY-MM-DD HH:MM:SS)
     - `work_notes`: Work notes to add to the change request

3. **list_change_requests** - List change requests with filtering options
   - Parameters:
     - `limit`: Maximum number of records to return (default: 10)
     - `offset`: Offset to start from (default: 0)
     - `state`: Filter by state
     - `type`: Filter by type (normal, standard, emergency)
     - `category`: Filter by category
     - `assignment_group`: Filter by assignment group
     - `timeframe`: Filter by timeframe (upcoming, in-progress, completed)
     - `query`: Additional query string

4. **get_change_request_details** - Get detailed information about a specific change request
   - Parameters:
     - `change_id` (required): Change request ID or sys_id

5. **add_change_task** - Add a task to a change request
   - Parameters:
     - `change_id` (required): Change request ID or sys_id
     - `short_description` (required): Short description of the task
     - `description`: Detailed description of the task
     - `assigned_to`: User assigned to the task
     - `planned_start_date`: Planned start date (YYYY-MM-DD HH:MM:SS)
     - `planned_end_date`: Planned end date (YYYY-MM-DD HH:MM:SS)

### Change Approval Workflow

1. **submit_change_for_approval** - Submit a change request for approval
   - Parameters:
     - `change_id` (required): Change request ID or sys_id
     - `approval_comments`: Comments for the approval request

2. **approve_change** - Approve a change request
   - Parameters:
     - `change_id` (required): Change request ID or sys_id
     - `approver_id`: ID of the approver
     - `approval_comments`: Comments for the approval

3. **reject_change** - Reject a change request
   - Parameters:
     - `change_id` (required): Change request ID or sys_id
     - `approver_id`: ID of the approver
     - `rejection_reason` (required): Reason for rejection

## Common tasks

These endpoints cover tasks such as:

### Creating and Managing Change Requests

- Create a change request for server maintenance to apply security patches tomorrow night
- Schedule a database upgrade for next Tuesday from 2 AM to 4 AM
- Create an emergency change to fix the critical security vulnerability in our web application

### Adding Tasks and Implementation Details

- Add a task to the server maintenance change for pre-implementation checks
- Add a task to verify system backups before starting the database upgrade
- Update the implementation plan for the network change to include rollback procedures

### Approval Workflow

- Submit the server maintenance change for approval
- Show me all changes waiting for my approval
- Approve the database upgrade change with comment: implementation plan looks thorough
- Reject the network change due to insufficient testing

### Querying Change Information

- Show me all emergency changes scheduled for this week
- What's the status of the database upgrade change?
- List all changes assigned to the Network team
- Show me the details of change CHG0010001## Example Code

Here's an example of how to use the change management tools programmatically:

```python
from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import create_change_request
from servicenow_mcp.utils.config import ServerConfig

# Create server configuration
server_config = ServerConfig(
    instance_url="https://your-instance.service-now.com",
)

# Create authentication manager
auth_manager = AuthManager(
    auth_type="basic",
    username="your-username",
    password="your-password",
    instance_url="https://your-instance.service-now.com",
)

# Create a change request
create_params = {
    "short_description": "Server maintenance - Apply security patches",
    "description": "Apply the latest security patches to the application servers.",
    "type": "normal",
    "risk": "moderate",
    "impact": "medium",
    "category": "Hardware",
    "start_date": "2023-12-15 01:00:00",
    "end_date": "2023-12-15 03:00:00",
}

result = create_change_request(auth_manager, server_config, create_params)
print(result)
```

For a complete example, see the [change_management_demo.py](../examples/change_management_demo.py) script.

## Customization

The change management tools can be customized to match your organization's specific ServiceNow configuration:

- State values may need to be adjusted based on your ServiceNow instance configuration
- Additional fields can be added to the parameter models if needed
- Approval workflows may need to be modified to match your organization's approval process

To customize the tools, modify the `change_tools.py` file in the `src/servicenow_mcp/tools` directory. 