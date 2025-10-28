# Flashy - TUI alternative to QFIL

Better than poorly designed QFIL which supports only one device at a time. And most importantly TUI > GUI.

## Pre-reqs
1. qdl
2. lsusb
3. Linux (Haven't tested this on windows because getting qdl there is kinda tricky)

## Usage

### 1. Allow flashy to run sudo for qdl and lsusb
Use `visudo` to add a `NOPASSWD` rule. Edit safely and specify full command paths. Example steps and rules:

1. Open sudoers file

```bash
sudo visudo
```

## Run Flashy
```bash
user ALL=(ALL) NOPASSWD: /path/to/qdl, /path/to/lsusb
```
* Security warning: `NOPASSWD` raises privilege risk. Limit to minimal commands and minimal users.

2. Run flashy


```bash
python flashy.py
```

## License

MIT License - Feel free to use and modify as needed.

