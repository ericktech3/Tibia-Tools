from __future__ import annotations

from datetime import date, datetime
from math import exp
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


def _safe_int_like(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(float(str(value).strip().replace(',', '.')))
    except (TypeError, ValueError):
        return None


def _format_percent_text(value: Optional[float]) -> str:
    if value is None:
        return ''
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return ''
    if pct < 0:
        return ''
    if 0 <= pct <= 1:
        pct *= 100.0
    elif pct > 100:
        return ''
    rounded = round(pct, 1)
    if abs(rounded - round(rounded)) < 1e-9:
        return f'{int(round(rounded))}%'
    return f'{rounded:.1f}%'


def _parse_date_loose(value: Any) -> Optional[date]:
    if value is None or value == '':
        return None
    txt = str(value).strip()
    if not txt:
        return None
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(txt, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(txt.replace('Z', '+00:00')).date()
    except ValueError:
        return None


def _format_estimated_index_text(value: Optional[float]) -> str:
    if value is None:
        return ''
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return ''
    if 0 <= pct <= 1:
        pct *= 100.0
    if pct < 0:
        return ''
    return f"{int(round(max(0.0, min(100.0, pct))))}%"


def _display_percent_value(row: Dict[str, Any]) -> Optional[float]:
    value = row.get('score')
    if value is None:
        value = row.get('estimated_index')
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if 0 <= value <= 1:
        value *= 100.0
    return max(0.0, min(100.0, value))


def _confidence_bucket(value: Optional[float]) -> str:
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return ''
    if 0 <= pct <= 1:
        pct *= 100.0
    if pct >= 75:
        return 'VERY HIGH'
    if pct >= 20:
        return 'MEDIUM'
    if pct > 0:
        return 'LOW'
    return ''


def _annotate_display_confidence(rows: List[Dict[str, Any]]) -> None:
    for row in rows:
        pct = _display_percent_value(row)
        row['display_percent'] = pct
        if row.get('score') is None and row.get('estimated_index_text'):
            row['display_percent_text'] = str(row.get('estimated_index_text') or '').strip()
        else:
            row['display_percent_text'] = _format_percent_text(pct)
        row['confidence_label'] = _confidence_bucket(pct)


def _compute_estimated_index(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return

    official_values = [float(r.get('score')) for r in rows if r.get('score') is not None]
    official_max = max(official_values) if official_values else None

    parsed_last_dates = []
    for row in rows:
        parsed_last = _parse_date_loose(row.get('last_match_date'))
        parsed_first = _parse_date_loose(row.get('first_match_date'))
        row['_parsed_last_match_date'] = parsed_last
        row['_parsed_first_match_date'] = parsed_first
        if parsed_last is not None:
            parsed_last_dates.append(parsed_last)

    ref_date = max(parsed_last_dates) if parsed_last_dates else date.today()

    for row in rows:
        score = row.get('score')
        if score is not None:
            est = None
            if official_max and official_max > 0:
                est = max(1.0, min(99.0, (float(score) / float(official_max)) * 100.0))
            row['estimated_index'] = est
            row['estimated_index_text'] = _format_estimated_index_text(est)
            row['estimated_index_is_official_proxy'] = True
            continue

        matches_count = row.get('matches_count') if isinstance(row.get('matches_count'), int) else 0
        last_date = row.get('_parsed_last_match_date')
        first_date = row.get('_parsed_first_match_date')

        if matches_count <= 0:
            est = None
        else:
            base = 100.0 * (1.0 - exp(-float(matches_count) / 11.0))

            days_old = 9999
            if isinstance(last_date, date):
                days_old = max(0, (ref_date - last_date).days)
            if days_old <= 14:
                recency_adj = 2.0
            elif days_old <= 30:
                recency_adj = 1.0
            elif days_old <= 90:
                recency_adj = 0.0
            elif days_old <= 180:
                recency_adj = -1.0
            elif days_old <= 365:
                recency_adj = -2.0
            else:
                recency_adj = -4.0

            span_days = 0
            if isinstance(first_date, date) and isinstance(last_date, date):
                span_days = max(0, (last_date - first_date).days)
            if span_days >= 180:
                persistence_bonus = 8.0
            elif span_days >= 90:
                persistence_bonus = 7.0
            elif span_days >= 30:
                persistence_bonus = 3.0
            elif span_days >= 7:
                persistence_bonus = 1.0
            else:
                persistence_bonus = 0.0

            density_penalty = 0.0
            if matches_count >= 10:
                if span_days <= 1:
                    density_penalty = 30.0
                elif span_days <= 3:
                    density_penalty = 24.0
                elif span_days <= 7:
                    density_penalty = 18.0
                elif span_days <= 14:
                    density_penalty = 12.0
                elif span_days <= 30:
                    density_penalty = 8.0

            est = base + recency_adj + persistence_bonus - density_penalty
            est = max(12.0, min(99.0, round(est, 1)))

        row['estimated_index'] = est
        row['estimated_index_text'] = _format_estimated_index_text(est)
        row['estimated_index_is_official_proxy'] = False

    for row in rows:
        row.pop('_parsed_last_match_date', None)
        row.pop('_parsed_first_match_date', None)

def _find_likely_score(item: dict) -> Optional[float]:
    for key in (
        'score', 'probability', 'confidence', 'points', 'matchScore', 'rankScore',
        'percentage', 'percent', 'chance', 'likelihood', 'probabilityPercentage',
        'probabilityPercent', 'percentChance', 'chancePercent', 'chancePercentage',
    ):
        value = _to_float(item.get(key))
        if value is not None:
            return value

    for key, raw_value in item.items():
        key_l = str(key).strip().lower()
        if not any(tok in key_l for tok in ('score', 'prob', 'conf', 'percent', 'chance', 'likely')):
            continue
        value = _to_float(raw_value)
        if value is not None:
            return value
    return None


def _candidate_from_item(item: Any) -> Optional[Dict[str, Any]]:
    if isinstance(item, str) and item.strip():
        return {
            'name': item.strip(),
            'score': None,
            'score_text': '',
            'chance_text': '',
            'estimated_index': None,
            'estimated_index_text': '',
            'estimated_index_is_official_proxy': False,
            'matches_count': None,
            'matches_text': '',
            'first_match_date': '',
            'last_match_date': '',
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

    score = _find_likely_score(item)

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
    chance_text = _format_percent_text(score)

    matches_count = None
    for mk in ('numberOfMatches', 'matchesCount', 'matchCount', 'correlationsCount', 'occurrences', 'hits'):
        matches_count = _safe_int_like(item.get(mk))
        if matches_count is not None:
            break

    first_match_date = _first_non_empty_str(item, ('First match date', 'firstMatchDate', 'firstMatchDateOnly', 'first_match_date'))
    last_match_date = _first_non_empty_str(item, ('Last match date', 'lastMatchDate', 'lastMatchDateOnly', 'last_match_date'))
    matches_text = ''
    if matches_count is not None:
        matches_text = '1 correlação' if matches_count == 1 else f'{matches_count} correlações'

    return {
        'name': name,
        'score': score,
        'score_text': score_text,
        'chance_text': chance_text,
        'estimated_index': None,
        'estimated_index_text': '',
        'estimated_index_is_official_proxy': False,
        'matches_count': matches_count,
        'matches_text': matches_text,
        'first_match_date': first_match_date,
        'last_match_date': last_match_date,
        'world': world,
        'level': level,
        'vocation': vocation,
    }


def _collect_candidate_lists(node: Any, out: List[list]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            key_l = str(key).lower()
            if isinstance(value, list) and any(tok in key_l for tok in ('score', 'candidate', 'possible', 'suggest', 'character', 'result', 'match', 'correlation')):
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

    rows = list(dedup.values())
    _compute_estimated_index(rows)
    _annotate_display_confidence(rows)

    ordered = sorted(
        rows,
        key=lambda row: (
            row.get('score') is not None,
            row.get('score') if row.get('score') is not None else (row.get('estimated_index') or -1),
            row.get('matches_count') if isinstance(row.get('matches_count'), int) else -1,
            row.get('name', '').lower(),
        ),
        reverse=True,
    )
    return ordered[: max(1, int(limit or 10))]
