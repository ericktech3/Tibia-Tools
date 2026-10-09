"""Informações públicas e consistência do visual (unittest, como no CI)."""
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.app_info import APP_VERSION, LEGAL_NOTICE, about_text, get_app_version
from ui.kv_loader import FALLBACK_KV, get_combined_kv_text

ROOT = Path(__file__).resolve().parents[1]


class AppInfoTests(unittest.TestCase):
    def test_desktop_version_matches_build_configuration(self):
        spec = (ROOT / "buildozer.spec").read_text("utf-8")
        expected = re.search(r"(?m)^version\s*=\s*([^\s#]+)", spec).group(1)
        with patch.dict(sys.modules, {"jnius": None}):
            self.assertEqual(get_app_version(), expected)

    def test_android_shows_installed_version_not_archive_number(self):
        activity = SimpleNamespace(
            getPackageManager=lambda: SimpleNamespace(
                getPackageInfo=lambda name, flags: SimpleNamespace(versionName="9.8.7")),
            getPackageName=lambda: "org.erick.tibiatools")
        jnius = SimpleNamespace(autoclass=lambda name: SimpleNamespace(mActivity=activity))
        with patch.dict(sys.modules, {"jnius": jnius}):
            self.assertEqual(get_app_version(), "9.8.7")

    def test_missing_spec_has_safe_fallback(self):
        with patch.dict(sys.modules, {"jnius": None}), patch.object(Path, "read_text", side_effect=OSError):
            self.assertEqual(get_app_version(), APP_VERSION)

    def test_about_includes_version_and_entire_legal_notice(self):
        text = about_text("1.2.1")
        self.assertIn("Versão 1.2.1", text)
        self.assertIn(LEGAL_NOTICE, text)
        self.assertIn("sem vínculo", text)
        self.assertIn("Tibia é marca registrada da CipSoft GmbH", text)

    def test_settings_displays_wrapped_legal_notice(self):
        kv = (ROOT / "ui/kv/settings.kv").read_text("utf-8")
        self.assertIn('text: "Versão " + app.app_version', kv)
        self.assertIn('text: app.legal_notice', kv)
        legal = kv.split('id: set_legal_notice')[1].split('AppCard:')[0]
        self.assertIn('text_size: self.width, None', legal)
        self.assertIn('height: self.texture_size[1] + dp(8)', legal)

    def test_shared_shapes_and_fallback_match(self):
        self.assertEqual(FALLBACK_KV, get_combined_kv_text())
        self.assertIn('rounded_button: True', FALLBACK_KV)
        self.assertIn('#:set CARD_RADIUS dp(22)', FALLBACK_KV)
        self.assertNotIn('radius: [dp(16)', FALLBACK_KV)


if __name__ == "__main__":
    unittest.main()
