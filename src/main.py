import asyncio
import time
from browser import fetch_product_cards
from parser import parse_all_cards
from config import TARGET_SITES
from database import VectorDBManager

async def run_pipeline():
    db = VectorDBManager()

    print(f"=== Starting MarketWatch Scrape Pipeline ({len(TARGET_SITES)} sites) ===")
    total_start_time = time.perf_counter()

    for site in TARGET_SITES:
        site_start_time = time.perf_counter()
        print(f"\n--- Processing: {site['name']} ---")
        
        # 1. Fetch card text snippets via Playwright
        cards = await fetch_product_cards(site["url"], site["card_selector"])
        print(f"[Browser] Extracted {len(cards)} cards from DOM.")
        
        # 2. Parse cards concurrently using local LLM
        products = await parse_all_cards(cards, site["name"])
        products_dict = [p.model_dump() for p in products]
        print(f"[LLM Parser] Successfully parsed {len(products_dict)} products.")
        
        # 3. Batch insert into SQLite and sqlite-vec
        if products_dict:
            db.insert_products(products_dict, site["url"])

        site_elapsed = time.perf_counter() - site_start_time
        minutes, seconds = divmod(site_elapsed, 60)
        print(f"⏱️ [{site['name']}] Execution Time: {int(minutes)}m {seconds:.2f}s")

    total_elapsed = time.perf_counter() - total_start_time
    total_min, total_sec = divmod(total_elapsed, 60)
    print(f"\n==================================================")
    print(f"🏁 Total Pipeline Execution Time: {int(total_min)}m {total_sec:.2f}s")
    print(f"==================================================")

if __name__ == "__main__":
    asyncio.run(run_pipeline())