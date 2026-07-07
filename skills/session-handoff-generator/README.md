# Session Handoff Generator

**Transform session transcripts into governed memory artifacts with explicit consent lifecycle.**

## Quick Start

### 1. Generate Draft Handoff

```bash
cd /Users/ocuser/.openclaw/workspace

# From session ID
./skills/session-handoff-generator/generate-handoff.py \
  --session-id "agent:main:dashboard:ffdc78df" \
  --output "memory/handoffs/2026-07-07-ffdc78df.md"

# From transcript file
./skills/session-handoff-generator/generate-handoff.py \
  --transcript-file ./session.json \
  --output "memory/handoffs/2026-07-07-session.md"
```

### 2. Review and Approve

```bash
./skills/session-handoff-generator/review-handoff.sh \
  memory/handoffs/2026-07-07-ffdc78df.md
```

Interactive prompts:
- **k**eep → Approve for next session
- **d**elete → Reject (won't carry forward)
- **e**dit → Modify text before approving
- **s**kip → Defer decision (stays in draft)

### 3. Output

Approved items automatically:
- Update handoff file with `consentState: user-reviewed`
- Commit corrections to `memory/corrections-log.md`
- Add unresolved tensions to `memory/03-projects-pending.md`

---

## What Gets Captured

| Type | Example | Action |
|------|---------|--------|
| **Framing Changes** | "Actually, let's pause this and look at X first" | Task scope shift noted |
| **Boundaries** | "Don't send external messages without approval" | Constraint enforced |
| **Unresolved Tensions** | "We'll come back to this after the firewall arrives" | Pending state preserved |
| **Corrections** | "The path is d03_ai not do3_ai" | Logged for regression testing |

---

## File Structure

```
skills/session-handoff-generator/
├── SKILL.md                    # Full specification
├── README.md                   # This file
├── generate-handoff.py         # Main generator script
├── review-handoff.sh           # Interactive review workflow
└── test-transcript.json        # Sample transcript for testing

memory/
├── handoffs/                   # Draft/approved handoff artifacts
│   └── 2026-07-07-{session-id}.md
├── corrections-log.md          # Approved corrections (auto-updated)
└── 03-projects-pending.md      # Unresolved tensions (auto-updated)
```

---

## Integration

### Gateway Config (Future)

```json
{
  "handoff": {
    "auto_generate": true,
    "require_review": true,
    "default_expiry_days": 90,
    "storage_path": "memory/handoffs/"
  }
}
```

### Eval Suite Tests

- `ctx_007`: Corrections log consulted before answering
- `ctx_008`: Boundary respected across sessions
- `ctx_009`: Unresolved tension preserved without auto-completion

---

## Examples

### Generate from Current Session

```bash
# Get current session ID
SESSION_ID=$(openclaw status --json | jq -r '.sessionId')

# Generate handoff
./skills/session-handoff-generator/generate-handoff.py \
  --session-id "$SESSION_ID" \
  --output "memory/handoffs/$(date +%Y-%m-%d)-${SESSION_ID: -8}.md"
```

### Batch Process Old Sessions

```bash
for session_file in sessions-archive/*.json; do
    ./skills/session-handoff-generator/generate-handoff.py \
      --transcript-file "$session_file" \
      --output "memory/handoffs/$(basename "$session_file" .json).md"
done
```

---

## Troubleshooting

**No items extracted:**
- Check transcript has user turns (only user input is analyzed)
- Verify patterns match (see `generate-handoff.py` PATTERNS dict)

**Too many low-confidence items:**
- Script filters out low-confidence by default
- Adjust `calculate_confidence()` thresholds if needed

**Review workflow hangs:**
- Ensure terminal supports interactive input
- Try running with `bash -i review-handoff.sh <file>`

---

## References

- [HackerNoon: AI Memory as Product State](https://hackernoon.com/ai-memory-should-be-product-state-not-a-hidden-prompt-trick)
- [SKILL.md](./SKILL.md) — Full specification and design rationale
