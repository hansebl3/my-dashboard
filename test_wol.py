import subprocess
import sys

mac = "2C:F0:5D:2C:02:36"
print(f"Testing WOL for {mac}...")
try:
    result = subprocess.run(['wakeonlan', mac], check=True, capture_output=True)
    print("Return Code:", result.returncode)
    print("Stdout:", result.stdout.decode())
    print("Stderr:", result.stderr.decode())
except subprocess.CalledProcessError as e:
    print("Failed with CalledProcessError")
    print("Return Code:", e.returncode)
    print("Stderr:", e.stderr.decode())
except Exception as e:
    print(f"Failed with {type(e).__name__}: {e}")
