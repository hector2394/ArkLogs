"""
tray_icon.py - Bandeja del sistema (system tray) para Windows
"""

import threading
import os

try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False


def _make_icon_image(has_alert: bool = False) -> "Image.Image":
    """
    Genera un icono simple 64x64 en memoria.
    Verde = OK, Rojo = alerta activa.
    """
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Fondo circular
    color = (220, 50, 50, 255) if has_alert else (40, 180, 80, 255)
    draw.ellipse([4, 4, size - 4, size - 4], fill=color)

    # Escudo simplificado (triángulo + líneas)
    shield_color = (255, 255, 255, 230)
    cx = size // 2
    # Cuerpo del escudo
    draw.polygon(
        [(cx, 12), (cx + 18, 22), (cx + 18, 40), (cx, 52), (cx - 18, 40), (cx - 18, 22)],
        fill=shield_color,
    )
    # Interior oscuro
    inner = (color[0] - 20, color[1] - 20, color[2] - 20, 200)
    draw.polygon(
        [(cx, 18), (cx + 12, 26), (cx + 12, 38), (cx, 46), (cx - 12, 38), (cx - 12, 26)],
        fill=inner,
    )

    return img


ICON_NORMAL = None
ICON_ALERT = None


def _get_icon(has_alert: bool):
    global ICON_NORMAL, ICON_ALERT

    # Intentar cargar desde archivo primero
    assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    icon_path = os.path.join(assets_dir, "icon_alert.ico" if has_alert else "icon.ico")
    if os.path.exists(icon_path):
        return Image.open(icon_path)

    # Generar en memoria
    if has_alert:
        if ICON_ALERT is None:
            ICON_ALERT = _make_icon_image(has_alert=True)
        return ICON_ALERT
    else:
        if ICON_NORMAL is None:
            ICON_NORMAL = _make_icon_image(has_alert=False)
        return ICON_NORMAL


class TrayIcon:
    """
    Icono en la bandeja del sistema con menú contextual.
    """

    def __init__(self, on_show, on_ack_all, on_start_stop, on_quit):
        self._on_show = on_show
        self._on_ack_all = on_ack_all
        self._on_start_stop = on_start_stop
        self._on_quit = on_quit
        self._icon: "pystray.Icon | None" = None
        self._thread: threading.Thread | None = None
        self._is_monitoring = False
        self._alert_count = 0

    def _build_menu(self):
        monitor_label = "⏹ Detener monitor" if self._is_monitoring else "▶ Iniciar monitor"
        return pystray.Menu(
            item("🛡 ARK Raid Monitor", self._on_show, default=True),
            pystray.Menu.SEPARATOR,
            item(monitor_label, self._toggle_monitor),
            item("✅ ACK - Confirmar alertas", self._ack_all),
            pystray.Menu.SEPARATOR,
            item("❌ Salir", self._quit),
        )

    def _toggle_monitor(self, icon, menu_item):
        self._on_start_stop()

    def _ack_all(self, icon, menu_item):
        self._on_ack_all()

    def _quit(self, icon, menu_item):
        self.stop()
        self._on_quit()

    def start(self):
        if not PYSTRAY_AVAILABLE:
            print("[Tray] pystray no disponible. Bandeja del sistema desactivada.")
            return

        self._icon = pystray.Icon(
            name="ark_raid_monitor",
            icon=_get_icon(False),
            title="ARK Raid Monitor",
            menu=self._build_menu(),
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._icon:
            self._icon.stop()

    def update_monitoring_state(self, is_monitoring: bool):
        self._is_monitoring = is_monitoring
        if self._icon:
            self._icon.menu = self._build_menu()

    def update_alert_count(self, count: int):
        self._alert_count = count
        if self._icon:
            self._icon.icon = _get_icon(count > 0)
            status = f"ARK Raid Monitor — {count} alerta(s) activa(s)" if count > 0 else "ARK Raid Monitor — OK"
            self._icon.title = status

    def notify(self, title: str, message: str):
        """Muestra una notificación nativa de Windows desde la bandeja."""
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception:
                pass
