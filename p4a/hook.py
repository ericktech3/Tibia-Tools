"""python-for-android hook.

Why this exists
---------------
Buildozer 1.5.0 can generate an invalid AndroidManifest.xml when using
`android.extra_manifest_application_arguments` (manifest merger fails).

We add our BootReceiver via this hook *before* the APK build runs.

This keeps the build stable across CI environments.
"""

from __future__ import annotations

from pathlib import Path
import re


RECEIVER_XML = """
    <receiver
        android:name=\"org.erick.tibiatools.BootReceiver\"
        android:enabled=\"true\"
        android:exported=\"true\">
        <intent-filter>
            <action android:name=\"android.intent.action.BOOT_COMPLETED\" />
            <action android:name=\"android.intent.action.LOCKED_BOOT_COMPLETED\" />
            <action android:name=\"android.intent.action.MY_PACKAGE_REPLACED\" />
            <action android:name=\"android.intent.action.QUICKBOOT_POWERON\" />
        </intent-filter>
    </receiver>
""".strip(
    "\n"
)


def _candidate_manifest_paths(toolchain) -> list[Path]:
    """Return a short list of likely manifest locations."""
    candidates: list[Path] = []

    # O hook roda de dentro da pasta da distribuicao: este e o manifesto real.
    candidates.append(Path("src/main/AndroidManifest.xml"))

    # Most common: toolchain._dist.dist_dir points to the dist folder.
    try:
        dist_dir = getattr(getattr(toolchain, "_dist", None), "dist_dir", None)
    except Exception:
        dist_dir = None
    if dist_dir:
        d = Path(dist_dir)
        candidates.append(d / "src/main/AndroidManifest.xml")

        # If dist_dir is only the dist *name*, try with ctx.dist_dir.
        ctx = getattr(toolchain, "ctx", None)
        ctx_dist = getattr(ctx, "dist_dir", None)
        if ctx_dist:
            candidates.append(Path(ctx_dist) / str(dist_dir) / "src/main/AndroidManifest.xml")

    # Fallbacks: search in .buildozer folder (used by Buildozer)
    cwd = Path(".").resolve()
    candidates.extend(
        sorted(cwd.glob(".buildozer/android/platform/build-*/dists/*/src/main/AndroidManifest.xml"))
    )

    # Deduplicate while preserving order
    seen = set()
    out: list[Path] = []
    for p in candidates:
        pp = p.resolve()
        if pp in seen:
            continue
        seen.add(pp)
        out.append(pp)
    return out


def _patch_manifest_file(manifest_path: Path) -> bool:
    """Inject receiver + foreground-service metadata into AndroidManifest.xml.

    Returns True if the file was changed.
    """
    if not manifest_path.exists():
        return False

    text = manifest_path.read_text("utf-8", errors="replace")
    changed = False

    # Ensure specific permission for dataSync foreground service.
    perm = '<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />'
    if 'android.permission.FOREGROUND_SERVICE_DATA_SYNC' not in text:
        manifest_close = text.find('>')
        app_idx = text.find('<application')
        if app_idx != -1:
            text = text[:app_idx] + perm + "\n" + text[app_idx:]
            changed = True

    # Android 16 (targetSdk 36) ativa o "predictive back" por padrao: o gesto/botao
    # voltar fecha a Activity sem enviar KEYCODE_BACK ao Kivy. Desativamos para
    # que o app receba o voltar e navegue para a aba anterior.
    # Aplica tanto no <application> quanto na Activity principal.
    def _add_back_flag(m):
        nonlocal changed
        tag = m.group(0)
        if 'enableOnBackInvokedCallback' in tag:
            return tag
        changed = True
        name = m.group(1)
        return f'<{name} android:enableOnBackInvokedCallback="false"' + tag[len(name) + 1:]
    text = re.sub(r'<(application)\b[^>]*>', _add_back_flag, text, count=1)
    text = re.sub(r'<(activity)\b[^>]*PythonActivity[^>]*>', _add_back_flag, text, count=1)

    # Ensure BootReceiver exists.
    if 'org.erick.tibiatools.BootReceiver' not in text:
        close_tag = '</application>'
        idx = text.rfind(close_tag)
        if idx == -1:
            return changed
        text = text[:idx] + "\n" + RECEIVER_XML + "\n" + text[idx:]
        changed = True

    # Ensure generated ServiceFavwatch has explicit foregroundServiceType.
    # Accept both `.ServiceFavwatch` and fully qualified names such as
    # `org.erick.tibiatools.ServiceFavwatch`, including self-closing tags.
    service_pattern = re.compile(
        r'(<service\b[^>]*android:name="(?:[^"]*\.)?ServiceFavwatch"[^>]*?)(\s*/?>)',
        re.IGNORECASE,
    )
    def add_type(m):
        head, tail = m.group(1), m.group(2)
        nonlocal changed
        if 'foregroundServiceType' in head:
            return m.group(0)
        changed = True
        return f'{head} android:foregroundServiceType="dataSync"{tail}'
    text = service_pattern.sub(add_type, text)

    if changed:
        manifest_path.write_text(text, 'utf-8')
    return changed


def _ensure_receiver(toolchain) -> None:
    try:
        paths = _candidate_manifest_paths(toolchain)
    except Exception:
        paths = [Path("src/main/AndroidManifest.xml")]
    for mf in paths:
        try:
            if _patch_manifest_file(mf):
                print(f"[tibia-tools hook] AndroidManifest atualizado: {mf}")
        except Exception:
            # Ignore and try next candidate.
            continue


# Hook entry points
# python-for-android calls these if present.

def before_apk_build(toolchain):  # noqa: N802
    _ensure_receiver(toolchain)


def before_apk_package(toolchain):  # noqa: N802
    _ensure_receiver(toolchain)


def after_apk_build(toolchain):  # noqa: N802
    # O manifesto e gerado de novo durante o build: aplica depois dele.
    _ensure_receiver(toolchain)


def before_apk_assemble(toolchain):  # noqa: N802
    # Ultima chance antes do Gradle empacotar o APK.
    _ensure_receiver(toolchain)
