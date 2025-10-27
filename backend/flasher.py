"""Flasher module for flashing Qualcomm devices using QDL."""

import subprocess
import os
from pathlib import Path
from typing import Optional, Callable


def validate_firmware_path(path: str) -> bool:
    """
    Validate that a firmware path contains required files.
    
    Args:
        path: Directory path to validate
        
    Returns:
        bool: True if path contains .elf and .xml files
    """
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
    output_callback: Optional[Callable[[str], None]] = None
) -> int:
    """
    Flash a Qualcomm device via QDL using its serial number.
    
    Args:
        serial: Serial number of the device
        firmware_path: Directory containing QDL firmware files
        storage_type: Storage type (emmc or ufs), default is emmc
        output_callback: Optional callback function to receive output lines
        
    Returns:
        int: Return code from the QDL process (0 = success)
        
    Raises:
        ValueError: If serial number is empty
        FileNotFoundError: If firmware path doesn't exist
    """
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
        "-d",  # debug output
        "-S", serial,  # device serial
        "--storage", storage_type,
        "prog_firehose_ddr.elf",
        "rawprogram_unsparse0.xml",
        "patch0.xml"
    ]
    
    # Run the command from inside the firmware directory (cd into firmware_path)
    if output_callback:
        # Stream output to callback
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
            , cwd=firmware_path
        )
        
        for line in process.stdout:
            line = line.strip()
            if line:
                output_callback(line)
        
        process.wait()
        return process.returncode
    else:
        # Run without streaming
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=firmware_path)
        return result.returncode


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
