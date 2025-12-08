import streamlit as st
import pandas as pd
from news_manager import NewsFetcher, NewsDatabase
from modules.llm_manager import LLMManager
import time
import queue
import threading

# Page Setup

st.set_page_config(page_title="News Reader", page_icon=None, layout="wide")

# CSS to left-align buttons (specifically for news titles)
st.markdown("""
<style>
/* Force left alignment and reduce font size for buttons (Article Titles) */
div[data-testid="stMainBlockContainer"] .stButton button {
    justify-content: flex-start !important;
    text-align: left !important;
    font-size: 14px !important;
    padding-top: 0.25rem !important;
    padding-bottom: 0.25rem !important;
    line-height: 1.4 !important;
}

/* Reduce main header sizes for mobile */
h1 {
    font-size: 1.8rem !important;
}
h2 {
    font-size: 1.5rem !important;
}
</style>
""", unsafe_allow_html=True)


st.title("Text News Reader")

# Initialize Managers
llm_manager = LLMManager()
fetcher = NewsFetcher()
db = NewsDatabase()

def auto_sum_worker(news_items, model, result_queue, stop_event):
    """Background thread to summarize news"""
    
    # Check GPU availability once before loop
    gpu_info = llm_manager.get_gpu_info()
    if not gpu_info:
        return # Skip if no GPU
        
    # We use a local fetcher instance to avoid any thread sharing issues with the main fetcher,
    # though NewsFetcher seems mostly stateless except config.
    # Actually, reusing the global 'fetcher' is fine if it's thread-safe.
    # But `generate_summary` instantiates `NewsDatabase`.
    
    for item in news_items:
        if stop_event.is_set():
            break
            
        link = item['link']
        
        try:
            # Fetch text (Network I/O)
            # Use cached text from main thread? No, worker needs to fetch if missing.
            # But the 'fetcher' instance is from main module import or passed arg?
            # It's a global in this file.
            
            # Optimization: Check cache first via fetcher (which checks DB)
            # But we need text for generation if cache miss.
            # So:
            # 1. Check DB cache (cheap)
            db = NewsDatabase()
            cached_sum = db.get_summary_from_cache(link)
            if cached_sum:
                result_queue.put((link, cached_sum))
                continue
            
            # 2. Fetch Text (expensive network)
            text = fetcher.get_full_text(link)
            
            # 3. Generate (via fetcher to reuse prompt logic)
            # We pass link=None because we handle DB explicitly here to avoid re-instantiating DB? 
            # Or just use fetcher's caching?
            
            # Let's use fetcher's caching logic! 
            # But wait, if we use fetcher.generate_summary(link=link), it checks DB again (redundant but fast).
            
            summary = fetcher.generate_summary(text, model, link=link)
            
            if summary:
                result_queue.put((link, summary))
            
            time.sleep(1) # Yield
        except Exception as e:
            print(f"Auto sum error: {e}")


