import streamlit as st

st.set_page_config(page_title="News Reader", layout="centered")

# CSS for font size (Mobile optimization)
st.markdown("""
<style>
h1 { font-size: 1.8rem !important; }
h2 { font-size: 1.5rem !important; }
</style>
""", unsafe_allow_html=True)

st.title("📰 News Reader")

st.markdown("""
This module is running as a separate application for stability and performance.

### 🚀 [Open News Reader (ross-server:8503)](http://ross-server:8503)

**Features:**
- 📰 Live News Feed from multiple sources
- 🤖 AI Summarization (Local/Remote LLM)
- 💾 Save & Archive Articles
""")

st.info("Click the link above to open the news reader in a new window.")

