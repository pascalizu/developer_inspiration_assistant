import asyncio
import json
import os
import re
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Output files
OUTPUT_ALL = "data/readytensor_publications.json"
OUTPUT_AWARDS = "data/readytensor_awards.json"

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
    "the imagenet competition in 2012"
]

def matches_award(text: str) -> bool:
    """Check if text contains award-related keywords."""
    if not text:
        return False
    lower = text.lower()
    return any(keyword in lower for keyword in AWARD_KEYWORDS)

def normalize_award_phrase(phrase: str) -> str:
    """Normalize award phrases to clean award names."""
    if not phrase:
        return None
    phrase = phrase.strip().lower()
    phrase = re.sub(r"\s+", " ", phrase)
    phrase = re.sub(r"['`]+", "", phrase)
    phrase = re.sub(r"\b(winner of|award(ed)?|recipient of|at the|for|in|with)\b", "", phrase, flags=re.IGNORECASE).strip()
    # Filter invalid awards
    if (len(phrase) < 5 or
        re.search(r"\b(it|this|because|from|classification|usecases|trending|topics|way|team|presentation)\b", phrase) or
        re.search(r"\d+", phrase) or
        len(phrase.split()) > 5):
        return None
    # Match against AWARD_KEYWORDS
    for keyword in AWARD_KEYWORDS:
        if keyword in phrase or phrase in keyword:
            return keyword
    return None

def extract_awards(description: str, page_content: dict) -> list:
    """Extract normalized award phrases from description and other page elements."""
    awards = []
    unmatched = []

    # Extract from JSON awards (if any)
    json_awards = page_content.get("awards", [])
    for award in json_awards:
        norm_award = normalize_award_phrase(award)
        if norm_award and norm_award not in awards:
            awards.append(norm_award)
        elif award:
            unmatched.append(award)

    # Extract from description
    if description:
        patterns = [
            r"award[:\-]?\s*([A-Za-z\s\-]{5,40})(?=\s*(?:$|\n|\.|,|;))",
            r"winner of\s*([A-Za-z\s\-]{5,40})(?=\s*(?:$|\n|\.|,|;))",
            r"received\s*([A-Za-z\s\-]{5,40})(?=\s*(?:$|\n|\.|,|;))",
            r"won\s*([A-Za-z\s\-]{5,40})(?=\s*(?:$|\n|\.|,|;))",
            r"(?:best|most|top|outstanding|innovative|promising)\s+([A-Za-z\s\-]{5,40})(?=\s*(?:$|\n|\.|,|;))"
        ]
        for pattern in patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            for match in matches:
                norm_award = normalize_award_phrase(match)
                if norm_award and norm_award not in awards:
                    awards.append(norm_award)
                elif match:
                    unmatched.append(match)

    # Extract from other page elements (e.g., badges, awards section)
    for selector in ["div.awards", "span.badge", "div[class*='award']", "li[class*='award']"]:
        try:
            elements = page_content.get("elements", {}).get(selector, [])
            for text in elements:
                norm_award = normalize_award_phrase(text)
                if norm_award and norm_award not in awards:
                    awards.append(norm_award)
                elif text:
                    unmatched.append(text)
        except Exception:
            continue

    # Log unmatched for debugging
    if unmatched:
        print(f"Unmatched awards for {page_content.get('id', 'unknown')} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}: {unmatched}")

    return list(set([a for a in awards if a]))

def wipe_outputs():
    """Remove old JSON files before each run."""
    for f in [OUTPUT_ALL, OUTPUT_AWARDS]:
        if os.path.exists(f):
            os.remove(f)

