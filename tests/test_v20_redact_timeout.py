import threading
import time
import unittest
from unittest import mock

import requests

from core import http_cache as hc
from services.error_reporting import redact


class RedactWindowsPathTests(unittest.TestCase):
    CASES = [
        (r"C:\Users\Erick\Tibia Tools\main.py", "Erick"),
        (r"C:\Users\Erick de Souza\Tibia Tools\main.py", "Erick de Souza"),
        (r"d:\users\joao.silva\app\x.py", "joao.silva"),
        ("C:/Users/Maria/app/x.py", "Maria"),
        (r"C:\\Users\\Ana\\app\\x.py", "Ana"),
        ("/home/erick/app/main.py", "erick"),
        ("/Users/erick/app/main.py", "erick"),
    ]

    def test_redact_user_paths(self):
        for path, name in self.CASES:
            with self.subTest(path=path):
                out = redact(f'File "{path}", line 3')
                self.assertNotIn(name, out)
                self.assertIn("<user>", out)
                self.assertTrue("main.py" in out or "x.py" in out)


class WaitSecondsTests(unittest.TestCase):
    def test_formats(self):
        cases = [(None, 20.0), (0, 20.0), (7, 7.0), (2.5, 2.5),
                 ((3, 10), 13.0), ((3, None), 3.0), ([1, 2], 3.0)]
        for timeout, expected in cases:
            with self.subTest(timeout=timeout):
                self.assertEqual(hc._wait_seconds(timeout), expected)


class ConcurrentTimeoutTests(unittest.TestCase):
    def _run(self, timeout):
        url = "https://api.tibiadata.com/v4/world/Secura"
        hc.clear()
        started = threading.Event()

        class S:
            def get(self, *a, **kw):
                started.set()
                time.sleep(0.3)
                r = requests.Response()
                r.status_code = 200
                r._content = b"novo"
                r.url = url
                return r

        results, errors = {}, []

        def run(key):
            try:
                results[key] = hc.cached_get(url, timeout=timeout)
            except Exception as e:
                errors.append(e)

        with mock.patch.object(hc, "_get_session", lambda: S()):
            t1 = threading.Thread(target=run, args=("a",))
            t1.start()
            started.wait(2)
            t2 = threading.Thread(target=run, args=("b",))
            t2.start()
            t1.join()
            t2.join()
        hc.clear()
        self.assertFalse(errors, errors)
        self.assertEqual(results["a"].content, b"novo")
        self.assertEqual(results["b"].content, b"novo")

    def test_int_timeout(self):
        self._run(1)

    def test_tuple_timeout(self):
        self._run((1, 1))


if __name__ == "__main__":
    unittest.main()
