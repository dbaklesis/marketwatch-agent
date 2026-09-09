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
        "base_url": "https://books.toscrape.com/catalogue/category/books_1/page-{}.html",
        "card_selector": "article.product_pod",
        "total_pages": 3
    },
    {
        "name": "Psichogios - Istoria",
        # Magento appends query parameters for pagination
        "base_url": "https://www.psichogios.gr/el/adults/biblia/non-fiction/istoria.html?p={}",
        "card_selector": "li.product-item",
        "total_pages": 3
    }
]