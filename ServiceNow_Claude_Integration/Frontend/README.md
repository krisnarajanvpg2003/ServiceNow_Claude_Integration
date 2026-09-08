# ServiceNow Chat (frontend)

A ChatGPT-style React UI for the ServiceNow MCP HTTP API that lives in `../servicenow-mcp`.
You type a question, the app maps it to one read-only backend endpoint, calls it, and renders
the result as a conversation (tables, cards, badges) with the exact request shown under each answer.

```
Browser  ──►  Vite dev server (localhost:5173)  ──/api/*──►  MCP HTTP API (127.0.0.1:8095)  ──►  ServiceNow
             React app, no secrets                          scripts/simple_test_api.py
                                                            holds SERVICENOW_* credentials
```

The frontend is completely separate from the backend. It never sees ServiceNow credentials:
they stay in `servicenow-mcp/.env` and are only read by the Python API.

## Prerequisites

- Node.js 18+ (tested with Node 24)
- The backend running on `http://127.0.0.1:8095`

## Run it locally

Open two terminals.

**Terminal 1: backend** (from the `servicenow-mcp` folder, credentials come from its `.env`)

```powershell
cd servicenow-mcp
.venv\Scripts\python.exe scripts\chat_api.py
```

`chat_api.py` serves the read-only routes **and** `POST /chat` (Claude AI mode). If you only want the rule-based
mode, `scripts\simple_test_api.py` still works; the Claude AI toggle then stays disabled.

If it says `[Errno 10048] ... only one usage of each socket address`, a copy is already running on port 8095.
Either use that one, or stop it first (`Stop-Process -Id <pid>` after `netstat -ano | findstr :8095`).

**Terminal 2: frontend** (from this `Frontend` folder)

```powershell
cd Frontend
npm install
npm run dev
```

Then open <http://localhost:5173>. The status pill in the top bar turns green once the API and ServiceNow answer.

### Production build

```powershell
npm run build      # outputs static files to dist/
npm run preview    # serves dist/ on http://localhost:4173 with the same /api proxy
```

For a real deployment, serve `dist/` behind any reverse proxy that forwards `/api/*` to the backend
(the same thing the Vite dev server does), or set `VITE_API_BASE` at build time and enable CORS on the backend.

## The two switches: Claude AI and MCP

The top bar has two switches. **Claude AI** decides *who* answers: Claude (via `POST /api/chat`) or the rule-based
parser in the browser. **MCP** decides *how* ServiceNow is reached: through the ServiceNow MCP server process, or by
calling the tool functions directly in the backend. Every answer carries a small tag saying which path produced it.

| Claude AI | MCP | What happens |
| --- | --- | --- |
| off | off | Browser maps the question to one GET, e.g. `/api/incidents?limit=5&via=direct`. The backend calls the Python tool function in-process, which calls the ServiceNow REST API. Fastest, no AI. |
| off | on | Same GET with `via=mcp`. The backend acts as an **MCP client** (`servicenow_mcp/mcp_client.py`): it sends a real `tools/call` over stdio to `python -m servicenow_mcp.cli`, which calls ServiceNow. Same result, one extra hop, no AI. |
| on | on | `POST /api/chat` with `transport: "mcp"`. The Claude Agent SDK starts the Claude Code CLI and attaches the MCP server; Claude reads the question, picks `mcp__servicenow__*` tools, and writes the answer. |
| on | off | `POST /api/chat` with `transport: "direct"`. The same read-only tool functions are registered **inside the backend** as in-process tools (`create_sdk_mcp_server` in `chat_agent.py`), so no MCP server process is started; Claude picks them and the backend calls ServiceNow directly. |

Rules mode is deterministic and free; Claude mode understands any phrasing and can chain several lookups.
The MCP switch never changes *what* data comes back, only the route it takes, which is the point of the demo.

On the backend, `servicenow-mcp/src/servicenow_mcp/chat_agent.py` runs the
[Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk): it starts the bundled Claude Code CLI, attaches either
the **existing, unchanged** ServiceNow MCP server (`python -m servicenow_mcp.cli`) over stdio or the in-process tools,
and lets Claude decide which tools to call. The route in `servicenow-mcp/scripts/chat_api.py` streams every step back
as server-sent events:

| Event         | Meaning                                                            |
| ------------- | ------------------------------------------------------------------ |
| `status`      | CLI started, MCP server connected, how many tools are available    |
| `tool_use`    | Claude called a tool (name + arguments), shown as a chip           |
| `tool_result` | The tool's JSON, rendered with the same tables as rules mode       |
| `text`        | Interim text such as "Let me check that"                           |
| `done`        | Final answer, session id, turn count, cost, duration               |
| `error`       | Something failed (auth, MCP server, SDK)                           |

