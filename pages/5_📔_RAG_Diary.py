import streamlit as st

st.set_page_config(page_title="RAG Diary", layout="centered")

# CSS for font size (Mobile optimization)
st.markdown("""
<style>
h1 { font-size: 1.8rem !important; }
h2 { font-size: 1.5rem !important; }
</style>
""", unsafe_allow_html=True)

st.title("📔 RAG Diary")

st.markdown("""
Your personal AI-enhanced diary. Write your daily logs and let AI extract insights.

### 🚀 [Open RAG Diary (ross-server:8510)](http://ross-server:8510)

**Features:**
- 📝 AI-Assisted Writing
- 🧠 Automatic Metadata Extraction
- 🔍 Full-Text Search & Archival
- 🛡️ Deduplicated Vector Storage
""")

st.info("Click the link above to open RAG Diary in a new window.")
