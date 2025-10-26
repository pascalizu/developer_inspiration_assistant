# scrape_readytensor_clean.py
import json
import os
import re
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

OUTPUT_ALL = "readytensor_publications.json"
OUTPUT_AWARDS = "readytensor_awards.json"

AWARD_KEYWORDS = [
    "best overall project",
    "best technical implementation",
    "most innovative project",
    "most engaging presentation",
    "outstanding solution implementation",
    "most promising innovation",
    "best ai tool innovation",
    "distinguished applied solution showcase",
    "distinguished technical deep-dive",
    "distinguished social impact innovation",
    "best creative ai project",
    "ai research excellence",
    "distinguished implementation guide",
    "excellence in educational content",
    "exceptional dataset contribution",
    "winner of",
    "award",
    "challenge"
]

def load_existing(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def matches_award(text: str) -> bool:
    text = text.lower()
    return any(kw in text for kw in AWARD_KEYWORDS)

async def scrape_project(page, url):
    record = {
        "id": None,
        "username": None,
        "license": None,
        "title": None,
        "publication_description": None,
        "status": "failed",
        "error": "",
        "scraped_at": datetime.utcnow().isoformat()
    }
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=120_000)

        # Extract ld+json structured metadata
        ldjson_elements = await page.query_selector_all("script[type='application/ld+json']")
        structured = None
        for el in ldjson_elements:
            try:
                txt = await el.text_content()
                data = json.loads(txt)
                if isinstance(data, dict) and "@type" in data and data["@type"].lower() in ["newsarticle", "article"]:
                    structured = data
                    break
            except Exception:
                continue

        if structured:
            record["id"] = url.split("/")[-1]
            record["title"] = structured.get("headline")
            record["publication_description"] = structured.get("description") or None
            # Author / username
            if "author" in structured and isinstance(structured["author"], list):
                author_obj = structured["author"][0]
                if isinstance(author_obj, list) and len(author_obj) > 0:
                    record["username"] = author_obj[0].get("name")
                elif isinstance(author_obj, dict):
                    record["username"] = author_obj.get("name")
            # License
            record["license"] = structured.get("license") if "license" in structured else None

        # Fallback: scrape full description from the DOM
        if not record["publication_description"]:
            desc_el = await page.query_selector("main")
            if desc_el:
                record["publication_description"] = await desc_el.inner_text()

        record["status"] = "ok"
    except Exception as e:
        record["error"] = str(e)
    return record

async def scrape_all():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("🌍 Navigating to publications listing...")
        await page.goto("https://app.readytensor.ai/publications", wait_until="domcontentloaded", timeout=120_000)

        # Collect all project links
        cards = await page.query_selector_all("a[href*='/publications/']")
        project_urls = []
        for card in cards:
            href = await card.get_attribute("href")
            if href and "/publications/" in href and not href.endswith("/create"):
                full_url = "https://app.readytensor.ai" + href if href.startswith("/") else href
                if full_url not in project_urls:
                    project_urls.append(full_url)

        print(f"✅ Found {len(project_urls)} project URLs")

        all_data = load_existing(OUTPUT_ALL)
        awards_data = load_existing(OUTPUT_AWARDS)

        new_all = []
        new_awards = []

        for url in project_urls:
            print(f"🌍 Scraping {url}")
            record = await scrape_project(page, url)
            new_all.append(record)

            desc = (record.get("title") or "") + " " + (record.get("publication_description") or "")
            if matches_award(desc):
                new_awards.append(record)

        save_json(OUTPUT_ALL, all_data + new_all)
        save_json(OUTPUT_AWARDS, awards_data + new_awards)

        print(f"✅ Saved {len(new_all)} new records to {OUTPUT_ALL}")
        print(f"🏆 Saved {len(new_awards)} award-tagged projects to {OUTPUT_AWARDS}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_all())
