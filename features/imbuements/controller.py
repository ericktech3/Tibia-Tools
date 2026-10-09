"""Imbuements: lista, favoritos e detalhes.

Extraído do main.py sem mudar comportamento. Os métodos rodam como parte do
app (mixin), então `self` é o TibiaToolsApp.
"""
# flake8: noqa
import os
import sys
import json
import re
import threading
import time
import urllib.parse
import webbrowser
import traceback
import math
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from typing import List, Optional
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import StringProperty, NumericProperty
from kivy.uix.screenmanager import ScreenManager
from kivy.utils import platform
from kivy.uix.behaviors import ButtonBehavior

from kivymd.app import MDApp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRectangleFlatIconButton
from kivymd.uix.list import (
    OneLineIconListItem,
    OneLineListItem,
    TwoLineIconListItem,
    IconLeftWidget,
)
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.behaviors import RectangularRippleBehavior
from kivymd.uix.scrollview import MDScrollView
_CORE_IMPORT_ERROR = None
try:
    from integrations.tibiadata import (
        fetch_character_tibiadata,
        fetch_worlds_tibiadata,
        is_character_online_tibiadata,
        fetch_guildstats_deaths_xp,
        fetch_guildstats_exp_changes,
    )
    from integrations.tibia_com import is_character_online_tibia_com, fetch_last_login_dt, parse_tibia_datetime
    from integrations.exevopan import fetch_exevopan_bosses, fetch_exevopan_result
    from core.exp_loss import estimate_death_exp_lost
    from core.storage import get_data_dir, safe_read_json, safe_write_json
    from core.boosted import fetch_boosted, fetch_boosted_result
    from core.result import Result as _Result
    from features.bosses import logic as _boss_logic
    from core.training import TrainingInput, compute_training_plan
    from core.hunt import parse_hunt_session_text
    from core.imbuements import fetch_imbuements_table, fetch_imbuement_details, ImbuementEntry
    from core.stamina import parse_hm_text, compute_offline_regen, format_hm
except Exception:
    _CORE_IMPORT_ERROR = traceback.format_exc()

from services.error_reporting import log_current_exception


