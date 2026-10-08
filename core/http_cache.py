"""Cache HTTP + conexão reaproveitada + novas tentativas automáticas.

Chame install() uma vez no início do app: todas as chamadas requests.get
passam a usar uma sessão compartilhada (conexões mais rápidas), com
retry em falhas temporárias e cache em memória por alguns minutos.
"""
from __future__ import annotations

import hashlib
import os
import pickle
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
_disk_dir: str | None = None


def configure_disk(directory: str):
    """Ativa cache em disco: sobrevive ao fechar o app e serve de fallback offline."""
    global _disk_dir
    try:
        os.makedirs(directory, exist_ok=True)
        _disk_dir = directory
    except Exception:
        _disk_dir = None


def _disk_file(k):
    if not _disk_dir:
        return None
    return os.path.join(_disk_dir, hashlib.md5(repr(k).encode("utf-8")).hexdigest() + ".bin")


def _disk_save(k, r):
    p = _disk_file(k)
    if not p:
        return
    try:
        with open(p, "wb") as f:
            pickle.dump({"status": r.status_code, "headers": dict(r.headers),
                         "content": r.content, "url": r.url}, f)
    except Exception:
        pass


def _stale_response(k, url):
    """Última resposta boa conhecida (memória de qualquer idade ou disco)."""
    with _lock:
        hit = _cache.get(k)
    if hit:
        return hit[1]
    p = _disk_file(k)
    if p and os.path.exists(p):
        try:
            with open(p, "rb") as f:
                d = pickle.load(f)
            resp = requests.Response()
            resp.status_code = d["status"]
            resp._content = d["content"]
            resp.headers.update(d["headers"])
            resp.url = d.get("url") or url
            with _lock:
                _cache[k] = (time.time(), resp)
            return resp
        except Exception:
            return None
    return None


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
        try:
            r = _session.get(url, **kwargs)
        except Exception:
            # Sem internet (ou site fora): devolve a última resposta salva, se houver
            stale = _stale_response(k, url)
            if stale is not None:
                return stale
            raise
        if r.status_code == 200:
            _ = r.content  # garante corpo carregado
            with _lock:
                if len(_cache) >= MAX_ENTRIES:
                    oldest = min(_cache, key=lambda x: _cache[x][0])
                    _cache.pop(oldest, None)
                _cache[k] = (time.time(), r)
            _disk_save(k, r)
        else:
            # Erro no site (403/500...): prefere dado antigo a tela vazia
            stale = _stale_response(k, url)
            if stale is not None:
                return stale
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
