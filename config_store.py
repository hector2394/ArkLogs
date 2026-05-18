"""
Shared configuration loading for ARK Raid Monitor.
"""

import copy
import json
import sys
from pathlib import Path


DEFAULT_CONFIG = {
    "check_interval": 5,
    "capture_region": None,
    "mode": "HARD",
    "categories": {
        "raid": True,
        "dinos_killed": True,
        "starving": True,
        "insiding": True,
        "player_killed": True,
    },
    "insiding": {
        "demolition_count": 3,
        "demolition_window_minutes": 2,
        "unclaim_count": 5,
        "unclaim_window_minutes": 2,
    },
    "telegram": {
        "token": "",
        "chat_ids": [],
    },
    "ntfy": {
        "server": "https://ntfy.sh",
        "topic": "",
        "priority": "urgent",
        "token": "",
    },
    "resend_interval": 30,
    "tesseract_path": "",
}


def _runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _bundle_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


CONFIG_PATH = _runtime_dir() / "config.json"
EXAMPLE_CONFIG_PATH = _bundle_dir() / "config.example.json"


def default_config() -> dict:
    if EXAMPLE_CONFIG_PATH.exists():
        try:
            with open(EXAMPLE_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return copy.deepcopy(DEFAULT_CONFIG)


def ensure_config() -> Path:
    if not CONFIG_PATH.exists():
        save_config(default_config())
    return CONFIG_PATH


def load_config() -> dict:
    try:
        with open(ensure_config(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_config()


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
