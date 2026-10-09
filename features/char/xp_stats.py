"""Cálculos do histórico de XP e das mortes (sem Kivy, testáveis)."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional


def _to_date(value) -> Optional[date]:
    try:
        return datetime.fromisoformat(str(value or "").strip()).date()
    except Exception:
        return None


def daily_map(rows: Iterable) -> Dict[date, int]:
    """Soma a XP por dia (se a mesma data vier duplicada, soma)."""
    out: Dict[date, int] = {}
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        d = _to_date(r.get("date"))
        if d is None:
            continue
        try:
            v = int(r.get("exp_change_int") or 0)
        except Exception:
            continue
        out[d] = out.get(d, 0) + v
    return out


def summarize_xp(rows: Iterable, today: Optional[date] = None) -> Dict[str, Any]:
    """Resumo da XP.

    A janela de 7 dias é a data mais recente do histórico e os 6 dias anteriores
    (7 dias exatos, os mesmos mostrados na lista).
    """
    dm = daily_map(rows)
    if not dm:
        return {"ok": False}
    ref = max(dm)
    days7 = [ref - timedelta(days=i) for i in range(7)]
    days30 = [ref - timedelta(days=i) for i in range(30)]
    total_7 = sum(dm.get(d, 0) for d in days7)
    total_30 = sum(dm.get(d, 0) for d in days30)
    active_7 = sum(1 for d in days7 if dm.get(d, 0) > 0)
    best_d = max(days30, key=lambda d: dm.get(d, 0))
    best_v = dm.get(best_d, 0)
    return {
        "ok": True,
        "ref": ref,
        "total_7": total_7,
        "total_30": total_30,
        "avg_7": int(round(total_7 / 7)),
        "active_7": active_7,
        "best_date": best_d if best_v > 0 else None,
        "best_value": best_v,
        "daily_7": [(d, dm.get(d, 0)) for d in days7],
        "lag_days": ((today or date.today()) - ref).days,
    }


def fmt_signed(n: int) -> str:
    try:
        n = int(n)
    except Exception:
        return str(n)
    s = f"{abs(n):,}".replace(",", ".")
    return ("-" if n < 0 else "+") + s


def fmt_compact(n: int) -> str:
    """Ex.: 12.345.678 -> '12,3 kk' (formato comum entre jogadores)."""
    n = int(n or 0)
    a = abs(n)
    sign = "-" if n < 0 else ""
    if a >= 1_000_000:
        return f"{sign}{a / 1_000_000:.1f} kk".replace(".", ",")
    if a >= 1_000:
        return f"{sign}{a / 1_000:.0f} k"
    return f"{sign}{a}"


def summary_lines(s: Dict[str, Any]) -> List[str]:
    if not s.get("ok"):
        return []
    lines = [f"Total 7d: {fmt_signed(s['total_7'])} XP • 30d: {fmt_signed(s['total_30'])} XP"]
    extra = f"Média 7d: {fmt_compact(s['avg_7'])}/dia • {s['active_7']}/7 dias com XP"
    if s.get("best_date"):
        extra += f" • Melhor dia: {s['best_date'].strftime('%d/%m')} ({fmt_compact(s['best_value'])})"
    lines.append(extra)
    if s.get("lag_days", 0) >= 2:
        lines.append(f"Último dia registrado: {s['ref'].strftime('%d/%m')} (o site pode estar atrasado)")
    return lines


def parse_xp_number(text) -> int:
    digits = re.sub(r"[^\d]", "", str(text or ""))
    return int(digits) if digits else 0


def summarize_deaths(deaths: Iterable) -> Dict[str, int]:
    count = 0
    total = 0
    for d in deaths or []:
        if not isinstance(d, dict):
            continue
        if not str(d.get("reason") or d.get("description") or "").strip():
            continue
        count += 1
        total += parse_xp_number(d.get("exp_lost") or d.get("xp_lost"))
    return {"count": count, "xp_lost": total}
