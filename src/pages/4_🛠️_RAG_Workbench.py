import streamlit as st

st.set_page_config(page_title="RAG Workbench", layout="centered")

# CSS for font size (Mobile optimization)
st.markdown("""
<style>
h1 { font-size: 1.8rem !important; }
h2 { font-size: 1.5rem !important; }
</style>
""", unsafe_allow_html=True)

st.title("🛠️ RAG Workbench")

st.markdown("""
This tool allows you to manage Vector Databases and test RAG Chat functionality.

### 🚀 [Open RAG Workbench (ross-server:8504)](http://ross-server:8504)

**Features:**
- 📝 System Prompt Editor
- 💾 Vector DB Embedder (JSON to ChromaDB)
- 🗃️ Database Viewer & Inspector
- 💬 RAG Chat with Ollama LLMs
""")

st.info("Click the link above to open the RAG Workbench in a new window.")
