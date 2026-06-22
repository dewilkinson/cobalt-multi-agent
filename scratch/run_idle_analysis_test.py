import sys
import os
import asyncio
import logging

# Configure python path to load src correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

# Setup mock logging to console
logging.basicConfig(level=logging.INFO)

async def test_flow():
    # Evict today's report files for key candidates to force regeneration
    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "data", "reports"))
    print(f"Reports dir: {reports_dir}")
    
    # Let's evict a few reports to force run_idle_analysis to process them
    targets_to_evict = ["analyze_bbcp.md", "analyze_crdo.md", "analyze_spy.md", "analyze_qqq.md"]
    for t in targets_to_evict:
        p = os.path.join(reports_dir, t)
        if os.path.exists(p):
            print(f"Evicting existing report: {p}")
            os.remove(p)
            
    # Also evict today's daily briefing to force compilation
    from datetime import datetime
    today_str = datetime.now().strftime("%Y-%m-%d")
    briefing_path = os.path.join(reports_dir, today_str, f"{today_str} Daily Briefing.md")
    if os.path.exists(briefing_path):
        print(f"Evicting briefing: {briefing_path}")
        os.remove(briefing_path)

    # Now import and execute run_idle_analysis
    from src.server.app import run_idle_analysis
    
    print("\n--- Starting run_idle_analysis (manual_trigger=True) ---")
    # Set thinking_mode to false temporarily to speed up the test run
    os.environ["BYPASS_REASONING_MODEL"] = "true"
    
    # We run the wrapper directly
    await run_idle_analysis(manual_trigger=True)
    
    print("\n--- Verifying Results ---")
    
    # 1. Verify candidate reports were written
    for t in targets_to_evict:
        p = os.path.join(reports_dir, t)
        if os.path.exists(p):
            print(f"[SUCCESS] Generated candidate report: {t}")
            # Check content of report
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
                print(f"  First 200 chars: {content[:200].strip()}...")
                
                # Check for News Sentiment section and fallback text if news is not available
                if "Not available" in content:
                    print("  [SUCCESS] Report contains 'Not available' fallback.")
        else:
            print(f"[FAIL] Report NOT generated: {t}")
            
    # 2. Verify daily briefing was written
    if os.path.exists(briefing_path):
        print(f"[SUCCESS] Compiled Daily Briefing: {briefing_path}")
        with open(briefing_path, "r", encoding="utf-8") as f:
            content = f.read()
            print(f"  First 200 chars: {content[:200].strip()}...")
    else:
        print(f"[FAIL] Daily Briefing NOT compiled at: {briefing_path}")

if __name__ == "__main__":
    asyncio.run(test_flow())
