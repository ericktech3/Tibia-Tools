"""Tela Bosses (ExevoPan): filtros, favoritos, mundos e carregamento.

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


class BossesControllerMixin:
    def _boss_wiki_url(self, boss_name: str) -> str:
        """Gera URL do boss no TibiaWiki (BR)."""
        title = (boss_name or "").strip().replace(" ", "_")
        # index.php?title=... é o formato mais estável do MediaWiki.
        return f"https://tibiawiki.com.br/index.php?title={quote(title)}"

    def _boss_open_prompt(self, boss_name: str) -> None:
        """Pergunta ao usuário se quer abrir a página do boss."""
        boss_name = (boss_name or "").strip()
        if not boss_name:
            return

        def go(*_):
            try:
                webbrowser.open(self._boss_wiki_url(boss_name))
            finally:
                dlg.dismiss()

        dlg = MDDialog(
            title=boss_name,
            text="Quer abrir a página desse boss para ver os detalhes?",
            buttons=[
                MDFlatButton(text="ABRIR", on_release=go),
                MDFlatButton(text="CANCELAR", on_release=lambda *_: dlg.dismiss()),
            ],
        )
        dlg.open()


    def _boss_chance_score(self, chance: str) -> float:
        return _boss_logic.chance_score(chance)

    def boss_is_favorite(self, boss_name: str) -> bool:
        favs = self._prefs_get("boss_favorites", []) or []
        if not isinstance(favs, list):
            favs = []
        return (boss_name or "").strip() in favs

    def boss_toggle_favorite(self, boss_name: str) -> bool:
        boss_name = (boss_name or "").strip()
        favs = self._prefs_get("boss_favorites", []) or []
        if not isinstance(favs, list):
            favs = []
        if boss_name in favs:
            favs.remove(boss_name)
            self._prefs_set("boss_favorites", favs)
            return False
        favs.append(boss_name)
        # remove duplicados mantendo ordem
        seen = set()
        out = []
        for x in favs:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        self._prefs_set("boss_favorites", out)
        return True

    def bosses_toggle_fav_only(self):
        cur = _boss_logic.favorites_only_enabled(self._prefs_get("boss_fav_only", False))
        cur = not cur
        self._prefs_set("boss_fav_only", cur)
        try:
            scr = self.root.get_screen("bosses")
            if "boss_fav_toggle" in scr.ids:
                scr.ids.boss_fav_toggle.icon = "star" if cur else "star-outline"
        except Exception:
            pass
        self.bosses_apply_filters()

    def bosses_apply_filters_debounced(self):
        try:
            if self._bosses_filter_debounce_ev:
                self._bosses_filter_debounce_ev.cancel()
        except Exception:
            pass
        self._bosses_filter_debounce_ev = Clock.schedule_once(lambda *_: self.bosses_apply_filters(), 0.15)

    def open_boss_filter_menu(self):
        scr = self.root.get_screen("bosses")
        caller = scr.ids.get("boss_filter_btn")
        if caller is None:
            return
        options = ["All", "High", "Medium+", "Low+", "No chance", "Unknown"]
        items = [{"text": opt, "on_release": (lambda x=opt: self._set_boss_filter(x))} for opt in options]
        if self._menu_boss_filter:
            self._menu_boss_filter.dismiss()
        self._menu_boss_filter = MDDropdownMenu(caller=caller, items=items, width_mult=4, max_height=dp(320))
        self._menu_boss_filter.open()

    def _set_boss_filter(self, value: str):
        self._prefs_set("boss_filter", value)
        try:
            scr = self.root.get_screen("bosses")
            if "boss_filter_label" in scr.ids:
                scr.ids.boss_filter_label.text = value
        except Exception:
            pass
        if self._menu_boss_filter:
            self._menu_boss_filter.dismiss()
        self.bosses_apply_filters()

    def open_boss_sort_menu(self):
        scr = self.root.get_screen("bosses")
        caller = scr.ids.get("boss_sort_btn")
        if caller is None:
            return
        options = ["Chance", "Name", "Favorites first"]
        items = [{"text": opt, "on_release": (lambda x=opt: self._set_boss_sort(x))} for opt in options]
        if self._menu_boss_sort:
            self._menu_boss_sort.dismiss()
        self._menu_boss_sort = MDDropdownMenu(caller=caller, items=items, width_mult=4, max_height=dp(260))
        self._menu_boss_sort.open()

    def _set_boss_sort(self, value: str):
        self._prefs_set("boss_sort", value)
        try:
            scr = self.root.get_screen("bosses")
            if "boss_sort_label" in scr.ids:
                scr.ids.boss_sort_label.text = value
        except Exception:
            pass
        if self._menu_boss_sort:
            self._menu_boss_sort.dismiss()
        self.bosses_apply_filters()

    def open_boss_favorites(self):
        self.go("boss_favorites")
        self.boss_favorites_refresh()

    def bosses_open_dialog(self, boss_dict):
        """Dialog de ações do boss (favoritar/copiar/abrir) com layout que não quebra em telas pequenas."""
        try:
            name = str(boss_dict.get("boss") or boss_dict.get("name") or "Boss").strip()
            chance = str(boss_dict.get("chance") or "").strip()
            status = str(boss_dict.get("status") or "").strip()
        except Exception:
            return

        url = self._boss_wiki_url(name)
        is_fav = self.boss_is_favorite(name)

        txt = "\n".join([x for x in [f"Chance: {chance}" if chance else "", status] if x]).strip() or " "

        # Conteúdo (texto + ações em lista) — evita estourar/ficar “fora” do dialog
        content = MDBoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        lbl = MDLabel(text=txt, theme_text_color="Secondary", size_hint_y=None)
        lbl.bind(texture_size=lambda inst, val: setattr(inst, "height", val[1] + dp(6)))
        content.add_widget(lbl)

        def close(*_):
            try:
                dlg.dismiss()
            except Exception:
                pass

        def toggle(*_):
            fav = self.boss_toggle_favorite(name)
            self.toast("Favoritado." if fav else "Removido dos favoritos.")
            close()
            self.bosses_apply_filters()
            self.dashboard_refresh()

        def copy(*_):
            try:
                Clipboard.copy(url)
                self.toast("Link copiado.")
            except Exception:
                self.toast("Não consegui copiar.")
            close()

        def open_url(*_):
            try:
                webbrowser.open(url)
            except Exception:
                self.toast("Não consegui abrir o navegador.")
            close()

        actions = [
            (("Remover dos favoritos" if is_fav else "Adicionar aos favoritos"), ("star" if is_fav else "star-outline"), toggle),
            ("Copiar link", "content-copy", copy),
            ("Abrir no navegador", "open-in-new", open_url),
        ]

        for label, icon, cb in actions:
            it = OneLineIconListItem(text=label)
            it.add_widget(IconLeftWidget(icon=icon))
            it.bind(on_release=cb)
            content.add_widget(it)

        dlg = MDDialog(
            title=name,
            type="custom",
            content_cls=content,
            buttons=[MDFlatButton(text="FECHAR", on_release=close)],
        )
        dlg.open()

    def bosses_apply_filters(self):
        scr = self.root.get_screen("bosses")
        bosses = getattr(scr, "bosses_raw", []) or []
        if not isinstance(bosses, list):
            bosses = []

        q = ""
        if "boss_search" in scr.ids:
            q = (scr.ids.boss_search.text or "").strip().lower()

        bf = str(self._prefs_get("boss_filter", "All") or "All")
        bs = str(self._prefs_get("boss_sort", "Chance") or "Chance")
        fav_only = _boss_logic.favorites_only_enabled(self._prefs_get("boss_fav_only", False))
        favs = self._prefs_get("boss_favorites", []) or []
        if not isinstance(favs, list):
            favs = []

        if fav_only and not favs:
            # Evita uma lista vazia permanente por uma preferência antiga.
            fav_only = False
            self._prefs_set("boss_fav_only", False)

        filtered = _boss_logic.filter_and_sort(
            bosses, query=q, chance_filter=bf, sort=bs, favorites=favs, fav_only=fav_only,
        )

        # Sincroniza o estado visível também ao receber dados do cache.
        if "boss_fav_toggle" in scr.ids:
            scr.ids.boss_fav_toggle.icon = "star" if fav_only else "star-outline"
        if "boss_filter_label" in scr.ids:
            scr.ids.boss_filter_label.text = bf + (" • Só favoritos" if fav_only else "")
        if "boss_sort_label" in scr.ids:
            scr.ids.boss_sort_label.text = bs
        scr.ids.boss_list.clear_widgets()
        scr.ids.boss_status.text = f"Bosses: {len(filtered)} (de {len(bosses)})"

        if not filtered:
            message = ("Nenhum favorito neste mundo. Toque na estrela para ver todos."
                       if fav_only else "Nada encontrado com esses filtros.")
            item = self._build_wrapped_info_row(message, icon="magnify")
            item.bind(on_release=lambda *_: self.bosses_toggle_fav_only() if fav_only else None)
            scr.ids.boss_list.add_widget(item)
            return

        for b in filtered[:200]:
            name = str(b.get("boss") or b.get("name") or "Boss")
            item = TwoLineIconListItem(text=name, secondary_text=_boss_logic.secondary_text(b))
            icon = "star" if self.boss_is_favorite(name) else "skull"
            item.add_widget(IconLeftWidget(icon=icon))
            item.bind(on_release=lambda _it, bb=b: self.bosses_open_dialog(bb))
            scr.ids.boss_list.add_widget(item)

    def boss_favorites_refresh(self):
        scr = self.root.get_screen("boss_favorites")
        favs = self._prefs_get("boss_favorites", []) or []
        if not isinstance(favs, list):
            favs = []
        scr.ids.boss_fav_list.clear_widgets()
        if not favs:
            scr.ids.boss_fav_status.text = "Sem favoritos. Favorite bosses na tela Bosses."
            it = OneLineIconListItem(text="Sem favoritos ainda.")
            it.add_widget(IconLeftWidget(icon="star-outline"))
            scr.ids.boss_fav_list.add_widget(it)
            return

        world = str(self._prefs_get("boss_last_world", "") or "")
        cache_key = f"bosses:{world.lower()}" if world else ""
        bosses = self._cache_get(cache_key, ttl_seconds=6 * 3600) if cache_key else None

        scr.ids.boss_fav_status.text = f"Favoritos: {len(favs)}" + (f" • World: {world}" if world else "")
        for name in favs[:200]:
            chance_txt = ""
            if isinstance(bosses, list):
                for b in bosses:
                    if str(b.get("boss") or b.get("name") or "") == name:
                        chance_txt = str(b.get("chance") or "").strip()
                        break
            item = OneLineIconListItem(text=f"{name}{(' ('+chance_txt+')') if chance_txt else ''}")
            item.add_widget(IconLeftWidget(icon="star"))
            item.bind(on_release=lambda _it, n=name: self.bosses_open_dialog({"boss": n, "chance": chance_txt}))
            scr.ids.boss_fav_list.add_widget(item)

    def _bosses_refresh_worlds(self):
        scr = self.root.get_screen("bosses")
        scr.ids.boss_status.text = "Carregando worlds..."

        def worker():
            data = fetch_worlds_tibiadata()
            return sorted([w.get("name") for w in data.get("worlds", {}).get("regular_worlds", []) if w.get("name")])

        def done(worlds):
            """Update Bosses world list/menu on the main thread.

            Defensive: exceptions here can hard-crash some Android/Kivy builds.
            """
            try:
                if worlds is None:
                    worlds = []
                elif not isinstance(worlds, (list, tuple)):
                    try:
                        worlds = list(worlds)
                    except Exception:
                        worlds = []

                if "boss_status" in scr.ids:
                    scr.ids.boss_status.text = f"Worlds: {len(worlds)}"

                # Restore last selected world (if field exists)
                field = getattr(scr.ids, "world_field", None)
                try:
                    last = str(self._prefs_get("boss_last_world", "") or "").strip()
                    if field is not None and last:
                        field.text = last
                except Exception:
                    pass

                arrow = getattr(scr.ids, "world_drop", None)
                row = getattr(scr.ids, "world_row", None)
                caller = row or field or arrow
                if caller is None:
                    return

                # Build dropdown items (cap to avoid very tall/heavy menus)
                items = [
                    {"text": w, "on_release": (lambda x=w: self._select_world(x))}
                    for w in (worlds or [])[:400]
                ]

                # Recreate menu safely
                if getattr(self, "_menu_world", None):
                    try:
                        self._menu_world.dismiss()
                    except Exception:
                        pass

                from kivymd.uix.menu import MDDropdownMenu
                from kivy.metrics import dp

                base_w = getattr(caller, "width", 0) or dp(280)
                menu_w = max(dp(220), min(dp(360), base_w))

                # Build the dropdown menu. Some KivyMD builds differ in supported kwargs,
                # so we try the more complete config first and fall back if needed.
                try:
                    self._menu_world = MDDropdownMenu(
                        caller=caller,
                        items=items,
                        width=menu_w,
                        max_height=dp(420),
                        position="auto",
                        border_margin=dp(12),
                    )
                except TypeError:
                    self._menu_world = MDDropdownMenu(
                        caller=caller,
                        items=items,
                        width=menu_w,
                        max_height=dp(420),
                    )

                # Extra safety: force the menu to grow inside the screen when supported.
                try:
                    if hasattr(self._menu_world, "hor_growth"):
                        self._menu_world.hor_growth = "right"
                    if hasattr(self._menu_world, "ver_growth"):
                        self._menu_world.ver_growth = "down"
                except Exception:
                    pass

            except Exception:
                try:
                    from kivy.logger import Logger
                    Logger.exception("Bosses: failed to build worlds menu")
                except Exception:
                    pass
        def run():
            try:
                worlds = worker()
                Clock.schedule_once(lambda *_: done(worlds), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, e=e: setattr(scr.ids.boss_status, "text", f"Erro: {e}"), 0)

        threading.Thread(target=run, daemon=True).start()



    def open_world_menu(self):
        # Open the World dropdown and keep it inside screen bounds.
        try:
            from kivy.metrics import dp

            screen = self.root.get_screen("bosses")
            field = getattr(screen.ids, "world_field", None)
            arrow = getattr(screen.ids, "world_drop", None)
            row = getattr(screen.ids, "world_row", None)
            caller = row or field or arrow
            if not self._menu_world or not caller:
                return

            # Width: prefer the full row width (field + arrow), clamped to screen.
            w = getattr(caller, "width", 0) or 0
            if w <= 1 and field is not None:
                w = field.width
            w = max(dp(240), min(w, self.root.width - dp(32)))

            # Height: avoid going behind bottom bar.
            max_h = min(dp(360), max(dp(160), self.root.height - dp(260)))

            try:
                self._menu_world.caller = caller
                self._menu_world.width = w
                self._menu_world.max_height = max_h

                # Keep a margin from the screen edges.
                try:
                    if hasattr(self._menu_world, "border_margin"):
                        self._menu_world.border_margin = dp(12)
                except Exception:
                    pass

                # Force growth to the right to avoid negative X on some layouts.
                if hasattr(self._menu_world, "hor_growth"):
                    self._menu_world.hor_growth = "right"
                if hasattr(self._menu_world, "ver_growth"):
                    self._menu_world.ver_growth = "down"
                if hasattr(self._menu_world, "position"):
                    self._menu_world.position = "auto"
            except Exception:
                pass

            self._menu_world.open()

            # Final safety clamp (some Android devices ignore border_margin/hor_growth).
            try:
                from kivy.core.window import Window
                from kivy.clock import Clock

                def _clamp_menu_pos(*_a):
                    try:
                        margin = dp(8)
                        target = None
                        # KivyMD may expose the visible container as `menu`.
                        if hasattr(self._menu_world, "menu"):
                            target = self._menu_world.menu
                        elif hasattr(self._menu_world, "_menu"):
                            target = self._menu_world._menu
                        else:
                            target = self._menu_world

                        if not hasattr(target, "x") or not hasattr(target, "width"):
                            return
                        # Clamp X inside the window.
                        max_x = Window.width - target.width - margin
                        if max_x < margin:
                            return
                        target.x = max(margin, min(target.x, max_x))
                    except Exception:
                        pass

                Clock.schedule_once(_clamp_menu_pos, 0)
            except Exception:
                pass
        except Exception:
            pass

    def _select_world(self, world: str):
        scr = self.root.get_screen("bosses")
        scr.ids.world_field.text = world
        try:
            self._prefs_set("boss_last_world", world)
        except Exception:
            pass
        if self._menu_world:
            self._menu_world.dismiss()

    def _boss_loading(self, on: bool):
        try:
            bar = self.root.get_screen("bosses").ids.boss_loading
            bar.opacity = 1 if on else 0
            bar.start() if on else bar.stop()
        except Exception:
            pass

    def bosses_auto_load(self):
        """Ao abrir a tela, busca sozinho o último world usado."""
        try:
            scr = self.root.get_screen("bosses")
            if not (scr.ids.world_field.text or "").strip():
                scr.ids.world_field.text = str(self._prefs_get("boss_last_world", "") or "")
            if (scr.ids.world_field.text or "").strip() and not getattr(scr, "_loading", False):
                self.bosses_fetch(silent=True)
        except Exception:
            pass

    def bosses_fetch(self, force: bool = False, silent: bool = False):
        scr = self.root.get_screen("bosses")
        world = (scr.ids.world_field.text or "").strip()
        if not world:
            if not silent:
                self.toast("Digite o world.")
            return
        if getattr(scr, "_loading", False):
            return
        scr._loading = True
        self._boss_loading(True)
        if force:
            try:
                from core.http_cache import clear as _clear_http
                _clear_http()
            except Exception:
                pass

        try:
            self._prefs_set("boss_last_world", world)
        except Exception:
            pass
        scr.ids.boss_status.text = "Buscando bosses..."
        scr.ids.boss_list.clear_widgets()
        for _ in range(6):
            it = OneLineIconListItem(text="Carregando...")
            it.add_widget(IconLeftWidget(icon="cloud-download"))
            scr.ids.boss_list.add_widget(it)


        def run():
            try:
                res = fetch_exevopan_result(world)
            except Exception as e:  # rede de segurança: nunca derruba o app
                res = _Result.from_exception(e)
            Clock.schedule_once(lambda *_: self._bosses_result(res), 0)

            def _end(*_):
                scr._loading = False
                self._boss_loading(False)
            Clock.schedule_once(_end, 0)

        threading.Thread(target=run, daemon=True).start()

    def _bosses_result(self, res):
        scr = self.root.get_screen("bosses")
        if not res.ok:
            scr.ids.boss_list.clear_widgets()
            scr.ids.boss_status.text = res.user_message()
            return
        self._bosses_done(res.data)
        if res.stale:
            try:
                scr.ids.boss_status.text += f"  (sem internet — dados de {res.age_text()})"
            except Exception:
                pass

    def _bosses_done(self, bosses):
        scr = self.root.get_screen("bosses")
        if not bosses:
            scr.ids.boss_list.clear_widgets()
            scr.ids.boss_status.text = "Nada encontrado (ou ExevoPan indisponível)."
            return

        # guarda raw para filtros e salva cache (TTL 6h)
        scr.bosses_raw = bosses
        world = (scr.ids.world_field.text or "").strip()
        if world:
            self._cache_set(f"bosses:{world.lower()}", bosses)

        # aplica prefs e UI labels
        try:
            if "boss_filter_label" in scr.ids:
                scr.ids.boss_filter_label.text = str(self._prefs_get("boss_filter", "All") or "All")
            if "boss_sort_label" in scr.ids:
                scr.ids.boss_sort_label.text = str(self._prefs_get("boss_sort", "Chance") or "Chance")
            if "boss_fav_toggle" in scr.ids:
                scr.ids.boss_fav_toggle.icon = "star" if _boss_logic.favorites_only_enabled(self._prefs_get("boss_fav_only", False)) else "star-outline"
        except Exception:
            pass

        self.bosses_apply_filters()
        self.dashboard_refresh()

    # --------------------
