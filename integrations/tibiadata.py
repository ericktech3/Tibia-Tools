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


from integrations.parsers.guildstats_parser import (  # noqa: F401  parsers separados
    _guildstats_blocked_or_empty,
    _html_to_plain_text,
    _has_guildstats_exp_structure,
    _looks_like_guildstats_exp_page,
    _extract_guildstats_tab_url,
    _extract_guildstats_exp_links,
    _extract_guildstats_exp_link,
    _unique_preserve_order,
    _diag_log,
    _log_preview,
    parse_guildstats_exp_html,
)

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

    # Layout novo (2026): a aba de Experience e carregada via AJAX em
    # include/character/tab.php?nick=...&tab=experience. A pagina principal
    # nao contem mais a tabela, por isso os valores vinham zerados.
    for ajax_url in (
        f"https://guildstats.eu/include/character/tab.php?nick={enc_plus}&tab=experience",
        f"https://guildstats.eu/include/character/tab.php?nick={enc_quote}&tab=experience",
    ):
        try:
            ajax_headers = dict(headers)
            ajax_headers["Referer"] = f"https://guildstats.eu/character?nick={enc_plus}"
            ajax_headers["X-Requested-With"] = "XMLHttpRequest"
            r = session.get(ajax_url, headers=ajax_headers, timeout=timeout)
            txt = r.text or ""
            if r.status_code < 400 and "Exp change" in txt and "<tr" in txt:
                _diag_log(f"ajax ok url={ajax_url} len={len(txt)}")
                return txt
            _diag_log(f"ajax miss url={ajax_url} status={r.status_code} len={len(txt)}")
        except Exception as e:
            _diag_log(f"ajax error url={ajax_url} err={e!r}")

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
        return parse_guildstats_exp_html(html, name=name)
    except Exception as exc:
        _diag_log(f"exception while fetching name={name!r} error={exc!r}")
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
