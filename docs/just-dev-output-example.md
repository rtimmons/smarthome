# Example `just dev` Output

This shows what the local development environment looks like when running.

## Startup

```
╭──────────────────────────────────────────────────────────────────────────────╮
│ 🚀 Starting smart home development environment...                            │
╰──────────────────────────────────────────────────────────────────────────────╯
Discovered 4 addon(s)
                                    Add-ons
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name                ┃ Port ┃ Type    ┃ Directory                             ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Printer Service     │ 8099 │ Python  │ /Users/you/Projects/smarthome/printer │
│ Sonos API           │ 5006 │ Node.js │ /Users/you/Projects/smarthome/sonos…  │
│ Node Sonos HTTP API │ 5005 │ Node.js │ /Users/you/Projects/smarthome/node-…  │
│ Grid Dashboard      │ 3000 │ Node.js │ /Users/you/Projects/smarthome/grid-…  │
└─────────────────────┴──────┴─────────┴───────────────────────────────────────┘
Startup order: printer → node-sonos-http-api → sonos-api → grid-dashboard

Starting services...
```

## Service Logs

Each service gets its own color-coded prefix with timestamps:

```
[printer 18:32:15] Starting: uv run printer-service
[printer 18:32:15] Working directory: /Users/you/Projects/smarthome/printer
[printer 18:32:16]  * Serving Flask app 'printer_service.app'
[printer 18:32:16]  * Running on http://0.0.0.0:8099

[node-sonos-http-api 18:32:17] Starting: npm start
[node-sonos-http-api 18:32:17] Working directory: /Users/you/.../node-sonos-http-api/node-sonos-http-api
[node-sonos-http-api 18:32:18] Listening on port 5005

[sonos-api 18:32:19] Starting: npm run dev
[sonos-api 18:32:19] Working directory: /Users/you/Projects/smarthome/sonos-api
[sonos-api 18:32:20] Running node-supervisor with program 'npm run start:dev'
[sonos-api 18:32:21] Starting child process with 'npm run start:dev'
[sonos-api 18:32:22] Listening on port 5006

[grid-dashboard 18:32:23] Starting: npm run dev
[grid-dashboard 18:32:23] Working directory: /Users/you/Projects/smarthome/grid-dashboard/ExpressServer
[grid-dashboard 18:32:24] Running node-supervisor with program 'npm start'
[grid-dashboard 18:32:25] Starting child process with 'npm start'
[grid-dashboard 18:32:26] Server started on port 3000
```

## Ready State

```
============================================================
✨ All services running!

   • Printer Service:     http://localhost:8099
   • Sonos API:          http://localhost:5006
   • Node Sonos HTTP API: http://localhost:5005
   • Grid Dashboard:      http://localhost:3000

Press Ctrl+C to stop all services.
============================================================
```

## Auto-Reload in Action

When you save a file, you'll see:

```
[grid-dashboard 18:35:42] File changed: src/server/index.ts
[grid-dashboard 18:35:43] crashing child
[grid-dashboard 18:35:43] Starting child process with 'npm start'
[grid-dashboard 18:35:44] Server started on port 3000
```

## Graceful Shutdown

When you press Ctrl+C:

```
^C
Shutting down all services...
[grid-dashboard 18:40:12] Stopping...
[grid-dashboard 18:40:13] Stopped
[sonos-api 18:40:13] Stopping...
[sonos-api 18:40:14] Stopped
[node-sonos-http-api 18:40:14] Stopping...
[node-sonos-http-api 18:40:15] Stopped
[printer 18:40:15] Stopping...
[printer 18:40:16] Stopped
All services stopped.
```

## Handling Missing Prerequisites

If a service can't start due to missing dependencies:

```
[node-sonos-http-api 18:32:17] ⚠️  node_modules not found. Run 'npm install' first.
[node-sonos-http-api 18:32:17]    cd /Users/you/Projects/smarthome/node-sonos-http-api && npm install
[node-sonos-http-api 18:32:17] Skipping due to missing prerequisites
```

The orchestrator continues starting other services instead of crashing.
