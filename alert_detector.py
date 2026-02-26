"""
alert_detector.py - Detección de eventos de ataque con categorías, modos y lógica de insiding
"""

import json
import os
import uuid
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

MODE_THRESHOLDS = {
    "HARD": 1,
    "MODERATE": 5,
    "SOFT": 20,
}


class AlertCategory(Enum):
    RAID = "Raid Alert"
    DINOS_KILLED = "Dinos Killed"
    STARVING = "Starving Dinos"
    INSIDING = "Insiding"
    PLAYER_KILLED = "Player Killed"


CATEGORY_KEYWORDS = {
    AlertCategory.RAID: [
        "was destroyed",
        "was demolished",
        "destroyed the",
        "demolished the",
        "enemy destroyed",
        "enemy demolished",
    ],
    AlertCategory.DINOS_KILLED: [
        "was killed by",
        "killed your",
    ],
    AlertCategory.STARVING: [
        "has starved",
        "starved to death",
        "is starving",
        "starved",
    ],
    AlertCategory.PLAYER_KILLED: [
        # Player killed entries in ARK typically mention "was killed by" without "Your"
        "was killed by",
    ],
}

INSIDING_DEMOLISH_KEYWORDS = ["demolished", "demolished the"]
INSIDING_EXPEL_KEYWORDS = [
    "was removed from the tribe",
    "was kicked from",
    "left the tribe",
    "was removed from your tribe",
]
INSIDING_UNCLAIM_KEYWORDS = ["unclaimed"]


@dataclass
class Alert:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    text: str = ""
    category: AlertCategory = AlertCategory.RAID
    severity: str = "CRITICAL"
    timestamp: str = field(
        default_factory=lambda: datetime.now().strftime("%H:%M:%S")
    )
    send_count: int = 0

    def category_icon(self) -> str:
        icons = {
            AlertCategory.RAID: "💥",
            AlertCategory.DINOS_KILLED: "🦖",
            AlertCategory.STARVING: "🍖",
            AlertCategory.INSIDING: "🐍",
            AlertCategory.PLAYER_KILLED: "💀",
        }
        return icons.get(self.category, "🚨")

    def format_message(self) -> str:
        icon = self.category_icon()
        sev_icon = "🚨" if self.severity == "CRITICAL" else "⚠️"
        return (
            f"{sev_icon} *ARK ALERT* - {icon} {self.category.value} {icon}\n"
            f"`[{self.timestamp}]`\n\n"
            f"{self.text}\n\n"
            f"_ID: {self.id} · Envío #{self.send_count + 1}_\n"
            f"Responde /ack para confirmar."
        )

    def format_ntfy_title(self) -> str:
        icon = self.category_icon()
        return f"{icon} ARK - {self.category.value}"

    def format_ntfy_message(self) -> str:
        return f"[{self.timestamp}] {self.text}"


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


