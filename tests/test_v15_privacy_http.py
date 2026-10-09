import os
import tempfile
import threading
import time
import unittest
from datetime import datetime
from unittest import mock

import requests

import core.http_cache as hc
from services import error_reporting as er
from integrations.tibia_com import eu_dst_offset_hours, _eu_dst_offset_manual


class RedactTests(unittest.TestCase):
    def test_removes_query_and_names(self):
        t = er.redact("GET https://guildstats.eu/include/character/tab.php?nick=Xman+Lord&tab=experience falhou")
        self.assertNotIn("Xman", t)
        self.assertIn("guildstats.eu", t)

    def test_removes_character_path(self):
        t = er.redact("https://api.tibiadata.com/v4/character/Monk%20Curandeiro")
        self.assertNotIn("Curandeiro", t)

    def test_removes_home_user(self):
        self.assertNotIn("erick", er.redact("File /home/erick/app/main.py"))

    def test_log_written_redacted_and_deletable(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(er, "get_writable_dir", return_value=d):
            er.write_crash_log("erro em https://x.com/a?name=Fulano")
            raw = open(os.path.join(d, er.CRASH_FILE_NAME), encoding="utf-8").read()
            self.assertNotIn("Fulano", raw)
            self.assertIn("x.com", er.read_crash_log())
            er.delete_crash_log()
            self.assertEqual("", er.read_crash_log())

    def test_old_file_expires(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(er, "get_writable_dir", return_value=d):
            old = os.path.join(d, er.CRASH_FILE_NAME + ".old")
            open(old, "w").write("velho")
            past = time.time() - er.MAX_OLD_AGE - 10
            os.utime(old, (past, past))
            er.write_crash_log("novo")
            self.assertFalse(os.path.exists(old))


class HttpClientTests(unittest.TestCase):
    def tearDown(self):
        hc.clear()

    def test_install_does_not_patch_requests(self):
        before = requests.get
        hc.install()
        self.assertIs(requests.get, before)

    def test_waiter_shares_owner_error_without_refetch(self):
        url = "https://api.tibiadata.com/v4/test-shared-error"
        calls = []
        started = threading.Event()

        class S:
            def get(self, *a, **kw):
                calls.append(1)
                started.set()
                time.sleep(0.3)
                raise requests.ConnectionError("sem rede")

        with mock.patch.object(hc, "_get_session", lambda: S()), \
                mock.patch.object(hc, "_disk_load", return_value=None):
            errs = {}

            def run(name):
                try:
                    hc.cached_get(url, timeout=1)
                except Exception as e:
                    errs[name] = e
            t1 = threading.Thread(target=run, args=("a",)); t1.start(); started.wait(2)
            t2 = threading.Thread(target=run, args=("b",)); t2.start(); t1.join(); t2.join()
        self.assertEqual(1, len(calls), "a thread que esperou não pode refazer a busca")
        self.assertIsInstance(errs.get("a"), requests.ConnectionError)
        self.assertIsInstance(errs.get("b"), requests.ConnectionError)

    def test_waiter_shares_success(self):
        url = "https://api.tibiadata.com/v4/test-shared-ok"
        started = threading.Event()
        calls = []

        class R:
            status_code = 200
            content = b"ok"
            headers = requests.structures.CaseInsensitiveDict()

        class S:
            def get(self, *a, **kw):
                calls.append(1); started.set(); time.sleep(0.2); return R()

        with mock.patch.object(hc, "_get_session", lambda: S()), mock.patch.object(hc, "_disk_save"):
            out = {}
            t1 = threading.Thread(target=lambda: out.__setitem__("a", hc.cached_get(url, timeout=1))); t1.start(); started.wait(2)
            t2 = threading.Thread(target=lambda: out.__setitem__("b", hc.cached_get(url, timeout=1))); t2.start(); t1.join(); t2.join()
        self.assertEqual(1, len(calls))
        self.assertEqual(200, out["b"].status_code)
        self.assertFalse(hc.is_stale(out["b"]))


class TimezoneTests(unittest.TestCase):
    def test_dst_boundaries_match_manual_rule(self):
        for dt in (datetime(2026, 3, 29, 1, 59), datetime(2026, 3, 29, 3, 0),
                   datetime(2026, 10, 25, 1, 0), datetime(2026, 10, 25, 4, 0),
                   datetime(2026, 7, 1, 12), datetime(2026, 1, 1, 12)):
            self.assertEqual(_eu_dst_offset_manual(dt), eu_dst_offset_hours(dt), dt)


if __name__ == "__main__":
    unittest.main()
