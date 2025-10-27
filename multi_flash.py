"""Multi-device flasher TUI application - Simplified."""

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.widgets import Header, Footer, Static, Input, DataTable, Label, RichLog
from textual.binding import Binding
from textual import work
from typing import List, Dict, Set
import os
from pathlib import Path
import time

from backend import get_qualcomm_serials, flash_device


class DeviceFlasher(App):
    """Multi-device Qualcomm flasher TUI with parallel flashing."""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #top-panel {
        height: auto;
        border: solid $accent;
        padding: 1;
        margin-bottom: 1;
    }
    
    #main-container {
        height: 1fr;
        layout: horizontal;
    }
    
    #devices-panel {
        width: 1fr;
        border: solid $accent;
        padding: 1;
        margin-right: 1;
    }
    
    #progress-container {
        width: 2fr;
        border: solid $accent;
        padding: 1;
    }
    
    #status-bar {
        dock: bottom;
        height: 3;
        background: $boost;
        padding: 1;
    }
    
    .panel-title {
        background: $accent;
        color: $text;
        padding: 0 1;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    
    #firmware-input {
        width: 100%;
        margin-bottom: 1;
    }
    
    DataTable {
        height: 1fr;
    }
    
    #progress-logs-container {
        height: 1fr;
        layout: horizontal;
    }
    
    .device-log {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        padding: 0;
        margin-right: 1;
    }
    
    .device-log-title {
        background: $boost;
        padding: 0 1;
        text-style: bold;
        width: 100%;
    }
    
    RichLog {
        height: 1fr;
        border: none;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_devices", "Refresh"),
        Binding("space", "toggle_device", "Select"),
        Binding("f", "start_flash", "Flash", show=True),
    ]
    
    def __init__(self):
        super().__init__()
        self.devices = []
        self.selected_devices = set()
        self.firmware_path = ""
        self.auto_refresh_enabled = True
        self.flash_results = {}
        self.device_progress = {}
        self.flash_start_times = {}
        self.flash_end_times = {}
    
    def compose(self):
        yield Header()
        
        with Vertical(id="top-panel"):
            yield Static("📂 Firmware Path", classes="panel-title")
            yield Input(
                placeholder="Enter firmware directory path",
                id="firmware-input"
            )
            yield Static(
                "SPACE to select devices | F to flash | R to refresh | Q to quit",
                id="help-text"
            )
        
        with Horizontal(id="main-container"):
            with Vertical(id="devices-panel"):
                yield Static("⚡ Qualcomm Devices", classes="panel-title")
                yield DataTable(id="devices-table")
            
            with Vertical(id="progress-container"):
                yield Static("⚡ Flash Progress", classes="panel-title")
                yield ScrollableContainer(
                    Horizontal(id="progress-logs-container"),
                    id="progress-scroll"
                )
        
        yield Container(
            Label("Ready", id="status-label"),
            id="status-bar"
        )
        
        yield Footer()
    
    def on_mount(self):
        table = self.query_one("#devices-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        
        fw_input = self.query_one("#firmware-input", Input)
        fw_input.value = "/home/hwpc/firmware/nfc-debug/qfil_download_emmc/"
        
        self.refresh_devices_table()
        self.start_auto_refresh()
    
    @work(thread=True)
    def start_auto_refresh(self):
        while self.auto_refresh_enabled:
            time.sleep(2)
            
            try:
                current_devices = get_qualcomm_serials()
                
                if set(current_devices) != set(self.devices):
                    self.call_from_thread(self.update_devices_list, current_devices)
                    
            except Exception:
                pass
    
    def update_devices_list(self, new_devices):
        added = set(new_devices) - set(self.devices)
        removed = set(self.devices) - set(new_devices)
        
        if added:
            for dev in added:
                os.system('play -nq -t alsa synth 0.1 sine 800 2>/dev/null &')
        
        if removed:
            for dev in removed:
                os.system('play -nq -t alsa synth 0.1 sine 400 2>/dev/null &')
                self.selected_devices.discard(dev)
        
        self.devices = new_devices
        self.refresh_devices_table(silent=True)
    
    def refresh_devices_table(self, silent=False):
        table = self.query_one("#devices-table", DataTable)
        
        table.clear(columns=True)
        table.add_columns("Select", "Device Serial", "Status")
        
        try:
            if not silent:
                self.devices = get_qualcomm_serials()
            
            if not self.devices:
                table.add_row("—", "No devices found", "—")
            else:
                for serial in self.devices:
                    select = "✓" if serial in self.selected_devices else "○"
                    
                    if serial in self.flash_results:
                        result = self.flash_results[serial]
                        if result == 0:
                            status = "[green]✓ Success[/green]"
                        else:
                            status = f"[red]✗ Failed ({result})[/red]"
                    elif serial in self.flash_start_times and serial not in self.flash_end_times:
                        status = "[yellow]⏳ Flashing...[/yellow]"
                    else:
                        status = "Ready"
                    
                    table.add_row(select, serial, status)
        
        except Exception as e:
            table.add_row("Error", str(e), "—")
        
        self.update_status(f"Devices: {len(self.devices)} | Selected: {len(self.selected_devices)}")
    
    def action_toggle_device(self):
        if not self.devices:
            return
        
        table = self.query_one("#devices-table", DataTable)
        
        try:
            row = table.cursor_row
            if row < len(self.devices):
                serial = self.devices[row]
                if serial in self.selected_devices:
                    self.selected_devices.remove(serial)
                else:
                    self.selected_devices.add(serial)
                
                self.refresh_devices_table(silent=True)
        except Exception:
            pass
    
    def action_refresh_devices(self):
        self.refresh_devices_table()
    
    def action_start_flash(self):
        fw_input = self.query_one("#firmware-input", Input)
        
        self.firmware_path = fw_input.value.strip()
        
        if not self.firmware_path:
            self.update_status("[red]Firmware path required![/red]")
            return
        
        if not Path(self.firmware_path).is_dir():
            self.update_status(f"[red]Path not found: {self.firmware_path}[/red]")
            return
        
        if not self.selected_devices:
            self.update_status("[red]No devices selected![/red]")
            return
        
        for serial in self.selected_devices:
            self.flash_results.pop(serial, None)
            self.flash_start_times.pop(serial, None)
            self.flash_end_times.pop(serial, None)
            self.device_progress[serial] = []
        
        self.create_progress_panes()
        
        for serial in self.selected_devices:
            self.flash_device_parallel(serial, self.firmware_path)
        
        self.update_status(f"Flashing {len(self.selected_devices)} device(s) in parallel...")
        self.refresh_devices_table(silent=True)
    
    def create_progress_panes(self):
        container = self.query_one("#progress-logs-container", Horizontal)
        container.remove_children()
        
        for serial in sorted(self.selected_devices):
            device_pane = Vertical(classes="device-log")
            
            title = Static(
                f"[bold]{serial}[/bold] [dim](starting...)[/dim]",
                id=f"title-{serial}",
                classes="device-log-title"
            )
            
            rich_log = RichLog(id=f"log-{serial}", wrap=True, highlight=True)
            
            device_pane.compose_add_child(title)
            device_pane.compose_add_child(rich_log)
            container.mount(device_pane)
    
    @work(thread=True)
    def flash_device_parallel(self, serial, firmware_path):
        start_time = time.time()
        self.flash_start_times[serial] = start_time
        
        self.call_from_thread(self.update_device_title, serial, "⏳", "Flashing")
        self.call_from_thread(self.add_device_log, serial, "[bold cyan]⏳ Starting flash...[/bold cyan]")
        
        try:
            def output_cb(line):
                self.device_progress[serial].append(line)
                self.call_from_thread(self.add_device_log, serial, line)
            
            returncode = flash_device(serial, firmware_path, output_callback=output_cb)
            self.flash_results[serial] = returncode
            
            end_time = time.time()
            self.flash_end_times[serial] = end_time
            elapsed = end_time - start_time
            
            if returncode == 0:
                self.call_from_thread(
                    self.add_device_log,
                    serial,
                    f"[bold green]✓ Success in {self.format_time(elapsed)}![/bold green]"
                )
                os.system('play -nq -t alsa synth 0.5 sine 440 2>/dev/null &')
                self.call_from_thread(self.update_device_title, serial, "✓", f"Success ({self.format_time(elapsed)})")
            else:
                self.call_from_thread(
                    self.add_device_log,
                    serial,
                    f"[bold red]✗ Failed after {self.format_time(elapsed)} (code {returncode})[/bold red]"
                )
                os.system('play -nq -t alsa synth 0.5 sine 220 2>/dev/null &')
                self.call_from_thread(self.update_device_title, serial, "✗", f"Failed ({self.format_time(elapsed)})")
        
        except Exception as e:
            end_time = time.time()
            elapsed = end_time - start_time
            self.call_from_thread(
                self.add_device_log,
                serial,
                f"[bold red]✗ Error: {e}[/bold red]"
            )
            self.flash_results[serial] = -1
            self.flash_end_times[serial] = end_time
            os.system('play -nq -t alsa synth 0.5 sine 220 2>/dev/null &')
            self.call_from_thread(self.update_device_title, serial, "✗", f"Error ({self.format_time(elapsed)})")
        
        finally:
            self.call_from_thread(self.refresh_devices_table, True)
    
    def add_device_log(self, serial, message):
        try:
            log = self.query_one(f"#log-{serial}", RichLog)
            log.write(message)
        except Exception:
            pass
    
    def update_device_title(self, serial, icon, status):
        try:
            title = self.query_one(f"#title-{serial}", Static)
            title.update(f"[bold]{icon} {serial}[/bold] [dim]{status}[/dim]")
        except Exception:
            pass
    
    @staticmethod
    def format_time(seconds):
        if seconds < 0:
            seconds = 0
        
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}m {secs:02d}s"
    
    def update_status(self, message):
        try:
            status = self.query_one("#status-label", Label)
            status.update(f"Status: {message}")
        except Exception:
            pass
    
    def on_unmount(self):
        self.auto_refresh_enabled = False


if __name__ == "__main__":
    app = DeviceFlasher()
    app.run()
