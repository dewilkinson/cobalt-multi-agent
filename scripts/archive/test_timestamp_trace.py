import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Trace")

def trace_timestamp(placed_time, date_only_override=None):
    placed_time_str = str(placed_time) if placed_time else ""
    date_only = str(placed_time)[:10] if placed_time else "Unknown"
    if date_only_override:
        date_only = date_only_override
        
    real_time = None
    if placed_time_str:
        if 'T' in placed_time_str:
            real_time = placed_time_str.split('T')[1][:8]
        elif ' ' in placed_time_str:
            real_time = placed_time_str.split(' ')[-1][:8]
            
    # Check if it's a default SnapTrade midnight UTC/EDT time
    is_midnight = False
    if real_time and (real_time.startswith('00:00') or real_time.startswith('04:00') or real_time.startswith('05:00')):
        is_midnight = True
        real_time = None
        
    logger.info(f"Trace -> placed_time: {repr(placed_time)}, type: {type(placed_time)}, placed_time_str: {repr(placed_time_str)}, extracted real_time: {real_time}, is_midnight: {is_midnight}")
    
    return real_time, date_only

def main():
    try:
        with open('data/brokerage_cache.json', encoding='utf-8') as f:
            cache = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load cache: {e}")
        return
        
    for account_id, acts in cache.items():
        logger.info(f"--- Account {account_id} ---")
        acts_rev = list(reversed(acts))
        for act in acts_rev[:10]: # Test first 10
            sym = act.get('symbol', {}).get('symbol') if isinstance(act.get('symbol'), dict) else act.get('symbol')
            if not sym and isinstance(act.get('universal_symbol'), dict):
                sym = act['universal_symbol'].get('symbol')
                
            placed_time = act.get('trade_date') or act.get('time_placed') or act.get('trade_time') or act.get('timestamp') or act.get('time') or act.get('date') or ''
            real_time, date_only = trace_timestamp(placed_time)
            
            if real_time:
                fmt_time = f"{date_only} {real_time}"
            else:
                fmt_time = f"{date_only} 09:30:xx (FALLBACK)"
                
            logger.info(f"Symbol: {sym}, Final Time: {fmt_time}")

if __name__ == '__main__':
    main()
