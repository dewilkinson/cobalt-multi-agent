import os
from snaptrade_client import SnapTrade
from dotenv import load_dotenv

load_dotenv("client/.env")

client_id = os.getenv("SNAPTRADE_CLIENT_ID")
consumer_key = os.getenv("SNAPTRADE_CONSUMER_KEY")
user_id = os.getenv("SNAPTRADE_USER_ID")

print(f"DEBUG: Using ID={client_id}, KEY={consumer_key}, USER={user_id}")

def try_register(host):
    print(f"\n--- Testing Host: {host} ---")
    try:
        client = SnapTrade(
            client_id=client_id,
            consumer_key=consumer_key,
            host=host
        )
        response = client.authentication.register_snap_trade_user(user_id=user_id)
        return response.body
    except Exception as e:
        return e

hosts = [
    "https://api.snaptrade.com/api/v1",
    "https://sandbox.snaptrade.com/api/v1"
]

for host in hosts:
    result = try_register(host)
    if isinstance(result, dict):
        print(f"SUCCESS on {host}!")
        print(f"USER_ID: {user_id}")
        print(f"USER_SECRET: {result.get('userSecret')}")
        exit(0)
    else:
        print(f"FAILED on {host}: {result}")

print("\nCONCLUSION: Both Production and Sandbox rejected these keys. Ensure they are EXACTLY as shown in the Dashboard.")
