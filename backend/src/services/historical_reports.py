import os
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

REPORTS_DIR = os.path.join(os.getcwd(), 'data', 'reports')
HISTORY_DIR = os.path.join(REPORTS_DIR, 'history')
PERFORMANCE_DIR = os.path.join(REPORTS_DIR, 'performance')

# Ensure directories exist
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(PERFORMANCE_DIR, exist_ok=True)

async def _condense_content(prompt_text: str) -> str:
    """Uses a fast LLM to condense context."""
    try:
        from src.llms.llm import get_llm_by_type
        from langchain_core.messages import HumanMessage, SystemMessage
        
        # Use the basic, cheaper model for summarization tasks
        llm = get_llm_by_type("basic")
        
        messages = [
            SystemMessage(content="You are a data synthesis engine. Condense the following report into a dense, highly factual summary. Maintain all key metrics, patterns, and critical takeaways. Output raw markdown without conversational filler."),
            HumanMessage(content=prompt_text)
        ]
        
        response = await llm.ainvoke(messages)
        return str(getattr(response, "content", response))
    except Exception as e:
        logger.error(f"Failed to condense content: {e}")
        return ""

def update_symbol_rolling_summary(ticker: str, new_report_content: str):
    """
    Called at 5 PM. Condenses the most recent Symbol Analysis Report into the rolling summary.
    """
    summary_path = os.path.join(HISTORY_DIR, f"Historical_Summary_{ticker.upper()}.md")
    
    existing_summary = ""
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            existing_summary = f.read()

    # If it's too big, we condense it. For now, we ask the LLM to integrate the new report.
    prompt = f"""
Existing Historical Summary for {ticker}:
{existing_summary if existing_summary else "No previous history."}

New Analysis Report Generated Today:
{new_report_content}

Integrate the new analysis into the existing historical summary. Create a cohesive, rolling context of the symbol's performance, setups, and key levels. Remove obsolete data but retain pattern recognition over time.
    """
    
    # We spawn it in the background if called synchronously, or just run it via asyncio.run if in thread
    async def _run():
        condensed = await _condense_content(prompt)
        if condensed:
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(condensed)
            logger.info(f"Updated Historical Symbol Summary for {ticker}")
            
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())


def update_performance_rolling_summary(new_report_content: str):
    """
    Condenses the daily post-mortem into a rolling trader performance history.
    """
    summary_path = os.path.join(PERFORMANCE_DIR, "Trader_Performance_History.md")
    
    existing_summary = ""
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            existing_summary = f.read()

    prompt = f"""
Existing Trader Performance History:
{existing_summary if existing_summary else "No previous history."}

Today's Post-Mortem Report:
{new_report_content}

Integrate today's performance into the rolling performance history. Focus on recurring mistakes, emotional patterns, strategy adherence, and ongoing strengths/weaknesses. Keep it dense and actionable for future reference.
    """
    
    async def _run():
        condensed = await _condense_content(prompt)
        if condensed:
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(condensed)
            logger.info("Updated Trader Performance History")
            
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())


def get_historical_symbol_summary(ticker: str) -> str:
    """Returns the rolling historical summary for a symbol to be injected into state."""
    summary_path = os.path.join(HISTORY_DIR, f"Historical_Summary_{ticker.upper()}.md")
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def get_trader_performance_summary() -> str:
    """Returns the rolling trader performance summary to be injected into post-mortems."""
    summary_path = os.path.join(PERFORMANCE_DIR, "Trader_Performance_History.md")
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def write_obsidian_daily_report(content: str):
    """Writes the raw Daily Trading Report to the Obsidian Journal vault."""
    try:
        from src.tools.journal import _get_obsidian_config
        vault_path, journal_dir = _get_obsidian_config(None)
        
        if not vault_path:
            logger.error("Obsidian vault path not configured for Daily Trading Report")
            return
        full_journal_dir = os.path.join(vault_path, journal_dir)
        reports_dir = os.path.join(full_journal_dir, "Daily Reports")
        os.makedirs(reports_dir, exist_ok=True)
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join(reports_dir, f"Daily_PostMortem_{date_str}.md")
        
        # We replace the file if it exists, since it's the 5 PM raw post mortem
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Wrote raw Daily PostMortem to Obsidian: {file_path}")
    except Exception as e:
        logger.error(f"Failed to write Obsidian report: {e}")


