"""Boosted Creature/Boss do dia.

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


class BoostedControllerMixin:
    def update_boosted(self, silent: bool = False, force: bool = False):
        """Atualiza Boosted Creature/Boss sem travar a UI.

        IMPORTANTE: em versões anteriores havia um loop de refresh que criava
        threads infinitas e deixava o app lento. Aqui adicionamos:
        - in-flight guard (não iniciar outro worker se já existe um rodando)
        - throttling (em updates silenciosos, não fazer fetch em sequência)
        """
        scr = self.root.get_screen("boosted")

        # Evita disparar vários downloads em cascata (principal causa do "travamento")
        now_mono = time.monotonic()
        min_interval = 90.0 if silent else 0.0  # silencioso: no máx. ~1x por 90s
        try:
            with self._boosted_lock:
                if self._boosted_inflight:
                    return
                if (not force) and min_interval and (now_mono - float(self._boosted_last_fetch_mono or 0.0) < min_interval):
                    return
                self._boosted_inflight = True
                self._boosted_last_fetch_mono = now_mono
        except Exception:
            # se por algum motivo o lock falhar, ainda tentamos seguir
            pass

        if not silent:
            scr.ids.boost_status.text = "Atualizando..."
        else:
            # não suja o status se for atualização usada pelo dashboard
            if not (scr.ids.boost_status.text or "").strip():
                scr.ids.boost_status.text = "Atualizando..."
        try:
            scr.ids.boost_loading.opacity = 1
        except Exception:
            pass

        def run():
            try:
                res = fetch_boosted_result()
            except Exception as e:  # rede de segurança
                res = _Result.from_exception(e)

            def finish(*_):
                # libera o in-flight guard SEMPRE (sucesso ou erro)
                try:
                    with self._boosted_lock:
                        self._boosted_inflight = False
                except Exception:
                    pass
                try:
                    scr.ids.boost_loading.opacity = 0
                except Exception:
                    pass

                if not res.ok:
                    if not silent:
                        try:
                            scr.ids.boost_status.text = res.user_message()
                        except Exception:
                            pass
                    return

                self._boosted_done(res.data, silent=silent)
                if res.stale:
                    try:
                        scr.ids.boost_status.text = f"Sem internet — dados de {res.age_text()}"
                    except Exception:
                        pass

            Clock.schedule_once(finish, 0)

        threading.Thread(target=run, daemon=True).start()

    def _boosted_done(self, data, silent: bool = False):
        scr = self.root.get_screen("boosted")
        if not data:
            if not silent:
                scr.ids.boost_status.text = "Falha ao buscar Boosted."
            return
        scr.ids.boost_status.text = "OK"
        scr.ids.boost_creature.text = data.get("creature", "N/A")
        scr.ids.boost_boss.text = data.get("boss", "N/A")

        # sprites (quando disponíveis)
        try:
            if "boost_creature_sprite" in scr.ids:
                scr.ids.boost_creature_sprite.source = data.get("creature_image") or ""
            if "boost_boss_sprite" in scr.ids:
                scr.ids.boost_boss_sprite.source = data.get("boss_image") or ""
        except Exception:
            pass

        # cache + histórico (7 dias)
        try:
            self._cache_set("boosted", data)
        except Exception:
            pass

        # também atualiza o card do Dashboard (Home)
        try:
            home = self.root.get_screen("home")
            hids = home.ids
            if "dash_boost_creature" in hids:
                hids.dash_boost_creature.text = data.get("creature", "-") or "-"
            if "dash_boost_boss" in hids:
                hids.dash_boost_boss.text = data.get("boss", "-") or "-"
            if "dash_boost_creature_sprite" in hids:
                hids.dash_boost_creature_sprite.source = data.get("creature_image") or ""
            if "dash_boost_boss_sprite" in hids:
                hids.dash_boost_boss_sprite.source = data.get("boss_image") or ""
            ts = self.cache.get("boosted", {}).get("ts", "")
            if "dash_boost_updated" in hids:
                hids.dash_boost_updated.text = f"Atualizado: {ts.split('T')[0] if ts else ''}"
        except Exception:
            pass


        try:
            hist = self._prefs_get("boosted_history", []) or []
            if not isinstance(hist, list):
                hist = []
            today = datetime.utcnow().date().isoformat()
            entry = {"date": today, "creature": data.get("creature"), "boss": data.get("boss")}
            # remove do mesmo dia e reinsere no topo
            hist = [h for h in hist if isinstance(h, dict) and h.get("date") != today]
            hist.insert(0, entry)
            hist = hist[:7]
            self._prefs_set("boosted_history", hist)
        except Exception:
            pass

        # UI: histórico
        try:
            if "boost_hist_list" in scr.ids:
                scr.ids.boost_hist_list.clear_widgets()
                hist = self._prefs_get("boosted_history", []) or []
                if isinstance(hist, list) and hist:
                    for h in hist:
                        if not isinstance(h, dict):
                            continue
                        dt = str(h.get("date") or "")
                        cr = str(h.get("creature") or "-")
                        bb = str(h.get("boss") or "-")
                        it = TwoLineIconListItem(text=f"{dt}", secondary_text=f"{cr} • {bb}")
                        it.add_widget(IconLeftWidget(icon="history"))
                        scr.ids.boost_hist_list.add_widget(it)
        except Exception:
            pass

        # notificação 1x ao dia se mudou
        try:
            if bool(self._prefs_get("notify_boosted", True)):
                today = datetime.utcnow().date().isoformat()
                last_date = str(self._prefs_get("boosted_notified_date", "") or "")
                last_seen = self._prefs_get("boosted_last_seen", {}) or {}
                changed = (isinstance(last_seen, dict) and (last_seen.get("creature") != data.get("creature") or last_seen.get("boss") != data.get("boss")))
                if changed and last_date != today:
                    self._prefs_set("boosted_notified_date", today)
                    self._send_notification("Boosted mudou", f"{data.get('creature','-')} • {data.get('boss','-')}")
                self._prefs_set("boosted_last_seen", data)
        except Exception:
            pass

        # NÃO chamar dashboard_refresh() aqui.
        # O _boosted_done já atualiza diretamente os widgets do Dashboard e chamar
        # dashboard_refresh() cria um ciclo indireto (e era a principal causa de
        # travamentos/threads em cascata em Android).
