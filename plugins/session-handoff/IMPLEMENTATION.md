# Session Handoff Plugin — Implementation Guide

**Status:** Implementation-ready (2026-07-07)  
**Version:** 1.0.0

## Overview

This plugin integrates the session handoff generator into OpenClaw's session lifecycle using typed plugin hooks.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  OpenClaw Gateway                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [Session Close Event]                                       │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────┐                                         │
│  │ session_end     │ ← Plugin hook (priority: 50)           │
│  │ (typed hook)    │                                         │
│  └────────┬────────┘                                         │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Check Threshold │ (minTurnsThreshold ≥ 5)                │
│  └────────┬────────┘                                         │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Generate        │ (execute generate-handoff.py)          │
│  │ Handoff         │                                         │
│  └────────┬────────┘                                         │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Save Draft      │ (memory/handoffs/{sessionId}.md)       │
│  └────────┬────────┘                                         │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Notify User     │ (event.messages.push)                  │
│  └─────────────────┘                                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Installation Steps

### 1. Build Plugin

```bash
cd /Users/ocuser/.openclaw/workspace/plugins/session-handoff

# Install dependencies (openclaw peer dependency)
npm install

# Build TypeScript
npm run build

# Verify build output
ls -la dist/
# Should show: index.js, index.d.ts, index.js.map
```

### 2. Enable in Gateway Config

Add to `~/.openclaw/openclaw.json`:

```json5
{
  plugins: {
    entries: {
      "session-handoff": {
        enabled: true,
        path: "/Users/ocuser/.openclaw/workspace/plugins/session-handoff",
        config: {
          minTurnsThreshold: 5,
          autoGenerate: true,
          requireReview: true,
          outputDir: "memory/handoffs",
          modality: {
            necessaryExpiryDays: 365,
            contingentExpiryDays: 30,
            boostNecessaryInRetrieval: true
          }
        }
      }
    }
  }
}
```

### 3. Restart Gateway

```bash
# Restart Gateway to load plugin
openclaw gateway restart

# Verify plugin loaded
openclaw plugins list | grep session-handoff
```

### 4. Test Integration

```bash
# Create a test session with > 5 turns
# Then close it (wait for idle timeout or use /stop)

# Check for generated handoff
ls -la /Users/ocuser/.openclaw/workspace/memory/handoffs/

# Review handoff
./skills/session-handoff-generator/review-handoff.sh memory/handoffs/<sessionId>-handoff.md
```

## Hook Semantics

### `session_end` Hook

Fired by Gateway during session finalization:

**Event Context:**
- `sessionKey`: Unique session identifier
- `sessionId`: Session ID
- `reason`: One of `idle`, `deleted`, `compaction`, `shutdown`, `restart`
- `context.messageCount`: Number of turns in session
- `context.transcriptPath`: Path to NDJSON transcript file

**Handler Behavior:**
1. Skip if `messageCount < minTurnsThreshold` (default: 5)
2. Execute `generate-handoff.py` with transcript path
3. Save output to `memory/handoffs/{sessionId}-handoff.md`
4. Push notification messages if `reason ∈ {idle, deleted}`

**Timeout:** 30 seconds per handler execution  
**Priority:** 50 (medium priority, runs after critical hooks)

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `minTurnsThreshold` | number | 5 | Minimum turns to generate handoff |
| `autoGenerate` | boolean | true | Auto-generate on session end |
| `requireReview` | boolean | true | Require user approval before memory commit |
| `outputDir` | string | `"memory/handoffs"` | Output directory (workspace-relative) |
| `defaultExpiryDays` | number | 90 | Default expiry for items without modality |
| `modality.necessaryExpiryDays` | number | 365 | Expiry for boundaries/corrections |
| `modality.contingentExpiryDays` | number | 30 | Expiry for framing changes |
| `modality.boostNecessaryInRetrieval` | boolean | true | Boost necessary items in memory_search |

## Error Handling

### Transcript Not Found

```typescript
if (!transcriptPath) {
  console.error(`[session-handoff] No transcript path for session ${sessionId}`);
  return; // Skip silently
}
```

### Generator Execution Failure

