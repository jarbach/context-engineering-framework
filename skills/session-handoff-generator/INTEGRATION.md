# Session Handoff Generator — Integration Design

**Version:** 2.0 (2026-07-07)  
**Status:** Implementation-ready

## Overview

This document describes how to integrate the handoff generator into OpenClaw's session lifecycle, enabling automatic draft generation on session close and governed memory injection.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Session Lifecycle                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [Session Start] → [Active Work] → [Session Close]          │
│                          │                                   │
│                          ▼                                   │
│              ┌───────────────────────┐                       │
│              │ Handoff Generator     │                       │
│              │ (auto-triggered)      │                       │
│              └───────────┬───────────┘                       │
│                          │                                   │
│                          ▼                                   │
│              ┌───────────────────────┐                       │
│              │ Draft Artifact        │                       │
│              │ - carryForward        │                       │
│              │ - unresolvedTensions  │                       │
│              │ - userCorrections     │                       │
│              │ - consentState: draft │                       │
│              └───────────┬───────────┘                       │
│                          │                                   │
│                          ▼                                   │
│              ┌───────────────────────┐                       │
│              │ User Review           │                       │
│              │ ./review-handoff.sh   │                       │
│              └───────────┬───────────┘                       │
│                          │                                   │
│            ┌─────────────┴─────────────┐                     │
│            ▼                           ▼                     │
│   [Approved/Edited]              [Rejected]                  │
│            │                           │                     │
│            ▼                           ▼                     │
│   ┌─────────────────┐         ┌─────────────────┐           │
│   │ Commit to Memory│         │ Archive/Discard │           │
│   │ consentState:   │         │ consentState:   │           │
│   │ approved        │         │ rejected        │           │
│   └─────────────────┘         └─────────────────┘           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Integration Points

### 1. Session Close Hook (Auto-Generate Draft)

**Location:** OpenClaw Gateway session lifecycle  
**Trigger:** Session status changes to `closed` or `aborted`  
**Action:** Spawn handoff generator sub-agent

```typescript
// Pseudocode for Gateway integration
async function onSessionClose(session: Session) {
  if (session.turnCount < 5) {
    // Skip trivial sessions
    return;
  }
  
  // Spawn handoff generator
  const handoffAgent = await sessions_spawn({
    task: `Generate handoff artifact for session ${session.id}`,
    agentId: 'main',
    mode: 'run',
    cleanup: 'keep',
  });
  
  // Pass transcript path
  await handoffAgent.invoke({
    tool: 'exec',
    command: `./skills/session-handoff-generator/generate-handoff.py \\
      --transcript-file ${session.transcriptPath} \\
      --output memory/handoffs/${session.id}-handoff.md`
  });
}
```

**Configuration:**
```json
{
  "handoff": {
    "auto_generate": true,
    "min_turns_threshold": 5,
    "require_review": true,
    "default_expiry_days": 90
  }
}
```

### 2. Review Workflow (User Consent)

**Location:** WebChat / TUI interface  
**Trigger:** User opens generated handoff file  
**Action:** Interactive review via `review-handoff.sh`

```bash
# Auto-invoked when user opens handoff file
./skills/session-handoff-generator/review-handoff.sh \
  memory/handoffs/${session.id}-handoff.md
```

**Review Actions:**
- **Keep** → Item approved, committed to memory
- **Edit** → Item modified, then approved
- **Delete** → Item rejected, not committed
- **Skip** → Defer decision (remains in draft)

### 3. Memory Commit (Governed Injection)

**Location:** Memory management skills (`memory-ops`)  
**Trigger:** User approves handoff items  
**Action:** Update domain-specific memory files

```python
# Pseudocode for memory commit
def commit_handoff(handoff: HandoffArtifact):
    if handoff['consentState'] != 'approved':
        raise ValueError("Handoff must be approved before commit")
    
    # Extract corrections
    for correction in handoff['userCorrections']:
        append_to_file(
            'memory/corrections-log.md',
            format_correction(correction)
        )
    
    # Extract boundaries
    for boundary in [i for i in handoff['carryForward'] 
                     if i['kind'] == 'boundary']:
        update_user_constraints(boundary)
    
    # Extract unresolved tensions
    for tension in handoff['unresolvedTensions']:
        append_to_pending_actions(tension)
    
    # Update handoff registry
    register_handoff(handoff)
```

### 4. Retrieval Enhancement (Modal Ranking)

**Location:** `memory_search` implementation  
**Change:** Boost necessary items, deprioritize contingent/expired

