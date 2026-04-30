import os
import sys
import argparse

# Add backend to path to import backend services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))
from src.services.brokerage_cache import BrokerageCache
from src.services.atp_importer import parse_atp_orders, parse_atp_history, parse_atp_positions, get_dropzone_csvs

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import ATP CSVs into BrokerageCache")
    parser.add_argument("-o", "--orders", default=None, help="Path to Orders_All_Accounts.csv")
    parser.add_argument("-H", "--history", default=None, help="Path to Accounts_History.csv")
    parser.add_argument("-p", "--positions", default=None, help="Path to Positions_All_Accounts.csv")
    args = parser.parse_args()
    
    csvs = get_dropzone_csvs()
    
    orders_csv = args.orders or csvs["orders"]
    history_csv = args.history or csvs["history"]
    positions_csv = args.positions or csvs["positions"]
    
    # 1. Orders
    if orders_csv:
        print(f"Parsing Orders CSV: {orders_csv}")
        new_acts_by_account = parse_atp_orders(orders_csv)
        total_injected = sum(len(acts) for acts in new_acts_by_account.values())
        print(f"Found {total_injected} executions across {len(new_acts_by_account)} accounts.")
        for account, acts in new_acts_by_account.items():
            BrokerageCache.merge_activities(account, acts)
            print(f"[{account}] Merged {len(acts)} trades.")
            
    # 2. History
    if history_csv:
        print(f"Parsing History CSV: {history_csv}")
        hist_acts_by_account = parse_atp_history(history_csv)
        total_injected = sum(len(acts) for acts in hist_acts_by_account.values())
        print(f"Found {total_injected} executions across {len(hist_acts_by_account)} accounts.")
        for account, acts in hist_acts_by_account.items():
            BrokerageCache.merge_activities(account, acts)
            print(f"[{account}] Merged {len(acts)} historical trades.")
            
    # 3. Positions
    if positions_csv:
        print(f"Parsing Positions CSV: {positions_csv}")
        pos_by_account = parse_atp_positions(positions_csv)
        total_pos = sum(len(p) for p in pos_by_account.values())
        print(f"Found {total_pos} positions across {len(pos_by_account)} accounts.")
        for account, pos in pos_by_account.items():
            BrokerageCache.set_positions(account, pos)
            print(f"[{account}] Set {len(pos)} explicit positions.")

    print("Success! All selected files imported.")