def parse_daily_journal_file(date_str: str) -> dict:
    """
    Parses today's daily journal markdown file from Obsidian to extract self-assessment grades and raw notes body.
    """
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
    
    data = {
        "date_str": date_str,
        "grades": {
            "prep": 3,
            "sleep": 3,
            "mood": 3,
            "energy": 3,
            "confidence": 3,
            "performance": "C"
        },
        "markdown": ""
    }
    
    if not os.path.exists(file_path):
        template = f"# Daily Trading Report - {date_str}\n\n"
        template += "###  Targeted Candidates\n- \n\n"
        template += "###  Morning Session Notes\n- \n\n"
        template += "###  Risk Multipliers (VIX/Gamma)\n- \n"
        data["markdown"] = template
        return data
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Failed to read journal file: {e}")
        return data

    import re
    import yaml
    
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if match:
        yaml_text = match.group(1)
        body_text = match.group(2)
        try:
            frontmatter = yaml.safe_load(yaml_text) or {}
            if isinstance(frontmatter, dict):
                data["grades"]["prep"] = int(frontmatter.get("prep", 3))
                data["grades"]["sleep"] = int(frontmatter.get("sleep", 3))
                data["grades"]["mood"] = int(frontmatter.get("mood", 3))
                data["grades"]["energy"] = int(frontmatter.get("energy", 3))
                data["grades"]["confidence"] = int(frontmatter.get("confidence", 3))
                data["grades"]["performance"] = str(frontmatter.get("performance", "C"))
        except Exception as e:
            logger.error(f"Error parsing frontmatter YAML: {e}")
        data["markdown"] = body_text.strip()
    else:
        data["markdown"] = content.strip()
        
    return data


def save_daily_journal_file(date_str: str, grades: dict, body_markdown: str):
    """
    Saves the daily journal file in the Obsidian vault with grades stored as YAML frontmatter.
    """
    try:
        from src.tools.journal import _get_obsidian_config
        vault_path, journal_dir = _get_obsidian_config(None)
    except Exception:
        vault_path, journal_dir = None, None
        
    if not vault_path:
        vault_path = os.environ.get("OBSIDIAN_VAULT_PATH", r"C:\github\obsidian-vault")
    if not journal_dir:
        journal_dir = os.environ.get("OBSIDIAN_JOURNAL_DIR", "Journals")
        
    full_journal_dir = os.path.join(vault_path, journal_dir)
    os.makedirs(full_journal_dir, exist_ok=True)
    file_path = os.path.join(full_journal_dir, f"Daily_Trading_Report_{date_str}.md")
    
    import yaml
    frontmatter = {
        "prep": int(grades.get("prep", 3)),
        "sleep": int(grades.get("sleep", 3)),
        "mood": int(grades.get("mood", 3)),
        "energy": int(grades.get("energy", 3)),
        "confidence": int(grades.get("confidence", 3)),
        "performance": str(grades.get("performance", "C")),
        "timestamp": datetime.now().isoformat()
    }
    
    yaml_str = yaml.safe_dump(frontmatter, sort_keys=False)
    content = f"---\n{yaml_str}---\n\n{body_markdown.strip()}\n"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Saved daily journal with grades to {file_path}")


def get_recent_grades_trend(date_str: str, limit_days: int = 7) -> str:
    """
    Scans the daily journals directory to retrieve self-assessment grades for the last limit_days entries.
    """
    try:
        from src.tools.journal import _get_obsidian_config
        vault_path, journal_dir = _get_obsidian_config(None)
    except Exception:
        vault_path, journal_dir = None, None
        
    if not vault_path:
        vault_path = os.environ.get("OBSIDIAN_VAULT_PATH", r"C:\github\obsidian-vault")
    if not journal_dir:
        journal_dir = os.environ.get("OBSIDIAN_JOURNAL_DIR", "Journals")
        
    full_journal_dir = os.path.join(vault_path, journal_dir)
    if not os.path.exists(full_journal_dir):
        return "No previous grade history found."
        
    import glob
    import re
    import yaml
    
    files = glob.glob(os.path.join(full_journal_dir, "Daily_Trading_Report_*.md"))
    if not files:
        return "No previous journal entries."
        
    pattern = r'Daily_Trading_Report_(\d{4}-\d{2}-\d{2})\.md'
    dated_files = []
    for f in files:
        m = re.search(pattern, os.path.basename(f))
        if m:
            f_date = m.group(1)
            if f_date <= date_str:
                dated_files.append((f_date, f))
                
    dated_files.sort(key=lambda x: x[0], reverse=True)
    prev_files = [f for d, f in dated_files if d < date_str][:limit_days]
    if not prev_files:
        return "No previous entries to establish trend."
        
    trend_lines = []
    prev_files.reverse()
    for f in prev_files:
        f_date = re.search(pattern, os.path.basename(f)).group(1)
        try:
            with open(f, "r", encoding="utf-8") as file:
                content = file.read()
            match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
            if match:
                yaml_text = match.group(1)
                fm = yaml.safe_load(yaml_text) or {}
                if isinstance(fm, dict):
                    prep = fm.get("prep", 3)
                    sleep = fm.get("sleep", 3)
                    mood = fm.get("mood", 3)
                    energy = fm.get("energy", 3)
                    confidence = fm.get("confidence", 3)
                    perf = fm.get("performance", "C")
                    trend_lines.append(f"- **{f_date}**: Prep={prep}/5, Sleep={sleep}/5, Mood={mood}/5, Energy={energy}/5, Confidence={confidence}/5, Grade={perf}")
        except Exception:
            pass
            
    return "\n".join(trend_lines) if trend_lines else "No previous grade history parsed."


