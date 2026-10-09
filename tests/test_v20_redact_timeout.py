import threading, time
import pytest
import requests

from core import http_cache as hc
from services.error_reporting import redact


@pytest.mark.parametrize("path,name", [
    (r"C:\Users\Erick\Tibia Tools\main.py", "Erick"),
    (r"C:\Users\Erick de Souza\Tibia Tools\main.py", "Erick de Souza"),
    (r"d:\users\joao.silva\app\x.py", "joao.silva"),
    ("C:/Users/Maria/app/x.py", "Maria"),
    (r"C:\\Users\\Ana\\app\\x.py", "Ana"),
    ("/home/erick/app/main.py", "erick"),
    ("/Users/erick/app/main.py", "erick"),
])
def test_redact_user_paths(path, name):
    out = redact(f'File "{path}", line 3')
    assert name not in out
    assert "<user>" in out
    assert "main.py" in out or "x.py" in out


@pytest.mark.parametrize("timeout,expected", [
    (None, 20.0), (0, 20.0), (7, 7.0), (2.5, 2.5), ((3, 10), 13.0), ((3, None), 3.0), ([1, 2], 3.0),
])
def test_wait_seconds_formats(timeout, expected):
    assert hc._wait_seconds(timeout) == expected


@pytest.mark.parametrize("timeout", [1, (1, 1)])
def test_concurrent_wait_accepts_int_and_tuple_timeout(monkeypatch, timeout):
    url = "https://api.tibiadata.com/v4/world/Secura"
    hc.clear()
    started = threading.Event()

    class S:
        def get(self, *a, **kw):
            started.set()
            time.sleep(0.3)
            r = requests.Response(); r.status_code = 200; r._content = b"novo"
            r.url = url
            return r
    monkeypatch.setattr(hc, "_get_session", lambda: S())
    results, errors = {}, []

    def run(key):
        try:
            results[key] = hc.cached_get(url, timeout=timeout)
        except Exception as e:  # pragma: no cover - falha do teste
            errors.append(e)
    t1 = threading.Thread(target=run, args=("a",)); t1.start(); started.wait(2)
    t2 = threading.Thread(target=run, args=("b",)); t2.start()
    t1.join(); t2.join()
    assert not errors, errors
    assert results["a"].content == b"novo" and results["b"].content == b"novo"
    hc.clear()
