---
description: Ask the remote Deerflow server a question and save the response to Obsidian
---
# CMA (Chat Multi-Agent)

This workflow allows you to consult the remote Deerflow API easily from your Gemini editor chat, while automatically saving the results to your Obsidian vault.

1. First, check if `local_client/.env` exists. If not, inform the user to copy `local_client/.env.example` to `local_client/.env` and fill in their `OBSIDIAN_VAULT_PATH`.
2. Extract the user's question from the prompt.
3. Use the `run_command` tool to execute the following command:
```bash
python local_client/ask_deerflow.py "<user_question>"
```
4. Wait for the command to finish. **Do not** timeout early, as the Deerflow server may take a moment to research the answer.
5. Read the terminal output and present the final answer to the user in this chat.
6. Look at the stdout to confirm if the script successfully saved to Obsidian, and let the user know.
