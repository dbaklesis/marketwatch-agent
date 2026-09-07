from pydantic import BaseModel, Field
from typing import List, Optional

class ProductItem(BaseModel):
    title: str = Field(description="Full name of the product")
    price: str = Field(description="Current price string including currency symbol")
    in_stock: bool = Field(description="True if in stock, False if out of stock or sold out")
    author: str = Field(description="Author of the product if applicable, e.g. for books")
    rating: Optional[str] = Field(None, description="Customer rating if available, e.g. 4.5/5")

class ExtractionResult(BaseModel):
    products: List[ProductItem]

# Target URLs to monitor
TARGET_SITES = [
    {
        "name": "BooksToScrape",
        "url": "https://books.toscrape.com/catalogue/category/books_1/page-2.html",
        "card_selector": "article.product_pod"  # Individual book container
    },
    {
        "name": "Psichogios - Istoria",
        "url": "https://www.psichogios.gr/el/adults/biblia/non-fiction/istoria.html",
        "card_selector": "li.product-item"       # Individual Magento product card
    }
]