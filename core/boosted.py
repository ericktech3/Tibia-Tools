import os
import hashlib
import requests

from core.http_client import get as http_get


def _cache_sprite(url: str, cache_dir: str, prefix: str) -> str:
    """Baixa um sprite remoto e salva localmente.

    - Retorna caminho local (preferencialmente PNG).
    - Em caso de falha, retorna string vazia (pra UI esconder o widget).
    """
    if not url:
        return ""

    try:
        os.makedirs(cache_dir, exist_ok=True)
    except Exception:
        return ""

    # nome determinístico por URL
    h = hashlib.md5(url.encode("utf-8")).hexdigest()  # nosec (somente cache)
    base = os.path.join(cache_dir, f"{prefix}_{h}")

    # detecta extensão
    clean = url.split("?")[0]
    ext = os.path.splitext(clean)[1].lower() or ".img"
    raw_path = base + ext
    png_path = base + ".png"

    # se já temos png cacheado, usa
    if os.path.exists(png_path) and os.path.getsize(png_path) > 0:
        return png_path
    # se existe o original, tenta usar (pode ser png/jpg)
    if os.path.exists(raw_path) and os.path.getsize(raw_path) > 0 and ext in (".png", ".jpg", ".jpeg", ".webp"):
        return raw_path

    # baixa
    try:
        r = http_get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        with open(raw_path, "wb") as f:
            f.write(r.content)
    except Exception:
        return ""

    # Se for GIF (comum nos sprites do tibia.com), converte pra PNG
    if ext == ".gif":
        try:
            from PIL import Image as PILImage  # pillow

            with PILImage.open(raw_path) as im:
                try:
                    im.seek(0)
                except Exception:
                    pass
                im = im.convert("RGBA")
                im.save(png_path, format="PNG")
            # remove o gif cru pra economizar espaço
            try:
                os.remove(raw_path)
            except Exception:
                pass
            return png_path if os.path.exists(png_path) else ""
        except Exception:
            # se não conseguir converter, devolve vazio pra não mostrar placeholder quebrado
            return ""

    # outros formatos: tenta usar o raw
    if os.path.exists(raw_path) and os.path.getsize(raw_path) > 0:
        return raw_path
    return ""

def _sprite_dir() -> str:
    # No Android, precisa ser um diretório gravável (user_data_dir).
    try:
        from kivy.app import App

        app = App.get_running_app()
        if app and getattr(app, "user_data_dir", None):
            return os.path.join(app.user_data_dir, "sprite_cache")
    except Exception:
        pass
    return os.path.join(os.getcwd(), ".sprite_cache")


def parse_boosted(creatures_json, bosses_json) -> dict:
    """Lê o JSON do TibiaData (sem rede). Lança ValueError se o formato mudou."""
    if not isinstance(creatures_json, dict) or not isinstance(bosses_json, dict):
        raise ValueError("resposta do TibiaData em formato inesperado")
    c_boosted = ((creatures_json.get("creatures") or {}).get("boosted") or {})
    b_boosted = ((bosses_json.get("boostable_bosses") or {}).get("boosted") or {})
    if not c_boosted and not b_boosted:
        raise ValueError("boosted ausente na resposta")
    return {
        "creature": c_boosted.get("name") or "N/A",
        "boss": b_boosted.get("name") or "N/A",
        "creature_image_url": c_boosted.get("image_url") or "",
        "boss_image_url": b_boosted.get("image_url") or "",
    }


def fetch_boosted_result():
    """Busca Boosted Creature/Boss e devolve core.result.Result."""
    from core.result import Result, response_meta, run_safely

    def _run():
        rc = http_get("https://api.tibiadata.com/v4/creatures", timeout=10)
        rb = http_get("https://api.tibiadata.com/v4/boostablebosses", timeout=10)
        rc.raise_for_status()
        rb.raise_for_status()
        info = parse_boosted(rc.json(), rb.json())
        base_dir = _sprite_dir()
        data = {
            "creature": info["creature"],
            "boss": info["boss"],
            # cache local (evita placeholder quebrado no AsyncImage, especialmente pra GIF)
            "creature_image": _cache_sprite(info["creature_image_url"], base_dir, "creature"),
            "boss_image": _cache_sprite(info["boss_image_url"], base_dir, "boss"),
        }
        m1, m2 = response_meta(rc), response_meta(rb)
        return Result.success(
            data,
            stale=m1["stale"] or m2["stale"],
            age_seconds=max(m1["age_seconds"], m2["age_seconds"]),
        )

    return run_safely(_run)


def fetch_boosted():
    """Compatibilidade: devolve o dicionário ou None em caso de erro."""
    res = fetch_boosted_result()
    return res.data if res.ok else None