def synthesize_journal_and_assessment(date_str: str, grades: dict, raw_notes: str, post_mortem_text: str = None) -> tuple[str, str]:
    """
    Invokes the LLM to synthesize raw Daily Journal notes and self-assessment grades
    into two sections: 'Trader Notes' (polished personal diary entry) and
    'Self Assessment' (rolling-context mindset coaching).
    """
    try:
        from src.llms.llm import get_llm_by_type
        from langchain_core.messages import HumanMessage, SystemMessage
        llm = get_llm_by_type("basic")
    except Exception as e:
        logger.error(f"Failed to load LLM for synthesis: {e}")
        return "", ""
        
    history_summary = get_trader_performance_summary()
    trends_summary = get_recent_grades_trend(date_str, limit_days=7)
    
    notes_prompt = f"""
You are a journaling companion for a professional trader.
Take their raw, informal daily trading notes and self-assessment grades, and synthesize them into a clean, friendly, reflective journal entry written in the first person ("I").
Correct grammar, improve formatting, and make it read like a cohesive personal diary entry of the day's experiences.

Trader's Self-Assessment Grades:
- Prep: {grades.get('prep', 3)}/5
- Sleep: {grades.get('sleep', 3)}/5
- Mood: {grades.get('mood', 3)}/5
- Energy: {grades.get('energy', 3)}/5
- Confidence: {grades.get('confidence', 3)}/5
- Overall Execution Grade: {grades.get('performance', 'C')}

Raw Daily Journal Notes:
\"\"\"
{raw_notes}
\"\"\"

Output only the synthesized markdown journal body. Keep it reflective, constructive, and friendly. Do not add any greeting, intro, or wrap-up conversation.
"""
    
    assessment_prompt = f"""
You are an expert trading coach and performance psychologist.
Analyze today's trading notes, self-assessment grades, and today's post-mortem execution details, in the context of the trader's historical performance history and recent grade trends.

Today's Grades:
- Prep: {grades.get('prep', 3)}/5, Sleep: {grades.get('sleep', 3)}/5, Mood: {grades.get('mood', 3)}/5, Energy: {grades.get('energy', 3)}/5, Confidence: {grades.get('confidence', 3)}/5
- Overall Execution Grade: {grades.get('performance', 'C')}

Recent Grade Trends (past 7 days):
{trends_summary}

Historical Performance Rolling Summary (recurring issues, patterns, strengths/weaknesses):
{history_summary if history_summary else "No historical performance summary recorded yet."}

Today's Trading Notes:
\"\"\"
{raw_notes}
\"\"\"

Today's Post-Mortem Report details (if available):
\"\"\"
{post_mortem_text if post_mortem_text else "No trades generated yet."}
\"\"\"

Based on this, write a Self Assessment report summarizing the trader's mindset/mood for the day, followed by a few paragraphs of encouragement, constructive feedback, and observations.
Specifically, note areas of concern, identify if they are repeating any recurring issues or patterns from the history/trends, point out where they might be slipping, and provide actionable observations.
Keep the tone direct, supportive, and analytical.
Output only the markdown content (do not write "## Self Assessment" heading, just write the paragraphs/bullets directly). Do not add any greeting, intro, or wrap-up conversation.
"""
    
    try:
        res_notes = llm.invoke([SystemMessage(content="You are a data synthesis engine."), HumanMessage(content=notes_prompt)])
        res_assess = llm.invoke([SystemMessage(content="You are an expert trading coach."), HumanMessage(content=assessment_prompt)])
        
        notes_md = str(getattr(res_notes, "content", res_notes)).strip()
        assess_md = str(getattr(res_assess, "content", res_assess)).strip()
        
        return notes_md, assess_md
    except Exception as e:
        logger.error(f"Failed to run LLM synthesis: {e}")
        return "", ""


