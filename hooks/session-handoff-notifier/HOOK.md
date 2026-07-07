---
name: session-handoff-notifier
description: "Notify users when handoff artifacts are generated"
metadata:
  { "openclaw": { "emoji": "📝", "events": ["message:sent"], "requires": { "bins": ["node"] } } }
---

# Session Handoff Notifier

Monitors outbound messages for handoff generation notifications and ensures they're properly routed to users.

## Events

- `message:sent` - Observes all outbound messages

## Behavior

This hook is a placeholder for future enhancement. The main handoff generation logic lives in the `session-handoff` plugin.

