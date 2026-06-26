import os
import shutil
import tempfile
import pytest

# Add backend directory to system path to ensure imports work correctly
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

def test_save_daily_journal_note():
    # 1. Try to import the sync function
    try:
        from src.services.historical_reports import save_daily_journal_note
    except ImportError as e:
        pytest.fail(f"Forced Failure: save_daily_journal_note is not implemented or importable: {e}")

    # Set up temp directories to act as mock Obsidian vault and VLI reports root
    temp_obsidian = tempfile.mkdtemp()
    temp_vli = tempfile.mkdtemp()

    # Mock environment variables
    os.environ["OBSIDIAN_VAULT_PATH"] = temp_obsidian
    os.environ["OBSIDIAN_JOURNAL_DIR"] = "Journals"
    os.environ["VLI_REPORTS_ROOT"] = temp_vli

    date_str = "2026-06-24"
    grades = {
        "prep": 4,
        "sleep": 3,
        "mood": 5,
        "energy": 4,
        "confidence": 4,
        "performance": "A-"
    }
    synthesized_notes = "Reflections text."
    synthesized_assessment = "Coaching text."

    try:
        # 2. Call the function
        save_daily_journal_note(date_str, grades, synthesized_notes, synthesized_assessment)

        # 3. Verify Obsidian Daily Journal file was written
        obsidian_file = os.path.join(temp_obsidian, "Journals", f"{date_str} Daily Journal.md")
        assert os.path.exists(obsidian_file), "Obsidian daily journal file was not created"

        with open(obsidian_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert f"# {date_str} Daily Journal" in content
        assert "### Today's Metrics" in content
        assert "* **Prep:** 4/5" in content
        assert "* **Sleep:** 3/5" in content
        assert "* **Mood:** 5/5" in content
        assert "* **Energy:** 4/5" in content
        assert "* **Confidence:** 4/5" in content
        assert "* **Overall Execution Grade:** A-" in content
        assert "## Polished Reflections" in content
        assert "Reflections text." in content
        assert "## Mindset Coaching" in content
        assert "Coaching text." in content
        
        # Ensure ## Trades and ## Notes sections are NOT in the file
        assert "## Trades" not in content
        assert "## Notes" not in content

        # 4. Verify VLI Daily Journal files were written
        vli_root_file = os.path.join(temp_vli, f"{date_str} Daily Journal.md")
        vli_date_file = os.path.join(temp_vli, date_str, f"{date_str} Daily Journal.md")

        assert os.path.exists(vli_root_file), "VLI root daily journal file was not created"
        assert os.path.exists(vli_date_file), "VLI date daily journal file was not created"

    finally:
        # Clean up temp directories
        shutil.rmtree(temp_obsidian)
        shutil.rmtree(temp_vli)


def test_sync_combined_report_files():
    from src.services.historical_reports import sync_combined_report_files

    # Set up temp directories to act as mock Obsidian vault, VLI reports root, and PERFORMANCE_DIR
    temp_obsidian = tempfile.mkdtemp()
    temp_vli = tempfile.mkdtemp()
    temp_perf = tempfile.mkdtemp()

    # Mock environment variables/globals
    os.environ["OBSIDIAN_VAULT_PATH"] = temp_obsidian
    os.environ["OBSIDIAN_JOURNAL_DIR"] = "Journals"
    os.environ["VLI_REPORTS_ROOT"] = temp_vli

    # Temporarily override PERFORMANCE_DIR in src.services.historical_reports
    import src.services.historical_reports
    original_perf_dir = src.services.historical_reports.PERFORMANCE_DIR
    src.services.historical_reports.PERFORMANCE_DIR = temp_perf

    date_str = "2026-06-24"
    combined_content = "# Daily Post Mortem\nSome content here."

    try:
        sync_combined_report_files(date_str, combined_content, has_market_report=False)

        # 1. Verify in performance cache
        perf_file = os.path.join(temp_perf, f"Daily_PostMortem_{date_str}.md")
        assert os.path.exists(perf_file)
        with open(perf_file, "r", encoding="utf-8") as f:
            assert f.read() == combined_content

        # 2. Verify in Obsidian daily reports directory
        obsidian_file = os.path.join(temp_obsidian, "Journals", "Daily Reports", f"Daily_PostMortem_{date_str}.md")
        assert os.path.exists(obsidian_file)
        with open(obsidian_file, "r", encoding="utf-8") as f:
            assert f.read() == combined_content

        # 3. Verify in VLI reports root
        vli_root_file1 = os.path.join(temp_vli, f"Daily_PostMortem_{date_str}.md")
        vli_root_file2 = os.path.join(temp_vli, f"{date_str} Daily Post Mortem.md")
        assert os.path.exists(vli_root_file1)
        assert os.path.exists(vli_root_file2)
        with open(vli_root_file1, "r", encoding="utf-8") as f:
            assert f.read() == combined_content

        # 4. Verify in VLI reports date subfolder
        vli_date_file1 = os.path.join(temp_vli, date_str, f"Daily_PostMortem_{date_str}.md")
        vli_date_file2 = os.path.join(temp_vli, date_str, f"{date_str} Daily Post Mortem.md")
        assert os.path.exists(vli_date_file1)
        assert os.path.exists(vli_date_file2)
        with open(vli_date_file1, "r", encoding="utf-8") as f:
            assert f.read() == combined_content

    finally:
        # Restore PERFORMANCE_DIR
        src.services.historical_reports.PERFORMANCE_DIR = original_perf_dir
        # Clean up temp directories
        shutil.rmtree(temp_obsidian)
        shutil.rmtree(temp_vli)
        shutil.rmtree(temp_perf)

