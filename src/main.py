import json
import sys
import tkinter as tk
from pathlib import Path

from services.flight_updater_service import FlightUpdaterService
from view.flight_updater_view import FlightUpdaterApp


def app_root() -> Path:
    """
    Return the application root directory.

    Source mode:
        FlightUpdater/
            src/main.py
            config.json

    PyInstaller mode:
        dist/
            FlightUpdater.exe
            config.json
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[1]


def load_config() -> dict:
    config_path = app_root() / "config.json"

    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    config = load_config()

    root = tk.Tk()
    service = FlightUpdaterService(config)
    app = FlightUpdaterApp(root, service)
    root.mainloop()