import os
import yaml
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

# Resolve absolute path to targets.yaml in project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "targets.yaml")

def load_targets() -> list[dict]:
    """Loads scraping targets dynamically from the external YAML file."""
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Configuration file not found at: {CONFIG_PATH}")
    
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []

# Expose TARGET_SITES dynamically for main.py
TARGET_SITES = load_targets()