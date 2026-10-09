from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from types import TracebackType
from typing import Optional

CRASH_FILE_NAME = "tibia_tools_crash.log"


def _try_android_app_storage() -> str | None:
    try:
        from android.storage import app_storage_path  # type: ignore
    except ImportError:
        return None
    except Exception:
        return None

    try:
        path = app_storage_path()
    except Exception:
        return None

    if not path:
        return None
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return None
    return str(path)


def _try_running_app_data_dir() -> str | None:
    try:
        from kivy.app import App  # type: ignore
    except ImportError:
        return None
    except Exception:
        return None

    try:
        app = App.get_running_app()
    except Exception:
        return None

    data_dir = getattr(app, "user_data_dir", None) if app else None
    if not data_dir:
        return None
    try:
        os.makedirs(str(data_dir), exist_ok=True)
    except OSError:
        return None
    return str(data_dir)


def get_writable_dir() -> str:
    for candidate in (_try_android_app_storage(), _try_running_app_data_dir()):
        if candidate:
            return candidate
    # Nunca grava na pasta do projeto (evita log versionado sem querer).
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "tibia_tools")
    try:
        os.makedirs(d, exist_ok=True)
        return d
    except OSError:
        return tempfile.gettempdir()


def get_crash_file_path(filename: str = CRASH_FILE_NAME) -> str:
    return str(Path(get_writable_dir()) / filename)


MAX_LOG_BYTES = 512 * 1024  # acima disso o log antigo vira .old (não cresce para sempre)
MAX_OLD_AGE = 14 * 24 * 3600  # o .old é apagado depois de 14 dias

# ---- Política de privacidade do log ----------------------------------------
# O log é só local. Ele nunca é enviado para lugar nenhum automaticamente;
# o usuário pode compartilhá-lo manualmente pelas Configurações.
# Antes de gravar, removemos: parâmetros de URL (nomes pesquisados), nomes em
# caminhos de personagem e o nome da pasta do usuário no computador.
import re as _re

_RE_QUERY = _re.compile(r"(https?://[^\s?#'\"]+)\?[^\s'\"]*")
_RE_CHAR_PATH = _re.compile(
    r"(/(?:characters?|character|guilds?|guild|highscores|nick)/)([^/\s?'\"]+)", _re.I)
_RE_NAME_PARAM = _re.compile(r"\b(nick|name|character|char|player)=([^&\s'\"]+)", _re.I)
# Pastas de usuário (Linux/macOS/Windows, com \ ou /). O nome pode ter espaços
# no Windows, então vai até a próxima barra.
_RE_HOME = _re.compile(r"(/home/|/Users/)([^/\\\s]+)|([A-Za-z]:[\\/]+Users[\\/]+)([^\\/\r\n]+)", _re.I)


def redact(text: str) -> str:
    """Remove dados pessoais/pesquisados de um texto de log."""
    if not text:
        return text
    try:
        out = _RE_QUERY.sub(r"\1?<…>", text)
        out = _RE_NAME_PARAM.sub(r"\1=<…>", out)
        out = _RE_CHAR_PATH.sub(r"\1<…>", out)
        out = _RE_HOME.sub(lambda m: (m.group(1) or m.group(3)) + "<user>", out)
        return out
    except Exception:
        return text


def _old_file(crash_file: Path) -> Path:
    return crash_file.with_suffix(crash_file.suffix + ".old")


def _rotate_if_needed(crash_file: Path) -> None:
    try:
        old = _old_file(crash_file)
        if old.exists() and (__import__("time").time() - old.stat().st_mtime) > MAX_OLD_AGE:
            old.unlink()
        if crash_file.exists() and crash_file.stat().st_size > MAX_LOG_BYTES:
            os.replace(crash_file, old)
    except OSError:
        pass


def read_crash_log(max_chars: int = 60_000, filename: str = CRASH_FILE_NAME) -> str:
    """Texto do log (já sem dados pessoais) para o usuário compartilhar."""
    parts = []
    base = Path(get_crash_file_path(filename))
    for f in (_old_file(base), base):
        try:
            if f.exists():
                parts.append(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    text = redact("".join(parts))
    return text[-max_chars:] if len(text) > max_chars else text


def delete_crash_log(filename: str = CRASH_FILE_NAME) -> None:
    base = Path(get_crash_file_path(filename))
    for f in (base, _old_file(base)):
        try:
            f.unlink()
        except OSError:
            pass


def write_crash_log(text: str, *, filename: str = CRASH_FILE_NAME) -> None:
    if text is None:
        return
    try:
        import time as _time
        crash_file = Path(get_crash_file_path(filename))
        crash_file.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed(crash_file)
        stamp = _time.strftime("%Y-%m-%d %H:%M:%S")
        text = redact(text)
        payload = text if text.endswith("\n") else f"{text}\n"
        with crash_file.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {payload}")
    except OSError:
        pass


def log_current_exception(*, prefix: str | None = None, filename: str = CRASH_FILE_NAME) -> None:
    text = traceback.format_exc()
    if prefix:
        text = f"{prefix}\n{text}"
    write_crash_log(text, filename=filename)


def install_excepthook(target_sys=None) -> None:
    module_sys = target_sys or sys
    default_hook = getattr(module_sys, "__excepthook__", None)

    def _hook(exc_type: type[BaseException], exc: BaseException, tb: Optional[TracebackType]) -> None:
        write_crash_log("".join(traceback.format_exception(exc_type, exc, tb)))
        if callable(default_hook):
            default_hook(exc_type, exc, tb)

    module_sys.excepthook = _hook

    # Erros em threads de fundo (buscas na internet) também vão para o log.
    try:
        import threading

        def _thread_hook(args) -> None:
            if args.exc_type is SystemExit:
                return
            name = getattr(args.thread, "name", "?")
            write_crash_log(f"[thread {name}]\n" + "".join(
                traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))

        threading.excepthook = _thread_hook
    except Exception:
        pass

    install_logging_handler()


def install_logging_handler(level: int | None = None) -> None:
    import logging

    root = logging.getLogger("tibia_tools")
    if any(getattr(h, "_tt_crash", False) for h in root.handlers):
        return

    class _Handler(logging.Handler):
        _tt_crash = True

        def emit(self, record):
            try:
                write_crash_log(self.format(record))
            except Exception:
                pass

    h = _Handler(level or logging.WARNING)
    h.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(h)
    root.setLevel(logging.INFO)
