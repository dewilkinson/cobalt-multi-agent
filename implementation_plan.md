# Implementation Plan - VLI Intent-Based Routing Refactor

This plan refactors the VLI Spine routing from simple keyword triggers (like "smc") to structural intent detection (**Question** vs **Command**).

## User Review Required

> [!IMPORTANT]
> This structural shift prioritizes sentence architecture over keyword presence.
> - **Questions/Conceptual Queries**: (e.g., "What is SMC?", "Describe RSI") will always be routed to the **Synthesizer** (High-Fidelity Research) node.
> - **Commands/Tactical Queries**: (e.g., "NVDA SMC Analysis", "Get price for AMD") will continue to be routed to the **Analyst** nodes for tool execution.
> - **Shared Keywords**: Keywords like "smc" or "rsi" will no longer force a technical audit if they appear within a question-based structure (started with "What", "How", etc.).

## Proposed Changes

### VLI Spine Routing Logic

#### [MODIFY] [vli.py](file:///C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/src/graph/nodes/vli.py)

- **Define Semantic Intent Buckets**:
  - `QUESTION_WORDS`: `["what", "how", "why", "describe", "define", "meaning", "mean", "explain", "info"]`
  - `ADVISORY_WORDS`: `["recommend", "should i", "can i", "what if", "how about"]`
  - `STRATEGY_KEYWORDS`: `["outlook", "strategy", "approach", "behavior", "macro", "scenario"]`
- **Refined Intent Detection**:
  - Implementation of `is_question` logic based on leading words or the `?` suffix.
  - Implementation of `is_conceptual_request` that detects when technical terms are used without imperative verbs.
- **Guardrail Priority Update**:
  - **Priority 1**: If it is a Question, Advisory, or Strategy query -> Force **SYNTHESIZER**.
  - **Priority 2**: If it is an Imperative Command (e.g., "Analyze", "Get") or targets a specific ticker context -> Force **ANALYST/SMC_ANALYST**.

## Open Questions

- Should the `?` symbol alone always force the Synthesizer path, or should we still allow "Price of NVDA?" to go to the fast-path Analyst? (Proposal: Treat trailing `?` as a secondary hint but prioritize imperative start-words for ticker data).

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
