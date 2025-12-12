
import streamlit as st

st.set_page_config(page_title="CSV Analyzer", layout="centered")

# CSS for font size (Mobile optimization)
st.markdown("""
<style>
h1 { font-size: 1.8rem !important; }
h2 { font-size: 1.5rem !important; }
</style>
""", unsafe_allow_html=True)

st.title("🔗 CSV Analyzer & Auto Validation")

st.markdown("""
This module is running as a separate application for stability and performance.

### 🚀 [Open CSV Analyzer (ross-server:8502)](http://ross-server:8502)

**Features:**
- 📊 General Data Analysis for time series data from CSV or Database
- 🤖 Auto Process Validation for CTC Lightspray project
""")

st.info("Click the link above to open the analysis tool in a new window.")
