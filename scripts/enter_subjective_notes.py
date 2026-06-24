import os
import sys
import argparse
import subprocess
from datetime import datetime

# Add project root to path
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if base_dir not in sys.path:
    sys.path.append(base_dir)

def main():
    parser = argparse.ArgumentParser(description="Cobalt Journalling CLI fallback tool")
    parser.add_argument("--date", help="Date in YYYY-MM-DD format (defaults to today)")
    parser.add_argument("--prep", type=int, help="Preparation score (1-5)")
    parser.add_argument("--sleep", type=int, help="Sleep quality score (1-5)")
    parser.add_argument("--mood", type=int, help="Mood score (1-5)")
    parser.add_argument("--energy", type=int, help="Energy level score (1-5)")
    parser.add_argument("--confidence", type=int, help="Confidence level score (1-5)")
    parser.add_argument("--performance", help="Overall execution grade (A-F)")
    parser.add_argument("--notes", help="Notes text body directly (bypasses editor)")
    
    args = parser.parse_args()
    
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    
    from src.services.historical_reports import parse_daily_journal_file, save_daily_journal_file
    
    journal_data = parse_daily_journal_file(date_str)
    grades = journal_data["grades"]
    markdown = journal_data["markdown"]
    
    # Update grades if supplied
    if args.prep is not None: grades["prep"] = args.prep
    if args.sleep is not None: grades["sleep"] = args.sleep
    if args.mood is not None: grades["mood"] = args.mood
    if args.energy is not None: grades["energy"] = args.energy
    if args.confidence is not None: grades["confidence"] = args.confidence
    if args.performance is not None: grades["performance"] = args.performance
    
    if args.notes is not None:
        markdown = args.notes
        save_daily_journal_file(date_str, grades, markdown)
    else:
        save_daily_journal_file(date_str, grades, markdown)
        
        try:
            from src.tools.journal import _get_obsidian_config
            vault_path, journal_dir = _get_obsidian_config(None)
        except Exception:
            vault_path, journal_dir = None, None
            
        if not vault_path:
            vault_path = os.environ.get("OBSIDIAN_VAULT_PATH", r"C:\github\obsidian-vault")
        if not journal_dir:
            journal_dir = os.environ.get("OBSIDIAN_JOURNAL_DIR", "Journals")
            
        file_path = os.path.join(vault_path, journal_dir, f"Daily_Trading_Report_{date_str}.md")
        
        print(f"Opening daily journal file for editing: {file_path}")
        print("Please edit and save the file. LLM synthesis will trigger when you close the editor.")
        
        if sys.platform == "win32":
            subprocess.run(["notepad.exe", file_path])
        else:
            editor = os.environ.get("EDITOR", "nano")
            subprocess.run([editor, file_path])
            
        # Re-parse after editor closes
        journal_data = parse_daily_journal_file(date_str)
        grades = journal_data["grades"]
        markdown = journal_data["markdown"]
        
    print("\nTriggering LLM synthesis and post-mortem report compilation...")
    from src.services.historical_reports import PERFORMANCE_DIR
    post_mortem_path = os.path.join(PERFORMANCE_DIR, f"Daily_PostMortem_{date_str}.md")
    if os.path.exists(post_mortem_path):
        from src.services.historical_reports import combine_reports, sync_combined_report_files
        with open(post_mortem_path, "r", encoding="utf-8") as f:
            pm_content = f.read()
            
        import re
        pattern_mr = r'\n+---\n+(?=# Daily Market Report|## Top 10 Market Gainers|# Daily Market Report:)'
        parts = re.split(pattern_mr, pm_content)
        raw_pm = parts[0].strip()
        mr_part = parts[1].strip() if len(parts) > 1 else ""
        
        combined_content = combine_reports(raw_pm, mr_part, date_str=date_str)
        sync_combined_report_files(date_str, combined_content, has_market_report=bool(mr_part))
        print("Success! Synthesized notes and self-assessment have been folded into the post-mortem report.")
    else:
        print("No end-of-day post-mortem report exists yet. Journal file updated successfully.")

if __name__ == "__main__":
    main()
