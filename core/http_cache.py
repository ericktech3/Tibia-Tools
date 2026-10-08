"""Cache HTTP + conexão reaproveitada + novas tentativas automáticas.

Chame install() uma vez no início do app: todas as chamadas requests.get
passam a usar uma sessão compartilhada (conexões mais rápidas), com
retry em falhas temporárias e cache em memória por alguns minutos.
"""
from __future__ import annotations

import threading
import time
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover
    Retry = None

# Tempo de cache (segundos) por site. Padrão para os demais: 120s.
TTL_BY_HOST = {
    "www.exevopan.com": 600,      # bosses mudam 1x por dia
    "exevopan.com": 600,
    "guildstats.eu": 600,         # XP diária
    "api.tibiadata.com": 120,
    "www.tibia.com": 120,
    "api.github.com": 1800,
}
DEFAULT_TTL = 120
MAX_ENTRIES = 200

_lock = threading.Lock()
_cache: dict = {}
_inflight: dict = {}
_session: requests.Session | None = None
_orig_get = requests.get
_installed = False


def _make_session() -> requests.Session:
    s = requests.Session()
    if Retry is not None:
        retry = Retry(total=2, backoff_factor=0.6,
                      status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=frozenset(["GET"]))
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    else:
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def _key(url, kwargs):
    params = kwargs.get("params")
    headers = kwargs.get("headers") or {}
    return (url, repr(sorted(params.items())) if isinstance(params, dict) else repr(params),
            headers.get("User-Agent", ""), headers.get("X-Requested-With", ""))


def clear():
    with _lock:
        _cache.clear()


def cached_get(url, params=None, **kwargs):
    if params is not None:
        kwargs["params"] = params
    if kwargs.pop("no_cache", False) or kwargs.get("stream"):
        return _session.get(url, **kwargs)
    host = urlparse(str(url)).netloc.lower()
    ttl = TTL_BY_HOST.get(host, DEFAULT_TTL)
    k = _key(url, kwargs)
    now = time.time()
    with _lock:
        hit = _cache.get(k)
        if hit and now - hit[0] < ttl:
            return hit[1]
        ev = _inflight.get(k)
        owner = ev is None
        if owner:
            ev = _inflight[k] = threading.Event()
    if not owner:  # outra thread já está buscando a mesma URL: espera
        ev.wait(timeout=(kwargs.get("timeout") or 20) + 5)
        with _lock:
            hit = _cache.get(k)
        if hit:
            return hit[1]
        return _session.get(url, **kwargs)
    try:
        r = _session.get(url, **kwargs)
        if r.status_code == 200:
            _ = r.content  # garante corpo carregado
            with _lock:
                if len(_cache) >= MAX_ENTRIES:
                    oldest = min(_cache, key=lambda x: _cache[x][0])
                    _cache.pop(oldest, None)
                _cache[k] = (time.time(), r)
        return r
    finally:
        with _lock:
            _inflight.pop(k, None)
        ev.set()


def install():
    global _session, _installed
    if _installed:
        return
    _session = _make_session()
    requests.get = cached_get
    _installed = True
