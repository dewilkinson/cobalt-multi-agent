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

def clean_val(val: str) -> str:
    if not val:
        return ""
    val_stripped = val.strip()
    if val_stripped.startswith("[") and val_stripped.endswith("]"):
        try:
            import ast
            parsed = ast.literal_eval(val_stripped)
            if isinstance(parsed, list):
                text_parts = []
                for item in parsed:
                    if isinstance(item, dict):
                        text_parts.append(item.get("text", ""))
                    else:
                        text_parts.append(str(item))
                return "".join(text_parts).strip()
        except Exception:
            pass
    return val

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

def write_obsidian_daily_report(content: str, date_str: str = None):
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
        
        if not date_str:
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
        
    # Strip ## Agent Feedback section from markdown so editor doesn't show it
    raw_md = data.get("markdown", "")
    if "## Agent Feedback" in raw_md:
        import re
        data["markdown"] = re.split(r'\n+## Agent Feedback\b', raw_md)[0].strip()
        
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
    logger.info(f"Saved daily journal with grades to Obsidian: {file_path}")
    
    # Write to VLI reports folder
    try:
        vli_reports_root = os.environ.get("VLI_REPORTS_ROOT")
        if not vli_reports_root:
            default_root = os.path.join(os.getcwd(), "data", "reports")
            if not os.path.exists(os.path.join(os.getcwd(), "data")):
                default_root = os.path.join(os.getcwd(), "backend", "data", "reports")
            vli_reports_root = default_root
            
        os.makedirs(vli_reports_root, exist_ok=True)
        vli_file_path = os.path.join(vli_reports_root, f"Daily_Trading_Report_{date_str}.md")
        with open(vli_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Saved daily journal with grades to VLI reports folder: {vli_file_path}")
        
        # Also save to date subfolder in VLI reports root if applicable
        vli_date_dir = os.path.join(vli_reports_root, date_str)
        os.makedirs(vli_date_dir, exist_ok=True)
        vli_date_file_path = os.path.join(vli_date_dir, f"Daily_Trading_Report_{date_str}.md")
        with open(vli_date_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Saved daily journal with grades to VLI date reports folder: {vli_date_file_path}")
    except Exception as e:
        logger.error(f"Failed to sync daily journal to VLI reports directory: {e}")

def save_daily_journal_note(date_str: str, grades: dict, synthesized_notes: str, synthesized_assessment: str):
    """
    Saves the daily journal file in BOTH the Obsidian vault and the VLI reports folders.
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
        
    try:
        vli_reports_root = os.environ.get("VLI_REPORTS_ROOT")
        if not vli_reports_root:
            default_root = os.path.join(os.getcwd(), "data", "reports")
            if not os.path.exists(os.path.join(os.getcwd(), "data")):
                default_root = os.path.join(os.getcwd(), "backend", "data", "reports")
            vli_reports_root = default_root
    except Exception:
        vli_reports_root = r"C:\github\obsidian-vault\_cobalt\Reports"

    # Format the daily journal report following a consistent structure
    content = f"# {date_str} Daily Journal\n\n"
    content += "### Today's Metrics\n"
    content += f"* **Prep:** {grades.get('prep', 3)}/5\n"
    content += f"* **Sleep:** {grades.get('sleep', 3)}/5\n"
    content += f"* **Mood:** {grades.get('mood', 3)}/5\n"
    content += f"* **Energy:** {grades.get('energy', 3)}/5\n"
    content += f"* **Confidence:** {grades.get('confidence', 3)}/5\n"
    content += f"* **Overall Execution Grade:** {grades.get('performance', 'C')}\n\n"
    content += "---\n\n"
    content += "## Polished Reflections\n"
    content += f"{synthesized_notes.strip() if synthesized_notes else 'No notes synthesized yet.'}\n\n"
    content += "## Mindset Coaching\n"
    content += f"{synthesized_assessment.strip() if synthesized_assessment else 'No coaching synthesized yet.'}\n"

    # Save to Obsidian Journals
    try:
        full_journal_dir = os.path.join(vault_path, journal_dir)
        os.makedirs(full_journal_dir, exist_ok=True)
        obsidian_file = os.path.join(full_journal_dir, f"{date_str} Daily Journal.md")
        with open(obsidian_file, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Saved Daily Journal to Obsidian: {obsidian_file}")
    except Exception as e:
        logger.error(f"Failed to write Daily Journal to Obsidian: {e}")

    # Save to VLI reports folders
    try:
        os.makedirs(vli_reports_root, exist_ok=True)
        vli_file = os.path.join(vli_reports_root, f"{date_str} Daily Journal.md")
        with open(vli_file, "w", encoding="utf-8") as f:
            f.write(content)
            
        vli_date_dir = os.path.join(vli_reports_root, date_str)
        os.makedirs(vli_date_dir, exist_ok=True)
        vli_date_file = os.path.join(vli_date_dir, f"{date_str} Daily Journal.md")
        with open(vli_date_file, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Saved Daily Journal to VLI: {vli_file} and {vli_date_file}")
    except Exception as e:
        logger.error(f"Failed to write Daily Journal to VLI: {e}")

def save_synthesized_feedback_to_journal(date_str: str, synthesized_notes: str, synthesized_assessment: str):
    """
    Appends/updates the AI synthesized feedback in the user's Daily Journal note in Obsidian under '## Agent Feedback'.
    """
    try:
        journal_data = parse_daily_journal_file(date_str)
        grades = journal_data.get("grades", {})
        raw_notes = journal_data.get("markdown", "").strip()
        
        # Strip any old Agent Feedback from raw_notes to prevent duplicates
        import re
        raw_notes = re.split(r'\n+## Agent Feedback\b', raw_notes)[0].strip()
        
        feedback_parts = []
        if synthesized_notes:
            feedback_parts.append(f"### Polished Reflections\n{synthesized_notes}")
        if synthesized_assessment:
            feedback_parts.append(f"### Mindset Coaching\n{synthesized_assessment}")
            
        feedback_text = ""
        if feedback_parts:
            feedback_content = "\n\n".join(feedback_parts)
            feedback_text = f"\n\n## Agent Feedback\n\n{feedback_content}"
            
        body_content = f"{raw_notes}{feedback_text}"
        save_daily_journal_file(date_str, grades, body_content)
        logger.info(f"Successfully saved synthesized feedback to Daily Journal file for {date_str}")
        
        # Write to daily journal file as well
        save_daily_journal_note(date_str, grades, synthesized_notes, synthesized_assessment)
    except Exception as e:
        logger.error(f"Failed to save synthesized report to Daily Journal: {e}")


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

        def extract_content(res):
            content = getattr(res, "content", res)
            if isinstance(content, str):
                return content.strip()
            elif isinstance(content, list):
                return " ".join([b.get("text", "") if isinstance(b, dict) else str(b) for b in content]).strip()
            return str(content).strip()

        notes_md = clean_val(extract_content(res_notes))
        assess_md = clean_val(extract_content(res_assess))
        
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
    cleaned_pm = re.split(r'\n+## (?:Trader Notes|Self Assessment|Subjective Experience|Notes|Agent Feedback)\b', cleaned_pm)[0].strip()
    
    # 2. Retrieve today's Daily Journal and synthesize sections
    notes_section = ""
    feedback_section = ""
    
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
        import json
        preview_cache_path = os.path.join(PERFORMANCE_DIR, f"Daily_Journal_Preview_{date_str}.json")
        synthesized_notes = ""
        synthesized_assessment = ""
        
        if os.path.exists(preview_cache_path):
            try:
                with open(preview_cache_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    synthesized_notes = clean_val(cached_data.get("trader_notes", ""))
                    synthesized_assessment = clean_val(cached_data.get("self_assessment", ""))
            except Exception as e:
                logger.error(f"Error reading preview cache in combine_reports: {e}")
                
        if not synthesized_notes or not synthesized_assessment:
            grades = journal_data.get("grades", {})
            synthesized_notes, synthesized_assessment = synthesize_journal_and_assessment(date_str, grades, raw_notes, cleaned_pm)
            synthesized_notes = clean_val(synthesized_notes)
            synthesized_assessment = clean_val(synthesized_assessment)
            
            # Cache it
            try:
                os.makedirs(PERFORMANCE_DIR, exist_ok=True)
                with open(preview_cache_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "trader_notes": synthesized_notes or "",
                        "self_assessment": synthesized_assessment or ""
                    }, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Error caching in combine_reports: {e}")
        
        # Save the synthesized report to the Obsidian daily journal MD file
        save_synthesized_feedback_to_journal(date_str, synthesized_notes, synthesized_assessment)
        
        notes_section = f"## Trader Notes\n\n{raw_notes}"
        
        feedback_parts = []
        if synthesized_notes:
            feedback_parts.append(f"### Polished Reflections\n{synthesized_notes}")
        if synthesized_assessment:
            feedback_parts.append(f"### Mindset Coaching\n{synthesized_assessment}")
            
        if feedback_parts:
            feedback_content = "\n\n".join(feedback_parts)
            feedback_section = f"## Agent Feedback\n\n{feedback_content}"
            
    final_pm = cleaned_pm
    if notes_section:
        final_pm += "\n\n" + notes_section
    if feedback_section:
        final_pm += "\n\n" + feedback_section
        
    if mr_clean:
        return final_pm + "\n\n---\n\n" + mr_clean
    else:
        return final_pm


def sync_combined_report_files(date_str: str, combined_content: str, has_market_report: bool = False):
    """
    Synchronizes the combined report content across the performance cache, Obsidian reports, and market reports archive.
    """
    # 1. Save to performance cache file (combined post-mortem)
    perf_path = os.path.join(PERFORMANCE_DIR, f"Daily_PostMortem_{date_str}.md")
    try:
        with open(perf_path, "w", encoding="utf-8") as f:
            f.write(combined_content)
        logger.info(f"Saved combined post-mortem cache: {perf_path}")
    except Exception as e:
        logger.error(f"Failed to save performance cache file: {e}")
        
    # Sync with alternative performance directory (root vs backend/data)
    try:
        if "backend" in PERFORMANCE_DIR:
            alt_perf_dir = PERFORMANCE_DIR.replace("backend" + os.sep + "data", "data")
        else:
            alt_perf_dir = os.path.abspath(os.path.join(PERFORMANCE_DIR, "..", "..", "backend", "data", "reports", "performance"))
            
        if alt_perf_dir != PERFORMANCE_DIR and os.path.exists(os.path.dirname(alt_perf_dir)):
            os.makedirs(alt_perf_dir, exist_ok=True)
            alt_path = os.path.join(alt_perf_dir, f"Daily_PostMortem_{date_str}.md")
            with open(alt_path, "w", encoding="utf-8") as f:
                f.write(combined_content)
            logger.info(f"Synced combined post-mortem to alternative path: {alt_path}")
    except Exception as e:
        logger.warning(f"Failed to sync alternative performance report path: {e}")
        
    # 2. Save to Obsidian daily reports directory
    write_obsidian_daily_report(combined_content, date_str=date_str)
    
    # Extract standalone Daily Scanner Review content if marker is present
    scanner_review_marker = "# Daily Scanner Review:"
    start_idx = combined_content.find(scanner_review_marker)
    if start_idx == -1:
        scanner_review_marker = "# Daily Market Report:"
        start_idx = combined_content.find(scanner_review_marker)
        
    scanner_review_content = ""
    if start_idx != -1:
        scanner_review_content = combined_content[start_idx:].strip()

    # 3. Save Standalone Daily Scanner Review to archive
    if has_market_report and scanner_review_content:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        out_dir = os.path.join(base_dir, "data", "archive", "daily_scanner_reviews")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"Daily_Scanner_Review_{date_str}.md")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(scanner_review_content)
            logger.info(f"Saved standalone Daily Scanner Review: {out_path}")
        except Exception as e:
            logger.error(f"Failed to save standalone Daily Scanner Review: {e}")
            
        # Sync with alternative daily scanner reviews archive path
        try:
            if "backend" in out_path:
                alt_out_path = out_path.replace("backend" + os.sep + "data", "data")
            else:
                alt_out_path = os.path.abspath(os.path.join(os.path.dirname(out_path), "..", "..", "backend", "data", "archive", "daily_scanner_reviews", f"Daily_Scanner_Review_{date_str}.md"))
                
            if alt_out_path != out_path and os.path.exists(os.path.dirname(os.path.dirname(alt_out_path))):
                os.makedirs(os.path.dirname(alt_out_path), exist_ok=True)
                with open(alt_out_path, "w", encoding="utf-8") as f:
                    f.write(scanner_review_content)
                logger.info(f"Synced standalone Daily Scanner Review to alternative path: {alt_out_path}")
        except Exception as e:
            logger.warning(f"Failed to sync alternative Daily Scanner Review path: {e}")
            
    # Always save to VLI reports folders and user daily journals
    try:
        from src.tools.journal import _get_obsidian_config
        vault_path, journal_dir = _get_obsidian_config(None)
        if not journal_dir:
            journal_dir = os.environ.get("OBSIDIAN_JOURNAL_DIR", "Journals")
        if vault_path:
            vault_reports_dir = os.environ.get("VLI_REPORTS_ROOT")
            if not vault_reports_dir:
                vault_reports_dir = os.path.join(vault_path, "_cobalt", "Reports")
            
            vault_today_dir = os.path.join(vault_reports_dir, date_str)
            os.makedirs(vault_today_dir, exist_ok=True)
            
            # Save combined report (Post-Mortem + folded Scanner Review) to VLI subfolders
            vault_out_path = os.path.join(vault_today_dir, f"{date_str} Daily Post Mortem.md")
            with open(vault_out_path, "w", encoding="utf-8") as f:
                f.write(combined_content)
            logger.info(f"Saved combined Daily Post Mortem in VLI folder: {vault_out_path}")
            
            os.makedirs(vault_reports_dir, exist_ok=True)
            pm_filenames = [f"Daily_PostMortem_{date_str}.md", f"{date_str} Daily Post Mortem.md"]
            for filename in pm_filenames:
                root_path = os.path.join(vault_reports_dir, filename)
                date_sub_path = os.path.join(vault_today_dir, filename)
                with open(root_path, "w", encoding="utf-8") as f:
                    f.write(combined_content)
                with open(date_sub_path, "w", encoding="utf-8") as f:
                    f.write(combined_content)
            logger.info(f"Copied combined Daily Post Mortem to VLI folders: {vault_reports_dir} and {vault_today_dir}")
            
            # Save standalone Daily Scanner Review to VLI reports folders
            if scanner_review_content:
                sr_filenames = [
                    (vault_reports_dir, f"Daily_Scanner_Review_{date_str}.md"),
                    (vault_reports_dir, f"{date_str} Daily Scanner Review.md"),
                    (vault_today_dir, f"Daily_Scanner_Review_{date_str}.md"),
                    (vault_today_dir, f"{date_str} Daily Scanner Review.md"),
                    (os.path.join(vault_path, journal_dir, "Daily Reports"), f"Daily_Scanner_Review_{date_str}.md")
                ]
                for folder, filename in sr_filenames:
                    os.makedirs(folder, exist_ok=True)
                    target_file = os.path.join(folder, filename)
                    with open(target_file, "w", encoding="utf-8") as f:
                        f.write(scanner_review_content)
                logger.info(f"Saved standalone Daily Scanner Review to VLI & journal target folders")

            # 3. Synchronize scanner review sections into user's Daily Journal and Daily Trading Report files
            if start_idx != -1:
                sep_idx = combined_content.rfind("---", 0, start_idx)
                if sep_idx != -1:
                    market_report_content = "\n\n" + combined_content[sep_idx:].strip()
                else:
                    market_report_content = "\n\n---\n\n" + combined_content[start_idx:].strip()
                    
                target_paths = [
                    os.path.join(vault_path, journal_dir, f"{date_str} Daily Journal.md"),
                    os.path.join(vault_path, journal_dir, f"Daily_Trading_Report_{date_str}.md"),
                    os.path.join(vault_reports_dir, f"{date_str} Daily Journal.md"),
                    os.path.join(vault_reports_dir, f"Daily_Trading_Report_{date_str}.md"),
                    os.path.join(vault_today_dir, f"{date_str} Daily Journal.md"),
                    os.path.join(vault_today_dir, f"Daily_Trading_Report_{date_str}.md")
                ]
                
                markers = ["# Daily Scanner Review:", "# Daily Market Report:"]
                
                for filepath in target_paths:
                    if os.path.exists(filepath):
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        found_marker = None
                        for m in markers:
                            if m in content:
                                found_marker = m
                                break
                                
                        if found_marker:
                            base_content = content.split(found_marker)[0].strip()
                            if base_content.endswith("---"):
                                base_content = base_content[:-3].strip()
                            new_content = base_content + market_report_content
                        else:
                            new_content = content.strip() + market_report_content
                            
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        logger.info(f"Updated market report inside Daily Journal file: {filepath}")
    except Exception as e:
        logger.error(f"Failed to update VLI market report: {e}")

