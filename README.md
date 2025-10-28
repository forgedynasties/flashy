# Flashy - Qualcomm Device Flasher

A modern Terminal User Interface (TUI) for flashing Qualcomm devices using QDL (Qualcomm Download Mode).

## Features

- 🔄 **Auto-refresh**: Automatically detects device connections/disconnections
- 📱 **Device Selection**: Easy keyboard navigation for device selection
- 💾 **Firmware Browser**: Navigate your filesystem to select firmware directories
- 📋 **Live Logging**: Real-time flash progress and status updates
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

```bash
# Install Python dependencies
pip install textual

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


## Development

### Testing Backend

```bash
# Test device scanner
python3 backend/device_scanner.py

# Test flasher
python3 backend/flasher.py <serial> <firmware_path>
```
## License

MIT License - Feel free to use and modify as needed.

