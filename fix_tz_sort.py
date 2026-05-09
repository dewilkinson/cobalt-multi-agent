import csv

input_csv = 'data/exports/tradezella-import.csv'

with open(input_csv, 'r', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    trades = list(reader)

trades.sort(key=lambda x: (x['Date'], x['Symbol'], 0 if x['Buy/Sell'].lower() == 'buy' else 1))

with open(input_csv, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=trades[0].keys())
    writer.writeheader()
    writer.writerows(trades)
print('Sorted successfully.')
