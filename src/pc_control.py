import streamlit as st
import subprocess
import time
import json
import os
import socket
import struct
import ipaddress

STATE_FILE = "pc_state.json"

class PCControl:
    def __init__(self, name, host, mac, ssh_user="ross"):
        self.name = name
        self.host = host
        self.mac = mac
        self.ssh_user = ssh_user
        
        # 세션 상태 키 (최적화용 - 페이지 리로드시 초기화됨)
        self.key_last_check = f"{self.name}_last_check"
        self.key_last_check = f"{self.name}_last_check"
        self.key_last_status = f"{self.name}_last_status"
        self.key_confirm_off = f"{self.name}_confirm_off"

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
        
        /* 세 번째 컬럼(Windows Boot 버튼)의 Primary 버튼을 파란색으로 변경 */
        div[data-testid="column"]:nth-of-type(3) button[kind="primary"],
        div[data-testid="stColumn"]:nth-of-type(3) button[kind="primary"] {
            background-color: #0078D7 !important;
            border-color: #0078D7 !important;
            color: white !important;
        }
        div[data-testid="column"]:nth-of-type(3) button[kind="primary"]:hover,
        div[data-testid="stColumn"]:nth-of-type(3) button[kind="primary"]:hover {
            background-color: #0063B1 !important;
            border-color: #005A9E !important;
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
        # 1. Ping Check (Don't return immediately if fail, just record result)
        is_pingable = False
        try:
            subprocess.run(['ping', '-c', '1', '-W', '1', self.host], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            is_pingable = True
        except subprocess.CalledProcessError:
            is_pingable = False

        # 2. SSH Banner Check (Robust: Separate Connect and Recv)
        ssh_banner = ""
        is_ssh_open = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(3.0) # Increased to 3.0s for stability
                
                # Connect first
                result = sock.connect_ex((self.host, 22))
                if result == 0:
                    is_ssh_open = True
                    # Try reading banner, but don't fail connection if it fails
                    try:
                        ssh_banner = sock.recv(1024).decode('utf-8', errors='ignore')
                    except:
                        # Connected but read failed (timeout or empty)
                        # Still count as SSH Open
                        pass
        except Exception:
            is_ssh_open = False

        # 3. Determine Status based on combined results
        if is_ssh_open:
            if "Ubuntu" in ssh_banner:
                return "UBUNTU"
            elif "Windows" in ssh_banner:
                return "WINDOWS"
            else:
                # Banner exists but neither Ubuntu nor Windows explicitly
                # Heuristic: If name contains "linux", assume Ubuntu
                if "linux" in self.name.lower():
                     return "UBUNTU"
                
                # User mentioned Windows SSH exists, so maybe it's just standard OpenSSH
                # default to WINDOWS for non-Ubuntu SSH in this dual-boot context
                return "WINDOWS"
        
        if is_pingable:
             # SSH Closed but Ping works -> Assume Windows (no SSH or blocked)
             return "WINDOWS"

        return "OFFLINE"

    def send_magic_packet(self):
        """Wake-on-LAN의 순수 파이썬 구현 (개선 버전)"""
        try:
            # MAC 주소에서 구분자 제거
            mac_address = self.mac.replace(":", "").replace("-", "").upper()
            if len(mac_address) != 12:
                raise ValueError(f"Invalid MAC address format: {self.mac} (길이가 12가 아님)")
            
            # MAC 주소가 유효한 16진수인지 확인
            try:
                int(mac_address, 16)
            except ValueError:
                raise ValueError(f"Invalid MAC address format: {self.mac} (16진수가 아님)")

            # 매직 패킷 생성: FF * 6 + MAC * 16
            data = bytes.fromhex("FF" * 6 + mac_address * 16)
            
            # 서브넷 브로드캐스트 주소 계산
            try:
                # 호스트가 Hostname일 경우 IP로 변환
                try:
                    target_ip = socket.gethostbyname(self.host)
                except socket.gaierror:
                    target_ip = self.host # 실패시 그대로 시도

                # 호스트 IP를 기반으로 서브넷 브로드캐스트 주소 계산
                # 일반적인 서브넷 마스크 가정 (24비트 = /24)
                # 실제 네트워크에 맞게 조정 필요할 수 있음
                network = ipaddress.IPv4Network(f"{target_ip}/24", strict=False)
                broadcast_addr = str(network.broadcast_address)
            except (ValueError, ipaddress.AddressValueError):
                # IP 주소 파싱 실패 시 기본 브로드캐스트 사용
                broadcast_addr = "255.255.255.255"
            
            # 브로드캐스트로 패킷 전송 (여러 번 전송하여 안정성 향상)
            success_count = 0
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
                # 패킷을 여러 번 전송 (Ports 7 & 9)
                ports = [7, 9]
                for port in ports:
                    # 전송 횟수를 5회로 증가
                    for i in range(5):
                        try:
                            # 서브넷 브로드캐스트로 전송
                            sock.sendto(data, (broadcast_addr, port))
                            # 전역 브로드캐스트도 전송
                            sock.sendto(data, ("255.255.255.255", port))
                            success_count += 1
                            time.sleep(0.05)
                        except socket.error:
                            pass
            
            # CLI 도구 사용 (wakeonlan 패키지가 설치되어 있으므로 활용)
            try:
                # -i 옵션으로 브로드캐스트 주소 지정 가능
                cmd = ['wakeonlan', '-i', broadcast_addr, self.mac]
                subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # 전역 브로드캐스트로도 한 번 더
                cmd_global = ['wakeonlan', '-i', '255.255.255.255', self.mac]
                subprocess.run(cmd_global, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                success_count += 1
            except FileNotFoundError:
                pass 

            if success_count == 0:
                raise Exception(f"WOL 패킷 전송 실패: 모든 전송 시도가 실패했습니다.")
            
            # 디버그용 정보 반환 (또는 로깅)
            return broadcast_addr
        except Exception as e:
            raise Exception(f"WOL 패킷 전송 실패: {str(e)}")

    @st.fragment(run_every=5) # Auto refresh every 5 seconds
    def render_ui(self):
        # 1. 영구 상태 로드 (파일)
        state = self._get_state()
        current_action = state.get("action")
        start_time = state.get("start_time")

        # 2. 세션 상태 초기화
        if self.key_last_check not in st.session_state:
            st.session_state[self.key_last_check] = 0
            st.session_state[self.key_last_status] = "OFFLINE" # Default to string status
        if self.key_confirm_off not in st.session_state:
            st.session_state[self.key_confirm_off] = False


        now = time.time()
        
        # 3. Automatic Status Check (Throttled, but more frequent during actions)
        last_check_time = st.session_state.get(self.key_last_check, 0)
        
        # Check interval: 
        # - 15s if idle
        # - 5s if in an active action (booting/shutdown)
        # - 30s if failed previously (to avoid constant lag)
        check_interval = 15
        if current_action is not None:
            check_interval = 5
        
        if (now - last_check_time > check_interval):
            status = self.check_status()
            st.session_state[self.key_last_status] = status
            st.session_state[self.key_last_check] = now
        else:
            status = st.session_state[self.key_last_status]
        
        # Header (No Refresh Button needed, auto-refresh is active)
        st.subheader(f"{self.name} Power Status")

        # Display Status with Icons
        if status == "UBUNTU":
            st.success("ONLINE (Ubuntu 🐧) ✅")
            is_online = True
        elif status == "WINDOWS":
            st.info("ONLINE (Windows 🪟) ✅")
            is_online = True
        elif status == "UNKNOWN":
            st.warning("ONLINE (Unknown OS ❓) ✅")
            is_online = True
        else:
            st.error("OFFLINE 🔴")
            is_online = False
        
        # 4. Status Indicator (Small debug info)
        if current_action:
            st.caption(f"Action in progress: {current_action.upper()}... (Current Status: {status})")


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
        elif current_action == "booting_win":
            elapsed = now - start_time
            # Windows 부팅은 확인이 어려우므로 60초 후 상태 초기화
            if elapsed > 60:
                self._update_state(None, 0)
                st.rerun()



        # 제어 버튼
        col1, col2, col3 = st.columns(3)
        
        # 버튼 비활성화 여부
        is_disabled = (current_action is not None)

        with col1:
            # 켜져있으면 기본(secondary), 꺼져있으면 강조(primary)
            btn_type = "secondary" if is_online else "primary"
            if st.button(f'⚡ Power ON (WOL)', key=f"{self.name}_on", type=btn_type, use_container_width=True, disabled=is_disabled):
                try:
                    # MAC 주소 검증 메시지 (디버깅용)
                    st.info(f"📡 WOL 패킷 전송 중... (MAC: {self.mac}, Host: {self.host})")
                    self.send_magic_packet()
                    st.toast(f"WOL 패킷 전송 완료! {self.name} 부팅 대기 중...", icon="🚀")
                    # 부팅 모드 진입
                    self._update_state("booting", time.time())
                    # 즉시 상태 체크를 위해 마지막 체크 시간 초기화
                    st.session_state[self.key_last_check] = 0 
                    st.rerun()
                except Exception as e:
                    error_detail = str(e)
                    st.error(f"❌ WOL 패킷 전송 실패: {error_detail}")
                    st.info(f"💡 확인사항:\n- MAC 주소가 올바른지 확인: {self.mac}\n- 대상 PC의 Wake-on-LAN이 활성화되어 있는지 확인\n- 같은 네트워크에 연결되어 있는지 확인")
                    # 에러 발생 시에도 상태는 업데이트하지 않음

        with col2:
            # 켜져있으면 강조(primary), 꺼져있으면 기본(secondary)
            btn_type = "primary" if is_online else "secondary"
            
            # 확인 상태가 아니면 "Power OFF" 버튼 표시
            if not st.session_state.get(self.key_confirm_off, False):
                if st.button(f'🛑 Power OFF (SSH)', key=f"{self.name}_off", type=btn_type, use_container_width=True, disabled=is_disabled):
                    if is_online:
                        st.session_state[self.key_confirm_off] = True
                        st.rerun()
                    else:
                        st.warning("Device is already offline.")
            else:
                # 확인 상태이면 "Yes/No" 버튼 표시
                st.markdown("⚠️ **Shutdown?**")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Yes", key=f"{self.name}_yes_off", type="primary", use_container_width=True):
                         try:
                            # SSH 종료 (Shutdown)
                            # SSH 키 파일 경로 확인 (여러 경로 시도)
                            ssh_key_paths = [
                                os.path.expanduser('~/.ssh/id_ed25519'),
                                os.path.expanduser('~/.ssh/id_rsa'),
                                os.path.expanduser('~/.ssh/id_ecdsa'),
                            ]
                            
                            ssh_key = None
                            for key_path in ssh_key_paths:
                                if os.path.exists(key_path) and os.access(key_path, os.R_OK):
                                    ssh_key = key_path
                                    break
                            
                            
                            cmd = [
                                'ssh', 
                                '-o', 'StrictHostKeyChecking=no', 
                                '-o', 'UserKnownHostsFile=/dev/null',
                                '-o', 'ConnectTimeout=5',
                            ]
                            
                            # Windows일 경우 -t 옵션 제외 (필요 없음), Ubuntu일 경우 sudo를 위해 -t (tty) 필요
                            if status == "UBUNTU":
                                cmd.append('-t')

                            # SSH 키가 있으면 추가
                            if ssh_key:
                                cmd.extend(['-i', ssh_key])
                            
                            if status == "WINDOWS":
                                # Windows Shutdown Command
                                cmd.extend([
                                    '-l', self.ssh_user,
                                    self.host, 
                                    'shutdown', '/s', '/t', '0'
                                ])
                                
                                subprocess.run(cmd, check=True, capture_output=True, timeout=10)
                                st.toast("Windows Shutdown Command Sent!")
                            else:
                                # Linux Shutdown Command
                                cmd.extend([
                                    '-l', self.ssh_user, 
                                    self.host, 
                                    'sudo', 'shutdown', '-h', 'now'
                                ])
                                
                                # -t 옵션으로 pseudo-terminal 할당하여 sudo 비밀번호 입력 가능하게 함
                                # 단, 원격 서버의 sudoers에 NOPASSWD 설정이 필요함
                                subprocess.run(cmd, check=True, capture_output=True, timeout=10)
                                st.toast("Linux Shutdown Command Sent!")

                            # 공통 종료 처리
                            # 종료 모드 진입
                            self._update_state("shutdown", time.time())
                            # 즉시 상태 체크를 위해 마지막 체크 시간 초기화
                            st.session_state[self.key_last_check] = 0
                            # 확인 상태 해제
                            st.session_state[self.key_confirm_off] = False
                            st.rerun()

                         except subprocess.CalledProcessError as e:
                            error_msg = e.stderr.decode().strip() if e.stderr else str(e)
                            st.error(f"Failed: {error_msg}")
                         except Exception as e:
                            st.error(f"Failed: {e}")

                with c2:
                    if st.button("❌ No", key=f"{self.name}_no_off", use_container_width=True):
                        st.session_state[self.key_confirm_off] = False
                        st.rerun()

                        # 켜져있으면 강조(primary), 꺼져있으면 기본(secondary)
            # Windows 상태라도 재부팅 용도로 Win Boot 버튼 활성화
            is_win_boot_disabled = is_disabled 
            
            btn_type = "primary" if is_online else "secondary"
            if st.button(f'🪟 Win Boot (SSH)', key=f"{self.name}_win_boot", type=btn_type, use_container_width=True, disabled=is_win_boot_disabled):
                if is_online:
                    try:
                        # SSH공통 로직 (키 찾기 및 명령어 실행)
                        ssh_key_paths = [
                            os.path.expanduser('~/.ssh/id_ed25519'),
                            os.path.expanduser('~/.ssh/id_rsa'),
                            os.path.expanduser('~/.ssh/id_ecdsa'),
                        ]
                        
                        ssh_key = None
                        for key_path in ssh_key_paths:
                            if os.path.exists(key_path) and os.access(key_path, os.R_OK):
                                ssh_key = key_path
                                break
                        
                        cmd = [
                            'ssh', 
                            '-o', 'StrictHostKeyChecking=no', 
                            '-o', 'UserKnownHostsFile=/dev/null',
                            '-o', 'ConnectTimeout=5',
                        ]
                        
                         # Windows일 경우 -t 옵션 제외, Ubuntu일 경우 -tt (tty force)
                        if status == "UBUNTU":
                            cmd.append('-tt')

                        if ssh_key:
                            cmd.extend(['-i', ssh_key])
                        
                        cmd.extend(['-l', self.ssh_user, self.host])

                        if status == "WINDOWS":
                            # Windows Reboot Command
                            cmd.extend(['shutdown', '/r', '/t', '0'])
                            subprocess.run(cmd, check=True, capture_output=True, timeout=10)
                            st.toast("Windows Reboot Command Sent!")
                            
                            self._update_state("booting_win", time.time())
                            st.session_state[self.key_last_check] = 0
                            st.rerun()

                        else: 
                            # Ubuntu Logic (Grub Reboot)
                            # 1. Grub Reboot 설정
                            cmd_grub = cmd + ['sudo', 'grub-reboot', '4']
                        
                        # Process execution with pipe handling for cleaner error capture
                        try:
                            result = subprocess.run(cmd_grub, check=True, capture_output=True, timeout=10)
                            st.toast("GRUB entry set for Windows!")
                        except subprocess.CalledProcessError as e:
                            error_msg = e.stderr.decode().strip() if e.stderr else str(e)
                            if "password is required" in error_msg or "sudo: a terminal is required" in error_msg:
                                st.error("❌ sudo 권한 설정 필요")
                                st.code(f"echo '{self.ssh_user} ALL=(ALL) NOPASSWD: /usr/sbin/grub-reboot, /usr/sbin/reboot' | sudo tee /etc/sudoers.d/pc_control", language="bash")
                                st.info("대상 PC에서 위 명령어를 한 번 실행해주세요.")
                                return # 더 이상 진행하지 않음
                            else:
                                raise e # 다른 에러는 상위로 전파

                        # 2. Reboot 실행
                        # Reboot 시 연결이 끊겨서 에러가 날 수 있으므로 예외 처리 완화
                        cmd_reboot = cmd + ['sudo', 'reboot']
                        try:
                            subprocess.run(cmd_reboot, check=True, capture_output=True, timeout=10)
                        except subprocess.CalledProcessError:
                            # reboot은 성공했지만 연결이 끊어진 경우 무시 (또는 실제 에러일 수도 있음)
                            pass
                        except subprocess.TimeoutExpired:
                            # 타임아웃은 명령이 실행되었음을 의미할 수 있음
                            pass

                        st.toast("Reboot Command Sent!")
                        # 종료/재부팅 모드 진입
                        self._update_state("booting_win", time.time())
                        st.session_state[self.key_last_check] = 0
                        st.rerun()

                    except subprocess.CalledProcessError as e:
                        error_msg = e.stderr.decode().strip() if e.stderr else str(e)
                        st.error(f"Failed: {error_msg}")
                    except Exception as e:
                        st.error(f"Failed: {e}")
                else:
                    st.warning("Device is offline.")


