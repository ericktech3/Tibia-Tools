"""Tela de personagem: busca e ações. Peças separadas em display/stalker/history."""
from features.char._common import (
    Clock, datetime, requests, threading, time, timedelta, urllib, webbrowser,
    _friendly_char_error, build_stalker_character_url, estimate_death_exp_lost,
    extract_stalker_candidates, fetch_character_tibiadata,
    fetch_guildstats_deaths_xp, fetch_guildstats_exp_changes,
    fetch_stalker_character, is_character_online_tibia_com,
    log_current_exception,
)
from features.char.display import CharDisplayMixin
from features.char.stalker import CharStalkerMixin
from features.char.history import CharHistoryMixin


class CharControllerMixin(CharDisplayMixin, CharStalkerMixin, CharHistoryMixin):
    """Busca de personagem; partes visuais/sugestões/histórico ficam em módulos irmãos."""
    def _get_home_screen(self):
        root = getattr(self, "root", None)
        if root is None:
            return None
        get_screen = getattr(root, "get_screen", None)
        if not callable(get_screen):
            return None
        try:
            return get_screen("home")
        except Exception:
            return None

    def _safe_menu_dismiss(self, attr_name: str) -> None:
        menu = getattr(self, attr_name, None)
        if menu is None:
            return
        try:
            menu.dismiss()
        except Exception:
            log_current_exception(prefix=f"[char] falha ao fechar menu {attr_name}")
        setattr(self, attr_name, None)

    def _safe_parse_iso_datetime(self, value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return None

    def _safe_parse_iso_date(self, value):
        dt = self._safe_parse_iso_datetime(value)
        return dt.date() if dt else None

    def _safe_int(self, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _favorite_names_set(self) -> set[str]:
        return {str(x).strip().lower() for x in (getattr(self, "favorites", []) or []) if str(x).strip()}

    def clear_char_search(self):
        home = self._get_home_screen()
        ids = getattr(home, "ids", None) if home is not None else None
        char_name = ids.get("char_name") if hasattr(ids, "get") else None
        if char_name is None:
            return
        char_name.text = ""
        try:
            char_name.focus = True
        except Exception:
            log_current_exception(prefix="[char] falha ao focar campo de busca")

    def open_char_from_account_list(self, name: str):
        """Abre (pesquisa) um personagem a partir da lista 'Outros chars na conta'."""
        nm = (name or "").strip()
        if not nm:
            return
        home = self._get_home_screen()
        ids = getattr(home, "ids", None) if home is not None else None
        char_name = ids.get("char_name") if hasattr(ids, "get") else None
        if char_name is not None:
            char_name.text = nm
            try:
                char_name.focus = False
            except Exception:
                log_current_exception(prefix="[char] falha ao desfocar campo de busca")
        try:
            self.search_character()
        except Exception:
            log_current_exception(prefix="[char] falha ao abrir personagem da conta")

    def search_character(self, *, silent: bool = False):
        home = self._get_home_screen()
        ids = getattr(home, "ids", None) if home is not None else None
        char_name = ids.get("char_name") if hasattr(ids, "get") else None
        name = (getattr(char_name, "text", "") or "").strip()
        if not name:
            if not silent:
                self.toast("Digite o nome do char.")
            return

        # Marca como "buscando" imediatamente (UI responsiva).
        self._char_set_loading(home, name)
        home.char_last_url = ""
        home.char_xp_source_url = ""
        home.char_stalker_source_url = build_stalker_character_url(name)

        # Token para evitar que resultados de buscas antigas sobrescrevam a busca atual.
        try:
            self._char_search_seq = int(getattr(self, "_char_search_seq", 0)) + 1
        except (TypeError, ValueError):
            self._char_search_seq = int(time.time() * 1000)
        seq = self._char_search_seq

        def done_stage1(ok: bool, payload_or_msg, url: str):
            if getattr(self, "_char_search_seq", None) != seq:
                return

            home.char_last_url = url
            if ok and isinstance(payload_or_msg, dict):
                home.char_xp_source_url = str(payload_or_msg.get("gs_exp_url") or "")
            else:
                home.char_xp_source_url = ""

            if ok:
                self._char_show_result(home, payload_or_msg, side_effects=True)

                title = str((payload_or_msg or {}).get("title") or "").strip()
                world = str((payload_or_msg or {}).get("world") or "").strip()
                status_label = str((payload_or_msg or {}).get("status") or "").strip().lower()
                last_login_iso = (payload_or_msg or {}).get("last_login_iso")

                if title and world and world.upper() != "N/A":
                    try:
                        self._cache_set(f"fav_world:{title.lower()}", world)
                    except Exception:
                        log_current_exception(prefix=f"[char] falha ao cachear world: {title}")
                if title and status_label == "online":
                    try:
                        self._set_cached_last_seen_online_iso(title, datetime.utcnow().isoformat())
                    except Exception:
                        log_current_exception(prefix=f"[char] falha ao salvar last_seen: {title}")
                if title:
                    try:
                        if status_label == "offline" and isinstance(last_login_iso, str) and last_login_iso.strip():
                            self._set_cached_fav_last_login_iso(title, last_login_iso.strip())
                        elif status_label == "online":
                            self._set_cached_fav_last_login_iso(title, None)
                    except Exception:
                        log_current_exception(prefix=f"[char] falha ao salvar last_login: {title}")

                if not silent:
                    self.toast("Char encontrado.")
            else:
                self._char_show_error(home, str(payload_or_msg))
                if not silent:
                    self.toast(str(payload_or_msg))

        def done_stage2(payload: dict, url: str):
            if getattr(self, "_char_search_seq", None) != seq:
                return
            current = getattr(home, "_last_char_payload", None) or {}
            cur_title = str(current.get("title") or "").strip().lower() if isinstance(current, dict) else ""
            new_title = str(payload.get("title") or "").strip().lower()
            if cur_title and new_title and cur_title != new_title:
                return

            home.char_last_url = url
            home.char_xp_source_url = str(payload.get("gs_exp_url") or "")
            self._char_show_result(home, payload, side_effects=False)

        def worker():
            try:
                data = fetch_character_tibiadata(name)
                if not data:
                    raise ValueError("Sem resposta da API.")
    
                character_wrapper = data.get("character", {})
                character = character_wrapper.get("character", character_wrapper) if isinstance(character_wrapper, dict) else {}
                if not isinstance(character, dict) or not str(character.get("name") or "").strip():
                    raise ValueError("Personagem não encontrado.")
    
                url = f"https://www.tibia.com/community/?subtopic=characters&name={name.replace(' ', '+')}"
                title = str(character.get("name") or name)
    
                voc = character.get("vocation", "N/A")
                level = character.get("level", "N/A")
                world = character.get("world", "N/A")
    
                # Status: prioriza TibiaData (rápido). Dados oficiais (tibia.com) ficam para o "enriquecimento".
                status_raw = str(character.get("status") or "").strip().lower()
                status = "online" if status_raw == "online" else "offline"

                # Correção: TibiaData/tibia.com podem dar falso OFF.
                # A lista oficial de players online por world costuma ser a fonte mais confiável.
                world_status_checked = False
                try:
                    w_clean = str(world or "").strip()
                    if w_clean and w_clean.upper() != "N/A":
                        online_set = self._fetch_world_online_players(w_clean, timeout=12)
                        if online_set is not None:
                            world_status_checked = True
                            status = "online" if (title or name).strip().lower() in online_set else "offline"
                except Exception:
                    world_status_checked = False
    
                guild = character.get("guild") or {}
                guild_name = ""
                guild_rank = ""
                if isinstance(guild, dict) and guild.get("name"):
                    guild_name = str(guild.get("name") or "").strip()
                    guild_rank = str(guild.get("rank") or guild.get("title") or "").strip()
    
                guild_line = (
                    f"Guild: {guild_name}{(' (' + guild_rank + ')') if guild_rank else ''}"
                    if guild_name
                    else "Guild: N/A"
                )
    
                houses = character.get("houses") or []
                houses_list = []
                if isinstance(houses, list):
                    for h in houses:
                        if isinstance(h, dict):
                            hn = str(h.get("name") or h.get("house") or "").strip()
                            ht = str(h.get("town") or "").strip()
                            if hn and ht:
                                houses_list.append(f"{hn} ({ht})")
                            elif hn:
                                houses_list.append(hn)
                        elif isinstance(h, str) and h.strip():
                            houses_list.append(h.strip())
    
                if houses_list:
                    if len(houses_list) == 1:
                        house_line = f"Houses: {houses_list[0]}"
                    else:
                        house_line = f"Houses: {len(houses_list)} (toque para ver)"
                else:
                    house_line = "Houses: Nenhuma"
    
                deaths = (character.get('deaths') or character_wrapper.get('deaths') or data.get('deaths') or [])
                if not isinstance(deaths, list):
                    deaths = []

                # Outros personagens visíveis na conta (TibiaData)
                def _find_other_chars(obj):
                    try:
                        if isinstance(obj, dict):
                            if "other_characters" in obj:
                                return obj.get("other_characters")
                            # alguns wrappers mudam o formato
                            for vv in obj.values():
                                r = _find_other_chars(vv)
                                if r is not None:
                                    return r
                        elif isinstance(obj, list):
                            for vv in obj:
                                r = _find_other_chars(vv)
                                if r is not None:
                                    return r
                    except Exception:
                        return None
                    return None

                other_raw = None
                try:
                    other_raw = character.get("other_characters")
                except Exception:
                    other_raw = None
                if other_raw is None:
                    try:
                        other_raw = character_wrapper.get("other_characters")
                    except Exception:
                        other_raw = None
                if other_raw is None:
                    other_raw = _find_other_chars(data)

                other_chars = []
                try:
                    if isinstance(other_raw, dict) and "other_characters" in other_raw:
                        other_raw = other_raw.get("other_characters")
                    if isinstance(other_raw, list):
                        for oc in other_raw:
                            if isinstance(oc, dict):
                                nm = str(oc.get("name") or oc.get("character") or oc.get("title") or "").strip()
                                if not nm:
                                    continue
                                other_chars.append({
                                    "name": nm,
                                    "world": str(oc.get("world") or "").strip(),
                                    "status": str(oc.get("status") or "").strip().lower(),
                                })
                            elif isinstance(oc, str) and oc.strip():
                                other_chars.append({"name": oc.strip(), "world": "", "status": ""})
                except Exception:
                    other_chars = []
    
                # Fonte do XP 30 dias (GuildStats tab=9)
                gs_exp_url = f"https://guildstats.eu/character?nick={urllib.parse.quote((title or name), safe='')}&tab=9"
    
                # Fallback robusto imediato: estimativa local (não depende de scraping)
                # (A etapa 2 tenta sobrescrever com valores do GuildStats se disponíveis.)
                for d in deaths:
                    if not isinstance(d, dict):
                        continue
                    if d.get("exp_lost"):
                        continue
                    lvl = d.get("level")
                    try:
                        lvl_int = int(lvl)
                    except Exception:
                        continue
                    exp_lost = estimate_death_exp_lost(lvl_int, blessings=7, promoted=True, retro_hardcore=False)
                    if exp_lost:
                        d["exp_lost"] = f"-{exp_lost:,}"
    
                payload = {
                    "title": title,
                    "status": status,
                    "voc": voc,
                    "level": level,
                    "world": world,
                    "guild": {"name": guild_name, "rank": guild_rank} if guild_name else None,
                    "houses": houses_list,
                    "guild_line": guild_line,
                    "house_line": house_line,
                    "deaths": deaths,
    
                    # XP 30 dias (GuildStats) — carregado em background (stage 2)
                    "exp_rows_30": [],
                    "exp_total_30": None,
                    "gs_exp_url": gs_exp_url,
                    "gs_exp_loading": True,

                    "other_characters": other_chars,
                    "stalker_candidates": [],
                    "stalker_loading": True,
                    "stalker_error": "",
                    "stalker_source_url": build_stalker_character_url(title or name),

                    "_world_status_checked": bool(world_status_checked),
                }
    
                # "Última vez online" (offline duration)
                try:
                    if status == "online":
                        # atualiza sempre o instante em que vimos ONLINE (útil para calcular o OFF depois)
                        try:
                            self._set_cached_last_seen_online_iso(title, datetime.utcnow().isoformat())
                        except Exception:
                            pass
                        payload["last_login_iso"] = None
                        payload["last_login_ago"] = None
                    else:
                        # Opção 1 (mais fiel): usa offline_since (detectado pelo monitor em background) quando disponível.
                        off_iso = None
                        try:
                            fav_set = {str(x).strip().lower() for x in (self.favorites or []) if str(x).strip()}
                            if (title or "").strip().lower() in fav_set:
                                ent = self._get_service_last_entry(title)
                                if ent and (not bool(ent.get("online"))):
                                    v = ent.get("offline_since_iso")
                                    if isinstance(v, str) and v.strip():
                                        off_iso = v.strip()
                        except Exception:
                            off_iso = None

                        if off_iso:
                            try:
                                dt = datetime.fromisoformat(off_iso)
                                payload["last_login_iso"] = off_iso
                                payload["last_login_ago"] = self._format_ago_long(dt)
                            except Exception:
                                payload["last_login_iso"] = None
                                payload["last_login_ago"] = None
                        else:
                            # Fallback: último instante em que vimos ONLINE (quando o app estava aberto)
                            seen_iso = self._get_cached_last_seen_online_iso(title)
                            if seen_iso:
                                try:
                                    dt = datetime.fromisoformat(str(seen_iso).strip())
                                    payload["last_login_iso"] = str(seen_iso).strip()
                                    payload["last_login_ago"] = self._format_ago_long(dt)
                                except Exception:
                                    payload["last_login_iso"] = None
                                    payload["last_login_ago"] = None
                            else:
                                # Último recurso (não é logout): TibiaData "Last Login".
                                last_dt = None
                                try:
                                    last_dt = self._extract_last_login_dt_from_tibiadata(data)
                                except Exception:
                                    last_dt = None
                                if last_dt:
                                    payload["last_login_iso"] = last_dt.isoformat()
                                    payload["last_login_ago"] = self._format_ago_long(last_dt)
                                else:
                                    payload["last_login_iso"] = None
                                    payload["last_login_ago"] = None
                except Exception:
                    payload["last_login_iso"] = None
                    payload["last_login_ago"] = None
    
                # Mostra o resultado básico imediatamente.
                Clock.schedule_once(lambda *_: done_stage1(True, payload, url), 0)
    
                # Se outra busca começou, não continua.
                if getattr(self, "_char_search_seq", None) != seq:
                    return
    
                # -----------------------------------------------------------
                # Stage 2: Enriquecimento (GuildStats + status oficial tibia.com)
                # - roda em background
                # - não bloqueia a exibição do resultado básico
                # -----------------------------------------------------------
                try:
                    # Status "oficial": tenta novamente via /v4/world (mais confiável) e evita sobrescrever se já checamos.
                    if not bool(payload.get("_world_status_checked")):
                        try:
                            w_clean2 = str(payload.get("world") or "").strip()
                            if w_clean2 and w_clean2.upper() != "N/A":
                                online_set2 = self._fetch_world_online_players(w_clean2, timeout=12)
                                if online_set2 is not None:
                                    payload["_world_status_checked"] = True
                                    payload["status"] = "online" if (title or name).strip().lower() in online_set2 else "offline"
                        except Exception:
                            pass

                    # Tibia.com apenas como fallback (pode dar falso OFF)
                    if not bool(payload.get("_world_status_checked")):
                        try:
                            online_web = is_character_online_tibia_com(title or name, world or "")
                        except Exception:
                            online_web = None
                        if online_web is True:
                            payload["status"] = "online"
                        elif online_web is False:
                            payload["status"] = "offline"

                    # Outros chars: tenta refinar o status via /v4/world/{world}
                    try:
                        others = payload.get("other_characters")
                        if isinstance(others, list) and others:
                            # agrupa worlds para evitar chamadas duplicadas
                            worlds_map = {}
                            for oc in others:
                                if not isinstance(oc, dict):
                                    continue
                                ww = str(oc.get("world") or "").strip()
                                if not ww or ww.upper() == "N/A":
                                    continue
                                worlds_map.setdefault(ww, []).append(oc)

                            # limita para não abusar de rede
                            for i, (ww, lst) in enumerate(list(worlds_map.items())):
                                if i >= 5:
                                    break
                                try:
                                    online_setw = self._fetch_world_online_players(ww, timeout=10)
                                except Exception:
                                    online_setw = None
                                if online_setw is None:
                                    continue
                                for oc in lst:
                                    nm_l = str(oc.get("name") or "").strip().lower()
                                    if not nm_l:
                                        continue
                                    oc["status"] = "online" if nm_l in online_setw else "offline"
                            payload["other_characters"] = others
                    except Exception:
                        pass
    
                    # Tibia Stalker (suggested alternate characters)
                    try:
                        stalker_data = fetch_stalker_character(title or name, timeout=12)
                        payload["stalker_candidates"] = extract_stalker_candidates(stalker_data, target_name=title or name, limit=10)
                        payload["stalker_error"] = ""
                    except requests.HTTPError as exc:
                        payload["stalker_candidates"] = []
                        status_code = getattr(getattr(exc, "response", None), "status_code", None)
                        if status_code == 404:
                            payload["stalker_error"] = "Sem sugestões para este personagem no Tibia Stalker."
                        else:
                            payload["stalker_error"] = "Tibia Stalker indisponível agora."
                    except Exception:
                        payload["stalker_candidates"] = []
                        payload["stalker_error"] = "Tibia Stalker indisponível agora."
                        log_current_exception(prefix=f"[char] Tibia Stalker falhou: {title or name}")
                    finally:
                        payload["stalker_loading"] = False

                    # Atualiza last_login_* com base no status refinado
                    try:
                        if payload.get("status") == "online":
                            try:
                                self._set_cached_last_seen_online_iso(title, datetime.utcnow().isoformat())
                            except Exception:
                                pass
                            payload["last_login_iso"] = None
                            payload["last_login_ago"] = None
                        else:
                            # se for favorito e o serviço marcou offline_since, usa isso
                            off_iso = None
                            try:
                                fav_set = {str(x).strip().lower() for x in (self.favorites or []) if str(x).strip()}
                                if (title or "").strip().lower() in fav_set:
                                    ent = self._get_service_last_entry(title)
                                    if ent and (not bool(ent.get("online"))):
                                        v = ent.get("offline_since_iso")
                                        if isinstance(v, str) and v.strip():
                                            off_iso = v.strip()
                            except Exception:
                                off_iso = None

                            if off_iso:
                                try:
                                    dt = datetime.fromisoformat(off_iso)
                                    payload["last_login_iso"] = off_iso
                                    payload["last_login_ago"] = self._format_ago_long(dt)
                                except Exception:
                                    pass
                            else:
                                seen_iso = self._get_cached_last_seen_online_iso(title)
                                if seen_iso:
                                    try:
                                        dt = datetime.fromisoformat(str(seen_iso).strip())
                                        payload["last_login_iso"] = str(seen_iso).strip()
                                        payload["last_login_ago"] = self._format_ago_long(dt)
                                    except Exception:
                                        pass
                    except Exception:
                        pass
    
                    # XP últimos ~30 dias (GuildStats tab=9)
                    exp_rows_30 = []
                    exp_total_30 = None
                    try:
                        key = f"gs_exp_rows:{(title or name).strip().lower()}"
                        rows = self._cache_get(key, ttl_seconds=10 * 60)
                        if rows is None:
                            try:
                                print(f"[gs-exp-ui] cache miss name={(title or name)!r}")
                            except Exception:
                                pass
                            rows = fetch_guildstats_exp_changes(title or name, light_only=self._is_android())
                            try:
                                print(f"[gs-exp-ui] fetched rows={len(rows or [])} name={(title or name)!r}")
                            except Exception:
                                pass
                            try:
                                # Nao mantemos lista vazia em cache por muito tempo: se o fansite
                                # falhar temporariamente, a proxima abertura do char deve poder
                                # tentar novamente em vez de prender a UI por 10 minutos.
                                if rows:
                                    self._cache_set(key, rows)
                            except Exception:
                                pass
                        else:
                            try:
                                print(f"[gs-exp-ui] cache hit rows={len(rows or [])} name={(title or name)!r}")
                            except Exception:
                                pass
    
                        if rows:
                            dates = []
                            for r in rows:
                                ds = str(r.get("date") or "")
                                try:
                                    dates.append(datetime.fromisoformat(ds).date())
                                except Exception:
                                    pass
                            ref = max(dates) if dates else datetime.utcnow().date()
                            cutoff = ref - timedelta(days=30)
    
                            for r in rows:
                                ds = str(r.get("date") or "")
                                try:
                                    d = datetime.fromisoformat(ds).date()
                                except Exception:
                                    continue
                                if d < cutoff:
                                    continue
                                exp_rows_30.append(r)
    
                            exp_rows_30.sort(key=lambda x: x.get("date", ""), reverse=True)
                            exp_total_30 = int(sum(int(r.get("exp_change_int") or 0) for r in exp_rows_30))
                    except Exception:
                        exp_rows_30 = []
                        exp_total_30 = None
    
                    payload["exp_rows_30"] = exp_rows_30
                    payload["exp_total_30"] = exp_total_30
                    payload["gs_exp_loading"] = False
    
                    # XP lost por morte (GuildStats tab=5) — tenta sobrescrever a estimativa
                    try:
                        deaths2 = payload.get("deaths") or []
                        xp_list = []
                        if deaths2:
                            key2 = f"gs_death_xp:{(title or name).strip().lower()}"
                            xp_list = self._cache_get(key2, ttl_seconds=6 * 3600)
                            if xp_list is None:
                                try:
                                    xp_list = fetch_guildstats_deaths_xp(title or name, light_only=self._is_android())
                                except Exception:
                                    xp_list = []
                                try:
                                    self._cache_set(key2, xp_list or [])
                                except Exception:
                                    pass
    
                        if xp_list:
                            for i, d in enumerate(deaths2):
                                if i >= len(xp_list):
                                    break
                                if isinstance(d, dict) and xp_list[i]:
                                    d["exp_lost"] = xp_list[i]
                            payload["deaths"] = deaths2
                    except Exception:
                        pass
    
                except Exception:
                    # não falha a busca básica por conta do enrichment
                    pass
    
                # Aplica o enrichment na UI (sem side-effects)
                if getattr(self, "_char_search_seq", None) == seq:
                    Clock.schedule_once(lambda *_: done_stage2(payload, url), 0)
    
            except Exception as e:
                msg = _friendly_char_error(e)
                Clock.schedule_once(lambda *_, msg=msg: done_stage1(False, msg, ""), 0)
    
        threading.Thread(target=worker, daemon=True).start()
    def open_last_in_browser(self):
        home = self.root.get_screen("home")
        url = getattr(home, "char_last_url", "") or ""
        if not url:
            self.toast("Sem link ainda. Faça uma busca primeiro.")
            return
        webbrowser.open(url)
    def open_char_xp_source(self):
        """Abre a fonte do histórico de XP (GuildStats tab=9) no navegador."""
        home = self.root.get_screen("home")
        url = getattr(home, "char_xp_source_url", "") or ""
        if not url:
            self.toast("Sem link ainda. Faça uma busca primeiro.")
            return
        webbrowser.open(url)
    def add_current_to_favorites(self):
        home = self.root.get_screen("home")
        name = (home.ids.char_name.text or "").strip()
        if not name:
            self.toast("Digite o nome do char.")
            return
        if name not in self.favorites:
            self.favorites.append(name)
            self.favorites.sort(key=lambda s: s.lower())
            self.save_favorites()
            # mantém serviço em sync
            try:
                self._maybe_start_fav_monitor_service()
            except Exception:
                pass
            self.refresh_favorites_list()
            self.toast("Adicionado aos favoritos.")
        else:
            self.toast("Já está nos favoritos.")
