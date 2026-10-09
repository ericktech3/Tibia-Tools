"""Cache HTTP + conexão reaproveitada + novas tentativas automáticas.

Chame install() uma vez no início do app. A partir daí, chamadas
requests.get para os sites conhecidos do app (TTL_BY_HOST) usam uma sessão
compartilhada, com retry em falhas temporárias, cache em memória e cache em
disco (fallback offline). Qualquer outro site passa direto para o
requests.get original, sem cache e sem alteração de comportamento.

Segurança: o cache em disco é gravado em JSON (sem pickle), então um arquivo
alterado ou corrompido nunca executa código — no pior caso é descartado.

Respostas vindas do cache recebem os cabeçalhos:
  X-TT-Cache: hit | stale
  X-TT-Cache-Age: idade em segundos (permite mostrar "dados de X min atrás")
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import logging
import os
import threading
import time
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover
    Retry = None

log = logging.getLogger("tibia_tools.http_cache")

# Tempo de cache (segundos) por site. Só esses sites passam pelo cache.
TTL_BY_HOST = {
    "www.exevopan.com": 600,      # bosses mudam 1x por dia
    "exevopan.com": 600,
    "guildstats.eu": 600,         # XP diária
    "api.tibiadata.com": 120,
    "www.tibia.com": 120,
    "api.github.com": 1800,
    "api.tibiastalker.pl": 300,
    "www.tibiawiki.com.br": 3600,
    "tibiawiki.com.br": 3600,
}
DEFAULT_TTL = 120
MAX_ENTRIES = 200
MAX_DISK_AGE = 7 * 24 * 3600      # dados offline com mais de 7 dias são descartados
DISK_FORMAT = 1

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
        _remove_legacy_pickle_files(directory)
    except Exception:
        log.warning("cache em disco indisponível em %s", directory, exc_info=True)
        _disk_dir = None


def _remove_legacy_pickle_files(directory: str):
    """Apaga arquivos .bin (pickle) de versões antigas: nunca são lidos."""
    try:
        for name in os.listdir(directory):
            if name.endswith(".bin"):
                try:
                    os.remove(os.path.join(directory, name))
                except OSError:
                    pass
    except OSError:
        pass


def is_cacheable_url(url) -> bool:
    try:
        return urlparse(str(url)).netloc.lower() in TTL_BY_HOST
    except Exception:
        return False


def _ttl_for(url) -> int:
    return TTL_BY_HOST.get(urlparse(str(url)).netloc.lower(), DEFAULT_TTL)


def _disk_file(k):
    if not _disk_dir:
        return None
    return os.path.join(_disk_dir, hashlib.sha256(repr(k).encode("utf-8")).hexdigest() + ".json")


def _disk_save(k, r, saved_at: float):
    p = _disk_file(k)
    if not p:
        return
    tmp = p + ".tmp"
    try:
        data = {
            "v": DISK_FORMAT,
            "saved_at": saved_at,
            "status": int(r.status_code),
            "url": str(r.url or ""),
            "encoding": r.encoding,
            "headers": {str(a): str(b) for a, b in dict(r.headers).items()},
            "content_b64": base64.b64encode(r.content or b"").decode("ascii"),
        }
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, p)  # gravação atômica: evita arquivo pela metade
    except Exception:
        log.warning("falha ao salvar cache em disco", exc_info=True)
        try:
            os.remove(tmp)
        except OSError:
            pass


def _disk_load(k, url):
    """Lê do disco. Arquivo corrompido/antigo é apagado e retorna None."""
    p = _disk_file(k)
    if not p or not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict) or d.get("v") != DISK_FORMAT:
            raise ValueError("formato desconhecido")
        saved_at = float(d["saved_at"])
        if time.time() - saved_at > MAX_DISK_AGE:
            raise ValueError("cache velho demais")
        resp = requests.Response()
        resp.status_code = int(d["status"])
        resp._content = base64.b64decode(d["content_b64"], validate=True)
        resp.headers.update(d.get("headers") or {})
        resp.url = d.get("url") or url
        resp.encoding = d.get("encoding")
        return saved_at, resp
    except Exception as e:
        log.info("descartando cache em disco inválido (%s)", e)
        try:
            os.remove(p)
        except OSError:
            pass
        return None


def _tagged(resp, saved_at: float, kind: str):
    """Cópia da resposta com indicação de origem e idade dos dados."""
    out = copy.copy(resp)
    out.headers = requests.structures.CaseInsensitiveDict(resp.headers)
    out.headers["X-TT-Cache"] = kind
    out.headers["X-TT-Cache-Age"] = str(max(0, int(time.time() - saved_at)))
    return out


def response_age_seconds(resp):
    """Idade (s) de uma resposta vinda do cache; 0 se veio da internet agora."""
    try:
        return int(resp.headers.get("X-TT-Cache-Age", "0") or 0)
    except Exception:
        return 0


def is_stale(resp) -> bool:
    try:
        return resp.headers.get("X-TT-Cache") == "stale"
    except Exception:
        return False


def _stale_response(k, url):
    """Última resposta boa conhecida (memória de qualquer idade ou disco)."""
    with _lock:
        hit = _cache.get(k)
    if hit:
        return _tagged(hit[1], hit[0], "stale")
    loaded = _disk_load(k, url)
    if loaded is None:
        return None
    saved_at, resp = loaded
    with _lock:
        _cache[k] = (saved_at, resp)
    return _tagged(resp, saved_at, "stale")


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
    return (str(url), repr(sorted(params.items())) if isinstance(params, dict) else repr(params),
            headers.get("User-Agent", ""), headers.get("X-Requested-With", ""))


def clear(disk: bool = False):
    with _lock:
        _cache.clear()
    if disk and _disk_dir:
        try:
            for name in os.listdir(_disk_dir):
                if name.endswith(".json"):
                    os.remove(os.path.join(_disk_dir, name))
        except OSError:
            log.warning("falha ao limpar cache em disco", exc_info=True)


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = _make_session()
    return _session


def cached_get(url, params=None, **kwargs):
    if params is not None:
        kwargs["params"] = params
    no_cache = kwargs.pop("no_cache", False)
    if not is_cacheable_url(url):
        # Site desconhecido: comportamento original do requests, sem cache.
        return _orig_get(url, **kwargs)
    session = _get_session()
    if no_cache or kwargs.get("stream"):
        return session.get(url, **kwargs)
    ttl = _ttl_for(url)
    k = _key(url, kwargs)
    now = time.time()
    with _lock:
        hit = _cache.get(k)
        if hit and now - hit[0] < ttl:
            return _tagged(hit[1], hit[0], "hit")
        ev = _inflight.get(k)
        owner = ev is None
        if owner:
            ev = _inflight[k] = threading.Event()
    if not owner:  # outra thread já está buscando a mesma URL: espera
        ev.wait(timeout=(kwargs.get("timeout") or 20) + 5)
        with _lock:
            hit = _cache.get(k)
        if hit:
            return _tagged(hit[1], hit[0], "hit")
        return session.get(url, **kwargs)
    try:
        try:
            r = session.get(url, **kwargs)
        except Exception as e:
            # Sem internet (ou site fora): devolve a última resposta salva, se houver
            stale = _stale_response(k, url)
            if stale is not None:
                log.info("offline/erro de rede em %s; usando cache (%s)", url, type(e).__name__)
                return stale
            raise
        if r.status_code == 200:
            _ = r.content  # garante corpo carregado
            saved_at = time.time()
            with _lock:
                if len(_cache) >= MAX_ENTRIES:
                    oldest = min(_cache, key=lambda x: _cache[x][0])
                    _cache.pop(oldest, None)
                _cache[k] = (saved_at, r)
            _disk_save(k, r, saved_at)
        else:
            # Erro no site (403/500...): prefere dado antigo a tela vazia
            stale = _stale_response(k, url)
            if stale is not None:
                log.info("HTTP %s em %s; usando cache", r.status_code, url)
                return stale
        return r
    finally:
        with _lock:
            _inflight.pop(k, None)
        ev.set()


def install():
    """Liga o cache para os sites do app. Seguro chamar mais de uma vez."""
    global _installed
    if _installed:
        return
    _get_session()
    requests.get = cached_get
    _installed = True


def uninstall():
    """Restaura o requests.get original (usado nos testes)."""
    global _installed
    requests.get = _orig_get
    _installed = False
