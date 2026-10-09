"""Cliente HTTP explícito do app.

As integrações chamam `http_client.get(...)` em vez de `requests.get(...)`.
Aqui ficam concentrados: timeout padrão, cache, retry, fallback offline e a
marcação de origem dos dados (X-TT-Cache). O `requests` global NÃO é alterado,
então bibliotecas de terceiros continuam com o comportamento normal.

Nos testes, basta trocar `core.http_client.get` (ou a função usada pelo módulo)
por um falso — sem mexer no requests do processo inteiro.
"""
from __future__ import annotations

DEFAULT_TIMEOUT = 15


def get(url, params=None, **kwargs):
    from core.http_cache import cached_get

    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    return cached_get(url, params=params, **kwargs)
