"""
notifier.py - Envío de notificaciones via Telegram y ntfy.sh
"""

import requests
import threading
from alert_detector import Alert
from config_store import load_config

try:
    import telegram
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


def _load_config() -> dict:
    return load_config()


class Notifier:
    def __init__(self, alert_manager_ref=None):
        self._alert_manager = alert_manager_ref
        cfg = _load_config()

        self._tg_token = cfg.get("telegram", {}).get("token", "")
        self._tg_chat_ids = cfg.get("telegram", {}).get("chat_ids", [])
        self._tg_bot = None

        if TELEGRAM_AVAILABLE and self._tg_token:
            try:
                self._tg_bot = telegram.Bot(token=self._tg_token)
            except Exception as e:
                print(f"[Notifier] Error Telegram: {e}")

        ntfy_cfg = cfg.get("ntfy", {})
        self._ntfy_server = ntfy_cfg.get("server", "https://ntfy.sh")
        self._ntfy_topic = ntfy_cfg.get("topic", "ark-raid-alert")
        self._ntfy_priority = ntfy_cfg.get("priority", "urgent")
        self._ntfy_token = ntfy_cfg.get("token", "")

    def reload_config(self):
        """Recarga credenciales desde config (útil cuando el usuario las cambia en la GUI)."""
        cfg = _load_config()
        self._tg_token = cfg.get("telegram", {}).get("token", "")
        self._tg_chat_ids = cfg.get("telegram", {}).get("chat_ids", [])
        ntfy_cfg = cfg.get("ntfy", {})
        self._ntfy_server = ntfy_cfg.get("server", "https://ntfy.sh")
        self._ntfy_topic = ntfy_cfg.get("topic", "ark-raid-alert")
        self._ntfy_priority = ntfy_cfg.get("priority", "urgent")
        self._ntfy_token = ntfy_cfg.get("token", "")

        if TELEGRAM_AVAILABLE and self._tg_token:
            try:
                self._tg_bot = telegram.Bot(token=self._tg_token)
            except Exception as e:
                print(f"[Notifier] Error Telegram reload: {e}")

    def set_alert_manager(self, am):
        self._alert_manager = am

    def send_alert(self, alert: Alert):
        """Envía la alerta a todos los canales en threads separados."""
        if self._tg_bot and self._tg_chat_ids:
            threading.Thread(target=self._send_telegram, args=(alert,), daemon=True).start()
        threading.Thread(target=self._send_ntfy, args=(alert,), daemon=True).start()

    def send_info(self, message: str):
        """Mensaje informativo (inicio/parada) solo por Telegram."""
        if not self._tg_bot:
            return
        for chat_id in self._tg_chat_ids:
            try:
                self._tg_bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
            except Exception as e:
                print(f"[Notifier] Error info Telegram {chat_id}: {e}")

    def _send_telegram(self, alert: Alert):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅  Dismiss All — Stop alerts", callback_data="ack_all")]
        ])
        for chat_id in self._tg_chat_ids:
            try:
                self._tg_bot.send_message(
                    chat_id=chat_id,
                    text=alert.format_message(),
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            except Exception as e:
                print(f"[Notifier] Error Telegram {chat_id}: {e}")

    def send_resend_summary(self, alerts: list):
        """Sends a single consolidated reminder when multiple alerts are still active."""
        reminder_num = max(a.send_count for a in alerts) + 1
        categories = [a.category.value for a in alerts]
        threading.Thread(
            target=self._send_ntfy_summary, args=(categories, reminder_num), daemon=True
        ).start()
        if self._tg_bot and self._tg_chat_ids:
            threading.Thread(
                target=self._send_telegram_summary, args=(alerts, reminder_num), daemon=True
            ).start()

    def _send_ntfy_summary(self, categories: list, reminder_num: int):
        url = f"{self._ntfy_server}/{self._ntfy_topic}"
        title = f"[STILL ACTIVE x{reminder_num}] {len(categories)} alert(s) ongoing"
        body_lines = [f"Reminder #{reminder_num} — Alerts not dismissed yet!", ""]
        for cat in categories:
            body_lines.append(f"  • {cat}")
        body_lines += ["", "Open ARK Raid Monitor and tap Dismiss All to stop."]
        headers = {
            "Title": title,
            "Priority": self._ntfy_priority,
            "Tags": "rotating_light,skull",
            "Content-Type": "text/plain; charset=utf-8",
        }
        if self._ntfy_token:
            headers["Authorization"] = f"Bearer {self._ntfy_token}"
        try:
            requests.post(
                url,
                data="\n".join(body_lines).encode("utf-8"),
                headers=headers,
                timeout=10,
            )
        except Exception as e:
            print(f"[Notifier] Error ntfy summary: {e}")

    def _send_telegram_summary(self, alerts: list, reminder_num: int):
        lines = [f"🔁 *REMINDER #{reminder_num}* — Alerts still active!\n"]
        for a in alerts:
            lines.append(f"{a.category_icon()} {a.category.value}")
        text = "\n".join(lines)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅  Dismiss All — Stop alerts", callback_data="ack_all")]
        ])
        for chat_id in self._tg_chat_ids:
            try:
                self._tg_bot.send_message(
                    chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=keyboard
                )
            except Exception as e:
                print(f"[Notifier] Error Telegram summary {chat_id}: {e}")

    def _send_ntfy(self, alert: Alert):
        url = f"{self._ntfy_server}/{self._ntfy_topic}"
        headers = {
            "Title": alert.format_ntfy_title(),
            "Priority": self._ntfy_priority,
            "Tags": "rotating_light,skull",
            "Content-Type": "text/plain; charset=utf-8",
        }
        if self._ntfy_token:
            headers["Authorization"] = f"Bearer {self._ntfy_token}"
        try:
            requests.post(
                url,
                data=alert.format_ntfy_message().encode("utf-8"),
                headers=headers,
                timeout=10,
            )
        except Exception as e:
            print(f"[Notifier] Error ntfy: {e}")


