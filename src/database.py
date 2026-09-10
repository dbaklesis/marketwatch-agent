import os
import sqlite3
import sqlite_vec
from sqlite_vec import serialize_float32
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "marketwatch.db")

class VectorDBManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Establishes connection and loads the sqlite-vec extension."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return conn

    def _init_db(self):
        """Creates standard metadata table and vector virtual table (768 dimensions for nomic-embed-text)."""
        with self._get_connection() as conn:
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
            
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_products USING vec0(
                    product_id INTEGER PRIMARY KEY,
                    embedding float[768]
                )
            """)

    def _get_embedding(self, text: str) -> list[float]:
        import requests
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text-v2-moe", "prompt": text}
        )
        response.raise_for_status()
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

                cursor = conn.execute("SELECT id FROM products WHERE title = ?", (title,))
                existing_row = cursor.fetchone()

                if existing_row:
                    product_id = existing_row[0]
                    conn.execute(
                        "UPDATE products SET author = ?, price = ?, in_stock = ?, url = ? WHERE id = ?",
                        (author, price, in_stock, site_url, product_id)
                    )
                    updated_count += 1
                else:
                    # Insert product and capture its generated id
                    cursor = conn.execute(
                        "INSERT INTO products (title, price, author, in_stock, url) VALUES (?, ?, ?, ?, ?)",
                        (title, price, author, in_stock, site_url)
                    )
                    product_id = cursor.lastrowid

                    # Insert into vec_products mapping product_id directly
                    # Insert into vec_products mapping product_id directly
                    document_text = f"Title: {title}\nAuthor: {author}"
                    embedding = self._get_embedding(
                        f"search_document: {document_text}"
                    )

                    conn.execute(
                        "INSERT INTO vec_products(product_id, embedding) VALUES (?, ?)",
                        (product_id, serialize_float32(embedding))
                    )
                    inserted_count += 1

            print(f"[Database] Finished processing: {inserted_count} new vector indexed, {updated_count} existing updated.")
            
    def search_semantic(self, query: str, limit: int = 3) -> list[dict]:
        """Performs natural language vector search using KNN vector distance."""
        # Fix: Prepend the required query prefix for nomic-embed-text
        prefixed_query = f"search_query: {query}"
        query_vector = self._get_embedding(prefixed_query)

        with self._get_connection() as conn:
            cursor = conn.execute("""
                WITH knn_matches AS (
                    SELECT 
                        product_id,
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
                JOIN products p ON p.id = m.product_id
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