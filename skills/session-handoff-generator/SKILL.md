# Session Handoff Generator

**Purpose:** Generate structured handoff artifacts at session end, capturing framing changes, boundaries, unresolved tensions, and corrections for user review before committing to memory.

**Version:** 1.0 (2026-07-07)

**Inspired by:** [HackerNoon "AI Memory Should Be Product State"](https://hackernoon.com/ai-memory-should-be-product-state-not-a-hidden-prompt-trick)

---

## Overview

This skill transforms session transcripts into governed handoff artifacts with explicit consent lifecycle (draft → review → approve/reject). Prevents "hidden prompt trick" memory by making carry-forward decisions visible and editable.

---

## Handoff Artifact Schema

```typescript
type HandoffArtifact = {
  id: string;                    // UUID or timestamp-based
  sessionId: string;             // Source session ID
  createdAt: string;             // ISO-8601 timestamp
  
  // Categorized items
  carryForward: HandoffItem[];        // Should enter next session
  doNotCarryForward: HandoffItem[];   // Explicitly excluded
  unresolvedTensions: HandoffItem[];  // Left open on purpose
  userCorrections: HandoffItem[];     // Fixes to prior errors
  
  // Consent state
  consentState: "draft" | "user-reviewed" | "approved" | "edited" | "rejected";
  reviewedAt?: string;
  expiresAt?: string;            // For deliberate forgetting
  
  // Metadata
  confidence: "low" | "medium" | "high";  // Overall artifact confidence
};

type HandoffItem = {
  kind: "framing-change" | "boundary" | "unresolved-tension" | "correction";
  text: string;                  // The memory content
  sourceExcerpt?: string;        // Quote from transcript
  reason: string;                // Why this matters
  confidence: "low" | "medium" | "high";
  regressionTest?: string;       // Linked eval test ID (e.g., "ctx_007")
};
```

---

## Files

| File | Purpose |
|------|---------|
| `skills/session-handoff-generator/SKILL.md` | This spec |
| `skills/session-handoff-generator/generate-handoff.py` | Main generator script |
| `skills/session-handoff-generator/review-handoff.sh` | Interactive review workflow |
| `memory/handoffs/YYYY-MM-DD-{session-id}.md` | Draft/approved handoff artifacts |
| `memory/corrections-log.md` | Approved corrections (subset of handoffs) |

---

## Quick Start

### Generate Draft Handoff

```bash
cd /Users/ocuser/.openclaw/workspace
./skills/session-handoff-generator/generate-handoff.py \
  --session-id "agent:main:dashboard:ffdc78df" \
  --output "memory/handoffs/2026-07-07-ffdc78df.md"
```

### Review and Approve

```bash
./skills/session-handoff-generator/review-handoff.sh \
  memory/handoffs/2026-07-07-ffdc78df.md
```

Workflow:
1. Displays draft handoff items
2. Prompts: keep / delete / edit / defer
3. Updates `consentState` based on choices
4. Commits approved items to appropriate memory files

---

## Item Classification Rules

### Framing Changes
**Detect when:**
- User shifts task scope ("Actually, let's rebuild the whole eval framework")
- Problem definition evolves ("The real issue isn't X, it's Y")
- Success criteria change ("Forget reliability, let's optimize for speed")

**Example:**
```yaml
kind: framing-change
text: "Task shifted from 'fix eval runner bugs' to 'integrate real OpenClaw execution'"
sourceExcerpt: "User: Let's hold it right there. I have something else for you to look at."
reason: "Scope expansion requires different implementation approach"
confidence: high
```

### Boundaries
**Detect when:**
- User sets constraints ("Don't modify safety constraints")
- Approval requirements stated ("Ask before external actions")
- Topic restrictions ("Don't bring up the firewall purchase unless I ask")

**Example:**
```yaml
kind: boundary
text: "Request explicit approval before any external messaging (email, Slack, etc.)"
sourceExcerpt: "User: Never send half-baked replies to messaging surfaces."
reason: "Safety governance requirement"
confidence: high
regressionTest: "ctx_008"
```

### Unresolved Tensions
**Detect when:**
- Work left pending intentionally ("We'll come back to this after the firewall arrives")
- Blocked decisions ("Waiting for Jon's response on the VPS choice")
- Deliberate non-closure ("Let's leave this open for now")

**Example:**
```yaml
kind: unresolved-tension
text: "Eval framework real execution integration pending"
sourceExcerpt: "Next phase options: Real Execution Integration, Daily Automation..."
reason: "Implementation deferred to next session"
confidence: medium
```

### Corrections
**Detect when:**
- User fixes agent mistake ("Actually, it's d03_ai not do3_ai")
- Config error corrected ("The path typo is causing MCP load failure")
- Behavior adjustment ("Don't use memory_search for simple acks")

**Example:**
```yaml
kind: correction
text: "Coral-Vision MCP path: d03_ai/workspace (not do3_ai)"
sourceExcerpt: "Coral-vision MCP server path fixed — do3_ai → d03_ai"
reason: "Typo caused server load failure"
confidence: high
regressionTest: "ctx_007"
```

---

## Generation Algorithm

```python
def generate_handoff(session_transcript):
    # Step 1: Extract candidate items
    candidates = []
    
    for turn in session_transcript:
        # Detect framing changes
        if turn.contains_scope_shift():
            candidates.append(classify_as_framing_change(turn))
        
        # Detect boundaries
        if turn.contains_constraint_or_requirement():
            candidates.append(classify_as_boundary(turn))
        
        # Detect unresolved tensions
        if turn.contains_pending_or_blocked_language():
            candidates.append(classify_as_unresolved_tension(turn))
        
        # Detect corrections
        if turn.contains_correction_pattern():
            candidates.append(classify_as_correction(turn))
    
    # Step 2: Deduplicate and rank by confidence
    ranked = deduplicate_and_rank(candidates)
    
    # Step 3: Categorize into carryForward vs doNotCarryForward
    # Default: all candidates are carryForward unless flagged
    handoff = {
        'carryForward': [item for item in ranked if not item.exclude],
        'doNotCarryForward': [item for item in ranked if item.exclude],
        'unresolvedTensions': [item for item in ranked if item.kind == 'unresolved-tension'],
        'userCorrections': [item for item in ranked if item.kind == 'correction'],
        'consentState': 'draft',
        'createdAt': now_iso(),
    }
    
    return handoff
```

---

## Review Workflow

```bash
$ ./review-handoff.sh memory/handoffs/2026-07-07-ffdc78df.md

=== Draft Handoff Review ===
Session: agent:main:dashboard:ffdc78df
Created: 2026-07-07 09:53

[CARRY FORWARD] (5 items)
─────────────────────────
1. [framing-change] Task shifted from 'fix eval runner bugs' to 'integrate real OpenClaw execution'
   Confidence: high
   Source: Turn 47
   
   Actions: [k]eep  [d]elete  [e]dit  [s]kip (defer decision)
   > _
```

User actions:
- **keep** → Item moves to approved list
- **delete** → Item added to `doNotCarryForward`
- **edit** → Opens text editor for modification
- **skip** → Item remains in draft state

After review:
- Updates `consentState` to "user-reviewed" or "edited"
- Commits approved corrections to `memory/corrections-log.md`
- Commits unresolved tensions to `memory/03-projects-pending.md`
- Archives rejected items with timestamp

---

## Integration Points

### With Eval Framework
- Link corrections to regression tests (`regressionTest` field)
- Validate handoff injection via `ctx_007`, `ctx_008`, `ctx_009` tests
- Track handoff-to-memory pipeline reliability

### With Gateway Config
```json
{
  "handoff": {
    "auto_generate": true,           // Generate draft at session end
    "require_review": true,          // Block commit without review
    "default_expiry_days": 90,       // Auto-archive old handoffs
    "storage_path": "memory/handoffs/"
  }
}
```

### With Memory Search
Extend retrieval results with handoff provenance:
```json
{
  "excerpt": "d03_ai/workspace (not do3_ai)",
  "source": "handoff",
  "handoffId": "2026-06-30-coral-vision-fix",
  "consentState": "approved",
  "kind": "correction",
  "reason": "Typo caused server load failure"
}
```

---

## Failure Modes to Avoid

1. **Over-extraction** — Don't generate 50 handoff items from a 20-turn session
   - Mitigation: Confidence threshold (only high/medium confidence items)
   
2. **Wrong classification** — Boundaries mislabeled as preferences
   - Mitigation: Explicit pattern matching for constraint language
   
3. **Stale handoffs** — Old drafts injected without expiration check
   - Mitigation: `expiresAt` field + Gateway config validation
   
4. **Review fatigue** — User approves everything to skip workflow
   - Mitigation: Keep draft generation concise (<10 items typical)

---

## Next Steps

1. Implement `generate-handoff.py` with LLM-based classification
2. Build `review-handoff.sh` interactive workflow
3. Add Gateway config schema for handoff settings
4. Integrate with session end hook (auto-generate draft)
5. Extend `memory_search` to include handoff provenance metadata

---

## References

- [HackerNoon: AI Memory as Product State](https://hackernoon.com/ai-memory-should-be-product-state-not-a-hidden-prompt-trick)
- [HackerNoon: Solving AI Amnesia at Scale](https://hackernoon.com/solving-ai-amnesia-at-scale-context-pipelines-for-large-enterprises)
- [nao Labs Context Engineering Playbook](https://docs.getnao.io/nao-agent/context-engineering/playbook)


## Modal Logic Integration (v2.0)

**Added:** 2026-07-07  
**Inspired by:** [HackerNoon "Modal Logic & Neural Networks"](https://hackernoon.com/modal-logic-and-neural-networks)

### Core Concept

From the article: "Rather than asking how tensors change numerically, modal logic asks what information remains necessarily true as those tensors change."

Applied to session handoffs:
- **Necessary properties** persist across "possible worlds" (sessions)
- **Contingent properties** may vary between sessions

### Modality Classification

| Kind | Modality | Expiry | Rationale |
|------|----------|--------|-----------|
| `boundary` | necessary | 365 days | Constraints are invariant |
| `correction` | necessary | 365 days | Fixed errors remain true |
| `unresolved-tension` | necessary | 365 days | Pending work persists until resolved |
| `framing-change` | contingent | 30 days | Task focus may shift again |

### Implementation

```python
def determine_modality(kind: HandoffKind) -> Modality:
    modality_map = {
        "boundary": "necessary",           # Invariant
        "correction": "necessary",          # Fixed truth
        "unresolved-tension": "necessary",  # Persists until resolved
        "framing-change": "contingent",     # May change
    }
    return modality_map.get(kind, "contingent")
```

### Connection to Neural Networks

The article's key example: LayerNorm normalizes `[2,4,6]` and `[20,40,60]` to the same vector `[-1.225, 0, 1.225]`.

**Traditional view:** Removes scale, stabilizes gradients  
**Modal view:** Discards contingent property (magnitude), preserves necessary structure (relationships)

**Handoff parallel:** 
- Contingent: Session-specific task framing ("Let's build eval framework")
- Necessary: Invariant constraints ("Don't send external messages without approval")

Handoff artifacts collapse many session variations into one semantic structure by preserving what's necessary.

### Eval Suite Integration

New tests in `memory/eval-suite.yml`:
- `ctx_011`: Necessary property persists (boundary across sessions)
- `ctx_012`: Necessary property persists (correction applied)
- `ctx_013`: Contingent property expires (old framing not injected)
- `ctx_014`: Modal distinction in retrieval ranking (necessary prioritized)