Follow-up questions in the same chat resume the same SDK session (`session_id`), so "show the second one" works.

What keeps it safe and cheap:

- **Read-only.** Only the tools in the `chat_readonly` package (`servicenow-mcp/config/tool_packages.yaml`) are
  loaded and only those are auto-approved; create/update/resolve tools are never approved. Built-in file and shell
  tools are disabled (`tools=[]`), and the agent ignores the machine's Claude settings (`setting_sources=[]`).
- **Credentials stay on the backend.** ServiceNow credentials go to the MCP subprocess; Anthropic credentials go to
  the CLI. The browser only sees events. With no `ANTHROPIC_API_KEY` in `servicenow-mcp/.env` the CLI uses the Claude
  (Pro/Max) login on that machine, so usage counts against the subscription and nothing is billed per token; the
  status endpoint reports this as `"billing": "subscription"`. Set an API key only for a server deployment.
- **Model and effort** come from `CHAT_MODEL` (default `claude-opus-5`) and `CHAT_EFFORT` (default `medium`).
  A question typically takes 10 to 25 seconds, mostly CLI and MCP start-up. `CHAT_MODEL=claude-sonnet-5` is
  faster and lighter on the subscription's usage limits.
- **Fallback.** `/`-prefixed raw paths and `help` always use rules mode, and if `/chat/status` reports Claude as
  unavailable the toggle is disabled with the reason in its tooltip.

## Share it as one link

Both servers run on your machine, so sharing means opening a tunnel. From the `Mcp_Demo` folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\share.ps1
```

The script downloads the Cloudflare tunnel client once (no account), starts the backend and frontend if they are
not running, and prints a `https://<random>.trycloudflare.com` link. That single link serves the UI and, through the
`/api` proxy, the backend. It works only while the script and your machine stay up, and the address changes each run.
Anyone holding the link can read from ServiceNow through the read-only account, so share it deliberately.

`vite.config.js` already allows the common tunnel hostnames (`*.trycloudflare.com`, `*.devtunnels.ms`, ngrok).
For another host, set `ALLOWED_HOSTS=your.host.name` in `Frontend/.env`.

## Configuration

Copy `.env.example` to `.env` if you need to change anything. Both values are optional.

| Variable        | Default                  | Purpose                                                                 |
| --------------- | ------------------------ | ----------------------------------------------------------------------- |
| `BACKEND_URL`   | `http://127.0.0.1:8095`  | Where the Vite dev/preview server forwards `/api/*` requests.           |
| `VITE_API_BASE` | `/api`                   | Base URL the browser calls. Leave as `/api` to keep using the proxy.    |

Never put `SERVICENOW_INSTANCE_URL`, `SERVICENOW_USERNAME` or `SERVICENOW_PASSWORD` in this folder.
Anything prefixed `VITE_` is bundled into the browser build and is public.

## Theme

The light theme uses the Data Recon palette (Supernova yellow `#FFC800`, orange `#FB621F`, Mine Shaft black
`#1F1F1F` on a warm off-white). The sidebar footer toggles **Dark mode**, which keeps the same accents on dark
surfaces. The choice is remembered per browser. All colours live as CSS variables at the top of `src/styles.css`.

## What you can ask

The intent parser (`src/lib/intent.js`) is rule-based and runs in the browser, so every question maps to exactly one GET request.

| You type                                                        | Backend call                                          |
| --------------------------------------------------------------- | ----------------------------------------------------- |
| `show me the 5 most recent incidents`                           | `GET /incidents?limit=5`  (newest first)              |
| `closed incidents about wifi`                                   | `GET /incidents?limit=5&q=wifi&state=7`               |
| `get INC0015571` or just `INC0015571`                           | `GET /incidents/INC0015571`                           |
| `catalog items about laptop`                                    | `GET /catalog/items?limit=5&q=laptop`                 |
| `show catalog item <32-char sys_id>`                            | `GET /catalog/items/<sys_id>`                         |
| `list catalog categories`                                       | `GET /catalog/categories?limit=5`                     |
| `catalog recommendations for inactive items and low usage`      | `GET /catalog/recommendations?types=inactive_items,low_usage` |
| `groups matching network`                                       | `GET /groups?limit=5&q=network`                       |
| `who is svc.claudecode.readonly`                                | `GET /users/svc.claudecode.readonly`                  |
| `user by email jane@example.com`                                | `GET /users/by-email/jane%40example.com`              |
| `health` / `is the api up`                                      | `GET /health`                                         |
| `which tool packages are loaded`                                | `GET /packages`                                       |
| `/incidents?limit=3&state=7` (any path starting with `/`)       | Called as-is (read-only paths only)                   |
| `help`                                                          | Answered locally                                      |

