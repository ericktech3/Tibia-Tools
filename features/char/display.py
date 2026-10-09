"""Montagem visual do resultado da busca (carregando, erro, resultado, mortes)."""
# flake8: noqa
from features.char._common import *  # noqa: F401,F403
from features.char._common import (  # noqa: F401
    _friendly_char_error, _StalkerCandidateItem, _StalkerBadge, _xp_stats,
)


class CharDisplayMixin:
    def _build_wrapped_info_row(self, text, secondary="", icon="skull"):
        """Linha com altura calculada pelo texto, sem reticências nem cortes."""
        row = _StalkerCandidateItem(
            orientation="horizontal", size_hint_y=None,
            padding=(dp(12), dp(12), dp(12), dp(12)), spacing=dp(12),
        )
        row.bind(minimum_height=row.setter("height"))
        row.add_widget(MDIcon(
            icon=icon, size_hint=(None, None), size=(dp(32), dp(32)),
            pos_hint={"center_y": 0.5},
        ))
        column = MDBoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        column.bind(minimum_height=column.setter("height"))
        for value, color in ((text, "Primary"), (secondary, "Secondary")):
            if not value:
                continue
            label = MDLabel(
                text=str(value), font_style="Body1", theme_text_color=color,
                size_hint_y=None, shorten=False,
            )
            label.bind(width=lambda inst, width: setattr(inst, "text_size", (width, None)))
            label.bind(texture_size=lambda inst, size: setattr(inst, "height", size[1]))
            column.add_widget(label)
        row.add_widget(column)
        return row

    def _death_display_meta(self, death):
        raw_date = str(death.get("time") or death.get("date") or "").strip()
        parsed = self._safe_parse_iso_datetime(raw_date)
        lines = [parsed.astimezone().strftime("%d/%m/%Y às %H:%M")
                 if parsed and parsed.tzinfo else
                 parsed.strftime("%d/%m/%Y às %H:%M") if parsed else raw_date]
        if death.get("level"):
            lines.append(f"Nível {death['level']}")
        xp = death.get("exp_lost") or death.get("xp_lost")
        if xp:
            try:
                xp = f"{int(xp):,}".replace(",", ".")
            except (TypeError, ValueError):
                pass
            lines.append(f"XP perdida: {xp}")
        return "\n".join(line for line in lines if line)

    def _shorten_death_reason(self, reason: str) -> str:
        """Deixa o texto da morte mais legível no card (o completo pode abrir no dialog)."""
        r = (reason or "").strip()
        if not r:
            return ""

        # Tenta reduzir listas enormes de killers: "... by A, B, C and D"
        low = r.lower()
        if " by " in low:
            idx = low.find(" by ")
            prefix = r[:idx].strip().rstrip(".")
            killers = r[idx + 4 :].strip().rstrip(".")

            # normaliza separadores
            killers_norm = killers.replace(" and ", ", ")
            parts = [p.strip() for p in killers_norm.split(",") if p.strip()]
            if parts:
                first = parts[0]
                extra = len(parts) - 1

                # compacta "Slain/Died at Level X" -> "Slain"/"Died"
                event = prefix
                if prefix.lower().startswith("slain"):
                    event = "Slain"
                elif prefix.lower().startswith("died"):
                    event = "Died"

                return f"{event} by {first}" + (f" +{extra}" if extra > 0 else "")

        # fallback: corta com bom senso (sem '...')
        return r[:80] + ("" if len(r) <= 80 else "…")
    def _char_set_loading(self, home, name: str):
        ids = getattr(home, "ids", None)
        if ids is None:
            return

        if "char_title" in ids and "char_details_list" in ids and "char_deaths_list" in ids:
            ids.char_title.text = name
            ids.char_badge.text = ""
            ids.char_details_list.clear_widgets()

            item = OneLineIconListItem(text="Buscando informações...")
            item.add_widget(IconLeftWidget(icon="cloud-search"))
            ids.char_details_list.add_widget(item)

            ids.char_deaths_list.clear_widgets()
            death_item = OneLineIconListItem(text="Aguardando...")
            death_item.add_widget(IconLeftWidget(icon="skull-outline"))
            ids.char_deaths_list.add_widget(death_item)

            xp_total = ids.get("char_xp_total") if hasattr(ids, "get") else None
            xp_list = ids.get("char_xp_list") if hasattr(ids, "get") else None
            if xp_total is not None:
                xp_total.text = "Carregando histórico de XP..."
                xp_total.theme_text_color = "Hint"
            if xp_list is not None:
                xp_list.clear_widgets()
                xp_item = OneLineIconListItem(text="Buscando histórico de XP...")
                xp_item.add_widget(IconLeftWidget(icon="chart-line"))
                xp_list.add_widget(xp_item)

            account_list = ids.get("char_account_list") if hasattr(ids, "get") else None
            if account_list is not None:
                account_list.clear_widgets()
                acc_item = OneLineIconListItem(text="Aguardando...")
                acc_item.add_widget(IconLeftWidget(icon="account-multiple"))
                account_list.add_widget(acc_item)

            stalker_list = ids.get("char_stalker_list") if hasattr(ids, "get") else None
            stalker_hint = ids.get("char_stalker_hint") if hasattr(ids, "get") else None
            if stalker_hint is not None:
                stalker_hint.text = "Sugestões por probabilidade; não é certeza."
            if stalker_list is not None:
                stalker_list.clear_widgets()
                st_item = OneLineIconListItem(text="Consultando Tibia Stalker...")
                st_item.add_widget(IconLeftWidget(icon="account-search-outline"))
                stalker_list.add_widget(st_item)
            return

        char_status = ids.get("char_status") if hasattr(ids, "get") else None
        if char_status is not None:
            char_status.text = "Buscando..."

    def _char_show_error(self, home, message: str):
        ids = getattr(home, "ids", None)
        if ids is None:
            return

        if "char_title" in ids and "char_details_list" in ids and "char_deaths_list" in ids:
            ids.char_title.text = "Erro"
            ids.char_badge.text = ""
            ids.char_details_list.clear_widgets()

            item = OneLineIconListItem(text=message)
            item.add_widget(IconLeftWidget(icon="alert-circle-outline"))
            ids.char_details_list.add_widget(item)

            ids.char_deaths_list.clear_widgets()
            death_item = OneLineIconListItem(text="—")
            death_item.add_widget(IconLeftWidget(icon="skull-outline"))
            ids.char_deaths_list.add_widget(death_item)

            xp_total = ids.get("char_xp_total") if hasattr(ids, "get") else None
            xp_list = ids.get("char_xp_list") if hasattr(ids, "get") else None
            if xp_total is not None:
                xp_total.text = "—"
                xp_total.theme_text_color = "Hint"
            if xp_list is not None:
                xp_list.clear_widgets()
                xp_item = OneLineIconListItem(text="Sem dados.")
                xp_item.add_widget(IconLeftWidget(icon="chart-line"))
                xp_list.add_widget(xp_item)

            account_list = ids.get("char_account_list") if hasattr(ids, "get") else None
            if account_list is not None:
                account_list.clear_widgets()
                acc_item = OneLineIconListItem(text="—")
                acc_item.add_widget(IconLeftWidget(icon="account-multiple"))
                account_list.add_widget(acc_item)

            stalker_list = ids.get("char_stalker_list") if hasattr(ids, "get") else None
            stalker_hint = ids.get("char_stalker_hint") if hasattr(ids, "get") else None
            if stalker_hint is not None:
                stalker_hint.text = "Sugestões por probabilidade; não é certeza."
            if stalker_list is not None:
                stalker_list.clear_widgets()
                st_item = OneLineIconListItem(text="—")
                st_item.add_widget(IconLeftWidget(icon="account-search-outline"))
                stalker_list.add_widget(st_item)
            return

        char_status = ids.get("char_status") if hasattr(ids, "get") else None
        if char_status is not None:
            char_status.text = message

    def _char_show_result(self, home, payload: dict, *, side_effects: bool = True):
        status = str(payload.get("status", "N/A"))
        title = str(payload.get("title", ""))
        voc = str(payload.get("voc", "N/A"))
        level = str(payload.get("level", "N/A"))
        world = str(payload.get("world", "N/A"))
        guild_line = str(payload.get("guild_line", "Guild: N/A"))
        house_line = str(payload.get("house_line", "Houses: N/A"))
        guild = payload.get("guild") or {}
        houses = payload.get("houses") or []
        deaths = payload.get("deaths", [])

        # XP últimos 30 dias (GuildStats tab=9)
        exp_rows_30 = payload.get("exp_rows_30") or []
        exp_total_30 = payload.get("exp_total_30")
        setattr(home, "char_xp_source_url", str(payload.get("gs_exp_url") or ""))
        setattr(home, "_last_char_payload", payload)

        # Side-effects (prefs/history/dashboard) apenas na primeira renderização do resultado.
        if side_effects:
            if title:
                try:
                    self._prefs_set("last_char", title)
                    self._add_to_char_history(title)
                except Exception:
                    log_current_exception(prefix=f"[char] falha ao persistir resultado: {title}")
            try:
                self.dashboard_refresh()
            except Exception:
                log_current_exception(prefix="[char] dashboard_refresh falhou")

        st = status.strip().lower()
        if st == "online":
            badge = "[b][color=#2ecc71]ONLINE[/color][/b]"
            status_icon = "wifi"
        elif st == "offline":
            badge = "[b][color=#e74c3c]OFFLINE[/color][/b]"
            status_icon = "wifi-off"
        else:
            badge = "[b][color=#e74c3c]OFFLINE[/color][/b]"
            status_icon = "help-circle-outline"

        # Layout novo (cards + listas)
        if hasattr(home, "ids") and "char_title" in home.ids and "char_details_list" in home.ids and "char_deaths_list" in home.ids:
            home.ids.char_title.text = title or "Resultado"
            home.ids.char_badge.text = badge

            dl = home.ids.char_details_list
            dl.clear_widgets()

            def add_one(text: str, icon: str, dialog_title: str = "", dialog_text: str = ""):
                item = OneLineIconListItem(text=text)
                item.add_widget(IconLeftWidget(icon=icon))
                if dialog_text:
                    item.bind(on_release=lambda *_: self._show_text_dialog(dialog_title or "Detalhes", dialog_text))
                dl.add_widget(item)

            def add_two(text: str, secondary: str, icon: str, dialog_title: str = "", dialog_text: str = ""):
                item = TwoLineIconListItem(text=text, secondary_text=secondary or " ")
                item.add_widget(IconLeftWidget(icon=icon))
                if dialog_text:
                    item.bind(on_release=lambda *_: self._show_text_dialog(dialog_title or "Detalhes", dialog_text))
                dl.add_widget(item)

            # Usuário pediu para mostrar apenas ONLINE/OFFLINE (sem "Status:")
            add_one((st if st in ("online", "offline") else "offline").capitalize(), status_icon)
            # Se estiver OFFLINE, mostra há quanto tempo (se disponível)
            try:
                if st == "offline":
                    ago = str(payload.get("last_login_ago") or "").strip()
                    if ago:
                        add_two("Última vez online", ago, "clock-outline")
            except Exception:
                pass
            add_one(f"Vocation: {voc}", "account")
            add_one(f"Level: {level}", "signal")
            add_one(f"World: {world}", "earth")

            # Guild (evita cortar demais; toque para ver completo)
            gname = str(guild.get("name") or "").strip() if isinstance(guild, dict) else ""
            grank = str(guild.get("rank") or "").strip() if isinstance(guild, dict) else ""
            if gname:
                full = f"{gname}{(' (' + grank + ')') if grank else ''}".strip()
                if grank:
                    add_two(f"Guild: {gname}", grank, "account-group", "Guild", full)
                else:
                    add_one(f"Guild: {gname}", "account-group", "Guild", full)
            else:
                add_one(guild_line, "account-group")

            # Houses (se for mais de 1, mostra quantidade e abre dialog com a lista)
            houses_list = [str(x).strip() for x in houses if str(x).strip()] if isinstance(houses, list) else []
            if not houses_list:
                add_one("Houses: Nenhuma", "home")
            elif len(houses_list) == 1:
                add_one(f"Houses: {houses_list[0]}", "home", "Houses", houses_list[0])
            else:
                full_h = "\n".join(houses_list)
                add_two("Houses", f"{len(houses_list)} casas", "home", "Houses", full_h)

            # ----------------------------
            # Card: XP últimos 30 dias
            # ----------------------------
            if "char_xp_list" in home.ids:
                def fmt_pt(n: int) -> str:
                    try:
                        s = f"{abs(int(n)):,}".replace(",", ".")
                    except Exception:
                        s = str(n)
                    return ("-" if int(n) < 0 else "+") + s

                try:
                    xlist = home.ids.char_xp_list
                    xlist.clear_widgets()

                    loading_gs = bool(payload.get("gs_exp_loading"))
                    rows = exp_rows_30 if isinstance(exp_rows_30, list) else []

                    if loading_gs and not rows:
                        home.ids.char_xp_total.text = "Carregando histórico de XP..."
                        home.ids.char_xp_total.theme_text_color = "Hint"
                    elif rows and _xp_stats.summarize_xp(rows).get("ok"):
                        _sum = _xp_stats.summarize_xp(rows)
                        _lines = _xp_stats.summary_lines(_sum)
                        _lines.append(f"Atualizado às {datetime.now().strftime('%H:%M')}")
                        home.ids.char_xp_total.text = "\n".join(_lines)
                        home.ids.char_xp_total.theme_text_color = "Primary"
                    elif not loading_gs:
                        home.ids.char_xp_total.text = "Histórico de XP indisponível. Toque no ícone ↗ para conferir."
                        home.ids.char_xp_total.theme_text_color = "Hint"

                    if not rows:
                        it = OneLineIconListItem(text=("Buscando dados no GuildStats..." if loading_gs else "Sem dados."))
                        it.add_widget(IconLeftWidget(icon="chart-line"))
                        xlist.add_widget(it)
                    else:
                        # Mostra sempre os últimos 7 dias (consecutivos). Se o GuildStats não listar um dia,
                        # exibimos 0 para ficar claro que não houve ganho/perda (ou que não foi trackeado).
                        try:
                            # Últimos 7 dias consecutivos; dia sem registro aparece como 0.
                            for d, ev_i in _xp_stats.summarize_xp(rows)["daily_7"]:
                                sec = f"{fmt_pt(ev_i)} XP"
                                icon = "trending-up" if ev_i > 0 else ("trending-down" if ev_i < 0 else "minus")
                                item = TwoLineIconListItem(text=d.strftime("%d/%m/%Y"), secondary_text=sec)
                                item.add_widget(IconLeftWidget(icon=icon))
                                xlist.add_widget(item)
                        except Exception:
                            # fallback: mostra os 7 primeiros registros como antes
                            for r in rows[:7]:
                                ds = str(r.get("date") or "").strip()
                                ev = r.get("exp_change_int")
                                try:
                                    ev_i = int(ev)
                                except Exception:
                                    continue
                                sec = f"{fmt_pt(ev_i)} XP"
                                icon = "trending-up" if ev_i >= 0 else "trending-down"
                                item = TwoLineIconListItem(text=ds, secondary_text=sec)
                                item.add_widget(IconLeftWidget(icon=icon))
                                xlist.add_widget(item)
                except Exception:
                    pass

            dlist = home.ids.char_deaths_list
            dlist.clear_widgets()

            deaths_list = [d for d in deaths if isinstance(d, dict)] if isinstance(deaths, list) else []
            try:
                _ds = _xp_stats.summarize_deaths(deaths_list)
                if _ds["count"]:
                    _txt = f"{_ds['count']} morte(s) recente(s)"
                    if _ds["xp_lost"]:
                        _txt += f"\nXP perdida: {_xp_stats.fmt_compact(_ds['xp_lost'])}"
                    _hdr = self._build_wrapped_info_row(_txt, icon="chart-bar")
                    dlist.add_widget(_hdr)
            except Exception:
                pass
            for d in deaths_list[:10]:
                reason_s = str(d.get("reason") or d.get("description") or "").strip()
                if not reason_s:
                    continue
                meta = self._death_display_meta(d)
                it = self._build_wrapped_info_row(reason_s, meta, icon="skull")
                it.bind(on_release=lambda *_ , rr=reason_s, mm=meta: self._show_text_dialog("Morte", f"{rr}\n\n{mm}".strip()))
                dlist.add_widget(it)

            if len(dlist.children) == 0:
                ditem = self._build_wrapped_info_row("Sem mortes recentes (ou sem dados).", icon="skull-outline")
                dlist.add_widget(ditem)

            # ----------------------------
            # Card: Tibia Stalker
            # ----------------------------
            if "char_stalker_list" in home.ids:
                try:
                    s_hint = home.ids.get("char_stalker_hint") if hasattr(home.ids, "get") else None
                    s_list = home.ids.char_stalker_list
                    s_list.clear_widgets()

                    loading_stalker = bool(payload.get("stalker_loading"))
                    stalker_error = str(payload.get("stalker_error") or "").strip()
                    stalker_rows = payload.get("stalker_candidates") or []
                    if s_hint is not None:
                        s_hint.text = "Sugestões por probabilidade; não é certeza."

                    if loading_stalker and not stalker_rows:
                        item = OneLineIconListItem(text="Consultando Tibia Stalker...")
                        item.add_widget(IconLeftWidget(icon="account-search-outline"))
                        s_list.add_widget(item)
                    elif isinstance(stalker_rows, list) and stalker_rows:
                        for row in stalker_rows[:10]:
                            if not isinstance(row, dict):
                                continue
                            widget = self._build_stalker_candidate_widget(row)
                            if widget is None:
                                continue
                            s_list.add_widget(widget)
                    else:
                        txt = stalker_error or "Sem sugestões para este personagem no Tibia Stalker."
                        item = OneLineIconListItem(text=txt)
                        item.add_widget(IconLeftWidget(icon="account-search-outline"))
                        s_list.add_widget(item)
                except Exception:
                    log_current_exception(prefix="[char] falha ao renderizar Tibia Stalker")

            # ----------------------------
            # Card: Outros chars na conta
            # ----------------------------
            if "char_account_list" in home.ids:
                try:
                    alist = home.ids.char_account_list
                    alist.clear_widgets()

                    others = payload.get("other_characters")
                    if others is None:
                        others = payload.get("other_chars")
                    if not isinstance(others, list):
                        others = []

                    # remove o próprio char, se vier na lista
                    cur_l = (title or "").strip().lower()
                    cleaned = []
                    for oc in others:
                        if not isinstance(oc, dict):
                            continue
                        nm = str(oc.get("name") or oc.get("title") or "").strip()
                        if not nm:
                            continue
                        if cur_l and nm.strip().lower() == cur_l:
                            continue
                        cleaned.append({
                            "name": nm,
                            "world": str(oc.get("world") or "").strip(),
                            "status": str(oc.get("status") or "").strip().lower(),
                        })

                    if not cleaned:
                        aitem = OneLineIconListItem(text="Nenhum outro personagem visível na conta.")
                        aitem.add_widget(IconLeftWidget(icon="account-multiple"))
                        alist.add_widget(aitem)
                    else:
                        # ordena por nome
                        cleaned.sort(key=lambda x: x.get("name", "").lower())
                        for oc in cleaned:
                            nm = oc.get("name") or ""
                            ww = oc.get("world") or ""
                            st2 = oc.get("status") or ""

                            # Se tivermos status, mostra junto; senão só o world.
                            sec = ww if ww else " "
                            if st2 in ("online", "offline"):
                                sec = (sec + (" • " if sec.strip() else "") + st2.capitalize()).strip()

                            icon = "wifi" if st2 == "online" else "wifi-off" if st2 == "offline" else "account"
                            it = TwoLineIconListItem(text=nm, secondary_text=sec or " ")
                            it.add_widget(IconLeftWidget(icon=icon))
                            it.bind(on_release=lambda *_ , nn=nm: self.open_char_from_account_list(nn))
                            alist.add_widget(it)
                except Exception:
                    pass
            return

        # Fallback antigo (se ainda existir)
        if "char_status" in home.ids:
            home.ids.char_status.text = (
                f"Status: {status}\n"
                f"Vocation: {voc}\n"
                f"Level: {level}\n"
                f"World: {world}\n"
                f"{guild_line}\n"
                f"{house_line}"
            )
