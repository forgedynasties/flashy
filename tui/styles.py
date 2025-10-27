"""CSS styles for the Flashy TUI."""

CSS = """
Screen {
    layout: grid;
    grid-size: 2 3;
    grid-rows: 1fr 3 2fr;
}

#devices-panel {
    column-span: 1;
    row-span: 1;
    border: solid $accent;
    height: 100%;
}

#firmware-panel {
    column-span: 1;
    row-span: 1;
    border: solid $accent;
    height: 100%;
}

#firmware-info {
    column-span: 2;
    row-span: 1;
    border: solid $accent;
    height: 100%;
    padding: 0 1;
}

#log-panel {
    column-span: 2;
    row-span: 1;
    border: solid $accent;
    height: 100%;
}

#status-bar {
    dock: bottom;
    height: 3;
    background: $boost;
    color: $text;
    padding: 1;
}

.panel-title {
    background: $accent;
    color: $text;
    padding: 0 1;
    text-align: center;
    text-style: bold;
}

DataTable {
    height: 1fr;
}

DirectoryTree {
    height: 1fr;
}

Log {
    height: 1fr;
}

#confirm-dialog {
    align: center middle;
    background: $surface;
    border: thick $primary;
    width: 60;
    height: 15;
    padding: 1;
}

#confirm-message {
    width: 100%;
    height: auto;
    content-align: center middle;
}

.button-row {
    align: center middle;
    width: 100%;
    height: auto;
    margin-top: 1;
}

.button-row Button {
    margin: 0 1;
}

.info-label {
    padding: 0 1;
    color: $text;
}
"""
