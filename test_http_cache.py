import json
import os
import pickle
import tempfile
import time
import unittest
from unittest import mock

import requests

from core import http_cache as hc


def _resp(body=b"ok", status=200, url="https://guildstats.eu/x"):
    r = requests.Response()
    r.status_code = status
    r._content = body
    r.url = url
    r.headers["Content-Type"] = "text/html"
    return r


class FakeSession:
    def __init__(self):
        self.calls = 0
        self.result = _resp()

    def get(self, url, **kw):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


URL = "https://guildstats.eu/x"


class HttpCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        hc.clear()
        hc.configure_disk(self.tmp.name)
        self.sess = FakeSession()
        hc._session = self.sess

    def tearDown(self):
        hc.clear()
        hc._disk_dir = None
        hc._session = None
        hc.uninstall()
        self.tmp.cleanup()

    def test_second_call_is_served_from_memory(self):
        hc.cached_get(URL)
        r = hc.cached_get(URL)
        self.assertEqual(self.sess.calls, 1)
        self.assertEqual(r.headers["X-TT-Cache"], "hit")

    def test_expired_entry_fetches_again(self):
        hc.cached_get(URL)
        k = next(iter(hc._cache))
        saved, resp = hc._cache[k]
        hc._cache[k] = (saved - 10_000, resp)
        hc.cached_get(URL)
        self.assertEqual(self.sess.calls, 2)

    def test_offline_uses_disk_cache_with_age(self):
        hc.cached_get(URL)
        hc.clear()  # simula app reaberto: só o disco sobrou
        self.sess.result = requests.ConnectionError("sem internet")
        r = hc.cached_get(URL)
        self.assertEqual(r.content, b"ok")
        self.assertTrue(hc.is_stale(r))
        self.assertGreaterEqual(hc.response_age_seconds(r), 0)

    def test_offline_without_cache_raises(self):
        self.sess.result = requests.ConnectionError("sem internet")
        with self.assertRaises(requests.ConnectionError):
            hc.cached_get(URL)

    def test_site_error_prefers_old_data(self):
        hc.cached_get(URL)
        self.sess.result = _resp(b"erro", status=503)
        hc.clear()
        r = hc.cached_get(URL)
        self.assertEqual(r.content, b"ok")

    def test_corrupted_disk_file_is_discarded(self):
        hc.cached_get(URL)
        files = [f for f in os.listdir(self.tmp.name) if f.endswith(".json")]
        self.assertEqual(len(files), 1)
        with open(os.path.join(self.tmp.name, files[0]), "w") as f:
            f.write("{isso nao e json")
        hc.clear()
        self.sess.result = requests.ConnectionError("x")
        with self.assertRaises(requests.ConnectionError):
            hc.cached_get(URL)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, files[0])))

    def test_too_old_disk_file_is_discarded(self):
        hc.cached_get(URL)
        f = [f for f in os.listdir(self.tmp.name) if f.endswith(".json")][0]
        p = os.path.join(self.tmp.name, f)
        d = json.load(open(p))
        d["saved_at"] = time.time() - hc.MAX_DISK_AGE - 10
        json.dump(d, open(p, "w"))
        hc.clear()
        self.sess.result = requests.ConnectionError("x")
        with self.assertRaises(requests.ConnectionError):
            hc.cached_get(URL)

    def test_disk_cache_is_not_pickle_and_legacy_files_removed(self):
        legacy = os.path.join(self.tmp.name, "old.bin")
        with open(legacy, "wb") as f:
            pickle.dump({"x": 1}, f)
        hc.configure_disk(self.tmp.name)
        self.assertFalse(os.path.exists(legacy))
        hc.cached_get(URL)
        f = [f for f in os.listdir(self.tmp.name) if f.endswith(".json")][0]
        json.load(open(os.path.join(self.tmp.name, f)))  # é JSON válido

    def test_unknown_host_passes_through_without_cache(self):
        with mock.patch.object(hc, "_orig_get", return_value=_resp(b"y")) as orig:
            hc.cached_get("https://example.org/a")
            hc.cached_get("https://example.org/a")
        self.assertEqual(orig.call_count, 2)
        self.assertEqual(self.sess.calls, 0)

    def test_install_and_uninstall(self):
        hc.install()
        self.assertIs(requests.get, hc.cached_get)
        hc.uninstall()
        self.assertIs(requests.get, hc._orig_get)


if __name__ == "__main__":
    unittest.main()
