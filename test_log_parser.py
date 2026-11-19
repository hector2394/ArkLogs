import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from log_parser import parse_new_lines


class LogParserTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = self.enterContext(TemporaryDirectory())
        self.cache_path = Path(directory) / "seen_lines.json"
        self.enterContext(patch("log_parser.SEEN_PATH", self.cache_path))

    def test_repeated_scan_only_returns_new_entries(self) -> None:
        first = "Day 1, 12:00:00: Your structure was destroyed!"
        second = "Day 1, 12:00:01: Your dino was killed by a raptor!"

        self.assertEqual(parse_new_lines(first), [first])
        self.assertEqual(parse_new_lines(f"{first}\n{second}\n{second}"), [second])
        self.assertEqual(parse_new_lines(f"{first}\n{second}"), [])

    def test_cache_evicts_the_oldest_entries_across_scans(self) -> None:
        entries = [f"Day {day}, 12:00:00: Your structure was destroyed!" for day in range(1, 503)]
        first_scan = "\n".join(entries[:500])
        second_scan = "\n".join([entries[0], *entries[-3:]])

        self.assertEqual(parse_new_lines(first_scan), entries[:500])
        self.assertEqual(parse_new_lines(second_scan), entries[-2:])
        self.assertEqual(parse_new_lines("\n".join(entries[2:])), [])
        self.assertEqual(parse_new_lines("\n".join(entries[:2])), entries[:2])

    def test_loads_existing_hash_list(self) -> None:
        known = "Day 1, 12:00:00: Your structure was destroyed!"
        new = "Day 1, 12:00:01: Your dino was killed by a raptor!"
        old_cache = [hashlib.md5(known.lower().encode()).hexdigest()]
        self.cache_path.write_text(json.dumps(old_cache), encoding="utf-8")

        self.assertEqual(parse_new_lines(f"{known}\n{new}"), [new])
