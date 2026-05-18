"""
monitor_thread.py - Thread de monitorización desacoplado de la GUI
Ejecuta el loop captura→OCR→parse→detect y notifica a la GUI via callbacks.
"""

import threading
import time

from screen_capture import capture_region
from ocr_engine import extract_text
from log_parser import parse_new_lines
from alert_detector import AlertDetector, Alert
from config_store import load_config


def _load_config() -> dict:
    return load_config()


class MonitorThread(threading.Thread):
    """
    Thread de monitorización. Callbacks para comunicarse con la GUI:
      on_log_line(line: str)          — nueva línea detectada en el log
      on_alert(alert: Alert)          — alerta disparada
      on_status(msg: str, ok: bool)   — mensaje de estado (ok=True verde, False rojo)
      on_cycle(cycle: int)            — número de ciclo completado
    """

    def __init__(self, on_log_line=None, on_alert=None, on_status=None, on_cycle=None):
        super().__init__(daemon=True)
        self.on_log_line = on_log_line or (lambda line: None)
        self.on_alert = on_alert or (lambda alert: None)
        self.on_status = on_status or (lambda msg, ok: None)
        self.on_cycle = on_cycle or (lambda n: None)
        self._running = False
        self._detector = AlertDetector()

    def run(self):
        self._running = True
        cycle = 0

        cfg = _load_config()
        region = cfg.get("capture_region")

        if not region:
            self.on_status("ERROR: No hay región seleccionada", False)
            return

        self.on_status("Monitorizando...", True)

        while self._running:
            cfg = _load_config()
            interval = cfg.get("check_interval", 5)
            region = cfg.get("capture_region")

            if not region:
                self.on_status("ERROR: Región no configurada", False)
                time.sleep(interval)
                continue

            try:
                image = capture_region(region)
                raw_text = extract_text(image)
                new_lines = parse_new_lines(raw_text)

                cycle += 1
                self.on_cycle(cycle)

                for line in new_lines:
                    self.on_log_line(line)

                alerts = self._detector.process_lines(new_lines)
                for alert in alerts:
                    self.on_alert(alert)

            except Exception as e:
                self.on_status(f"Error: {e}", False)

            time.sleep(interval)

        self.on_status("Detenido", False)

    def stop(self):
        self._running = False

    def reset_detector(self):
        """Reinicia el contador de eventos pendientes (útil al cambiar de modo)."""
        self._detector.reset()
