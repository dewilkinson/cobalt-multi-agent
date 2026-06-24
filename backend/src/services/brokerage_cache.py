import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "brokerage_cache.json"))

class BrokerageCache:
    """
    Manages a local disk cache for SnapTrade brokerage activities to prevent
    rate limits and reduce latency on long historical fetches.
    """
    @classmethod
    def _parse_time(cls, act: Dict[str, Any]) -> datetime:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        eastern_tz = ZoneInfo("America/New_York")
        t_str = act.get('trade_date', '') or act.get('time_placed', '')
        if not t_str:
            return datetime.min.replace(tzinfo=eastern_tz)
        
        # Strip Z or timezone offset if present, to treat the hours as Eastern Time
        t_str_clean = str(t_str)
        if t_str_clean.endswith('Z'):
            t_str_clean = t_str_clean[:-1]
        if '+' in t_str_clean:
            t_str_clean = t_str_clean.split('+')[0]
            
        # Try parsing Month-Day-Year (e.g. Oct-7-2025 or May-20-2026)
        if '-' in t_str_clean and not t_str_clean.startswith('20'):
            try:
                dt = datetime.strptime(t_str_clean, "%b-%d-%Y")
                return dt.replace(tzinfo=eastern_tz)
            except Exception:
                pass
                
        # Try parsing Month/Day/Year (e.g. 10/7/2025)
        if '/' in t_str_clean:
            try:
                dt = datetime.strptime(t_str_clean, "%m/%d/%Y")
                return dt.replace(tzinfo=eastern_tz)
            except Exception:
                try:
                    dt = datetime.strptime(t_str_clean, "%m/%d/%y")
                    return dt.replace(tzinfo=eastern_tz)
                except Exception:
                    pass
                    
        try:
            if 'T' in t_str_clean:
                if '.' in t_str_clean:
                    parts = t_str_clean.split('.')
                    frac = parts[1][:3]
                    t_str_clean = parts[0] + '.' + frac
                    dt = datetime.strptime(t_str_clean, "%Y-%m-%dT%H:%M:%S.%f")
                else:
                    dt = datetime.strptime(t_str_clean, "%Y-%m-%dT%H:%M:%S")
            else:
                dt = datetime.fromisoformat(t_str_clean)
                
            return dt.replace(tzinfo=eastern_tz)
        except Exception:
            try:
                dt = datetime.fromisoformat(t_str.replace('Z', '+00:00'))
                return dt.astimezone(eastern_tz)
            except Exception:
                return datetime.min.replace(tzinfo=eastern_tz)

    @classmethod
    def ingest_fidelity_payload(cls, payload: Dict[str, Any]) -> int:
        """
        Ingests a raw payload from the Chrome Extension.
        If payloadType == 'dom', it uses regex to extract execution times.
        """
        import re
        
        extracted = []
        
        if payload.get('payloadType') == 'dom':
            html = payload.get('html', '')
            logger.info(f"Received DOM payload of size {len(html)} bytes")
            
            # Save for debugging
            import os
            debug_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "fidelity_extension_debug_dom.html"))
            try:
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(html)
            except Exception:
                pass
                
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            rows = soup.find_all('div', class_=lambda c: c and ('gridrow' in c.lower() or 'ao-row-container' in c.lower()))
            
            extracted_set = set()
            for row in rows:
                row_text = row.get_text(separator=' ', strip=True)
                times = re.findall(r'\b\d{1,2}:\d{2}:\d{2}\s(?:AM|PM|am|pm)\b', row_text)
                syms = re.findall(r'\(([A-Z]{1,5})\)|Symbol ([A-Z]{1,5})\b', row_text)
                symbols = [s[0] or s[1] for s in syms if s[0] or s[1]]
                
                if times and symbols:
                    sym = symbols[-1]
                    t = times[-1]
                    sig = f"{sym}_{t}"
                    if sig not in extracted_set:
                        extracted_set.add(sig)
                        extracted.append({'symbol': sym, 'time': t})
                        logger.info(f"[VLI_TRACE] Bridge Extracted: {sym} @ {t}")

            logger.info(f"[VLI_TRACE] Extracted {len(extracted)} potential trades from DOM payload via bs4.")
        else:
            # Fallback JSON parsing if needed
            logger.warning("Received non-DOM payload, skipping.")
            return 0
        
        # Merge into cache
        cache = cls._load_cache()
        merged_count = 0
        for account_id, acct_data in cache.items():
            activities = acct_data.get("activities", []) if isinstance(acct_data, dict) else acct_data
            for act in activities:
                snap_time = act.get('trade_date', '') or act.get('time_placed', '')
                snap_sym = ''
                if 'universal_symbol' in act and act['universal_symbol'] and isinstance(act['universal_symbol'], dict):
                    snap_sym = act['universal_symbol'].get('symbol', '')
                elif 'symbol' in act and act['symbol'] and isinstance(act['symbol'], dict):
                    snap_sym = act['symbol'].get('symbol', '')
                    
                if snap_sym and (snap_time.endswith('00:00:00Z') or snap_time.endswith('04:00:00Z') or snap_time.endswith('05:00:00Z')):
                    for ex in extracted:
                        if ex['symbol'] == snap_sym:
                            date_part = snap_time.split('T')[0]
                            act['trade_date'] = f"{date_part}T{ex['time']}"
                            merged_count += 1
                            break
                            
        if merged_count > 0:
            cls._save_cache(cache)
            logger.info(f"Merged {merged_count} execution times into BrokerageCache!")
            
        return merged_count

    @classmethod
    def _load_cache(cls) -> Dict[str, Any]:
        if not os.path.exists(CACHE_FILE):
            return {}
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            migrated = False
            for key, value in data.items():
                if isinstance(value, list):
                    data[key] = {"activities": value, "positions": []}
                    migrated = True
                    
            if migrated:
                cls._save_cache(data)
                
            return data
        except Exception as e:
            logger.error(f"Failed to load brokerage cache: {e}")
            return {}

    @classmethod
    def _save_cache(cls, data: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save brokerage cache: {e}")

    @classmethod
    def get_backup_dir(cls) -> str:
        """
        Resolves the backup directory from configuration (conf.yaml -> BACKUP_POLICY.archive_dir).
        Defaults to 'G:\\My Drive\\Backups\\cobalt'.
        Falls back to 'C:\\Backup' if the configured directory is not writable/accessible.
        Generates highly visible warnings if the configured location is offline/inaccessible.
        """
        from src.config.loader import get_config
        
        try:
            config = get_config()
        except Exception as e:
            logger.warning(f"Failed to load application configuration: {e}. Using default values.")
            config = {}
            
        backup_policy = config.get("BACKUP_POLICY", {})
        archive_dir = backup_policy.get("archive_dir", "G:\\My Drive\\Backups\\cobalt")
        
        # Verify if archive_dir is accessible/writable
        try:
            os.makedirs(archive_dir, exist_ok=True)
            if os.path.exists(archive_dir):
                return archive_dir
        except Exception as e:
            msg = (
                "\n"
                "========================================================================\n"
                "!!! CRITICAL WARNING: CONFIGURED BACKUP LOCATION IS NOT ACCESSIBLE !!!\n"
                f"Configured Path: {archive_dir}\n"
                f"Error: {e}\n"
                "FALLING BACK TO SYSTEM BACKUP DIRECTORY: C:\\Backup\n"
                "========================================================================"
            )
            logger.error(msg)
            print(msg)
            
        # Fallback path (C:\\Backup)
        fallback_dir = "C:\\Backup"
        try:
            os.makedirs(fallback_dir, exist_ok=True)
            return fallback_dir
        except Exception as e2:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            ultimate_fallback = os.path.join(project_root, "data", "archive")
            msg2 = (
                "\n"
                "========================================================================\n"
                "!!! ULTIMATE CRITICAL WARNING: C:\\Backup IS NOT ACCESSIBLE !!!\n"
                f"Error: {e2}\n"
                f"FALLING BACK TO LOCAL PROJECT ARCHIVE: {ultimate_fallback}\n"
                "========================================================================"
            )
            logger.error(msg2)
            print(msg2)
            os.makedirs(ultimate_fallback, exist_ok=True)
            return ultimate_fallback
    @classmethod
    def _backup_project_data_and_uncommitted(cls, archive_dir: str, date_str: str, is_weekly: bool) -> None:
        """
        Compresses and archives:
        1. Local data/ directory (excluding data/archive/)
        2. Local backend/data/ directory
        3. All other uncommitted, untracked, or ignored files (excluding build/dependency/cache dirs)
        Saves the compressed ZIP file to the active backup directory.
        """
        import zipfile
        import subprocess
        
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        
        # 1. Identify all target files to back up
        files_to_backup = {} # maps abs_path -> relative_path_in_zip
        
        # Add a directory helper
        def add_dir_files(dir_path: str, exclude_dirs: list[str] = None):
            if not os.path.exists(dir_path):
                return
            for root, dirs, files in os.walk(dir_path):
                if exclude_dirs:
                    for d in list(dirs):
                        if d in exclude_dirs:
                            dirs.remove(d)
                for file in files:
                    abs_p = os.path.join(root, file)
                    rel_p = os.path.relpath(abs_p, project_root)
                    files_to_backup[abs_p] = rel_p

        # A. Add .\data (excluding 'archive')
        add_dir_files(os.path.join(project_root, "data"), exclude_dirs=["archive"])
        
        # B. Add .\backend\data
        add_dir_files(os.path.join(project_root, "backend", "data"))
        
        # C. Retrieve and add other uncommitted/untracked/ignored files from Git
        ignored_patterns = [
            "node_modules",
            "__pycache__",
            ".venv",
            ".next",
            ".pytest_cache",
            ".git",
            "tsconfig.tsbuildinfo"
        ]
        
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain", "--ignored"],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=True
            )
            git_lines = res.stdout.splitlines()
        except Exception as e:
            logger.error(f"Failed to query git status for backup: {e}")
            git_lines = []
            
        for line in git_lines:
            if len(line) < 4:
                continue
            status = line[:2]
            path_part = line[3:].strip().strip('"')
            
            if status in ("??", "!!") or "M" in status or "A" in status:
                abs_p = os.path.abspath(os.path.join(project_root, path_part))
                
                # Check exclusion patterns
                skip = False
                for pat in ignored_patterns:
                    if pat in path_part or pat in abs_p:
                        skip = True
                        break
                        
                # Exclude local archive folder and backup folder itself
                if "data/archive" in path_part or "data\\archive" in path_part:
                    skip = True
                if "C:\\Backup" in abs_p or "C:/Backup" in abs_p:
                    skip = True
                    
                if not skip and os.path.exists(abs_p):
                    if os.path.isfile(abs_p):
                        rel_p = os.path.relpath(abs_p, project_root)
                        files_to_backup[abs_p] = rel_p
                    elif os.path.isdir(abs_p):
                        add_dir_files(abs_p, exclude_dirs=ignored_patterns + ["archive"])
                        
        if not files_to_backup:
            logger.warning("No files identified for project backup.")
            return
            
        # Determine output filename
        if is_weekly:
            zip_name = f"DataBackup_{date_str}.zip"
        else:
            zip_name = f"DataDailyBackup_{date_str}.zip"
            
        zip_path = os.path.join(archive_dir, zip_name)
        logger.info(f"Compressing {len(files_to_backup)} files to {zip_path}...")
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for abs_p, rel_p in files_to_backup.items():
                    if os.path.exists(abs_p):
                        zipf.write(abs_p, rel_p)
            logger.info(f"Successfully created backup at {zip_path} ({len(files_to_backup)} files).")
        except Exception as e:
            logger.error(f"Failed to create project ZIP backup: {e}")

    @classmethod
    def backup_cache(cls, is_weekly: bool = False) -> None:
        """
        Takes a scheduled backup of the current brokerage cache.
        """
        if not os.path.exists(CACHE_FILE):
            return
            
        import shutil
        from datetime import datetime
        import glob
        
        filename = os.path.basename(CACHE_FILE)
        name, ext = os.path.splitext(filename)
        
        archive_dir = cls.get_backup_dir()
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        if is_weekly:
            backup_path = os.path.join(archive_dir, f"BrokerageCacheBackup_{date_str}{ext}")
            shutil.copy2(CACHE_FILE, backup_path)
            
            # [NEW] Backup Obsidian Journals and internal Analysis Reports
            try:
                from src.tools.journal import _get_obsidian_config
                vault_path, journal_dir = _get_obsidian_config(None)
                
                if vault_path:
                    full_journal_dir = os.path.join(vault_path, journal_dir)
                    if os.path.exists(full_journal_dir):
                        journal_backup = os.path.join(archive_dir, f"TradingJournalsBackup_{date_str}")
                        shutil.make_archive(journal_backup, 'zip', full_journal_dir)
                        logger.info(f"Backed up Obsidian journals to {journal_backup}.zip")
                        
                reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", 'data', 'reports'))
                if os.path.exists(reports_dir):
                    reports_backup = os.path.join(archive_dir, f"AnalysisReportsBackup_{date_str}")
                    shutil.make_archive(reports_backup, 'zip', reports_dir)
                    logger.info(f"Backed up internal reports to {reports_backup}.zip")
                    
            except Exception as e:
                logger.error(f"Failed to backup extra directories during weekly cron: {e}")
            
            # Compress and sync weekly project files
            cls._backup_project_data_and_uncommitted(archive_dir, date_str, is_weekly=True)
            logger.info(f"Created weekly BrokerageCache backup: {backup_path}")
        else:
            # Daily backups rolling 7-day rotation
            new_backup_filename = f"BrokerageCacheDailyBackup_{date_str}{ext}"
            new_backup_path = os.path.join(archive_dir, new_backup_filename)
            
            shutil.copy2(CACHE_FILE, new_backup_path)
            logger.info(f"Created daily BrokerageCache backup: {new_backup_path}")
            
            # Compress and sync daily project files
            cls._backup_project_data_and_uncommitted(archive_dir, date_str, is_weekly=False)
            
            # Rotate daily cache backups
            pattern = os.path.join(archive_dir, "BrokerageCacheDailyBackup_*json")
            existing_backups = glob.glob(pattern)
            existing_backups.sort()
            
            if len(existing_backups) > 7:
                files_to_delete = existing_backups[:-7]
                for file_path in files_to_delete:
                    try:
                        os.remove(file_path)
                        logger.info(f"Deleted old daily backup: {file_path}")
                    except Exception as e:
                        logger.error(f"Failed to delete old backup {file_path}: {e}")

            # Rotate daily project backups
            daily_zip_pattern = os.path.join(archive_dir, "DataDailyBackup_*zip")
            existing_zips = glob.glob(daily_zip_pattern)
            existing_zips.sort()
            
            if len(existing_zips) > 7:
                zips_to_delete = existing_zips[:-7]
                for zip_file in zips_to_delete:
                    try:
                        os.remove(zip_file)
                        logger.info(f"Deleted old daily zip backup: {zip_file}")
                    except Exception as e:
                        logger.error(f"Failed to delete old daily zip backup {zip_file}: {e}")

    @classmethod
    def backup_cache_daily(cls) -> None:
        cls.backup_cache(is_weekly=False)

    @classmethod
    def backup_cache_weekly(cls) -> None:
        cls.backup_cache(is_weekly=True)

    @classmethod
    def get_activities(cls, account_id: str) -> List[Dict[str, Any]]:
        """Returns all cached activities for the given account ID."""
        cache = cls._load_cache()
        acct_data = cache.get(account_id, {})
        if isinstance(acct_data, list):
            return acct_data
        return acct_data.get("activities", [])

    @classmethod
    def get_positions(cls, account_id: str) -> List[Dict[str, Any]]:
        """Returns all cached explicit positions for the given account ID."""
        cache = cls._load_cache()
        acct_data = cache.get(account_id, {})
        if isinstance(acct_data, list):
            return []
        return acct_data.get("positions", [])

    @classmethod
    def set_positions(cls, account_id: str, positions: List[Dict[str, Any]]) -> None:
        """Sets explicit positions for the given account."""
        cache = cls._load_cache()
        acct_data = cache.get(account_id, {"activities": [], "positions": []})
        if isinstance(acct_data, list):
            acct_data = {"activities": acct_data, "positions": []}
            
        acct_data["positions"] = positions
        cache[account_id] = acct_data
        cls._save_cache(cache)
        logger.info(f"Set {len(positions)} explicit positions for account {account_id}")

    @classmethod
    def merge_activities(cls, account_id: str, new_activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merges new activities into the cache for the given account.
        Deduplicates based on the trade 'id'.
        Returns the FULL updated list of activities for the account.
        """
        cache = cls._load_cache()
        acct_data = cache.get(account_id, {"activities": [], "positions": [], "closed_positions": []})
        if isinstance(acct_data, list):
            acct_data = {"activities": acct_data, "positions": [], "closed_positions": []}
            
        existing_activities = acct_data.get("activities", [])
        
        # Build a set of existing IDs for fast lookup
        existing_ids = {act['id'] for act in existing_activities if 'id' in act}
        
        # Build a fuzzy index of existing activities to handle ATP/HIST overlap
        # Key: (symbol, action, units, trade_date_YYYY-MM-DD)
        fuzzy_existing = {}
        for act in existing_activities:
            sym_obj = act.get('symbol', {})
            sym = sym_obj.get('symbol', '') if isinstance(sym_obj, dict) else sym_obj
            trade_date = str(act.get('trade_date', act.get('time_placed', '')))[:10]
            action = act.get('type', act.get('action', 'N/A'))
            units = act.get('units', 0)
            key = (sym, action, units, trade_date)
            if key not in fuzzy_existing:
                fuzzy_existing[key] = []
            fuzzy_existing[key].append(act)
            
        atp_absorption = {}
        
        # Add new activities
        added = 0
        for act in new_activities:
            act_id = act.get('id')
            if not act_id or act_id in existing_ids:
                continue
                
            sym_obj = act.get('symbol', {})
            sym = sym_obj.get('symbol', '') if isinstance(sym_obj, dict) else sym_obj
            trade_date = str(act.get('trade_date', act.get('time_placed', '')))[:10]
            action = act.get('type', act.get('action', 'N/A'))
            units = act.get('units', 0)
            key = (sym, action, units, trade_date)

            is_duplicate = False

            if act_id.startswith('HIST-') and key in fuzzy_existing:
                # Find an ATP trade that hasn't absorbed a HIST trade yet
                for f_act in fuzzy_existing[key]:
                    f_id = f_act.get('id', '')
                    if f_id.startswith('ATP-') and atp_absorption.get(f_id, 0) == 0:
                        is_duplicate = True
                        atp_absorption[f_id] = 1
                        break

            elif act_id.startswith('ATP-') and key in fuzzy_existing:
                # Find a HIST trade to replace
                hist_to_remove = None
                for f_act in fuzzy_existing[key]:
                    f_id = f_act.get('id', '')
                    if f_id.startswith('HIST-') and atp_absorption.get(f_id, 0) == 0:
                        hist_to_remove = f_act
                        break
                
                if hist_to_remove:
                    hist_id = hist_to_remove.get('id')
                    existing_activities = [e for e in existing_activities if e.get('id') != hist_id]
                    if hist_id in existing_ids:
                        existing_ids.remove(hist_id)
                    fuzzy_existing[key].remove(hist_to_remove)
                    atp_absorption[act_id] = 1

            if not is_duplicate:
                existing_activities.append(act)
                existing_ids.add(act_id)
                if key not in fuzzy_existing:
                    fuzzy_existing[key] = []
                fuzzy_existing[key].append(act)
                added += 1
                
                # [NEW] Reconciliation Logic: Deduct sold units from Open Positions
                action_upper = action.upper()
                if "SELL" in action_upper or "SOLD" in action_upper:
                    open_positions = acct_data.get("positions", [])
                    closed_positions = acct_data.get("closed_positions", [])
                    sell_units = abs(float(act.get("units", 0)))
                    
                    if sell_units > 0:
                        pos_to_remove = []
                        for idx, p in enumerate(open_positions):
                            p_sym_obj = p.get('symbol', {})
                            p_sym = p_sym_obj.get('symbol', '') if isinstance(p_sym_obj, dict) else p_sym_obj
                            
                            if p_sym == sym:
                                p_units = float(p.get("units", 0))
                                deduction = min(p_units, sell_units)
                                p["units"] = p_units - deduction
                                sell_units -= deduction
                                
                                if p["units"] <= 0.0001:
                                    pos_to_remove.append(idx)
                                
                                if sell_units <= 0.0001:
                                    break
                                    
                        for idx in reversed(pos_to_remove):
                            closed_p = open_positions.pop(idx)
                            closed_positions.append(closed_p)
                            
                        acct_data["positions"] = open_positions
                        acct_data["closed_positions"] = closed_positions
                
        if added > 0:
            # Sort by trade_date or time_placed descending (newest first)
            existing_activities.sort(key=cls._parse_time, reverse=True)
            acct_data["activities"] = existing_activities
            cache[account_id] = acct_data
            cls._save_cache(cache)
            logger.info(f"Merged {added} new activities into brokerage cache for account {account_id}")
            
        return existing_activities

    @classmethod
    def get_closed_positions(cls, account_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieves explicitly set closed positions for the account, or None if not set.
        """
        cache = cls._load_cache()
        account_cache = cache.get(account_id, {})
        return account_cache.get("closed_positions", None)

    @classmethod
    def replace_closed_positions(cls, account_id: str, closed_positions: List[Dict[str, Any]]) -> None:
        """
        Replaces the explicit closed positions list for the account with a new list.
        """
        cache = cls._load_cache()
        if account_id not in cache:
            cache[account_id] = {"activities": [], "positions": [], "closed_positions": [], "balances": {}}
            
        cache[account_id]["closed_positions"] = closed_positions
        cls._save_cache(cache)
        logger.info(f"Replaced explicit closed positions for account {account_id} with {len(closed_positions)} items")

    @classmethod
    def calculate_realized_pnl(cls, account_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Calculates the Realized PnL for a given date range using a FIFO tax-lot engine.
        Returns a dict with total_pnl and a list of closed_trades.
        """
        activities = cls.get_activities(account_id)
        if not activities:
            return {"total_pnl": 0.0, "closed_trades": []}
            
        # Sort chronologically (oldest first) using parse_time
        chronological_acts = sorted(activities, key=cls._parse_time)
        
        from datetime import datetime
        from zoneinfo import ZoneInfo
        eastern_tz = ZoneInfo("America/New_York")
        now = datetime.now(eastern_tz)
        cutoff_date = datetime(now.year, now.month, 1, tzinfo=eastern_tz)
        cleared_orphans = False
        
        tax_lots = {} # dict of symbol -> list of {"qty": float, "price": float}
        realized_pnl = 0.0
        closed_trades = []
        
        for act in chronological_acts:
            # Check if we should clear orphaned trades from before this month
            trade_time = cls._parse_time(act)
            if not cleared_orphans and trade_time >= cutoff_date:
                tax_lots.clear()
                cleared_orphans = True
                
            action = act.get('type', act.get('action', 'N/A')).upper()
            if action not in ["BUY", "SELL", "BOUGHT", "SOLD", "BTO", "STC", "BTC", "STO", "REINVEST", "DIVIDEND"]:
                continue
                
            status = str(act.get('status', act.get('state', 'Executed'))).upper()
            if status in ["OPEN", "PENDING", "CANCELED", "CANCELLED", "EXPIRED", "REJECTED"]:
                continue

                
            sym_obj = act.get('symbol') or act.get('universal_symbol') or {}
            sym = sym_obj.get('symbol', act.get('symbol')) if isinstance(sym_obj, dict) else sym_obj
            if not sym or sym == 'N/A':
                continue
                
            sym_raw = str(sym).upper().replace('-USD', '').replace('*', '')
            qty = float(act.get('units', 0))
            price = float(act.get('price', 0))
            
            trade_date_str = str(act.get('trade_date', act.get('time_placed', '')) or '')
            date_only = trade_date_str[:10] if trade_date_str else "Unknown"
            
            in_range = False
            if start_date <= date_only <= end_date or date_only == "Unknown":
                in_range = True
                
            if sym_raw not in tax_lots:
                tax_lots[sym_raw] = []
                
            if action in ["BUY", "BOUGHT", "BTO", "BTC", "REINVEST", "DIVIDEND"]:
                tax_lots[sym_raw].append({"qty": qty, "price": price})
            elif action in ["SELL", "SOLD", "STC", "STO"]:
                sell_qty_remaining = qty
                trade_pnl = 0.0
                total_cost_basis = 0.0
                qty_matched = 0.0
                
                while sell_qty_remaining > 0.0001 and len(tax_lots[sym_raw]) > 0:
                    lot = tax_lots[sym_raw][0]
                    if lot["qty"] <= sell_qty_remaining:
                        # Consume entire lot
                        trade_pnl += (price - lot["price"]) * lot["qty"]
                        total_cost_basis += lot["price"] * lot["qty"]
                        qty_matched += lot["qty"]
                        sell_qty_remaining -= lot["qty"]
                        tax_lots[sym_raw].pop(0)
                    else:
                        # Consume partial lot
                        trade_pnl += (price - lot["price"]) * sell_qty_remaining
                        total_cost_basis += lot["price"] * sell_qty_remaining
                        qty_matched += sell_qty_remaining
                        lot["qty"] -= sell_qty_remaining
                        sell_qty_remaining = 0.0
                
                # If we still have sell_qty_remaining, we don't have cost basis data in our imported tax lots.
                # Fall back to the average cost from the Positions CSV if available.
                if sell_qty_remaining > 0.0001:
                    fallback_cost = 0.0
                    positions = cls.get_positions(account_id)
                    for p in positions:
                        if p.get('symbol') == sym_raw:
                            fallback_cost = float(p.get('average_cost') or 0.0)
                            break
                            
                    if fallback_cost > 0.0:
                        trade_pnl += (price - fallback_cost) * sell_qty_remaining
                        total_cost_basis += fallback_cost * sell_qty_remaining
                        qty_matched += sell_qty_remaining
                        sell_qty_remaining = 0.0
                    
                avg_cost = (total_cost_basis / qty_matched) if qty_matched > 0 else 0.0
                
                if in_range and qty_matched > 0:
                    realized_pnl += trade_pnl
                    closed_trades.append({
                        "symbol": sym_raw,
                        "close_date": trade_date_str,
                        "qty": qty_matched,
                        "sell_price": price,
                        "buy_price": avg_cost,
                        "pnl": trade_pnl,
                        "pnl_pct": (trade_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0.0
                    })
                    
        return {"total_pnl": realized_pnl, "closed_trades": closed_trades}

