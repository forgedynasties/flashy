"""Device scanner for detecting Qualcomm devices."""

import subprocess
from typing import List


def get_qualcomm_serials() -> List[str]:
    """
    Returns a list of Qualcomm device serial numbers (SN) detected via lsusb.
    
    Uses sudo lsusb -v to scan for Qualcomm devices and extracts their serial numbers
    from the iProduct string descriptor.
    
    Returns:
        List[str]: List of serial numbers (e.g., ['CB4713E8', 'A1B2C3D4'])
    """
    cmd = (
        "sudo lsusb -v 2>/dev/null | "
        "awk '/Qualcomm/ {in_dev=1} "
        "in_dev && /iProduct/ {if (match($0, /SN:([A-F0-9]+)/, m)) print m[1]; in_dev=0}'"
    )
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=True
        )
        serials = result.stdout.strip().splitlines()
        return serials
    except subprocess.CalledProcessError as e:
        print(f"Error running lsusb command: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error scanning devices: {e}")
        return []


if __name__ == "__main__":
    # Test the scanner
    serials = get_qualcomm_serials()
    if serials:
        print(f"Found {len(serials)} Qualcomm device(s):")
        for serial in serials:
            print(f"  - {serial}")
    else:
        print("No Qualcomm devices found.")
