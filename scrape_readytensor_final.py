import asyncio
import json
import os
import re
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

OUTPUT_ALL = "readytensor_publications.json"
OUTPUT_AWARDS = "readytensor_awards.json"

# Expanded award-related keywords
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
    "winner",
    "award",
    "challenge",
    "hackathon"
]

def matches_award(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(keyword in lower for keyword in AWARD_KEYWORDS)

def normalize_award_phrase(phrase: str) -> str:
    """Normalize award phrases to clean award names."""
    if not phrase:
        return None
    phrase = phrase.strip()
    phrase = re.sub(r"^(winner of|award(ed)?|recipient of)\s*", "", phrase, flags=re.IGNORECASE)
    phrase = re.sub(r"\s+", " ", phrase)
    return phrase.strip()

def extract_awards(description: str) -> list:
    """Extract normalized award phrases from description."""
    awards = []
    if not description:
        return awards
    matches = re.findall(
        r"(winner of\s+[^\n.,;]+|award(ed)?\s+[^\n.,;]+|recipient of\s+[^\n.,;]+)",
        description,
        flags=re.IGNORECASE
    )
    for match in matches:
        phrase = match[0] if isinstance(match, tuple) else match
        normalized = normalize_award_phrase(phrase)
        if normalized and normalized not in awards:
            awards.append(normalized)
    return awards

def wipe_outputs():
    """Remove old JSON files before each run."""
    for f in [OUTPUT_ALL, OUTPUT_AWARDS]:
        if os.path.exists(f):
            os.remove(f)

def save_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def extract_project_data(page, url):
    """Extract structured project data from a ReadyTensor project page."""
    try:
        project_id = url.rstrip("/").split("/")[-1]

        # Username
        username = None
        try:
            username = await page.locator("a[href*='/users/']").first.text_content()
        except Exception:
            pass

        # License
        license_text = None
        try:
            license_text = await page.locator("text=License").first.text_content()
        except Exception:
            pass

        # Title
        title = None
        try:
            title = await page.locator("h1").first.text_content()
        except Exception:
            pass

        # Description
        description = None
        selectors = ["div.markdown", "div.prose", "article", "main"]
        for sel in selectors:
            try:
                if await page.locator(sel).count() > 0:
                    text = await page.locator(sel).inner_text()
                    if text and len(text.strip()) > 50:
                        description = text.strip()
                        break
            except Exception:
                continue

        # Fallbacks
        if not description:
            try:
                paragraphs = await page.locator("p").all_inner_texts()
                text = "\n\n".join(p.strip() for p in paragraphs if p.strip())
                if text and len(text) > 50:
                    description = text
            except Exception:
                pass

        if not description:
            try:
                description = await page.locator("meta[name='description']").get_attribute("content")
            except Exception:
                pass

        if not description:
            description = "No description found"

        awards = extract_awards(description)

        return {
            "id": project_id,
            "username": username,
            "license": license_text,
            "title": title,
            "publication_description": description,
            "awards": awards
        }

    except Exception as e:
        return {
            "id": url.split("/")[-1],
            "username": None,
            "license": None,
            "title": None,
            "publication_description": f"Error extracting: {e}",
            "awards": []
        }

async def scrape_all():
    wipe_outputs()
    all_records = []
    award_records = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("🌍 Navigating to publications index...")
        await page.goto("https://app.readytensor.ai/publications", wait_until="domcontentloaded", timeout=120000)

        # Pagination loop
        urls = set()
        page_num = 1
        MAX_PAGES = 100

        while page_num <= MAX_PAGES:
            print(f"📄 Collecting page {page_num}...", flush=True)

            try:
                await page.wait_for_selector("a[href^='/publications/']", timeout=8000)
            except PlaywrightTimeoutError:
                print("⚠️ No project links found on this page, breaking.", flush=True)
                break

            links = await page.locator("a[href^='/publications/']").all()
            new_urls = set()
            for link in links:
                href = await link.get_attribute("href")
                if href and href.startswith("/publications/") and href != "/publications/create":
                    new_urls.add("https://app.readytensor.ai" + href)

            print(f"→ Found {len(new_urls)} links on page {page_num}", flush=True)

            before_size = len(urls)
            urls |= new_urls
            after_size = len(urls)

            if after_size == before_size:
                print("✅ No new unique URLs found, stopping pagination.", flush=True)
                break

            # Find next button
            next_btn = None
            next_selectors = [
                "[aria-label='Next']",
                "a:has-text('Next')",
                "button:has-text('Next')",
                "a:has-text('›')",
                "button:has-text('›')"
            ]
            for sel in next_selectors:
                try:
                    if await page.locator(sel).count() > 0:
                        btn = page.locator(sel).first
                        if await btn.is_enabled() and await btn.is_visible():
                            next_btn = btn
                            break
                except Exception:
                    continue

            if not next_btn:
                print("✅ No Next button visible, finishing.", flush=True)
                break

            print("→ Clicking Next...", flush=True)
            await next_btn.click()
            await asyncio.sleep(1.5)
            page_num += 1

        urls = sorted(urls)
        print(f"🔗 Found {len(urls)} unique project URLs across {page_num} pages", flush=True)

        # Scrape project details
        for url in urls:
            print(f"➡️ Scraping {url}")
            retries = 3
            data = None
            for attempt in range(1, retries + 1):
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    data = await extract_project_data(page, url)
                    break
                except Exception as e:
                    print(f"⚠️ Attempt {attempt}/{retries} failed for {url}: {e}")
                    if attempt == retries:
                        data = {
                            "id": url.split("/")[-1],
                            "username": None,
                            "license": None,
                            "title": None,
                            "publication_description": f"Failed after {retries} retries",
                            "awards": []
                        }
            if data:
                all_records.append(data)
                if matches_award(json.dumps(data).lower()):
                    award_records.append(data)

        await browser.close()

    save_json(all_records, OUTPUT_ALL)
    save_json(award_records, OUTPUT_AWARDS)

    print(f"💾 Saved {len(all_records)} total projects to {OUTPUT_ALL}")
    print(f"🏆 Saved {len(award_records)} award-tagged projects to {OUTPUT_AWARDS}")

if __name__ == "__main__":
    asyncio.run(scrape_all())
