import os
import json
import sqlite3
import requests
import pandas as pd
import streamlit as st
import sqlite_vec
from sqlite_vec import serialize_float32

# Set page layout and title
st.set_page_config(page_title="MarketWatch Agent", page_icon="🔍", layout="wide")

st.title("🔍 MarketWatch Agent")
st.caption("Search scraped products using semantic vector search or inspect local database records.")

# Build absolute path to data/marketwatch.db to align with database.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "marketwatch.db")

def get_db_connection():
    """Establishes connection, loads sqlite-vec extension, and creates missing tables if needed."""
    conn = sqlite3.connect(DB_PATH)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    
    # Auto-initialize schema
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
            embedding float[384]
        )
    """)
    return conn

# Helper to generate embeddings via local Ollama instance
def get_local_embedding(text: str) -> list[float]:
    try:
        res = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "all-minilm", "prompt": text},
            timeout=10
        )
        res.raise_for_status()
        return res.json()["embedding"]
    except Exception as e:
        st.error(f"Failed to reach local Ollama embedding service: {e}")
        return []

# Helper to execute sqlite-vec KNN search
def search_semantic(query: str, limit: int = 5):
    query_vector = get_local_embedding(query)
    if not query_vector:
        return []

    conn = get_db_connection()
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
            p.author,
            p.price,
            p.in_stock,
            p.url,
            m.distance
        FROM knn_matches m
        JOIN products p ON p.id = m.rowid
        ORDER BY m.distance ASC
    """, (serialize_float32(query_vector), limit))
    
    results = cursor.fetchall()
    conn.close()
    return results

# --- TABBED UI NAVIGATION ---
tab_search, tab_debug = st.tabs(["🔍 Semantic Search", "🛠️ Database Inspector"])

# --- TAB 1: SEMANTIC SEARCH ---
with tab_search:
    query = st.text_input("Enter natural language query:", placeholder="e.g., books about history, war, or ancient civilizations")

    col1, col2 = st.columns([1, 4])
    with col1:
        top_k = st.slider("Results limit", min_value=1, max_value=10, value=5)

    if query:
        with st.spinner("Generating embeddings & searching sqlite-vec..."):
            results = search_semantic(query, limit=top_k)
        
        if results:
            st.subheader(f"Top {len(results)} Matches:")
            for row in results:
                p_id, title, author, price, in_stock, url, distance = row
                
                with st.container(border=True):
                    st.markdown(f"### {title}")
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Author", author)
                    c2.metric("Price", price)
                    c3.metric("Stock Status", "In Stock" if in_stock else "Out of Stock")
                    c4.metric("Vector Distance", f"{distance:.4f}")
                    
                    if url:
                        st.markdown(f"[View Source Page]({url})")
        else:
            st.info("No semantic matches found. Make sure you have run 'python src/main.py' at least once to populate the database.")

# --- TAB 2: DATABASE INSPECTOR ---
with tab_debug:
    st.header("Database Debug Inspector")
    
    if os.path.exists(DB_PATH):
        conn = get_db_connection()
        
        # High-Level Metrics
        p_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        v_count = conn.execute("SELECT COUNT(*) FROM vec_products").fetchone()[0]
        
        col1, col2 = st.columns(2)
        col1.metric("Products Table Rows", p_count)
        col2.metric("Indexed Vectors", v_count)
        
        st.divider()
        
        # Interactive Table
        st.subheader("All Stored Products")
        df = pd.read_sql_query("SELECT id, title, author, price, in_stock, url FROM products", conn)
        st.dataframe(df, use_container_width=True)
        
        # JSON Exporter
        st.divider()
        st.subheader("Export JSON")
        json_dump = df.to_json(orient="records", indent=2, force_ascii=False)
        st.download_button(
            label="📥 Download Database as JSON",
            data=json_dump,
            file_name="marketwatch_database_dump.json",
            mime="application/json"
        )
        conn.close()
    else:
        st.error(f"Database file not found at: `{DB_PATH}`. Please run `python src/main.py` first.")