"""Resultado padrão de sucesso/erro para todas as buscas do app.

Em vez de cada tela inventar sua própria mensagem ("Erro: HTTPSConnectionPool..."),
as buscas devolvem um Result e a tela só mostra `result.user_message()`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

log = logging.getLogger("tibia_tools.result")

# Tipos de erro conhecidos
OFFLINE = "offline"
TIMEOUT = "timeout"
NOT_FOUND = "not_found"
SITE_ERROR = "site_error"
EMPTY = "empty"
INVALID_INPUT = "invalid_input"
UNKNOWN = "unknown"

_MESSAGES = {
    OFFLINE: "Sem conexão com a internet. Verifique o Wi-Fi ou os dados móveis.",
    TIMEOUT: "O site demorou demais para responder. Tente de novo em instantes.",
    NOT_FOUND: "Não encontrado.",
    SITE_ERROR: "O site de dados está fora do ar ou mudou. Tente mais tarde.",
    EMPTY: "Nada encontrado.",
    INVALID_INPUT: "Dados inválidos.",
    UNKNOWN: "Ocorreu um erro inesperado. Tente novamente.",
}


@dataclass
class Result:
    ok: bool
    data: Any = None
    kind: str = ""                 # tipo do erro (vazio quando ok)
    message: str = ""              # mensagem específica (opcional)
    stale: bool = False            # dados antigos vindos do cache offline
    age_seconds: int = 0           # idade dos dados (0 = acabou de buscar)
    extra: dict = field(default_factory=dict)

    @classmethod
    def success(cls, data, *, stale: bool = False, age_seconds: int = 0, **extra) -> "Result":
        return cls(True, data, stale=stale, age_seconds=int(age_seconds or 0), extra=extra)

    @classmethod
    def failure(cls, kind: str, message: str = "", **extra) -> "Result":
        return cls(False, None, kind=kind or UNKNOWN, message=message, extra=extra)

    @classmethod
    def from_exception(cls, exc: BaseException) -> "Result":
        return cls.failure(classify_exception(exc))

    def user_message(self) -> str:
        if self.ok:
            return ""
        return self.message or _MESSAGES.get(self.kind, _MESSAGES[UNKNOWN])

    def age_text(self) -> str:
        """Ex.: 'agora', 'há 5 min', 'há 2 h' — para mostrar a idade dos dados."""
        return format_age(self.age_seconds)

    def __bool__(self) -> bool:
        return self.ok


def format_age(seconds: int) -> str:
    s = max(0, int(seconds or 0))
    if s < 60:
        return "agora"
    m = s // 60
    if m < 60:
        return f"há {m} min"
    h = m // 60
    if h < 24:
        return f"há {h} h"
    return f"há {h // 24} dia(s)"


def classify_exception(exc: BaseException) -> str:
    try:
        import requests  # import local: core não depende de rede para funcionar

        if isinstance(exc, requests.Timeout):
            return TIMEOUT
        if isinstance(exc, requests.ConnectionError):
            return OFFLINE
        if isinstance(exc, requests.HTTPError):
            resp = getattr(exc, "response", None)
            if resp is not None and getattr(resp, "status_code", 0) == 404:
                return NOT_FOUND
            return SITE_ERROR
    except Exception:
        pass
    if isinstance(exc, (TimeoutError,)):
        return TIMEOUT
    if isinstance(exc, (ConnectionError, OSError)):
        return OFFLINE
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return SITE_ERROR  # resposta em formato inesperado
    return UNKNOWN


def run_safely(fn: Callable[[], Any], *, empty_is_error: bool = False) -> Result:
    """Executa fn; nunca deixa a exceção escapar. Útil dentro de threads."""
    try:
        value = fn()
    except Exception as exc:
        log.warning("falha em %s: %s", getattr(fn, "__name__", "busca"), exc, exc_info=True)
        return Result.from_exception(exc)
    if isinstance(value, Result):
        return value
    if empty_is_error and not value:
        return Result.failure(EMPTY)
    return Result.success(value)


def response_meta(resp) -> dict:
    """Extrai 'stale' e 'age_seconds' dos cabeçalhos do cache HTTP."""
    try:
        from core.http_cache import is_stale, response_age_seconds

        return {"stale": is_stale(resp), "age_seconds": response_age_seconds(resp)}
    except Exception:
        return {"stale": False, "age_seconds": 0}
