# Design Plan - Daily Journal Syncing

This plan details the changes required to ensure that EOD journal entries saved via the Journalling Module page are written/synced to the daily journal files (`{date_str} Daily Journal.md`) in both the Obsidian vault and the VLI reports folder.

## Proposed Changes

### Backend - Service Layer

We will update the `save_daily_journal_file` function in `src/services/historical_reports.py` to also write to the `{date_str} Daily Journal.md` files in both the Obsidian vault and the VLI reports folder.

#### [MODIFY] [historical_reports.py](file:///c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/src/services/historical_reports.py)

- Add a function `save_daily_journal_note(date_str: str, grades: dict, synthesized_notes: str, synthesized_assessment: str)` to write/update the daily journal files in the new format containing the title, today's metrics, polished reflections, and mindset coaching.
- Call this function inside `save_synthesized_feedback_to_journal` and in POST `/api/vli/journal/{date_str}` to write/update:
  1. Obsidian daily journal: `{vault_path}/{journal_dir}/{date_str} Daily Journal.md`
  2. VLI daily journal: `{vli_reports_root}/{date_str}/{date_str} Daily Journal.md`
  3. VLI reports root daily journal: `{vli_reports_root}/{date_str} Daily Journal.md`

## Verification Plan

### Automated Tests
- We will write an automated unit test `tests/unit/test_daily_journal_sync.py` that calls `save_daily_journal_note`, verifies that the target files are updated in both Obsidian and VLI folders, and checks that the written content matches the daily consistent metrics/synthesis structure.

```bash
pytest tests/unit/test_daily_journal_sync.py
```
