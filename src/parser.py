import asyncio
import json
import httpx
from json_repair import repair_json
from config import ProductItem

LLM_SEMAPHORE = asyncio.Semaphore(1)

async def parse_single_card_async(card_data: dict, site_name: str, client: httpx.AsyncClient) -> ProductItem:
    """Parses card using DOM fields first, falling back to strict LLM instructions."""
    
    dom_title = card_data.get("dom_title", "")
    dom_author = card_data.get("dom_author", "")
    dom_price = card_data.get("dom_price", "")
    raw_text = card_data.get("raw_text", "")

    # If DOM direct extraction captured the title cleanly, use it directly!
    if dom_title and dom_price:
        author_final = dom_author if dom_author else ("N/A" if "BooksToScrape" in site_name else "Unknown Author")
        return ProductItem(
            title=dom_title,
            author=author_final,
            price=dom_price,
            in_stock=True
        )

    # Fallback to LLM with STRICT non-translation rules
    prompt = f"""Extract product details from this snippet:
"{raw_text}"

STRICT GUARDRAILS:
1. DO NOT translate Greek titles to English. Keep titles verbatim in Greek.
2. DO NOT transliterate Greek characters into Latin script.
3. Keep exact original spelling and alphabet.
4. If site is BooksToScrape, set "author" to "N/A".

Return ONLY JSON:
{{
  "title": "Verbatim Exact Title",
  "author": "Verbatim Author or N/A",
  "price": "Price string with currency",
  "in_stock": true
}}"""

    payload = {
        "model": "qwen2.5:3b",
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "num_predict": 128,
            "num_thread": 4
        }
    }

    async with LLM_SEMAPHORE:
        try:
            res = await client.post("http://localhost:11434/api/generate", json=payload, timeout=60.0)
            res.raise_for_status()
            parsed = repair_json(res.json().get("response", ""), return_objects=True)

            if isinstance(parsed, dict):
                return ProductItem(
                    title=str(parsed.get("title", "Unknown Title")).strip(),
                    author=str(parsed.get("author", "N/A")).strip(),
                    price=str(parsed.get("price", "N/A")).strip(),
                    in_stock=bool(parsed.get("in_stock", True))
                )
        except Exception as e:
            print(f"[LLM Error] Fallback parsing failed: {e}")
            
    return None

async def parse_all_cards(cards: list[dict], site_name: str) -> list[ProductItem]:
    async with httpx.AsyncClient() as client:
        tasks = [parse_single_card_async(card, site_name, client) for card in cards]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r and r.title != "Unknown Title"]