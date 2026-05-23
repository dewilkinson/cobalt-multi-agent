# Implementation Plan - VLI Intent-Based Routing Refactor

This plan refactors the VLI Spine routing from simple keyword triggers (like "smc") to structural intent detection (**Question** vs **Command**).

## User Review Required

> [!IMPORTANT]
> The routing logic will now follow the **Question Mark Rule**:
> - **Query Presence**: Any request containing a `?` is explicitly a **Query** and will be routed to the **Synthesizer** (High-Fidelity Research) for institutional context.
> - **Command Presence**: A command will **not** include a question mark. If it does not contain a `?`, it is treated as a tactical command and routed to the **Analyst** nodes for tool execution.
> - **Precedence**: The presence of a `?` overrides any tactical keywords (like "smc" or "rsi").

## Proposed Changes

### VLI Spine Routing Logic

#### [MODIFY] [vli.py](file:///C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/src/graph/nodes/vli.py)

- **Define Semantic Intent Buckets**:
  - `QUESTION_WORDS`: `["what", "how", "why", "describe", "define", "meaning", "mean", "explain", "info"]`
  - `ADVISORY_WORDS`: `["recommend", "should i", "can i", "what if", "how about"]`
  - `STRATEGY_KEYWORDS`: `["outlook", "strategy", "approach", "behavior", "macro", "scenario"]`
- **Refined Intent Detection**:
  - **Priority 1 (Absolute)**: If the query contains `?` -> Force **SYNTHESIZER**.
  - **Priority 2 (Strategy/Advisory)**: If it contains strategy or advisory words without `?` -> Force **SYNTHESIZER**.
  - **Priority 3 (Tactical)**: If it is an Imperative Command (no `?`) or targets a specific ticker context -> Force **ANALYST/SMC_ANALYST**.

## Open Questions

- No open questions. The "Question Mark Rule" is definitive.

## Verification Plan

### Automated Tests
- Run `scratch/trace_diagnostic.py` to verify the following routing paths:
  1. `"describe what smc means"` -> **Synthesizer**
  2. `"get NVDA smc analysis"` -> **SMC Analyst**
  3. `"what is the strategy for this week?"` -> **Synthesizer**
  4. `"recommend a trade approach"` -> **Synthesizer**

### Manual Verification
- Confirm that conceptual SMC reports no longer include hallucinated technical data points ($150 targets, etc.).
- Verify the `VLI_Spine` logs in the UI reflect the correct node forced (Research vs Audit).
