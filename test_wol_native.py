from pc_control import PCControl
import sys

# Mock configuration
name = "TestPC"
host = "100.65.53.9"
mac = "2C:F0:5D:2C:02:36"
ssh_user = "ross"

print(f"Testing Native WOL for {mac}...")
try:
    pc = PCControl(name, host, mac, ssh_user)
    # We only test the send_magic_packet method
    success = pc.send_magic_packet()
    if success:
        print("Success: Magic packet sent.")
    else:
        print("Failed: Method returned False.")
except Exception as e:
    print(f"Failed with exception: {e}")
    sys.exit(1)
