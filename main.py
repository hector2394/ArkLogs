"""
main.py - Punto de entrada de ARK Raid Monitor
"""

import sys
import os

# Asegurarse de que el directorio del proyecto esté en el path
sys.path.insert(0, os.path.dirname(__file__))

from gui_app import run

if __name__ == "__main__":
    run()
