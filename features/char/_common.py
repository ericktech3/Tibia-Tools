"""Imports e peças visuais compartilhadas pela parte de personagem."""
# flake8: noqa
from __future__ import annotations

import math
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime, timedelta

import requests
from kivy.clock import Clock
from kivy.metrics import dp

try:
    from kivy.graphics import Color, RoundedRectangle
except Exception:  # pragma: no cover - test fallback
    Color = RoundedRectangle = None

try:
    from kivy.uix.behaviors import ButtonBehavior
except Exception:  # pragma: no cover - test fallback when Kivy UI modules are stubbed
    class ButtonBehavior:
        pass

try:
    from kivymd.uix.boxlayout import MDBoxLayout
except Exception:  # pragma: no cover - test fallback
    class MDBoxLayout:
        def __init__(self, *args, **kwargs):
            self.children = []
            self.canvas = type("_DummyCanvas", (), {"before": []})()
            for k, v in kwargs.items():
                setattr(self, k, v)

        def add_widget(self, widget):
            self.children.append(widget)

        def bind(self, **kwargs):
            return None

        def setter(self, name):
            def _set(_, value):
                setattr(self, name, value)
            return _set

try:
    from kivymd.uix.label import MDIcon, MDLabel
except Exception:  # pragma: no cover - test fallback
    class _DummyLabel:
        def __init__(self, *args, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.children = []

        def add_widget(self, widget):
            self.children.append(widget)

        def bind(self, **kwargs):
            return None

    MDIcon = MDLabel = _DummyLabel

try:
    from kivymd.uix.list import OneLineIconListItem, TwoLineIconListItem, IconLeftWidget
except Exception:  # pragma: no cover - test fallback
    class _DummyListItem:
        def __init__(self, text="", secondary_text="", **kwargs):
            self.text = text
            self.secondary_text = secondary_text
            self.children = []
            self._bindings = {}
            for k, v in kwargs.items():
                setattr(self, k, v)

        def add_widget(self, widget):
            self.children.append(widget)

        def bind(self, **kwargs):
            self._bindings.update(kwargs)

    class _DummyIconLeftWidget:
        def __init__(self, icon="", **kwargs):
            self.icon = icon
            for k, v in kwargs.items():
                setattr(self, k, v)

    OneLineIconListItem = TwoLineIconListItem = _DummyListItem
    IconLeftWidget = _DummyIconLeftWidget

try:
    from kivymd.uix.menu import MDDropdownMenu
except Exception:  # pragma: no cover - test fallback
    class MDDropdownMenu:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.opened = False

        def open(self):
            self.opened = True

        def dismiss(self):
            self.opened = False

try:
    from kivymd.uix.progressbar import MDProgressBar
except Exception:  # pragma: no cover - test fallback
    class MDProgressBar:
        def __init__(self, *args, **kwargs):
            self.value = kwargs.get("value", 0)
            for k, v in kwargs.items():
                setattr(self, k, v)

try:
    from kivymd.uix.widget import MDWidget
except Exception:  # pragma: no cover - test fallback
    class MDWidget:
        def __init__(self, *args, **kwargs):
            self.children = []

        def add_widget(self, widget):
            self.children.append(widget)

from features.char import xp_stats as _xp_stats
from integrations.tibiadata import (
    fetch_character_tibiadata,
    fetch_guildstats_deaths_xp,
    fetch_guildstats_exp_changes,
)
from integrations.tibia_com import is_character_online_tibia_com
from integrations.tibiastalker import (
    build_stalker_character_url,
    extract_stalker_candidates,
    fetch_stalker_character,
)
from core.exp_loss import estimate_death_exp_lost
from services.error_reporting import log_current_exception


def _friendly_char_error(exc) -> str:
    """Mensagem amigavel (nunca deve levantar excecao)."""
    try:
        txt = str(exc or "").strip()
        resp = getattr(exc, "response", None)
        code = int(getattr(resp, "status_code", 0) or 0)
        if code == 404 or "nao encontrado" in txt.lower() or "não encontrado" in txt.lower():
            return "Personagem não encontrado."
        if code >= 500:
            return "Servidor de dados indisponível. Tente novamente."
        if "timeout" in txt.lower() or "timed out" in txt.lower():
            return "Tempo esgotado. Verifique sua internet."
        return f"Erro: {txt or type(exc).__name__}"
    except Exception:
        return "Erro ao buscar personagem."


class _StalkerCandidateItem(ButtonBehavior, MDBoxLayout):
    pass


class _StalkerBadge(MDBoxLayout):
    def __init__(self, text="", bg_color=(0.2, 0.2, 0.2, 1), text_color=(1, 1, 1, 1), **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("height", dp(28))
        kwargs.setdefault("padding", (dp(10), 0, dp(10), 0))
        super().__init__(**kwargs)
        self.adaptive_width = True
        self.spacing = dp(4)
        self._badge_bg_color = bg_color
        self._badge_radius = dp(13)
        self._bg_instr = None
        self._bg_rect = None

        if Color is not None and RoundedRectangle is not None and hasattr(self, "canvas"):
            try:
                with self.canvas.before:
                    self._bg_instr = Color(*bg_color)
                    self._bg_rect = RoundedRectangle(pos=getattr(self, "pos", (0, 0)), size=getattr(self, "size", (0, 0)), radius=[self._badge_radius] * 4)
                self.bind(pos=self._sync_bg, size=self._sync_bg)
            except Exception:
                self._bg_instr = None
                self._bg_rect = None

        self._label = MDLabel(
            text=f"[b]{text}[/b]",
            markup=True,
            halign="center",
            valign="middle",
            theme_text_color="Custom",
            text_color=text_color,
            size_hint=(None, None),
            adaptive_size=True,
        )
        self.add_widget(self._label)

    def _sync_bg(self, *_):
        if self._bg_rect is not None:
            try:
                self._bg_rect.pos = self.pos
                self._bg_rect.size = self.size
            except Exception:
                return None
        return None
