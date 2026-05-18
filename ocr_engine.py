"""
ocr_engine.py - Extracción de texto de capturas de pantalla usando Tesseract OCR
"""

import pytesseract
from PIL import Image, ImageFilter, ImageEnhance
import os
from config_store import load_config


def _load_tesseract_path():
    try:
        cfg = load_config()
        path = cfg.get("tesseract_path", "")
        if path and os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
    except Exception:
        pass


_load_tesseract_path()


def _preprocess(image: Image.Image) -> Image.Image:
    """
    Preprocesa la imagen para mejorar el reconocimiento OCR.
    El tribe log de ARK tiene texto blanco/coloreado sobre fondo oscuro.
    """
    # Escalar 2x para mejor precisión OCR
    w, h = image.size
    image = image.resize((w * 2, h * 2), Image.LANCZOS)

    # Escala de grises
    image = image.convert("L")

    # Aumentar contraste
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.5)

    # Aumentar brillo ligeramente
    enhancer = ImageEnhance.Brightness(image)
    image = enhancer.enhance(1.3)

    # Binarizar: texto claro sobre fondo oscuro → invertir para Tesseract
    # Tesseract funciona mejor con texto negro sobre fondo blanco
    image = image.point(lambda x: 255 if x > 100 else 0)

    return image


def extract_text(image: Image.Image) -> str:
    """
    Extrae el texto de una imagen PIL preprocesada.
    Devuelve el texto como string, líneas separadas por \\n.
    """
    processed = _preprocess(image)

    config = "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 !.,:-_'\"()[]{}/@#%&*+<>?;"

    text = pytesseract.image_to_string(processed, config=config, lang="eng")
    return text.strip()
