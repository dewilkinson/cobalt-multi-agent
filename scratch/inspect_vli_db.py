import sqlite3
import pandas as pd

db_path = r"backend/data/vli_main.db"
conn = sqlite3.connect(db_path)

# List tables
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables in vli_main.db:", tables)

for t in tables:
    t_name = t[0]
    cursor.execute(f"SELECT COUNT(*) FROM {t_name}")
    count = cursor.fetchone()[0]
    print(f"Table {t_name} has {count} rows")
    
    # Show first 3 rows
    try:
        df = pd.read_sql_query(f"SELECT * FROM {t_name} LIMIT 3", conn)
        print("Columns:", df.columns)
        print(df)
    except Exception as e:
        print(e)
    print("="*40)
    
conn.close()