def combine_reports(post_mortem: str, market_report: str, date_str: str = None) -> str:
    """Combines the Daily Post-Mortem Report, synthesized Trader Notes & Self Assessment, and the Daily Market Report."""
    pm_clean = (post_mortem or "").strip()
    mr_clean = (market_report or "").strip()
    
    if not date_str:
        import re
        match = re.search(r'\b\d{4}-\d{2}-\d{2}\b', pm_clean)
        if match:
            date_str = match.group(0)
        else:
            match = re.search(r'\b\d{4}-\d{2}-\d{2}\b', mr_clean)
            if match:
                date_str = match.group(0)
            else:
                date_str = datetime.now().strftime("%Y-%m-%d")
                
    # 1. Clean out previous combined components to get raw post-mortem
    import re
    pattern_mr = r'\n+---\n+(?=# Daily Market Report|## Top 10 Market Gainers|# Daily Market Report:)'
    split_mr = re.split(pattern_mr, pm_clean)
    cleaned_pm = split_mr[0].strip()
    
    # Strip any old synthesized sections
    cleaned_pm = re.split(r'\n+## (?:Trader Notes|Self Assessment|Subjective Experience|Notes)\b', cleaned_pm)[0].strip()
    
    # 2. Retrieve today's Daily Journal and synthesize sections
    notes_section = ""
    assessment_section = ""
    
    journal_data = parse_daily_journal_file(date_str)
    raw_notes = journal_data.get("markdown", "").strip()
    
    # Check if notes are non-empty and non-blank
    is_blank = not raw_notes or (
        "###  Targeted Candidates" in raw_notes and
        "###  Morning Session Notes" in raw_notes and
        raw_notes.count("- ") >= 3 and
        len(raw_notes.replace("###  Targeted Candidates", "").replace("###  Morning Session Notes", "").replace("###  Risk Multipliers (VIX/Gamma)", "").replace("-", "").replace("\n", "").replace(" ", "").replace("DailyTradingReport", "").replace(date_str, "")) < 10
    )
    
    if not is_blank and raw_notes:
        grades = journal_data.get("grades", {})
        synthesized_notes, synthesized_assessment = synthesize_journal_and_assessment(date_str, grades, raw_notes, cleaned_pm)
        
        if synthesized_notes:
            notes_section = f"## Trader Notes\n\n{synthesized_notes}"
        if synthesized_assessment:
            assessment_section = f"## Self Assessment\n\n{synthesized_assessment}"
            
    final_pm = cleaned_pm
    if notes_section:
        final_pm += "\n\n" + notes_section
    if assessment_section:
        final_pm += "\n\n" + assessment_section
        
    if mr_clean:
        return final_pm + "\n\n---\n\n" + mr_clean
    else:
        return final_pm


def sync_combined_report_files(date_str: str, combined_content: str, has_market_report: bool = False):
    """
    Synchronizes the combined report content across the performance cache, Obsidian reports, and market reports archive.
    """
    # 1. Save to performance cache file
    perf_path = os.path.join(PERFORMANCE_DIR, f"Daily_PostMortem_{date_str}.md")
    try:
        with open(perf_path, "w", encoding="utf-8") as f:
            f.write(combined_content)
        logger.info(f"Saved combined post-mortem cache: {perf_path}")
    except Exception as e:
        logger.error(f"Failed to save performance cache file: {e}")
        
    # 2. Save to Obsidian daily reports directory
    write_obsidian_daily_report(combined_content)
    
    # 3. Save to market reports archive if there is market report content
    if has_market_report:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        out_dir = os.path.join(base_dir, "data", "archive", "daily_market_reports")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"report_{date_str}.md")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(combined_content)
            logger.info(f"Saved combined market report archive: {out_path}")
        except Exception as e:
            logger.error(f"Failed to save market report archive: {e}")
            
        # Update Obsidian market report copy
        try:
            from src.tools.journal import _get_obsidian_config
            vault_path, _ = _get_obsidian_config(None)
            if vault_path:
                vault_reports_dir = os.environ.get("VLI_REPORTS_ROOT")
                if not vault_reports_dir:
                    vault_reports_dir = os.path.join(vault_path, "_cobalt", "Reports")
                
                vault_today_dir = os.path.join(vault_reports_dir, date_str)
                os.makedirs(vault_today_dir, exist_ok=True)
                vault_out_path = os.path.join(vault_today_dir, f"{date_str} Daily Market Report.md")
                with open(vault_out_path, "w", encoding="utf-8") as f:
                    f.write(combined_content)
                logger.info(f"Saved combined market report in Obsidian: {vault_out_path}")
        except Exception as e:
            logger.error(f"Failed to update Obsidian market report: {e}")