# Sidebar: Source Selection & Mode
with st.sidebar:
    st.header("Settings")
    mode = st.radio("View Mode", ["Live News", "Saved News"])
    
    if mode == "Live News":
        source = st.selectbox("Select Source", list(fetcher.sources.keys()))
        
        # Model Selection
        if 'available_models' not in st.session_state:
             st.session_state.available_models = llm_manager.get_models()
        
        # If models fetched successfully
        if st.session_state.available_models:
            # Determine default index
            config = llm_manager.get_config()
            default_model = config.get("default_model")
            
            default_index = 0
            if default_model in st.session_state.available_models:
                default_index = st.session_state.available_models.index(default_model)

            def on_model_change():
                llm_manager.update_config("default_model", st.session_state.selected_model)

            selected_model = st.selectbox(
                "AI Model", 
                st.session_state.available_models, 
                index=default_index,
                key="selected_model",
                on_change=on_model_change
            )
            
            # Auto Summary Toggle
            # Load initial state from config if not in session yet
            if 'auto_summary_enabled' not in st.session_state:
                st.session_state.auto_summary_enabled = config.get("auto_summary_enabled", False)

            def on_summary_toggle():
                 llm_manager.update_config("auto_summary_enabled", st.session_state.auto_summary_enabled)

            # Just display the toggle here
            st.toggle("Auto Summary", key="auto_summary_enabled", on_change=on_summary_toggle)
            
            # Queue Initialization
            if 'result_queue' not in st.session_state:
                st.session_state.result_queue = queue.Queue()
            
        else:
            st.caption("AI Models: Not Connected")
            st.session_state.selected_model = None

        if st.button("Refresh Feed"):
            st.rerun()
            
    

    st.markdown("---")
    st.caption("**AI Server Status**")
    
    col_stat1, col_stat2 = st.columns([1,1])
    with col_stat1:
        if st.button("Check", key="check_ollama", use_container_width=True):
            # Refresh models list when checked
            st.session_state.available_models = llm_manager.get_models()
            success, msg = llm_manager.check_connection()
            if success:
                st.toast(f"Connected! Found {len(st.session_state.available_models)} models.")
            else:
                st.toast(msg)
    
    with col_stat2:
        st.write("") # Spacer

    # GPU Info (Moved up)
    gpu_info = llm_manager.get_gpu_info()
    if gpu_info:
        count = len(gpu_info)
        names = set(gpu_info) # Unique names
        name_str = ", ".join(names)
        st.caption(f"**GPU:** {count} Cards Detected ({name_str})")
    else:
        st.caption("**GPU:** Not Detected (SSH Failed)")

    # Data Usage Stats (Moved down)
    st.markdown("---")
    st.caption("**Server Data Usage (Today)**")
    
    from modules.metrics_manager import DataUsageTracker
    tracker = DataUsageTracker()
    stats = tracker.get_stats()
    
    def format_bytes(size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:,.0f} {unit}" if unit == 'B' else f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"

    rx_str = format_bytes(stats['rx_bytes'])
    tx_str = format_bytes(stats['tx_bytes'])
    total_str = format_bytes(stats['total_bytes'])

    st.markdown(f"""
    <div style="font_size: 0.8rem; color: #666;">
        <div style="display: flex; justify-content: space-between;">
            <span>Rx: <b>{rx_str}</b></span>
            <span>Tx: <b>{tx_str}</b></span>
        </div>
        <div style="margin-top: 4px; font-weight: bold;">
            Total: {total_str}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
# Main Content
if mode == "Live News":
    st.header(f"Live Feed: {source}")
    
    # Initialize session state for news if not present or source changed
    if 'current_source' not in st.session_state or st.session_state.current_source != source:
        st.session_state.news_items = fetcher.fetch_feeds(source)
        st.session_state.current_source = source
        # Source changed, stop old thread if any
        if 'stop_event' in st.session_state:
            st.session_state.stop_event.set()
            
        # Prefetch summaries from DB
        st.session_state.summaries = {}
        for item in st.session_state.news_items:
            cached = db.get_summary_from_cache(item['link'])
            if cached:
                st.session_state.summaries[item['link']] = cached

    if not st.session_state.news_items:
        st.info("No news items found or unable to fetch.")
    
    # Thread Management (Now that we have items)
    auto_sum_on = st.session_state.get('auto_summary_enabled', False)
    selected_model = st.session_state.get('selected_model')
    
    if auto_sum_on and selected_model:
        # Check if we need to start a thread
        # 1. Thread not alive
        # 2. OR Thread alive but probably done? (Hard to know, but if stop_event is set we should restart)
        
        need_start = False
        if 'auto_thread' not in st.session_state:
            need_start = True
        elif not st.session_state.auto_thread.is_alive():
            need_start = True
        elif st.session_state.get('stop_event') and st.session_state.stop_event.is_set():
             # Previous one was stopped, needed new one
             need_start = True
        
        if need_start:
             if 'summaries' not in st.session_state: st.session_state.summaries = {}
             
             items_to_process = [
                 item for item in st.session_state.news_items 
                 if item['link'] not in st.session_state.summaries
             ]
             
             if items_to_process:
                 stop_event = threading.Event()
                 t = threading.Thread(
                     target=auto_sum_worker, 
                     args=(items_to_process, selected_model, st.session_state.result_queue, stop_event),
                     daemon=True
                 )
                 t.start()
                 st.session_state.auto_thread = t
                 st.session_state.stop_event = stop_event
    else:
        # If disabled, ensure stopped
        if 'stop_event' in st.session_state:
            st.session_state.stop_event.set()
    
    
    # Initialize dictionary to store fetched texts if not exists
    if 'fetched_texts' not in st.session_state:
        st.session_state.fetched_texts = {}

    # Display News List
    @st.fragment(run_every=2 if st.session_state.get('auto_summary_enabled') else None)
    def render_news_list():
        if 'summaries' not in st.session_state:
            st.session_state.summaries = {}

        # Poll Queue
        if 'result_queue' in st.session_state:
            try:
                while True:
                    link, summary = st.session_state.result_queue.get_nowait()
                    st.session_state.summaries[link] = summary
            except queue.Empty:
                pass
            
        for i, item in enumerate(st.session_state.news_items):
            # Create a container for each item
            with st.container():
                # Use columns to mock a header
                # Title as a button
                if st.button(f"{item['title']}", key=f"title_btn_{i}", use_container_width=True):
                    # Toggle selection
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

                # Show Auto Summary if available (Indented)
                if item['link'] in st.session_state.summaries:
                    c_spacer, c_summary = st.columns([0.015, 0.985])
                    with c_summary:
                        st.info(st.session_state.summaries[item['link']])

                # Date snippet (Below)
                st.caption(f"Published: {item['published']}")
                
                # If this item is expanded
                if st.session_state.get('expanded_id') == i:
                    st.markdown("---")
                    
                    full_text = st.session_state.fetched_texts.get(item['link'], "")
                    
                    # Controls Row
                    col_regen, col_save_area = st.columns([1, 3])
                    
                    with col_regen:
                         if st.button("Regen", key=f"sum_{i}"):
                            with st.spinner(f"Asking Local LLM ({st.session_state.get('selected_model', 'Default')})..."):
                                model_to_use = st.session_state.get('selected_model')
                                if model_to_use:
                                    summary = fetcher.generate_summary(full_text, model=model_to_use, link=item['link'], force_refresh=True)
                                    st.session_state.summaries[item['link']] = summary
                                    st.rerun()
                                else:
                                    st.error("No AI Model selected/available.")

                    with col_save_area:
                        c_comment, c_btn = st.columns([4, 1])
                        with c_comment:
                            user_comment = st.text_input("Note", key=f"comment_{i}", placeholder="Comment...", label_visibility="collapsed")
                        with c_btn:
                            if st.button("Save", key=f"save_{i}"):
                                article_data = {
                                    'title': item['title'],
                                    'link': item['link'],
                                    'published': item['published'],
                                    'source': item['source'],
                                    'summary': st.session_state.summaries.get(item['link'], ""),
                                    'content': full_text,
                                    'comment': user_comment
                                }
                                if db.save_article(article_data):
                                    st.toast("Saved to DB!")
                                else:
                                    st.error("Save failed.")
    
                    # Show Content
                    st.write(full_text)
                    
                    # Original Link at Bottom
                    st.markdown(f"[Original Link]({item['link']})")
                    
                    st.markdown("---")
                    st.empty() # Spacer
    
    render_news_list()

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
                 
                 # Show Comment
                 if item.get('comment'):
                     st.warning(f"**Note:** {item['comment']}")
                 
                 # Directly show content for saved items
                 st.markdown("**Summary:**")
                 st.info(item['summary'])
                 
                 st.markdown("**Full Text:**")
                 st.text(item['content']) # Use text or markdown
                 
                 st.markdown(f"[Original Link]({item['link']})")
