from src.services.inbox_rules import InboxRuleEngine
import os

engine = InboxRuleEngine("C:\\tmp")
test_file = "March 30, 2026.md"
proposal = engine._check_journal_rule(test_file)
print(f"Proposal: {proposal}")

test_file_iso = "2026-03-31 Action Plan.md"
proposal_iso = engine._check_action_plan_rule(test_file_iso)
print(f"Action Proposal: {proposal_iso}")
