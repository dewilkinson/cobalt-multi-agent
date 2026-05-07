import os
import json
import logging
from typing import List, Dict, Any, Optional

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
                        
                reports_dir = os.path.join(os.getcwd(), 'data', 'reports')
                if os.path.exists(reports_dir):
                    reports_backup = os.path.join(archive_dir, f"AnalysisReportsBackup_{date_str}")
                    shutil.make_archive(reports_backup, 'zip', reports_dir)
                    logger.info(f"Backed up internal reports to {reports_backup}.zip")
                    
            except Exception as e:
                logger.error(f"Failed to backup extra directories during weekly cron: {e}")
            
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
            
        # Sort chronologically (oldest first)
        def get_sort_key(act):
            return act.get('trade_date', act.get('time_placed', ''))
        
        chronological_acts = sorted(activities, key=get_sort_key)
        
        tax_lots = {} # dict of symbol -> list of {"qty": float, "price": float}
        realized_pnl = 0.0
        closed_trades = []
        
        for act in chronological_acts:
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
            
            trade_date_str = get_sort_key(act)
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

