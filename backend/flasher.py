"""Flasher module for flashing Qualcomm devices using QDL."""

import subprocess
import os
import re
from pathlib import Path
from typing import Optional, Callable, Dict


def validate_firmware_path(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    
    firmware_dir = Path(path)
    has_elf = any(f.suffix == '.elf' for f in firmware_dir.iterdir())
    has_xml = any(f.suffix == '.xml' for f in firmware_dir.iterdir())
    
    return has_elf and has_xml


def flash_device(
    serial: str,
    firmware_path: str,
    storage_type: str = "emmc",
    output_callback: Optional[Callable[[str], None]] = None,
    logs_dir: Optional[str] = "backend/logs",
) -> int:
    if not serial:
        raise ValueError("Serial number is required")
    
    # Ensure the path exists
    if not os.path.isdir(firmware_path):
        raise FileNotFoundError(f"Firmware path not found: {firmware_path}")
    
    # Validate firmware files exist
    if not validate_firmware_path(firmware_path):
        raise ValueError(f"Firmware path does not contain required .elf and .xml files: {firmware_path}")
    
    # prefer absolute qdl path if available (snap may place it in /snap/bin)
    import shutil
    qdl_exec = shutil.which("qdl") or "qdl"

    cmd = [
        "sudo", qdl_exec,
        "-S", serial,  # device serial
        "--storage", storage_type,
        "prog_firehose_ddr.elf",
        "rawprogram_unsparse0.xml",
        "patch0.xml"
    ]
    
    # Run the command from inside the firmware directory (cd into firmware_path).
    # Stream stdout/stderr and call output_callback for each line if provided.
    prev_cwd = os.getcwd()
    try:
        os.chdir(firmware_path)
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        # Stream lines to callback if provided
        if output_callback and proc.stdout is not None:
            for line in proc.stdout:
                if line is None:
                    break
                output_callback(line.rstrip('\r\n'))

        proc.wait()
        return proc.returncode
    finally:
        os.chdir(prev_cwd)


# Compatibility wrapper for old code
def flash_qdl(serial: str, path: str) -> None:
    """
    Legacy flash function for backward compatibility.
    
    Args:
        serial: Serial number of the device
        path: Directory containing QDL firmware files
    """
    result = flash_device(serial, path)
    if result != 0:
        raise subprocess.CalledProcessError(result, f"qdl flash {serial}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python flasher.py <serial> <firmware_path>")
        sys.exit(1)
    
    serial = sys.argv[1]
    firmware_path = sys.argv[2]
    
    print(f"Flashing device {serial} with firmware from {firmware_path}...")
    
    try:
        returncode = flash_device(
            serial, 
            firmware_path,
            output_callback=lambda line: print(f"  {line}")
        )
        
        if returncode == 0:
            print("✓ Flash completed successfully!")
        else:
            print(f"✗ Flash failed with exit code {returncode}")
            sys.exit(returncode)
            
    except Exception as e:
        print(f"✗ Flash error: {e}")
        sys.exit(1)
