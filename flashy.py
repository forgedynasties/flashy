from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal, Container
from textual.widgets import Header, Footer, Static, DataTable, Label, Input
from textual.binding import Binding
from textual import work
from typing import List, Dict, Optional
import time
from pathlib import Path

from backend import correlate_adb_and_usb, adb_reboot_edl, flash_device
# Display latest streamed log line only; no on-disk parsing required here


class DeviceFlasher(App):
    """Flashy - Multi-device flasher UI."""

    TITLE = "Flashy"
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_devices", "Refresh"),
        Binding("space", "toggle_device", "Select"),
        #Binding("e", "reboot_selected", "Reboot to EDL", show=True),
        Binding("f", "flash_selected", "Flash", show=True),
    ]

    def __init__(self):
        super().__init__()
        # devices is a list of correlated device dicts from correlate_adb_and_usb()
        self.devices: List[Dict[str, Optional[str]]] = []
        # Selected set contains the key used to identify devices (usb path or serial or transport)
        self.selected_keys = set()
        self.auto_refresh_enabled = True
        # Flash status tracking
        self.flashing_devices = set()
        # Flash status: key -> "not started" | "in progress" | "completed"
        self.flash_status: Dict[str, str] = {}
        # Live latest log line per device (key -> last line)
        self.last_lines: Dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Static(
            """
███████╗██╗      █████╗ ███████╗██╗  ██╗██╗   ██╗
██╔════╝██║     ██╔══██╗██╔════╝██║  ██║╚██╗ ██╔╝
█████╗  ██║     ███████║███████╗███████║ ╚████╔╝ 
██╔══╝  ██║     ██╔══██║╚════██║██╔══██║  ╚██╔╝  
██║     ███████╗██║  ██║███████║██║  ██║   ██║   
╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   
                                                 
            """,
            id="flashy-logo", classes="logo"
        )
        with Vertical(id="main"):
            with Horizontal(id="firmware-row"):
                #yield Static("FW:", classes="fw-label")
                yield Input(placeholder="/path/to/firmware", id="firmware-input", value="/home/hwpc/firmware/nfc-debug/qfil_download_emmc/")
                # Optional expected partitions input to compute percentage progress
                #yield Input(placeholder="expected partitions (optional)", id="expected-input", value="")
            yield DataTable(id="devices-table")
        yield Label("Status: Ready", id="status")
        yield Footer()

    CSS = """
    #flashy-logo {
        width: 100%;
        content-align: center middle;
        color: $accent;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 1;
    }

    #firmware-row {
        height: auto;
        margin: 1;
    }
    .fw-label {
        width: 4;
        content-align: right middle;
    }
    #firmware-input {
        width: 1fr;
    }
    """

    def on_mount(self) -> None:
        table = self.query_one("#devices-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.focus()
        self.refresh_devices_table()
        self.set_interval(2.0, self._periodic_refresh)

    def _device_key(self, d: Dict[str, Optional[str]]) -> str:
        # Unique-ish key used for selection: prefer usb path, then serial, then transport_id
        return d.get("usb") or d.get("serial") or (d.get("transport_id") or "")

    def _periodic_refresh(self) -> None:
        if self.auto_refresh_enabled:
            # We're already running on the app/main thread via set_interval,
            # so call refresh directly instead of call_from_thread.
            self.refresh_devices_table()

    def refresh_devices_table(self, silent: bool = False) -> None:
        table = self.query_one("#devices-table", DataTable)
        status = self.query_one("#status", Label)

        # Save cursor position before refresh
        try:
            saved_cursor_row = table.cursor_row
        except Exception:
            saved_cursor_row = 0

        # Fetch correlated devices
        try:
            new_devices = correlate_adb_and_usb()
        except Exception as e:
            status.update(f"Status: error refreshing devices: {e}")
            return

        # Keep only Qualcomm or explicit EDL PID devices
        qual = [d for d in new_devices if (d.get("vendor") == "05c6" or d.get("product") == "9008")]

        self.devices = qual

        # Rebuild table (Progress column shows latest streamed log line)
        table.clear(columns=True)
        table.add_columns("Sel", "Serial", "Status", "Progress", "Flash")

        if not qual:
            table.add_row(" ", "No Qualcomm devices found", "—", "—")
            status.update("Status: no devices")
            return

        for d in qual:
            key = self._device_key(d)
            sel = "✓" if key in self.selected_keys else " "
            
            # Extract serial number from product_str if available (like "SN:CB4713E8")
            import re
            serial_str = d.get("serial")
            if not serial_str:
                ps = d.get("product_str") or ""
                m = re.search(r"SN[:=]?([A-F0-9]+)", ps, re.IGNORECASE)
                if m:
                    serial_str = m.group(1)
            
            # Fallback to usb path if no serial
            if not serial_str:
                serial_str = d.get("usb") or "(no id)"
            
            # Show EDL/ADB status
            device_status = "EDL" if d.get("product") == "9008" else "ADB"
            
            # Show flash status
            flash_status = self.flash_status.get(key, "not started")

            # Show latest streamed log line or a placeholder
            latest_line = self.last_lines.get(key)
            if latest_line:
                # keep the cell compact
                progress_cell = latest_line if len(latest_line) <= 80 else latest_line[:77] + "..."
            else:
                progress_cell = "—"

            table.add_row(sel, serial_str, device_status, progress_cell, flash_status)

        status.update(f"Status: {len(self.devices)} device(s)")
        
        # Restore cursor position
        if saved_cursor_row is not None and saved_cursor_row >= 0:
            try:
                # Make sure cursor is within valid range
                if saved_cursor_row < len(self.devices):
                    table.move_cursor(row=saved_cursor_row)
            except Exception:
                pass

    def action_refresh_devices(self) -> None:
        self.refresh_devices_table()

    def action_toggle_device(self) -> None:
        table = self.query_one("#devices-table", DataTable)
        try:
            row = table.cursor_row
        except Exception:
            return

        if row is None:
            return

        if row < 0 or row >= len(self.devices):
            return

        d = self.devices[row]
        key = self._device_key(d)
        if key in self.selected_keys:
            self.selected_keys.remove(key)
        else:
            self.selected_keys.add(key)
        self.refresh_devices_table(silent=True)

    def action_reboot_selected(self) -> None:
        # Trigger background reboot for selected devices
        if not self.selected_keys:
            self.query_one("#status", Label).update("Status: no device selected")
            return
        self.reboot_selected_to_edl(list(self.selected_keys))

    def action_flash_selected(self) -> None:
        # Trigger background flash for selected devices
        if not self.selected_keys:
            self.query_one("#status", Label).update("Status: no device selected")
            return
        
        # Get firmware path from input
        firmware_input = self.query_one("#firmware-input", Input)
        firmware_path = firmware_input.value.strip()
        
        if not firmware_path:
            self.query_one("#status", Label).update("Status: firmware path required")
            return
        
        if not Path(firmware_path).is_dir():
            self.query_one("#status", Label).update(f"Status: firmware path not found: {firmware_path}")
            return
        
        # Separate ADB and EDL devices
        adb_devices = []
        edl_devices = []
        
        for key in self.selected_keys:
            for d in self.devices:
                if key == self._device_key(d):
                    if d.get("status") == "adb":
                        adb_devices.append((key, d))
                    else:
                        edl_devices.append((key, d))
                    break
        
        # Start the flash sequence
        self.flash_sequence(adb_devices, edl_devices, firmware_path)
    
    @work(thread=True)
    def flash_sequence(self, adb_devices: List, edl_devices: List, firmware_path: str) -> None:
        """Flash devices, rebooting ADB devices to EDL first."""
        status = self.query_one("#status", Label)
        
        # Step 1: Reboot ADB devices to EDL
        if adb_devices:
            self.call_from_thread(status.update, f"Status: Rebooting {len(adb_devices)} ADB device(s) to EDL...")
            
            for key, device in adb_devices:
                tid = device.get("transport_id")
                if tid:
                    try:
                        adb_reboot_edl(tid, confirm=False)
                        self.call_from_thread(status.update, f"Status: Rebooted {key} to EDL, waiting...")
                    except Exception as e:
                        self.call_from_thread(status.update, f"Status: Failed to reboot {key}: {e}")
            
            # Wait for devices to appear in EDL mode
            self.call_from_thread(status.update, "Status: Waiting 5s for devices to enter EDL...")
            time.sleep(5)
            
            # Refresh device list to get updated status
            self.call_from_thread(self.refresh_devices_table)
            time.sleep(1)  # Give UI time to update
        
        # Step 2: Flash all devices (original EDL + rebooted ADB)
        all_devices_to_flash = []
        
        # Re-scan to get updated device list with new EDL devices
        for key in self.selected_keys:
            for d in self.devices:
                if key == self._device_key(d):
                    all_devices_to_flash.append((key, d))
                    break
        
        if not all_devices_to_flash:
            self.call_from_thread(status.update, "Status: No devices to flash")
            return
        
        self.call_from_thread(status.update, f"Status: Starting flash on {len(all_devices_to_flash)} device(s)...")
        
        for key, device in all_devices_to_flash:
            self.flashing_devices.add(key)
            self.flash_status[key] = "in progress"
            # no progress counts — we will display the latest log line only
            self.flash_device_bg(key, device, firmware_path)
        
        self.call_from_thread(self.refresh_devices_table)

    @work(thread=True)
    def flash_device_bg(self, key: str, device: Dict, firmware_path: str) -> None:
        """Flash a single device in background thread."""
        status = self.query_one("#status", Label)
        
        # Extract serial for qdl command (same logic as display)
        import re
        serial = device.get("serial")
        if not serial:
            ps = device.get("product_str") or ""
            m = re.search(r"SN[:=]?([A-F0-9]+)", ps, re.IGNORECASE)
            if m:
                serial = m.group(1)
        
        # Fallback to usb path if no serial found
        if not serial:
            serial = device.get("usb") or key
        
        # Define a simple line callback: store the latest line and refresh UI
        def _line_cb(line: str) -> None:
            try:
                self.last_lines[key] = line
            except Exception:
                pass
            # refresh UI to show the latest line in Progress column
            try:
                self.call_from_thread(self.refresh_devices_table, True)
            except Exception:
                pass
            # update a compact status line for the user
            try:
                self.call_from_thread(status.update, f"Status: {serial} | {line}")
            except Exception:
                pass

        try:
            # Run flash in streaming-only mode (no writing to file) and pass the callback
            returncode = flash_device(
                serial,
                firmware_path,
                output_callback=_line_cb,
                logs_dir=None,
            )
            
            if returncode == 0:
                self.call_from_thread(status.update, f"Status: {serial} flashed successfully")
                self.flash_status[key] = "completed"
                # final refresh to ensure progress shows final count
                try:
                    self.call_from_thread(self.refresh_devices_table, True)
                except Exception:
                    pass
            else:
                self.call_from_thread(status.update, f"Status: {serial} flash failed (code {returncode})")
                self.flash_status[key] = "failed"
        except Exception as e:
            self.call_from_thread(status.update, f"Status: {serial} error: {e}")
            self.flash_status[key] = "failed"
        finally:
            self.flashing_devices.discard(key)
            self.call_from_thread(self.refresh_devices_table)

    @work(thread=True)
    def reboot_selected_to_edl(self, keys: List[str]) -> None:
        status = self.query_one("#status", Label)
        correlated = self.devices
        count = 0
        for key in keys:
            # find device in correlated list
            target = None
            for d in correlated:
                if key == self._device_key(d):
                    target = d
                    break
            if not target:
                continue
            tid = target.get("transport_id")
            if not tid:
                # no adb transport id -> skip
                self.call_from_thread(status.update, f"Status: device {key} has no adb transport id")
                continue
            # perform reboot (no interactive confirm here)
            res = adb_reboot_edl(tid, confirm=False)
            self.call_from_thread(status.update, f"Status: reboot {key} -> {res.get('msg')}")
            count += 1
            time.sleep(0.1)
        self.call_from_thread(status.update, f"Status: rebooted {count} device(s)")

    def on_unmount(self) -> None:
        """Cleanup on exit."""
        self.auto_refresh_enabled = False


if __name__ == "__main__":
    app = DeviceFlasher()
    app.run()
