from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_service_requests_auto_restart_and_wakelock():
    src = (ROOT / "service" / "main.py").read_text(encoding="utf-8")
    assert "setAutoRestartService(True)" in src
    assert "PARTIAL_WAKE_LOCK" in src
    assert src.count("_android_release_keep_alive()\n") >= 2


def test_battery_permission_declared():
    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    assert "REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" in spec


def test_bridge_prompts_battery_exemption():
    src = (ROOT / "services" / "android_bridge.py").read_text(encoding="utf-8")
    assert "ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" in src
