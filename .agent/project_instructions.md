# Project Guidelines: Cobalt Multiagent

## Design & Documentation Rules
1. **Implementation Plans**: All final implementation plans must be stored in the `docs/design` folder. Don't keep multiple copies of implementation plans for the same feature.
2. **Lifecycle States**:
   - Plans awaiting review or currently in-progress should be stored in `docs/design/pending/`.
   - Once a plan is fully approved and implemented, it should be moved to the root of `docs/design/`.
3. **Execution Boundary**: Do NOT proceed with implementation code changes until the user explicitly issues the command: **"proceed WITH IMPLEMENTATION"**. All other approvals refer only to updating the design documents. The exception is the word 'go'; this word means the design mode is complete and you can proceed with implementation 
4. **Pine Script Storage**: Save all Pine Script files (`.pine`) to a dedicated folder under `scripts/pine/` instead of placing them directly in the root of the `scripts/` directory.
5. **Bug Fix Verification**: Always create/update a self-contained reproduction test (e.g. in `tests/unit/`) to verify a bug fix. Do NOT report completion until the fix is verified as robust by the test.
6. **Preferred Standalone Testing**: Always prefer a simple standalone test to verify fixes over using the VLI dashboard. Exceptions include tests which rely on screen grabs or UX elements, or if the user specifically asks for the dashboard to be used.
7. **Browser Test Freshness**: When testing new features via the browser on the live dashboard, ALWAYS ensure the backend server is running the latest code. Explicitly kill any existing background processes holding port 8000 and restart the server before triggering the UI test to prevent rogue ghost instances from executing outdated logic.
8. **VLI Session Dashboard URL**: When requested to run tests on the 'VLI session dashboard', always target the dashboard at `http://localhost:8000/VLI_session_dashboard.html`.


## MANDATORY FOR BUG FIXES
Due to a high number of 'hallucinated fixes', all AI generated code changes must be fully tested before returning a 'fixed' summary to the user. To determine which test to run, refer to the local chat context to determine which one to run. If no valid test exists, then create one and ensure a passing result.

**Unbreakable TDD Sequence for Code Modifications:**
1. **Test Creation BEFORE Modification (Red Phase):** Before using code-editing tools (`replace_file_content` or `write_to_file`), first write a self-contained, automated test script (e.g., in `tests/unit/`) that explicitly tests the interface and expected output.
2. **Forced Failure:** Run that test script and verify that it fails, proving that the test accurately captures the broken state.
3. **Implementation (Green Phase):** Only after a proven failure will you modify the actual source code to implement the fix.
4. **Automated Verification:** Run the exact same test script and achieve a clean, automated pass. Ad-hoc `python -c` terminal one-liners to manually read output files are permanently banned as "proof" of a fix.

## Operational Accuracy & Verification Protocol
1. **Data Provenance Tracing:** Never assume the active generation engine based on filenames. Always start at the target output (e.g., final JSON cache, UI view) and trace the execution path backwards (checking config, env vars, and app routing) before modifying code.
2. **Mandatory Exhaustive Searching:** When modifying UI or configuration logic, ALWAYS use full codebase searches (e.g., `grep_search`) to guarantee identical logic blocks aren't duplicated elsewhere in the file.
3. **Strict Test Environments:** When running manual verification tests from the terminal, always verify the Current Working Directory (`Cwd`). Tests must execute in the exact environment and path context as the live application to prevent silent writes to orphaned directories.
4. **Data Over Code Validation:** Do not rely exclusively on terminal exit codes. If a user reports an issue persists, immediately inspect the raw output file (e.g., the JSON data or Markdown file) to verify the data integrity before analyzing the Python logic.
5. **Stateful Reloading Awareness:** If a bug fix involves modifying memory-resident global structures (e.g., caches, singletons, `asyncio.Semaphore` instances), the fix is NOT complete until the backend server is restarted. I must explicitly instruct the user to restart their server processes to flush the stale state.
6. **End-to-End Execution Validation:** Never assume a code patch is successful based on static analysis alone. If an error is triggered by a specific pipeline command, I must write an automated test script that directly invokes that exact pipeline (e.g., calling `_invoke_vli_agent`) to prove the exception is truly resolved before reporting success.
7. **Mandatory API Back-off Logic:** All outbound network and third-party API requests (e.g., YFinance, Alpha Vantage, Web Search) MUST be wrapped in resilient exponential back-off logic (such as using the `tenacity` library) to protect against rate limits (HTTP 429) and transient timeouts, especially during batch scanning operations.
8. **Pipeline Dependency Synchronization:** Whenever modifying a core pipeline constraint (e.g., changing data schemas, altering filter thresholds, or modifying schedules), I MUST explicitly trace the execution path fully forwards and backwards through the codebase. All downstream consumers and upstream producers MUST be validated and updated simultaneously to prevent pipeline desynchronization and infinite loops. I cannot stop at the first location that seems to solve the problem.
