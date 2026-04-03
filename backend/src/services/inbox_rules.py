# Cobalt Multiagent - Inbox Filing Rules
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>

import os
import re
from datetime import datetime
from typing import List, Dict, Optional, Any

class InboxRuleEngine:
    def __init__(self, vault_root: str):
        self.vault_root = vault_root
        self.inbox_dir = os.path.join("_cobalt", "inbox")
        self.journal_dir = "CMA journals"
        self.archive_dir = os.path.join("_cobalt", "archives", "action_plans")
        self.rules_enabled = True

    def get_inbox_proposals(self, file_list: List[str]) -> List[Dict[str, Any]]:
        """Analyze inbox files and return suggested filing actions."""
        if not self.rules_enabled:
            return []

        proposals = []
        for filename in file_list:
            # 1. Check for Daily Journal (e.g. March 30, 2026 or 2026-03-30)
            journal_proposal = self._check_journal_rule(filename)
            if journal_proposal:
                proposals.append(journal_proposal)
                continue

            # 2. Check for Action Plan (e.g. 2026-03-30 Action Plan.md)
            action_plan_proposal = self._check_action_plan_rule(filename)
            if action_plan_proposal:
                proposals.append(action_plan_proposal)

        return proposals

    def is_filing_candidate(self, filename: str) -> bool:
        """Check if a file matches any manual filing rule, ignoring engine enabled state."""
        return self._check_journal_rule(filename) is not None or self._check_action_plan_rule(filename) is not None

    def _check_journal_rule(self, filename: str) -> Optional[Dict[str, Any]]:
        """Detect and normalize Daily Journal files."""
        # Regex for common date formats like 'March 30, 2026' or '2026-03-30'
        # Group 1: Month Name, Group 2: Day, Group 3: Year
        date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})"
        iso_pattern = r"(\d{4})-(\d{2})-(\d{2})"

        match_date = re.search(date_pattern, filename, re.IGNORECASE)
        match_iso = re.search(iso_pattern, filename)

        target_date = None
        if match_date:
            try:
                dt = datetime.strptime(f"{match_date.group(1)} {match_date.group(2)} {match_date.group(3)}", "%B %d %Y")
                target_date = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        elif match_iso:
            target_date = f"{match_iso.group(1)}-{match_iso.group(2)}-{match_iso.group(3)}"

        if target_date:
            return {
                "original_name": filename,
                "suggested_name": f"{target_date}.md",
                "target_folder": self.journal_dir,
                "rule_name": "Daily Journal",
                "action_type": "move_journal"
            }
        return None

    def _check_action_plan_rule(self, filename: str) -> Optional[Dict[str, Any]]:
        """Detect and archive Action Plan files."""
        if "Action Plan" in filename:
            return {
                "original_name": filename,
                "suggested_name": filename,
                "target_folder": self.archive_dir,
                "rule_name": "Action Plan Archival",
                "action_type": "archive_plan"
            }
        return None

    def handle_collision(self, target_path: str) -> str:
        """Increment filename if it already exists in the target folder."""
        base_path, ext = os.path.splitext(target_path)
        counter = 1
        new_path = target_path
        
        while os.path.exists(new_path):
            new_path = f"{base_path} {counter}{ext}"
            counter += 1
        return new_path
