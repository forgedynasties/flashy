#!/usr/bin/env python3
"""Find and return information about Qualcomm USB devices."""

import usb.core
import usb.util


def get_qualcomm_devices():
    """
    Find all Qualcomm USB devices and return their serial numbers and modes.
    
    Returns:
        dict: A dictionary mapping serial numbers to product IDs (modes).
              Example: {'5EC4ABFD': '9008', 'ABC123': '900E'}
    """
    qualcomm_devices = {}
    devices = usb.core.find(find_all=True)
    
    for dev in devices:
        try:
            product = usb.util.get_string(dev, dev.iProduct) or ""
            manufacturer = usb.util.get_string(dev, dev.iManufacturer) or ""
            
            if "Qualcomm" in manufacturer or "Qualcomm" in product:
                serial = None
                if "SN:" in product:
                    serial = product.split("SN:")[-1].strip()
                elif dev.iSerial:
                    serial = usb.util.get_string(dev, dev.iSerial).strip()
                
                if serial:
                    mode = f"{dev.idProduct:04X}"  # Uppercase hex
                    qualcomm_devices[serial] = mode
                    
        except (ValueError, usb.core.USBError):
            continue
        
    return qualcomm_devices