def save_json(data, filename):
    """Save data to JSON file."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def extract_project_data(page, url):
    """Extract structured project data from a ReadyTensor project page."""
    try:
        project_id = url.rstrip("/").split("/")[-1]

        # Username
        username = None
        try:
            username = await page.locator("a[href*='/users/']").first.text_content(timeout=15000)
        except Exception:
            pass

        # License
        license_text = None
        try:
            license_text = await page.locator("text=License").first.text_content(timeout=15000)
        except Exception:
            pass

        # Title
        title = None
        try:
            title = await page.locator("h1").first.text_content(timeout=15000)
        except Exception:
            pass

        # Description
        description = None
        selectors = ["div.markdown", "div.prose", "article", "main"]
        for sel in selectors:
            try:
                if await page.locator(sel).count() > 0:
                    text = await page.locator(sel).inner_text(timeout=15000)
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
                description = await page.locator("meta[name='description']").get_attribute("content", timeout=15000)
            except Exception:
                pass

        if not description:
            description = "No description found"

        # Extract additional elements for awards
        elements = {}
        for selector in ["div.awards", "span.badge", "div[class*='award']", "li[class*='award']"]:
            try:
                texts = await page.locator(selector).all_inner_texts()
                elements[selector] = [t.strip() for t in texts if t.strip()]
            except Exception:
                elements[selector] = []

        page_content = {
            "id": project_id,
            "username": username,
            "license": license_text,
            "title": title,
            "publication_description": description,
            "awards": [],  # Will be filled by extract_awards
            "elements": elements
        }

        awards = extract_awards(description, page_content)

        page_content["awards"] = awards

        return page_content

    except Exception as e:
        print(f"Error extracting {url} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}: {e}")
        return {
            "id": url.split("/")[-1],
            "username": None,
            "license": None,
            "title": None,
            "publication_description": f"Error extracting: {e}",
            "awards": [],
            "elements": {}
        }

async def scrape_all():
    """Scrape all ReadyTensor publications."""
    wipe_outputs()
    all_records = []
    award_records = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()

        print(f"🌍 Navigating to publications index at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}...")
        try:
            await page.goto("https://app.readytensor.ai/publications", wait_until="domcontentloaded", timeout=60000)
        except PlaywrightTimeoutError:
            print(f"⚠️ Timeout on index page at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}, continuing with collected URLs...")

        # Pagination loop
        urls = set()
        page_num = 1
        MAX_PAGES = 10  # Expect ~120 projects, 20 per page
        no_content_count = 0
        MAX_NO_CONTENT = 2  # Stop after 2 pages with no project links

        while page_num <= MAX_PAGES:
            # Navigate to page using URL
            page_url = f"https://app.readytensor.ai/publications?page={page_num}" if page_num > 1 else "https://app.readytensor.ai/publications"
            print(f"📄 Navigating to page {page_num} ({page_url}) at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}...", flush=True)

            try:
                await page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_load_state("domcontentloaded", timeout=60000)
                await asyncio.sleep(6)  # Increased wait for dynamic content
            except Exception as e:
                print(f"⚠️ Failed to load {page_url} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}: {e}")
                no_content_count += 1
                if no_content_count >= MAX_NO_CONTENT:
                    print(f"✅ No content loaded for {MAX_NO_CONTENT} consecutive pages at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}, stopping pagination.", flush=True)
                    break
                page_num += 1
                continue

            # Check for project links
            try:
                await page.wait_for_selector("a[href*='/publications/']", timeout=30000)
                links = await page.locator("a[href*='/publications/']").all()
                new_urls = set()
                for link in links:
                    href = await link.get_attribute("href")
                    if href and href.startswith("/publications/") and href != "/publications/create" and not "page=" in href:
                        full_url = "https://app.readytensor.ai" + href
                        new_urls.add(full_url)

                print(f"→ Found {len(new_urls)} new links on page {page_num} (total unique: {len(urls) + len(new_urls)}) at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}", flush=True)
                if new_urls:
                    print(f"→ URLs on page {page_num}: {list(new_urls)[:5]}... (showing first 5)", flush=True)
                else:
                    print(f"→ No project links found on page {page_num} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}", flush=True)

                # Update URLs
                urls.update(new_urls)

                # Stop if no project links found
                if not new_urls:
                    no_content_count += 1
                    if no_content_count >= MAX_NO_CONTENT:
                        print(f"✅ No project links found for {MAX_NO_CONTENT} consecutive pages at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}, stopping pagination.", flush=True)
                        break
                else:
                    no_content_count = 0

            except PlaywrightTimeoutError:
                print(f"⚠️ No project links found on page {page_num} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}", flush=True)
                no_content_count += 1
                if no_content_count >= MAX_NO_CONTENT:
                    print(f"✅ No project links found for {MAX_NO_CONTENT} consecutive pages at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}, stopping pagination.", flush=True)
                    break

            page_num += 1

        urls = sorted(list(urls))
        print(f"🔗 Found {len(urls)} unique project URLs across {page_num - 1} pages at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}", flush=True)
        print(f"🔗 All URLs: {urls[:10]}... (showing first 10)", flush=True)

        # Scrape project details
        for url in urls:
            print(f"➡️ Scraping {url} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}", flush=True)
            retries = 3
            data = None
            for attempt in range(1, retries + 1):
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    data = await extract_project_data(page, url)
                    break
                except Exception as e:
                    print(f"⚠️ Attempt {attempt}/{retries} failed for {url} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}: {e}")
                    if attempt == retries:
                        data = {
                            "id": url.split("/")[-1],
                            "username": None,
                            "license": None,
                            "title": None,
                            "publication_description": f"Failed after {retries} retries",
                            "awards": [],
                            "elements": {}
                        }
            if data:
                all_records.append(data)
                if data["awards"] or matches_award(data["publication_description"].lower()):
                    award_records.append(data)

        await context.close()
        await browser.close()

    save_json(all_records, OUTPUT_ALL)
    save_json(award_records, OUTPUT_AWARDS)

    print(f"💾 Saved {len(all_records)} total projects to {OUTPUT_ALL} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"🏆 Saved {len(award_records)} award-tagged projects to {OUTPUT_AWARDS} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")

if __name__ == "__main__":
    asyncio.run(scrape_all())