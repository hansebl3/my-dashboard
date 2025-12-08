import streamlit as st
import pandas as pd
from news_manager import NewsFetcher, NewsDatabase
import time

# Page Setup

st.set_page_config(page_title="News Reader", page_icon="📰", layout="wide")

# CSS to left-align buttons (specifically for news titles)
st.markdown("""
<style>
/* Force left alignment for buttons in the main content area */
div[data-testid="stMainBlockContainer"] .stButton button {
    justify-content: flex-start !important;
    text-align: left !important;
}
</style>
""", unsafe_allow_html=True)


st.title("📰 Text News Reader")

# Initialize Managers
fetcher = NewsFetcher()
db = NewsDatabase()

# Sidebar: Source Selection & Mode
with st.sidebar:
    st.header("Settings")
    mode = st.radio("View Mode", ["Live News", "Saved News"])
    
    if mode == "Live News":
        source = st.selectbox("Select Source", list(fetcher.sources.keys()))
        if st.button("Refresh Feed"):
            st.rerun()

    with st.expander("🔌 AI Server Status"):
        if st.button("Test Connection"):
            success, msg = fetcher.check_ollama_connection()
            if success:
                st.success(msg)
            else:
                st.error(f"Connection Failed: {msg}")

# Main Content
if mode == "Live News":
    st.header(f"Live Feed: {source}")
    
    # Initialize session state for news if not present or source changed
    if 'current_source' not in st.session_state or st.session_state.current_source != source:
        st.session_state.news_items = fetcher.fetch_feeds(source)
        st.session_state.current_source = source

    if not st.session_state.news_items:
        st.info("No news items found or unable to fetch.")
    
    
    # Initialize dictionary to store fetched texts if not exists
    if 'fetched_texts' not in st.session_state:
        st.session_state.fetched_texts = {}

    # Display News List
    for i, item in enumerate(st.session_state.news_items):
        # Create a container for each item
        with st.container():
            # Use columns to mock a header
            # Title as a button (simulates link behavior)
            if st.button(f"📄 {item['title']}", key=f"title_btn_{i}", use_container_width=True):
                # Toggle selection or set selection
                # If same item clicked, toggle off? Or just reload.
                # Let's say it sets the expanded view below.
                if st.session_state.get('expanded_id') == i:
                    st.session_state.expanded_id = None
                else:
                    st.session_state.expanded_id = i
                    # Auto-fetch text if not there
                    if item['link'] not in st.session_state.fetched_texts:
                        with st.spinner("Fetching full text..."):
                            text = fetcher.get_full_text(item['link'])
                            st.session_state.fetched_texts[item['link']] = text
                st.rerun()

            # Date snippet
            st.caption(f"Published: {item['published']}")
            
            # If this item is expanded
            if st.session_state.get('expanded_id') == i:
                st.markdown("---")
                # Controls
                col_sum, col_orig, col_save = st.columns([1, 1, 1])
                
                full_text = st.session_state.fetched_texts.get(item['link'], "")
                
                with col_sum:
                     if st.button("🤖 AI Summary (Local)", key=f"sum_{i}"):
                        with st.spinner("Asking Local LLM..."):
                            summary = fetcher.summarize_text(full_text)
                            st.info(f"**Summary:**\n\n{summary}")
                
                with col_orig:
                     st.markdown(f"[🔗 Original Link]({item['link']})")
                
                with col_save:
                    if st.button("💾 Save to DB", key=f"save_{i}"):
                        article_data = {
                            'title': item['title'],
                            'link': item['link'],
                            'published': item.get('published', ''),
                            'summary': '', # We might not have summary unless generated
                            'content': full_text,
                            'source': item.get('source', 'Unknown')
                        }
                        if db.save_article(article_data):
                            st.success("Saved!")
                        else:
                            st.error("Save failed.")

                # Show Content
                st.markdown("### Full Text")
                st.write(full_text)
                st.markdown("---")
                st.empty() # Spacer

# Saved News Mode
elif mode == "Saved News":
    st.header("Saved Articles")
    saved_items = db.get_saved_articles()
    
    if not saved_items:
        st.info("No saved articles found.")
    else:
        for item in saved_items:
             with st.expander(f"{item['title']} (Saved: {item['created_at']})"):
                 st.markdown(f"**Source:** {item['source']}")
                 # Directly show content for saved items
                 st.markdown("**Summary:**")
                 st.info(item['summary'])
                 
                 st.markdown("**Full Text:**")
                 st.text(item['content']) # Use text or markdown
                 
                 st.markdown(f"[🔗 Original Link]({item['link']})")
