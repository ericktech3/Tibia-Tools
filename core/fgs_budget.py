"""Controle do limite de 6 h/24 h do Android 15+ para serviços dataSync.

O Android 15/16 (app com alvo API 35+) só deixa um serviço "dataSync" rodar
6 horas a cada 24 horas em segundo plano. Ao estourar, o sistema chama
Service.onTimeout() e, se o serviço não parar em poucos segundos, o app é
encerrado com erro. Para nunca chegar lá, o monitor conta o próprio tempo e
pausa sozinho com folga (BUDGET_SECONDS). O contador zera quando o usuário
abre o app (o Android também zera o limite nesse momento).
"""
from __future__ import annotations

import json
import os
import time

WINDOW_SECONDS = 24 * 3600
BUDGET_SECONDS = int(5.5 * 3600)   # folga de 30 min antes do limite de 6 h
FILE_NAME = "fgs_budget.json"


def _path(data_dir: str) -> str:
    return os.path.join(data_dir, FILE_NAME)


def _load(data_dir: str) -> dict:
    try:
        with open(_path(data_dir), "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("spans"), list):
            return d
    except Exception:
        pass
    return {"spans": []}


def _save(data_dir: str, d: dict) -> None:
    try:
        p = _path(data_dir)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, p)
    except Exception:
        pass


def _clean(spans, now: float):
    out = []
    for s in spans:
        try:
            a, b = float(s[0]), float(s[1])
        except Exception:
            continue
        if b > now - WINDOW_SECONDS and b >= a:
            out.append([max(a, now - WINDOW_SECONDS), b])
    return out


def used_seconds(data_dir: str, now: float | None = None) -> float:
    now = time.time() if now is None else now
    return sum(b - a for a, b in _clean(_load(data_dir)["spans"], now))


def record(data_dir: str, start: float, end: float, now: float | None = None) -> float:
    """Soma o intervalo [start, end] ao uso e devolve o total usado em 24 h."""
    now = time.time() if now is None else now
    d = _load(data_dir)
    spans = _clean(d["spans"], now)
    if end > start:
        if spans and abs(spans[-1][1] - start) < 1:
            spans[-1][1] = end          # junta com o intervalo anterior
        else:
            spans.append([start, end])
    d["spans"] = spans[-200:]
    _save(data_dir, d)
    return sum(b - a for a, b in spans)


def exhausted(data_dir: str, now: float | None = None) -> bool:
    return used_seconds(data_dir, now) >= BUDGET_SECONDS


def seconds_until_available(data_dir: str, now: float | None = None) -> int:
    """Quanto falta (s) para liberar tempo de novo, se esgotado."""
    now = time.time() if now is None else now
    spans = _clean(_load(data_dir)["spans"], now)
    used = sum(b - a for a, b in spans)
    if used < BUDGET_SECONDS:
        return 0
    # tempo até o intervalo mais antigo sair da janela o suficiente
    excess = used - BUDGET_SECONDS + 60
    t = now
    for a, b in spans:
        dur = b - a
        t = b + WINDOW_SECONDS
        excess -= dur
        if excess <= 0:
            break
    return max(60, int(t - now))


def reset(data_dir: str) -> None:
    """Chamado quando o usuário abre o app (o Android zera o limite também)."""
    _save(data_dir, {"spans": [], "reset_at": time.time()})
