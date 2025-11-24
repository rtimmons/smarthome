# OmniFocus Integration

## Overview

This document describes how to integrate flagged OmniFocus tasks into the snapshot-service, which will then be printed by the printer add-on.

## Architecture

```
┌─────────────┐                    ┌──────────────────┐                 ┌─────────────┐
│  OmniFocus  │                    │ snapshot-service │                 │   printer   │
│  (Laptop)   │                    │ (homeassistant)  │                 │   add-on    │
└──────┬──────┘                    └────────┬─────────┘                 └──────┬──────┘
       │                                    │                                   │
       │  1. launchd triggers               │                                   │
       │     every 5 minutes                │                                   │
       │                                    │                                   │
       │  2. AppleScript/JXA                │                                   │
       │     queries flagged tasks          │                                   │
       │                                    │                                   │
       │  3. POST /reminders                │                                   │
       │────────────────────────────────────>│                                   │
       │    { reminders: ["Task 1", ...] }  │                                   │
       │                                    │                                   │
       │  4. Cache in memory                │                                   │
       │                                    │  5. GET /snapshot                 │
       │                                    │<──────────────────────────────────│
       │                                    │                                   │
       │                                    │  6. Returns full snapshot         │
       │                                    │    (including cached reminders)   │
       │                                    │───────────────────────────────────>│
       │                                    │                                   │
       │                                    │                              7. Print!
```

## Implementation Tasks

### Phase 1: Snapshot-Service API Updates

1. **Add POST endpoint for reminders**
   - Endpoint: `POST /reminders`
   - Request body: `{ reminders: string[] }`
   - Stores reminders in memory cache
   - Optional: Add authentication token

2. **Add in-memory cache**
   - Simple Map/object to store latest reminders
   - Include timestamp for staleness detection
   - Default to empty array if no data received

3. **Update GET /snapshot endpoint**
   - Replace fixture reminders with cached data
   - Optionally include metadata (last_updated timestamp)

### Phase 2: OmniFocus Query Script (macOS)

1. **Create AppleScript/JXA script**
   - Location: `~/bin/omnifocus-to-snapshot.js` (or `.scpt`)
   - Query flagged tasks using OmniFocus scripting API
   - Format as JSON array
   - POST to snapshot-service endpoint

2. **Script features**
   - Filter: Only flagged tasks
   - Filter: Exclude completed tasks
   - Filter: Exclude dropped tasks
   - Sort: By due date (optional)
   - Limit: Max N tasks (e.g., 10)
   - Format: Extract task name (and optionally due date)

3. **HTTP client**
   - Use `curl` or Node.js `fetch`
   - Target: `http://homeassistant.local:4010/reminders`
   - Handle network errors gracefully
   - Log to file for debugging

### Phase 3: Automated Execution (macOS)

1. **Create launchd plist**
   - Location: `~/Library/LaunchAgents/com.user.omnifocus-sync.plist`
   - Trigger: Every 5 minutes
   - Run: Query script from Phase 2
   - Log: Stdout/stderr to files

2. **Installation script**
   - Copy plist to LaunchAgents
   - Load with `launchctl load`
   - Test with `launchctl start`

## Implementation Details

### OmniFocus Query (JavaScript for Automation)

```javascript
#!/usr/bin/env osascript -l JavaScript

function run(argv) {
  const omnifocus = Application("OmniFocus");
  const defaultDoc = omnifocus.defaultDocument;

  // Get all flagged, available tasks
  const flaggedTasks = defaultDoc.flattenedTasks.whose({
    flagged: true,
    completed: false,
    dropped: false
  })();

  // Extract task names
  const reminders = flaggedTasks
    .slice(0, 10) // Limit to 10 tasks
    .map(task => task.name());

  return JSON.stringify({ reminders });
}
```

### Alternative: AppleScript

```applescript
tell application "OmniFocus"
  tell default document
    set flaggedTasks to every flattened task whose (flagged is true and completed is false)
    set reminderList to {}
    repeat with aTask in flaggedTasks
      set end of reminderList to name of aTask
    end repeat
    return reminderList
  end tell
end tell
```

### Snapshot-Service Endpoint (TypeScript)

