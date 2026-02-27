"""
log_parser.py - Parseo del tribe log de ARK y tracking de líneas ya vistas
"""

import re
import json
import os
import hashlib

SEEN_PATH = os.path.join(os.path.dirname(__file__), "seen_lines.json")

# Formato típico ARK tribe log:
# "Day 123, 15:30:45: Your Dino - Lvl 5 was killed by PlayerName!"
# "Day 123, 15:30:45: Your structure Thatch Foundation was destroyed!"
ARK_LOG_PATTERN = re.compile(
    r"Day\s+\d+[,.]?\s*\d{1,2}:\d{2}:\d{2}[:\.]?\s*(.+)",
    re.IGNORECASE,
)


def _load_seen() -> set:
    if not os.path.exists(SEEN_PATH):
        return set()
    try:
        with open(SEEN_PATH, "r") as f:
            data = json.load(f)
        return set(data)
    except Exception:
        return set()


def _save_seen(seen: set):
    # Solo guardamos los últimos 500 hashes para no crecer infinitamente
    seen_list = list(seen)[-500:]
    with open(SEEN_PATH, "w") as f:
        json.dump(seen_list, f)


def _hash_line(line: str) -> str:
    return hashlib.md5(line.strip().lower().encode()).hexdigest()


def parse_new_lines(raw_text: str) -> list[str]:
    """
    Dado el texto OCR extraído, devuelve solo las líneas que son nuevas
    (no vistas en capturas anteriores).

    Las líneas son filtradas para que solo contengan entradas con formato ARK
    o líneas que parezcan eventos del tribe log.
    """
    seen = _load_seen()
    new_lines = []

    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

    for line in lines:
        # Filtrar líneas muy cortas o que claramente son ruido OCR
        if len(line) < 10:
            continue

        h = _hash_line(line)
        if h not in seen:
            seen.add(h)
            new_lines.append(line)

    _save_seen(seen)
    return new_lines


def reset_seen():
    """Limpia el historial de líneas vistas (útil al reiniciar el monitor)."""
    if os.path.exists(SEEN_PATH):
        os.remove(SEEN_PATH)
    print("[Parser] Historial de líneas vistas reiniciado.")
