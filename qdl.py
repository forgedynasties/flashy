import subprocess

def flash_qdl(serial: str):
    """
    Flash a Qualcomm device via QDL using its serial number.

    Args:
        serial (str): Serial number of the device
    """
    if not serial:
        raise ValueError("Serial number is required")

    cmd = [
        "sudo", "qdl",
        "-d",             # debug info
        "-S", serial,     # device serial
        "--storage", "emmc",
        "prog_firehose_ddr.elf",
        "rawprogram_unsparse0.xml",
        "patch0.xml"
    ]

    subprocess.run(cmd, check=True)
