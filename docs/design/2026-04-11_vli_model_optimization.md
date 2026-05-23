# Implementation Plan - VLI Model Optimization

This plan re-configures the agent-to-model mapping (`AGENT_LLM_MAP`) to balance intelligence, latency, and the 250-call daily quota for Gemini 3 Pro.

## Proposed Model Architecture

| Node | Model Tier | Choice | Rationale |
| :--- | :--- | :--- | :--- |
| **Parser** | `core` | **Gemma 4** | Offloads high-frequency chat and intent-routing to local hardware. |
| **Coordinator / Planner** | `reasoning` | **Gemini 3 Pro** | Highest logic density. Strategy failures break the entire graph. |
| **Analyst / SMC Analyst** | `reasoning` | **Gemini 3 Pro** | Expert-level technical interpretation requires deep reasoning. |
| **Reporter** | `basic` | **Gemini 3 Flash** | Optimal for high-throughput text synthesis and low final latency. |
| **Synthesizer** | `basic` | **Gemini 3 Flash** | High volume deep-research tasks would deplete Pro quota instantly. |
| **Risk / Portfolio / Scout**| `basic` | **Gemini 3 Flash** | Deterministic tool-calling. Intelligence headroom is not required. |

## Proposed Changes

### [VLI Configuration]

#### [MODIFY] [agents.py](file:///C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/src/config/agents.py)
Update the `_BASE_AGENT_LLM_MAP` with the new optimized tiers.

```python
_BASE_AGENT_LLM_MAP: dict[str, LLMType] = {
    "coordinator": "reasoning",
    "parser": "core",           # [NEW] Offload to local Gemma 4
    "planner": "reasoning",
    "synthesizer": "basic",
    "coder": "basic",
    "reporter": "basic",
    "podcast_script_writer": "basic",
    "ppt_composer": "basic",
    "prose_writer": "basic",
    "prompt_enhancer": "basic",
    "scout": "basic",
    "journaler": "basic",
    "portfolio_manager": "basic", # [DOWNGRADE] Save reasoning quota
    "risk_manager": "basic",      # [DOWNGRADE] Save reasoning quota
    "analyst": "reasoning",
    "smc_analyst": "reasoning",
    "imaging": "vision",
    "vision_specialist": "vision",
    "system": "basic",
}
```

## Verification Plan

### Automated Verification
1.  **Parser Check**: Send a simple "Hello" to the dashboard and verify in the backend logs that `Gemma 4` (via Ollama) is initialized.
2.  **SMC Check**: Run "Get full SMC analysis for NVDA" and verify in logs that:
    - **Step 1 (Parser)** uses Gemma 4.
    - **Step 2 (Coordinator)** uses Gemini Pro.
    - **Step 3 (SMC Analyst)** uses Gemini Pro.
    - **Step 4 (Reporter)** uses Gemini Flash.

### Manual Verification
- Monitor the daily quota usage in the Google Cloud console (if accessible) or track the "REASONING" tier invocations in the `VLI_Raw_Telemetry.md` file.