```typescript
// Add to src/server.ts

interface ReminderCache {
  reminders: string[];
  lastUpdated: Date;
}

let cachedReminders: ReminderCache = {
  reminders: [],
  lastUpdated: new Date()
};

// POST endpoint to receive reminders from laptop
app.post(
  "/reminders",
  {
    schema: {
      body: z.object({
        reminders: z.array(z.string())
      }),
      response: {
        200: z.object({ success: z.boolean() })
      }
    }
  },
  async (request) => {
    cachedReminders = {
      reminders: request.body.reminders,
      lastUpdated: new Date()
    };
    return { success: true };
  }
);

// Update GET /snapshot to use cached reminders
app.get("/snapshot", async () => {
  return {
    ...snapshotFixture,
    reminders: cachedReminders.reminders
  };
});
```

### launchd Configuration

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.user.omnifocus-sync</string>

  <key>ProgramArguments</key>
  <array>
    <string>/Users/USERNAME/bin/omnifocus-to-snapshot.sh</string>
  </array>

  <key>StartInterval</key>
  <integer>300</integer> <!-- 5 minutes -->

  <key>RunAtLoad</key>
  <true/>

  <key>StandardOutPath</key>
  <string>/Users/USERNAME/Library/Logs/omnifocus-sync.log</string>

  <key>StandardErrorPath</key>
  <string>/Users/USERNAME/Library/Logs/omnifocus-sync.err</string>
</dict>
</plist>
```

### Wrapper Shell Script

```bash
#!/bin/bash
# ~/bin/omnifocus-to-snapshot.sh

set -euo pipefail

SNAPSHOT_URL="http://homeassistant.local:4010/reminders"
SCRIPT_DIR="$(dirname "$0")"

# Query OmniFocus and get JSON
REMINDERS_JSON=$("$SCRIPT_DIR/query-omnifocus.js")

# POST to snapshot-service
curl -X POST \
  -H "Content-Type: application/json" \
  -d "$REMINDERS_JSON" \
  "$SNAPSHOT_URL" \
  --max-time 5 \
  --silent \
  --show-error

echo "$(date): Synced reminders to snapshot-service"
```

## Security Considerations

### Optional Authentication

If you want to add basic security to prevent unauthorized reminder updates:

```typescript
// Add to server.ts
const REMINDER_TOKEN = process.env.REMINDER_TOKEN || "changeme";

app.post("/reminders", async (request, reply) => {
  const authHeader = request.headers.authorization;
  if (authHeader !== `Bearer ${REMINDER_TOKEN}`) {
    reply.code(401);
    return { error: "Unauthorized" };
  }
  // ... rest of handler
});
```

Then update the curl command:
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SECRET_TOKEN" \
  -d "$REMINDERS_JSON" \
  "$SNAPSHOT_URL"
```

## Testing

### Manual Testing

1. **Test OmniFocus query:**
   ```bash
   ~/bin/query-omnifocus.js
   ```

2. **Test POST endpoint:**
   ```bash
   curl -X POST \
     -H "Content-Type: application/json" \
     -d '{"reminders":["Test reminder 1","Test reminder 2"]}' \
     http://homeassistant.local:4010/reminders
   ```

3. **Test GET endpoint:**
   ```bash
   curl http://homeassistant.local:4010/snapshot | jq '.reminders'
   ```

4. **Test launchd job:**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.user.omnifocus-sync.plist
   launchctl start com.user.omnifocus-sync
   tail -f ~/Library/Logs/omnifocus-sync.log
   ```

## Troubleshooting

### OmniFocus not accessible
- Ensure OmniFocus is running
- Check System Preferences → Security & Privacy → Automation
- Grant Terminal (or your script runner) permission to control OmniFocus

### Network issues
- Verify `homeassistant.local` resolves: `ping homeassistant.local`
- Check snapshot-service is running: `curl http://homeassistant.local:4010/healthz`
- Review logs: `~/Library/Logs/omnifocus-sync.err`

### launchd not running
- Check status: `launchctl list | grep omnifocus-sync`
- Reload: `launchctl unload ~/Library/LaunchAgents/com.user.omnifocus-sync.plist && launchctl load ~/Library/LaunchAgents/com.user.omnifocus-sync.plist`
- Check system logs: `log show --predicate 'process == "launchd"' --last 1h`

## Future Enhancements

- [ ] Add due date information to reminders
- [ ] Include project/context information
- [ ] Support for different OmniFocus perspectives
- [ ] Persist reminders to disk/database for restarts
- [ ] Add staleness warning if data is old
- [ ] Support for multiple data sources (Calendar, etc.)
- [ ] Rich reminder schema (task name, due date, project, tags)
