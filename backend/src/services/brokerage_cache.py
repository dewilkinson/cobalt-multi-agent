import os
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "brokerage_cache.json"))

class BrokerageCache:
    """
    Manages a local disk cache for SnapTrade brokerage activities to prevent
    rate limits and reduce latency on long historical fetches.
    """
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
    def backup_cache(cls, is_weekly: bool = False) -> None:
        """
        Takes a scheduled backup of the current brokerage cache.
        """
        if not os.path.exists(CACHE_FILE):
            return
            
        import shutil
        from datetime import datetime
        
        base_dir = os.path.dirname(CACHE_FILE)
        filename = os.path.basename(CACHE_FILE)
        name, ext = os.path.splitext(filename)
        
        archive_dir = os.path.join(base_dir, "archive")
        os.makedirs(archive_dir, exist_ok=True)
        
        if is_weekly:
            date_str = datetime.now().strftime("%Y-%m-%d")
            backup_path = os.path.join(archive_dir, f"BrokerageCacheBackup_{date_str}{ext}")
            shutil.copy2(CACHE_FILE, backup_path)
            logger.info(f"Created weekly BrokerageCache backup: {backup_path}")
        else:
            backup_path = os.path.join(archive_dir, f"BrokerageCacheDailyBackup{ext}")
            shutil.copy2(CACHE_FILE, backup_path)
            logger.info(f"Created daily BrokerageCache backup: {backup_path}")

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
        acct_data = cache.get(account_id, {"activities": [], "positions": []})
        if isinstance(acct_data, list):
            acct_data = {"activities": acct_data, "positions": []}
            
        existing_activities = acct_data.get("activities", [])
        
        # Build a set of existing IDs for fast lookup
        existing_ids = {act['id'] for act in existing_activities if 'id' in act}
        
        # Add new activities
        added = 0
        for act in new_activities:
            act_id = act.get('id')
            if not act_id or act_id not in existing_ids:
                existing_activities.append(act)
                if act_id:
                    existing_ids.add(act_id)
                added += 1
                
        if added > 0:
            # Sort by trade_date or time_placed descending (newest first)
            def get_sort_key(act):
                return act.get('trade_date', act.get('time_placed', ''))
                
            existing_activities.sort(key=get_sort_key, reverse=True)
            acct_data["activities"] = existing_activities
            cache[account_id] = acct_data
            cls._save_cache(cache)
            logger.info(f"Merged {added} new activities into brokerage cache for account {account_id}")
            
        return existing_activities
