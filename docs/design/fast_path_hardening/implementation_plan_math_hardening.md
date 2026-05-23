# Implementation Plan: Math Bypass Hardening

This plan fixes the issue where algebraic queries like `solve for x: 5x+10=35` occasionally skip the Fast-Path and trigger a 9s analytical report. We will implement "Hard-Force" logic in the Spine to prioritize direct algebraic results from the Parser.

## User Review Required

> [!IMPORTANT]
> This change forces a "Direct Exit" if the Parser provides an answer for an algebraic query, even if the model's `has_enough_context` status is set to `false`. This prevents the model's over-cautious planning from adding 8 seconds of unnecessary latency to simple math.

## Proposed Changes

### 1. Spine Logic: Algebraic Hard-Force

#### [MODIFY] [vli.py](file:///C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/src/graph/nodes/vli.py)
*   Update the `Layer 1: Parser Early-Exit` condition:
    *   **Check**: If `is_algebra` is `True` AND `plan_obj_a.direct_response` is not null/empty:
        *   Override `should_bypass` to `True`.
        *   Log: `[VLI_SPINE] Hard-forcing algebra bypass`.
    *   This ensures that if the Parser solved the problem, we return it instantly regardless of its own planning confidence.

### 2. Prompt Hardening: Direct Algebra Mandate

#### [MODIFY] [parser.md](file:///C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/src/prompts/parser.md)
*   **Update Rule**: "For algebraic equations (containing '=' or 'solve for'), you MUST perform the calculation yourself and provide the result in `direct_response`. You are FORBIDDEN from creating a multi-agent plan for math unless it involves external data fetching (e.g., 'What is Apple's PE ratio times 5?')."
*   **New Example**: Add an explicit JSON example for `solve for x: 5x+10=35` showing `direct_response: "x = 5"`.

## Verification Plan

### Automated Benchmark
- **Algebra Test**: "solve for x: 5x+10=35"
    - [x] Expected: Latency < 2.0s.
    - [x] Expected: Goto "reporter", skipping "coordinator".

### Manual Verification
- Test the same query in the VLI Dashboard. Confirm the result appears in the Chat window as a concise string, and the "Reports" window remains in "Awaiting Results" or stays clear.
