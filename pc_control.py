import streamlit as st
import subprocess
import time
import json
import os

STATE_FILE = "pc_state.json"

class PCControl:
    def __init__(self, name, host, mac, ssh_user="ross"):
        self.name = name
        self.host = host
        self.mac = mac
        self.ssh_user = ssh_user
        
        # 세션 상태 키 (최적화용 - 페이지 리로드시 초기화됨)
        self.key_last_check = f"{self.name}_last_check"
        self.key_last_status = f"{self.name}_last_status"

    @staticmethod
    def load_css():
        st.markdown("""
        <style>
        /* 첫 번째 컬럼(ON 버튼)의 Primary 버튼을 녹색으로 변경 */
        div[data-testid="column"]:nth-of-type(1) button[kind="primary"],
        div[data-testid="stColumn"]:nth-of-type(1) button[kind="primary"] {
            background-color: #28a745 !important;
            border-color: #28a745 !important;
            color: white !important;
        }
        div[data-testid="column"]:nth-of-type(1) button[kind="primary"]:hover,
        div[data-testid="stColumn"]:nth-of-type(1) button[kind="primary"]:hover {
            background-color: #218838 !important;
            border-color: #1e7e34 !important;
            color: white !important;
        }

        /* 두 번째 컬럼(OFF 버튼)의 Primary 버튼을 빨간색으로 변경 */
        div[data-testid="column"]:nth-of-type(2) button[kind="primary"],
        div[data-testid="stColumn"]:nth-of-type(2) button[kind="primary"] {
            background-color: #dc3545 !important;
            border-color: #dc3545 !important;
            color: white !important;
        }
        div[data-testid="column"]:nth-of-type(2) button[kind="primary"]:hover,
        div[data-testid="stColumn"]:nth-of-type(2) button[kind="primary"]:hover {
            background-color: #c82333 !important;
            border-color: #bd2130 !important;
            color: white !important;
        }
        </style>
        """, unsafe_allow_html=True)

    def _get_state(self):
        """파일에서 상태 읽기 (영구 저장)"""
        if not os.path.exists(STATE_FILE):
            return {"action": None, "start_time": 0}
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
            state = data.get(self.name, {"action": None, "start_time": 0})
            # 구버전 데이터 호환성 처리
            if "booting" in state:
                return {"action": "booting" if state["booting"] else None, "start_time": state.get("boot_start_time", 0)}
            return state
        except:
            return {"action": None, "start_time": 0}

    def _update_state(self, action, start_time):
        """파일에 상태 저장"""
        data = {}
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
            except:
                pass
        
        data[self.name] = {
            "action": action,
            "start_time": start_time
        }
        
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)

    def check_status(self):
        try:
            # Ping 1회, 타임아웃 1초
            subprocess.run(['ping', '-c', '1', '-W', '1', self.host], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            return False

    @st.fragment(run_every=2)
    def render_ui(self):
        # 1. 영구 상태 로드 (파일)
        state = self._get_state()
        current_action = state.get("action")
        start_time = state.get("start_time")

        # 2. 세션 상태 초기화 (최적화용)
        if self.key_last_check not in st.session_state:
            st.session_state[self.key_last_check] = 0
            st.session_state[self.key_last_status] = False

        # 3. 상태 체크 주기 설정 (액션중: 2초, 평소: 5초)
        check_interval = 2 if current_action else 5
        
        now = time.time()

        # 4. 상태 체크 수행 (주기 도달 시)
        if (now - st.session_state[self.key_last_check] >= check_interval):
            is_online = self.check_status()
            st.session_state[self.key_last_status] = is_online
            st.session_state[self.key_last_check] = now
        else:
            # 캐시된 상태 사용
            is_online = st.session_state[self.key_last_status]

        # 5. 액션 로직 처리
        if current_action == "booting":
            elapsed = now - start_time
            # 1. 켜졌으면 해제
            if is_online:
                self._update_state(None, 0)
                st.rerun()
            # 2. 120초 타임아웃
            elif elapsed > 120:
                self._update_state(None, 0)
                st.toast(f"{self.name}: Booting timed out.", icon="⚠️")
                st.rerun()
        elif current_action == "shutdown":
            elapsed = now - start_time
            # 1. 10초 타임아웃 (무조건 10초 대기)
            if elapsed > 10:
                self._update_state(None, 0)
                st.rerun()

        # 6. 상태 표시 UI
        st.subheader(f"{self.name} Power Status")
        
        if current_action == "booting":
            elapsed = int(now - start_time)
            remaining = 120 - elapsed
            st.info(f"🚀 Booting... Please wait. ({remaining}s)")
            st.progress(min(elapsed / 120, 1.0))
        elif current_action == "shutdown":
            elapsed = int(now - start_time)
            remaining = 10 - elapsed
            st.warning(f"💤 Shutting down... Please wait. ({remaining}s)")
            st.progress(min(elapsed / 10, 1.0))
        elif is_online:
            st.success("ONLINE ✅")
        else:
            st.error("OFFLINE 🔴")

        # 제어 버튼
        col1, col2 = st.columns(2)
        
        # 버튼 비활성화 여부
        is_disabled = (current_action is not None)

        with col1:
            # 켜져있으면 기본(secondary), 꺼져있으면 강조(primary)
            btn_type = "secondary" if is_online else "primary"
            if st.button(f'⚡ Power ON (WOL)', key=f"{self.name}_on", type=btn_type, use_container_width=True, disabled=is_disabled):
                try:
                    subprocess.run(['wakeonlan', self.mac], check=True, capture_output=True)
                    st.toast("WOL Packet Sent! Waiting for boot...", icon="🚀")
                    # 부팅 모드 진입
                    self._update_state("booting", time.time())
                    # 즉시 상태 체크를 위해 마지막 체크 시간 초기화
                    st.session_state[self.key_last_check] = 0 
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

        with col2:
            # 켜져있으면 강조(primary), 꺼져있으면 기본(secondary)
            btn_type = "primary" if is_online else "secondary"
            if st.button(f'🛑 Power OFF (SSH)', key=f"{self.name}_off", type=btn_type, use_container_width=True, disabled=is_disabled):
                if is_online:
                    try:
                        # SSH Shutdown
                        cmd = [
                            'ssh', 
                            '-o', 'StrictHostKeyChecking=no', 
                            '-o', 'UserKnownHostsFile=/dev/null',
                            '-o', 'ConnectTimeout=5',
                            '-l', self.ssh_user, 
                            self.host, 
                            'sudo', 'shutdown', '-h', 'now'
                        ]
                        subprocess.run(cmd, check=True, capture_output=True)
                        st.toast("Shutdown Command Sent!")
                        # 종료 모드 진입
                        self._update_state("shutdown", time.time())
                        # 즉시 상태 체크를 위해 마지막 체크 시간 초기화
                        st.session_state[self.key_last_check] = 0
                        st.rerun()
                    except subprocess.CalledProcessError as e:
                        error_msg = e.stderr.decode().strip() if e.stderr else str(e)
                        st.error(f"Failed: {error_msg}")
                    except Exception as e:
                        st.error(f"Failed: {e}")
                else:
                    st.warning("Device is already offline.")

        # 상태 리셋 버튼 (작게)
        if current_action:
            if st.button("🔄 Reset Status", key=f"{self.name}_reset", help="Stop waiting and enable buttons"):
                self._update_state(None, 0)
                st.rerun()
