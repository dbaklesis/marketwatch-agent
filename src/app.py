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
st.caption("Search scraped products using semantic vector search with relevance filtering.")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "marketwatch.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn

def get_local_embedding(text: str) -> list[float]:
    try:
        res = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "all-minilm", "prompt": text}, # Change to "nomic-embed-text" if using nomic
            timeout=10
        )
        res.raise_for_status()
        return res.json()["embedding"]
    except Exception as e:
        st.error(f"Failed to generate query embedding: {e}")
        return []

def search_semantic(query: str, limit: int = 5, max_distance: float = 1.0):
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
    
    # Filter out results that exceed the maximum distance threshold (lower distance = higher relevance)
    filtered_results = [row for row in results if row[6] <= max_distance]
    return filtered_results

# --- SIDEBAR CONTROLS ---
st.sidebar.header("Search Settings")
top_k = st.sidebar.slider("Max Results Limit", min_value=1, max_value=20, value=10)
max_dist = st.sidebar.slider("Relevance Cutoff (Max Distance)", min_value=0.1, max_value=2.0, value=1.0, step=0.05, 
                             help="Lower values mean stricter matching. Irrelevant results above this score are dropped.")

# --- TABBED UI NAVIGATION ---
tab_search, tab_debug = st.tabs(["🔍 Semantic Search", "🛠️ Database Inspector"])

with tab_search:
    query = st.text_input("Enter natural language query:", placeholder="e.g., books about history, war, or ancient civilizations")

    if query:
        with st.spinner("Searching with relevance filtering..."):
            results = search_semantic(query, limit=top_k, max_distance=max_dist)
        
        if results:
            st.subheader(f"Found {len(results)} Relevant Matches:")
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
            st.warning("No sufficiently related products found matching your criteria within the distance threshold. Try lowering the strictness in the sidebar or broadening your query.")

with tab_debug:
    st.header("Database Debug Inspector")
    if os.path.exists(DB_PATH):
        conn = get_db_connection()
        p_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        v_count = conn.execute("SELECT COUNT(*) FROM vec_products").fetchone()[0]
        
        col1, col2 = st.columns(2)
        col1.metric("Products Table Rows", p_count)
        col2.metric("Indexed Vectors", v_count)
        
        st.divider()
        df = pd.read_sql_query("SELECT id, title, author, price, in_stock, url FROM products", conn)
        st.dataframe(df, use_container_width=True)
        conn.close()
    else:
        st.error(f"Database file not found at: `{DB_PATH}`")