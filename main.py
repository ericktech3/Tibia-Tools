# -*- coding: utf-8 -*-
"""
Tibia Tools (Android) - KivyMD app

Tabs: Char / Share XP / Favoritos / Mais
Mais -> telas internas: Bosses (ExevoPan), Boosted, Treino (Exercise), Imbuements, Hunt Analyzer
"""
from __future__ import annotations

try:
    from kivy.config import Config
    # Impede que o Kivy trate Back/Escape como fechamento automático do app.
    # No Android isso é essencial para que o botão/gesto Voltar passe pela navegação interna.
    Config.set("kivy", "exit_on_escape", "0")
except Exception:
    Config = None

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

try:
    from core.http_cache import install as _install_http_cache, configure_disk as _configure_http_disk
    _install_http_cache()  # cache + conexões reaproveitadas + retry
except Exception:
    _configure_http_disk = None

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

# ---- IMPORTS DO CORE (com proteção para não “fechar sozinho” no Android) ----
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

KV_FILE = "tibia_tools.kv"

from services.infrastructure import InfrastructureMixin
from services.persistence import PersistenceService
from services.android_bridge import AndroidBridgeService
from services.error_reporting import install_excepthook, log_current_exception
from features.char.controller import CharControllerMixin
from features.favorites.controller import FavoritesControllerMixin
from features.settings.controller import SettingsControllerMixin
from features.bosses.controller import BossesControllerMixin
from features.boosted.controller import BoostedControllerMixin
from features.training.controller import TrainingControllerMixin
from features.imbuements.controller import ImbuementsControllerMixin
from ui.kv_loader import load_root_kv


# --------------------
# Crash logging (Android-friendly)
# --------------------
install_excepthook(sys)



class RootSM(ScreenManager):
    pass


class MoreItem(OneLineIconListItem):
    icon = StringProperty("chevron-right")




class ClickableRow(RectangularRippleBehavior, ButtonBehavior, MDBoxLayout):
    """Linha clicável usada no Dashboard/Home."""
    pass


