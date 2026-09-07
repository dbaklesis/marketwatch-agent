import os
import sqlite3
import sqlite_vec
from sqlite_vec import serialize_float32
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

api_key = os.getenv("OPENAI_API_KEY")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data\\marketwatch.db")

class VectorDBManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.client = OpenAI(api_key=api_key)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Establishes connection and loads the sqlite-vec extension."""
        conn = sqlite3.connect(self.db_path)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return conn

    def _init_db(self):
        """Creates standard metadata table and vector virtual table (1536 dimensions)."""
        with self._get_connection() as conn:
            # 1. Standard Relational Table for Metadata
            # Standard Relational Table with UNIQUE constraint on title
            conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL UNIQUE,
                    author TEXT NOT NULL,
                    price TEXT NOT NULL,
                    in_stock BOOLEAN NOT NULL,
                    url TEXT
                )
            """)
            
            # 2. Virtual Vector Table for Semantic Search (OpenAI embedding dim = 1536)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_products USING vec0(
                    embedding float[384]
                )
            """)

    # Change dimensions in _init_db from 1536 to 384 for all-minilm 
    # vec0(embedding float[384])

    def _get_embedding(self, text: str) -> list[float]:
        import requests
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "all-minilm", "prompt": text}
        )
        return response.json()["embedding"]

    def insert_products(self, products: list[dict], site_url: str):
        """Inserts metadata into SQLite and vectors into vec_products with duplicate detection."""
        inserted_count = 0
        updated_count = 0

        with self._get_connection() as conn:
            for item in products:
                title = item["title"]
                author = item["author"]
                price = item["price"]
                in_stock = item["in_stock"]

                # 1. Check if product already exists by title
                cursor = conn.execute("SELECT id FROM products WHERE title = ?", (title,))
                existing_row = cursor.fetchone()

                if existing_row:
                    product_id = existing_row[0]
                    # Corrected UPDATE query to include author placeholder
                    conn.execute(
                        "UPDATE products SET author = ?, price = ?, in_stock = ?, url = ? WHERE id = ?",
                        (author, price, in_stock, site_url, product_id)
                    )
                    updated_count += 1
                else:
                    # 2. Insert new metadata record
                    cursor = conn.execute(
                        "INSERT INTO products (title, author, price, in_stock, url) VALUES (?, ?, ?, ?, ?)",
                        (title, author, price, in_stock, site_url)
                    )
                    product_id = cursor.lastrowid

                    # 3. Generate embedding & insert vector only for brand-new products
                    vector = self._get_embedding(title)
                    conn.execute(
                        "INSERT INTO vec_products(rowid, embedding) VALUES (?, ?)",
                        (product_id, serialize_float32(vector))
                    )
                    inserted_count += 1

            print(f"[Database] Finished processing: {inserted_count} new vector indexed, {updated_count} existing updated.")
            
    def search_semantic(self, query: str, limit: int = 3) -> list[dict]:
        """Performs natural language vector search using KNN vector distance."""
        query_vector = self._get_embedding(query)

        with self._get_connection() as conn:
            # Use CTE (WITH clause) and specify 'and k = ?' inside the match constraint
            cursor = conn.execute("""
                WITH knn_matches AS (
                    SELECT 
                        rowid,
                        distance
                    FROM vec_products
                    WHERE embedding MATCH ? AND k = ?
                )
                SELECT 
                    p.id,
                    p.title,
                    p.price,
                    p.in_stock,
                    p.url,
                    p.author,
                    m.distance
                FROM knn_matches m
                JOIN products p ON p.id = m.rowid
                ORDER BY m.distance ASC
            """, (serialize_float32(query_vector), limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "id": row[0],
                    "title": row[1],
                    "price": row[2],
                    "in_stock": bool(row[3]),
                    "url": row[4],
                    "author": row[5],
                    "distance_score": round(row[6], 5)
                })
            return results