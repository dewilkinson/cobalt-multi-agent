import csv
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
target_file = os.path.join(BASE_DIR, "data", "exports", "tradezella-import-TopStepX.csv")

def audit_pnl():
    if not os.path.exists(target_file):
        print(f"File not found: {target_file}")
        return

    with open(target_file, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    print(f"Total Trade Rows: {len(rows)}\n")

    gross_pnl = 0.0
    total_fees = 0.0
    total_comm = 0.0

    print("Index | Ticker | Type | Qty | Entry | Exit | Gross PnL | Fees | Comm | Net PnL")
    print("-" * 80)

    for i, r in enumerate(rows):
        pnl = float(r.get('PnL', 0))
        fees = float(r.get('Fees', 0))
        comm = float(r.get('Commissions', 0))
        contract = r.get('ContractName', '')
        trade_type = r.get('Type', '')
        size = r.get('Size', '')
        entry_p = r.get('EntryPrice', '')
        exit_p = r.get('ExitPrice', '')

        gross_pnl += pnl
        total_fees += fees
        total_comm += comm

        net = pnl - fees - comm
        print(f"{i+1:2d}    | {contract:6s} | {trade_type:5s} | {size:3s} | {entry_p} | {exit_p} | ${pnl:8.2f} | ${fees:5.2f} | ${comm:5.2f} | ${net:8.2f}")

    net_total = gross_pnl - total_fees - total_comm

    print("-" * 80)
    print(f"Sum Gross PnL       : ${gross_pnl:10.2f}")
    print(f"Sum Fees            : ${total_fees:10.2f}")
    print(f"Sum Commissions     : ${total_comm:10.2f}")
    print(f"Net Total PnL       : ${net_total:10.2f}")
    print(f"User Stated Total   : $ 1411.00")
    print(f"TradeZella Reported : $  891.71")
    print(f"Difference (User - TZ): ${1411.00 - 891.71:.2f}")

if __name__ == "__main__":
    audit_pnl()
