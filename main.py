#!/usr/bin/env python3
"""
Flashy - Qualcomm Device Flasher TUI

A terminal user interface for flashing Qualcomm devices using QDL.
"""

from tui import FlashyTUI


def main():
    """Run the Flashy TUI application."""
    app = FlashyTUI()
    app.run()


if __name__ == "__main__":
    main()
