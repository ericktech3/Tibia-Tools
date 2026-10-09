import os, threading, time
import requests

from core import http_cache as hc
from core import fgs_budget


class _Resp:
    def __init__(self, body=b"ok"):
        self.status_code = 200
        self._content = body
        self.content = body
        self.headers = {}
        self.url = "https://api.tibiadata.com/x"
        self.encoding = "utf-8"


def test_waiting_thread_gets_stale_when_owner_fails(monkeypatch):
    url = "https://api.tibiadata.com/v4/world/Antica"
    hc.clear()
    k = hc._key(url, {})
    old = requests.Response(); old.status_code = 200; old._content = b"old"
    with hc._lock:
        hc._cache[k] = (time.time() - 10_000, old)  # vencido
    started = threading.Event()

    class S:
        def get(self, *a, **kw):
            started.set()
            time.sleep(0.3)
            raise requests.ConnectionError("sem rede")
    monkeypatch.setattr(hc, "_get_session", lambda: S())
    results = {}
    t1 = threading.Thread(target=lambda: results.__setitem__("a", hc.cached_get(url, timeout=1)))
    t1.start(); started.wait(2)
    t2 = threading.Thread(target=lambda: results.__setitem__("b", hc.cached_get(url, timeout=1)))
    t2.start(); t1.join(); t2.join()
    assert hc.is_stale(results["a"])
    assert hc.is_stale(results["b"]), "thread que esperou não pode marcar dado vencido como hit"
    hc.clear()


def test_private_requests_skip_cache_and_key_headers():
    assert hc.is_private_request({"headers": {"authorization": "x"}})
    assert hc.is_private_request({"cookies": {"a": "b"}})
    assert not hc.is_private_request({"headers": {"User-Agent": "x"}})
    a = hc._key("u", {"headers": {"Accept-Language": "pt"}})
    b = hc._key("u", {"headers": {"accept-language": "en"}})
    assert a != b


def test_prune_disk_limits_size_and_age(tmp_path, monkeypatch):
    monkeypatch.setattr(hc, "_disk_dir", str(tmp_path))
    monkeypatch.setattr(hc, "MAX_DISK_FILES", 3)
    now = time.time()
    for i in range(6):
        p = tmp_path / f"{i}.json"; p.write_text("x" * 10)
        os.utime(p, (now - 100 + i, now - 100 + i))
    old = tmp_path / "velho.json"; old.write_text("x")
    os.utime(old, (now - hc.MAX_DISK_AGE - 10,) * 2)
    hc.prune_disk(force=True, now=now)
    names = sorted(os.listdir(tmp_path))
    assert names == ["3.json", "4.json", "5.json"]
    # sem force, não varre de novo antes do intervalo
    (tmp_path / "n.json").write_text("x")
    hc.prune_disk(now=now + 10)
    assert len(os.listdir(tmp_path)) == 4


def test_fgs_budget(tmp_path):
    d = str(tmp_path); now = 1_000_000.0
    fgs_budget.record(d, now - 3 * 3600, now - 3600, now=now)
    assert not fgs_budget.exhausted(d, now=now)
    fgs_budget.record(d, now - 3600, now + 3.6 * 3600, now=now + 3.6 * 3600)
    assert fgs_budget.exhausted(d, now=now + 3.6 * 3600)
    assert fgs_budget.seconds_until_available(d, now=now + 3.6 * 3600) > 0
    assert not fgs_budget.exhausted(d, now=now + 30 * 3600)  # saiu da janela
    fgs_budget.reset(d)
    assert fgs_budget.used_seconds(d) == 0


def test_hook_adds_on_timeout(tmp_path):
    from p4a import hook
    j = tmp_path / "ServiceFavwatch.java"
    j.write_text("public class ServiceFavwatch extends PythonService {\n}\n")
    assert hook._patch_service_java(j)
    assert "onTimeout(int startId, int fgsType)" in j.read_text()
    assert not hook._patch_service_java(j)