class TibiaToolsApp(
    CharControllerMixin,
    FavoritesControllerMixin,
    SettingsControllerMixin,
    BossesControllerMixin,
    BoostedControllerMixin,
    TrainingControllerMixin,
    ImbuementsControllerMixin,
    InfrastructureMixin,
    MDApp,
):
    # Altura da barra de status do Android (dp) — usada pelo StatusBarSpacer no KV
    status_bar_height_dp = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.favorites: List[str] = []

        # -----------------------------------------------------------------
        # Boosted fetch (ANTI-TRAVAMENTO)
        #
        # Havia um loop indireto:
        #   dashboard_refresh() -> update_boosted() -> _boosted_done() -> dashboard_refresh() -> ...
        # Isso gerava threads em cascata, uso alto de CPU/rede e UI “travando”,
        # principalmente após buscar personagem (que chama dashboard_refresh).
        #
        # Estes flags/lock evitam workers simultâneos e permitem throttling.
        # -----------------------------------------------------------------
        self._boosted_lock = threading.Lock()
        self._boosted_inflight = False
        self._boosted_last_fetch_mono = 0.0

        # Android background service handle (favorites monitor)
        self._bg_service = None

        # data dir (writable) – evita crash quando fallback cai em pasta sem permissão no Android
        self.data_dir = ""
        if _CORE_IMPORT_ERROR is None:
            try:
                self.data_dir = str(get_data_dir() or "")
            except Exception:
                self.data_dir = ""

        if not self.data_dir:
            # user_data_dir é o caminho mais confiável no Android
            try:
                self.data_dir = str(getattr(self, "user_data_dir", "") or "")
            except Exception:
                self.data_dir = ""

        if not self.data_dir:
            self.data_dir = os.getcwd()

        def _ensure_writable_dir(p: str) -> str:
            try:
                os.makedirs(p, exist_ok=True)
                test_path = os.path.join(p, ".tt_write_test")
                with open(test_path, "w", encoding="utf-8") as f:
                    f.write("ok")
                try:
                    os.remove(test_path)
                except Exception:
                    pass
                return p
            except Exception:
                return ""

        ok_dir = _ensure_writable_dir(self.data_dir)
        if not ok_dir:
            try:
                ok_dir = _ensure_writable_dir(str(getattr(self, "user_data_dir", "") or ""))
            except Exception:
                ok_dir = ""
        if not ok_dir:
            ok_dir = os.getcwd()
        self.data_dir = ok_dir

        # Cache HTTP em disco: app abre instantâneo e funciona offline com os últimos dados
        try:
            if _configure_http_disk is not None:
                _configure_http_disk(os.path.join(self.data_dir, "http_cache"))
        except Exception:
            pass

        self.fav_path = os.path.join(self.data_dir, "favorites.json")
        self.prefs_path = os.path.join(self.data_dir, "prefs.json")
        self.cache_path = os.path.join(self.data_dir, "cache.json")
        self.prefs = {}
        self.cache = {}
        self._bosses_filter_debounce_ev = None
        self._menu_boss_filter = None
        self._menu_boss_sort = None
        self._menu_imb_tier = None

        self._menu_world: Optional[MDDropdownMenu] = None
        self._menu_skill: Optional[MDDropdownMenu] = None
        self._menu_vocation: Optional[MDDropdownMenu] = None
        self._menu_weapon: Optional[MDDropdownMenu] = None

        # Char search history menu
        self._menu_char_history: Optional[MDDropdownMenu] = None

        # Favorites (chars) UI/status helpers
        self._fav_items = {}  # lower(char_name) -> list item
        self._fav_status_cache = {}  # lower(char_name) -> last known "online"/"offline"
        self._fav_world_cache = {}  # lower(char_name) -> cached world
        self._fav_last_login_cache = {}  # lower(char_name) -> last_login ISO (UTC)
        self._last_seen_online_cache = {}  # lower(char_name) -> last time we saw ONLINE (UTC ISO)
        self._fav_status_job_id = 0
        self._fav_refresh_event = None

        # Disk I/O debounce (evita travadas por salvar JSON a cada update)
        self._prefs_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._prefs_dirty = False
        self._cache_dirty = False
        self._disk_event = threading.Event()
        self._disk_stop = threading.Event()
        self.persistence = PersistenceService(self)
        self.android_bridge = AndroidBridgeService(self)
        self._disk_thread = threading.Thread(target=self._disk_worker_loop, daemon=True)
        self._disk_thread.start()

        # Evita rebuild completo da lista de favoritos a cada refresh
        self._fav_rendered_signature = None
        self._fav_refreshing = False

        # Navegação/back (Android)
        self._back_bound = False
        self._last_back_press_ts = 0.0
        self._nav_parent_map = {
            "boss_favorites": "bosses",
        }
        self._nav_history = []
        self._nav_current_route = None
        self._nav_max_history = 64
        self._suppress_home_tab_event = False

    def build(self):


        self.title = "Tibia Tools"
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Dark"

        # Android 15+ desenha o app sob a barra de status: detecta a altura dela
        # para o StatusBarSpacer (KV) afastar o conteúdo do topo.
        self._detect_status_bar_height()
        # Insets podem ainda não estar prontos antes da primeira tela.
        Clock.schedule_once(lambda *_: self._detect_status_bar_height(), 0.5)

        # Se algum import do core falhar no Android, mostre na tela em vez de fechar.
        if _CORE_IMPORT_ERROR is not None:
            print(_CORE_IMPORT_ERROR)
            from kivymd.uix.label import MDLabel
            return MDLabel(
                text="Erro ao importar módulos (core).\nVeja o logcat (Traceback).",
                halign="center",
            )

        # Preferências (tema) antes de carregar o KV
        try:
            self._load_prefs_cache()
            style = str(self._prefs_get("theme_style", "Dark") or "Dark").strip().title()
            if style in ("Dark", "Light"):
                self.theme_cls.theme_style = style
        except Exception:
            pass

        kv_ok = False
        try:
            root = load_root_kv(Builder)
            kv_ok = True
        except Exception:
            traceback.print_exc()
            from kivymd.uix.label import MDLabel
            root = MDLabel(text="Erro ao iniciar. Veja o logcat (Traceback).", halign="center")

        # ✅ MUITO IMPORTANTE:
        # só agenda funções que usam telas/ids se o KV carregou de verdade.
        if kv_ok and isinstance(root, ScreenManager):
            self.load_favorites()
            self._load_prefs_cache()
            Clock.schedule_once(lambda *_: self._safe_call(self._apply_settings_to_ui), 0)
            # (disabled) background monitor service auto-start for stability
            Clock.schedule_once(lambda *_: self._safe_call(self._set_initial_home_tab), 0)
            Clock.schedule_once(lambda *_: self._safe_call(self._sync_nav_with_ui), 0.05)
            Clock.schedule_once(lambda *_: self._safe_call(self.dashboard_refresh), 0)

            Clock.schedule_once(lambda *_: self._safe_call(self.refresh_favorites_list, silent=True), 0)
            # Auto-atualização do status dos favoritos (não faz sentido ficar "travado")
            if self._fav_refresh_event is None:
                self._fav_refresh_event = Clock.schedule_interval(
                    lambda dt: self._safe_call(self.refresh_favorites_list, silent=True),
                    30,
                )
            Clock.schedule_once(lambda *_: self._safe_call(self.update_boosted), 0)

        self._bind_android_back()
        return root

    def center_top_app_bar(self, toolbar):
        """KivyMD 1.2 aplica padding negativo na barra M2 (56dp)."""
        def align(*_):
            actions = toolbar.ids.get("left_actions")
            if actions is not None and actions.parent is not None:
                actions.parent.padding = [0, 0, 0, 0]
        # A biblioteca calcula sua altura depois de on_kv_post.
        toolbar.bind(height=lambda *_: Clock.schedule_once(align, 0))
        Clock.schedule_once(align, 0)

    def _detect_status_bar_height(self):
        """Calcula a altura da barra de status (dp) no Android; 0 nas demais plataformas."""
        try:
            if platform != "android":
                return
            from jnius import autoclass  # type: ignore
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            density = float(activity.getResources().getDisplayMetrics().density or 1.0)
            top = 0
            try:
                insets = activity.getWindow().getDecorView().getRootWindowInsets()
                if insets is not None:
                    WindowInsetsType = autoclass("android.view.WindowInsets$Type")
                    top = int(insets.getInsets(WindowInsetsType.statusBars()).top)
            except Exception:
                top = 0
            if top <= 0:
                res = activity.getResources()
                rid = res.getIdentifier("status_bar_height", "dimen", "android")
                if rid > 0:
                    top = int(res.getDimensionPixelSize(rid))
            if top > 0:
                self.status_bar_height_dp = dp(max(0.0, float(top) / density))
        except Exception:
            pass

    def _safe_call(self, fn, *args, **kwargs):
        """Executa fn e captura exceções, evitando fechar o app no Android."""
        try:
            return fn(*args, **kwargs)
        except Exception:
            log_current_exception()
            # tenta mostrar uma mensagem simples na UI (sem quebrar se KV falhou)
            try:
                dlg = MDDialog(
                    title="Erro",
                    text="Ocorreu um erro e foi gravado em tibia_tools_crash.log.\nAbra o app novamente e me envie esse log.",
                    buttons=[MDFlatButton(text="OK", on_release=lambda *_: dlg.dismiss())],
                )
                dlg.open()
            except Exception:
                pass
            return None

    def on_pause(self):
        """Android: ao ir para o background, força flush de prefs/cache.

        Isso ajuda a não perder dados caso o sistema mate o processo.
        """
        try:
            self._flush_prefs_to_disk(force=True)
            self._flush_cache_to_disk(force=True)
        except Exception:
            pass
        # Faz apenas uma sincronizacao atrasada e debounced ao ir para background.
        # O AndroidBridgeService ja aplica cooldown/anti-loop; aqui apenas garantimos
        # que o monitor nao fique morto para usuarios com favoritos ativos.
        try:
            Clock.unschedule(self._sync_monitor_on_pause)
        except Exception:
            pass
        try:
            Clock.schedule_once(lambda *_: self._safe_call(self._sync_monitor_on_pause), 0.8)
        except Exception:
            pass
        return True

    def on_stop(self):
        """Flush final e encerra o worker de disco."""
        try:
            try:
                self._unbind_android_back()
            except Exception:
                pass
            try:
                self._disk_stop.set()
            except Exception:
                pass
            try:
                self._disk_event.set()
            except Exception:
                pass
            # flush final
            self._flush_prefs_to_disk(force=True)
            self._flush_cache_to_disk(force=True)
        except Exception:
            pass

    def _bind_android_back(self):
        try:
            if self._back_bound:
                return
            Window.bind(on_keyboard=self._on_window_keyboard)
            Window.bind(on_key_down=self._on_window_key_down)
            Window.bind(on_key_up=self._on_window_key_up)
            Window.bind(on_request_close=self._on_window_request_close)
            self._back_bound = True
        except Exception:
            log_current_exception()
            self._back_bound = False
        # Android 13+ (e principalmente Android 16): registra o "voltar" direto no
        # sistema. Assim o gesto nao fecha o app mesmo que o sistema nao envie
        # a tecla Voltar para o Kivy.
        try:
            self._register_android_back_callback()
        except Exception:
            log_current_exception()

    def _register_android_back_callback(self):
        if platform != "android":
            return
        if getattr(self, "_back_invoked_cb", None) is not None:
            return
        try:
            from jnius import autoclass, PythonJavaClass, java_method  # type: ignore
            VERSION = autoclass("android.os.Build$VERSION")
            if int(VERSION.SDK_INT) < 33:
                return
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
        except Exception:
            log_current_exception()
            return

        app = self

        class _TTBackCallback(PythonJavaClass):
            __javainterfaces__ = ["android/window/OnBackInvokedCallback"]
            __javacontext__ = "app"

            @java_method("()V")
            def onBackInvoked(self):
                # Chamado na thread do Android; a navegacao roda na thread do Kivy.
                try:
                    Clock.schedule_once(lambda *_: app._on_android_back_invoked(), 0)
                except Exception:
                    pass

        def _do_register(*_args):
            try:
                activity = PythonActivity.mActivity
                dispatcher = activity.getOnBackInvokedDispatcher()
                cb = _TTBackCallback()
                dispatcher.registerOnBackInvokedCallback(0, cb)  # PRIORITY_DEFAULT
                # Guarda referencias para o Python nao apagar o callback da memoria.
                app._back_invoked_cb = cb
                app._back_invoked_dispatcher = dispatcher
            except Exception:
                log_current_exception()

        try:
            from android.runnable import run_on_ui_thread  # type: ignore
            run_on_ui_thread(_do_register)()
        except Exception:
            _do_register()

    def _unregister_android_back_callback(self):
        cb = getattr(self, "_back_invoked_cb", None)
        dispatcher = getattr(self, "_back_invoked_dispatcher", None)
        if cb is None or dispatcher is None:
            return
        try:
            dispatcher.unregisterOnBackInvokedCallback(cb)
        except Exception:
            pass
        self._back_invoked_cb = None
        self._back_invoked_dispatcher = None

    def _on_android_back_invoked(self):
        """Voltar recebido pelo callback do sistema (Android 13+)."""
        try:
            handled = self._dispatch_android_back()
        except Exception:
            log_current_exception()
            return
        if not handled:
            # Segundo toque na Home: manda o app para segundo plano (como o Android faz).
            self._send_app_to_background()

    def _send_app_to_background(self):
        try:
            from jnius import autoclass  # type: ignore
            activity = autoclass("org.kivy.android.PythonActivity").mActivity

            def _move(*_args):
                try:
                    activity.moveTaskToBack(True)
                except Exception:
                    log_current_exception()

            try:
                from android.runnable import run_on_ui_thread  # type: ignore
                run_on_ui_thread(_move)()
            except Exception:
                _move()
        except Exception:
            log_current_exception()

    def _unbind_android_back(self):
        try:
            if not self._back_bound:
                return
            Window.unbind(on_keyboard=self._on_window_keyboard)
            Window.unbind(on_key_down=self._on_window_key_down)
            Window.unbind(on_key_up=self._on_window_key_up)
            Window.unbind(on_request_close=self._on_window_request_close)
        except Exception:
            log_current_exception()
        self._back_bound = False
        try:
            self._unregister_android_back_callback()
        except Exception:
            pass

    def _get_current_screen_name(self) -> str:
        try:
            sm = self.root
            if isinstance(sm, ScreenManager):
                return str(sm.current or "")
        except Exception:
            pass
        return ""

    def _get_current_home_tab(self) -> str:
        try:
            sm = self.root
            if not isinstance(sm, ScreenManager) or "home" not in sm.screen_names:
                return ""
            home = sm.get_screen("home")
            bottom_nav = home.ids.get("bottom_nav")
            if bottom_nav is None:
                return ""
            return str(getattr(bottom_nav, "current", "") or "")
        except Exception:
            return ""

    def _normalize_home_tab(self, tab_name: str) -> str:
        tab = str(tab_name or "").strip()
        return tab or "tab_dashboard"

    def _make_route(self, screen_name: str, tab_name: Optional[str] = None):
        screen = str(screen_name or "").strip() or "home"
        if screen == "home":
            return ("home", self._normalize_home_tab(tab_name or self._get_current_home_tab()))
        return (screen, "")

    def _get_current_route(self):
        current = self._get_current_screen_name() or "home"
        if current == "home":
            return self._make_route("home", self._get_current_home_tab())
        return self._make_route(current)

    def _push_history_entry(self, route) -> None:
        if not route:
            return
        hist = getattr(self, "_nav_history", None)
        if hist is None:
            self._nav_history = []
            hist = self._nav_history
        if hist and hist[-1] == route:
            return
        hist.append(route)
        max_items = int(getattr(self, "_nav_max_history", 64) or 64)
        if max_items > 0 and len(hist) > max_items:
            del hist[:-max_items]

    def _remember_current_route_before(self, next_route) -> None:
        current = getattr(self, "_nav_current_route", None) or self._get_current_route()
        if current and current != next_route:
            self._push_history_entry(current)

    def _sync_nav_with_ui(self, *_args) -> None:
        self._nav_current_route = self._get_current_route()

    def _set_screen_current(self, screen_name: str) -> bool:
        sm = self.root
        if isinstance(sm, ScreenManager) and screen_name in sm.screen_names:
            sm.current = screen_name
            return True
        return False

    def _clear_home_tab_event_suppression(self, *_args):
        self._suppress_home_tab_event = False

    def _set_home_tab_current(self, tab_name: str) -> bool:
        try:
            home = self.root.get_screen("home")
            bottom_nav = home.ids.get("bottom_nav")
            if bottom_nav is None:
                return False
            tab = self._normalize_home_tab(tab_name)
            self._suppress_home_tab_event = True
            if hasattr(bottom_nav, "switch_tab"):
                bottom_nav.switch_tab(tab)
            else:
                bottom_nav.current = tab
            Clock.schedule_once(self._clear_home_tab_event_suppression, 0)
            return True
        except Exception:
            self._suppress_home_tab_event = False
            return False

    def on_home_tab_selected(self, tab_name: str, *_args):
        target = self._make_route("home", tab_name)
        current = getattr(self, "_nav_current_route", None) or self._get_current_route()

        if getattr(self, "_suppress_home_tab_event", False):
            self._nav_current_route = target
            return

        if current != target:
            self._push_history_entry(current)
        self._nav_current_route = target

    def _navigate_to_route(self, route, *, record: bool = True) -> bool:
        if not route:
            return False
        screen_name, tab_name = route
        target = self._make_route(screen_name, tab_name)
        if record:
            self._remember_current_route_before(target)

        changed = False
        if target[0] == "home":
            changed = self._set_screen_current("home") or changed
            changed = self._set_home_tab_current(target[1]) or changed
        else:
            changed = self._set_screen_current(target[0]) or changed

        if changed:
            self._nav_current_route = target
        return changed

    def _go_home_dashboard(self, *, record: bool = True):
        self._navigate_to_route(self._make_route("home", "tab_dashboard"), record=record)

    def _pop_nav_history(self):
        hist = getattr(self, "_nav_history", None) or []
        while hist:
            route = hist.pop()
            if route and route != (getattr(self, "_nav_current_route", None) or self._get_current_route()):
                return route
        return None

    def navigate_back(self, *_args) -> bool:
        route = self._pop_nav_history()
        if route:
            return bool(self._navigate_to_route(route, record=False))
        return False

    def _handle_back_navigation(self) -> bool:
        if self.navigate_back():
            return True

        # Sem histórico: se não estamos na aba inicial, volta para ela em vez de fechar o app
        try:
            current = getattr(self, "_nav_current_route", None) or self._get_current_route()
        except Exception:
            current = None
        home_route = ("home", "tab_dashboard")
        if current and tuple(current) != home_route:
            if self._navigate_to_route(home_route, record=False):
                return True

        now = time.monotonic()
        if (now - float(getattr(self, "_last_back_press_ts", 0.0) or 0.0)) < 2.0:
            return False

        self._last_back_press_ts = now
        try:
            self.toast("Pressione voltar novamente para sair")
        except Exception:
            pass
        return True

    def _is_duplicate_back_event(self) -> bool:
        try:
            now = time.monotonic()
            last = float(getattr(self, "_last_back_event_ts", 0.0) or 0.0)
            guard = float(getattr(self, "_back_event_guard_s", 0.35) or 0.35)
            if (now - last) < guard:
                return True
            self._last_back_event_ts = now
            return False
        except Exception:
            return False

    def _is_android_back_key(self, key=None, scancode=None) -> bool:
        try:
            key_i = None if key is None else int(key)
        except Exception:
            key_i = key
        # Importante: nao tratar scancode como back.
        # Em SDL/Kivy, scancode 4 e 27 podem corresponder a teclas normais
        # como 'a' e 'x', o que fazia o teclado fechar ao digitar.
        return key_i in (4, 27, 1001)

    def _iter_widget_tree(self, root_widget):
        stack = [root_widget]
        seen = set()
        while stack:
            widget = stack.pop()
            ident = id(widget)
            if ident in seen:
                continue
            seen.add(ident)
            yield widget
            try:
                children = list(getattr(widget, "children", None) or [])
            except Exception:
                children = []
            stack.extend(children)

    def _is_text_input_widget(self, widget) -> bool:
        if widget is None:
            return False
        name = type(widget).__name__.lower()
        if "textinput" in name or "textfield" in name:
            return True
        return hasattr(widget, "focus") and (hasattr(widget, "input_filter") or hasattr(widget, "multiline"))

    def _get_focused_text_input(self):
        root = getattr(self, "root", None)
        if root is None:
            return None
        try:
            for widget in self._iter_widget_tree(root):
                if getattr(widget, "focus", False) and self._is_text_input_widget(widget):
                    return widget
        except Exception:
            return None
        return None

    def _dismiss_focused_text_input(self) -> bool:
        widget = self._get_focused_text_input()
        if widget is None:
            return False
        try:
            widget.focus = False
            return True
        except Exception:
            return False

    def _dispatch_android_back(self) -> bool:
        if self._dismiss_focused_text_input():
            return True
        if self._is_duplicate_back_event():
            return True
        return bool(self._handle_back_navigation())

    def _on_window_keyboard(self, _window, key, scancode=None, *_args):
        if not self._is_android_back_key(key, scancode):
            return False
        try:
            return self._dispatch_android_back()
        except Exception:
            log_current_exception()
            return True  # nunca fecha o app por erro na navegacao

    def _on_window_key_down(self, _window, key, scancode=None, *_args):
        if not self._is_android_back_key(key, scancode):
            return False
        try:
            return self._dispatch_android_back()
        except Exception:
            log_current_exception()
            return True  # nunca fecha o app por erro na navegacao

    def _on_window_key_up(self, _window, key, scancode=None, *_args):
        try:
            if not self._is_android_back_key(key, scancode):
                return False
            return True
        except Exception:
            return False

    def _on_window_request_close(self, *_args):
        try:
            return self._dispatch_android_back()
        except Exception:
            log_current_exception()
            return True

    # --------------------
    # Deep-link / Notification click handling (Android)
    # --------------------
    def _handle_android_intent(self) -> None:
        """Se o app foi aberto por uma notificação do serviço, abre a aba Char e (opcionalmente) dispara a busca.

        O serviço envia extras no Intent:
        - tt_open_tab: "tab_char"
        - tt_char_name: nome do char (opcional)
        - tt_auto_search: bool
        - tt_event_type: "online"/"level"/"death" (opcional)
        """
        if not self._is_android():
            return
        try:
            from jnius import autoclass  # type: ignore
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")

            act = PythonActivity.mActivity
            intent = act.getIntent()
            if intent is None:
                return

            open_tab = None
            char_name = None
            auto_search = False
            event_type = None
            try:
                open_tab = intent.getStringExtra("tt_open_tab")
            except Exception:
                open_tab = None
            try:
                char_name = intent.getStringExtra("tt_char_name")
            except Exception:
                char_name = None
            try:
                event_type = intent.getStringExtra("tt_event_type")
            except Exception:
                event_type = None
            try:
                auto_search = bool(intent.getBooleanExtra("tt_auto_search", False))
            except Exception:
                auto_search = False

            if not (open_tab or char_name or event_type):
                return

            sig = f"{open_tab}|{char_name}|{auto_search}|{event_type}"
            if getattr(self, "_last_intent_sig", None) == sig:
                return
            self._last_intent_sig = sig

            # Garante que estamos na Home e na aba Char
            try:
                self.go("home")
            except Exception:
                pass
            try:
                self.select_home_tab("tab_char")
            except Exception:
                pass

            def apply_and_search(*_):
                try:
                    home = self.root.get_screen("home")
                    if char_name and "char_name" in home.ids:
                        home.ids.char_name.text = str(char_name)
                    if auto_search and char_name:
                        # silencioso: não spammar toast ao tocar na notificação
                        self.search_character(silent=True)
                except Exception:
                    pass

            # Deixa a UI terminar de montar antes de mexer nos ids
            Clock.schedule_once(apply_and_search, 0.15)

            # Evita re-disparar ao voltar de background: limpa o Intent atual
            try:
                empty = Intent()
                try:
                    empty.setAction(f"TT_HANDLED_{int(time.time()*1000)}")
                except Exception:
                    pass
                act.setIntent(empty)
            except Exception:
                # fallback: remove extras
                try:
                    intent.removeExtra("tt_open_tab")
                    intent.removeExtra("tt_char_name")
                    intent.removeExtra("tt_auto_search")
                    intent.removeExtra("tt_event_type")
                except Exception:
                    pass
        except Exception:
            return

    # --------------------
    # Navigation
    # --------------------

    def on_start(self):
        # Startup: handle deep-link intents (if any) + request notification permission (Android 13+).
        try:
            Clock.schedule_once(lambda *_: self._handle_android_intent(), 0.6)
        except Exception:
            pass

        # Ask once on first run (Android 13+ requires POST_NOTIFICATIONS).
        try:
            Clock.schedule_once(lambda *_: self._ensure_post_notifications_permission(), 0.9)
        except Exception:
            pass

        # Sincroniza o monitor uma vez apos a UI subir.
        # Isso restaura o servico para quem ja tinha favoritos/configuracao ativa,
        # sem voltar ao loop agressivo anterior de start em varios lifecycle hooks.
        try:
            Clock.schedule_once(lambda *_: self._safe_call(self._sync_monitor_on_start), 1.6)
        except Exception:
            pass

    def _sync_monitor_on_start(self):
        try:
            self._maybe_start_fav_monitor_service(reason="startup_sync")
        except Exception:
            log_current_exception(prefix="[main] falha ao sincronizar monitor no start")

    def _sync_monitor_on_pause(self):
        try:
            # So tenta religar se o monitor nao parece vivo.
            if bool(getattr(self, "_bg_service", False)) and getattr(self, "android_bridge", None):
                try:
                    if self.android_bridge._monitor_service_alive():
                        return
                except Exception:
                    pass
            self._maybe_start_fav_monitor_service(reason="pause_sync")
        except Exception:
            log_current_exception(prefix="[main] falha ao sincronizar monitor no pause")

    def on_resume(self):
        # Quando o usuário toca na notificação com o app em background, isso garante o deep-link.
        try:
            Clock.schedule_once(lambda *_: self._handle_android_intent(), 0.2)
        except Exception:
            pass

        # Nao reinicia o servico automaticamente no on_resume.
        # Evita loops de start/stop em aparelhos/OEMs que entregam varios eventos
        # de ciclo de vida em sequencia.

    def go(self, screen_name: str, *, record: bool = True):
        if screen_name == "home":
            current_tab = self._get_current_home_tab() or "tab_dashboard"
            self._navigate_to_route(self._make_route("home", current_tab), record=record)
            return
        self._navigate_to_route(self._make_route(screen_name), record=record)

    def back_home(self, *_):
        if not self.navigate_back():
            self._go_home_dashboard(record=True)


    def open_boosted_from_home(self, which: str = ""):
        """Abre a tela Boosted a partir do card da Home.

        which: "creature" | "boss" | "" (opcional, apenas para futuras melhorias).
        """
        try:
            self.go("boosted")
        except Exception:
            return

        # garante que os dados estejam atualizados ao entrar
        try:
            self.update_boosted(silent=False)
        except Exception:
            pass


    def select_home_tab(self, tab_name: str, *, record: bool = True):
        """Seleciona uma aba dentro da HomeScreen (BottomNavigation)."""
        self._navigate_to_route(self._make_route("home", tab_name), record=record)

    def open_more_target(self, target: str):
        # Itens que abrem dialog/ações, não telas
        if target == "about":
            self.show_about()
            return
        if target == "changelog":
            self.show_changelog()
            return
        if target == "feedback":
            self.open_feedback()
            return

        self.go(target)
        if target == "bosses":
            self._bosses_refresh_worlds()
        elif target == "imbuements":
            self._imbuements_load()
        elif target == "training":
            self._ensure_training_menus()
        elif target == "settings":
            self._apply_settings_to_ui()

    def dashboard_refresh(self, *_):
        """Atualiza o resumo do Dashboard usando cache e, se possível, dados ao vivo."""
        try:
            home = self.root.get_screen("home")
            ids = home.ids
        except Exception:
            return

        # último char
        last_char = str(self._prefs_get("last_char", "") or "")
        try:
            ids.dash_last_char.text = last_char if last_char else "-"
        except Exception:
            pass

        # boosted do cache (TTL 12h) e atualização ao vivo em background
        cached_boost = self._cache_get("boosted", ttl_seconds=12 * 3600) or {}
        if isinstance(cached_boost, dict) and cached_boost:
            try:
                ids.dash_boost_creature.text = (cached_boost.get('creature') or '-')
                ids.dash_boost_boss.text = (cached_boost.get('boss') or '-')
                # sprites no dashboard (quando disponíveis)
                if "dash_boost_creature_sprite" in ids:
                    ids.dash_boost_creature_sprite.source = cached_boost.get("creature_image") or ""
                if "dash_boost_boss_sprite" in ids:
                    ids.dash_boost_boss_sprite.source = cached_boost.get("boss_image") or ""
                ts = self.cache.get("boosted", {}).get("ts", "")
                ids.dash_boost_updated.text = f"Atualizado: {ts.split('T')[0] if ts else ''}"
            except Exception:
                pass
        else:
            try:
                ids.dash_boost_creature.text = "-"
                ids.dash_boost_boss.text = "-"
                if "dash_boost_creature_sprite" in ids:
                    ids.dash_boost_creature_sprite.source = ""
                if "dash_boost_boss_sprite" in ids:
                    ids.dash_boost_boss_sprite.source = ""
                ids.dash_boost_updated.text = "Sem cache ainda."
            except Exception:
                pass

        # Atualiza Boosted ao vivo (sem travar UI), mas com *throttling*.
        # Chamar isso a cada dashboard_refresh (ex: ao buscar personagem) cria
        # muita atividade de rede/CPU no Android. Atualizamos apenas se o cache
        # estiver ausente ou "velho" o suficiente.
        try:
            need_live = False
            ts = None
            try:
                ts = (self.cache.get("boosted") or {}).get("ts")
            except Exception:
                ts = None

            if not ts:
                need_live = True
            else:
                try:
                    dt = datetime.fromisoformat(str(ts))
                    age_s = (datetime.utcnow() - dt).total_seconds()
                    # Boosted muda 1x por dia; 6h é um bom equilíbrio.
                    if age_s > 6 * 3600:
                        need_live = True
                except Exception:
                    need_live = True

            if need_live:
                self.update_boosted(silent=True)
        except Exception:
            pass

        # bosses favoritos high (do cache do último world)
        try:
            ids.dash_boss_list.clear_widgets()
        except Exception:
            pass

        favs = self._prefs_get("boss_favorites", []) or []
        if not isinstance(favs, list):
            favs = []

        world = str(self._prefs_get("boss_last_world", "") or "")
        cache_key = f"bosses:{world.lower()}" if world else ""
        bosses = self._cache_get(cache_key, ttl_seconds=6 * 3600) if cache_key else None
        if not bosses:
            try:
                ids.dash_boss_hint.text = "Sem cache de bosses ainda. Abra Bosses e toque em Buscar."
            except Exception:
                pass
            return

        high = []
        for b in bosses:
            try:
                name = str(b.get("boss") or b.get("name") or "")
                if name not in favs:
                    continue
                score = self._boss_chance_score(str(b.get("chance") or ""))
                if score >= 70:
                    high.append((score, b))
            except Exception:
                continue

        high.sort(key=lambda t: t[0], reverse=True)
        if not high:
            try:
                ids.dash_boss_hint.text = f"Nenhum favorito High em {world}."
            except Exception:
                pass
            return

        try:
            ids.dash_boss_hint.text = f"World: {world}  •  High: {len(high)}"
        except Exception:
            pass

        for _, b in high[:6]:
            name = str(b.get("boss") or b.get("name") or "Boss")
            chance = str(b.get("chance") or "").strip()
            it = OneLineIconListItem(text=f"{name} ({chance})")
            it.add_widget(IconLeftWidget(icon="star"))
            it.bind(on_release=lambda _it, bb=b: self.bosses_open_dialog(bb))
            try:
                ids.dash_boss_list.add_widget(it)
            except Exception:
                pass

        # alerta (apenas ao abrir/app na frente) - best effort
        try:
            if bool(self._prefs_get("notify_boss_high", True)) and high:
                today = datetime.utcnow().date().isoformat()
                last = str(self._prefs_get("boss_high_notified_date", "") or "")
                if last != today:
                    self._prefs_set("boss_high_notified_date", today)
                    self._send_notification("Boss favorito HIGH", f"{high[0][1].get('boss','Boss')} está HIGH em {world}")
        except Exception:
            pass

    def dashboard_open_last_char(self):
        last_char = str(self._prefs_get("last_char", "") or "").strip()
        if not last_char:
            self.toast("Nenhum char salvo ainda.")
            return
        try:
            webbrowser.open(f"https://www.tibia.com/community/?subtopic=characters&name={last_char.replace(' ', '+')}")
        except Exception:
            self.toast("Não consegui abrir o navegador.")

    # --------------------
    # Clipboard / Share helpers
    # --------------------
    def copy_deaths_to_clipboard(self):
        try:
            home = self.root.get_screen("home")
            title = (home.ids.char_title.text or "").strip()
            payload = getattr(home, "_last_char_payload", None)
            deaths = []
            if isinstance(payload, dict):
                deaths = payload.get("deaths") or []
            lines = [f"Mortes - {title}"]
            for d in deaths[:30]:
                if not isinstance(d, dict):
                    continue
                when = str(d.get("time") or d.get("date") or "")
                lvl = str(d.get("level") or "")
                reason = str(d.get("reason") or "")
                xp = str(d.get("exp_lost") or "")
                parts = [p for p in [when, f"Level {lvl}" if lvl else "", xp, reason] if p]
                lines.append(" - ".join(parts))
            Clipboard.copy("\n".join(lines))
            self.toast("Copiado.")
        except Exception:
            self.toast("Não consegui copiar.")

    def hunt_copy(self):
        try:
            scr = self.root.get_screen("hunt")
            Clipboard.copy(scr.ids.hunt_output.text or "")
            self.toast("Copiado.")
        except Exception:
            self.toast("Nada para copiar.")

    def hunt_share(self):
        try:
            scr = self.root.get_screen("hunt")
            txt = (scr.ids.hunt_output.text or "").strip()
            if not txt:
                self.toast("Nada para compartilhar.")
                return
            try:
                from plyer import share  # type: ignore
                share.share(txt, title="Hunt Analyzer")
                return
            except Exception:
                Clipboard.copy(txt)
                self.toast("Copiado (share indisponível).")
        except Exception:
            self.toast("Falha ao compartilhar.")

