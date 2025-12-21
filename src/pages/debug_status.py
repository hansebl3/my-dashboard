import streamlit as st
import subprocess
import socket
import json
import os
import time
import sys

# Check if running in Streamlit
try:
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    IS_STREAMLIT = get_script_run_ctx() is not None
except:
    IS_STREAMLIT = False

# Fallback check if the above fails (e.g. older versions or different context)
if not IS_STREAMLIT:
    # If "streamlit" is in the command, assume Streamlit
    IS_STREAMLIT = "streamlit" in sys.argv[0]

def log(msg, type="info"):
    if IS_STREAMLIT:
        if type == "success": st.success(msg)
        elif type == "error": st.error(msg)
        elif type == "warning": st.warning(msg)
        elif type == "code": st.code(msg)
        elif type == "markdown": st.markdown(msg)
        elif type == "divider": st.divider()
        elif type == "expander": return st.expander(msg)
        else: st.info(msg)
    else:
        # CLI Output
        prefix = "ℹ️ "
        if type == "success": prefix = "✅ "
        elif type == "error": prefix = "❌ "
        elif type == "warning": prefix = "⚠️ "
        print(f"{prefix}{msg}")
        
    return None

if IS_STREAMLIT:
    st.set_page_config(page_title="Status Debugger", page_icon="🐞")
    st.title("🐞 PC Status Debugger")

# Load Config - robust search
possible_paths = [
    "config.json", 
    "../config.json", 
    "../../config.json",
    os.path.join(os.path.dirname(__file__), "../../config.json")
]

CONFIG_FILE = None
for path in possible_paths:
    if os.path.exists(path):
        CONFIG_FILE = path
        break

devices = []
if CONFIG_FILE:
    try:
        with open(CONFIG_FILE, "r") as f:
            config_data = json.load(f)
            if isinstance(config_data, list):
                devices = config_data
            else:
                devices = config_data.get("devices", [])
        log(f"Loaded config from: {CONFIG_FILE}", type="success")
    except Exception as e:
        log(f"Error loading config: {e}", type="error")
else:
    log("Config file not found in common locations.", type="error")

def verbose_check(name, host):
    if IS_STREAMLIT:
        st.markdown(f"### Testing: **{name}** ({host})")
    else:
        print(f"\n--- Testing: {name} ({host}) ---")
    
    # 1. PING Check
    is_pingable = False
    try:
        # Run ping
        result = subprocess.run(['ping', '-c', '1', '-W', '1', host], capture_output=True, text=True)
        if result.returncode == 0:
            log(f"Ping Success ({host})", type="success")
            is_pingable = True
        else:
            log(f"Ping Failed ({host})", type="error")
            is_pingable = False
            if IS_STREAMLIT:
                with st.expander("Ping Error Output"):
                    st.code(result.stderr or result.stdout)
            else:
                print(f"  > Output: {result.stderr or result.stdout}")
    except Exception as e:
        log(f"Ping Execution Error: {e}", type="error")

    # 2. SSH Port Check
    is_ssh_open = False
    ssh_banner = ""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.0)
            start_time = time.time()
            result = sock.connect_ex((host, 22))
            end_time = time.time()
            
            if result == 0:
                is_ssh_open = True
                latency = (end_time - start_time) * 1000
                log(f"Port 22 Open (Latency: {latency:.1f}ms)", type="success")
                
                # Banner logic
                try:
                    banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
                    ssh_banner = banner
                    log(f"SSH Banner: {banner}", type="info")
                except:
                    log("Connected but could not read banner.", type="warning")
            else:
                log(f"Port 22 Closed (Result code: {result})", type="error")
    except Exception as e:
        log(f"Socket Error: {e}", type="error")

    # 3. Logic Conclusion
    if IS_STREAMLIT: st.write("#### Diagnosis")
    else: print("  > Diagnosis:")
    
    if is_ssh_open:
        log("- SSH is Open.", type="info")
        if "Ubuntu" in ssh_banner:
            log("=> Result: UBUNTU (Banner matches 'Ubuntu')", type="success")
        elif "Windows" in ssh_banner:
            log("=> Result: WINDOWS (Banner matches 'Windows')", type="info")
        else:
            log("=> Result: WINDOWS (SSH Open, Defaulting to Windows)", type="info")
    else:
        log("- SSH is Closed.", type="info")
        if is_pingable:
             log("=> Result: WINDOWS (Ping OK, SSH Closed)", type="info")
        else:
             log("=> Result: OFFLINE (Both Ping and SSH failed)", type="error")

    if IS_STREAMLIT: st.divider()

if IS_STREAMLIT:
    if st.button("▶️ Run Diagnostics", type="primary"):
        for device in devices:
            verbose_check(device['name'], device['host'])
else:
    # Auto-run if CLI
    if not devices:
        print("No devices found in config.")
    for device in devices:
        verbose_check(device['name'], device['host'])
