import os
import sys
from dotenv import load_dotenv

# Try to import snaptrade_client
try:
    from snaptrade_client import SnapTrade
except ImportError:
    print("Error: snaptrade_client not found. Please run this script in an environment where it is installed.")
    sys.exit(1)

def main():
    # Determine absolute paths to .env files
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backend_env = os.path.join(base_dir, "backend", ".env")
    web_env = os.path.join(base_dir, "web", ".env")
    
    loaded = False
    if os.path.exists(backend_env):
        load_dotenv(backend_env, override=True)
        loaded = True
        print(f"Loaded variables from: {backend_env}")
    if os.path.exists(web_env):
        load_dotenv(web_env, override=True)
        print(f"Loaded variables from: {web_env}")

    client_id = os.getenv("SNAPTRADE_CLIENT_ID")
    consumer_key = os.getenv("SNAPTRADE_CONSUMER_KEY")
    user_id = os.getenv("SNAPTRADE_USER_ID")

    if not all([client_id, consumer_key, user_id]):
        print("Error: Missing SNAPTRADE_CLIENT_ID, SNAPTRADE_CONSUMER_KEY, or SNAPTRADE_USER_ID in .env.")
        print("Please ensure these are populated before running the rotation script.")
        sys.exit(1)

    print(f"Rotating SnapTrade User Secret for user ID: {user_id}...")
    client = SnapTrade(client_id=client_id, consumer_key=consumer_key)
    
    try:
        print("Deleting existing user (if any)...")
        try:
            client.authentication.delete_snap_trade_user(user_id=user_id)
        except Exception as e:
            print(f"(Note: Deletion skipped or failed: {e})")
            pass

        print("Registering new user to generate secret...")
        response = client.authentication.register_snap_trade_user(user_id=user_id)
        
        new_secret = getattr(response, 'user_secret', None)
        if not new_secret and isinstance(response, dict):
            new_secret = response.get('userSecret') or response.get('user_secret')
            
        print("\n--- SUCCESS ---")
        print(f"New User Secret: {new_secret}")
        if not new_secret:
            print("\nWARNING: No secret was returned.")
        else:
            print("\nIMPORTANT: Please manually update SNAPTRADE_USER_SECRET in your backend/.env and web/.env files with the value above.")
    except Exception as e:
        print(f"\nFailed to retrieve secret: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
