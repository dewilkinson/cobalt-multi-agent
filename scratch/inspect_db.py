import sqlite3

def main():
    conn = sqlite3.connect('backend/data/vli_main.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT resource_type FROM persistent_cache;")
    print("Distinct resource types in persistent_cache:")
    for r in cursor.fetchall():
        print(f"  {r[0]}")
        
    cursor.execute("SELECT ticker, resource_type, timeframe, created_at FROM persistent_cache LIMIT 10;")
    print("\nSample rows:")
    for r in cursor.fetchall():
        print(f"  {r}")

if __name__ == "__main__":
    main()
