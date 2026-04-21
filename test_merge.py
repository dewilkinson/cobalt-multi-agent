from backend.src.tools.scanner import sanitize_data

match = {"symbol": "AIP", "grade": "C"}
p = {"symbol": "AIP", "grade": "S", "heat_score": 100, "raw_power": 76.5}

merged = sanitize_data({**match, **p})
print("Merged:", merged)
