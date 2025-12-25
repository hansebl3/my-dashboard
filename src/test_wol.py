import json
import os
import sys
import socket
import ipaddress
import time

# Ensure we can import pc_control
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from pc_control import PCControl
except ImportError:
    print("Error: Could not import PCControl. Run this from the src/ directory or ensure pc_control.py is accessible.")
    sys.exit(1)

def test_wol():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    
    if not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}")
        return

    try:
        with open(config_path, "r") as f:
            config_data = json.load(f)
            if isinstance(config_data, list):
                devices = config_data
            else:
                devices = config_data.get("devices", [])
    except Exception as e:
        print(f"Error reading config: {e}")
        return

    print(f"Found {len(devices)} devices in config.")
    
    target_device = None
    for device in devices:
        if "2080" in device["name"] or "linux" in device["name"].lower():
            target_device = device
            break
    
    if not target_device:
        print("Could not find a device matching '2080' or 'linux'. listing all:")
        for i, d in enumerate(devices):
            print(f"{i+1}. {d['name']} ({d['host']} / {d['mac']})")
        
        try:
            idx = int(input("Select device number: ")) - 1
            target_device = devices[idx]
        except:
            print("Invalid selection.")
            return

    print(f"\n--- Testing WOL for {target_device['name']} ---")
    print(f"Host: {target_device['host']}")
    print(f"MAC:  {target_device['mac']}")

    pc = PCControl(
        name=target_device["name"],
        host=target_device["host"],
        mac=target_device["mac"],
        ssh_user=target_device.get("ssh_user", "ross")
    )

    # Manual Debugging of Magic Packet Logic
    print("\n[Debug Info]")
    try:
        target_ip = socket.gethostbyname(pc.host)
        print(f"Resolved IP: {target_ip}")
        
        try:
            network = ipaddress.IPv4Network(f"{target_ip}/24", strict=False)
            broadcast_addr = str(network.broadcast_address)
            print(f"Calculated Broadcast Address: {broadcast_addr}")
        except Exception as e:
            print(f"Error calculating broadcast address: {e}")
            broadcast_addr = "255.255.255.255"
            print(f"Fallback Broadcast Address: {broadcast_addr}")

    except socket.gaierror:
        print(f"Error: Could not resolve hostname {pc.host}")
    
    print("\nSending Magic Packet...")
    try:
        pc.send_magic_packet()
        print("Magic Packet Sent Successfully! (Check if PC turns on)")
    except Exception as e:
        print(f"Failed to send packet: {e}")

if __name__ == "__main__":
    test_wol()