Incident state words map to ServiceNow codes: new = 1, in progress = 2, on hold = 3, resolved = 6, closed = 7, canceled = 8.
Numbers such as "top 3" set the limit (max 50). Clicking an incident number or catalog item in a result sends a follow-up question for its details.

### Dates and sorting (incidents)

Incidents are always returned **newest first** unless you ask otherwise. Date words in the question become a
`created_from` / `created_to` window (or `updated_from` / `updated_to` when you say "updated"). The window is
computed in your browser's local time and shown in the reply.

| You type                                        | Effect                                                              |
| ----------------------------------------------- | ------------------------------------------------------------------- |
| `incidents created in the last 7 days`          | `created_from` = now minus 7 days                                   |
| `incidents updated in the last 2 weeks`         | `updated_from` = now minus 14 days, sorted by last update           |
| `incidents today` / `yesterday` / `this month`  | that calendar window                                                |
| `incidents in June 2025` / `from June 2025`     | 2025-06-01 00:00:00 to 2025-06-30 23:59:59                          |
| `incidents in 2024`                             | the whole year                                                      |
| `incidents since 2025-06-01`                    | open-ended from that day                                            |
| `incidents before 2024` / `older than 30 days`  | open-ended up to that point                                         |
| `incidents between 2025-06-01 and 2025-06-30`   | explicit range (also `5 June 2025`, `June 5, 2025`)                 |
| `oldest incidents`                              | `sort=created&order=asc`                                            |
| `recently updated incidents`                    | `sort=updated&order=desc`                                           |
| `incidents by priority`                         | `sort=priority&order=asc` (P1 first)                                |

If a window returns nothing, the reply says so and suggests widening it. On the demo instance the newest incidents
are from mid-2025, so "last 7 days" is usually empty while "June 2025" has data.

### Backend parameters this relies on

`GET /incidents` in `servicenow-mcp/scripts/simple_test_api.py` accepts `limit`, `q`, `state`,
`sort` (`created` default, `updated`, `opened`, `resolved`, `closed`, `number`, `priority`), `order` (`asc`/`desc`),
`created_from`, `created_to`, `updated_from`, `updated_to` (`YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`).
They map onto the `list_incidents` MCP tool, which now always sends an `ORDERBY` to ServiceNow and validates
the sort field and date formats. Invalid values come back as HTTP 400.

## Project layout

```
Frontend/
├─ index.html
├─ vite.config.js            # /api proxy to the backend
├─ package.json
├─ .env.example
└─ src/
   ├─ main.jsx
   ├─ App.jsx                # conversation state, sending, brand bar, health pill
   ├─ styles.css             # Data Recon palette, dark mode, ChatGPT-like layout
   ├─ lib/
   │  ├─ api.js              # fetch wrapper + error normalisation
   │  ├─ intent.js           # question -> endpoint mapping, dates and sorting
   │  ├─ summarize.js        # one-line reply per tool result
   │  ├─ format.js           # display helpers (display_value, badges, html stripping)
   │  └─ storage.js          # localStorage for history and theme
   └─ components/
      ├─ Sidebar.jsx  ChatWindow.jsx  Message.jsx  Composer.jsx  EmptyState.jsx
      ├─ ToolResult.jsx      # picks a renderer by MCP tool name, falls back to JSON
      └─ renderers/          # IncidentList, IncidentDetail, CatalogItems, UserCard, Groups, ...
```

## Troubleshooting

- **Red "API offline" pill / "I couldn't reach the ServiceNow MCP API"**: the backend is not running on port 8095. Start it with the command above. If you run it on another port, set `BACKEND_URL` in `Frontend/.env` and restart `npm run dev`.
- **"ServiceNow unreachable"**: the backend is up but its `/health` check against ServiceNow failed. Check `servicenow-mcp/.env`.
- **HTTP 502 with a ServiceNow message**: the record does not exist or the read-only account cannot see it. The raw payload is under "Show JSON".
- **Incidents look unsorted or ignore dates**: the backend process is running old code. Restart it so the new `list_incidents` parameters are loaded.
- **Port 5173 already in use**: run `npm run dev -- --port 5174`.
