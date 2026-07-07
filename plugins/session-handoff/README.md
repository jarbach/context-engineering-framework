# Session Handoff Generator Plugin

Automatically generates structured handoff artifacts when OpenClaw sessions close.

## Features

- **Auto-generation** on session close (idle, deleted, compaction)
- **Modal classification**: necessary (boundaries, corrections) vs contingent (framing changes)
- **Consent workflow**: drafts require user review before memory commit
- **Provenance tracking**: every item traces to session ID + turn number

## Installation

```bash
# From workspace
cd /Users/ocuser/.openclaw/workspace/plugins/session-handoff
npm install  # Install peer dependencies
npm run build

# Enable in Gateway config
# Add to ~/.openclaw/openclaw.json:
{
  "plugins": {
    "entries": {
      "session-handoff": {
        "enabled": true,
        "path": "/Users/ocuser/.openclaw/workspace/plugins/session-handoff"
      }
    }
  }
}
```

## Configuration

```json5
{
  plugins: {
    entries: {
      "session-handoff": {
        enabled: true,
        config: {
          minTurnsThreshold: 5,          // Skip sessions with < N turns
          autoGenerate: true,            // Auto-generate on session end
          requireReview: true,           // Require user approval before memory commit
          outputDir: "memory/handoffs",  // Relative to workspace
          defaultExpiryDays: 90,         // Default expiry for contingent items
          modality: {
            necessaryExpiryDays: 365,    // Boundaries/corrections persist longer
            contingentExpiryDays: 30,    // Framing changes expire sooner
            boostNecessaryInRetrieval: true
          }
        }
      }
    }
  }
}
```

## Usage

### Automatic Generation

Once enabled, the plugin automatically generates handoff drafts when sessions close:

```
Session ended → Handoff draft created → User notified
```

### Manual Review

Review generated handoffs:

```bash
./skills/session-handoff-generator/review-handoff.sh memory/handoffs/<sessionId>-handoff.md
```

### Review Actions

- **Keep** → Item approved, committed to memory
- **Edit** → Item modified, then approved  
- **Delete** → Item rejected, not committed
- **Skip** → Defer decision (remains in draft)

## File Structure

```
plugins/session-handoff/
├── package.json          # Plugin metadata
├── src/index.ts          # Plugin entry point
├── tsconfig.json         # TypeScript config
└── README.md             # This file

workspace/memory/handoffs/
└── {sessionId}-handoff.md  # Generated drafts
```

## Hook Behavior

The plugin registers a `session_end` hook with priority 50:

- Fires on: `idle`, `deleted`, `compaction`, `shutdown`, `restart`
- Skips: Sessions with < 5 turns (configurable)
- Timeout: 30 seconds per handoff generation
- Notification: Only for `idle` and `deleted` reasons

## Modal Logic Integration

Handoff items are classified by modality:

| Kind | Modality | Expiry | Example |
|------|----------|--------|---------|
| Boundary | Necessary | 365 days | "Don't send external messages without approval" |
| Correction | Necessary | 365 days | "Workspace path should be /Volumes/d03_ai/workspace" |
| Unresolved Tension | Necessary | 365 days | "Waiting for firewall appliance to arrive" |
| Framing Change | Contingent | 30 days | "Pause eval framework, work on handoff generator" |

Retrieval ranking boosts necessary items and decays old contingent items.

## Testing

```bash
# Test with mock transcript
./skills/session-handoff-generator/generate-handoff.py \
  --transcript-file skills/session-handoff-generator/test-transcript.json \
  --output test-handoff.md

# Test with real session
./skills/session-handoff-generator/generate-handoff.py \
  --transcript-file ~/.openclaw/agents/main/sessions/<sessionId>.jsonl \
  --output memory/handoffs/<sessionId>-handoff.md
```

## Troubleshooting

### Handoffs not generating

1. Check plugin is enabled: `openclaw plugins list`
2. Verify Gateway restarted after config change
3. Check Gateway logs: `openclaw logs --follow | grep session-handoff`

### Review workflow stuck

Run review script manually:
```bash
./skills/session-handoff-generator/review-handoff.sh <handoff-file>
```

## Related

- [Integration Design](../../skills/session-handoff-generator/INTEGRATION.md)
- [HackerNoon: AI Memory as Product State](https://hackernoon.com/ai-memory-should-be-product-state-not-a-hidden-prompt-trick)
- [OpenClaw Plugin Hooks](https://docs.openclaw.ai/plugins/hooks)