def start_telegram_bot(notifier: Notifier):
    """
    Arranca el polling del bot de Telegram en thread daemon.
    Usa notifier._alert_manager para acceder siempre al manager activo.
    """
    if not TELEGRAM_AVAILABLE:
        return

    cfg = _load_config()
    token = cfg.get("telegram", {}).get("token", "")
    if not token:
        return

    from telegram.ext import Updater, CommandHandler, CallbackQueryHandler

    updater = Updater(token=token)
    dp = updater.dispatcher

    def _am():
        """Devuelve el AlertManager activo en este momento."""
        return notifier._alert_manager

    def cmd_start(update, context):
        chat_id = update.effective_chat.id
        update.message.reply_text(
            f"✅ *ARK Raid Monitor* active\n\nYour chat\\_id: `{chat_id}`\n\n"
            "/ack — Dismiss all active alerts\n"
            "/status — Show active alerts\n"
            "/test — Send a test notification",
            parse_mode="Markdown",
        )

    def cmd_ack(update, context):
        am = _am()
        if am is None:
            update.message.reply_text("Monitor is not running.")
            return
        count = am.acknowledge_all()
        msg = f"✅ {count} alert(s) dismissed. No more notifications." if count else "No active alerts."
        update.message.reply_text(msg)

    def cmd_status(update, context):
        am = _am()
        if am is None:
            update.message.reply_text("Monitor is not running.")
            return
        update.message.reply_text(am.get_active_summary())

    def cmd_test(update, context):
        from alert_detector import Alert, AlertCategory
        test_alert = Alert(
            text="[TEST] Your Parasaur - Lvl 100 was killed by TestPlayer of Tribe Enemies!",
            category=AlertCategory.DINOS_KILLED,
            severity="CRITICAL",
        )
        notifier.send_alert(test_alert)
        update.message.reply_text("✅ Test notification sent.")

    def callback_ack(update, context):
        query = update.callback_query
        am = _am()
        if am is None:
            query.answer("Monitor not running.")
            return
        am.acknowledge_all()
        query.answer("✅ All alerts dismissed.")
        try:
            query.edit_message_text("✅ All alerts dismissed. No more notifications.")
        except Exception:
            pass

    dp.add_handler(CommandHandler("start", cmd_start))
    dp.add_handler(CommandHandler("ack", cmd_ack))
    dp.add_handler(CommandHandler("status", cmd_status))
    dp.add_handler(CommandHandler("test", cmd_test))
    dp.add_handler(CallbackQueryHandler(callback_ack))

    updater.start_polling(drop_pending_updates=True)
