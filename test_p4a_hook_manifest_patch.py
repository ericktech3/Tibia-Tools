import importlib.util
import tempfile
import unittest
from pathlib import Path


HOOK_PATH = Path(__file__).resolve().parents[1] / 'p4a' / 'hook.py'
SPEC = importlib.util.spec_from_file_location('p4a_hook', HOOK_PATH)
hook = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(hook)


class P4aHookManifestPatchTests(unittest.TestCase):
    def test_adds_foreground_service_type_for_fully_qualified_service_name(self):
        manifest = '''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="org.erick.tibiatools">
    <application>
        <service android:name="org.erick.tibiatools.ServiceFavwatch" android:exported="false" />
    </application>
</manifest>
'''

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / 'AndroidManifest.xml'
            manifest_path.write_text(manifest, encoding='utf-8')

            changed = hook._patch_manifest_file(manifest_path)
            patched = manifest_path.read_text(encoding='utf-8')

        self.assertTrue(changed)
        self.assertIn('android:name="org.erick.tibiatools.ServiceFavwatch"', patched)
        self.assertIn('android:foregroundServiceType="dataSync"', patched)
        self.assertIn('android.permission.FOREGROUND_SERVICE_DATA_SYNC', patched)

    def test_patch_is_idempotent(self):
        manifest = '''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="org.erick.tibiatools">
    <application>
        <service android:name="org.erick.tibiatools.ServiceFavwatch" android:exported="false" />
    </application>
</manifest>
'''

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / 'AndroidManifest.xml'
            manifest_path.write_text(manifest, encoding='utf-8')

            first_changed = hook._patch_manifest_file(manifest_path)
            second_changed = hook._patch_manifest_file(manifest_path)
            patched = manifest_path.read_text(encoding='utf-8')

        self.assertTrue(first_changed)
        self.assertFalse(second_changed)
        self.assertEqual(patched.count('android:foregroundServiceType="dataSync"'), 1)
        self.assertEqual(patched.count('android.permission.FOREGROUND_SERVICE_DATA_SYNC'), 1)


    def test_disables_predictive_back_on_application_and_activity(self):
        manifest = '''<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application android:label="Tibia Tools">
        <activity android:name="org.kivy.android.PythonActivity" android:exported="true">
        </activity>
    </application>
</manifest>
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            mp = Path(tmpdir) / 'AndroidManifest.xml'
            mp.write_text(manifest, encoding='utf-8')
            hook._patch_manifest_file(mp)
            hook._patch_manifest_file(mp)
            patched = mp.read_text(encoding='utf-8')
        self.assertEqual(patched.count('android:enableOnBackInvokedCallback="false"'), 2)
        self.assertIn('<application android:enableOnBackInvokedCallback="false" android:label', patched)


if __name__ == '__main__':
    unittest.main()
