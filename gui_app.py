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

# Apariencia
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CATEGORY_LABELS = {
    "raid":         ("💥 Raid Alert",     "Estructuras destruidas / demolidas"),
    "dinos_killed": ("🦖 Dinos Killed",   "Tus dinos matados por enemigos"),
    "starving":     ("🍖 Starving Dinos", "Dinos muriendo de hambre"),
    "insiding":     ("🐍 Insiding",       "Demoliciones/unclaims masivos, expulsiones"),
    "player_killed":("💀 Player Killed",  "Jugador de la tribu muerto"),
}

MODE_DESCRIPTIONS = {
    "HARD":     "1 evento = alerta inmediata",
    "MODERATE": "5 eventos acumulados = alerta",
    "SOFT":     "20 eventos acumulados = alerta",
}

MAX_LOG_LINES = 200


def _load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def _save_config(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("⚙ Settings")
        self.geometry("420x500")
        self.resizable(False, False)
        self.grab_set()
        self.focus()

        cfg = _load_config()

        pad = {"padx": 18, "pady": 6}

        ctk.CTkLabel(self, text="⚙  Configuración", font=("Arial", 16, "bold")).pack(pady=(18, 4))

        # Telegram
        ctk.CTkLabel(self, text="Telegram Bot Token", anchor="w").pack(fill="x", **pad)
        self._tg_token = ctk.CTkEntry(self, width=380, placeholder_text="123456:ABCdef...")
        self._tg_token.pack(**pad)
        self._tg_token.insert(0, cfg.get("telegram", {}).get("token", ""))

        ctk.CTkLabel(self, text="Chat IDs (separados por coma)", anchor="w").pack(fill="x", **pad)
        self._chat_ids = ctk.CTkEntry(self, width=380, placeholder_text="123456789, 987654321")
        self._chat_ids.pack(**pad)
        self._chat_ids.insert(0, ", ".join(str(i) for i in cfg.get("telegram", {}).get("chat_ids", [])))

        # ntfy
        ctk.CTkLabel(self, text="ntfy Topic (nombre único para tu tribu)", anchor="w").pack(fill="x", **pad)
        self._ntfy_topic = ctk.CTkEntry(self, width=380, placeholder_text="mi-tribu-ark-2024")
        self._ntfy_topic.pack(**pad)
        self._ntfy_topic.insert(0, cfg.get("ntfy", {}).get("topic", "ark-raid-alert"))

        # Resend interval
        ctk.CTkLabel(self, text="Re-envío si no hay ACK (segundos)", anchor="w").pack(fill="x", **pad)
        self._resend = ctk.CTkEntry(self, width=380)
        self._resend.pack(**pad)
        self._resend.insert(0, str(cfg.get("resend_interval", 30)))

        # Insiding thresholds
        ctk.CTkLabel(self, text="Insiding – Demoliciones para alertar", anchor="w").pack(fill="x", **pad)
        self._demo_count = ctk.CTkEntry(self, width=380)
        self._demo_count.pack(**pad)
        self._demo_count.insert(0, str(cfg.get("insiding", {}).get("demolition_count", 3)))

        ctk.CTkLabel(self, text="Insiding – Ventana de tiempo demoliciones (minutos)", anchor="w").pack(fill="x", **pad)
        self._demo_win = ctk.CTkEntry(self, width=380)
        self._demo_win.pack(**pad)
        self._demo_win.insert(0, str(cfg.get("insiding", {}).get("demolition_window_minutes", 2)))

        # Botones
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=14, padx=18, fill="x")
        ctk.CTkButton(btn_frame, text="Guardar", command=self._save, width=120).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_frame, text="Cancelar", command=self.destroy, width=120,
                      fg_color="gray30", hover_color="gray20").pack(side="right")

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

        self.title("🛡 ARK Raid Monitor v1.0")
        self.geometry("440x600")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._monitor: MonitorThread | None = None
        self._notifier: Notifier | None = None
        self._alert_manager: AlertManager | None = None
        self._bot_started = False
        self._cycle = 0

        self._build_ui()
        self._load_state_from_config()

        # System tray
        self._tray = TrayIcon(
            on_show=self._show_window,
            on_ack_all=self._ack_all,
            on_start_stop=self._toggle_monitor,
            on_quit=self._quit_app,
        )
        self._tray.start()

    # ── UI BUILD ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, height=54, corner_radius=0, fg_color="#1a1a2e")
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header,
            text="🛡  ARK RAID MONITOR",
            font=("Arial", 18, "bold"),
            text_color="#e94560",
        ).pack(side="left", padx=16, pady=12)
        ctk.CTkLabel(
            header, text="v1.0", font=("Arial", 11), text_color="gray50"
        ).pack(side="right", padx=14)

        # Mode selector
        mode_frame = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=10)
        mode_frame.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            mode_frame, text="SENSITIVITY MODE", font=("Arial", 11, "bold"), text_color="gray60"
        ).pack(anchor="w", padx=14, pady=(10, 4))

        self._mode_var = tk.StringVar(value="HARD")
        btn_row = ctk.CTkFrame(mode_frame, fg_color="transparent")
        btn_row.pack(padx=14, pady=(0, 12), fill="x")

        self._mode_buttons: dict[str, ctk.CTkButton] = {}
        for mode, desc in MODE_DESCRIPTIONS.items():
            col = ctk.CTkFrame(btn_row, fg_color="transparent")
            col.pack(side="left", expand=True, fill="x", padx=4)
            btn = ctk.CTkButton(
                col,
                text=mode,
                width=100,
                height=36,
                font=("Arial", 13, "bold"),
                command=lambda m=mode: self._set_mode(m),
            )
            btn.pack(fill="x")
            ctk.CTkLabel(col, text=desc, font=("Arial", 9), text_color="gray50", wraplength=120).pack(pady=(2, 0))
            self._mode_buttons[mode] = btn

        # Category toggles
        cat_frame = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=10)
        cat_frame.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(
            cat_frame, text="ALERT TYPES", font=("Arial", 11, "bold"), text_color="gray60"
        ).pack(anchor="w", padx=14, pady=(10, 6))

        grid = ctk.CTkFrame(cat_frame, fg_color="transparent")
        grid.pack(padx=14, pady=(0, 12), fill="x")
        self._cat_vars: dict[str, tk.BooleanVar] = {}

        cats = list(CATEGORY_LABELS.items())
        for i, (key, (label, tooltip)) in enumerate(cats):
            row = i // 2
            col = i % 2
            var = tk.BooleanVar(value=True)
            self._cat_vars[key] = var
            sw = ctk.CTkSwitch(
                grid,
                text=label,
                variable=var,
                onvalue=True,
                offvalue=False,
                command=lambda k=key, v=var: self._toggle_category(k, v),
                font=("Arial", 12),
            )
            sw.grid(row=row, column=col, sticky="w", padx=8, pady=4)

        # Action buttons
        act_frame = ctk.CTkFrame(self, fg_color="transparent")
        act_frame.pack(fill="x", padx=14, pady=6)

        ctk.CTkButton(
            act_frame,
            text="📷  Select Region",
            command=self._select_region,
            width=150,
            fg_color="#0f3460",
            hover_color="#16213e",
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            act_frame,
            text="⚙  Settings",
            command=self._open_settings,
            width=100,
            fg_color="#0f3460",
            hover_color="#16213e",
        ).pack(side="left")

        ctk.CTkButton(
            act_frame,
            text="✅  ACK All",
            command=self._ack_all,
            width=100,
            fg_color="#1a5c2e",
            hover_color="#0f3c1e",
        ).pack(side="right")

        # Start/Stop button
        self._start_btn = ctk.CTkButton(
            self,
            text="▶  START MONITORING",
            font=("Arial", 14, "bold"),
            height=44,
            fg_color="#e94560",
            hover_color="#c73652",
            command=self._toggle_monitor,
        )
        self._start_btn.pack(fill="x", padx=14, pady=6)

        # Status bar
        status_frame = ctk.CTkFrame(self, fg_color="#0a0a1a", corner_radius=8, height=32)
        status_frame.pack(fill="x", padx=14, pady=(2, 4))
        status_frame.pack_propagate(False)
        self._status_dot = ctk.CTkLabel(status_frame, text="⏹", font=("Arial", 13), text_color="gray50")
        self._status_dot.pack(side="left", padx=(10, 4))
        self._status_label = ctk.CTkLabel(status_frame, text="Inactivo", font=("Arial", 12), text_color="gray60")
        self._status_label.pack(side="left")
        self._alert_badge = ctk.CTkLabel(status_frame, text="", font=("Arial", 11, "bold"), text_color="#e94560")
        self._alert_badge.pack(side="right", padx=10)

        # Log panel
        log_label_row = ctk.CTkFrame(self, fg_color="transparent")
        log_label_row.pack(fill="x", padx=14)
        ctk.CTkLabel(log_label_row, text="LIVE LOG", font=("Arial", 10, "bold"), text_color="gray50").pack(side="left")
        ctk.CTkButton(
            log_label_row, text="Clear", width=48, height=20,
            fg_color="transparent", hover_color="gray20",
            font=("Arial", 10), text_color="gray50",
            command=self._clear_log,
        ).pack(side="right")

        self._log_box = ctk.CTkTextbox(
            self,
            height=180,
            font=("Consolas", 11),
            fg_color="#0a0a1a",
            text_color="#a0c4a0",
            activate_scrollbars=True,
            wrap="word",
        )
        self._log_box.pack(fill="both", expand=True, padx=14, pady=(2, 14))
        self._log_box.configure(state="disabled")

    # ── STATE ────────────────────────────────────────────────────────────────

    def _load_state_from_config(self):
        cfg = _load_config()
        mode = cfg.get("mode", "HARD")
        self._mode_var.set(mode)
        self._refresh_mode_buttons(mode)

        cats = cfg.get("categories", {})
        for key, var in self._cat_vars.items():
            var.set(cats.get(key, True))

    def _set_mode(self, mode: str):
        cfg = _load_config()
        cfg["mode"] = mode
        _save_config(cfg)
        self._mode_var.set(mode)
        self._refresh_mode_buttons(mode)
        if self._monitor:
            self._monitor.reset_detector()
        self._log(f"[Mode] Cambiado a {mode} ({MODE_DESCRIPTIONS[mode]})", color="gray60")

    def _refresh_mode_buttons(self, active: str):
        colors = {
            "HARD":     ("#e94560", "#c73652"),
            "MODERATE": ("#f5a623", "#c4841c"),
            "SOFT":     ("#27ae60", "#1e8449"),
        }
        for mode, btn in self._mode_buttons.items():
            if mode == active:
                c, h = colors[mode]
                btn.configure(fg_color=c, hover_color=h)
            else:
                btn.configure(fg_color="#1e1e3a", hover_color="#2a2a4a")

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
            self._log("[Error] No hay región seleccionada. Pulsa 'Select Region' primero.", color="#e94560")
            return

        if not cfg.get("telegram", {}).get("token"):
            self._log("[Aviso] Token de Telegram no configurado. Ve a Settings.", color="#f5a623")

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

        self._start_btn.configure(text="⏹  STOP MONITORING", fg_color="#555", hover_color="#444")
        self._tray.update_monitoring_state(True)
        self._log("[Monitor] Iniciado. Capturando cada 5s...", color="#27ae60")

    def _stop_monitor(self):
        if self._monitor:
            self._monitor.stop()
            self._monitor = None
        if self._alert_manager:
            self._alert_manager.stop()

        self._start_btn.configure(
            text="▶  START MONITORING", fg_color="#e94560", hover_color="#c73652"
        )
        self._tray.update_monitoring_state(False)
        self._set_status("Detenido", ok=False)
        self._log("[Monitor] Detenido.", color="gray60")

    def _ack_all(self):
        if self._alert_manager:
            count = self._alert_manager.acknowledge_all()
            self._log(f"[ACK] {count} alerta(s) confirmada(s).", color="#27ae60")
            self._update_alert_badge(0)
            self._tray.update_alert_count(0)

    # ── CALLBACKS DEL MONITOR THREAD ─────────────────────────────────────────

    def _on_log_line(self, line: str):
        self.after(0, lambda: self._log(f"> {line}", color="#a0c4a0"))

    def _on_alert(self, alert: Alert):
        def _handle():
            if self._alert_manager:
                self._alert_manager.add_alert(alert)
                count = self._alert_manager.active_count()
                self._update_alert_badge(count)
                self._tray.update_alert_count(count)
                self._tray.notify(
                    f"⚠ ARK - {alert.category.value}",
                    alert.text[:100],
                )
            color_map = {
                "CRITICAL": "#e94560",
                "WARNING": "#f5a623",
            }
            color = color_map.get(alert.severity, "#e94560")
            icon = alert.category_icon()
            self._log(f"{icon} [{alert.severity}] {alert.category.value}: {alert.text}", color=color)
        self.after(0, _handle)

    def _on_status(self, msg: str, ok: bool):
        self.after(0, lambda: self._set_status(msg, ok))

    def _on_cycle(self, cycle: int):
        self._cycle = cycle
        if cycle % 10 == 0:
            self.after(0, lambda: self._set_status(f"Monitorizando... ciclo #{cycle}", ok=True))

    # ── UI HELPERS ────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, ok: bool):
        dot = "🟢" if ok else "⏹"
        color = "#27ae60" if ok else "gray50"
        self._status_dot.configure(text=dot)
        self._status_label.configure(text=msg, text_color=color)

    def _update_alert_badge(self, count: int):
        if count > 0:
            self._alert_badge.configure(text=f"🔴 {count} ALERT(S)")
        else:
            self._alert_badge.configure(text="")

    def _log(self, text: str, color: str = "#a0c4a0"):
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
            self._log(f"[Region] Seleccionada: {region}", color="#27ae60")
        else:
            self._log("[Region] Selección cancelada.", color="gray60")

    def _open_settings(self):
        dialog = SettingsDialog(self)
        self.wait_window(dialog)
        if self._notifier:
            self._notifier.reload_config()
        self._log("[Settings] Configuración guardada.", color="gray60")

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
