import sqlite3
import os
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "watchlists.db"))

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            color TEXT NOT NULL,
            symbol TEXT NOT NULL,
            filename TEXT,
            imported_at TEXT,
            UNIQUE(date, color, symbol)
        )
    """)
    conn.commit()
    conn.close()

def save_watchlist_entries(entries: list):
    """
    entries is a list of tuples: (date, color, symbol, filename, imported_at)
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.executemany("""
            INSERT OR REPLACE INTO watchlists (date, color, symbol, filename, imported_at)
            VALUES (?, ?, ?, ?, ?)
        """, entries)
        conn.commit()
        logger.info(f"Saved {len(entries)} watchlist entries to database.")
    except Exception as e:
        logger.error(f"Failed to insert watchlist entries: {e}")
    finally:
        conn.close()

def resolve_color_from_filename(filename: str) -> str:
    lower = filename.lower()
    if "primary" in lower or "cyan" in lower:
        return "Cyan"
    elif "rejected" in lower or "red" in lower:
        return "Red"
    elif "potential" in lower or "pink" in lower:
        return "Pink"
    elif "gold" in lower or "yellow" in lower:
        return "Gold"
    return "Unknown"

def resolve_date_from_filename(filename: str, file_path: str) -> str:
    match = re.search(r"(\d{4})[-_](\d{2})[-_](\d{2})", filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    try:
        mtime = os.path.getmtime(file_path)
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except:
        return datetime.now().strftime("%Y-%m-%d")

def parse_watchlist_file(file_path: str, default_color: str) -> list:
    symbols_with_colors = []
    active_color = default_color
    
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
                
            # Check for header color section
            if line.startswith("#"):
                clean_header = line.lstrip("#").strip().lower()
                if "primary" in clean_header or "cyan" in clean_header:
                    active_color = "Cyan"
                elif "rejected" in clean_header or "red" in clean_header:
                    active_color = "Red"
                elif "potential" in clean_header or "pink" in clean_header:
                    active_color = "Pink"
                elif "gold" in clean_header or "yellow" in clean_header:
                    active_color = "Gold"
                continue
                
            # Parse symbol line (e.g., NASDAQ:AAPL or AAPL or AAPL, comment)
            parts = line.split(",")
            raw_sym = parts[0].strip()
            
            # Remove exchange prefix if present (e.g., BATS:OSCR or NASDAQ:AAPL)
            if ":" in raw_sym:
                raw_sym = raw_sym.split(":")[-1].strip()
                
            sym = raw_sym.upper()
            if sym.isalnum() and 1 <= len(sym) <= 6:
                symbols_with_colors.append((sym, active_color))
                
    return symbols_with_colors
