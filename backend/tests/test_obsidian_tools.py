import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from deerflow.community.obsidian.tools import (
    read_obsidian_note,
    write_obsidian_note,
    append_obsidian_note,
    list_obsidian_notes,
    search_obsidian_notes,
)

class TestObsidianTools(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for the mock vault
        self.test_dir = tempfile.mkdtemp()
        self.vault_path = Path(self.test_dir)
        
        # Create some initial structure
        (self.vault_path / "Meetings").mkdir()
        (self.vault_path / "Note1.md").write_text("Hello Obsidian", encoding="utf-8")
        (self.vault_path / "Meetings" / "Meeting1.md").write_text("Meeting notes here", encoding="utf-8")

    def tearDown(self):
        # Remove the temporary directory
        shutil.rmtree(self.test_dir)

    def test_resolve_path_safety(self):
        # This tests the internal _resolve_obsidian_path via one of the tools
        with patch("deerflow.community.obsidian.tools._get_obsidian_vault_path", return_value=self.vault_path):
            res = read_obsidian_note.run("../outside.md")
            self.assertIn("Error", res)
            self.assertIn("denied", res.lower())

    def test_read_note(self):
        with patch("deerflow.community.obsidian.tools._get_obsidian_vault_path", return_value=self.vault_path):
            # Test reading existing note (with extension)
            res = read_obsidian_note.run("Note1.md")
            self.assertEqual(res, "Hello Obsidian")
            
            # Test reading existing note (without extension)
            res = read_obsidian_note.run("Note1")
            self.assertEqual(res, "Hello Obsidian")
            
            # Test non-existent note
            res = read_obsidian_note.run("Missing")
            self.assertIn("Error", res)

    def test_write_note(self):
        with patch("deerflow.community.obsidian.tools._get_obsidian_vault_path", return_value=self.vault_path):
            res = write_obsidian_note.run({"path": "NewNote", "content": "New Content"})
            self.assertIn("Successfully", res)
            self.assertTrue((self.vault_path / "NewNote.md").exists())
            self.assertEqual((self.vault_path / "NewNote.md").read_text(), "New Content")

    def test_append_note(self):
        with patch("deerflow.community.obsidian.tools._get_obsidian_vault_path", return_value=self.vault_path):
            res = append_obsidian_note.run({"path": "Note1", "content": "Appended line"})
            self.assertIn("Successfully", res)
            content = (self.vault_path / "Note1.md").read_text()
            self.assertIn("Hello Obsidian", content)
            self.assertIn("Appended line", content)

    def test_list_notes(self):
        with patch("deerflow.community.obsidian.tools._get_obsidian_vault_path", return_value=self.vault_path):
            # List root
            res = list_obsidian_notes.run("")
            self.assertIn("📁 Meetings", res)
            self.assertIn("📄 Note1.md", res)
            
            # List subfolder
            res = list_obsidian_notes.run("Meetings")
            self.assertIn("📄 Meeting1.md", res)

    def test_search_notes(self):
        with patch("deerflow.community.obsidian.tools._get_obsidian_vault_path", return_value=self.vault_path):
            res = search_obsidian_notes.run("Meeting")
            self.assertIn("Meetings/Meeting1.md:1: Meeting notes here", res)
            
            res = search_obsidian_notes.run("Obsidian")
            self.assertIn("Note1.md:1: Hello Obsidian", res)
            
            res = search_obsidian_notes.run("Nonexistent")
            self.assertIn("No matches found", res)

if __name__ == "__main__":
    unittest.main()