```typescript
try {
  await execFileAsync(...);
} catch (error) {
  console.error(`[session-handoff] Error:`, error);
  event.messages.push(`⚠️ Handoff generation failed`);
}
```

### Timeout Protection

The 30-second timeout prevents slow handoff generation from blocking session cleanup:

```typescript
await execFileAsync(..., { timeout: 30000 });
```

## Testing Strategy

### Unit Tests

Test pattern detection, modality classification, confidence calculation:

```bash
cd /Users/ocuser/.openclaw/workspace
./skills/session-handoff-generator/generate-handoff.py \
  --transcript-file skills/session-handoff-generator/test-transcript.json \
  --output test-output.md
```

### Integration Tests

Test full lifecycle:

1. Start fresh session
2. Have conversation with boundaries/corrections/framing changes
3. Close session (idle timeout or `/stop`)
4. Verify handoff generated
5. Review and approve items
6. Verify memory files updated

### Regression Tests

Run eval suite tests `ctx_011` through `ctx_014`:

```bash
cd /Users/ocuser/.openclaw/workspace
./skills/agent-eval-framework/run-eval.sh --verbose
./skills/agent-eval-framework/analyze-results.py --min-reliability 0.90
```

## Monitoring

### Logs

```bash
# Watch plugin logs
openclaw logs --follow | grep session-handoff

# Check for errors
openclaw logs --level error | grep session-handoff
```

### Metrics

Track via Gateway diagnostics:

- Handoffs generated per day
- Average generation time
- Review approval rate
- Modal distribution (necessary vs contingent)

### Health Checks

```bash
# Check plugin status
openclaw plugins info session-handoff

# Verify output directory exists
ls -la /Users/ocuser/.openclaw/workspace/memory/handoffs/

# Check recent handoffs
tail -20 memory/handoffs/*.md
```

## Migration Path

### Phase 1: Manual Generation ✅ (Current)

Users manually run generator on transcripts.

### Phase 2: Plugin Auto-Generation (This Implementation)

Plugin auto-generates drafts on session close.

### Phase 3: Automated Review Workflow

Build UI integration for review/approval in webchat/TUI.

### Phase 4: Memory Commit Automation

Approved items auto-committed to domain memory files.

### Phase 5: Retrieval Enhancement

`memory_search` enhanced with modal ranking logic.

## Security Considerations

1. **Consent Lifecycle**: Drafts require explicit approval before memory commit
2. **Provenance**: Every item traces to session ID + turn number
3. **Path Validation**: Generator only writes to workspace-relative paths
4. **Timeout Protection**: 30-second limit prevents resource exhaustion

## Troubleshooting

### Plugin Not Loading

```bash
# Check config syntax
openclaw config validate

# Check plugin path
ls -la /Users/ocuser/.openclaw/workspace/plugins/session-handoff/dist/index.js

# Restart gateway
openclaw gateway restart
```

### Handoffs Not Generating

```bash
# Check session had enough turns
# Check Gateway logs
openclaw logs --follow | grep session-handoff

# Test generator manually
./skills/session-handoff-generator/generate-handoff.py \
  --transcript-file <path> \
  --output test.md
```

### Review Workflow Issues

```bash
# Run review script manually
./skills/session-handoff-generator/review-handoff.sh <handoff-file>

# Check file permissions
chmod +x ./skills/session-handoff-generator/review-handoff.sh
```

## Related Documentation

- [Plugin Hooks Reference](https://docs.openclaw.ai/plugins/hooks)
- [Integration Design](../../skills/session-handoff-generator/INTEGRATION.md)
- [Eval Framework](../../skills/agent-eval-framework/SKILL.md)
- [HackerNoon: AI Memory as Product State](https://hackernoon.com/ai-memory-should-be-product-state-not-a-hidden-prompt-trick)

## Next Steps

1. **Build & Test** — Compile TypeScript, verify plugin loads
2. **Config Schema** — Add `plugins.entries.session-handoff.config.*` to Gateway schema
3. **Review UI** — Build webchat/TUI integration for interactive review
4. **Memory Commit API** — Extend `memory-ops` skill with handoff-aware functions
5. **Retrieval Enhancement** — Add modal ranking to `memory_search` implementation
