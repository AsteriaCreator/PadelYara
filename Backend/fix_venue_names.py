"""
Fix venue names: prepend operator brand where name doesn't already contain it.
Rule: for operators with ≥2 venues (chains), if name doesn't start with or
contain the operator's first word → rename to "Operator Name".
"""
import os, sys
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")

from pymongo import MongoClient
from dotenv import load_dotenv
from collections import Counter

load_dotenv("Backend/.env")
client = MongoClient(os.getenv("MONGODB_URI"))
db = client["padel_checker"]

venues = list(db.venues.find({}, {"_id": 1, "id": 1, "name": 1, "operator": 1}))

# Count venues per operator to find chains
operator_counts = Counter(v.get("operator", "").strip() for v in venues if v.get("operator"))

PROPOSED = []

for v in venues:
    op = (v.get("operator") or "").strip()
    name = (v.get("name") or "").strip()

    if not op or not name:
        continue

    # Only process chain operators (≥2 venues)
    if operator_counts[op] < 2:
        continue

    # Skip if name already contains the operator (case-insensitive)
    if op.lower() in name.lower():
        continue

    # Skip if first word of operator already appears in name
    first_word = op.split()[0]
    if first_word.lower() in name.lower():
        continue

    # Handle CamelCase operators: "PadelBeach" → "padel" + "beach"
    # If the operator without spaces matches the name without spaces, skip.
    if op.lower().replace(" ", "") in name.lower().replace(" ", ""):
        continue

    new_name = f"{op} {name}"
    PROPOSED.append((v["_id"], v.get("id", "?"), name, new_name, op))

print(f"Found {len(PROPOSED)} venues to rename:\n")
for _id, vid, old, new, op in PROPOSED:
    print(f"  [{op}]  '{old}'  →  '{new}'")

print()
confirm = input("Apply all? (y/n): ").strip().lower()
if confirm != "y":
    print("Aborted.")
    sys.exit(0)

fixed = 0
for _id, vid, old, new, op in PROPOSED:
    result = db.venues.update_one({"_id": _id}, {"$set": {"name": new}})
    if result.modified_count:
        fixed += 1
        print(f"  ✓ '{old}'  →  '{new}'")

print(f"\nFixed {fixed} venue names.")
