import json
import os
from zoneinfo import ZoneInfo
from datetime import datetime

def parse_time(act):
    t_str = act.get('trade_date', '') or act.get('time_placed', '')
    eastern_tz = ZoneInfo("America/New_York")
    if not t_str:
        return datetime.min.replace(tzinfo=eastern_tz)
    
    if t_str.endswith('Z'):
        try:
            dt = datetime.fromisoformat(t_str.replace('Z', '+00:00'))
            return dt.astimezone(eastern_tz)
        except Exception:
            pass
            
    # Try parsing Month-Day-Year (e.g. Oct-7-2025 or May-20-2026)
    if '-' in t_str and not t_str.startswith('20'):
        try:
            dt = datetime.strptime(t_str, "%b-%d-%Y")
            return dt.replace(tzinfo=eastern_tz)
        except Exception:
            pass
            
    # Try parsing Month/Day/Year (e.g. 10/7/2025)
    if '/' in t_str:
        try:
            dt = datetime.strptime(t_str, "%m/%d/%Y")
            return dt.replace(tzinfo=eastern_tz)
        except Exception:
            try:
                dt = datetime.strptime(t_str, "%m/%d/%y")
                return dt.replace(tzinfo=eastern_tz)
            except Exception:
                pass
                
    try:
        t_str_clean = t_str
        if t_str_clean.endswith('Z'):
            t_str_clean = t_str_clean[:-1]
            
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
            
        if dt.tzinfo is not None:
            dt = dt.astimezone(eastern_tz)
        else:
            dt = dt.replace(tzinfo=eastern_tz)
        return dt
    except Exception:
        try:
            dt = datetime.fromisoformat(t_str.replace('Z', '+00:00'))
            return dt.astimezone(eastern_tz)
        except Exception:
            return datetime.min.replace(tzinfo=eastern_tz)

project_root = r"c:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent"
cache_file = os.path.join(project_root, "backend", "data", "brokerage_cache.json")

with open(cache_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

activities = data.get("Rollover IRA *5513", {}).get("activities", [])
for act in activities:
    if act.get('price') == 23.045:
        print(act)

