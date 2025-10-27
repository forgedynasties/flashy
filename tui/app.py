"""Main TUI application for Flashy."""

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, Static, DataTable, DirectoryTree, Log, Label, Button
from textual.binding import Binding
from textual import work
from textual.message import Message
from typing import List, Optional
import os
from pathlib import Path
import time
import subprocess

from backend import get_qualcomm_serials, flash_device
from .screens import FlashConfirmScreen
from .styles import CSS


class FlashyTUI(App):
    """A TUI for flashing Qualcomm devices."""
    
    CSS = CSS
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_devices", "Refresh Devices"),
        Binding("f", "confirm_flash", "Flash Selected", show=True),
        Binding("tab", "focus_next", "Next Panel"),
        Binding("shift+tab", "focus_previous", "Previous Panel"),
    ]
    
    def __init__(self):
        super().__init__()
        self.selected_device = None
        self.selected_firmware = None
        self.devices = []
        self.auto_refresh_enabled = True
        self.last_device_count = 0
        self.flash_confirmed = False
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        # Devices Panel
        with Vertical(id="devices-panel"):
            yield Static("📱 Qualcomm Devices (Auto-refresh: ON)", classes="panel-title", id="devices-title")
            yield DataTable(id="devices-table")
        
        # Firmware Panel
        with Vertical(id="firmware-panel"):
            yield Static("💾 Firmware Selection (↑↓ navigate, Space/Enter select)", classes="panel-title")
            yield DirectoryTree(str(Path.home()), id="firmware-tree")
        
        # Firmware Info Panel
        with Vertical(id="firmware-info"):
            yield Static("📂 Selected Firmware", classes="panel-title")
            yield Static("No firmware selected", id="firmware-path", classes="info-label")
        
        # Log Panel
        with Vertical(id="log-panel"):
            yield Static("📋 Flash Log", classes="panel-title")
            yield Log(id="flash-log")
        
        yield Container(
            Label("Status: Ready | Auto-refresh: ON", id="status-label"),
            id="status-bar"
        )
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the app when mounted."""
        self.refresh_devices_table()
        
        # Setup devices table
        table = self.query_one("#devices-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.focus()
        
        # Setup directory tree
        tree = self.query_one("#firmware-tree", DirectoryTree)
        tree.show_root = True
        tree.show_guides = True
        
        # Setup log
        log = self.query_one("#flash-log", Log)
        log.write_line("[bold green]Flashy TUI Started[/bold green]")
        log.write_line("Auto-refresh enabled - devices will update automatically")
        log.write_line("Navigation: TAB to switch panels, Arrow keys to navigate, SPACE/ENTER to select firmware")
        log.write_line("Press 'r' to refresh devices manually, 'f' to flash selected device")
        
        # Start auto-refresh worker
        self.start_auto_refresh()
    
    @work(thread=True)
    def start_auto_refresh(self) -> None:
        """Background thread to auto-refresh device list."""
        while self.auto_refresh_enabled:
            time.sleep(2)  # Check every 2 seconds
            
            try:
                current_devices = get_qualcomm_serials()
                
                # Check if device list changed
                if set(current_devices) != set(self.devices):
                    # Detect what changed
                    added = set(current_devices) - set(self.devices)
                    removed = set(self.devices) - set(current_devices)
                    
                    # Update UI from thread
                    self.call_from_thread(self.update_devices_list, current_devices, added, removed)
                    
            except Exception as e:
                # Silently continue on errors (device might be in transition)
                pass
    
    def update_devices_list(self, new_devices: List[str], added: set, removed: set) -> None:
        """Update the devices list when changes are detected."""
        log = self.query_one("#flash-log", Log)
        
        # Log changes
        if added:
            for device in added:
                log.write_line(f"[bold green]🔌 Device connected: {device}[/bold green]")
                # Play connection sound
                os.system('play -nq -t alsa synth 0.1 sine 800 2>/dev/null &')
        
        if removed:
            for device in removed:
                log.write_line(f"[bold red]🔌 Device disconnected: {device}[/bold red]")
                # Play disconnection sound
                os.system('play -nq -t alsa synth 0.1 sine 400 2>/dev/null &')
                
                # Clear selection if removed device was selected
                if device == self.selected_device:
                    self.selected_device = None
                    log.write_line(f"[yellow]⚠ Selected device disconnected[/yellow]")
        
        # Update the table
        self.devices = new_devices
        self.refresh_devices_table(silent=True)
    
    def refresh_devices_table(self, silent: bool = False) -> None:
        """Refresh the devices table with current Qualcomm devices."""
        table = self.query_one("#devices-table", DataTable)
        log = self.query_one("#flash-log", Log)
        
        # Save current selection
        try:
            current_row = table.cursor_row
        except:
            current_row = None
        
        table.clear(columns=True)
        table.add_columns("Serial Number", "Status")
        
        if not silent:
            log.write_line("[cyan]Scanning for Qualcomm devices...[/cyan]")
        
        try:
            if not silent:
                self.devices = get_qualcomm_serials()
            
            if not self.devices:
                if not silent:
                    log.write_line("[yellow]No Qualcomm devices found[/yellow]")
                table.add_row("No devices found", "—")
            else:
                for idx, serial in enumerate(self.devices):
                    status = "Selected" if serial == self.selected_device else "Ready"
                    table.add_row(serial, status)
                
                if not silent:
                    log.write_line(f"[green]Found {len(self.devices)} device(s)[/green]")
                
                # Restore selection if device still exists
                if self.selected_device in self.devices:
                    row_idx = self.devices.index(self.selected_device)
                    table.move_cursor(row=row_idx)
                
        except Exception as e:
            log.write_line(f"[red]Error scanning devices: {e}[/red]")
            table.add_row("Error scanning", "—")
        
        self.update_status("Ready")
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle device selection."""
        table = self.query_one("#devices-table", DataTable)
        
        if self.devices and event.cursor_row < len(self.devices):
            self.selected_device = self.devices[event.cursor_row]
            log = self.query_one("#flash-log", Log)
            log.write_line(f"[cyan]Selected device: {self.selected_device}[/cyan]")
            self.update_status(f"Selected: {self.selected_device}")
            
            # Update table to show selection
            self.refresh_devices_table(silent=True)
    
    def on_key(self, event) -> None:
        """Handle global key events."""
        # Check if firmware tree is focused and space is pressed
        try:
            tree = self.query_one("#firmware-tree", DirectoryTree)
            if tree.has_focus and event.key == "space":
                # Get the currently highlighted node
                if tree.cursor_node is not None:
                    node = tree.cursor_node
                    if node.data:
                        path = node.data.path
                        self.handle_firmware_selection(path)
                        event.prevent_default()
                        event.stop()
        except Exception:
            pass  # Ignore if tree not ready
    
    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handle firmware directory selection with Enter key on files."""
        # When Enter is pressed on a file, select its parent directory
        self.handle_firmware_selection(event.path)
    
    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Handle firmware directory selection with Enter key on directories."""
        # When Enter is pressed on a directory, try to select it as firmware
        self.handle_firmware_selection(event.path)
    
    def handle_firmware_selection(self, path: Path) -> None:
        """Common handler for firmware selection."""
        log = self.query_one("#flash-log", Log)
        firmware_path_widget = self.query_one("#firmware-path", Static)
        
        # Check if it's a directory containing firmware files
        if path.is_dir():
            # Look for typical firmware files
            files = list(path.iterdir())
            has_elf = any(f.suffix == '.elf' for f in files)
            has_xml = any(f.suffix == '.xml' for f in files)
            
            if has_elf and has_xml:
                self.selected_firmware = str(path)
                log.write_line(f"[bold green]✓ Selected firmware: {path}[/bold green]")
                firmware_path_widget.update(f"[green]{self.selected_firmware}[/green]")
                self.update_status(f"Firmware: {path.name}")
            else:
                log.write_line(f"[yellow]⚠ Directory does not contain firmware files (.elf and .xml)[/yellow]")
                log.write_line(f"[dim]Path: {path}[/dim]")
        else:
            # If it's a file, select its parent directory
            parent = path.parent
            self.handle_firmware_selection(parent)
    
    def update_status(self, message: str) -> None:
        """Update the status bar."""
        status = self.query_one("#status-label", Label)
        status.update(f"Status: {message} | Auto-refresh: ON")
    
    def action_refresh_devices(self) -> None:
        """Refresh the devices list."""
        self.refresh_devices_table()
    
    def action_confirm_flash(self) -> None:
        """Show confirmation dialog for flashing."""
        log = self.query_one("#flash-log", Log)
        
        if not self.selected_device:
            log.write_line("[red]⚠ No device selected![/red]")
            return
        
        if not self.selected_firmware:
            log.write_line("[red]⚠ No firmware selected![/red]")
            return
        
        # Push the confirmation screen
        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                self.start_flash()
            else:
                log.write_line("[yellow]Flash operation cancelled[/yellow]")
        
        self.push_screen(FlashConfirmScreen(self.selected_device, self.selected_firmware, on_confirm))
    
    def action_select(self) -> None:
        """Select current item (for firmware tree)."""
        try:
            tree = self.query_one("#firmware-tree", DirectoryTree)
            if tree.has_focus and tree.cursor_node is not None:
                node = tree.cursor_node
                if node.data:
                    path = node.data.path
                    self.handle_firmware_selection(path)
        except Exception:
            pass
    
    def start_flash(self) -> None:
        """Start the flashing process in a background thread."""
        self.do_flash()
    
    @work(thread=True)
    def do_flash(self) -> None:
        """Flash the device in a background thread."""
        log = self.query_one("#flash-log", Log)
        
        log.write_line("[bold yellow]" + "="*50 + "[/bold yellow]")
        log.write_line(f"[bold]Starting flash operation...[/bold]")
        log.write_line(f"Device: [cyan]{self.selected_device}[/cyan]")
        log.write_line(f"Firmware: [yellow]{self.selected_firmware}[/yellow]")
        log.write_line("[bold yellow]" + "="*50 + "[/bold yellow]")
        
        self.call_from_thread(self.update_status, "Flashing...")
        
        try:
            # Flash device with output callback
            def log_output(line: str):
                log.write_line(line)
            
            returncode = flash_device(
                self.selected_device,
                self.selected_firmware,
                output_callback=log_output
            )
            
            if returncode == 0:
                log.write_line("[bold green]✓ Flash completed successfully![/bold green]")
                self.call_from_thread(self.update_status, "Flash completed!")
                # Play success sound
                os.system('play -nq -t alsa synth 0.5 sine 440 2>/dev/null')
            else:
                log.write_line(f"[bold red]✗ Flash failed with exit code {returncode}[/bold red]")
                self.call_from_thread(self.update_status, "Flash failed!")
                # Play error sound
                os.system('play -nq -t alsa synth 0.5 sine 220 2>/dev/null')
                
        except Exception as e:
            log.write_line(f"[bold red]✗ Flash error: {e}[/bold red]")
            self.call_from_thread(self.update_status, "Flash error!")
            os.system('play -nq -t alsa synth 0.5 sine 220 2>/dev/null')
    
    def on_unmount(self) -> None:
        """Cleanup when app closes."""
        self.auto_refresh_enabled = False
