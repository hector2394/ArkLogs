"""
gui_app.py - Ventana principal de ARK Raid Monitor (customtkinter)
"""

import json
import os
import threading
import tkinter as tk
from datetime import datetime

import customtkinter as ctk

from alert_detector import Alert, AlertCategory
from alert_manager import AlertManager
from monitor_thread import MonitorThread
from notifier import Notifier, start_telegram_bot
from screen_capture import select_region
from tray_icon import TrayIcon

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Paleta de colores ─────────────────────────────────────────────────────────
C = {
    "bg":          "#0d1117",
    "surface":     "#161b22",
    "surface2":    "#21262d",
    "border":      "#30363d",
    "text":        "#e6edf3",
    "muted":       "#7d8590",
    "red":         "#f85149",
    "red_dk":      "#da3633",
    "orange":      "#e3b341",
    "orange_dk":   "#bb8009",
    "green":       "#3fb950",
    "green_dk":    "#2ea043",
    "blue":        "#388bfd",
    "blue_dk":     "#1f6feb",
    "purple":      "#bc8cff",
}

CATEGORY_DATA = {
    "raid":         ("💥", "Raid Alert",     "Estructuras destruidas o demolidas"),
    "dinos_killed": ("🦖", "Dinos Killed",   "Tus dinos matados por enemigos"),
    "starving":     ("🍖", "Starving Dinos", "Dinos muriendo de hambre"),
    "insiding":     ("🐍", "Insiding",       "Demoliciones/unclaims masivos, expulsiones"),
    "player_killed":("💀", "Player Killed",  "Jugador de la tribu eliminado"),
}

MODE_DATA = {
    "HARD":     ("🔴", "HARD",     "1 evento",  "Alerta inmediata"),
    "MODERATE": ("🟡", "MODERATE", "5 eventos", "Acumulado medio"),
    "SOFT":     ("🟢", "SOFT",     "20 eventos","Solo raids serios"),
}

MAX_LOG_LINES = 200


