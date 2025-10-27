# Flashy - Qualcomm Device Flasher

A modern Terminal User Interface (TUI) for flashing Qualcomm devices using QDL (Qualcomm Download Mode).

## Features

- 🔄 **Auto-refresh**: Automatically detects device connections/disconnections
- 📱 **Device Selection**: Easy keyboard navigation for device selection
- 💾 **Firmware Browser**: Navigate your filesystem to select firmware directories
- 📋 **Live Logging**: Real-time flash progress and status updates
- 🔊 **Audio Feedback**: Sound notifications for connections and flash completion
- ⌨️  **Keyboard-Only**: Full keyboard navigation, no mouse required

## Project Structure

```
flashy/
├── backend/                 # Backend logic
│   ├── __init__.py         # Backend module exports
│   ├── device_scanner.py   # Qualcomm device detection
│   └── flasher.py          # QDL flashing functionality
├── tui/                    # Frontend TUI
│   ├── __init__.py         # TUI module exports
│   ├── app.py              # Main TUI application
│   ├── screens.py          # Modal screens (dialogs)
│   └── styles.py           # CSS styling
├── main.py                 # Application entry point
├── lsusb.py               # Legacy device scanner (for reference)
├── qdl.py                 # Legacy flasher (for reference)
└── test.py                # Simple test script

```

## Installation

### Prerequisites

1. **Python 3.8+**
2. **QDL tool** - Qualcomm Download Mode tool
3. **textual** - Python TUI framework
4. **sox** (optional) - For audio feedback

```bash
# Install Python dependencies
pip install textual

# Install sox for audio (optional)
sudo apt install sox  # Ubuntu/Debian
```

### Setup

```bash
# Clone or navigate to the flashy directory
cd /home/hwpc/flashy

# Make sure you have sudo access for USB operations
sudo usermod -a -G plugdev $USER
```

## Usage

### Run the TUI

```bash
python3 main.py
```

### Keyboard Controls

| Key | Action |
|-----|--------|
| `Tab` | Switch between panels |
| `Shift+Tab` | Switch panels (reverse) |
| `↑` / `↓` | Navigate within panels |
| `Space` | Select firmware directory |
| `Enter` | Select firmware / device |
| `r` | Refresh device list |
| `f` | Flash selected device |
| `q` | Quit application |

### Workflow

1. **Connect Device**: Plug in your Qualcomm device in EDL/QDL mode
2. **Select Device**: Device appears automatically in the top-left panel
3. **Select Firmware**: Navigate to firmware directory in top-right panel, press Space/Enter
4. **Flash**: Press `f` to start flashing
5. **Confirm**: Confirm the operation in the dialog
6. **Monitor**: Watch progress in the log panel

## Backend API

### Device Scanner

```python
from backend import get_qualcomm_serials

# Get list of connected Qualcomm devices
serials = get_qualcomm_serials()
print(serials)  # ['CB4713E8', ...]
```

### Flasher

```python
from backend import flash_device

# Flash a device
returncode = flash_device(
    serial="CB4713E8",
    firmware_path="/path/to/firmware",
    storage_type="emmc",  # or "ufs"
    output_callback=lambda line: print(line)
)

if returncode == 0:
    print("Success!")
```

## Development

### Adding New Features

- **Backend**: Add new modules to `backend/`
- **TUI Screens**: Add new screens to `tui/screens.py`
- **Styles**: Modify `tui/styles.py` for visual changes
- **Main App**: Edit `tui/app.py` for core functionality

### Testing Backend

```bash
# Test device scanner
python3 backend/device_scanner.py

# Test flasher
python3 backend/flasher.py <serial> <firmware_path>
```

## Troubleshooting

### No devices found
- Ensure device is in EDL/QDL mode
- Check USB connection
- Verify sudo permissions: `sudo -v`

### Flash fails
- Verify firmware files exist (.elf and .xml)
- Check device serial number is correct
- Ensure QDL tool is installed and in PATH

### Permission errors
- Run with sudo access
- Add user to plugdev group

## License

MIT License - Feel free to use and modify as needed.

## Credits

Built with [Textual](https://github.com/Textualize/textual) - Modern TUI framework for Python
