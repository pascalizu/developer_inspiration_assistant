import json
import os
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

OUTPUT_FILE = "readytensor_publications.json"

def save_data(records):
    """Append new records to JSON file."""
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []
    else:
        existing = []

    existing.extend(records)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

def extract_nextdata(page, url):
    """Try extracting JSON from __NEXT_DATA__ or self.__next_f.push streams."""

    # 1. Old Next.js: __NEXT_DATA__
    handle = page.query_selector("script#__NEXT_DATA__")
    if handle:
        raw_json = handle.inner_text()
        return {"source": "__NEXT_DATA__", "parsed": json.loads(raw_json)}

    # 2. New Next.js: wait for streamed <script> tags
    try:
        page.wait_for_selector("script", timeout=20000)  # wait up to 20s
    except:
        return None

    scripts = page.query_selector_all("script")

    # Debug dump
    with open("debug_scripts.txt", "w", encoding="utf-8") as f:
        for i, s in enumerate(scripts):
            try:
                content = s.inner_text()
                f.write(f"--- Script {i} ---\n")
                f.write(content[:2000])  # only first 2k chars to keep file light
                f.write("\n\n")
            except:
                f.write(f"--- Script {i} unreadable ---\n\n")

    collected = []
    for s in scripts:
        content = s.inner_text()
        if "self.__next_f.push" in content:
            matches = re.findall(r"self\.__next_f\.push\((.*?)\);", content)
            for m in matches:
                try:
                    parsed = json.loads(m)
                    collected.append(parsed)
                except Exception as e:
                    collected.append({"raw": m, "error": str(e)})

    if collected:
        return {"source": "__NEXT_STREAM__", "parsed": collected}

    return None

def scrape_page(page, url):
    print(f"🌍 Scraping {url}")

    if "/publications/create" in url:
        return {
            "url": url,
            "status": "skipped",
            "error": "Not a real project page",
            "scraped_at": datetime.utcnow().isoformat()
        }

    try:
        page.goto(url, timeout=60000)

        data = extract_nextdata(page, url)
        if not data:
            return {
                "url": url,
                "status": "failed",
                "error": "No __NEXT_DATA__ or __next_f.push found",
                "scraped_at": datetime.utcnow().isoformat()
            }

        return {
            "url": url,
            "status": "ok",
            "data": data,
            "scraped_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return {
            "url": url,
            "status": "failed",
            "error": str(e),
            "scraped_at": datetime.utcnow().isoformat()
        }

def main():
    PROJECT_URLS = [
        "https://app.readytensor.ai/publications/kestrel-llm-powered-cybersecurity-research-assistant-using-rag-S9iUf5RHEHKf",
        "https://app.readytensor.ai/publications/capital-compass-an-agentic-ai-application-for-investment-research-T1vToFFZgKMr",
    ]

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for url in PROJECT_URLS:
            results.append(scrape_page(page, url))

        browser.close()

    save_data(results)
    print(f"✅ Saved {len(results)} records to {OUTPUT_FILE}")
    print("📂 Check debug_scripts.txt to inspect raw <script> contents.")

if __name__ == "__main__":
    main()
