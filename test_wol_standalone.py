import socket
import struct
import sys

# Mock configuration
mac = "2C:F0:5D:2C:02:36"

def send_magic_packet(mac):
    """Native Python implementation of Wake-on-LAN (Standalone Test)"""
    try:
        # MAC 주소에서 구분자 제거
        mac_address = mac.replace(":", "").replace("-", "")
        if len(mac_address) != 12:
            raise ValueError("Invalid MAC address format")

        # 매직 패킷 생성: FF * 6 + MAC * 16
        data = bytes.fromhex("FF" * 6 + mac_address * 16)
        
        # 브로드캐스트로 패킷 전송
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(data, ("255.255.255.255", 9))
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

print(f"Testing Native WOL for {mac}...")
if send_magic_packet(mac):
    print("Success: Magic packet sent.")
else:
    print("Failed.")
    sys.exit(1)
