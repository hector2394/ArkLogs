"""
test_ocr.py - Herramienta de prueba del OCR
Toma un screenshot manual de la región configurada y muestra el texto extraído.

Uso:
  python test_ocr.py           - Usa la región guardada en config.json
  python test_ocr.py --select  - Te permite seleccionar una nueva región primero
"""

import sys
import json
import os
from screen_capture import capture_region, select_region
from ocr_engine import extract_text
from alert_detector import detect_alerts
from log_parser import parse_new_lines

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def main():
    print("=== ArkLogs - Test de OCR ===\n")

    with open(CONFIG_PATH, "r") as f:
        cfg = json.load(f)

    if "--select" in sys.argv or not cfg.get("capture_region"):
        print("Selecciona la región del tribe log...")
        region = select_region()
        if not region:
            print("Cancelado.")
            return
    else:
        region = cfg["capture_region"]

    print(f"Región: {region}")
    print("Capturando pantalla...")

    image = capture_region(region)
    image.save("test_capture.png")
    print("Imagen guardada en: test_capture.png")

    print("\nEjecutando OCR...")
    raw_text = extract_text(image)

    print("\n--- TEXTO EXTRAÍDO ---")
    print(raw_text if raw_text else "(sin texto detectado)")
    print("---------------------\n")

    if raw_text:
        new_lines = parse_new_lines(raw_text)
        print(f"Líneas reconocidas: {len(new_lines)}")
        for line in new_lines:
            print(f"  > {line}")

        print()
        alerts = detect_alerts(new_lines)
        if alerts:
            print(f"⚠️  ALERTAS DETECTADAS: {len(alerts)}")
            for a in alerts:
                print(f"  [{a.severity}] {a.text}")
        else:
            print("✅ No se detectaron alertas de raid en el texto.")
    else:
        print("No se detectó texto. Posibles causas:")
        print("  - Tesseract no está instalado o la ruta es incorrecta")
        print("  - La región seleccionada no contiene texto legible")
        print("  - El tribe log no está visible en pantalla")
        print("\nComprueba la imagen guardada en test_capture.png")


if __name__ == "__main__":
    main()
