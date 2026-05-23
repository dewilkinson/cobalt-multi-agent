---
description: Send a raw string verbatim to the local VLI backend without agentic processing
---
# VLI Headless Passthrough

This workflow allows you to talk to your local VLI backend (running on 127.0.0.1:8000) directly from Gemini Chat without the IDE AI trying to intercept, analyze, or write scripts to fulfill your question yourself.

1. Extract the user's question perfectly from the prompt following the `/vli` token.
2. Use the `run_command` tool to execute the following command:
```bash
python scripts/call_vli.py '<user_question_text>'
```
*(Make sure your working directory is `C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\backend`. Also note the single quotes around the question to prevent PowerShell eating dollar signs for Tickers!)*
    
3. Print out the raw stdout exactly as returned from the VLI.
