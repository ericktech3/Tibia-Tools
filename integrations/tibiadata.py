"""HTTP helpers + aliases de compatibilidade.

Este módulo existe para evitar que mudanças de nome quebrem o app no Android.
A UI (main.py) usa principalmente:
- fetch_character_tibiadata  -> JSON completo da TibiaData v4
- fetch_worlds_tibiadata     -> JSON completo da lista de mundos

Também expomos:
- fetch_character_snapshot   -> snapshot leve (para service/monitor)
- is_character_online_tibiadata -> fallback para status Online/Offline via /v4/world/{world}
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import date as _date
import re
import time
import html as _html
from urllib.parse import quote, quote_plus, urljoin

import requests
from bs4 import BeautifulSoup


# TibiaData v4
WORLDS_URL = "https://api.tibiadata.com/v4/worlds"
CHAR_URL = "https://api.tibiadata.com/v4/character/{name}"
WORLD_URL = "https://api.tibiadata.com/v4/world/{world}"

# GuildStats (fansite) – usado apenas para complementar informações (ex: xp lost em mortes)
GUILDSTATS_DEATHS_URL = "https://guildstats.eu/character?nick={name}&tab=5"

# GuildStats (fansite) – histórico de experiência (tab=9)
GUILDSTATS_EXP_URL = "https://guildstats.eu/character?nick={name}&tab=9"

# Tibia.com (oficial) – fallback extra para detectar ONLINE
# Preferimos a página do personagem (não é paginada como a lista do world).
TIBIA_CHAR_URL = "https://www.tibia.com/community/?subtopic=characters&name={name}"

# Alguns fansites servem um HTML reduzido/alternativo para user-agents mobile.
# Para o GuildStats, preferimos um UA de navegador desktop para aumentar a chance
# de receber a página completa da aba Experience.
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
}


def _get_json(url: str, timeout: int) -> Dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=timeout, headers=UA)
            # Alguns endpoints podem devolver 5xx temporariamente
            if int(getattr(r, "status_code", 0) or 0) >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_exc = e
            if attempt < 2:
                time.sleep(0.6 * (2 ** attempt))
            continue
    if last_exc:
        raise last_exc
    return {}


def _get_text(url: str, timeout: int, headers: Optional[dict] = None) -> str:
    """GET com retry básico (evita falhas temporárias)"""
    hdr = headers or UA
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            try:
                r = requests.get(url, timeout=timeout, headers=hdr)
            except requests.exceptions.SSLError:
                # Fansites podem falhar em alguns builds Android com OpenSSL/CA antigos.
                # Como é uma fonte auxiliar e somente leitura, tentamos novamente sem verify.
                r = requests.get(url, timeout=timeout, headers=hdr, verify=False)
            if int(getattr(r, "status_code", 0) or 0) >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
            if r.status_code != 200:
                return ""
            return r.text or ""
        except Exception as e:
            last_exc = e
            if attempt < 2:
                time.sleep(0.6 * (2 ** attempt))
            continue
    _ = last_exc
    return ""


def _new_browser_session() -> requests.Session:
    sess = requests.Session()
    try:
        sess.headers.update({
            **UA,
            "Referer": "https://guildstats.eu/",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Upgrade-Insecure-Requests": "1",
            # On Android, keeping encodings simple helps avoid responses that
            # requests may fail to decode reliably on some builds (e.g. br/zstd).
            "Accept-Encoding": "gzip, deflate",
        })
    except Exception:
        pass
    return sess


def _session_get_text(session: requests.Session, url: str, timeout: int, headers: Optional[dict] = None) -> str:
    hdr = headers or {}
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            try:
                r = session.get(url, timeout=timeout, headers=hdr or None, allow_redirects=True)
            except requests.exceptions.SSLError:
                r = session.get(url, timeout=timeout, headers=hdr or None, allow_redirects=True, verify=False)
            if int(getattr(r, "status_code", 0) or 0) >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
            if r.status_code != 200:
                return ""
            return r.text or ""
        except Exception as e:
            last_exc = e
            if attempt < 2:
                time.sleep(0.6 * (2 ** attempt))
            continue
    _ = last_exc
    return ""


def _guildstats_blocked_or_empty(html_text: str) -> bool:
    low = (html_text or "").lower()
    if not low.strip():
        return True
    block_markers = (
        "checking your browser",
        "just a moment",
        "cf-browser-verification",
        "attention required",
        "verify you are human",
        "enable javascript",
        "access denied",
        "captcha",
        "security check",
    )
    return any(marker in low for marker in block_markers)


def _html_to_plain_text(html_text: str) -> str:
    txt = html_text or ""
    txt = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", txt)
    txt = re.sub(r"(?i)<br\s*/?>", " ", txt)
    txt = re.sub(r"(?is)<[^>]+>", " ", txt)
    try:
        txt = _html.unescape(txt)
    except Exception:
        pass
    txt = txt.replace("\xa0", " ")
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def _has_guildstats_exp_structure(html_text: str) -> bool:
    plain = _html_to_plain_text(html_text).lower()
    if not plain:
        return False

    date_hits = len(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", plain))
    short_date_hits = len(re.findall(r"\b\d{2}-\d{2}\b", plain))

    direct_markers = (
        "date exp change",
        "date change",
        "data mudança de exp",
        "data mudanca de exp",
        "mudanca de exp",
        "mudança de exp",
    )
    if any(marker in plain for marker in direct_markers):
        return True

    context_markers = (
        "avg exp per hour",
        "average daily exp",
        "best recorded day",
        "time on-line",
        "time online",
        "vocation rank",
        "rank da vocação",
        "rank da vocacao",
        "total in month",
        "total no mês",
        "total no mes",
    )
    if (date_hits >= 2 or short_date_hits >= 2) and any(marker in plain for marker in context_markers):
        return True

    try:
        soup = BeautifulSoup(html_text or "", "html.parser")
    except Exception:
        soup = None

    if soup is not None:
        for table in soup.find_all("table"):
            headers = [re.sub(r"\s+", " ", (th.get_text(" ", strip=True) or "")).strip().lower() for th in table.find_all("th")]
            if not headers:
                continue
            joined = " | ".join(headers)
            has_date = any(h == "date" or h == "data" or "date" in h or "data" in h for h in headers)
            has_change = any(("exp" in h and "change" in h) or h == "change" or "mudanca" in h or "mudança" in h for h in headers)
            if has_date and has_change:
                return True
            if has_date and ("avg exp per hour" in joined or "time on-line" in joined or "vocation rank" in joined):
                return True

    return False


def _looks_like_guildstats_exp_page(html_text: str) -> bool:
    plain = _html_to_plain_text(html_text).lower()
    if not plain:
        return False

    if _has_guildstats_exp_structure(html_text):
        return True

    if re.search(r"\bdate\b.*\bexp\s+change\b.*\bexperience\b", plain):
        return True
    if re.search(r"\bdate\b.*\bchange\b.*\btime\s*on-?line\b", plain):
        return True
    if re.search(r"\bdata\b.*\bexp\b.*\bexperi", plain):
        return True
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", plain) and ("vocation rank" in plain or "time on-line" in plain):
        return True
    if re.search(r"\b\d{2}-\d{2}\b", plain) and ("avg exp per hour" in plain or "time on-line" in plain or "vocation rank" in plain):
        return True
    return False


def _extract_guildstats_tab_url(base_html: str, tab_number: str) -> str:
    txt = base_html or ""
    if not txt:
        return ""
    pat = re.compile(
        r'href\s*=\s*["\'](?P<href>[^"\']*character[^"\']*tab='
        + re.escape(str(tab_number))
        + r'[^"\']*)["\']',
        re.I,
    )
    m = pat.search(txt)
    if not m:
        return ""
    href = _html.unescape(str(m.group("href") or "").strip())
    if not href:
        return ""
    return urljoin("https://guildstats.eu/", href)


def _extract_guildstats_exp_links(base_html: str) -> List[str]:
    txt = base_html or ""
    if not txt:
        return []

    out: List[str] = []

    try:
        soup = BeautifulSoup(txt, "html.parser")
    except Exception:
        soup = None

    if soup is not None:
        exp_tokens = ("experience", "experiencia", "experiência", "exp")
        for a in soup.find_all("a"):
            href = str(a.get("href") or "").strip()
            if not href:
                continue
            href_low = href.lower()
            label = re.sub(r"\s+", " ", (a.get_text(" ", strip=True) or "")).strip().lower()
            if not label:
                continue
            if not any(tok in label for tok in exp_tokens):
                continue
            if "character" not in href_low and "tab=9" not in href_low:
                continue
            out.append(urljoin("https://guildstats.eu/", _html.unescape(href)))

    tab_url = _extract_guildstats_tab_url(txt, "9")
    if tab_url:
        out.append(tab_url)
    return _unique_preserve_order(out)


def _extract_guildstats_exp_link(base_html: str) -> str:
    links = _extract_guildstats_exp_links(base_html)
    return links[0] if links else ""


def _unique_preserve_order(urls: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in urls or []:
        u = str(raw or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out



def _diag_log(message: str) -> None:
    try:
        print(f"[gs-exp] {message}")
    except Exception:
        pass


def _log_preview(text: str, limit: int = 220) -> str:
    raw = str(text or "").replace("\n", " ").replace("\r", " ")
    raw = re.sub(r"\s+", " ", raw).strip()
    if len(raw) <= limit:
        return raw
    return raw[:limit] + " ..."

def _fetch_guildstats_exp_html(name: str, timeout: int = 12) -> str:
    enc_quote = quote(name, safe="")
    enc_plus = quote_plus(name)

    base_urls = [
        f"https://guildstats.eu/character?lang=en&nick={enc_plus}",
        f"https://guildstats.eu/character?lang=pt&nick={enc_plus}",
        f"https://guildstats.eu/character?nick={enc_plus}",
        f"https://guildstats.eu/character?lang=en&nick={enc_quote}",
        f"https://guildstats.eu/character?lang=pt&nick={enc_quote}",
        f"https://guildstats.eu/character?nick={enc_quote}",
    ]
    tab_urls = [
        GUILDSTATS_EXP_URL.format(name=enc_quote),
        GUILDSTATS_EXP_URL.format(name=enc_plus),
        GUILDSTATS_EXP_URL.format(name=enc_quote) + "&lang=pt",
        GUILDSTATS_EXP_URL.format(name=enc_quote) + "&lang=en",
        GUILDSTATS_EXP_URL.format(name=enc_plus) + "&lang=pt",
        GUILDSTATS_EXP_URL.format(name=enc_plus) + "&lang=en",
    ]

    session = _new_browser_session()
    headers = {
        "Referer": "https://guildstats.eu/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Accept": UA.get("Accept", "*/*"),
        "Accept-Language": UA.get("Accept-Language", "en-US,en;q=0.8"),
    }

    _diag_log(f"fetch start name={name!r}")

    base_html = ""
    base_url_used = ""
    for url in _unique_preserve_order(base_urls):
        req_headers = dict(headers)
        if base_url_used:
            req_headers["Referer"] = base_url_used
        txt = _session_get_text(session, url, timeout=timeout, headers=req_headers)
        if not txt:
            _diag_log(f"base empty url={url}")
            continue
        if _guildstats_blocked_or_empty(txt):
            _diag_log(f"base blocked url={url} snippet={_log_preview(_html_to_plain_text(txt))}")
            continue
        base_html = txt
        base_url_used = url
        _diag_log(f"base ok url={url} len={len(txt)} snippet={_log_preview(_html_to_plain_text(txt))}")
        break

    candidate_urls: List[str] = []
    extracted_links = _extract_guildstats_exp_links(base_html)
    if extracted_links:
        _diag_log(
            "exp link candidates="
            + ", ".join(_log_preview(u, 140) for u in extracted_links[:4])
        )
        candidate_urls.extend(extracted_links)
    else:
        _diag_log("exp link candidates=none")

    if base_html and _has_guildstats_exp_structure(base_html):
        _diag_log("base page already contains exp-like structure; keeping it as fallback candidate")

    candidate_urls.extend(tab_urls)

    if base_html and _has_guildstats_exp_structure(base_html):
        # A pagina base do personagem pode conter um teaser/resumo da Experience,
        # mas nao necessariamente a tabela completa do historico. Tentamos as URLs
        # explicitas da aba antes de cair nesse HTML base, para evitar parar cedo
        # num fallback parcial que costuma gerar poucos registros ou zeros.
        candidate_urls.append("__base_html__")

    best_html = ""
    best_score = -1
    best_url = ""
    best_looks = False
    for url in _unique_preserve_order(candidate_urls):
        req_headers = dict(headers)
        if base_url_used:
            req_headers["Referer"] = base_url_used
        if url == "__base_html__":
            txt = base_html
        else:
            txt = _session_get_text(session, url, timeout=timeout, headers=req_headers)
        if not txt:
            _diag_log(f"tab empty url={url}")
            continue
        if _guildstats_blocked_or_empty(txt):
            _diag_log(f"tab blocked url={url} snippet={_log_preview(_html_to_plain_text(txt))}")
            continue

        plain = _html_to_plain_text(txt).lower()
        looks_exp = _looks_like_guildstats_exp_page(txt)
        score = 0
        if looks_exp:
            score += 1000
        score += len(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", plain))
        if "avg exp per hour" in plain:
            score += 50
        if "total in month" in plain:
            score += 50

        _diag_log(
            f"tab ok url={url} len={len(txt)} score={score} looks_exp={looks_exp} "
            f"snippet={_log_preview(plain)}"
        )

        if score > best_score:
            best_html = txt
            best_score = score
            best_url = url
            best_looks = looks_exp
        if url != "__base_html__" and looks_exp and score >= 1000:
            break

    if best_html:
        structural = _has_guildstats_exp_structure(best_html)
        _diag_log(
            f"selected exp html score={best_score} url={best_url} looks_exp={best_looks} structural={structural}"
        )
        if not best_looks and not structural:
            _diag_log(
                f"rejecting selected html because looks_exp=False and structural=False score={best_score} url={best_url}"
            )
            return ""
    else:
        _diag_log("no usable exp html found")
    return best_html


def fetch_worlds_tibiadata(timeout: int = 12) -> Dict[str, Any]:
    """JSON completo do endpoint /v4/worlds."""
    return _get_json(WORLDS_URL, timeout)


# Compat: alguns lugares antigos chamavam fetch_worlds()
def fetch_worlds(timeout: int = 12) -> List[str]:
    """Lista simples de nomes de worlds (compat)."""
    data = fetch_worlds_tibiadata(timeout=timeout)
    worlds = data.get("worlds", {}).get("regular_worlds", []) or []
    out: List[str] = []
    for w in worlds:
        if isinstance(w, dict) and w.get("name"):
            out.append(str(w["name"]))
    return out


def fetch_character_tibiadata(name: str, timeout: int = 12) -> Dict[str, Any]:
    """JSON completo do endpoint /v4/character/{name}."""
    safe_name = quote(name)
    return _get_json(CHAR_URL.format(name=safe_name), timeout)


def fetch_character_snapshot(name: str, timeout: int = 12) -> Dict[str, Any]:
    """Snapshot leve (compat).

    Mantemos a assinatura para evitar quebrar código antigo. Hoje, retorna um
    subconjunto do /v4/character.
    """
    data = fetch_character_tibiadata(name=name, timeout=timeout)
    ch = (
        data.get("character", {})
        .get("character", {})
        or {}
    )
    return {
        "name": ch.get("name"),
        "world": ch.get("world"),
        "level": ch.get("level"),
        "vocation": ch.get("vocation"),
        "status": ch.get("status"),
        "url": f"https://www.tibia.com/community/?subtopic=characters&name={quote(name)}",
    }


def is_character_online_tibiadata(name: str, world: Optional[str] = None, timeout: int = 12) -> Optional[bool]:
    """
    Retorna:
      - True  -> online
      - False -> offline
      - None  -> falha (para permitir fallback em outro método)

    Se world não for informado, usa o endpoint do personagem (que já traz status).
    """
    try:
        # Sem world: endpoint do personagem (melhor para Favoritos)
        if not world:
            data = fetch_character_tibiadata(name, timeout=timeout)
            status = None
            if isinstance(data, dict):
                char_block = data.get("character")
                if isinstance(char_block, dict):
                    inner = char_block.get("character") if isinstance(char_block.get("character"), dict) else char_block
                    if isinstance(inner, dict):
                        status = inner.get("status") or inner.get("state") or inner.get("online_status")
            if isinstance(status, str):
                st = status.strip().lower()
                if st == "online":
                    return True
                if st == "offline":
                    return False
            # Sem status: assume offline (sem "desconhecido" na UI)
            return False

        # Com world: checa lista de online players do mundo
        safe_world = quote(str(world).strip())
        url = f"https://api.tibiadata.com/v4/world/{safe_world}"
        data = _get_json(url, timeout=timeout)

        world_block = (data or {}).get("world", {}) if isinstance(data, dict) else {}
        players = None
        if isinstance(world_block, dict):
            players = world_block.get("online_players") or world_block.get("players_online") or world_block.get("players")
            if isinstance(players, dict):
                players = players.get("online_players") or players.get("players") or players.get("data")
        if not players or not isinstance(players, list):
            return False

        target = name.strip().lower()
        for p in players:
            if isinstance(p, dict):
                pname = p.get("name") or p.get("player_name")
            else:
                pname = p
            if isinstance(pname, str) and pname.strip().lower() == target:
                return True
        return False
    except Exception:
        return None

def is_character_online_tibia_com(name: str, world: str, timeout: int = 12, *, light_only: bool = False) -> Optional[bool]:
    """Fallback extra usando o site oficial (tibia.com) para checar se o char está online.

    Importante: NÃO usamos a página do world porque é paginada (pode dar falso OFFLINE).

    Retorna:
    - True/False se conseguimos checar
    - None se houve erro/parsing falhou
    """
    _ = world  # mantemos o parâmetro por compatibilidade
    try:
        safe_name = quote_plus(str(name))
        url = TIBIA_CHAR_URL.format(name=safe_name)
        html = _get_text(url, timeout=timeout, headers=UA)
        if not html:
            return None
        # Fast path: tenta achar o Status via regex (evita BeautifulSoup e reduz uso de CPU/GIL no Android)
        try:
            m = re.search(r"status:</td>\s*<td[^>]*>\s*(online|offline)\s*<", html, flags=re.I)
            if m:
                return m.group(1).strip().lower() == "online"
        except Exception:
            pass

        if light_only:
            return None

        soup = BeautifulSoup(html, "html.parser")
        # A página do char tem uma tabela com linhas "Label" / "Value".
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            k = (tds[0].get_text(" ", strip=True) or "").strip().rstrip(":").strip().lower()
            if k != "status":
                continue
            v = (tds[1].get_text(" ", strip=True) or "").strip().lower()
            if "online" in v:
                return True
            if "offline" in v:
                return False
            return None

        return None
    except Exception:
        return None


def fetch_guildstats_deaths_xp(name: str, timeout: int = 12, *, light_only: bool = False) -> List[str]:
    """Retorna a lista de 'Exp lost' (strings) do GuildStats, em ordem (mais recente primeiro).

    Observação: é um complemento (fansite). Se falhar, devolve lista vazia.
    """
    try:
        # Em query-string, preferimos + para espaços.
        safe = quote_plus(name)
        base_url = GUILDSTATS_DEATHS_URL.format(name=safe)

        def fetch_html(u: str) -> str:
            try:
                return _get_text(u, timeout=timeout, headers=UA)
            except Exception:
                return ""

        # Alguns ambientes/rotas podem variar por linguagem; tentamos algumas opções.
        html = ""
        for u in (base_url, base_url + "&lang=pt", base_url + "&lang=en"):
            html = fetch_html(u)
            if html:
                break
        if not html:
            return []

        # Alguns chars não têm a lista atualizada (GuildStats mostra uma mensagem e não renderiza tabela).
        if "death list is not updated" in html.lower():
            return []

        # Fast path: tenta extrair a coluna "Exp lost" via regex (sem BeautifulSoup) — bem mais leve no Android
        try:
            low = html.lower()
            if "exp lost" in low:
                pos = low.find("exp lost")
                table_start = low.rfind("<table", 0, pos)
                table_end = low.find("</table>", pos)
                chunk = ""
                if table_start != -1 and table_end != -1 and table_end > table_start:
                    chunk = html[table_start:table_end]
                else:
                    chunk = html[pos:pos + 20000]  # limite defensivo

                vals: List[str] = []
                for m1 in re.finditer(r"<td[^>]*>\s*(-\s*[\d\.,]+)\s*</td>", chunk, flags=re.I):
                    raw = (m1.group(1) or "").strip()
                    digits = re.findall(r"\d+", raw)
                    if not digits:
                        continue
                    num = int("".join(digits))
                    if num < 10_000:
                        continue
                    vals.append(f"-{num:,}")
                if vals:
                    return vals
        except Exception:
            pass

        # Mesmo no Android, se o parser leve falhar, tentamos o BeautifulSoup.
        # Essa busca já roda em background thread, então priorizamos robustez.
        soup = BeautifulSoup(html, "html.parser")

        def norm(s: str) -> str:
            return re.sub(r"\s+", " ", (s or "").strip()).lower()

        # Procurar a tabela correta de forma robusta:
        # - achar uma linha de header (<tr> com <th>) que tenha uma coluna contendo "Exp lost"
        # - capturar o índice dessa coluna
        best = None  # (table, exp_idx, score)
        for table in soup.find_all("table"):
            header_tr = None
            for tr in table.find_all("tr"):
                ths = tr.find_all("th")
                if ths:
                    header_tr = tr
                    break
            if not header_tr:
                continue

            headers = [norm(th.get_text(" ", strip=True)) for th in header_tr.find_all("th")]
            if not headers:
                continue

            exp_idx = None
            for i, h in enumerate(headers):
                if "exp" in h and "lost" in h:
                    exp_idx = i
                    break
            if exp_idx is None:
                continue

            # heurística extra: a tabela de mortes também tem "lvl" e/ou "morto"/"killed"/"when"
            score = 0
            joined = " ".join(headers)
            if "lvl" in joined or "level" in joined:
                score += 1
            if "quando" in joined or "when" in joined:
                score += 1
            if "morto" in joined or "killed" in joined:
                score += 1

            if best is None or score > best[2]:
                best = (table, exp_idx, score)

        if not best:
            _diag_log(f"no table selected after BeautifulSoup snippet={_log_preview(_html_to_plain_text(html), 260)}")
            return []

        table, exp_idx, _score = best

        out: List[str] = []
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue
            if exp_idx >= len(tds):
                continue
            xp = tds[exp_idx].get_text(" ", strip=True)
            xp = re.sub(r"\s+", " ", xp).strip()
            # filtra linhas que não parecem valor (cabeçalhos/colunas vazias)
            if not xp:
                continue
            out.append(xp)

        # Normalmente a primeira linha é a mais recente; mantemos a ordem.
        if out:
            _diag_log(f"beautifulsoup heuristic rows={len(out)}")
        else:
            _diag_log(f"no rows after all parsers snippet={_log_preview(_html_to_plain_text(html), 260)}")
        return out
    except Exception as exc:
        _diag_log(f"exception while parsing name={name!r} error={exc!r}")
        return []


def fetch_guildstats_exp_changes(name: str, timeout: int = 12, *, light_only: bool = False) -> List[Dict[str, Any]]:
    """Retorna o histórico (diário) de experiência do GuildStats (tab=9).

    Saída (ordem conforme a tabela):
      [{"date": "YYYY-MM-DD", "exp_change": "+33,820,426", "exp_change_int": 33820426}, ...]

    Observação: é um complemento (fansite). Se falhar, devolve lista vazia.
    """
    try:
        # O GuildStats e um fansite e, no Android, o acesso direto ao tab=9 pode
        # voltar para a pagina base do personagem ou vir sem a tabela de Experience.
        # Para ficar mais robusto, abrimos primeiro a pagina base do char com uma
        # sessao browser-like e depois seguimos para a aba 9 na mesma sessao/cookies.
        html = _fetch_guildstats_exp_html(name, timeout=timeout)
        if not html:
            _diag_log(f"no html for name={name!r}")
            return []
        _diag_log(f"html fetched len={len(html)} snippet={_log_preview(_html_to_plain_text(html), 260)}")

        # Fast path: tenta extrair a tabela via regex (sem BeautifulSoup) — bem mais leve no Android
        # (robusto: não assume que Date/Exp são sempre as colunas 0/1)
        try:
            def _parse_exp_to_int_fast(s: str) -> Optional[int]:
                txt = (s or "").strip()
                if not txt:
                    return None
                t = txt.replace(" ", " ")
                m0 = re.search(r"([+-])?\s*(\d[\d\s,\.]*)", t)
                if not m0:
                    return None
                sign_ch = m0.group(1)
                digits = re.findall(r"\d+", m0.group(2) or "")
                if not digits:
                    return None
                num = int("".join(digits))
                return -num if sign_ch == "-" else num

            # Datas: ISO (YYYY-MM-DD), DMY (DD.MM.YYYY / DD/MM/YYYY / DD-MM-YYYY)
            # e o layout novo do GuildStats com MM-DD visivel na tabela.
            iso_re = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
            dmy_re = re.compile(r"\b(\d{2})[./-](\d{2})[./-](\d{4})\b")
            md_re = re.compile(r"\b(\d{2})-(\d{2})\b")

            def _infer_year_for_month_day(month: int, day: int) -> int:
                today = _date.today()
                year = today.year
                try:
                    candidate = _date(year, month, day)
                except Exception:
                    return year
                delta_days = (candidate - today).days
                if delta_days > 45:
                    return year - 1
                if delta_days < -320:
                    return year + 1
                return year

            def _extract_date_iso(s: str) -> Optional[str]:
                txt = (s or "").strip()
                m = iso_re.search(txt)
                if m:
                    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                m = dmy_re.search(txt)
                if m:
                    dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
                    return f"{yyyy}-{mm}-{dd}"
                m = md_re.search(txt)
                if m:
                    mm, dd = int(m.group(1)), int(m.group(2))
                    yyyy = _infer_year_for_month_day(mm, dd)
                    return f"{yyyy:04d}-{mm:02d}-{dd:02d}"
                return None

            def _strip_tags(s: str) -> str:
                t = s or ""
                # remove blocos grandes que só atrapalham
                t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
                t = re.sub(r"(?is)<[^>]+>", " ", t)
                try:
                    t = _html.unescape(t)
                except Exception:
                    pass
                t = t.replace(" ", " ")
                t = re.sub(r"\s+", " ", t).strip()
                return t

            def _flatten_html_text(s: str) -> str:
                t = s or ""
                t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
                # Alguns layouts mais novos usam div/span em vez de tabela.
                # Mantemos um texto linear para extrair blocos entre datas.
                t = re.sub(r"(?i)<br\s*/?>", " ", t)
                t = re.sub(r"(?i)</?(tr|td|th|table|tbody|thead|tfoot|div|p|li|ul|ol|section|article|h[1-6])[^>]*>", " ", t)
                t = re.sub(r"(?is)<[^>]+>", " ", t)
                try:
                    t = _html.unescape(t)
                except Exception:
                    pass
                t = t.replace(" ", " ")
                t = re.sub(r"\s+", " ", t).strip()
                return t

            def _parse_rows(fragment: str) -> List[Dict[str, Any]]:
                rows: List[Dict[str, Any]] = []
                seen_dates = set()

                for mtr in re.finditer(r"(?is)<tr[^>]*>.*?</tr>", fragment or ""):
                    tr_html = mtr.group(0) or ""
                    tds = re.findall(r"(?is)<td[^>]*>.*?</td>", tr_html)
                    if len(tds) < 2:
                        continue

                    cells = [_strip_tags(td) for td in tds]

                    date_iso = None
                    for c in cells:
                        date_iso = _extract_date_iso(c)
                        if date_iso:
                            break

                    if not date_iso or date_iso in seen_dates:
                        continue

                    candidates = []
                    for c in cells:
                        exp_int = _parse_exp_to_int_fast(c)
                        if exp_int is None:
                            continue
                        # evita pegar colunas pequenas (lvl/rank)
                        if abs(int(exp_int)) not in (0,) and abs(int(exp_int)) < 10_000:
                            continue
                        has_sign = bool(re.search(r"^\s*[+-]", c))
                        candidates.append((1 if has_sign else 0, abs(int(exp_int)), c, int(exp_int)))

                    if not candidates:
                        continue

                    # Escolha do "Exp change":
                    # 1) se houver valor com +/-, ele quase sempre é o delta
                    # 2) se não houver, mas houver 0, preferimos 0 (evita pegar "Total experience")
                    # 3) senão, pega o menor valor absoluto (delta costuma ser menor que o total)
                    signed = [x for x in candidates if x[0] == 1]
                    if signed:
                        best = max(signed, key=lambda x: x[1])
                    else:
                        zeros = [x for x in candidates if x[3] == 0]
                        if zeros:
                            best = zeros[0]
                        else:
                            best = min(candidates, key=lambda x: x[1])

                    _sgn, _abs, exp_txt, exp_int = best
                    seen_dates.add(date_iso)
                    rows.append({
                        'date': date_iso,
                        'exp_change': exp_txt,
                        'exp_change_int': int(exp_int),
                    })

                return rows

            def _extract_best_table_fragment(html_full: str) -> str:
                best = ""
                best_score = 0
                for mt in re.finditer(r"(?is)<table[^>]*>.*?</table>", html_full or ""):
                    chunk = mt.group(0) or ""
                    score = len(iso_re.findall(chunk)) + len(dmy_re.findall(chunk))
                    if score > best_score:
                        best_score = score
                        best = chunk
                return best if best_score >= 1 else ""

            def _extract_exp_section_text(fragment: str) -> str:
                text_flat = _flatten_html_text(fragment)
                if not text_flat:
                    return ""

                low = text_flat.lower()
                header_patterns = [
                    re.compile(r"date\s+exp\s+change", re.I),
                    re.compile(r"data\s+mudan[çc]a\s+de\s+exp", re.I),
                ]
                start_idx = -1
                for pattern in header_patterns:
                    m_header = pattern.search(low)
                    if m_header:
                        start_idx = int(m_header.start())
                        break

                if start_idx == -1:
                    for marker in ("average daily exp", "média diária de exp", "media diaria de exp"):
                        pos = low.find(marker)
                        if pos != -1:
                            start_idx = pos
                            break

                if start_idx == -1:
                    return text_flat

                sliced = text_flat[start_idx:].strip()
                low_sliced = sliced.lower()
                footer_positions = []
                for marker in (
                    "total in month",
                    "total no mês",
                    "total no mes",
                    "guildstats.eu",
                    "partners compare characters",
                ):
                    pos = low_sliced.find(marker)
                    if pos != -1:
                        footer_positions.append(pos)
                if footer_positions:
                    sliced = sliced[:min(footer_positions)].strip()
                return sliced

            def _parse_rows_from_flat_text(fragment: str) -> List[Dict[str, Any]]:
                primary_text = _extract_exp_section_text(fragment)
                full_text = _flatten_html_text(fragment)

                def _parse_rows_from_flat_text_source(text_flat: str) -> List[Dict[str, Any]]:
                    rows: List[Dict[str, Any]] = []
                    seen_dates = set()
                    text_flat = re.sub(
                        r"(?i)\bbest recorded day\b\s+(?:\d{4}-\d{2}-\d{2}|\d{2}[./-]\d{2}[./-]\d{4}|\d{2}-\d{2})\s+(?:change\s+)?[+-]?\d[\d,.]*",
                        " ",
                        text_flat or "",
                    )
                    text_flat = re.sub(
                        r"(?i)\b(?:average daily exp|level prediction)\b.*?(?=(?:\b\d{4}-\d{2}-\d{2}\b|\b\d{2}[./-]\d{2}[./-]\d{4}\b|\b\d{2}-\d{2}\b)\s+(?:exp\s*change|change)\b)",
                        " ",
                        text_flat,
                    )
                    date_block_re = re.compile(
                        r"(?P<date>\b(?:\d{4}-\d{2}-\d{2}|\d{2}[./-]\d{2}[./-]\d{4}|\d{2}-\d{2})\b)(?P<body>.*?)(?=(?:\b(?:\d{4}-\d{2}-\d{2}|\d{2}[./-]\d{2}[./-]\d{4}|\d{2}-\d{2})\b)|$)",
                        re.S,
                    )
                    token_re = re.compile(r"(?<!\d)([+-]\s*\d[\d,.]*|\b0\b|\d[\d,.]*)(?!\d)")

                    for mblk in date_block_re.finditer(text_flat):
                        date_iso = _extract_date_iso(mblk.group('date') or '')
                        if not date_iso or date_iso in seen_dates:
                            continue

                        body = str(mblk.group('body') or '')
                        if not body.strip():
                            continue

                        # Ignora linhas que claramente pertencem a outros blocos
                        # (former worlds / best day / transicao de header), comuns na pagina base.
                        if re.search(r"(?i)\bdate\s+exp\s+change\b", body) or re.search(r"(?i)\blevel prediction\b", body):
                            continue

                        body = re.split(
                            r"(?i)\b(?:total in month|total no m[eê]s|total no mes|guildstats\.eu|partners compare characters)\b",
                            body,
                            maxsplit=1,
                        )[0]
                        if not body.strip():
                            continue

                        body_norm = re.sub(r"\s+", " ", body).strip()
                        body_norm = re.sub(r"\(\s*[+-]\s*\d[\d,.]*\s*\)", " ", body_norm)
                        body_norm = re.sub(r"(?i)\bview on tibia\.com\b", " ", body_norm)
                        body_norm = re.sub(
                            r"(?i)\b(?:vocation rank|rank da vocação|rank da vocacao|lvl|level|experience|time on-?line|avg exp per hour|average daily exp|média diária de exp|media diaria de exp)\b",
                            " ",
                            body_norm,
                        )
                        body_norm = re.sub(r"\s+", " ", body_norm).strip()

                        exp_txt = ""
                        fallback_zero = ""
                        fallback_unsigned = ""
                        fallback_signed_small = ""
                        leading_candidate = ""
                        leading_unsigned = ""

                        labeled_match = re.search(
                            r"(?i)\b(?:exp\s*change|change|mudan[çc]a\s+de\s+exp)\b[^0-9+-]{0,20}(?P<value>[+-]?\s*\d[\d,.]*)",
                            body,
                        )
                        if labeled_match:
                            labeled_raw = str(labeled_match.group('value') or '').strip()
                            labeled_int = _parse_exp_to_int_fast(labeled_raw)
                            if labeled_int is not None:
                                exp_txt = labeled_raw.replace(" ", "")

                        first_token = token_re.search(body_norm)
                        if first_token:
                            raw0 = str(first_token.group(1) or '').strip()
                            exp0 = _parse_exp_to_int_fast(raw0)
                            if exp0 is not None:
                                raw0_clean = raw0.replace(" ", "")
                                if raw0.lstrip().startswith(("+", "-")) or int(exp0) == 0:
                                    leading_candidate = raw0_clean
                                elif 0 < abs(int(exp0)) <= 500_000_000:
                                    leading_unsigned = raw0_clean

                        for mnum in token_re.finditer(body_norm):
                            raw = str(mnum.group(1) or '').strip()
                            exp_int = _parse_exp_to_int_fast(raw)
                            if exp_int is None:
                                continue
                            abs_int = abs(int(exp_int))

                            if raw.lstrip().startswith(("+", "-")) and abs_int >= 10_000:
                                exp_txt = raw.replace(" ", "")
                                break

                            if raw.lstrip().startswith(("+", "-")) and abs_int < 10_000 and not fallback_signed_small:
                                fallback_signed_small = raw.replace(" ", "")
                                continue

                            if int(exp_int) == 0 and not fallback_zero:
                                fallback_zero = "0"
                                continue

                            if not raw.lstrip().startswith(("+", "-")) and 10_000 <= abs_int <= 500_000_000 and not fallback_unsigned:
                                fallback_unsigned = raw.replace(" ", "")

                        if not exp_txt:
                            exp_txt = leading_candidate or leading_unsigned or fallback_signed_small or fallback_unsigned or fallback_zero
                        if not exp_txt:
                            continue

                        exp_int = _parse_exp_to_int_fast(exp_txt)
                        if exp_int is None:
                            continue
                        if abs(int(exp_int)) not in (0,) and abs(int(exp_int)) < 10_000 and exp_txt not in (leading_candidate, leading_unsigned, fallback_signed_small):
                            continue

                        exp_txt_out = exp_txt
                        if not str(exp_txt_out).lstrip().startswith(("+", "-")) and int(exp_int) > 0:
                            exp_txt_out = _format_exp_text(int(exp_int))

                        seen_dates.add(date_iso)
                        rows.append({
                            'date': date_iso,
                            'exp_change': exp_txt_out,
                            'exp_change_int': int(exp_int),
                        })

                    return rows

                primary_rows = _parse_rows_from_flat_text_source(primary_text) if primary_text else []
                primary_nonzero = sum(1 for row in primary_rows if int(row.get('exp_change_int') or 0) != 0)
                if full_text and full_text != primary_text and (not primary_rows or primary_nonzero == 0):
                    full_rows = _parse_rows_from_flat_text_source(full_text)
                    full_nonzero = sum(1 for row in full_rows if int(row.get('exp_change_int') or 0) != 0)
                    if len(full_rows) > len(primary_rows) or full_nonzero > primary_nonzero:
                        return full_rows
                return primary_rows
                return best_rows
            def _format_exp_text(value: int) -> str:
                if int(value) == 0:
                    return "0"
                return f"{int(value):+,}"

            def _parse_rows_from_js(fragment: str) -> List[Dict[str, Any]]:
                scripts = "\n".join(re.findall(r"(?is)<script[^>]*>(.*?)</script>", fragment or ""))
                haystack = scripts or (fragment or "")
                rows: List[Dict[str, Any]] = []
                seen_dates = set()
                patterns = [
                    re.compile(r"[\"']date[\"']\s*:\s*[\"'](?P<date>\d{4}-\d{2}-\d{2})[\"'][^{}\n]{0,240}?[\"'](?:exp[_ ]?change|expChange|value|gain|y)[\"']\s*:\s*[\"']?(?P<value>[+-]?\d[\d,\.]*)", re.I),
                    re.compile(r"\[\s*[\"'](?P<date>\d{4}-\d{2}-\d{2})[\"']\s*,\s*[\"']?(?P<value>[+-]?\d[\d,\.]*)[\"']?\s*\]", re.I),
                    re.compile(r"[\"'](?P<date>\d{4}-\d{2}-\d{2})[\"']\s*,\s*[\"']?(?P<value>[+-]?\d[\d,\.]*)[\"']?", re.I),
                ]
                for pattern in patterns:
                    for match in pattern.finditer(haystack):
                        date_iso = str(match.group('date') or '').strip()
                        if not date_iso or date_iso in seen_dates:
                            continue
                        raw_value = str(match.group('value') or '').strip()
                        exp_int = _parse_exp_to_int_fast(raw_value)
                        if exp_int is None:
                            continue
                        if abs(int(exp_int)) not in (0,) and abs(int(exp_int)) < 10_000:
                            continue
                        seen_dates.add(date_iso)
                        rows.append({
                            'date': date_iso,
                            'exp_change': _format_exp_text(int(exp_int)),
                            'exp_change_int': int(exp_int),
                        })
                    if rows:
                        break
                return rows

            def _rows_quality(rows: List[Dict[str, Any]], *, hint: int = 0) -> int:
                if not rows:
                    return -(10 ** 9)
                unique_dates = {}
                signed_count = 0
                for row in rows:
                    ds = str(row.get('date') or '').strip()
                    if not ds:
                        continue
                    try:
                        unique_dates[ds] = int(row.get('exp_change_int') or 0)
                    except Exception:
                        unique_dates[ds] = 0
                    txt = str(row.get('exp_change') or '').lstrip()
                    if txt.startswith(("+", "-")):
                        signed_count += 1
                values = [int(v) for v in unique_dates.values()]
                nonzero = sum(1 for v in values if int(v) != 0)
                max_abs = max((abs(int(v)) for v in values), default=0)
                abs_sum = sum(min(abs(int(v)), 100_000_000) for v in values)
                zero_only_penalty = 200_000 if nonzero == 0 else 0
                huge_penalty = 120_000 if max_abs > 500_000_000 else 0
                return (
                    int(hint)
                    + (len(unique_dates) * 1_000)
                    + (nonzero * 15_000)
                    + (signed_count * 2_500)
                    + min(abs_sum // 1_000, 300_000)
                    - zero_only_penalty
                    - huge_penalty
                )

            def _remember_candidate(bucket: List[Any], label: str, rows: List[Dict[str, Any]], *, hint: int = 0) -> None:
                if not rows:
                    return
                score = _rows_quality(rows, hint=hint)
                bucket.append((int(score), str(label), rows))

            def _best_candidate(bucket: List[Any]) -> tuple[int, str, List[Dict[str, Any]]]:
                if not bucket:
                    return (-(10 ** 9), "", [])
                return max(bucket, key=lambda item: int(item[0]))

            def _normalize_label(s: str) -> str:
                txt = (s or "").lower().strip()
                txt = txt.replace("ç", "c").replace("ã", "a").replace("á", "a").replace("é", "e")
                txt = re.sub(r"\s+", " ", txt)
                return txt

            def _extract_cell_attr(cell: Any, *attrs: str) -> str:
                for attr in attrs:
                    try:
                        raw = cell.get(attr)
                    except Exception:
                        raw = None
                    if raw is None:
                        continue
                    txt = re.sub(r"\s+", " ", str(raw)).strip()
                    if txt:
                        return txt
                return ""

            def _parse_rows_from_labeled_tables(fragment: str) -> List[Dict[str, Any]]:
                try:
                    soup_local = BeautifulSoup(fragment or "", "html.parser")
                except Exception:
                    return []

                best_rows: List[Dict[str, Any]] = []
                best_score = -(10 ** 9)

                for table in soup_local.find_all("table"):
                    tr_nodes = table.find_all("tr")
                    if not tr_nodes:
                        continue

                    matrix_text: List[List[str]] = []
                    matrix_cells: List[List[Any]] = []
                    for tr in tr_nodes:
                        cells = tr.find_all(["th", "td"])
                        if not cells:
                            continue
                        texts = [re.sub(r"\s+", " ", (c.get_text(" ", strip=True) or "")).strip() for c in cells]
                        matrix_text.append(texts)
                        matrix_cells.append(cells)

                    if not matrix_text:
                        continue

                    header_row_idx = None
                    date_idx = None
                    exp_idx = None

                    for ri, row in enumerate(matrix_text[:4]):
                        for ci, txt in enumerate(row):
                            low = _normalize_label(txt)
                            if date_idx is None and re.search(r"\b(?:date|data)\b", low):
                                date_idx = ci
                            if exp_idx is None and (("exp" in low and "change" in low) or "mudanca de exp" in low or re.fullmatch(r"change", low)):
                                exp_idx = ci
                        if date_idx is not None and exp_idx is not None and date_idx != exp_idx:
                            header_row_idx = ri
                            break

                    if header_row_idx is None or date_idx is None or exp_idx is None or date_idx == exp_idx:
                        continue

                    rows: List[Dict[str, Any]] = []
                    seen_dates = set()
                    for texts, cells in zip(matrix_text[header_row_idx + 1 :], matrix_cells[header_row_idx + 1 :]):
                        if date_idx >= len(texts) or exp_idx >= len(texts):
                            continue
                        if date_idx >= len(cells) or exp_idx >= len(cells):
                            continue

                        date_sources = [
                            _extract_cell_attr(cells[date_idx], "data-sort", "data-order", "data-value", "sorttable_customkey", "title", "aria-label"),
                            texts[date_idx],
                        ]
                        date_iso = None
                        for source in date_sources:
                            date_iso = _extract_date_iso(source)
                            if date_iso:
                                break
                        if not date_iso or date_iso in seen_dates:
                            continue

                        exp_sources = [
                            texts[exp_idx],
                            _extract_cell_attr(cells[exp_idx], "data-sort", "data-order", "data-value", "sorttable_customkey", "title", "aria-label"),
                        ]
                        exp_int = None
                        exp_txt = ""
                        for source in exp_sources:
                            if not source:
                                continue
                            parsed = _parse_exp_to_int_fast(source)
                            if parsed is None:
                                continue
                            exp_int = int(parsed)
                            exp_txt = str(source).strip()
                            break
                        if exp_int is None:
                            continue

                        if not exp_txt or _parse_exp_to_int_fast(exp_txt) is None or (not re.search(r"[+-]", exp_txt) and int(exp_int) != 0):
                            exp_txt = _format_exp_text(int(exp_int))
                        else:
                            exp_txt = exp_txt.replace(" ", "")

                        seen_dates.add(date_iso)
                        rows.append({
                            'date': date_iso,
                            'exp_change': exp_txt,
                            'exp_change_int': int(exp_int),
                        })

                    table_score = _rows_quality(rows, hint=90_000)
                    if rows and table_score > best_score:
                        best_score = table_score
                        best_rows = rows

                return best_rows

            def _parse_rows_from_structured_blocks(fragment: str) -> List[Dict[str, Any]]:
                try:
                    soup_local = BeautifulSoup(fragment or "", "html.parser")
                except Exception:
                    return []

                def _iter_attr_values(node: Any) -> List[str]:
                    values: List[str] = []
                    try:
                        descendants = [node, *list(node.descendants)]
                    except Exception:
                        descendants = [node]
                    for item in descendants:
                        if not hasattr(item, "attrs"):
                            continue
                        for attr in ("data-sort", "data-order", "data-value", "sorttable_customkey", "title", "aria-label"):
                            try:
                                raw = item.get(attr)
                            except Exception:
                                raw = None
                            if raw is None:
                                continue
                            txt = re.sub(r"\s+", " ", str(raw)).strip()
                            if txt:
                                values.append(txt)
                    return values

                def _pick_exp_from_payload(text_payload: str, attr_values: List[str]) -> Optional[tuple[str, int]]:
                    payload = re.sub(r"\s+", " ", str(text_payload or "")).strip()
                    if not payload and not attr_values:
                        return None

                    payload = re.sub(r"\(\s*[+-]\s*\d[\d,.]*\s*\)", " ", payload)
                    payload = re.sub(r"(?i)\bview on tibia\.com\b", " ", payload)
                    payload = re.sub(r"\s+", " ", payload).strip()
                    low_payload = payload.lower()
                    attr_blob = " ".join(str(v or "") for v in attr_values).lower()
                    has_change_context = any(marker in low_payload for marker in (
                        "exp change", "change", "gain", "avg exp", "average daily exp", "time on-line", "time online",
                    )) or any(marker in attr_blob for marker in ("exp change", "change", "gain"))
                    if not has_change_context:
                        return None
                    if any(marker in low_payload for marker in (
                        "best recorded day", "average daily exp", "level prediction",
                    )) and not re.search(r"(?i)\b(?:date|data)\b.*\b(?:exp\s*change|change|mudan[çc]a\s+de\s+exp)\b", low_payload):
                        return None

                    labeled = re.search(
                        r"(?i)\b(?:exp\s*change|change|gain|mudan[çc]a\s+de\s+exp)\b[^0-9+-]{0,24}(?P<value>[+-]?\s*\d[\d,.]*)",
                        payload,
                    )
                    if labeled:
                        raw = str(labeled.group("value") or "").strip().replace(" ", "")
                        parsed = _parse_exp_to_int_fast(raw)
                        if parsed is not None and 0 <= abs(int(parsed)) <= 300_000_000 and (raw.lstrip().startswith(("+", "-")) or abs(int(parsed)) >= 100 or int(parsed) == 0):
                            if int(parsed) == 0 and attr_values:
                                numeric_attrs: List[int] = []
                                for raw_attr in attr_values:
                                    parsed_attr = _parse_exp_to_int_fast(raw_attr)
                                    if parsed_attr is None:
                                        continue
                                    attr_abs = abs(int(parsed_attr))
                                    if attr_abs < 10_000 or attr_abs > 300_000_000:
                                        continue
                                    numeric_attrs.append(int(parsed_attr))
                                if numeric_attrs:
                                    best_val = max(numeric_attrs, key=lambda v: abs(int(v)))
                                    return (_format_exp_text(int(best_val)), int(best_val))
                            out = raw
                            if not raw.lstrip().startswith(("+", "-")) and int(parsed) > 0:
                                out = _format_exp_text(int(parsed))
                            return (out, int(parsed))

                    signed_candidates: List[tuple[int, str, int]] = []
                    unsigned_candidates: List[tuple[int, str, int]] = []
                    token_re_local = re.compile(r"(?<!\d)([+-]\s*\d[\d,.]*|\b0\b|\d[\d,.]*)(?!\d)")
                    for match in token_re_local.finditer(payload):
                        raw = str(match.group(1) or "").strip().replace(" ", "")
                        parsed = _parse_exp_to_int_fast(raw)
                        if parsed is None:
                            continue
                        val = int(parsed)
                        abs_val = abs(val)
                        if abs_val > 300_000_000:
                            continue
                        if raw.lstrip().startswith(("+", "-")):
                            signed_candidates.append((abs_val, raw, val))
                        else:
                            if abs_val not in (0,) and abs_val < 10_000:
                                continue
                            unsigned_candidates.append((abs_val, raw, val))

                    if signed_candidates:
                        _abs, raw, val = max(signed_candidates, key=lambda item: item[0])
                        return (raw, int(val))

                    if has_change_context:
                        numeric_attrs: List[int] = []
                        for raw_attr in attr_values:
                            parsed = _parse_exp_to_int_fast(raw_attr)
                            if parsed is None:
                                continue
                            val = int(parsed)
                            abs_val = abs(val)
                            if abs_val == 0:
                                continue
                            if abs_val < 10_000 or abs_val > 300_000_000:
                                continue
                            numeric_attrs.append(val)
                        if numeric_attrs:
                            best_val = max(numeric_attrs, key=lambda v: abs(int(v)))
                            return (_format_exp_text(int(best_val)), int(best_val))

                    if unsigned_candidates and has_change_context:
                        _abs, raw, val = max(unsigned_candidates, key=lambda item: item[0])
                        out_txt = raw
                        if int(val) > 0 and not raw.lstrip().startswith(("+", "-")):
                            out_txt = _format_exp_text(int(val))
                        return (out_txt, int(val))

                    if re.search(r"(?<!\d)0(?!\d)", payload):
                        return ("0", 0)
                    return None

                preferred_tags = {"tr": 40, "li": 32, "article": 28, "section": 26, "div": 24}

                def _container_signature(node: Any) -> tuple[str, str, str, str]:
                    tag_name = getattr(node, "name", "") or "div"
                    try:
                        classes = tuple(sorted(str(c) for c in (node.get("class") or [])))
                    except Exception:
                        classes = tuple()
                    parent = getattr(node, "parent", None)
                    parent_name = getattr(parent, "name", "") or ""
                    try:
                        parent_classes = tuple(sorted(str(c) for c in ((parent.get("class") if parent else None) or [])))
                    except Exception:
                        parent_classes = tuple()
                    return (tag_name, " ".join(classes), parent_name, " ".join(parent_classes))

                def _build_grouped_rows() -> List[Dict[str, Any]]:
                    groups: Dict[tuple[str, str, str, str], List[Dict[str, Any]]] = {}
                    for container in soup_local.find_all(list(preferred_tags.keys())):
                        payload_text = re.sub(r"\s+", " ", container.get_text(" ", strip=True) or "").strip()
                        if not payload_text or len(payload_text) > 500:
                            continue
                        low_payload = payload_text.lower()
                        if any(marker in low_payload for marker in (
                            "guildstats.eu", "total in month", "total no mes", "total no mês",
                            "best recorded day", "average daily exp", "level prediction",
                        )):
                            continue
                        date_hits = re.findall(r"\b(?:\d{4}-\d{2}-\d{2}|\d{2}[./-]\d{2}[./-]\d{4}|\d{2}-\d{2})\b", payload_text)
                        if len(date_hits) != 1:
                            continue
                        date_iso = _extract_date_iso(date_hits[0])
                        if not date_iso:
                            continue
                        attr_values = _iter_attr_values(container)
                        picked = _pick_exp_from_payload(payload_text, attr_values)
                        if not picked:
                            continue
                        out_txt, out_int = picked
                        sig = _container_signature(container)
                        groups.setdefault(sig, []).append({
                            'date': date_iso,
                            'exp_change': out_txt,
                            'exp_change_int': int(out_int),
                        })

                    best_rows: List[Dict[str, Any]] = []
                    best_score = -(10 ** 9)
                    for sig, raw_rows in groups.items():
                        uniq: Dict[str, Dict[str, Any]] = {}
                        for row in raw_rows:
                            uniq[str(row['date'])] = row
                        rows = [uniq[k] for k in sorted(uniq.keys())]
                        if len(rows) < 2:
                            continue
                        score = _rows_quality(rows, hint=85_000)
                        score += preferred_tags.get(sig[0], 10) * 10
                        if score > best_score:
                            best_score = score
                            best_rows = rows
                    return best_rows

                grouped_rows = _build_grouped_rows()
                if grouped_rows:
                    return grouped_rows

                seen_dates = set()
                rows: List[Dict[str, Any]] = []
                for text_node in soup_local.find_all(string=True):
                    raw_text = re.sub(r"\s+", " ", str(text_node or "")).strip()
                    if not raw_text:
                        continue
                    date_iso = _extract_date_iso(raw_text)
                    if not date_iso or date_iso in seen_dates:
                        continue

                    try:
                        parent = text_node.parent
                    except Exception:
                        parent = None
                    ancestors = []
                    hops = 0
                    while parent is not None and hops < 6:
                        tag_name = getattr(parent, "name", "") or ""
                        if tag_name in preferred_tags:
                            ancestors.append(parent)
                        parent = getattr(parent, "parent", None)
                        hops += 1

                    best_pick: Optional[tuple[int, str, int]] = None
                    for container in ancestors:
                        tag_name = getattr(container, "name", "") or "div"
                        payload_text = re.sub(r"\s+", " ", container.get_text(" ", strip=True) or "").strip()
                        if not payload_text:
                            continue
                        low_payload = payload_text.lower()
                        if any(marker in low_payload for marker in (
                            "total in month", "total no mes", "total no mês", "guildstats.eu",
                            "best recorded day", "average daily exp", "level prediction",
                        )):
                            continue
                        header_pos = low_payload.find("date exp change")
                        date_pos = low_payload.find(str(raw_text or "").lower())
                        if header_pos != -1 and date_pos != -1 and date_pos < header_pos:
                            continue
                        date_hits = len(re.findall(r"\b(?:\d{4}-\d{2}-\d{2}|\d{2}[./-]\d{2}[./-]\d{4}|\d{2}-\d{2})\b", payload_text))
                        if date_hits < 1 or date_hits > 3:
                            continue
                        if len(payload_text) > 900:
                            continue

                        attr_values = _iter_attr_values(container)
                        picked = _pick_exp_from_payload(payload_text, attr_values)
                        if not picked:
                            continue
                        out_txt, out_int = picked
                        score = preferred_tags.get(tag_name, 10)
                        score += max(0, 350 - min(len(payload_text), 350)) // 20
                        if any(label in low_payload for label in ("exp change", "change", "gain", "avg exp")):
                            score += 10
                        if int(out_int) != 0:
                            score += 20
                        if best_pick is None or score > best_pick[0]:
                            best_pick = (score, out_txt, int(out_int))

                    if best_pick is None:
                        continue
                    _score, out_txt, out_int = best_pick
                    seen_dates.add(date_iso)
                    rows.append({
                        'date': date_iso,
                        'exp_change': out_txt,
                        'exp_change_int': int(out_int),
                    })

                if len(rows) == 1:
                    return []
                return rows

            fast_candidates: List[Any] = []
            _remember_candidate(fast_candidates, 'generic-tr', _parse_rows(html), hint=1_000)

            frag = _extract_best_table_fragment(html)
            if frag:
                _remember_candidate(fast_candidates, 'best-table-fragment', _parse_rows(frag), hint=3_000)

            if _looks_like_guildstats_exp_page(html):
                _remember_candidate(fast_candidates, 'structured-blocks', _parse_rows_from_structured_blocks(html), hint=70_000)
                _remember_candidate(fast_candidates, 'flat-text', _parse_rows_from_flat_text(html), hint=6_000)
            else:
                _diag_log('skip flat-text parser because html is not confirmed as experience page')
            _remember_candidate(fast_candidates, 'script-json', _parse_rows_from_js(html), hint=500)
            _remember_candidate(fast_candidates, 'labeled-table', _parse_rows_from_labeled_tables(html), hint=95_000)

            fast_score, fast_label, fast_rows = _best_candidate(fast_candidates)
            if fast_rows:
                _diag_log(f"fast parser selected={fast_label} rows={len(fast_rows)} score={fast_score}")
                if _rows_quality(fast_rows) >= 1:
                    return fast_rows
        except Exception:
            pass

        _diag_log("fast parser returned 0 rows; trying BeautifulSoup fallback")
        # Mesmo no Android (light_only), ainda tentamos o BeautifulSoup como fallback.
        # O caminho "leve" cobre a maioria dos casos, mas o GuildStats às vezes devolve
        # um HTML que só o parser do BeautifulSoup consegue normalizar.
        soup = BeautifulSoup(html, "html.parser")

        def parse_exp_to_int(s: str) -> Optional[int]:
            # exemplos: "+33,820,426" | "-55,947,218" | "0" | "+200,710,181 👍"
            txt = (s or "").strip()
            if not txt:
                return None
            # Normaliza NBSP e tenta achar um número.
            t = txt.replace("\u00a0", " ")
            # pega primeiro bloco numérico e sinal se existir no começo
            m = re.search(r"([+-])?\s*(\d[\d\s,\.]*)", t)
            if not m:
                return None
            sign_ch = m.group(1)
            digits = re.findall(r"\d+", m.group(2) or "")
            if not digits:
                return None
            num = int("".join(digits))
            return -num if sign_ch == "-" else num

        date_re = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

        # Tenta um parsing simples (col0=data, col1=exp_change) percorrendo todos os <tr>.
        # Isso cobre variações em que a tabela não tem <th> ou muda de classe/estrutura.
        fast_rows: List[Dict[str, Any]] = []
        seen_dates = set()
        for tr in soup.find_all('tr'):
            tds = tr.find_all('td')
            if len(tds) < 2:
                continue
            dtext = re.sub(r'\s+', ' ', (tds[0].get_text(' ', strip=True) or '')).strip()
            mdate = date_re.search(dtext)
            if not mdate:
                continue
            date_iso = mdate.group(1)
            etext = re.sub(r'\s+', ' ', (tds[1].get_text(' ', strip=True) or '')).strip()
            exp_int = parse_exp_to_int(etext)
            if exp_int is None:
                continue
            # evita pegar colunas pequenas (rank/lvl) por engano
            if abs(int(exp_int)) not in (0,) and abs(int(exp_int)) < 10_000:
                continue
            if date_iso in seen_dates:
                continue
            seen_dates.add(date_iso)
            fast_rows.append({
                'date': date_iso,
                'exp_change': etext,
                'exp_change_int': int(exp_int),
            })

        if len(fast_rows) >= 1:
            _diag_log(f"beautifulsoup simple rows={len(fast_rows)}")
            return fast_rows

        # Heurística robusta: escolhe a tabela em que muitas linhas possuem uma data ISO
        # e alguma coluna com valores grandes e frequentemente prefixados com +/-. 
        best = None  # (table, date_idx, exp_idx, score)

        for table in soup.find_all("table"):
            rows = []
            max_cols = 0
            for tr in table.find_all("tr"):
                cells = tr.find_all(["td", "th"])
                if not cells:
                    continue
                row = [re.sub(r"\s+", " ", (c.get_text(" ", strip=True) or "")).strip() for c in cells]
                if not row:
                    continue
                rows.append(row)
                max_cols = max(max_cols, len(row))

            if not rows or max_cols < 2:
                continue

            # normaliza linhas para mesmo tamanho
            norm_rows = [r + [""] * (max_cols - len(r)) for r in rows]

            # conta datas por coluna
            date_counts = [0] * max_cols
            for r in norm_rows:
                for ci, v in enumerate(r):
                    if date_re.search(v or ""):
                        date_counts[ci] += 1

            date_idx = max(range(max_cols), key=lambda i: date_counts[i])
            # Alguns chars podem ter poucos registros (tracking recente).
            if date_counts[date_idx] < 1:
                continue

            # pontua colunas de EXP
            col_scores = []
            for ci in range(max_cols):
                if ci == date_idx:
                    col_scores.append((-1, ci))
                    continue
                exp_count = 0
                plusminus = 0
                abs_sum = 0
                max_abs = 0
                zero_count = 0
                for r in norm_rows:
                    if not date_re.search(r[date_idx] or ""):
                        continue
                    v = (r[ci] or "").strip()
                    if not v:
                        continue
                    exp_int = parse_exp_to_int(v)
                    if exp_int is None:
                        continue
                    exp_count += 1
                    ai = abs(int(exp_int))
                    abs_sum += ai
                    max_abs = max(max_abs, ai)
                    if int(exp_int) == 0:
                        zero_count += 1
                    if v.lstrip().startswith(("+", "-")):
                        plusminus += 1

                if exp_count < 1:
                    col_scores.append((-1, ci))
                    continue

                avg_abs = abs_sum / float(exp_count) if exp_count else 0.0

                # Evita confundir com colunas pequenas (lvl/rank) — normalmente exp change tem valores grandes,
                # mas também pode ter muitos "0". A coluna "Experience" (total) tem valores enormes e SEM +/-. 
                if plusminus > 0:
                    if avg_abs < 10_000:
                        col_scores.append((-1, ci))
                        continue
                    # score: +/− domina completamente (senão a coluna "Experience" ganha pelo tamanho).
                    score = (plusminus * 1_000_000) + (exp_count * 1000) + min(avg_abs, 1_000_000_000) / 1_000_000_000
                else:
                    # Sem sinais: aceitaremos apenas se os valores não forem absurdamente grandes
                    # (para não pegar a coluna "Experience"). Também damos bônus se for muito "0".
                    if max_abs > 5_000_000:
                        col_scores.append((-1, ci))
                        continue
                    zero_ratio = (zero_count / float(exp_count)) if exp_count else 0.0
                    score = (exp_count * 1000) + (zero_ratio * 500) + (5_000_000 - max_abs) / 10_000
                col_scores.append((score, ci))

            best_col = max(col_scores, key=lambda x: x[0])
            if best_col[0] < 0:
                continue
            exp_idx = best_col[1]

            table_score = date_counts[date_idx] + best_col[0]
            if best is None or table_score > best[3]:
                best = (table, date_idx, exp_idx, table_score)

        if not best:
            _diag_log(f"no table selected after BeautifulSoup snippet={_log_preview(_html_to_plain_text(html), 260)}")
            return []

        table, date_idx, exp_idx, _score = best

        out: List[Dict[str, Any]] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue
            vals = [re.sub(r"\s+", " ", (c.get_text(" ", strip=True) or "")).strip() for c in cells]
            if date_idx >= len(vals) or exp_idx >= len(vals):
                continue

            date_txt = vals[date_idx]
            exp_txt = vals[exp_idx]
            if not date_txt or not exp_txt:
                continue

            m = date_re.search(date_txt)
            if not m:
                continue
            date_iso = m.group(1)

            exp_int = parse_exp_to_int(exp_txt)
            if exp_int is None:
                continue

            out.append({
                "date": date_iso,
                "exp_change": exp_txt,
                "exp_change_int": int(exp_int),
            })

        if out:
            _diag_log(f"beautifulsoup heuristic rows={len(out)}")
        else:
            _diag_log(f"no rows after all parsers snippet={_log_preview(_html_to_plain_text(html), 260)}")
        return out
    except Exception as exc:
        _diag_log(f"exception while parsing name={name!r} error={exc!r}")
        return []


__all__ = [
    "fetch_worlds",
    "fetch_worlds_tibiadata",
    "fetch_character_snapshot",
    "fetch_character_tibiadata",
    "is_character_online_tibiadata",
    "is_character_online_tibia_com",
    "fetch_guildstats_deaths_xp",
    "fetch_guildstats_exp_changes",
]
