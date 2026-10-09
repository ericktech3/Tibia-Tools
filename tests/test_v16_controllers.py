"""Garante que as telas separadas do main.py continuam ligadas ao app."""
import unittest

from test_back_navigation_events import TibiaToolsApp

EXPECTED = {
    "features.bosses.controller": ["bosses_fetch", "bosses_apply_filters", "boss_toggle_favorite", "open_world_menu"],
    "features.boosted.controller": ["update_boosted", "_boosted_done"],
    "features.training.controller": ["training_calculate", "training_open_menu"],
    "features.char.display": ["_char_show_result", "_char_show_error", "_char_set_loading"],
    "features.char.stalker": ["_build_stalker_candidate_widget", "open_char_from_stalker_list"],
    "features.char.history": ["open_char_history_menu", "_add_to_char_history"],
    "features.imbuements.controller": ["imbuements_refresh_list", "imbuement_toggle_favorite", "_imbu_show"],
}


class ControllerSplitTests(unittest.TestCase):
    def test_methods_live_in_feature_modules_and_reach_app(self):
        for module, names in EXPECTED.items():
            for n in names:
                fn = getattr(TibiaToolsApp, n, None)
                self.assertIsNotNone(fn, n)
                self.assertEqual(module, fn.__module__, n)

    def test_main_no_longer_defines_them(self):
        import main
        src = open(main.__file__, encoding="utf-8").read()
        for names in EXPECTED.values():
            for n in names:
                self.assertNotIn(f"    def {n}(", src, n)


if __name__ == "__main__":
    unittest.main()
