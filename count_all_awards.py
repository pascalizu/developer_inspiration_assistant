import json
import re
from collections import defaultdict

def normalize_award(award: str) -> str:
    """Normalize award names to lowercase with collapsed whitespace."""
    if not award:
        return None
    award = award.strip().lower()
    award = re.sub(r"\s+", " ", award)
    award = re.sub(r"['`]+", "", award)
    # Remove common prefixes/suffixes
    award = re.sub(r"\b(at the|for|in|with)\b", "", award).strip()
    # Filter invalid awards
    if (len(award) < 5 or
        re.search(r"\b(it|this|because|from|classification|usecases|trending|topics|way)\b", award) or
        re.search(r"\d+", award) or
        len(award.split()) > 5):
        return None
    return award

def extract_awards(desc: str, json_awards: list = None):
    """Extract valid awards from description and JSON awards."""
    awards = json_awards or []
    valid_keywords = [
        "best overall project", "most innovative project", "most promising innovation",
        "best technical implementation", "distinguished technical deep-dive",
        "the imagenet competition in 2012", "innovative approach", "outstanding contribution"
    ]
    
    extracted = []
    unmatched = []
    # Process JSON awards
    for award in awards:
        norm_award = normalize_award(award)
        if norm_award and any(vk in norm_award or norm_award in vk for vk in valid_keywords):
            extracted.append(norm_award)
        elif norm_award:
            unmatched.append(award)

    # Patterns for description
    patterns = [
        r"award[:\-]?\s*([A-Za-z\s\-]{5,40})(?=\s*(?:$|\n|\.|,|;))",
        r"winner of\s*([A-Za-z\s\-]{5,40})(?=\s*(?:$|\n|\.|,|;))",
        r"received\s*([A-Za-z\s\-]{5,40})(?=\s*(?:$|\n|\.|,|;))",
        r"won\s*([A-Za-z\s\-]{5,40})(?=\s*(?:$|\n|\.|,|;))",
        r"(?:best|most|top|outstanding|innovative|promising)\s+([A-Za-z\s\-]{5,40})(?=\s*(?:$|\n|\.|,|;))"
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, desc, re.IGNORECASE)
        for match in matches:
            norm_award = normalize_award(match)
            if norm_award and any(vk in norm_award or norm_award in vk for vk in valid_keywords):
                extracted.append(norm_award)
            elif norm_award:
                unmatched.append(match)

    # Log unmatched awards for debugging
    if unmatched:
        print(f"Unmatched awards: {unmatched}")

    return list(set(extracted))

# Load dataset
with open("data/readytensor_awards.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Count awards
award_counts = defaultdict(set)
for pub in data:
    pub_id = pub["id"]
    awards = extract_awards(pub.get("publication_description", ""), pub.get("awards", []))
    for award in awards:
        award_counts[award].add(pub_id)

# Print results
print(f"Total publications: {len(data)}")
for award, pub_ids in sorted(award_counts.items()):
    print(f"\nAward: {award}")
    print(f"Publications: {len(pub_ids)}")
    for pub_id in pub_ids:
        pub = next(p for p in data if p["id"] == pub_id)
        print(f"- ID: {pub_id} | Title: {pub['title']} | Awards: {pub['awards']}")