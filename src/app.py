import os
import requests
import pandas as pd
import streamlit as st
import sqlite_vec
from sqlite_vec import serialize_float32

from database import VectorDBManager


st.set_page_config(
    page_title="MarketWatch Agent",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 MarketWatch Agent")
st.caption(
    "Multilingual semantic search with cross-lingual query expansion "
    "and relevance filtering."
)

# Create DB manager AFTER Streamlit has initialized
db = VectorDBManager()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "marketwatch.db")

def get_db_connection():
    #conn = sqlite3.connect(DB_PATH)
    conn =db._get_connection()  # Use the VectorDBManager's connection method to ensure sqlite-vec is loaded
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn

def expand_query_multilingual(query: str) -> str:
    """Uses qwen2.5:3b to expand English queries into Greek (and vice versa) for cross-lingual matching."""
    try:
        res = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen2.5:3b",
                "prompt": f"Translate and expand this search query into both English and Greek terms so it can match multilingual book titles. Return ONLY the combined search terms:\n'{query}'",
                "stream": False
            },
            timeout=5
        )
        expanded = res.json().get("response", query).strip()
        return f"{query} {expanded}"
    except Exception:
        return query
    
# --- SIDEBAR CONTROLS ---
st.sidebar.header("Search Settings")
top_k = st.sidebar.slider("Max Results Limit", min_value=1, max_value=20, value=10)
# max_dist = st.sidebar.slider(
#     "Relevance Cutoff (Max Distance)",
#     min_value=10.0,
#     max_value=25.0,
#     value=16.0,
#     step=0.1
# )
# --- TABBED UI NAVIGATION ---
tab_search, tab_debug = st.tabs(["🔍 Semantic Search", "🛠️ Database Inspector"])

with tab_search:
    query = st.text_input("Enter natural language query:", placeholder="e.g., books about war, history, or ancient civilizations")

if query:
    with st.spinner("Searching..."):

        # Use the user's query directly — no Qwen expansion
        enriched_query = query

        results = db.search_semantic(enriched_query, limit=top_k)

        st.write("Query:", enriched_query)
        st.write("RAW RESULTS:", results)

        # Temporarily don't filter by distance
        filtered_results = results

    if filtered_results:
        for r in filtered_results:
            st.write(
                f"**{r['title']}** — "
                f"distance: {r['distance_score']}"
            )
    else:
        st.warning("No results found.")
        
    # if query:
    #     with st.spinner("Translating query and searching across languages..."):
    #         # Expand the query first using your function
    #         #enriched_query = expand_query_multilingual(query)
    #         enriched_query = query

    #         results = db.search_semantic(
    #             enriched_query,
    #             limit=top_k
    #         )

    #         st.write("Enriched query:", enriched_query)
    #         st.write("RAW RESULTS:", results)

    #         st.write("Distance cutoff:", max_dist)

    #         for r in results:
    #             st.write(
    #                 r["title"],
    #                 "distance =",
    #                 r["distance_score"]
    #             )

    #         #results = [r for r in results if r["distance_score"] <= max_dist]
        
    #     if results:
    #         st.subheader(f"Found {len(results)} Relevant Matches:")
    #         for row in results:
    #             with st.container(border=True):
    #                 st.markdown(f"### {row['title']}")
    #                 c1, c2, c3, c4 = st.columns(4)
    #                 c1.metric("Author", row['author'])
    #                 c2.metric("Price", row['price'])
    #                 c3.metric("Stock Status", "In Stock" if row['in_stock'] else "Out of Stock")
    #                 c4.metric("Vector Distance", f"{row['distance_score']:.4f}")
                    
    #                 if row['url']:
    #                     st.markdown(f"[View Source Page]({row['url']})")
    #     else:
    #         st.warning("No matching products found within the relevance threshold.")

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