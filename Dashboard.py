import streamlit as st
from pc_control import PCControl
import json
import os

# 페이지 설정
st.set_page_config(page_title="Ross Dashboard", layout="centered")

st.title("🖥️ Ross Dashboard!!")

# CSS 스타일 로드
PCControl.load_css()

# 설정 파일 로드
CONFIG_FILE = "config.json"
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config_data = json.load(f)
        # 리스트인 경우(구버전)와 딕셔너리인 경우(신버전) 모두 처리
        if isinstance(config_data, list):
            devices = config_data
        else:
            devices = config_data.get("devices", [])
else:
    st.error(f"Configuration file '{CONFIG_FILE}' not found.")
    devices = []

# PC 인스턴스 생성 및 UI 렌더링
for device in devices:
    pc = PCControl(
        name=device["name"], 
        host=device["host"], 
        mac=device["mac"], 
        ssh_user=device["ssh_user"]
    )
    pc.render_ui()
    st.markdown("---") # 구분선 추가
