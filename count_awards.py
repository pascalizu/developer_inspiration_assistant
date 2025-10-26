import json
import re

DATA_FILE = "data/readytensor_awards.json"

try:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"❌ Could not find {DATA_FILE}. Ensure it's in the 'data' folder.")
    exit(1)

for award_search in ["best overall project", "most innovative project"]:
    count_awards = sum(1 for pub in data if any(award_search in a.lower() for a in pub.get("awards", [])))
    count_text = sum(1 for pub in data if award_search in pub.get("publication_description", "").lower())
    unique_ids = set()
    for pub in data:
        if any(award_search in a.lower() for a in pub.get("awards", [])) or award_search in pub.get("publication_description", "").lower():
            unique_ids.add(pub["id"])
    print(f"\nTotal publications in dataset: {len(data)}")
    print(f"Publications with '{award_search}' in awards array: {count_awards}")
    print(f"Publications with '{award_search}' in description text: {count_text}")
    print(f"Total unique publications with '{award_search}': {len(unique_ids)}")
    print(f"Publications with '{award_search}':")
    for pub in data:
        if any(award_search in a.lower() for a in pub.get("awards", [])) or award_search in pub.get("publication_description", "").lower():
            print(f"- ID: {pub['id']} | Title: {pub['title']} | Awards: {pub['awards']} | Description mention: {award_search in pub.get('publication_description', '').lower()}")