"""Regressões: favoritos ocultos, mortes completas e alinhamento da barra."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from test_back_navigation_events import TibiaToolsApp
from features.bosses.logic import favorites_only_enabled
from features.char.controller import CharControllerMixin
from ui.kv_loader import FALLBACK_KV, get_combined_kv_text


class Ids(dict):
    __getattr__ = dict.__getitem__


class List:
    def __init__(self):
        self.children = []

    def clear_widgets(self):
        self.children.clear()

    def add_widget(self, item):
        self.children.append(item)


class FakeWidget:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.children = []

    def add_widget(self, widget):
        self.children.append(widget)

    def bind(self, **kwargs):
        pass


class V9Tests(unittest.TestCase):
    def setUp(self):
        import main
        import features.bosses.controller as bosses_ctrl
        for mod in (main, bosses_ctrl):
            for name in ("TwoLineIconListItem", "IconLeftWidget", "OneLineIconListItem"):
                p = patch.object(mod, name, FakeWidget, create=True)
                p.start()
                self.addCleanup(p.stop)

    def test_boolean_preferences(self):
        for value in (False, "false", "False", "0", "off", None, 0):
            self.assertFalse(favorites_only_enabled(value))
        for value in (True, "true", "1", 1):
            self.assertTrue(favorites_only_enabled(value))

    def make_boss_app(self, enabled, favorites):
        app = TibiaToolsApp()
        prefs = {"boss_fav_only": enabled, "boss_favorites": favorites}
        app._prefs_get = lambda key, default=None: prefs.get(key, default)
        app._prefs_set = lambda key, value: prefs.update({key: value})
        app.boss_is_favorite = lambda name: name in favorites
        screen = SimpleNamespace(bosses_raw=[{"boss": "Ghazbaran", "chance": "No chance"}], ids=Ids(
            boss_list=List(), boss_search=SimpleNamespace(text=""),
            boss_status=SimpleNamespace(text=""), boss_filter_label=SimpleNamespace(text="All"),
            boss_sort_label=SimpleNamespace(text="Chance"), boss_fav_toggle=SimpleNamespace(icon="star-outline"),
        ))
        app.root = SimpleNamespace(get_screen=lambda _: screen)
        app._build_wrapped_info_row = lambda text, **kwargs: SimpleNamespace(text=text, bind=lambda **kw: None)
        return app, screen, prefs

    def test_no_favorites_cannot_hide_all_bosses(self):
        app, screen, prefs = self.make_boss_app(True, [])
        app.bosses_apply_filters()
        self.assertEqual(screen.ids.boss_status.text, "Bosses: 1 (de 1)")
        self.assertFalse(prefs["boss_fav_only"])
        self.assertEqual(screen.ids.boss_fav_toggle.icon, "star-outline")

    def test_string_false_displays_all(self):
        app, screen, _ = self.make_boss_app("false", ["Ferumbras"])
        app.bosses_apply_filters()
        self.assertEqual(screen.ids.boss_status.text, "Bosses: 1 (de 1)")

    def test_cache_path_always_shows_active_filter(self):
        app, screen, _ = self.make_boss_app(True, ["Ferumbras"])
        app.bosses_apply_filters()
        self.assertIn("Só favoritos", screen.ids.boss_filter_label.text)
        self.assertEqual(screen.ids.boss_fav_toggle.icon, "star")
        self.assertIn("Toque na estrela", screen.ids.boss_list.children[0].text)

    def test_death_metadata_has_full_lines(self):
        meta = CharControllerMixin()._death_display_meta({
            "time": "2026-09-18T18:54:35Z", "level": 725, "exp_lost": 123456789,
        })
        self.assertIn("18/09/2026", meta)
        self.assertIn("\nNível 725\nXP perdida: 123.456.789", meta)
        self.assertNotIn("T18:", meta)

    def test_invalid_death_date_does_not_crash(self):
        self.assertEqual(CharControllerMixin()._death_display_meta({"time": "indisponível"}), "indisponível")

    def test_toolbar_alignment_is_scheduled_after_height_update(self):
        app = TibiaToolsApp()
        container = SimpleNamespace(padding=[0, 0, 0, -12])
        bar = SimpleNamespace(ids={"left_actions": SimpleNamespace(parent=container)},
                              bind=lambda **kwargs: None)
        with patch("features.bosses.controller.Clock.schedule_once", side_effect=lambda fn, delay=0: fn()), patch("main.Clock.schedule_once", side_effect=lambda fn, delay=0: fn()):
            app.center_top_app_bar(bar)
        self.assertEqual(container.padding, [0, 0, 0, 0])

    def test_fallback_includes_same_layout_fixes(self):
        self.assertEqual(FALLBACK_KV, get_combined_kv_text())
        self.assertIn("on_kv_post: app.center_top_app_bar(self)", FALLBACK_KV)


if __name__ == "__main__":
    unittest.main()