class AlertDetector:
    """
    Detecta eventos de ataque en las líneas del tribe log.
    Gestiona el threshold por modo (HARD/MODERATE/SOFT) y la lógica de insiding.
    """

    def __init__(self):
        self._pending_count = 0
        self._pending_alerts: list[Alert] = []
        # Ventanas deslizantes para insiding
        self._demolish_times: deque = deque()
        self._unclaim_times: deque = deque()

    def reset(self):
        """Reinicia contadores (tras enviar alertas o al cambiar modo)."""
        self._pending_count = 0
        self._pending_alerts = []

    def process_lines(self, new_lines: list[str]) -> list[Alert]:
        """
        Procesa nuevas líneas del tribe log.
        Devuelve una lista de alertas SOLO si se ha alcanzado el threshold del modo.
        Las expulsiones de tribu siempre disparan alerta inmediata.
        """
        cfg = _load_config()
        mode = cfg.get("mode", "HARD")
        threshold = MODE_THRESHOLDS.get(mode, 1)
        categories_cfg = cfg.get("categories", {})
        insiding_cfg = cfg.get("insiding", {})

        immediate_alerts = []  # Alertas que ignoran threshold (expulsiones)
        detected = []

        for line in new_lines:
            line_lower = line.lower()

            # --- INSIDING: Expulsión (siempre alerta, ignora threshold) ---
            if categories_cfg.get("insiding", True):
                for kw in INSIDING_EXPEL_KEYWORDS:
                    if kw in line_lower:
                        a = Alert(
                            text=line,
                            category=AlertCategory.INSIDING,
                            severity="CRITICAL",
                        )
                        immediate_alerts.append(a)
                        break

            # --- INSIDING: Demoliciones masivas ---
            if categories_cfg.get("insiding", True):
                for kw in INSIDING_DEMOLISH_KEYWORDS:
                    if kw in line_lower:
                        now = time.time()
                        self._demolish_times.append(now)
                        window = insiding_cfg.get("demolition_window_minutes", 2) * 60
                        count_limit = insiding_cfg.get("demolition_count", 3)
                        # Limpiar entradas fuera de la ventana
                        while self._demolish_times and now - self._demolish_times[0] > window:
                            self._demolish_times.popleft()
                        if len(self._demolish_times) >= count_limit:
                            a = Alert(
                                text=f"[INSIDING] {len(self._demolish_times)} demoliciones en {insiding_cfg.get('demolition_window_minutes', 2)} min: {line}",
                                category=AlertCategory.INSIDING,
                                severity="CRITICAL",
                            )
                            immediate_alerts.append(a)
                            self._demolish_times.clear()
                        break

            # --- INSIDING: Unclaims masivos ---
            if categories_cfg.get("insiding", True):
                for kw in INSIDING_UNCLAIM_KEYWORDS:
                    if kw in line_lower:
                        now = time.time()
                        self._unclaim_times.append(now)
                        window = insiding_cfg.get("unclaim_window_minutes", 2) * 60
                        count_limit = insiding_cfg.get("unclaim_count", 5)
                        while self._unclaim_times and now - self._unclaim_times[0] > window:
                            self._unclaim_times.popleft()
                        if len(self._unclaim_times) >= count_limit:
                            a = Alert(
                                text=f"[INSIDING] {len(self._unclaim_times)} unclaims en {insiding_cfg.get('unclaim_window_minutes', 2)} min",
                                category=AlertCategory.INSIDING,
                                severity="CRITICAL",
                            )
                            immediate_alerts.append(a)
                            self._unclaim_times.clear()
                        break

            # --- RAID ---
            if categories_cfg.get("raid", True):
                for kw in CATEGORY_KEYWORDS[AlertCategory.RAID]:
                    if kw in line_lower:
                        detected.append(Alert(text=line, category=AlertCategory.RAID, severity="CRITICAL"))
                        break

            # --- DINOS KILLED ---
            if categories_cfg.get("dinos_killed", True):
                for kw in CATEGORY_KEYWORDS[AlertCategory.DINOS_KILLED]:
                    if kw in line_lower and "starved" not in line_lower:
                        detected.append(Alert(text=line, category=AlertCategory.DINOS_KILLED, severity="CRITICAL"))
                        break

            # --- STARVING ---
            if categories_cfg.get("starving", True):
                for kw in CATEGORY_KEYWORDS[AlertCategory.STARVING]:
                    if kw in line_lower:
                        detected.append(Alert(text=line, category=AlertCategory.STARVING, severity="WARNING"))
                        break

            # --- PLAYER KILLED ---
            if categories_cfg.get("player_killed", True):
                if "was killed by" in line_lower and "your tribe" in line_lower:
                    detected.append(Alert(text=line, category=AlertCategory.PLAYER_KILLED, severity="CRITICAL"))

        # Acumular en el buffer de pending
        self._pending_alerts.extend(detected)
        self._pending_count += len(detected)

        # Decidir qué devolver
        result = list(immediate_alerts)

        if self._pending_count >= threshold:
            result.extend(self._pending_alerts)
            self.reset()

        return result
