import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_kivy_stubs():
    kivy = sys.modules.get("kivy") or types.ModuleType("kivy")
    kivy.__path__ = []

    kivy_clock = types.ModuleType("kivy.clock")
    kivy_clock.Clock = SimpleNamespace(
        schedule_once=lambda fn, dt=0: fn(dt),
        schedule_interval=lambda fn, dt=0: None,
    )

    kivy_lang = types.ModuleType("kivy.lang")
    kivy_lang.Builder = object()

    kivy_metrics = types.ModuleType("kivy.metrics")
    kivy_metrics.dp = lambda value: value

    kivy_core = sys.modules.get("kivy.core") or types.ModuleType("kivy.core")
    kivy_core.__path__ = []
    kivy_clipboard = types.ModuleType("kivy.core.clipboard")
    kivy_clipboard.Clipboard = SimpleNamespace(copy=lambda value: None)

    class _DummyWindow:
        @staticmethod
        def bind(**kwargs):
            return None

        @staticmethod
        def unbind(**kwargs):
            return None

    kivy_window = types.ModuleType("kivy.core.window")
    kivy_window.Window = _DummyWindow

    kivy_properties = types.ModuleType("kivy.properties")
    kivy_properties.StringProperty = lambda *args, **kwargs: None

    kivy_screenmanager = types.ModuleType("kivy.uix.screenmanager")
    kivy_screenmanager.ScreenManager = type("ScreenManager", (), {})

    kivy_behaviors = types.ModuleType("kivy.uix.behaviors")
    kivy_behaviors.ButtonBehavior = type("ButtonBehavior", (), {})

    kivy_utils = types.ModuleType("kivy.utils")
    kivy_utils.platform = "linux"

    kivymd = types.ModuleType("kivymd")
    kivymd.__path__ = []
    kivymd_uix = types.ModuleType("kivymd.uix")
    kivymd_uix.__path__ = []

    app_mod = types.ModuleType("kivymd.app")
    app_mod.MDApp = type("MDApp", (), {"__init__": lambda self, **kwargs: None})

    dialog_mod = types.ModuleType("kivymd.uix.dialog")
    dialog_mod.MDDialog = type("MDDialog", (), {})

    button_mod = types.ModuleType("kivymd.uix.button")
    button_mod.MDFlatButton = type("MDFlatButton", (), {})
    button_mod.MDRectangleFlatIconButton = type("MDRectangleFlatIconButton", (), {})

    list_mod = types.ModuleType("kivymd.uix.list")
    for name in ["OneLineIconListItem", "OneLineListItem", "TwoLineIconListItem", "IconLeftWidget"]:
        setattr(list_mod, name, type(name, (), {}))

    menu_mod = types.ModuleType("kivymd.uix.menu")
    menu_mod.MDDropdownMenu = type("MDDropdownMenu", (), {})

    box_mod = types.ModuleType("kivymd.uix.boxlayout")
    box_mod.MDBoxLayout = type("MDBoxLayout", (), {})

    label_mod = types.ModuleType("kivymd.uix.label")
    label_mod.MDLabel = type("MDLabel", (), {})

    behavior_mod = types.ModuleType("kivymd.uix.behaviors")
    behavior_mod.RectangularRippleBehavior = type("RectangularRippleBehavior", (), {})

    scroll_mod = types.ModuleType("kivymd.uix.scrollview")
    scroll_mod.MDScrollView = type("MDScrollView", (), {})

    sys.modules.update(
        {
            "kivy": kivy,
            "kivy.clock": kivy_clock,
            "kivy.lang": kivy_lang,
            "kivy.metrics": kivy_metrics,
            "kivy.core": kivy_core,
            "kivy.core.clipboard": kivy_clipboard,
            "kivy.core.window": kivy_window,
            "kivy.properties": kivy_properties,
            "kivy.uix.screenmanager": kivy_screenmanager,
            "kivy.uix.behaviors": kivy_behaviors,
            "kivy.utils": kivy_utils,
            "kivymd": kivymd,
            "kivymd.uix": kivymd_uix,
            "kivymd.app": app_mod,
            "kivymd.uix.dialog": dialog_mod,
            "kivymd.uix.button": button_mod,
            "kivymd.uix.list": list_mod,
            "kivymd.uix.menu": menu_mod,
            "kivymd.uix.boxlayout": box_mod,
            "kivymd.uix.label": label_mod,
            "kivymd.uix.behaviors": behavior_mod,
            "kivymd.uix.scrollview": scroll_mod,
        }
    )


_install_kivy_stubs()
from main import TibiaToolsApp


class BackNavigationEventsTests(unittest.TestCase):
    def make_app(self):
        app = TibiaToolsApp()
        app.toast_messages = []
        app.toast = lambda msg: app.toast_messages.append(msg)
        return app

    def test_request_close_is_consumed_on_first_back(self):
        app = self.make_app()
        app.navigate_back = lambda *args: False
        handled = app._on_window_request_close()
        self.assertTrue(handled)
        self.assertEqual(app.toast_messages, ["Pressione voltar novamente para sair"])

    def test_duplicate_keyboard_then_request_close_does_not_exit(self):
        app = self.make_app()
        app.navigate_back = lambda *args: False
        first = app._on_window_keyboard(None, 27)
        second = app._on_window_request_close()
        self.assertTrue(first)
        self.assertTrue(second)
        self.assertEqual(app.toast_messages, ["Pressione voltar novamente para sair"])


if __name__ == "__main__":
    unittest.main()
