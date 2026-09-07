import asyncio
from playwright.async_api import async_playwright

async def fetch_product_cards(url: str, card_selector: str) -> list[dict]:
    """Extracts structured DOM elements directly per card with raw text fallback."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=200)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        print(f"[Browser] Navigating to {url}...")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(2)

            # Dismiss cookie banner
            try:
                cookie_btn = page.locator("button:has-text('ΑΠΟΔΟΧΗ'), button:has-text('Accept')").first
                if await cookie_btn.is_visible(timeout=1000):
                    await cookie_btn.click(force=True)
            except Exception:
                pass

            await page.mouse.wheel(0, 800)
            await asyncio.sleep(1.5)

            cards = await page.locator(card_selector).all()
            print(f"[Browser] Found {len(cards)} product cards matching '{card_selector}'")

            card_data = []
            for card in cards:
                # Direct HTML targeted extraction
                title_el = card.locator("a.product-item-link, .product_pod h3 a").first
                author_el = card.locator(".author, .product-item-author, .writer").first
                price_el = card.locator(".price-wrapper .price, .price_color").first

                title = await title_el.inner_text() if await title_el.count() > 0 else ""
                author = await author_el.inner_text() if await author_el.count() > 0 else ""
                price = await price_el.inner_text() if await price_el.count() > 0 else ""
                raw_text = " ".join((await card.inner_text()).split())

                card_data.append({
                    "dom_title": title.strip(),
                    "dom_author": author.strip(),
                    "dom_price": price.strip(),
                    "raw_text": raw_text
                })

            await browser.close()
            return card_data

        except Exception as e:
            print(f"[Browser Error] {e}")
            await browser.close()
            return []