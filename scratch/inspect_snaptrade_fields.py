import json

with open("scratch/snaptrade_raw_activities.json", "r", encoding="utf-8") as f:
    data = json.load(f)

if not data:
    print("No activities found in file.")
    exit(0)

# Print a couple of sample records completely
print("Sample Activity 1:")
print(json.dumps(data[0], indent=2))
print("\nSample Activity 2:")
print(json.dumps(data[1], indent=2))