def _load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def _save_config(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def _section_label(parent, text: str):
    """Etiqueta de sección estilo uppercase muted."""
    ctk.CTkLabel(
        parent, text=text,
        font=("Arial", 10, "bold"),
        text_color=C["muted"],
        anchor="w",
    ).pack(fill="x", padx=16, pady=(14, 4))


def _divider(parent):
    ctk.CTkFrame(parent, height=1, fg_color=C["border"]).pack(fill="x", padx=0, pady=0)


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("460x560")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self.grab_set()
        self.focus()

        cfg = _load_config()

        # ── Header ──
        hdr = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="⚙  Settings", font=("Arial", 15, "bold"),
                     text_color=C["text"]).pack(side="left", padx=18)

        scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"], scrollbar_button_color=C["surface2"])
        scroll.pack(fill="both", expand=True, padx=0, pady=0)

        def field(label, placeholder, value, show=""):
            _section_label(scroll, label)
            e = ctk.CTkEntry(
                scroll, placeholder_text=placeholder,
                fg_color=C["surface"], border_color=C["border"],
                text_color=C["text"], placeholder_text_color=C["muted"],
                height=36, show=show,
            )
            e.pack(fill="x", padx=16, pady=(0, 2))
            if value:
                e.insert(0, value)
            return e

        # Telegram
        _section_label(scroll, "  TELEGRAM")
        ctk.CTkFrame(scroll, height=1, fg_color=C["border"]).pack(fill="x", padx=16)

        self._tg_token = field(
            "Bot Token",
            "123456789:ABCdefGhIjKlMnOpQrSt...",
            cfg.get("telegram", {}).get("token", ""),
        )
        self._chat_ids = field(
            "Chat IDs  (separados por coma)",
            "123456789, 987654321",
            ", ".join(str(i) for i in cfg.get("telegram", {}).get("chat_ids", [])),
        )

        # ntfy
        _section_label(scroll, "  NTFY.SH")
        ctk.CTkFrame(scroll, height=1, fg_color=C["border"]).pack(fill="x", padx=16)

        self._ntfy_topic = field(
            "Topic  (nombre único para tu tribu)",
            "mi-tribu-ark-2024",
            cfg.get("ntfy", {}).get("topic", "ark-raid-alert"),
        )

        # Timing
        _section_label(scroll, "  TIMING")
        ctk.CTkFrame(scroll, height=1, fg_color=C["border"]).pack(fill="x", padx=16)

        self._resend = field(
            "Re-envío sin ACK (segundos)",
            "30",
            str(cfg.get("resend_interval", 30)),
        )

        # Insiding
        _section_label(scroll, "  INSIDING THRESHOLDS")
        ctk.CTkFrame(scroll, height=1, fg_color=C["border"]).pack(fill="x", padx=16)

        row2 = ctk.CTkFrame(scroll, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(4, 0))

        for label, val, attr in [
            ("Demoliciones para alertar", str(cfg.get("insiding", {}).get("demolition_count", 3)), "_demo_count"),
            ("Ventana (minutos)",         str(cfg.get("insiding", {}).get("demolition_window_minutes", 2)), "_demo_win"),
        ]:
            col = ctk.CTkFrame(row2, fg_color="transparent")
            col.pack(side="left", expand=True, fill="x", padx=(0, 8))
            ctk.CTkLabel(col, text=label, font=("Arial", 11), text_color=C["muted"], anchor="w").pack(fill="x")
            e = ctk.CTkEntry(col, fg_color=C["surface"], border_color=C["border"],
                             text_color=C["text"], height=34)
            e.pack(fill="x")
            e.insert(0, val)
            setattr(self, attr, e)

        # Botones
        foot = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=56)
        foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)
        ctk.CTkButton(
            foot, text="Guardar", command=self._save,
            fg_color=C["blue"], hover_color=C["blue_dk"],
            font=("Arial", 13, "bold"), width=120, height=36,
        ).pack(side="right", padx=12, pady=10)
        ctk.CTkButton(
            foot, text="Cancelar", command=self.destroy,
            fg_color=C["surface2"], hover_color=C["border"],
            text_color=C["muted"], width=100, height=36,
        ).pack(side="right", pady=10)

    def _save(self):
        cfg = _load_config()
        cfg["telegram"]["token"] = self._tg_token.get().strip()
        ids_raw = self._chat_ids.get().strip()
        cfg["telegram"]["chat_ids"] = [x.strip() for x in ids_raw.split(",") if x.strip()]
        cfg["ntfy"]["topic"] = self._ntfy_topic.get().strip()
        try:
            cfg["resend_interval"] = int(self._resend.get().strip())
        except ValueError:
            pass
        try:
            cfg["insiding"]["demolition_count"] = int(self._demo_count.get().strip())
            cfg["insiding"]["demolition_window_minutes"] = int(self._demo_win.get().strip())
        except ValueError:
            pass
        _save_config(cfg)
        self.destroy()


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ARK Raid Monitor")
        self.geometry("460x700")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._monitor: MonitorThread | None = None
        self._notifier: Notifier | None = None
        self._alert_manager: AlertManager | None = None
        self._bot_started = False
        self._cycle = 0

        self._build_ui()
        self._load_state_from_config()

        self._tray = TrayIcon(
            on_show=self._show_window,
            on_ack_all=self._ack_all,
            on_start_stop=self._toggle_monitor,
            on_quit=self._quit_app,
        )
        self._tray.start()

    # ── UI BUILD ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_mode_section()
        self._build_category_section()
        self._build_action_bar()
        self._build_start_button()
        self._build_status_bar()
        self._build_log_section()

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=68)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", padx=18, pady=10)

        ctk.CTkLabel(
            left, text="🛡  ARK RAID MONITOR",
            font=("Arial", 20, "bold"), text_color=C["red"], anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            left, text="Real-time tribe log alert system",
            font=("Arial", 11), text_color=C["muted"], anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            hdr, text="v1.0",
            font=("Arial", 10), text_color=C["muted"],
        ).pack(side="right", padx=16)

        ctk.CTkFrame(self, height=1, fg_color=C["border"], corner_radius=0).pack(fill="x")

    def _build_mode_section(self):
        _section_label(self, "  SENSITIVITY MODE")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 6))

        self._mode_buttons: dict[str, ctk.CTkFrame] = {}
        self._mode_btn_widgets: dict[str, ctk.CTkButton] = {}

        for mode, (dot, name, threshold, desc) in MODE_DATA.items():
            card = ctk.CTkFrame(
                row, fg_color=C["surface"], corner_radius=10,
                border_width=2, border_color=C["border"],
            )
            card.pack(side="left", expand=True, fill="x", padx=5)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(padx=12, pady=10, fill="x")

            ctk.CTkLabel(inner, text=dot, font=("Arial", 22)).pack(anchor="w")
            ctk.CTkLabel(inner, text=name, font=("Arial", 13, "bold"),
                         text_color=C["text"]).pack(anchor="w", pady=(2, 0))
            ctk.CTkLabel(inner, text=threshold, font=("Arial", 11, "bold"),
                         text_color=C["muted"]).pack(anchor="w")
            ctk.CTkLabel(inner, text=desc, font=("Arial", 10),
                         text_color=C["muted"], wraplength=120).pack(anchor="w", pady=(2, 4))

            btn = ctk.CTkButton(
                inner, text="Select",
                height=28, font=("Arial", 11, "bold"),
                fg_color=C["surface2"], hover_color=C["border"],
                text_color=C["muted"],
                command=lambda m=mode: self._set_mode(m),
            )
            btn.pack(fill="x")

            self._mode_buttons[mode] = card
            self._mode_btn_widgets[mode] = btn

    def _build_category_section(self):
        _section_label(self, "  ALERT TYPES")

        outer = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=10,
                             border_width=1, border_color=C["border"])
        outer.pack(fill="x", padx=14, pady=(0, 6))

        self._cat_vars: dict[str, tk.BooleanVar] = {}
        cats = list(CATEGORY_DATA.items())

        for i, (key, (icon, label, desc)) in enumerate(cats):
            var = tk.BooleanVar(value=True)
            self._cat_vars[key] = var

            row = ctk.CTkFrame(outer, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=1)

            # Icono + textos
            ctk.CTkLabel(row, text=icon, font=("Arial", 18), width=30).pack(side="left")
            txt = ctk.CTkFrame(row, fg_color="transparent")
            txt.pack(side="left", padx=8, expand=True, fill="x")
            ctk.CTkLabel(txt, text=label, font=("Arial", 12, "bold"),
                         text_color=C["text"], anchor="w").pack(anchor="w")
            ctk.CTkLabel(txt, text=desc, font=("Arial", 10),
                         text_color=C["muted"], anchor="w").pack(anchor="w")

            ctk.CTkSwitch(
                row, text="", variable=var, width=46,
                onvalue=True, offvalue=False,
                progress_color=C["green"],
                command=lambda k=key, v=var: self._toggle_category(k, v),
            ).pack(side="right")

            # Divisor entre filas (excepto la última)
            if i < len(cats) - 1:
                ctk.CTkFrame(outer, height=1, fg_color=C["border"]).pack(fill="x", padx=14)

    def _build_action_bar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=14, pady=(6, 4))

        ctk.CTkButton(
            bar, text="📷  Select Region",
            fg_color=C["surface"], hover_color=C["surface2"],
            border_width=1, border_color=C["border"],
            text_color=C["text"], font=("Arial", 12),
            height=34, width=160,
            command=self._select_region,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            bar, text="⚙  Settings",
            fg_color=C["surface"], hover_color=C["surface2"],
            border_width=1, border_color=C["border"],
            text_color=C["text"], font=("Arial", 12),
            height=34, width=110,
            command=self._open_settings,
        ).pack(side="left")

        ctk.CTkButton(
            bar, text="✅  ACK All",
            fg_color=C["green_dk"], hover_color=C["green"],
            text_color="#000", font=("Arial", 12, "bold"),
            height=34, width=110,
            command=self._ack_all,
        ).pack(side="right")

    def _build_start_button(self):
        self._start_btn = ctk.CTkButton(
            self,
            text="▶   START MONITORING",
            font=("Arial", 15, "bold"),
            height=48,
            fg_color=C["red"],
            hover_color=C["red_dk"],
            corner_radius=10,
            command=self._toggle_monitor,
        )
        self._start_btn.pack(fill="x", padx=14, pady=(4, 6))

    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=8,
                           border_width=1, border_color=C["border"], height=34)
        bar.pack(fill="x", padx=14, pady=(0, 4))
        bar.pack_propagate(False)

        self._status_dot = ctk.CTkLabel(bar, text="●", font=("Arial", 14), text_color=C["muted"])
        self._status_dot.pack(side="left", padx=(12, 4))

        self._status_label = ctk.CTkLabel(bar, text="Inactivo",
                                          font=("Arial", 12), text_color=C["muted"])
        self._status_label.pack(side="left")

        self._alert_badge = ctk.CTkLabel(bar, text="", font=("Arial", 11, "bold"), text_color=C["red"])
        self._alert_badge.pack(side="right", padx=12)

    def _build_log_section(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(2, 0))

        ctk.CTkLabel(hdr, text="LIVE LOG", font=("Arial", 10, "bold"),
                     text_color=C["muted"]).pack(side="left")
        ctk.CTkButton(
            hdr, text="Clear", width=44, height=18,
            fg_color="transparent", hover_color=C["surface2"],
            font=("Arial", 10), text_color=C["muted"],
            command=self._clear_log,
        ).pack(side="right")

        self._log_box = ctk.CTkTextbox(
            self, height=160,
            font=("Consolas", 11),
            fg_color=C["surface"],
            border_width=1, border_color=C["border"],
            text_color="#8b949e",
            corner_radius=8,
            activate_scrollbars=True,
            wrap="word",
        )
        self._log_box.pack(fill="both", expand=True, padx=14, pady=(2, 14))
        self._log_box.configure(state="disabled")

    # ── STATE ────────────────────────────────────────────────────────────────

    def _load_state_from_config(self):
        cfg = _load_config()
        mode = cfg.get("mode", "HARD")
        self._refresh_mode_buttons(mode)

        cats = cfg.get("categories", {})
        for key, var in self._cat_vars.items():
            var.set(cats.get(key, True))

    def _set_mode(self, mode: str):
        cfg = _load_config()
        cfg["mode"] = mode
        _save_config(cfg)
        self._refresh_mode_buttons(mode)
        if self._monitor:
            self._monitor.reset_detector()
        _, _, threshold, desc = MODE_DATA[mode]
        self._log(f"[Mode] → {mode}  ({threshold} · {desc})", color=C["muted"])

    def _refresh_mode_buttons(self, active: str):
        border_colors = {
            "HARD":     C["red"],
            "MODERATE": C["orange"],
            "SOFT":     C["green"],
        }
        btn_colors = {
            "HARD":     (C["red"],    C["red_dk"],    "#fff"),
            "MODERATE": (C["orange"], C["orange_dk"], "#000"),
            "SOFT":     (C["green"],  C["green_dk"],  "#000"),
        }
        for mode, card in self._mode_buttons.items():
            btn = self._mode_btn_widgets[mode]
            if mode == active:
                card.configure(border_color=border_colors[mode])
                fg, hv, tc = btn_colors[mode]
                btn.configure(fg_color=fg, hover_color=hv, text_color=tc, text="✓ Selected")
            else:
                card.configure(border_color=C["border"])
                btn.configure(fg_color=C["surface2"], hover_color=C["border"],
                              text_color=C["muted"], text="Select")

    def _toggle_category(self, key: str, var: tk.BooleanVar):
        cfg = _load_config()
        cfg["categories"][key] = var.get()
        _save_config(cfg)

    # ── MONITOR CONTROL ───────────────────────────────────────────────────────

    def _toggle_monitor(self):
        if self._monitor and self._monitor.is_alive():
            self._stop_monitor()
        else:
            self._start_monitor()

    def _start_monitor(self):
        cfg = _load_config()

        if not cfg.get("capture_region"):
            self._log("[Error] No hay región seleccionada. Pulsa 'Select Region' primero.", color=C["red"])
            return

        if not cfg.get("telegram", {}).get("token"):
            self._log("[Aviso] Token de Telegram no configurado. Ve a Settings.", color=C["orange"])

        # Inicializar notifier y alert manager
        self._notifier = Notifier()
        self._alert_manager = AlertManager(self._notifier)
        self._notifier.set_alert_manager(self._alert_manager)
        self._alert_manager.start()

        # Iniciar bot de Telegram una sola vez
        if not self._bot_started and cfg.get("telegram", {}).get("token"):
            threading.Thread(
                target=start_telegram_bot,
                args=(self._notifier, self._alert_manager),
                daemon=True,
            ).start()
            self._bot_started = True

        self._monitor = MonitorThread(
            on_log_line=self._on_log_line,
            on_alert=self._on_alert,
            on_status=self._on_status,
            on_cycle=self._on_cycle,
        )
        self._monitor.start()

        self._start_btn.configure(text="⏹   STOP MONITORING", fg_color=C["surface2"], hover_color=C["border"])
        self._tray.update_monitoring_state(True)
        self._log("[Monitor] Iniciado. Capturando cada 5s...", color=C["green"])

    def _stop_monitor(self):
        if self._monitor:
            self._monitor.stop()
            self._monitor = None
        if self._alert_manager:
            self._alert_manager.stop()

        self._start_btn.configure(
            text="▶   START MONITORING", fg_color=C["red"], hover_color=C["red_dk"]
        )
        self._tray.update_monitoring_state(False)
        self._set_status("Detenido", ok=False)
        self._log("[Monitor] Detenido.", color=C["muted"])

    def _ack_all(self):
        if self._alert_manager:
            count = self._alert_manager.acknowledge_all()
            self._log(f"[ACK] {count} alerta(s) confirmada(s).", color=C["green"])
            self._update_alert_badge(0)
            self._tray.update_alert_count(0)

    # ── CALLBACKS DEL MONITOR THREAD ─────────────────────────────────────────

    def _on_log_line(self, line: str):
        self.after(0, lambda: self._log(f"  {line}"))

    def _on_alert(self, alert: Alert):
        def _handle():
            if self._alert_manager:
                self._alert_manager.add_alert(alert)
                count = self._alert_manager.active_count()
                self._update_alert_badge(count)
                self._tray.update_alert_count(count)
                self._tray.notify(
                    f"ARK — {alert.category.value}",
                    alert.text[:100],
                )
            color = C["red"] if alert.severity == "CRITICAL" else C["orange"]
            icon = alert.category_icon()
            self._log(f"{icon}  {alert.category.value.upper()}  ·  {alert.text}", color=color)
        self.after(0, _handle)

    def _on_status(self, msg: str, ok: bool):
        self.after(0, lambda: self._set_status(msg, ok))

    def _on_cycle(self, cycle: int):
        self._cycle = cycle
        self.after(0, lambda: self._set_status(f"Monitoring  ·  cycle #{cycle}", ok=True))

    # ── UI HELPERS ────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, ok: bool):
        color = C["green"] if ok else C["muted"]
        self._status_dot.configure(text_color=color)
        self._status_label.configure(text=msg, text_color=color)

    def _update_alert_badge(self, count: int):
        if count > 0:
            self._alert_badge.configure(text=f"⚠  {count} UNACK")
        else:
            self._alert_badge.configure(text="")

    def _log(self, text: str, color: str = "#8b949e"):
        def _insert():
            self._log_box.configure(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self._log_box.insert("end", f"[{ts}] {text}\n")
            # Limitar líneas
            content = self._log_box.get("1.0", "end").splitlines()
            if len(content) > MAX_LOG_LINES:
                self._log_box.delete("1.0", f"{len(content) - MAX_LOG_LINES}.0")
            self._log_box.see("end")
            self._log_box.configure(state="disabled")
        self.after(0, _insert)

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    # ── ACTIONS ───────────────────────────────────────────────────────────────

    def _select_region(self):
        self.withdraw()
        self.after(300, self._do_select_region)

    def _do_select_region(self):
        region = select_region()
        self.deiconify()
        if region:
            self._log(f"[Region] Seleccionada: {region}", color=C["green"])
        else:
            self._log("[Region] Selección cancelada.", color=C["muted"])

    def _open_settings(self):
        dialog = SettingsDialog(self)
        self.wait_window(dialog)
        if self._notifier:
            self._notifier.reload_config()
        self._log("[Settings] Configuración guardada.", color=C["muted"])

    # ── WINDOW / TRAY ─────────────────────────────────────────────────────────

    def _on_close(self):
        """Al cerrar la ventana, minimizar a la bandeja en lugar de cerrar."""
        self.withdraw()

    def _show_window(self):
        self.after(0, self.deiconify)
        self.after(0, self.focus_force)

    def _quit_app(self):
        self._stop_monitor()
        self._tray.stop()
        self.after(0, self.destroy)


def run():
    app = MainWindow()
    app.mainloop()
