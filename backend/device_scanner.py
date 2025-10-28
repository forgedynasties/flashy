"""Device scanner for detecting Qualcomm devices.

This module provides utilities to:
- list adb-connected devices (with transport ids and usb path from `adb devices -l`)
- enumerate USB devices from sysfs (`/sys/bus/usb/devices`) and read idVendor/idProduct/serial
- correlate adb entries to sysfs USB devices using the usb path token (e.g. "1-1" or "1-9.1")
- mark a device as being in 'adb' or (likely) 'edl'
- provide a safe helper to reboot an adb device into EDL using its transport id

Design notes / assumptions:
- We prefer reading /sys/bus/usb/devices/* to calling sudo lsusb -v. This avoids requiring sudo and
  gives the kernel USB device name ("1-1", "1-9.1") which adb also exposes as "usb:1-1".
- Correlation is done by matching the adb usb:<path> token to the sysfs device directory name.
- A device appearing in the adb list is considered in adb-mode. If a Qualcomm USB device
  (vendor 05c6) exists in sysfs but does not appear in adb list, it may be in EDL.
  This heuristic is not perfect for all vendor/product combinations but works well for common flows.
"""

import os
import subprocess
from typing import Dict, List, Optional


def _read_sysfs_file(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None
    except Exception:
        return None


def get_usb_devices_sysfs() -> Dict[str, Dict[str, Optional[str]]]:
    """Enumerate USB devices from /sys/bus/usb/devices.

    Returns a mapping keyed by the kernel USB device name (e.g. '1-1', '1-9.1')
    with values containing idVendor, idProduct, serial (if available) and product string.
    """
    usb_root = "/sys/bus/usb/devices"
    devices: Dict[str, Dict[str, Optional[str]]] = {}
    if not os.path.isdir(usb_root):
        return devices

    for name in os.listdir(usb_root):
        # Skip entries that are not device directories (they may contain colons for interfaces)
        path = os.path.join(usb_root, name)
        if not os.path.isdir(path):
            continue
        # kernel names for devices are digits and dashes (e.g. '1-1', '2-1.4')
        if not (name[0].isdigit()):
            continue

        vendor = _read_sysfs_file(os.path.join(path, "idVendor"))
        product = _read_sysfs_file(os.path.join(path, "idProduct"))
        serial = _read_sysfs_file(os.path.join(path, "serial"))
        product_str = _read_sysfs_file(os.path.join(path, "product"))

        if not vendor or not product:
            # Not a USB device with vendor/product IDs (could be interface entries)
            continue

        devices[name] = {
            "name": name,
            "vendor": vendor.lower(),
            "product": product.lower(),
            "serial": serial,
            "product_str": product_str,
            "sys_path": path,
        }

    return devices


def parse_adb_devices() -> List[Dict[str, Optional[str]]]:
    """Call `adb devices -l` and parse its output.

    Returns a list of dicts with keys: serial, state, usb (kernel name like '1-1'), transport_id,
    product, model, device.
    """
    try:
        result = subprocess.run(
            ["adb", "devices", "-l"], capture_output=True, text=True, check=True
        )
    except FileNotFoundError:
        # adb not installed/available
        return []
    except subprocess.CalledProcessError:
        # adb command failed (perhaps adb server not running), return empty list
        return []

    devices: List[Dict[str, Optional[str]]] = []
    lines = result.stdout.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("List of devices attached"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue
        serial = parts[0]
        state = parts[1]

        info = {"serial": serial, "state": state, "usb": None, "transport_id": None, "product": None, "model": None, "device": None}
        # parse remaining key:value tokens
        for token in parts[2:]:
            if ":" not in token:
                continue
            key, val = token.split(":", 1)
            if key == "usb":
                # adb reports usb:1-1
                info["usb"] = val
            elif key == "transport_id":
                info["transport_id"] = val
            elif key == "product":
                info["product"] = val
            elif key == "model":
                info["model"] = val
            elif key == "device":
                info["device"] = val

        devices.append(info)

    return devices


def correlate_adb_and_usb() -> List[Dict[str, Optional[str]]]:
    """Return a list of devices combining adb and sysfs USB info.

    Each returned dict will include at least:
    - serial (adb serial if present)
    - state (adb state)
    - usb (kernel usb name like '1-1')
    - transport_id (adb transport id)
    - vendor, product (from sysfs idVendor/idProduct if available)
    - status: 'adb' if present in adb list, 'edl' if a Qualcomm USB device exists but not in adb, else 'unknown'
    """
    usb_map = get_usb_devices_sysfs()
    adb_list = parse_adb_devices()

    # Start with adb devices
    combined: List[Dict[str, Optional[str]]] = []
    adb_usb_names = set()

    for a in adb_list:
        usb_name = a.get("usb")
        vendor = None
        product = None
        serial = None
        if usb_name and usb_name in usb_map:
            u = usb_map[usb_name]
            vendor = u.get("vendor")
            product = u.get("product")
            serial = u.get("serial")
            adb_usb_names.add(usb_name)

        status = "adb"
        combined.append({
            "serial": a.get("serial"),
            "state": a.get("state"),
            "usb": usb_name,
            "transport_id": a.get("transport_id"),
            "vendor": vendor,
            "product": product,
            "product_str": usb_map.get(usb_name, {}).get("product_str") if usb_name else None,
            "status": status,
        })

    # Add USB-only devices (not present in adb). These may be in EDL or otherwise not in adb-mode.
    for usb_name, u in usb_map.items():
        if usb_name in adb_usb_names:
            continue
        vendor = u.get("vendor")
        product = u.get("product")
        # Detect common EDL indications:
        # - product id 9008 is the common Qualcomm EDL PID
        # - vendor 05c6 (Qualcomm) not present in adb may indicate EDL as well
        known_edl_pids = {"9008"}
        if product in known_edl_pids:
            status = "edl"
        elif vendor == "05c6":
            status = "edl"
        else:
            status = "unknown"

        combined.append({
            "serial": u.get("serial"),
            "state": None,
            "usb": usb_name,
            "transport_id": None,
            "vendor": vendor,
            "product": product,
            "product_str": u.get("product_str"),
            "status": status,
        })

    return combined


def adb_reboot_edl(transport_id: str, confirm: bool = True) -> Dict[str, str]:
    """Attempt to reboot the adb device identified by transport_id into EDL.

    If confirm is True the function will prompt the user via input() before proceeding.
    Returns a dict with keys: success ("true"/"false"), msg (human-readable)
    """
    if not transport_id:
        return {"success": "false", "msg": "No transport_id provided"}

    if confirm:
        ans = input(f"Reboot adb device with transport_id={transport_id} into EDL? [y/N]: ")
        if ans.strip().lower() not in ("y", "yes"):
            return {"success": "false", "msg": "User cancelled"}

    try:
        # adb -t <transport_id> reboot edl
        subprocess.run(["adb", "-t", str(transport_id), "reboot", "edl"], check=True)
        return {"success": "true", "msg": "Sent reboot edl command"}
    except FileNotFoundError:
        return {"success": "false", "msg": "adb not found"}
    except subprocess.CalledProcessError as e:
        return {"success": "false", "msg": f"adb failed: {e}"}


if __name__ == "__main__":
    # Quick CLI to print correlated devices and offer to reboot adb devices into EDL
    devices = correlate_adb_and_usb()
    if not devices:
        print("No devices detected (adb missing or no USB devices)")
    else:
        for d in devices:
            usb = d.get("usb") or "(no usb path)"
            vendor = d.get("vendor") or "?"
            product = d.get("product") or "?"
            status = d.get("status")
            t = d.get("transport_id") or "-"
            print(f"usb={usb} vendor={vendor} product={product} status={status} transport_id={t}")

        # Offer to reboot adb devices that appear in adb and have vendor:product indicating not EDL
        for d in devices:
            if d.get("status") == "adb":
                # If vendor:product is specifically 05c6:901f (example in user's note), suggest reboot
                vp = None
                if d.get("vendor") and d.get("product"):
                    vp = f"{d.get('vendor')}:{d.get('product')}"
                if vp == "05c6:901f" or vp is None:
                    tid = d.get("transport_id")
                    if tid:
                        print(f"Device {d.get('usb')} (transport {tid}) appears to be in adb (vendor:product={vp}).")
                        res = adb_reboot_edl(tid, confirm=True)
                        print(res.get("msg"))


def get_qualcomm_serials() -> List[str]:
    """Backwards-compatible helper.

    Returns a list of strings identifying Qualcomm devices. This preserves the old
    function name used elsewhere in the codebase. The returned identifiers prefer
    the device serial from sysfs (if available), otherwise the kernel usb path
    (e.g. '1-1'), otherwise the adb transport id.
    """
    import re

    devices = correlate_adb_and_usb()
    ids: List[str] = []
    for d in devices:
        # Prefer an explicit serial if available
        sid = d.get("serial")
        if not sid:
            # Try to extract SN from product_str (many EDL devices embed SN in the product string)
            ps = d.get("product_str") or ""
            m = re.search(r"SN[:=]?([A-F0-9]+)", ps, re.IGNORECASE)
            if m:
                sid = m.group(1)

        # Fallbacks
        if not sid:
            sid = d.get("usb") or d.get("transport_id")

        if sid:
            ids.append(sid)

    return ids
