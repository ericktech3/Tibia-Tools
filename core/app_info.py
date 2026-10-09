"""Identificação pública do aplicativo, sem dependência de Kivy."""
from pathlib import Path
import re

APP_NAME = "Tibia Tools"
# Valor de reserva para cópias empacotadas sem buildozer.spec.
APP_VERSION = "1.2.1"
LEGAL_NOTICE = (
    "Tibia Tools é um aplicativo independente, não oficial, sem vínculo, "
    "patrocínio ou aprovação da CipSoft GmbH. Tibia é marca registrada da "
    "CipSoft GmbH. As marcas, imagens e demais conteúdos relacionados ao "
    "jogo pertencem aos seus respectivos titulares."
)


def get_app_version() -> str:
    """Android: versão do APK instalado; desktop: versão da configuração."""
    try:
        from jnius import autoclass
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        if activity is not None:
            info = activity.getPackageManager().getPackageInfo(activity.getPackageName(), 0)
            version = str(info.versionName or "").strip()
            if version:
                return version
    except Exception:
        # Pyjnius/Activity não existe fora do Android; usar configuração local.
        pass
    try:
        spec = Path(__file__).resolve().parents[1] / "buildozer.spec"
        match = re.search(r"(?m)^version\s*=\s*([^\s#]+)", spec.read_text("utf-8"))
        if match:
            return match.group(1)
    except (OSError, UnicodeError):
        pass
    return APP_VERSION


def about_text(version: str) -> str:
    return (
        f"{APP_NAME}\nVersão {version}\n\n"
        "Personagens, histórico de XP e mortes, favoritos, bosses, boosted "
        "e ferramentas de treino e hunts.\n\n"
        "Fontes: TibiaData, Tibia.com e fansites auxiliares. "
        "A disponibilidade e a atualização dos dados dependem dessas fontes.\n\n"
        + LEGAL_NOTICE
    )
