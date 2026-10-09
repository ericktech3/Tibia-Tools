"""Regras da tela de Bosses (sem Kivy): pontuação, filtro e ordenação."""
from __future__ import annotations

import re
from typing import Dict, Iterable, List

FILTERS = ("All", "High", "Medium+", "Low+", "No chance", "Unknown")
SORTS = ("Chance", "Name", "Favorites first")


def boss_name(b: dict, default: str = "") -> str:
    return str(b.get("boss") or b.get("name") or default)


def chance_score(chance: str) -> float:
    c = (chance or "").strip().lower()
    if not c:
        return 0.0
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", c)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except Exception:
            return 0.0
    if "no chance" in c or "sem chance" in c:
        return 0.0
    if "unknown" in c or "desconhecido" in c:
        return 0.0
    if "very low" in c:
        return 10.0
    if "low chance" in c or c == "low":
        return 25.0
    if "medium chance" in c or c == "medium":
        return 50.0
    if "high chance" in c or c == "high":
        return 75.0
    return 0.0


def matches_filter(b: dict, chance_filter: str) -> bool:
    chance = str(b.get("chance") or "")
    score = chance_score(chance)
    lowc = chance.lower()
    if chance_filter == "High":
        return score >= 70.0
    if chance_filter == "Medium+":
        return score >= 40.0
    if chance_filter == "Low+":
        return score >= 10.0
    if chance_filter == "No chance":
        return ("no chance" in lowc) or ("sem chance" in lowc)
    if chance_filter == "Unknown":
        return score == 0.0 and ("unknown" in lowc or "desconhecido" in lowc or (not chance))
    return True


def filter_and_sort(
    bosses: Iterable,
    *,
    query: str = "",
    chance_filter: str = "All",
    sort: str = "Chance",
    favorites: Iterable[str] = (),
    fav_only: bool = False,
) -> List[Dict]:
    q = (query or "").strip().lower()
    favs = set(favorites or [])
    out = []
    for b in bosses or []:
        if not isinstance(b, dict):
            continue
        name = boss_name(b)
        if q and q not in name.lower():
            continue
        if fav_only and name not in favs:
            continue
        if not matches_filter(b, chance_filter):
            continue
        out.append(b)

    if sort == "Name":
        out.sort(key=lambda b: boss_name(b).lower())
    elif sort == "Favorites first":
        out.sort(key=lambda b: (0 if boss_name(b) in favs else 1,
                                -chance_score(str(b.get("chance") or "")),
                                boss_name(b).lower()))
    else:
        out.sort(key=lambda b: chance_score(str(b.get("chance") or "")), reverse=True)
    return out


def secondary_text(b: dict) -> str:
    chance = str(b.get("chance") or "").strip()
    status = str(b.get("status") or "").strip()
    return " • ".join([x for x in [chance, status] if x]) or " "


def favorites_only_enabled(value) -> bool:
    """JSON antigo pode conter 'false' como texto; bool('false') seria True."""
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return value is True or value == 1
