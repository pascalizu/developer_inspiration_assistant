import asyncio
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# Expanded award-related keywords
AWARD_KEYWORDS = [
    "winner of",
    "awarded",
    "award",
    "prize",
    "trophy",
    "recognition",
    "innovation challenge",
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
    "excellence",
    "outstanding",
    "distinguished",
]

OUTPUT_JSON = "readytensor_awards.json"

def matches_award(record, full_html=""):
    """Check if a record mentions an award in description, tags, or full HTML text"""
    text_parts = [
        record.get("description") or "",
        " ".join(record.get("tags", [])),
        full_html,
    ]
    combined = " ".join(text_parts).lower()
    return any(kw in combined for kw in AWARD_KEYWORDS)

async def scrape_project(page, url):
    """Scrape a single ReadyTensor project page"""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=120000)
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Title
        title_el = soup.find("h1")
        title = title_el.get_text(strip=True) if title_el else None

        # Description
        desc_el = soup.find("div", class_="markdown")
        description = desc_el.get_text(" ", strip=True) if desc_el else None

        # Tags
        tags = [t.get_text(strip=True) for t in soup.select("._f7")]

        # Author
        author_el = soup.select_one("div._h5[title]")
        author = author_el["title"] if author_el and "title" in author_el.attrs else None

        # Date & reads
        date_el = soup.find("time")
        date_published = date_el.get_text(strip=True) if date_el else None

        reads_el = soup.find("span", string=lambda s: s and "read" in s.lower())
        reads = reads_el.get_text(strip=True) if reads_el else None

        # Build record
        record = {
            "id": url.rstrip("/").split("/")[-1],
            "url": url,
            "title": title,
            "description": description,
            "tags": tags,
            "author": author,
            "date": date_published,
            "reads": reads,
            "status": "ok",
            "error": "",
            "scraped_at": datetime.utcnow().isoformat(),
        }

        # Award detection
        record["award"] = matches_award(record, html)

        return record

    except Exception as e:
        return {
            "id": url.rstrip("/").split("/")[-1],
            "url": url,
            "status": "failed",
            "error": str(e),
            "scraped_at": datetime.utcnow().isoformat(),
        }

async def scrape_readytensor():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("🌍 Navigating to publications page...")
        try:
            await page.goto("https://app.readytensor.ai/publications", wait_until="domcontentloaded", timeout=120000)
        except Exception as e:
            print(f"⚠️ First attempt failed: {e}, retrying...")
            await page.goto("https://app.readytensor.ai/publications", wait_until="domcontentloaded", timeout=120000)

        # Infinite scroll
        last_height = 0
        for _ in range(20):  # adjust number of scrolls if needed
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Collect project URLs
        cards = await page.query_selector_all("a[href*='/publications/']")
        urls = []
        for card in cards:
            href = await card.get_attribute("href")
            if href and "/publications/" in href and not href.endswith("/create"):
                urls.append("https://app.readytensor.ai" + href)

        urls = list(set(urls))
        print(f"✅ Found {len(urls)} project URLs")

        results = []
        for url in urls:
            print(f"🔎 Scraping {url}")
            record = await scrape_project(page, url)
            if record.get("award"):
                results.append(record)

        # Append to JSON
        if results:
            if os.path.exists(OUTPUT_JSON):
                with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            else:
                existing = []

            combined = existing + results
            with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                json.dump(combined, f, indent=2, ensure_ascii=False)

            print(f"🏆 Saved {len(results)} award-tagged projects to {OUTPUT_JSON}")
        else:
            print("ℹ️ No award-tagged projects found.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_readytensor())