class ImbuementsControllerMixin:
    def imbuement_is_favorite(self, name: str) -> bool:
        favs = self._prefs_get("imb_favorites", []) or []
        if not isinstance(favs, list):
            favs = []
        return (name or "").strip() in favs

    def imbuement_toggle_favorite(self, name: str) -> bool:
        name = (name or "").strip()
        favs = self._prefs_get("imb_favorites", []) or []
        if not isinstance(favs, list):
            favs = []
        if name in favs:
            favs.remove(name)
            self._prefs_set("imb_favorites", favs)
            return False
        favs.append(name)
        self._prefs_set("imb_favorites", favs)
        return True

    def open_imb_tier_menu(self):
        scr = self.root.get_screen("imbuements")
        caller = scr.ids.get("imb_tier_btn")
        if caller is None:
            return
        options = ["All", "Basic", "Intricate", "Powerful"]
        items = [{"text": opt, "on_release": (lambda x=opt: self._set_imb_tier(x))} for opt in options]
        if self._menu_imb_tier:
            self._menu_imb_tier.dismiss()
        self._menu_imb_tier = MDDropdownMenu(caller=caller, items=items, width_mult=4, max_height=dp(220))
        self._menu_imb_tier.open()

    def _set_imb_tier(self, value: str):
        self._prefs_set("imb_tier", value)
        try:
            scr = self.root.get_screen("imbuements")
            scr.ids.imb_tier_label.text = value
        except Exception:
            pass
        if self._menu_imb_tier:
            self._menu_imb_tier.dismiss()
        self.imbuements_refresh_list()

    def imbuements_toggle_fav_only(self):
        cur = bool(self._prefs_get("imb_fav_only", False))
        cur = not cur
        self._prefs_set("imb_fav_only", cur)
        try:
            scr = self.root.get_screen("imbuements")
            scr.ids.imb_fav_toggle.icon = "star" if cur else "star-outline"
        except Exception:
            pass
        self.imbuements_refresh_list()

    def imbuements_copy_selected_hint(self):
        self.toast("Abra um imbuement e use o botão COPIAR no dialog.")

    def _imbuements_load(self):
        scr = self.root.get_screen("imbuements")
        scr.entries = []
        scr.ids.imb_status.text = "Carregando (offline)..."
        scr.ids.imb_list.clear_widgets()

        def run():
            ok, data = fetch_imbuements_table()
            Clock.schedule_once(lambda *_: self._imbuements_done(ok, data), 0)

        threading.Thread(target=run, daemon=True).start()

    def _imbuements_done(self, ok: bool, data):
        scr = self.root.get_screen("imbuements")
        if not ok:
            scr.ids.imb_status.text = f"Erro: {data}"
            return
        scr.entries = data
        scr.ids.imb_status.text = f"Imbuements: {len(data)}"
        try:
            scr.ids.imb_tier_label.text = str(self._prefs_get("imb_tier", "All") or "All")
            scr.ids.imb_fav_toggle.icon = "star" if bool(self._prefs_get("imb_fav_only", False)) else "star-outline"
        except Exception:
            pass
        self.imbuements_refresh_list()

    def imbuements_refresh_list(self):
        scr = self.root.get_screen("imbuements")
        q = (scr.ids.imb_search.text or "").strip().lower()
        tier = str(self._prefs_get("imb_tier", "All") or "All")
        fav_only = bool(self._prefs_get("imb_fav_only", False))
        favs = self._prefs_get("imb_favorites", []) or []
        if not isinstance(favs, list):
            favs = []

        scr.ids.imb_list.clear_widgets()
        entries: List[ImbuementEntry] = getattr(scr, "entries", [])

        def matches(ent: ImbuementEntry) -> bool:
            if q and q not in ent.name.lower():
                return False
            if fav_only and ent.name not in favs:
                return False
            if tier == "Basic" and not (ent.basic or "").strip():
                return False
            if tier == "Intricate" and not (ent.intricate or "").strip():
                return False
            if tier == "Powerful" and not (ent.powerful or "").strip():
                return False
            return True

        filtered = [e for e in entries if matches(e)]
        scr.ids.imb_status.text = f"Imbuements: {len(filtered)}"

        for e in filtered[:200]:
            icon = "star" if self.imbuement_is_favorite(e.name) else "flash"
            item = OneLineIconListItem(text=e.name)
            item.add_widget(IconLeftWidget(icon=icon))
            item.bind(on_release=lambda _item, ent=e: self._imbu_show(ent))
            scr.ids.imb_list.add_widget(item)

    def _imbu_show(self, ent: ImbuementEntry):
        # Abre primeiro com placeholder e depois carrega os itens (sob demanda)
        title = (ent.name or "").strip()

        def copy_now(*_):
            try:
                Clipboard.copy(getattr(dlg, "_last_text", "") or "")
                self.toast("Copiado.")
            except Exception:
                self.toast("Ainda não carregou.")

        def toggle_fav(*_):
            fav = self.imbuement_toggle_favorite(title)
            self.toast("Favoritado." if fav else "Removido dos favoritos.")
            try:
                dlg.dismiss()
            except Exception:
                pass
            self.imbuements_refresh_list()

        fav_txt = "REMOVER ⭐" if self.imbuement_is_favorite(title) else "FAVORITAR ⭐"

        dlg = MDDialog(
            title=title,
            text="Carregando detalhes...",
            buttons=[
                MDFlatButton(text=fav_txt, on_release=toggle_fav),
                MDFlatButton(text="COPIAR", on_release=copy_now),
                MDFlatButton(text="FECHAR", on_release=lambda *_: dlg.dismiss()),
            ],
        )
        dlg.open()

        def run():
            try:
                page = (ent.page or "").strip()
                if not page:
                    page = title.replace(" ", "_")

                ok, data = fetch_imbuement_details(page)
                if not ok:
                    msg = f"Erro ao carregar detalhes:\n{data}"
                    Clock.schedule_once(lambda *_: setattr(dlg, "text", msg), 0)
                    return

                tiers = data  # dict com basic/intricate/powerful

                def fmt(tkey: str, label: str) -> str:
                    tier = tiers.get(tkey, {}) if isinstance(tiers, dict) else {}

                    def clean(s: str) -> str:
                        # Converte sequências literais (ex.: "\\n") em quebras de linha reais
                        return (s or "").replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t").strip()

                    effect = clean(str(tier.get("effect", "")))
                    items = tier.get("items", []) or []

                    out_lines = [f"{label}:"]
                    if effect:
                        out_lines.append(f"Efeito: {effect}")
                    if items:
                        out_lines.append("Itens:")
                        for it in items[:50]:
                            out_lines.append(f"• {clean(str(it))}")
                    else:
                        out_lines.append("Itens: (não encontrado)")
                    return "\n".join(out_lines)

                text = (
                    fmt("basic", "Basic")
                    + "\n\n"
                    + fmt("intricate", "Intricate")
                    + "\n\n"
                    + fmt("powerful", "Powerful")
                    + "\n\n(Fonte: TibiaWiki BR)"
                )
                def _set_text(*_):
                    setattr(dlg, "text", text)
                    setattr(dlg, "_last_text", text)
                Clock.schedule_once(_set_text, 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, e=e: setattr(dlg, "text", f"Erro: {e}"), 0)

        threading.Thread(target=run, daemon=True).start()
