import sqlite3
import pandas as pd
import json

db_path = r"backend/data/vli_main.db"
conn = sqlite3.connect(db_path)

# List unique resource types in persistent_cache
df_types = pd.read_sql_query("SELECT DISTINCT resource_type, timeframe FROM persistent_cache", conn)
print("Unique resource types & timeframes in persistent_cache:")
print(df_types)

# Find entries for ARM
df_arm = pd.read_sql_query("SELECT * FROM persistent_cache WHERE ticker='ARM'", conn)
print(f"\nFound {len(df_arm)} entries for ARM:")
for idx, row in df_arm.iterrows():
    print(f"Resource: {row['resource_type']} | Timeframe: {row['timeframe']} | Created: {row['created_at']}")
    try:
        data = json.loads(row['data'])
        print(f"Data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
        if isinstance(data, list) and len(data) > 0:
            print("First item:", data[0])
        elif isinstance(data, dict):
            # Print a snippet of keys
            for k, v in list(data.items())[:2]:
                print(f"  {k}: {str(v)[:100]}")
    except Exception as e:
        print("Error parsing data:", e)
    print("-"*40)

conn.close()
