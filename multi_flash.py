"""Minimal multi-device flasher UI.

This simplified TUI focuses on listing Qualcomm devices and providing
real-time progress tracking during flashing.

- Shows only Qualcomm devices (vendor 05c6 or product 9008)
- Displays Serial and Progress% for each device
- 'space' toggles selection
- 'e' reboots selected device(s) into EDL
- 'f' starts flashing selected devices with real-time progress
"""

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Header, Footer, Static, DataTable, Label, Input
from textual.binding import Binding
from textual import work
from typing import List, Dict, Optional
import time

from backend import correlate_adb_and_usb, adb_reboot_edl, flash_device


class DeviceFlasher(App):
    """Minimal multi-device UI with progress tracking."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_devices", "Refresh"),
        Binding("space", "toggle_device", "Select"),
        Binding("e", "reboot_selected", "Reboot -> EDL", show=True),
        Binding("f", "flash_selected", "Flash", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.devices: List[Dict[str, Optional[str]]] = []
        self.selected_keys = set()
        self.auto_refresh_enabled = True
        self.device_progress: Dict[str, int] = {}  # key -> progress %
        self.firmware_path = "/home/hwpc/firmware/nfc-debug/qfil_download_emmc/"

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main"):
            yield Static("📱 Multi-Flash — SPACE=select | e=reboot EDL | f=flash | r=refresh", id="help")
            yield Input(placeholder="Firmware path", value=self.firmware_path, id="fw-input")
            yield DataTable(id="devices-table")
        yield Label("Status: Ready", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#devices-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.focus()
        self.refresh_devices_table()
        self.set_interval(2.0, self._periodic_refresh)

    def _device_key(self, d: Dict[str, Optional[str]]) -> str:
        return d.get("usb") or d.get("serial") or (d.get("transport_id") or "")

    def _periodic_refresh(self) -> None:
        if self.auto_refresh_enabled:
            self.refresh_devices_table()

    def refresh_devices_table(self, silent: bool = False) -> None:
        table = self.query_one("#devices-table", DataTable)
        status = self.query_one("#status", Label)

        try:
            new_devices = correlate_adb_and_usb()
        except Exception as e:
            status.update(f"Status: error: {e}")
            return

        qual = [d for d in new_devices if (d.get("vendor") == "05c6" or d.get("product") == "9008")]
        self.devices = qual

        table.clear(columns=True)
        table.add_columns("Sel", "Serial", "Progress")

        if not qual:
            table.add_row(" ", "No devices", "—")
            status.update("Status: no devices")
            return

        for d in qual:
            key = self._device_key(d)
            sel = "✓" if key in self.selected_keys else " "
            
            # Extract serial from product_str or use usb path
            serial = d.get("serial") or d.get("usb") or "(unknown)"
            
            # Show progress if available
            progress = self.device_progress.get(key, 0)
            if progress > 0:
                progress_str = f"{progress}%"
            else:
                # Show EDL/ADB status if not flashing
                st = "EDL" if d.get("product") == "9008" else "ADB"
                progress_str = st
            
            table.add_row(sel, serial, progress_str)

        status.update(f"Status: {len(self.devices)} device(s)")
        
        # Update log display
        self._update_log_display()

    def _update_log_display(self) -> None:
        """Update the log container with latest device logs."""
        log_container = self.query_one("#log-container", ScrollableContainer)
        log_container.remove_children()
        
        # Show logs for devices that are currently flashing
        for key in self.flashing_devices:
            if key in self.device_logs:
                # Find device serial for display
                serial = key
                for d in self.devices:
                    if self._device_key(d) == key:
                        serial = d.get("serial") or key
                        break
                
                with log_container:
                    log_container.mount(Static(f"📱 {serial}", classes="log-header"))
                    log_container.mount(Static(self.device_logs[key], classes="log-line"))

    def action_refresh_devices(self) -> None:
        self.refresh_devices_table()

    def action_toggle_device(self) -> None:
        table = self.query_one("#devices-table", DataTable)
        try:
            row = table.cursor_row
        except Exception:
            return

        if row is None or row < 0 or row >= len(self.devices):
            return

        d = self.devices[row]
        key = self._device_key(d)
        if key in self.selected_keys:
            self.selected_keys.remove(key)
        else:
            self.selected_keys.add(key)
        self.refresh_devices_table()

    def action_reboot_selected(self) -> None:
        if not self.selected_keys:
            self.query_one("#status", Label).update("Status: no device selected")
            return
        self.reboot_selected_to_edl(list(self.selected_keys))

    @work(thread=True)
    def reboot_selected_to_edl(self, keys: List[str]) -> None:
        status = self.query_one("#status", Label)
        count = 0
        for key in keys:
            target = None
            for d in self.devices:
                if key == self._device_key(d):
                    target = d
                    break
            if not target:
                continue
            tid = target.get("transport_id")
            if not tid:
                self.call_from_thread(status.update, f"Status: {key} no transport id")
                continue
            res = adb_reboot_edl(tid, confirm=False)
            self.call_from_thread(status.update, f"Status: rebooted {key}")
            count += 1
            time.sleep(0.1)
        self.call_from_thread(status.update, f"Status: rebooted {count} device(s)")

    def action_flash_selected(self) -> None:
        if not self.selected_keys:
            self.query_one("#status", Label).update("Status: no device selected")
            return
        
        # Get firmware path from input
        fw_input = self.query_one("#fw-input", Input)
        self.firmware_path = fw_input.value.strip()
        
        if not self.firmware_path:
            self.query_one("#status", Label).update("Status: firmware path required")
            return
        
        # Start flashing selected devices
        for key in self.selected_keys:
            target = None
            for d in self.devices:
                if key == self._device_key(d):
                    target = d
                    break
            if target:
                # Reset progress
                self.device_progress[key] = 0
                self.flash_device_thread(key, target, self.firmware_path)
        
        self.query_one("#status", Label).update(f"Status: flashing {len(self.selected_keys)} device(s)...")

    @work(thread=True)
    def flash_device_thread(self, key: str, device: Dict, fw_path: str) -> None:
        status = self.query_one("#status", Label)
        
        # Get serial for qdl command
        serial = device.get("serial") or device.get("usb") or key
        
        def progress_cb(percent: int):
            self.device_progress[key] = percent
            self.call_from_thread(self.refresh_devices_table)
        
        try:
            returncode = flash_device(
                serial,
                fw_path,
                progress_callback=progress_cb
            )
            
            if returncode == 0:
                self.device_progress[key] = 100
                self.call_from_thread(status.update, f"Status: {key} flash complete")
            else:
                self.device_progress[key] = 0
                self.call_from_thread(status.update, f"Status: {key} flash failed ({returncode})")
        except Exception as e:
            self.device_progress[key] = 0
            self.call_from_thread(status.update, f"Status: {key} error: {e}")

from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal, Container, ScrollableContainer
from textual.widgets import Header, Footer, Static, DataTable, Label, Input, ProgressBar
from textual.binding import Binding
from textual import work
from typing import List, Dict, Optional
import time
from pathlib import Path

from backend import correlate_adb_and_usb, adb_reboot_edl, flash_device


class DeviceFlasher(App):
    """Flashy - Multi-device flasher UI."""

    TITLE = "Flashy"
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_devices", "Refresh"),
        Binding("space", "toggle_device", "Select"),
        Binding("e", "reboot_selected", "Reboot -> EDL", show=True),
        Binding("f", "flash_selected", "Flash", show=True),
    ]

    def __init__(self):
        super().__init__()
        # devices is a list of correlated device dicts from correlate_adb_and_usb()
        self.devices: List[Dict[str, Optional[str]]] = []
        # Selected set contains the key used to identify devices (usb path or serial or transport)
        self.selected_keys = set()
        self.auto_refresh_enabled = True
        # Progress tracking: key -> percentage
        self.device_progress: Dict[str, int] = {}
        # Flash status tracking
        self.flashing_devices = set()
        # Log tracking: key -> latest log line
        self.device_logs: Dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main"):
            with Horizontal(id="firmware-row"):
                yield Static("FW:", classes="fw-label")
                yield Input(placeholder="/path/to/firmware", id="firmware-input", value="/home/hwpc/firmware/nfc-debug/qfil_download_emmc/")
            yield DataTable(id="devices-table")
            with ScrollableContainer(id="log-container"):
                pass  # Will be populated with device logs dynamically
        yield Label("Status: Ready", id="status")
        yield Footer()

    CSS = """
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
    #log-container {
        height: 8;
        border: solid $primary;
        margin: 1;
    }
    .device-log-panel {
        height: auto;
        margin-bottom: 1;
    }
    .log-header {
        background: $primary;
        color: $text;
        padding: 0 1;
    }
    .log-line {
        color: $text-muted;
        padding: 0 1;
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

        # Rebuild table
        table.clear(columns=True)
        table.add_columns("Sel", "Serial", "Status", "Progress Bar")

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
            
            # Get progress and create progress bar
            if key in self.device_progress:
                percent = self.device_progress[key]
                if percent == -1:
                    progress_display = "[Failed]"
                else:
                    # Create ASCII progress bar
                    bar_width = 20
                    filled = int(bar_width * percent / 100)
                    bar = "█" * filled + "░" * (bar_width - filled)
                    progress_display = f"[{bar}] {percent}%"
            elif key in self.flashing_devices:
                bar = "░" * 20
                progress_display = f"[{bar}] 0%"
            else:
                progress_display = "—"
            
            table.add_row(sel, serial_str, device_status, progress_display)

        status.update(f"Status: {len(self.devices)} device(s)")
        
        # Restore cursor position
        if saved_cursor_row is not None and saved_cursor_row >= 0:
            try:
                # Make sure cursor is within valid range
                if saved_cursor_row < len(self.devices):
                    table.move_cursor(row=saved_cursor_row)
            except Exception:
                pass
        
        # Update log display
        self._update_log_display()

    def _update_log_display(self) -> None:
        """Update the log container with latest device logs."""
        log_container = self.query_one("#log-container", ScrollableContainer)
        log_container.remove_children()
        
        # Show logs for devices that are currently flashing
        for key in self.flashing_devices:
            if key in self.device_logs:
                # Find device serial for display
                serial = key
                for d in self.devices:
                    if self._device_key(d) == key:
                        import re
                        ps = d.get("product_str") or ""
                        m = re.search(r"SN[:=]?([A-F0-9]+)", ps, re.IGNORECASE)
                        if m:
                            serial = m.group(1)
                        break
                
                log_container.mount(Static(f"📱 {serial}", classes="log-header"))
                log_container.mount(Static(self.device_logs[key], classes="log-line"))

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
            self.device_progress[key] = 0
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
        
        def progress_cb(percent: int):
            self.device_progress[key] = percent
            self.call_from_thread(self.refresh_devices_table)
        
        def output_cb(line: str):
            # Store the latest log line for this device
            # Truncate long lines to fit display
            truncated = line[:80] if len(line) > 80 else line
            self.device_logs[key] = truncated
            self.call_from_thread(self.refresh_devices_table)
        
        try:
            returncode = flash_device(
                serial,
                firmware_path,
                progress_callback=progress_cb,
                output_callback=output_cb
            )
            
            if returncode == 0:
                self.call_from_thread(status.update, f"Status: {serial} flashed successfully")
                self.device_progress[key] = 100
                self.device_logs[key] = "✓ Flash completed successfully"
            else:
                self.call_from_thread(status.update, f"Status: {serial} flash failed (code {returncode})")
                self.device_progress[key] = -1  # Mark as failed
                self.device_logs[key] = f"✗ Flash failed with exit code {returncode}"
        except Exception as e:
            self.call_from_thread(status.update, f"Status: {serial} error: {e}")
            self.device_progress[key] = -1
            self.device_logs[key] = f"✗ Error: {e}"
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
