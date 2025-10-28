"""Modal screens for the Flashy TUI."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Static
from textual.screen import ModalScreen
from typing import Callable, Optional


class FlashConfirmScreen(ModalScreen[bool]):
    """Modal screen to confirm flashing operation."""
    
    def __init__(self, device: str, firmware_path: str, callback: Optional[Callable[[bool], None]] = None):
        super().__init__()
        self.device = device
        self.firmware_path = firmware_path
        self.callback = callback
    
    def compose(self) -> ComposeResult:
        yield Container(
            Static(
                f"[bold]Confirm Flash Operation[/bold]\n\n"
                f"Device: [cyan]{self.device}[/cyan]\n"
                f"Firmware: [yellow]{self.firmware_path}[/yellow]\n\n"
                f"This will overwrite the device firmware!\n"
                f"Are you sure?", 
                id="confirm-message"
            ),
            Horizontal(
                Button("Flash", variant="error", id="confirm-yes"),
                Button("Cancel", variant="primary", id="confirm-no"),
                classes="button-row"
            ),
            id="confirm-dialog"
        )
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        result = event.button.id == "confirm-yes"
        if self.callback:
            self.callback(result)
        self.dismiss(result)


class RebootConfirmScreen(ModalScreen[bool]):
    """Modal screen to confirm reboot-to-EDL action for an adb-connected device."""

    def __init__(self, device_usb: str, transport_id: str, callback: Optional[Callable[[bool], None]] = None):
        super().__init__()
        self.device_usb = device_usb
        self.transport_id = transport_id
        self.callback = callback

    def compose(self) -> ComposeResult:
        yield Container(
            Static(
                f"[bold]Reboot Device to EDL[/bold]\n\n"
                f"Device USB path: [cyan]{self.device_usb}[/cyan]\n"
                f"Transport ID: [yellow]{self.transport_id}[/yellow]\n\n"
                f"This will reboot the device into EDL mode. Continue?",
                id="reboot-confirm-message",
            ),
            Horizontal(
                Button("Reboot to EDL", variant="error", id="reboot-yes"),
                Button("Cancel", variant="primary", id="reboot-no"),
                classes="button-row"
            ),
            id="reboot-confirm-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        result = event.button.id == "reboot-yes"
        if self.callback:
            self.callback(result)
        self.dismiss(result)