```python
def retrieve_with_modality(query: str, candidates: list[MemoryItem]) -> list[MemoryItem]:
    # Standard semantic ranking
    ranked = semantic_search(query, candidates)
    
    # Apply modality boosts
    for item in ranked:
        # Necessary items get priority
        if item.get('modality') == 'necessary':
            item.score *= 1.5
        
        # Contingent items decay after 30 days
        elif item.get('modality') == 'contingent':
            age_days = (datetime.now() - item.created_at).days
            if age_days > 30:
                item.score *= 0.5
        
        # Expired items excluded
        if item.expires_at and datetime.fromisoformat(item.expires_at) < datetime.now():
            item.excluded = True
    
    return [i for i in ranked if not i.excluded]
```

## File Structure

```
/Users/ocuser/.openclaw/workspace/
├── skills/session-handoff-generator/
│   ├── SKILL.md                    # Skill documentation
│   ├── generate-handoff.py         # Generator executable
│   ├── review-handoff.sh           # Review workflow
│   ├── README.md                   # Quickstart guide
│   └── INTEGRATION.md              # This file
│
├── memory/
│   ├── handoffs/                   # Generated drafts
│   │   ├── {sessionId}-handoff.md
│   │   └── ...
│   ├── corrections-log.md          # Approved corrections
│   └── eval-suite.yml              # Modal logic tests
│
└── openclaw.json                   # Gateway config (TBD)
```

## Configuration Schema (Proposed)

Add to Gateway configuration:

```json
{
  "handoff": {
    "enabled": true,
    "auto_generate": true,
    "min_turns_threshold": 5,
    "require_review": true,
    "default_expiry_days": 90,
    "modality": {
      "necessary_expiry_days": 365,
      "contingent_expiry_days": 30,
      "boost_necessary_in_retrieval": true
    },
    "output_path": "memory/handoffs",
    "cleanup_after_commit": false
  }
}
```

## Testing Strategy

### Unit Tests
- Pattern detection accuracy (precision/recall)
- Modality classification correctness
- Confidence calculation

### Integration Tests
- End-to-end: session close → draft generation → review → memory commit
- Retrieval ranking with modal boosts
- Expiry enforcement (contingent items expire after 30 days)

### Eval Suite Coverage
Tests already in `memory/eval-suite.yml`:
- `ctx_011`: Necessary boundary persists
- `ctx_012`: Necessary correction applied
- `ctx_013`: Contingent framing expires
- `ctx_014`: Modal distinction in retrieval

## Migration Path

### Phase 1: Manual Generation (Current)
- Users manually run `generate-handoff.py` on session transcripts
- Review via `review-handoff.sh`
- Manual memory updates

### Phase 2: Auto-Generate Drafts
- Gateway hook triggers on session close
- Drafts saved to `memory/handoffs/`
- Users notified of pending reviews

### Phase 3: Automated Commit (Opt-In)
- Users approve/reject via interactive review
- Approved items auto-committed to memory files
- Corrections log updated automatically

### Phase 4: Full Integration
- Retrieval enhanced with modal ranking
- Expiry enforcement automated
- Dashboard shows handoff health metrics

## Security Considerations

1. **Consent Lifecycle**: No memory injected without explicit approval
2. **Provenance Tracking**: Every memory item traces back to handoff ID + turn number
3. **Correction Validation**: Corrections checked against existing facts before commit
4. **Boundary Enforcement**: Boundaries applied across all sessions once approved

## Open Questions

1. **Who can approve handoffs?** Only session owner, or delegated roles?
2. **Conflict resolution**: What if two handoffs contradict (e.g., different boundaries)?
3. **Expiry notifications**: Should users be alerted when contingent items are about to expire?
4. **Audit trail**: How long to keep rejected/archived handoffs?

## Next Steps

1. **Gateway Config Schema** — Define `handoff.*` fields in `config.schema.lookup`
2. **Session Close Hook** — Implement auto-generation trigger
3. **Review UI** — Build webchat/TUI integration for `review-handoff.sh`
4. **Memory Commit API** — Extend `memory-ops` with handoff-aware functions
5. **Retrieval Enhancement** — Add modal ranking to `memory_search`

---

**Related Documentation:**
- [HackerNoon "AI Memory as Product State"](https://hackernoon.com/ai-memory-should-be-product-state-not-a-hidden-prompt-trick)
- [HackerNoon "Modal Logic & Neural Networks"](https://hackernoon.com/modal-logic-and-neural-networks)
- [OpenClaw Memory Management Skills](~/.openclaw/workspace/skills/memory-management/SKILL.md)