# --------------------
    # Storage
    # --------------------
















    # --------------------
    # Offline duration helpers ("última vez online")
    # --------------------
    def _eu_dst_offset_hours(self, dt_local: datetime) -> int:
        """Retorna offset CET/CEST (horas) assumindo regra EU.

        Usado quando a API não informa timezone.
        """
        try:
            y = dt_local.year
            # last Sunday of March
            import calendar
            def last_sunday(year: int, month: int) -> datetime:
                last_day = calendar.monthrange(year, month)[1]
                d = datetime(year, month, last_day)
                # weekday: Monday=0 ... Sunday=6
                delta = (d.weekday() - 6) % 7
                return d - timedelta(days=delta)

            start = last_sunday(y, 3).replace(hour=2, minute=0, second=0, microsecond=0)  # 02:00 local
            end = last_sunday(y, 10).replace(hour=3, minute=0, second=0, microsecond=0)   # 03:00 local
            if start <= dt_local < end:
                return 2  # CEST
            return 1      # CET
        except Exception:
            # fallback simples
            try:
                return 2 if 4 <= int(dt_local.month) <= 9 else 1
            except Exception:
                return 1

    def _parse_tibia_datetime(self, raw: str) -> Optional[datetime]:
        """Tenta converter datas vindas do TibiaData/tibia.com para datetime UTC (naive)."""
        if not isinstance(raw, str):
            return None
        s = raw.strip()
        if not s or s.lower() in ("n/a", "none", "null"):
            return None

        # Normaliza alguns formatos
        s2 = s.replace("\u00a0", " ").strip()
        # ISO com Z
        if s2.endswith('Z'):
            try:
                dt = datetime.fromisoformat(s2[:-1] + '+00:00')
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                pass

        # ISO (talvez com offset)
        try:
            dt = datetime.fromisoformat(s2)
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            pass

        # Formatos comuns do TibiaData (sem tz)
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d, %H:%M:%S", "%Y-%m-%d"):
            try:
                dt_local = datetime.strptime(s2, fmt)
                off = self._eu_dst_offset_hours(dt_local)
                return (dt_local - timedelta(hours=off))
            except Exception:
                continue

        # Formato típico do tibia.com: "Jan 22 2026, 10:42:00 CET"
        # Vamos remover o timezone e aplicar CET/CEST.
        import re
        m = re.match(r"^([A-Za-z]{3})\s+(\d{1,2})\s+(\d{4}),\s*(\d{2}:\d{2}:\d{2})(?:\s+([A-Za-z]{2,5}))?$", s2)
        if m:
            mon, day, year, hhmmss, tz = m.groups()
            try:
                dt_local = datetime.strptime(f"{mon} {day} {year}, {hhmmss}", "%b %d %Y, %H:%M:%S")
            except Exception:
                dt_local = None
            if dt_local:
                tz_u = (tz or "").upper().strip()
                if tz_u == "CEST":
                    off = 2
                elif tz_u == "CET":
                    off = 1
                elif tz_u in ("UTC", "GMT"):
                    off = 0
                else:
                    off = self._eu_dst_offset_hours(dt_local)
                return dt_local - timedelta(hours=off)

        return None

    def _extract_last_login_dt_from_tibiadata(self, data: dict) -> Optional[datetime]:
        """Extrai o 'last_login' (ou equivalente) do JSON do TibiaData."""
        if not isinstance(data, dict):
            return None
        ch_wrap = data.get('character') or {}
        ch = None
        if isinstance(ch_wrap, dict):
            ch = ch_wrap.get('character') if isinstance(ch_wrap.get('character'), dict) else ch_wrap
        if not isinstance(ch, dict):
            return None

        # Possíveis chaves (variam por versão/API)
        candidates = [
            'last_login',
            'lastLogin',
            'last_logout',
            'lastLogout',
            'last_seen',
            'lastSeen',
            'last_online',
            'lastOnline',
        ]
        raw = None
        for k in candidates:
            if k in ch and ch.get(k):
                raw = ch.get(k)
                break

        # Às vezes vem como dict
        if isinstance(raw, dict):
            raw = raw.get('date') or raw.get('datetime') or raw.get('time')

        if isinstance(raw, str):
            return self._parse_tibia_datetime(raw)

        return None

    def _fetch_last_login_dt_tibia_com(self, name: str, timeout: int = 12) -> Optional[datetime]:
        """Fallback: delega a leitura de Last Login para integrations.tibia_com."""
        try:
            return fetch_last_login_dt(name, timeout=timeout)
        except Exception:
            return None

    def _get_cached_fav_last_login_iso(self, name: str) -> Optional[str]:
        key = (name or "").strip().lower()
        if not key:
            return None
        try:
            if key in getattr(self, "_fav_last_login_cache", {}):
                v = self._fav_last_login_cache.get(key)
                return str(v) if v else None
        except Exception:
            pass
        cached = self._cache_get(f"fav_last_login:{key}")
        if isinstance(cached, str) and cached.strip():
            try:
                self._fav_last_login_cache[key] = cached.strip()
            except Exception:
                pass
            return cached.strip()
        return None

    def _set_cached_fav_last_login_iso(self, name: str, iso: Optional[str]) -> None:
        key = (name or "").strip().lower()
        if not key:
            return
        try:
            if iso and str(iso).strip():
                self._fav_last_login_cache[key] = str(iso).strip()
                self._cache_set(f"fav_last_login:{key}", str(iso).strip())
            else:
                self._fav_last_login_cache.pop(key, None)
                self._cache_set(f"fav_last_login:{key}", None)
        except Exception:
            pass



    def _get_cached_last_seen_online_iso(self, name: str) -> Optional[str]:
        """Instante (UTC ISO) em que o app viu o char ONLINE pela última vez.

        Tibia.com expõe "Last Login" (hora que entrou), não "Last Logout".
        Para mostrar "há quanto tempo ficou OFF", usamos o último instante em que o app confirmou o ONLINE.
        """
        key = (name or "").strip().lower()
        if not key:
            return None

        try:
            if key in getattr(self, "_last_seen_online_cache", {}):
                v = self._last_seen_online_cache.get(key)
                return str(v) if v else None
        except Exception:
            pass

        cached = self._cache_get(f"last_seen_online:{key}")
        if isinstance(cached, str) and cached.strip():
            try:
                self._last_seen_online_cache[key] = cached.strip()
            except Exception:
                pass
            return cached.strip()

        return None



    def _set_cached_last_seen_online_iso(self, name: str, iso: Optional[str]) -> None:
        key = (name or "").strip().lower()
        if not key:
            return
        try:
            if iso and str(iso).strip():
                self._last_seen_online_cache[key] = str(iso).strip()
                self._cache_set(f"last_seen_online:{key}", str(iso).strip())
            else:
                self._last_seen_online_cache.pop(key, None)
                self._cache_set(f"last_seen_online:{key}", None)
        except Exception:
            pass


    def _get_cached_offline_since_iso(self, name: str) -> Optional[str]:
        """Instante (UTC ISO) em que o app/serviço detectou a transição Online -> Offline.

        Esse é o mais próximo de "quando deslogou" que dá para medir automaticamente.
        """
        key = (name or "").strip().lower()
        if not key:
            return None
        try:
            if key in getattr(self, "_offline_since_cache", {}):
                v = self._offline_since_cache.get(key)
                return str(v) if v else None
        except Exception:
            pass
        cached = self._cache_get(f"offline_since:{key}")
        if isinstance(cached, str) and cached.strip():
            try:
                if not hasattr(self, "_offline_since_cache"):
                    self._offline_since_cache = {}
                self._offline_since_cache[key] = cached.strip()
            except Exception:
                pass
            return cached.strip()
        return None

    def _set_cached_offline_since_iso(self, name: str, iso: Optional[str]) -> None:
        key = (name or "").strip().lower()
        if not key:
            return
        try:
            if not hasattr(self, "_offline_since_cache"):
                self._offline_since_cache = {}
            if iso and str(iso).strip():
                self._offline_since_cache[key] = str(iso).strip()
                self._cache_set(f"offline_since:{key}", str(iso).strip())
            else:
                self._offline_since_cache.pop(key, None)
                self._cache_set(f"offline_since:{key}", None)
        except Exception:
            pass


    def _format_ago_short(self, dt_utc: datetime) -> str:
        try:
            now = datetime.utcnow()
            sec = max(0, int((now - dt_utc).total_seconds()))
            mins = sec // 60
            if mins < 60:
                return f"há {mins}m"
            hrs = mins // 60
            if hrs < 24:
                return f"há {hrs}h"
            days = hrs // 24
            if days < 30:
                return f"há {days}d"
            # meses aproximados
            months = days // 30
            return f"há {months}m"
        except Exception:
            return ""

    def _format_ago_long(self, dt_utc: datetime) -> str:
        try:
            now = datetime.utcnow()
            sec = max(0, int((now - dt_utc).total_seconds()))
            mins = sec // 60
            if mins < 60:
                n = mins
                return f"há {n} minuto" + ("s" if n != 1 else "")
            hrs = mins // 60
            if hrs < 24:
                n = hrs
                return f"há {n} hora" + ("s" if n != 1 else "")
            days = hrs // 24
            if days < 30:
                n = days
                return f"há {n} dia" + ("s" if n != 1 else "")
            months = days // 30
            n = months
            return f"há {n} mês" + ("es" if n != 1 else "")
        except Exception:
            return ""

    def _fetch_last_login_iso_for_char(self, name: str) -> Optional[str]:
        """Busca o last_login (UTC ISO) do char.

        1) tenta TibiaData /v4/character
        2) fallback tibia.com
        """
        try:
            data = fetch_character_tibiadata(name, timeout=12)
            dt = self._extract_last_login_dt_from_tibiadata(data)
            if dt:
                return dt.isoformat()
        except Exception:
            pass
        try:
            dt = self._fetch_last_login_dt_tibia_com(name, timeout=12)
            if dt:
                return dt.isoformat()
        except Exception:
            pass
        return None

    def _set_initial_home_tab(self, *_):
        # abre direto no Dashboard
        self.select_home_tab("tab_dashboard", record=False)
        self._sync_nav_with_ui()


    def toast(self, message: str):
        """Mostra uma mensagem rápida sem derrubar o app."""
        try:
            from kivymd.uix.snackbar import Snackbar  # type: ignore
            try:
                Snackbar(text=message).open()
                return
            except Exception:
                pass
        except Exception:
            pass

        try:
            from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText  # type: ignore
            sb = MDSnackbar(MDSnackbarText(text=message))
            sb.open()
            return
        except Exception:
            pass

        print(f"[TOAST] {message}")

    def _show_text_dialog(self, title: str, text: str):
        """Abre um dialog simples para mostrar textos longos (sem cortar com '...')."""
        try:
            if getattr(self, "_active_dialog", None):
                self._active_dialog.dismiss()
        except Exception:
            pass

        dialog = MDDialog(
            title=title,
            text=text,
            buttons=[
                MDFlatButton(text="OK", on_release=lambda *_: dialog.dismiss()),
            ],
        )
        self._active_dialog = dialog
        dialog.open()






    # --------------------
    # Char tab
    # --------------------
    
    



    # --------------------
    # Favorites tab
    # --------------------

















    def calc_shared_xp(self):
        home = self.root.get_screen("home")
        try:
            level = int((home.ids.share_level.text or "0").strip())
        except ValueError:
            self.toast("Digite um level válido.")
            return

        if level <= 0:
            self.toast("Digite um level maior que 0.")
            return

        min_level = int(math.ceil(level * 2.0 / 3.0))
        max_level = int(math.floor(level * 3.0 / 2.0))

        home.ids.share_result.text = (
            f"Seu level: {level}\n"
            f"Pode sharear com: {min_level} até {max_level}"
        )

    # --------------------
    # Stamina (offline)
    # --------------------
    def stamina_calculate(self):
        """Calcula quanto tempo ficar offline para atingir a stamina desejada.

        Regra usada:
        - a regeneração começa 10 minutos após deslogar;
        - até 39:00: 1 min stamina / 3 min offline;
        - de 39:00 a 42:00: 1 min stamina / 6 min offline.
        """
        scr = self.root.get_screen("stamina")

        try:
            cur_min = parse_hm_text(scr.ids.stam_cur_h.text, scr.ids.stam_cur_m.text)
            tgt_min = parse_hm_text(scr.ids.stam_tgt_h.text, scr.ids.stam_tgt_m.text)
        except Exception as e:
            self.toast(str(e))
            return

        res = compute_offline_regen(cur_min, tgt_min)
        now = datetime.now()

        if res.offline_needed_min <= 0:
            scr.ids.stam_result.text = (
                f"Stamina atual: {format_hm(res.current_min)}\n"
                f"Stamina alvo: {format_hm(res.target_min)}\n\n"
                "Você já está no alvo."
            )
            return

        offline_total = res.offline_needed_min
        offline_h = offline_total // 60
        offline_m = offline_total % 60

        regen_only = res.regen_offline_only_min
        regen_h = regen_only // 60
        regen_m = regen_only % 60

        reached_at = now + timedelta(minutes=offline_total)

        scr.ids.stam_result.text = (
            f"Stamina atual: {format_hm(res.current_min)}\n"
            f"Stamina alvo: {format_hm(res.target_min)}\n\n"
            f"Tempo offline necessário: {offline_h}h {offline_m:02d}min\n"
            f"(Regeneração: {regen_h}h {regen_m:02d}min + 10min iniciais)\n\n"
            f"Você terá {format_hm(res.target_min)} em: {reached_at.strftime('%d/%m %H:%M')}\n"
            "(considerando que você desloga agora)"
        )

    # --------------------
    # Bosses (ExevoPan)
    # --------------------

    # Boosted

    # --------------------

    # --------------------
    # Training (Exercise)
    # --------------------
    def _menu_fix_position(self, menu):
        """Tenta manter dropdown dentro da tela (KivyMD 1.2)."""
        try:
            # Se disponível, força crescimento horizontal para a esquerda.
            menu.hor_growth = "left"
        except Exception:
            pass
        try:
            menu.ver_growth = "down"
        except Exception:
            pass
        try:
            # Margem para evitar colar na borda.
            menu.border_margin = dp(16)
        except Exception:
            pass

    def _clamp_dropdown_to_window(self, menu, _tries: int = 3):
        """Garante que o dropdown não fique fora da tela (extra p/ Android)."""
        try:
            from kivy.core.window import Window
        except Exception:
            return

        try:
            w = float(getattr(menu, "width", 0) or 0)
            h = float(getattr(menu, "height", 0) or 0)
        except Exception:
            return

        # Em alguns devices o size ainda não está pronto no mesmo frame.
        if w <= 0 or h <= 0:
            if _tries > 0:
                Clock.schedule_once(lambda *_: self._clamp_dropdown_to_window(menu, _tries=_tries - 1), 0)
            return

        m = dp(8)
        try:
            menu.x = max(m, min(menu.x, Window.width - w - m))
        except Exception:
            pass
        try:
            menu.y = max(m, min(menu.y, Window.height - h - m))
        except Exception:
            pass


    # --------------------
    # Hunt Analyzer
    # --------------------
    def hunt_parse(self):
        scr = self.root.get_screen("hunt")
        raw = (scr.ids.hunt_input.text or "").strip()
        if not raw:
            self.toast("Cole o texto do Session Data.")
            return
        scr.ids.hunt_status.text = "Analisando..."
        scr.ids.hunt_output.text = ""

        def run():
            res = parse_hunt_session_text(raw)
            Clock.schedule_once(lambda *_: self._hunt_done(res), 0)

        threading.Thread(target=run, daemon=True).start()

    def _hunt_done(self, res):
        scr = self.root.get_screen("hunt")
        if not res.ok:
            scr.ids.hunt_status.text = res.error or "Erro"
            scr.ids.hunt_output.text = ""
            return
        scr.ids.hunt_status.text = "OK"
        scr.ids.hunt_output.text = res.pretty

    # --------------------
    # Imbuements
    # --------------------


if __name__ == "__main__":
    try:
        TibiaToolsApp().run()
    except Exception:
        log_current_exception()
        raise
