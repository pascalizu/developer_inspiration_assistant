import json
import os
from datetime import datetime
import requests
from bs4 import BeautifulSoup

OUTPUT_FILE = "readytensor_publications.json"

# Example: replace this with your own list of publication URLs
PROJECT_URLS = [
    "https://app.readytensor.ai/publications/kestrel-llm-powered-cybersecurity-research-assistant-using-rag-S9iUf5RHEHKf",
    "https://app.readytensor.ai/publications/capital-compass-an-agentic-ai-application-for-investment-research-T1vToFFZgKMr",
]

def load_existing():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def save_data(all_data):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

def scrape_page(url):
    print(f"🌍 Scraping {url}")
    if url.endswith("/create"):
        return {
            "url": url,
            "status": "failed",
            "error": "Skipped create page",
            "scraped_at": datetime.utcnow().isoformat()
        }

    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # 1. Look for ld+json block
        ld_json_tag = soup.find("script", {"type": "application/ld+json"})
        ld_json = None
        if ld_json_tag:
            try:
                ld_json = json.loads(ld_json_tag.string.strip())
            except:
                pass

        record = {
            "id": None,
            "url": url,
            "username": None,
            "user_url": None,
            "license": None,
            "title": None,
            "description": None,
            "datePublished": None,
            "image": None,
            "raw": ld_json,
            "status": "ok",
            "error": "",
            "scraped_at": datetime.utcnow().isoformat()
        }

        if ld_json:
            # Extract fields
            record["title"] = ld_json.get("headline")
            record["datePublished"] = ld_json.get("datePublished")
            record["image"] = ld_json.get("image")

            # Author (flatten if nested)
            authors = ld_json.get("author", [])
            if authors and isinstance(authors, list):
                flat_authors = []
                for a in authors:
                    if isinstance(a, list):
                        for sub in a:
                            if isinstance(sub, dict):
                                flat_authors.append(sub)
                    elif isinstance(a, dict):
                        flat_authors.append(a)

                if flat_authors:
                    record["username"] = flat_authors[0].get("name")
                    record["user_url"] = flat_authors[0].get("url")

            # ID from slug
            record["id"] = url.rstrip("/").split("/")[-1]

        # 2. Fallback: if no description in ld+json, try markdown div
        if not record["description"]:
            md_div = soup.find("div", {"class": "markdown"})
            if md_div:
                record["description"] = md_div.get_text(strip=True)

        # Ensure we have at least a title
        if not record["title"]:
            record["status"] = "failed"
            record["error"] = "No ld+json headline found"

        return record

    except Exception as e:
        return {
            "url": url,
            "status": "failed",
            "error": str(e),
            "scraped_at": datetime.utcnow().isoformat()
        }

def main():
    existing = load_existing()
    existing_urls = {r["url"] for r in existing}

    new_records = []
    for url in PROJECT_URLS:
        if url in existing_urls:
            print(f"⏭️ Skipping already scraped: {url}")
            continue
        rec = scrape_page(url)
        new_records.append(rec)

    if new_records:
        all_data = existing + new_records
        save_data(all_data)
        print(f"✅ Saved {len(new_records)} new records to {OUTPUT_FILE}")
    else:
        print("ℹ️ No new records scraped.")

if __name__ == "__main__":
    main()
