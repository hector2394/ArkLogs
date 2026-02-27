"""
test_notify.py - Send test alerts through AlertManager (with resend loop)

Usage:
    py -3.11 test_notify.py              # send all 5 types, keeps resending until Ctrl+C
    py -3.11 test_notify.py raid         # only raid
    py -3.11 test_notify.py dinos
    py -3.11 test_notify.py starving
    py -3.11 test_notify.py insiding
    py -3.11 test_notify.py player
    py -3.11 test_notify.py once         # send once only, no resend loop

Press Ctrl+C to stop (simulates Dismiss All).
"""

import sys
import threading
import time
from alert_detector import Alert, AlertCategory
from alert_manager import AlertManager
from notifier import Notifier, start_telegram_bot

TESTS = {
    "raid": Alert(
        text="Your Metal Vault was destroyed by EnemyPlayer of Tribe RaidersClan!",
        category=AlertCategory.RAID,
        severity="CRITICAL",
    ),
    "dinos": Alert(
        text="Your Argentavis - Lvl 220 'SkyKing' was killed by EnemyPlayer of Tribe RaidersClan!",
        category=AlertCategory.DINOS_KILLED,
        severity="CRITICAL",
    ),
    "starving": Alert(
        text="Your Ankylosaurus - Lvl 150 'RockCrusher' has starved to death!",
        category=AlertCategory.STARVING,
        severity="WARNING",
    ),
    "insiding": Alert(
        text="INSIDING: 3 demolitions in 2 min — Your Metal Foundation demolished by TribeMember",
        category=AlertCategory.INSIDING,
        severity="CRITICAL",
    ),
    "player": Alert(
        text="Your tribe member PlayerName was killed by EnemyPlayer of Tribe RaidersClan!",
        category=AlertCategory.PLAYER_KILLED,
        severity="CRITICAL",
    ),
}


def main():
    args = sys.argv[1:]
    once = "once" in args
    keys_arg = [a for a in args if a != "once"]

    which = keys_arg[0] if keys_arg else "all"
    keys = list(TESTS.keys()) if which == "all" else [which]

    invalid = [k for k in keys if k not in TESTS]
    if invalid:
        print(f"Unknown type: {invalid}. Options: {', '.join(TESTS.keys())}, all, once")
        return

    notifier = Notifier()

    if once:
        # Single send, no resend loop
        for key in keys:
            alert = TESTS[key]
            print(f"Sending [{alert.category.value}] once...")
            notifier.send_alert(alert)
            time.sleep(0.5)
        time.sleep(4)
        print("Done.")
        return

    # Full AlertManager loop — keeps resending until Ctrl+C
    manager = AlertManager(notifier)
    notifier.set_alert_manager(manager)
    manager.start()

    # Arrancar bot de Telegram para que funcionen /ack y el botón Dismiss All
    threading.Thread(target=start_telegram_bot, args=(notifier,), daemon=True).start()

    for key in keys:
        alert = TESTS[key]
        print(f"Adding [{alert.category.value}] to active alerts...")
        manager.add_alert(alert)
        time.sleep(0.3)

    import json, os
    try:
        with open(os.path.join(os.path.dirname(__file__), "config.json")) as f:
            interval = json.load(f).get("resend_interval", 30)
    except Exception:
        interval = 30

    print(f"\n{len(keys)} alert(s) active. Resend every {interval}s.")
    print("Press Ctrl+C to simulate Dismiss All and stop.\n")

    try:
        while True:
            count = manager.active_count()
            if count == 0:
                print("All alerts dismissed.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        dismissed = manager.acknowledge_all()
        print(f"\nDismissed {dismissed} alert(s). Stopped.")

    manager.stop()


if __name__ == "__main__":
    main()
