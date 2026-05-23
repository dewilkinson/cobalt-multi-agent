import os
import shutil
import tempfile
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add backend directory to sys.path so we can import src
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from src.services.brokerage_cache import BrokerageCache
from src.services.atp_importer import check_and_backup_dropzone_file

class TestBackupRotation(unittest.TestCase):
    def setUp(self):
        # Create temp directories for testing
        self.test_dir = tempfile.mkdtemp()
        self.backup_dir = os.path.join(self.test_dir, "backups")
        
        # Stub the conf.yaml and CACHE_FILE pathing
        self.mock_config = {
            "BACKUP_POLICY": {
                "archive_dir": self.backup_dir
            }
        }
        
        # Create a dummy cache file so backup_cache has something to copy
        self.cache_file = os.path.join(self.test_dir, "brokerage_cache.json")
        with open(self.cache_file, "w") as f:
            f.write('{"test": "data"}')
            
        # Patch the configuration and cache file paths
        self.patcher_config = patch("src.config.loader.get_config", return_value=self.mock_config)
        self.patcher_cache_file = patch("src.services.brokerage_cache.CACHE_FILE", self.cache_file)
        self.mock_get_config = self.patcher_config.start()
        self.patcher_cache_file.start()

    def tearDown(self):
        self.patcher_config.stop()
        self.patcher_cache_file.stop()
        shutil.rmtree(self.test_dir)

    def test_get_backup_dir(self):
        """Test that get_backup_dir correctly resolves the configured path."""
        resolved = BrokerageCache.get_backup_dir()
        self.assertEqual(os.path.normpath(resolved), os.path.normpath(self.backup_dir))

    def test_daily_backup_rotation(self):
        """Test that we keep exactly 7 daily backups, rotating out the oldest."""
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Pre-populate with 9 old daily backups
        dates = [
            "2026-05-10", "2026-05-11", "2026-05-12", "2026-05-13",
            "2026-05-14", "2026-05-15", "2026-05-16", "2026-05-17",
            "2026-05-18"
        ]
        for d in dates:
            filename = f"BrokerageCacheDailyBackup_{d}.json"
            with open(os.path.join(self.backup_dir, filename), "w") as f:
                f.write('{"old": "data"}')

        # Run backup_cache (daily) which adds the 10th file (today's date)
        BrokerageCache.backup_cache(is_weekly=False)

        # Check existing files
        backup_files = [f for f in os.listdir(self.backup_dir) if f.startswith("BrokerageCacheDailyBackup_")]
        backup_files.sort()

        # We should have exactly 7 backups
        self.assertEqual(len(backup_files), 7)

        # The oldest files (2026-05-10, 2026-05-11, 2026-05-12) should have been pruned
        expected_dates = sorted(dates + [datetime_today_str()])[-7:]
        expected_filenames = [f"BrokerageCacheDailyBackup_{d}.json" for d in expected_dates]
        self.assertEqual(backup_files, expected_filenames)

    def test_dropzone_file_backup_checking(self):
        """Test check_and_backup_dropzone_file only backs up CSVs containing date and time."""
        # 1. Test CSV with Order Time header (contains date and time)
        good_csv = os.path.join(self.test_dir, "Orders_Test.csv")
        with open(good_csv, "w", encoding="utf-8") as f:
            f.write("Symbol,Action,Amount,Status,Order Time\n")
            f.write("AAPL,BUY,10,Filled,10:00:00 AM ET 05-23-2026\n")

        # 2. Test CSV without Date and Time (e.g. only Run Date or no Time)
        bad_csv = os.path.join(self.test_dir, "Positions_Test.csv")
        with open(bad_csv, "w", encoding="utf-8") as f:
            f.write("Symbol,Description,Quantity\n")
            f.write("AAPL,Apple Inc,10\n")

        # Run backup check on good CSV
        check_and_backup_dropzone_file(good_csv)
        
        # Run backup check on bad CSV
        check_and_backup_dropzone_file(bad_csv)

        # Check the backup folder contents
        backup_files = os.listdir(self.backup_dir)
        
        # Good CSV should have been backed up (contains Orders_Test in name)
        backed_up_orders = [f for f in backup_files if f.startswith("Orders_Test_")]
        self.assertEqual(len(backed_up_orders), 1)
        self.assertTrue(backed_up_orders[0].endswith(".csv"))

        # Bad CSV should NOT have been backed up
        backed_up_positions = [f for f in backup_files if f.startswith("Positions_Test_")]
        self.assertEqual(len(backed_up_positions), 0)

def datetime_today_str():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")

if __name__ == "__main__":
    unittest.main()
