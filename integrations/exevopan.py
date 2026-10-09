from __future__ import annotations

from typing import Dict, List

import requests
from urllib.parse import quote

from core.result import EMPTY, INVALID_INPUT, SITE_ERROR, Result, classify_exception, response_meta

# Parsers ficam separados (sem rede). Reexportados aqui por compatibilidade.
from integrations.parsers.exevopan_parser import *  # noqa: F401,F403
from integrations.parsers.exevopan_parser import (  # noqa: F401
    _CHANCE_RE, _EXPECTED_RE, _normalize_chance, _normalize_expected,
    _parse_from_next_data, _parse_from_text, _score, parse_bosses,
)

# ExevoPan (Next.js) – algumas rotas variam por idioma.
EXEVOPAN_URLS = [
    "https://www.exevopan.com/bosses/{world}",
    "https://www.exevopan.com/pt/bosses/{world}",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_exevopan_result(world: str, timeout: int = 20) -> Result:
    """Busca bosses e devolve Result (sucesso com lista ou erro explicado)."""
    world = (world or "").strip()
    if not world:
        return Result.failure(INVALID_INPUT, "Digite o world.")

    last_kind = SITE_ERROR
    for tpl in EXEVOPAN_URLS:
        url = tpl.format(world=quote(world))
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
        except Exception as exc:
            last_kind = classify_exception(exc)
            continue
        if r.status_code >= 400 or not (r.text or ""):
            last_kind = SITE_ERROR
            continue
        bosses = parse_bosses(r.text)
        if bosses:
            return Result.success(bosses, **response_meta(r))
        last_kind = EMPTY
    if last_kind == EMPTY:
        return Result.failure(EMPTY, "Nenhum boss encontrado. Confira o nome do world.")
    return Result.failure(last_kind)


def fetch_exevopan_bosses(world: str, timeout: int = 20) -> List[Dict[str, str]]:
    """Compatibilidade: devolve só a lista (vazia em caso de erro)."""
    res = fetch_exevopan_result(world, timeout=timeout)
    return list(res.data or []) if res.ok else []
