import csv
with open(r'C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\data\dropzone\archive\Orders_All_Accounts.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        sym = row.get("Symbol", "")
        if sym == "XLI":
            status = row.get("Status", "")
            print(f"XLI Status: {repr(status)}")
            try:
                price_str = status.split("$")[-1] if "$" in status and "Filled" in status else "0"
                print(f"Extracted string: {repr(price_str)}")
                price = float(price_str.replace(',', ''))
                print(f"Float price: {price}")
            except Exception as e:
                print(f"Error: {e}")
