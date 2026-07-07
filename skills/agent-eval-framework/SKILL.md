# Agent Evaluation Framework

**Purpose:** Measure and improve OpenClaw agent reliability through systematic testing, tracking, and iteration.

**Version:** 1.0 (2026-07-07)

**Inspired by:** [nao Labs Context Engineering Playbook](https://docs.getnao.io/nao-agent/context-engineering/playbook)

---

## Overview

This skill provides an evaluation harness for testing OpenClaw agent reliability across six categories:

1. **Memory Recall** (25%) — Fact lookup, cross-file synthesis, semantic search
2. **Tool Routing** (25%) — Correct tool selection, parameter extraction, multi-tool sequences
3. **Session Management** (15%) — State persistence, sub-agent spawning, completion handling
4. **Config/Gateway** (15%) — Config validation, schema lookup, safe mutations
5. **Skill Execution** (10%) — Skill discovery, SKILL.md parsing, workflow execution
6. **Safety/Governance** (10%) — Approval flows, PII protection, external action boundaries

---

## Quick Start

```bash
# Run full evaluation suite
cd /Users/ocuser/.openclaw/workspace
./skills/agent-eval-framework/run-eval.sh

# Run quick subset (for pre-commit)
./skills/agent-eval-framework/run-eval.sh --quick

# Analyze historical results
./skills/agent-eval-framework/analyze-results.py --trend 7d
```

---

## Files

| File | Purpose |
|------|---------|
| `memory/eval-suite.yml` | Test case definitions (20 canonical tasks) |
| `skills/agent-eval-framework/run-eval.sh` | Main runner script |
| `skills/agent-eval-framework/analyze-results.py` | Metrics and trend analysis |
| `skills/agent-eval-framework/EVAL_RESULTS.md` | Human-readable results dashboard |

---

## Test Case Format

Each test in `eval-suite.yml` follows this schema:

```yaml
- id: mem_001
  category: memory_recall
  name: "Descriptive name"
  prompt: "User prompt to test"
  
  # For content validation:
  expected_contains: ["string1", "string2"]
  forbidden_contains: ["wrong_answer"]
  
  # For tool routing validation:
  expected_tool: read
  expected_params:
    path_pattern: "pattern"
  
  # For behavior validation:
  expected_behavior: "decline_or_redact_pii"
  forbidden_tools: ["exec_curl"]
  
  # Documentation:
  sources: ["USER.md", "MEMORY.md"]
```

---

## Running Evaluations

### Full Suite

```bash
./skills/agent-eval-framework/run-eval.sh
```

Output:
- Creates timestamped result directory: `eval-results/YYYYMMDD-HHMMSS/`
- Writes `results.json` with detailed pass/fail per test
- Prints summary with category breakdown
- Updates `EVAL_RESULTS.md` dashboard

### Quick Mode (Pre-commit)

```bash
./skills/agent-eval-framework/run-eval.sh --quick
```

Runs only 5 critical tests (safety + core memory recall). Use in git pre-commit hooks.

### Scheduled Runs

Add to crontab or Gateway cron:

```bash
# Daily at 6 AM
0 6 * * * cd /Users/ocuser/.openclaw/workspace && ./skills/agent-eval-framework/run-eval.sh >> /tmp/eval-cron.log 2>&1
```

---

## Metrics Dashboard

After each run, check `skills/agent-eval-framework/EVAL_RESULTS.md` for:

| Metric | Target | Current | Trend |
|--------|--------|---------|-------|
| **Overall Reliability** | ≥90% | — | — |
| Memory Recall Accuracy | ≥95% | — | — |
| Tool Routing Correctness | ≥90% | — | — |
| Session State Integrity | ≥95% | — | — |
| Config Safety | 100% | — | — |

---

## Failure Analysis

When tests fail:

1. **Check `eval-results/<timestamp>/results.json`** — See exact failure details
2. **Categorize failure type:**
   - Memory gap → Update MEMORY.md or domain files
   - Tool misrouting → Adjust system prompts or tool descriptions
   - Safety violation → Review safety constraints
   - Stale context → Refresh outdated information
3. **Add regression test** — Convert failure into new test case
4. **Re-run eval** — Verify fix doesn't break existing tests

---

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/agent-eval.yml
name: Agent Evaluation

on:
  push:
    paths: ['memory/*.md', 'skills/**/*.md', 'memory/eval-suite.yml']
  schedule:
    - cron: '0 6 * * *'

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Eval Suite
        run: ./skills/agent-eval-framework/run-eval.sh
      - name: Check Threshold
        run: |
          python3 skills/agent-eval-framework/analyze-results.py --min-reliability 0.85
```

### Pre-commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash
if git diff --cached --name-only | grep -qE '^memory/|^skills/'; then
    ./skills/agent-eval-framework/run-eval.sh --quick || exit 1
fi
```

---

## Iteration Workflow

```
┌─────────────────┐
│  Run Eval Suite │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  < 90% Pass?    │──No──►┌──────────────────┐
└────────┬────────┘       │  Record Baseline │
         │ Yes            └──────────────────┘
         ▼
┌─────────────────┐
│ Identify Top 3  │
│ Failure Types   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Fix Context/    │
│ Docs/Prompts    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Add Regression  │
│ Tests for Fail  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Re-run Eval     │
└─────────────────┘
```

---

## Success Criteria

**Week 1:**
- [ ] 20 test cases defined
- [ ] Runner script functional
- [ ] Baseline reliability measured (expect 40-60%)

**Week 2:**
- [ ] CI integration working
- [ ] Daily automated runs
- [ ] Reliability ≥70%

**Month 1:**
- [ ] Reliability ≥90% sustained
- [ ] Production failures auto-converted to test cases
- [ ] Context change governance enforced

---

## References

- [nao Labs Context Engineering Playbook](https://docs.getnao.io/nao-agent/context-engineering/playbook)
- [nao Labs Evaluation Guide](https://docs.getnao.io/nao-agent/context-engineering/evaluation)
- [Anthropic Self-Service Analytics](https://claude.com/blog/how-anthropic-enables-self-service-data-analytics-with-claude)
