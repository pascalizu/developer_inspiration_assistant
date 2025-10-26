import asyncio
import json
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

# Output file
OUTPUT_JSON = Path("readytensor_publications.json")

# Start with some example project URLs (extend this list or scrape the catalog first)
PROJECT_URLS = [
    "https://app.readytensor.ai/publications/kestrel-llm-powered-cybersecurity-research-assistant-using-rag-S9iUf5RHEHKf",
    "https://app.readytensor.ai/publications/capital-compass-an-agentic-ai-application-for-investment-research-T1vToFFZgKMr",
]

async def scrape_project(page, url):
    """Extract __NEXT_DATA__ JSON from a single project page."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # Grab the script tag with id="__NEXT_DATA__"
        element = await page.query_selector("script#__NEXT_DATA__")
        if not element:
            return {"url": url, "status": "failed", "error": "No __NEXT_DATA__ found"}

        raw_json = await element.inner_text()
        data = json.loads(raw_json)

        # Store everything as-is to preserve full schema
        return {
            "url": url,
            "status": "ok",
            "error": "",
            "scraped_at": datetime.utcnow().isoformat(),
            "data": data,  # the full ReadyTensor schema
        }
    except Exception as e:
        return {
            "url": url,
            "status": "failed",
            "error": str(e),
            "scraped_at": datetime.utcnow().isoformat(),
        }

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        results = []
        for url in PROJECT_URLS:
            print(f"🌍 Scraping {url}")
            result = await scrape_project(page, url)
            results.append(result)

        await browser.close()

        # Append or create JSON file
        if OUTPUT_JSON.exists():
            existing = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
        else:
            existing = []

        existing.extend(results)
        OUTPUT_JSON.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"✅ Saved {len(results)} new records to {OUTPUT_JSON}")

if __name__ == "__main__":
    asyncio.run(main())
