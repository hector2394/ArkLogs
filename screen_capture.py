"""
screen_capture.py - Captura de pantalla y selector visual de región
"""

import tkinter as tk
from tkinter import messagebox
import mss
import mss.tools
from PIL import Image
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_region(region: dict):
    config = load_config()
    config["capture_region"] = region
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    print(f"[Region] Guardada: {region}")


class RegionSelector:
    """
    Overlay transparente para que el usuario seleccione la región del tribe log
    arrastrando el ratón.
    """

    def __init__(self, parent=None):
        self.start_x = 0
        self.start_y = 0
        self.rect = None
        self.region = None
        self._has_parent = parent is not None

        if self._has_parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-alpha", 0.3)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        self.root.title("Select Tribe Log Region")

        self.canvas = tk.Canvas(
            self.root,
            cursor="crosshair",
            bg="black",
            highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        label = tk.Label(
            self.canvas,
            text="Drag to select the Tribe Log region\nPress ESC to cancel",
            fg="white",
            bg="black",
            font=("Arial", 18, "bold"),
        )
        label.place(relx=0.5, rely=0.05, anchor="center")

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def _on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)

    def _on_drag(self, event):
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x,
            self.start_y,
            event.x,
            event.y,
            outline="red",
            width=2,
            fill="",
        )

    def _on_release(self, event):
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)

        width = x2 - x1
        height = y2 - y1

        if width < 50 or height < 20:
            messagebox.showwarning(
                "Region too small",
                "Please select a larger area.",
                parent=self.root,
            )
            return

        self.region = {"left": x1, "top": y1, "width": width, "height": height}
        self.root.destroy()

    def select(self):
        if self._has_parent:
            self.root.wait_window()
        else:
            self.root.mainloop()
        return self.region


def select_region(parent=None) -> dict:
    """
    Abre el selector visual y devuelve la región seleccionada.
    También la guarda en config.json.
    """
    selector = RegionSelector(parent=parent)
    region = selector.select()

    if region is None:
        print("[Setup] Selección cancelada.")
        return None

    save_region(region)
    return region


def capture_region(region: dict) -> Image.Image:
    """
    Captura la región especificada de la pantalla.
    region = {"left": int, "top": int, "width": int, "height": int}
    Devuelve una imagen PIL.
    """
    with mss.mss() as sct:
        screenshot = sct.grab(region)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
    return img
