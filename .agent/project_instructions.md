# Project Guidelines: Cobalt Multiagent

## Design & Documentation Rules
1. **Implementation Plans**: All final implementation plans must be stored in the `docs/design` folder.
2. **Lifecycle States**:
   - Plans awaiting review or currently in-progress should be stored in `docs/design/pending/`.
   - Once a plan is fully approved and implemented, it should be moved to the root of `docs/design/`.
3. **Execution Boundary**: Do NOT proceed with implementation code changes until the user explicitly issues the command: **"proceed WITH IMPLEMENTATION"**. All other approvals refer only to updating the design documents. The exception is the word 'go'; this word means the design mode is complete and you can proceed with implementation 
4. **Bug Fix Verification**: Always create/update a self-contained reproduction test (e.g. in `tests/unit/`) to verify a bug fix. Do NOT report completion until the fix is verified as robust by the test.
5. **Preferred Standalone Testing**: Always prefer a simple standalone test to verify fixes over using the VLI dashboard. Exceptions include tests which rely on screen grabs or UX elements, or if the user specifically asks for the dashboard to be used.
6. **Browser Test Freshness**: When testing new features via the browser on the live dashboard, ALWAYS ensure the backend server is running the latest code. Explicitly kill any existing background processes holding port 8000 and restart the server before triggering the UI test to prevent rogue ghost instances from executing outdated logic.
7. **VLI Session Dashboard URL**: When requested to run tests on the 'VLI session dashboard', always target the dashboard at `http://localhost:8000/VLI_session_dashboard.html`.
