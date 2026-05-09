<!--
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0
-->

# Cobalt Multiagent (CMA) Test Specification

This document outlines the test suite for the Cobalt Multiagent system, including unit tests and integration workflows.

##  Unit Tests

### 1. Graph Modules
| Test Name | Module | Description | Expected Input | Expected Output |
| :--- | :--- | :--- | :--- | :--- |
| `test_start_node_router` | `builder.py` | Routes initial entry point based on background investigation flag. | `State` with `enable_background_investigation` True/False. | `"vli_research_module"` or `"parser"`. |
| `test_continue_to_running_scheduler` | `builder.py` | Decides next node based on current plan progress. | `State` with `current_plan` (Plan object). | Correct node name (e.g., `"analyst"`, `"scout"`, `"reporter"`). |
| `test_scout_node` | `nodes.py` | Performs sanitized context gathering via Scout primitives. | `State` with `research_topic`. | `State` update with `observations`. |

### 2. Analytical Primitives (Specialized Agents)
| Test Name | Module | Description | Expected Input | Expected Output |
| :--- | :--- | :--- | :--- | :--- |
| `test_analyst_restriction` | `nodes.py` / `analyst.md` | Ensures Analyst does not use `yfinance` directly. | Plan involving financial analysis. | Verify no `yfinance` calls in code execution. |
| `test_analyst_verbosity` | `nodes.py` / `analyst.md` | Verifies filler suppression in low verbosity modes. | `State` with `verbosity=0`. | Output with zero conversational filler. |
| `test_scout_search` | `search.py` | Verifies sanitized search result output. | Search query via `fetch_web_search`. | Sanitized text (No scripts/HTML tags). |

### 3. Utility Primitives
| Test Name | Module | Description | Expected Input | Expected Output |
| :--- | :--- | :--- | :--- | :--- |
| `test_sanitize_content` | `text_utils.py` | Strips malicious code and excess markup from text. | Raw HTML/Script string. | Clean, play text. |

##  Integration Workflows (Real-Life Scenarios)

### Scenario A: High-Fidelity SMC Analysis
*   **Workflow**: VLI: Parser -> VLI: Coordinator -> VLI: Human Review -> VLI: Scheduler -> Analyst -> Reporter.
*   **Input**: "/cma analyze NVDA structural liquidity and FVG confluence."
*   **Success Criteria**: Final report contains SMC tables, no `yfinance` logs in Analyst REPL, and a finalized Obsidian summary.

### Scenario B: Background Investigation & Contextual Reporting
*   **Workflow**: VLI: Scout -> VLI: Parser -> VLI: Coordinator -> Reporter.
*   **Input**: "What happened to the yield curve today?" (with `enable_background_investigation: true`)
*   **Success Criteria**: `observations` contains sanitized news blurbs used by the Reporter.

##  Pre-Commit Hook
All tests are integrated into a single verification script located at `backend/scripts/verify_system.py`. This script must return a success code (0) before any code is committed.
