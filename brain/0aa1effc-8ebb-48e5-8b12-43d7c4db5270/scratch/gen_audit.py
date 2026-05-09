import csv
import sys
import io

# Force stdout to use utf-8 for Windows console emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def generate_audit_table(import_file):
    trades = []
    with open(import_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trades.append(row)
    
    # Group by Date and Symbol
    groups = {}
    for t in trades:
        key = (t['Date'], t['Symbol'])
        if key not in groups:
            groups[key] = []
        groups[key].append(t)
    
    # Sort groups by Date (latest first for audit)
    sorted_keys = sorted(groups.keys(), key=lambda x: (x[0].split('/')[2], x[0].split('/')[0], x[0].split('/')[1]), reverse=True)
    
    table_rows = []
    for date, symbol in sorted_keys:
        group = groups[(date, symbol)]
        # Sort group by time
        group.sort(key=lambda x: x['Time'])
        
        first = group[0]
        last = group[-1]
        
        first_action = f"{first['Buy/Sell']} ({first['Time']})"
        
        # Determine if it's a day trade or a partial
        has_buy = any(t['Buy/Sell'] == 'Buy' for t in group)
        has_sell = any(t['Buy/Sell'] == 'Sell' for t in group)
        
        if has_buy and has_sell:
            # Find the first buy and the first sell for the "First/Second Action" columns
            # to match the "Entry/Exit" feel of the image.
            b_trades = [t for t in group if t['Buy/Sell'] == 'Buy']
            s_trades = [t for t in group if t['Buy/Sell'] == 'Sell']
            
            row_first_action = f"Buy ({b_trades[0]['Time']})"
            row_second_action = f"Sell ({s_trades[0]['Time']})"
            result = " Long"
        elif has_buy:
            row_first_action = f"Buy ({group[0]['Time']})"
            row_second_action = "-"
            result = " Long-Open"
        else:
            row_first_action = f"Sell ({group[0]['Time']})"
            row_second_action = "-"
            result = " Long-Close"
            
        table_rows.append([date, symbol, row_first_action, row_second_action, result])

    # Print markdown table
    print("| Date | Symbol | First Action | Second Action | Result |")
    print("| :--- | :--- | :--- | :--- | :--- |")
    for row in table_rows[:100]:
        print(f"| {row[0]} | **{row[1]}** | {row[2]} | {row[3]} | {row[4]} |")

if __name__ == "__main__":
    generate_audit_table("c:/github/cobalt-multi-agent/tools/csv-to-tradezella/logs/tradezella-import.txt")
