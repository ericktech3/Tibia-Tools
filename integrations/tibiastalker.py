from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

import requests

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; Mobile) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "application/json,text/plain;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

BASE_URL = "https://api.tibiastalker.pl"
CHARACTER_URL = BASE_URL + "/api/tibia-stalker/v1/characters/{name}"


class TibiaStalkerError(RuntimeError):
    pass


def fetch_stalker_character(name: str, timeout: int = 12) -> Dict[str, Any]:
    safe_name = quote(str(name).strip())
    url = CHARACTER_URL.format(name=safe_name)
    resp = requests.get(url, timeout=timeout, headers=UA)
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else {}


def build_stalker_character_url(name: str) -> str:
    safe_name = quote(str(name).strip())
    return CHARACTER_URL.format(name=safe_name)


def _first_non_empty_str(item: dict, keys: Iterable[str]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        txt = str(value).strip().replace('%', '').replace(',', '.')
        return float(txt)
    except (TypeError, ValueError):
        return None


def _candidate_from_item(item: Any) -> Optional[Dict[str, Any]]:
    if isinstance(item, str) and item.strip():
        return {
            'name': item.strip(),
            'score': None,
            'score_text': '',
            'world': '',
            'level': None,
            'vocation': '',
        }
    if not isinstance(item, dict):
        return None

    name = _first_non_empty_str(item, (
        'name', 'characterName', 'character_name', 'otherCharacterName',
        'possibleCharacterName', 'nick', 'nickname', 'title'
    ))
    if not name:
        nested = item.get('character')
        if isinstance(nested, dict):
            name = _first_non_empty_str(nested, ('name', 'characterName', 'title'))
    if not name:
        return None

    score = None
    for key in ('score', 'probability', 'confidence', 'points', 'matchScore', 'rankScore'):
        score = _to_float(item.get(key))
        if score is not None:
            break

    world = _first_non_empty_str(item, ('world', 'server'))
    vocation = _first_non_empty_str(item, ('vocation', 'voc'))
    level = None
    raw_level = item.get('level')
    try:
        level = int(raw_level) if raw_level not in (None, '') else None
    except (TypeError, ValueError):
        level = None

    score_text = ''
    if score is not None:
        score_text = f'{int(score)}' if abs(score - int(score)) < 1e-9 else f'{score:.1f}'

    return {
        'name': name,
        'score': score,
        'score_text': score_text,
        'world': world,
        'level': level,
        'vocation': vocation,
    }


def _collect_candidate_lists(node: Any, out: List[list]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            key_l = str(key).lower()
            if isinstance(value, list) and any(tok in key_l for tok in ('score', 'candidate', 'possible', 'suggest', 'character', 'result', 'match')):
                out.append(value)
            _collect_candidate_lists(value, out)
    elif isinstance(node, list):
        for value in node:
            _collect_candidate_lists(value, out)


def extract_stalker_candidates(data: Dict[str, Any], target_name: str = '', limit: int = 10) -> List[Dict[str, Any]]:
    if not isinstance(data, dict) or not data:
        return []

    target_l = str(target_name or '').strip().lower()
    lists: List[list] = []
    _collect_candidate_lists(data, lists)

    candidates: List[Dict[str, Any]] = []
    for lst in lists:
        if not isinstance(lst, list):
            continue
        local: List[Dict[str, Any]] = []
        for item in lst:
            cand = _candidate_from_item(item)
            if cand is None:
                continue
            name_l = cand['name'].strip().lower()
            if target_l and name_l == target_l:
                continue
            local.append(cand)
        if local:
            candidates.extend(local)

    # fallback: if no list qualified, try direct dict fields that may hold one candidate
    if not candidates:
        single = _candidate_from_item(data)
        if single is not None:
            name_l = single['name'].strip().lower()
            if not target_l or name_l != target_l:
                candidates.append(single)

    dedup: Dict[str, Dict[str, Any]] = {}
    for cand in candidates:
        key = cand['name'].strip().lower()
        prev = dedup.get(key)
        if prev is None:
            dedup[key] = cand
            continue
        prev_score = prev.get('score')
        new_score = cand.get('score')
        if (new_score is not None) and (prev_score is None or new_score > prev_score):
            dedup[key] = cand

    ordered = sorted(
        dedup.values(),
        key=lambda row: (row.get('score') is not None, row.get('score') or -1, row.get('name', '').lower()),
        reverse=True,
    )
    return ordered[: max(1, int(limit or 10))]
