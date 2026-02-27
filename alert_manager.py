"""
alert_manager.py - Gestiona el ciclo de vida de las alertas y los re-envíos
"""

import threading
import time
import json
import os
from alert_detector import Alert

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def _get_resend_interval() -> int:
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = json.load(f)
        return int(cfg.get("resend_interval", 30))
    except Exception:
        return 30


class AlertManager:
    """
    Mantiene el diccionario de alertas activas y lanza un thread de re-envío.
    """

    def __init__(self, notifier):
        self.notifier = notifier
        self._active_alerts: dict[str, Alert] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._resend_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def add_alert(self, alert: Alert):
        """Añade una nueva alerta y la envía inmediatamente."""
        with self._lock:
            self._active_alerts[alert.id] = alert
        self.notifier.send_alert(alert)
        alert.send_count += 1

    def acknowledge_all(self) -> int:
        """Confirma todas las alertas activas. Devuelve el número confirmado."""
        with self._lock:
            count = len(self._active_alerts)
            self._active_alerts.clear()
        return count

    def acknowledge_by_id(self, alert_id: str) -> bool:
        """Confirma una alerta específica por ID."""
        with self._lock:
            if alert_id in self._active_alerts:
                del self._active_alerts[alert_id]
                return True
        return False

    def active_count(self) -> int:
        with self._lock:
            return len(self._active_alerts)

    def get_active_summary(self) -> str:
        with self._lock:
            if not self._active_alerts:
                return "No active alerts."
            lines = [f"Active alerts ({len(self._active_alerts)}):"]
            for a in self._active_alerts.values():
                lines.append(f"  [{a.id}] {a.category.value}: {a.text[:60]}...")
            return "\n".join(lines)

    def _resend_loop(self):
        """Thread background: re-envía alertas no confirmadas cada N segundos."""
        while self._running:
            interval = _get_resend_interval()
            time.sleep(interval)

            with self._lock:
                pending = list(self._active_alerts.values())

            if pending:
                if len(pending) == 1:
                    self.notifier.send_alert(pending[0])
                else:
                    self.notifier.send_resend_summary(pending)
                for alert in pending:
                    alert.send_count += 1
