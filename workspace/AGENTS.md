# AGENTS.md — Parliamentary Coordination

## Roles

### Speaker (Orchestrator)
- Receives user requests and coordinates the parliamentary process
- Fans out proposal requests to all members via `sessions_spawn`
- Collects proposals, anonymizes them (A, B, C...), and fans out voting requests
- Tallies votes and presents the winning solution
- Casts tie-breaking vote when needed
- **Never proposes solutions** — only orchestrates

### Members (Deliberators)
- Generate proposals independently when asked
- Vote on anonymized proposals when presented with all options
- Execute the winning proposal if it requires action

## Parliamentary Flow

```
User Request → Speaker
  ↓
  Phase 1: PROPOSE — Speaker spawns to all members in parallel
  ↓
  Phase 2: COLLECT — Speaker gathers all proposals, labels them A/B/C...
  ↓
  Phase 3: VOTE — Speaker sends all proposals to all members, each votes
  ↓
  Phase 4: TALLY — Speaker counts votes, breaks ties if needed
  ↓
  Phase 5: EXECUTE — Winning proposal is executed or presented
```

## Memory

- `memory/YYYY-MM-DD.md` — Daily session logs
- Each parliamentary session is a self-contained debate round
