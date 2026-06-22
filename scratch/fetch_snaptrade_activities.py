import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from snaptrade_client import SnapTrade

# Load the environment variables from the backend .env
backend_env_path = "backend/.env"
if os.path.exists(backend_env_path):
    load_dotenv(backend_env_path)
    print("Loaded env from backend/.env")
else:
    print("backend/.env not found!")
    exit(1)

client_id = os.getenv("SNAPTRADE_CLIENT_ID", "").strip()
consumer_key = os.getenv("SNAPTRADE_CONSUMER_KEY", "").strip()
user_id = os.getenv("SNAPTRADE_USER_ID", "").strip()
user_secret = os.getenv("SNAPTRADE_USER_SECRET", "").strip()

print(f"SnapTrade Client ID: {client_id}")
print(f"SnapTrade User ID: {user_id}")

if not client_id or not consumer_key or not user_id or not user_secret:
    print("SnapTrade credentials are not fully configured in backend/.env!")
    exit(1)

try:
    print("Initializing SnapTrade client...")
    client = SnapTrade(client_id=client_id, consumer_key=consumer_key)
    
    print("Listing user accounts...")
    accounts_res = client.account_information.list_user_accounts(user_id=user_id, user_secret=user_secret)
    accounts = getattr(accounts_res, 'body', accounts_res)
    print(f"Found {len(accounts)} accounts.")
    
    start_date = "2026-05-15"
    end_date = "2026-05-23"
    print(f"Fetching activities between {start_date} and {end_date}...")
    
    all_activities = []
    for acc in accounts:
        acc_id = acc.get('id') if isinstance(acc, dict) else getattr(acc, 'id', None)
        acc_name = acc.get('name', 'Unknown') if isinstance(acc, dict) else getattr(acc, 'name', 'Unknown')
        if not acc_id:
            continue
        print(f"Querying account {acc_name} ({acc_id})...")
        try:
            api_response = client.transactions_and_reporting.get_activities(
                user_id=user_id,
                user_secret=user_secret,
                accounts=acc_id,
                start_date=start_date,
                end_date=end_date
            )
            activities = getattr(api_response, 'body', api_response)
            if isinstance(activities, list):
                print(f"  Received {len(activities)} activities.")
                for act in activities:
                    # Inject account name for reference
                    if isinstance(act, dict):
                        act['account_name'] = acc_name
                    all_activities.append(act)
            else:
                print(f"  Unexpected response format: {type(activities)}")
        except Exception as e:
            print(f"  Error fetching activities for account {acc_id}: {e}")
            
    print(f"\nTotal activities fetched: {len(all_activities)}")
    
    # Save to a temporary JSON file so we can analyze it
    output_path = "scratch/snaptrade_raw_activities.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_activities, f, indent=2)
    print(f"Saved raw activities to {output_path}")
    
    # Print out summary
    print("\nSummary of activities:")
    for act in all_activities:
        if isinstance(act, dict):
            # Parse symbol
            sym = ""
            if 'universal_symbol' in act and act['universal_symbol']:
                sym = act['universal_symbol'].get('symbol', '')
            elif 'symbol' in act and act['symbol'] and isinstance(act['symbol'], dict):
                sym = act['symbol'].get('symbol', '')
            elif 'symbol' in act and isinstance(act['symbol'], str):
                sym = act['symbol']
                
            date = act.get('trade_date') or act.get('date') or act.get('timestamp')
            action = act.get('type') or act.get('action')
            units = act.get('units') or act.get('quantity')
            price = act.get('price')
            print(f"Account: {act.get('account_name')} | Date: {date} | Symbol: {sym} | Action: {action} | Units: {units} | Price: {price}")
            
except Exception as e:
    print(f"Error during execution: {e}")
