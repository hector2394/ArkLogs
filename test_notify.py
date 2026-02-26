"""
test_notify.py - Send test alerts without monitoring

Usage:
    py -3.11 test_notify.py              # send all test types
    py -3.11 test_notify.py raid         # only raid
    py -3.11 test_notify.py dinos
    py -3.11 test_notify.py starving
    py -3.11 test_notify.py insiding
    py -3.11 test_notify.py player
"""

import sys
import time
from alert_detector import Alert, AlertCategory
from notifier import Notifier

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
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    keys = list(TESTS.keys()) if which == "all" else [which]

    invalid = [k for k in keys if k not in TESTS]
    if invalid:
        print(f"Unknown type: {invalid}. Options: {', '.join(TESTS.keys())}, all")
        return

    notifier = Notifier()

    for key in keys:
        alert = TESTS[key]
        print(f"Sending [{alert.category.value}] → {alert.text[:60]}...")
        notifier.send_alert(alert)
        time.sleep(0.5)

    print("\nWaiting for notifications to send...")
    time.sleep(4)
    print("Done.")


if __name__ == "__main__":
    main()
