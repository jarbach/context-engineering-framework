# Context Engineering Analysis

## Source Articles

1. [nao Labs Context Engineering Playbook](https://docs.getnao.io/nao-agent/context-engineering/playbook)
2. [HackerNoon: Solving AI Amnesia at Scale](https://hackernoon.com/solving-ai-amnesia-at-scale-context-pipelines-for-large-enterprises)
3. [HackerNoon: AI Memory Should Be Product State](https://hackernoon.com/ai-memory-should-be-product-state-not-a-hidden-prompt-trick)
4. [HackerNoon: Modal Logic & Neural Networks](https://hackernoon.com/modal-logic-neural-networks)

---

## Key Insights

### 1. Context Engineering = Analytics Engineering 2.0

**Parallel:** Just as analytics engineering brought structure to raw data (dbt, transformation layers, documentation), context engineering brings structure to raw context.

**Reliability Jump:** 40% → 90% achieved through:
- Cleaning data models (memory structure)
- Writing good documentation (handoff artifacts)
- NOT fancy profiling tools or complex context sources

**Implication for OpenClaw:** Focus on memory hygiene and documentation quality over adding more context sources.

### 2. Context Needs Its Own Stack

```
Ingest → Transform → Resolve → Expose
```

**Ingest:** Memory writes, session transcripts, config changes  
**Transform:** Modal classification, contradiction resolution, staleness detection  
**Resolve:** Single source of truth, evidence-based retrieval  
**Expose:** Prompt injection with provenance metadata

**Current Gap:** OpenClaw has Ingest (memory files) and Expose (memory_search), but Transform and Resolve are ad-hoc.

### 3. Two-State Memory Model

**userMemoryEnabled** vs **canUsePromptMemory**:
- Storage ≠ Injection
- Explicit consent lifecycle required
- "Do not carry forward" list as important as carry-forward

**Implementation:** Handoff artifact generator with draft → review → approve workflow.

### 4. Modal Logic Framework

**Necessary Properties:**
- Invariant across possible worlds (sessions)
- Boundaries, corrections, unresolved tensions
- Should persist forever (365-day expiry)

**Contingent Properties:**
- Session-specific framing
- Task focus, hypotheses
- Should expire (~30 days)

**Philosophical Validation:** LayerNorm discards contingent magnitude while preserving necessary relational structure — mirrors how handoffs should work.

### 5. Failure Modes to Test

**Context Pipeline Anti-Patterns:**
1. **Retrieval Bugs** — Wrong timezone from structured fields
2. **Summarization Loss** — Entity relationships flattened
3. **Context Dilution** — Too much irrelevant history
4. **Assembly Order** — Stale summaries override new corrections
5. **Deliberate Forgetting** — Expired items still injected

**Eval Coverage:** Tests ctx_001 through ctx_014 validate these failure modes.

---

## OpenClaw Mapping

| Article Concept | OpenClaw Implementation | Status |
|-----------------|------------------------|--------|
| Context Stack | Gateway config + memory skills | ✅ Partial |
| Memory Hygiene | memory/ split architecture | ✅ Complete |
| Handoff Artifacts | session-handoff-generator skill | ✅ Complete |
| Modal Classification | generate-handoff.py modality logic | ✅ Complete |
| Evidence-Based Retrieval | modal-memory-retrieval skill | ✅ Complete |
| Eval Framework | agent-eval-framework skill | ✅ Complete |
| Contradiction Resolution | corrections-log.md | ✅ Started |
| Staleness Detection | (proposed) | ⏳ Pending |
| Semantic Metrics Layer | (proposed) | ⏳ Pending |

---

## Actionable Takeaways

### 1. Memory Hygiene Protocol
- [x] Split MEMORY.md into domain files (<24K each)
- [x] Add corrections-log.md for invariant fixes
- [ ] Add staleness detector (cron job flags old dated files)
- [ ] Add expiration enforcement (auto-archive contingent items >90 days)

### 2. Agent Reliability Evals
- [x] Build eval framework with 7 weighted categories
- [x] Achieve 100% baseline (36/36 tests)
- [ ] Integrate real OpenClaw API calls (replace placeholders)
- [ ] Set up automated daily runs (cron or GitHub Actions)
- [ ] Add trend analysis dashboard

### 3. Contradiction Resolution
- [x] Create corrections-log.md template
- [ ] Design contradiction detection workflow (memory_search + LLM judge)
- [ ] Add resolution state tracking (pending → resolved)

### 4. Governance Layer
- [x] Handoff generator with consent lifecycle
- [x] Modal classification (necessary vs contingent)
- [ ] Gateway config for memory access states
- [ ] Retrieval provenance metadata (reason, source, consentState)

### 5. Semantic Layer for Metrics
- [ ] Define standard metrics (reliability, latency, context quality)
- [ ] Aggregate across sessions/agents
- [ ] Expose via dashboard API

---

## Implementation Priority

**Phase 1 (Complete):**
- Eval framework prototype
- Handoff generator v2.0 with modal logic
- Modal retrieval engine
- Gateway plugin skeleton

**Phase 2 (In Progress):**
- Plugin build & installation
- Real eval execution (not simulated)
- Integration testing end-to-end

**Phase 3 (Planned):**
- Native Gateway config schema
- Staleness detector
- Contradiction resolution workflow
- Automated daily eval runs

---

## References

- [OpenClaw Memory Search Docs](https://docs.openclaw.ai/concepts/memory-search)
- [OpenClaw Plugin Hooks](https://docs.openclaw.ai/plugins/hooks)
- [Anthropic Self-Service Analytics](https://claude.com/blog/how-anthropic-enables-self-service-data-analytics-with-claude)
