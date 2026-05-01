import json
with open('data/brokerage_cache.json', encoding='utf-8') as f: cache = json.load(f)
acts = list(cache.values())[0]
acts = list(reversed(acts))
daily_counters = {}
for act in acts[:5]:
    placed_time = act.get('trade_date') or act.get('time_placed') or ''
    date_only = str(placed_time)[:10] if placed_time else 'Unknown'
    real_time = None
    if placed_time and isinstance(placed_time, str):
        if 'T' in placed_time:
            real_time = placed_time.split('T')[1][:8]
        elif ':' in placed_time:
            real_time = placed_time.split(' ')[-1]
    if real_time:
        fmt_time = f'{date_only} {real_time}'
    else:
        if date_only not in daily_counters:
            daily_counters[date_only] = 0
        daily_counters[date_only] += 1
        seconds = daily_counters[date_only]
        minutes = seconds // 60
        remaining_secs = seconds {30 + minutes:02d}:{remaining_secs:02d}'
        fmt_time = f'{date_only} {synth_time}'
    print(f'fmt_time: {fmt_time}')
