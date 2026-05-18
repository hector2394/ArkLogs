# ARK Raid Monitor

ARK Raid Monitor is a Windows desktop tool that watches your ARK tribe log through screen capture and OCR, detects dangerous events, and sends alerts through Telegram and ntfy.

It is designed for players who keep the tribe log visible and want a lightweight warning system for raids, killed tames, starving dinos, suspicious tribe activity, and player deaths.

## Features

- Real-time OCR monitoring of a selected screen region.
- Alert categories for raids, dinos killed, starving dinos, possible insiding, and tribe member deaths.
- Sensitivity modes:
  - `HARD`: alert after 1 matching event.
  - `MODERATE`: alert after 5 matching events.
  - `SOFT`: alert after 20 matching events.
- Telegram notifications with `/ack`, `/status`, `/test`, and dismiss buttons.
- ntfy.sh push notifications.
- Repeated reminders until active alerts are acknowledged.
- CustomTkinter desktop UI with system tray support.
- Visual region selector for choosing the tribe log area.

## Requirements

- Windows.
- Python 3.11.
- Tesseract OCR installed locally.
- ARK running with the tribe log visible on screen.
- Optional: a Telegram bot token and chat ID.
- Optional: an ntfy topic, and token if using a private ntfy server/topic.

Install Tesseract OCR from the official installer or your preferred package source, then set `tesseract_path` in `config.json` if it is not available on your system path.

## Installation

Clone the repository and create a virtual environment:

```powershell
git clone https://github.com/hectorjimenezpalomo/ArkLogs.git
cd ArkLogs
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Create your local configuration:

```powershell
copy config.example.json config.json
```

Edit `config.json` and add your own values:

- `telegram.token`: your Telegram bot token.
- `telegram.chat_ids`: one or more Telegram chat IDs.
- `ntfy.topic`: your ntfy topic name.
- `ntfy.token`: optional token for private ntfy topics.
- `tesseract_path`: optional full path to `tesseract.exe`.

`config.json` is intentionally ignored by Git because it can contain private credentials and local screen coordinates.

## Running

Start the app:

```powershell
python main.py
```

In the app:

1. Click **Select Region** and drag over the ARK tribe log.
2. Open **Settings** and configure notifications.
3. Choose a sensitivity mode and alert categories.
4. Click **Start Monitoring**.

The app captures the selected screen region, extracts text with Tesseract, filters new log lines, detects alerts, and sends notifications.

## Testing

Send test notifications:

```powershell
python test_notify.py once
```

Test OCR with the configured region:

```powershell
python test_ocr.py
```

Select a new OCR region before testing:

```powershell
python test_ocr.py --select
```

## Building An Executable

Install dependencies, ensure `config.example.json` exists, then run:

```powershell
pyinstaller build.spec
```

The generated executable is written to `dist/`. The build includes the safe example config, not your private `config.json`.

When distributing the executable, users should keep their own `config.json` next to the executable. If it is missing, the app creates one from the bundled defaults.

## Security Notes

Never commit `config.json`. It may contain Telegram bot tokens, chat IDs, ntfy tokens, local screen coordinates, and machine-specific paths.

If a real token was ever committed, revoke or rotate it before making the repository public. Removing the file from the latest commit is not enough if the token still exists in Git history.

Before publishing this repository, inspect tracked files for secrets:

```powershell
git grep -n "token\|chat_id\|ntfy\|tesseract_path"
```

If secrets exist in history, clean the history with a tool such as `git filter-repo` or BFG Repo-Cleaner, then force-push only after confirming the rewritten history is correct.

## Project Structure

- `main.py`: application entrypoint.
- `gui_app.py`: CustomTkinter desktop UI.
- `monitor_thread.py`: capture, OCR, parse, detect loop.
- `screen_capture.py`: screenshot capture and region selector.
- `ocr_engine.py`: Tesseract preprocessing and text extraction.
- `log_parser.py`: new-line tracking for OCR output.
- `alert_detector.py`: alert categories, thresholds, and insiding detection.
- `alert_manager.py`: active alerts and resend loop.
- `notifier.py`: Telegram and ntfy delivery.
- `tray_icon.py`: Windows system tray integration.
- `config.example.json`: safe public configuration template.

## License

No license has been declared yet. Add one before accepting external contributions or distributing public releases.
