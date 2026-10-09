"""Sugestões de personagens (TibiaStalker) e seus cartões."""
from features.char._common import (
    dp, webbrowser,
    MDBoxLayout, MDIcon, MDLabel, MDProgressBar,
    _StalkerBadge, _StalkerCandidateItem, log_current_exception,
)


class CharStalkerMixin:
    def _stalker_percent_value(self, row: dict):
        value = row.get("display_percent")
        try:
            if value is None:
                value = row.get("score")
            if value is None:
                value = row.get("estimated_index")
            value = float(value)
        except (TypeError, ValueError):
            return None
        if 0 <= value <= 1:
            value *= 100.0
        return max(0.0, min(100.0, value))

    def _stalker_confidence_label(self, row: dict) -> str:
        label = str(row.get("confidence_label") or "").strip()
        if label:
            return label
        value = self._stalker_percent_value(row)
        if value is None:
            return ""
        if value >= 80:
            return "VERY HIGH"
        if value >= 50:
            return "MEDIUM"
        if value > 0:
            return "LOW"
        return ""

    def _stalker_visual_palette(self, row: dict) -> dict:
        label = self._stalker_confidence_label(row)
        palettes = {
            "VERY HIGH": {
                "badge_bg": (0.18, 0.58, 0.23, 1),
                "badge_text": (1, 1, 1, 1),
                "bar": (0.47, 0.93, 0.29, 1),
                "bar_bg": (0.20, 0.27, 0.20, 1),
            },
            "MEDIUM": {
                "badge_bg": (0.88, 0.62, 0.10, 1),
                "badge_text": (0.13, 0.10, 0.02, 1),
                "bar": (0.98, 0.81, 0.23, 1),
                "bar_bg": (0.28, 0.24, 0.14, 1),
            },
            "LOW": {
                "badge_bg": (0.29, 0.52, 0.92, 1),
                "badge_text": (1, 1, 1, 1),
                "bar": (0.35, 0.67, 1.0, 1),
                "bar_bg": (0.18, 0.24, 0.33, 1),
            },
        }
        return palettes.get(label, {
            "badge_bg": (0.35, 0.35, 0.35, 1),
            "badge_text": (1, 1, 1, 1),
            "bar": (0.24, 0.65, 0.96, 1),
            "bar_bg": (0.27, 0.27, 0.27, 1),
        })

    def _format_stalker_secondary(self, row: dict) -> str:
        bits = []
        display_percent_text = str(row.get("display_percent_text") or "").strip()
        if display_percent_text:
            bits.append(f"Score {display_percent_text}")

        matches_text = str(row.get("matches_text") or "").strip()
        if matches_text:
            bits.append(matches_text)
        elif not display_percent_text:
            score_text = str(row.get("score_text") or "").strip()
            if score_text:
                bits.append(f"Score {score_text}")
        world = str(row.get("world") or "").strip()
        if world:
            bits.append(world)
        level = row.get("level")
        if isinstance(level, int):
            bits.append(f"lvl {level}")
        voc = str(row.get("vocation") or "").strip()
        if voc:
            bits.append(voc)
        last_match_date = str(row.get("last_match_date") or "").strip()
        if last_match_date:
            bits.append(f"última {last_match_date}")
        first_match_date = str(row.get("first_match_date") or "").strip()
        if first_match_date and not last_match_date:
            bits.append(f"primeira {first_match_date}")
        return " • ".join(bits) if bits else "Toque para abrir no app"

    def _build_stalker_candidate_widget(self, row: dict):
        nm = str(row.get("name") or "").strip()
        if not nm:
            return None

        percent = self._stalker_percent_value(row)
        percent_text = str(row.get("display_percent_text") or "").strip()
        if not percent_text and percent is not None:
            rounded = round(percent, 1)
            percent_text = f"{int(rounded)}%" if abs(rounded - round(rounded)) < 1e-9 else f"{rounded:.1f}%"
        confidence_label = self._stalker_confidence_label(row)
        palette = self._stalker_visual_palette(row)

        score_text = f"Score {percent_text}" if percent_text else "Score indisponível"
        matches_text = str(row.get("matches_text") or "").strip() or "Sem correlações detalhadas"

        right_meta_bits = []
        last_match_date = str(row.get("last_match_date") or "").strip()
        if last_match_date:
            right_meta_bits.append(f"última {last_match_date}")
        world = str(row.get("world") or "").strip()
        level = row.get("level")
        vocation = str(row.get("vocation") or "").strip()

        world_line_bits = []
        if world:
            world_line_bits.append(world)
        if isinstance(level, int):
            world_line_bits.append(f"lvl {level}")
        if world_line_bits:
            right_meta_bits.append(" • ".join(world_line_bits))
        if vocation:
            right_meta_bits.append(vocation)

        item = _StalkerCandidateItem(
            orientation="vertical",
            size_hint_y=None,
            padding=(dp(14), dp(10), dp(14), dp(10)),
            spacing=dp(8),
        )
        item.bind(minimum_height=item.setter("height"))
        item.bind(on_release=lambda *_: self.open_char_from_stalker_list(nm))

        header = MDBoxLayout(size_hint_y=None, height=dp(30), spacing=dp(10))
        header.add_widget(MDIcon(icon="account-search", size_hint=(None, None), size=(dp(24), dp(24)), pos_hint={"center_y": 0.5}))
        header.add_widget(MDLabel(
            text=nm,
            font_style="Body1",
            bold=True,
            shorten=True,
            shorten_from="right",
        ))
        badge = _StalkerBadge(
            text=confidence_label or (percent_text or "INFO"),
            bg_color=palette["badge_bg"],
            text_color=palette["badge_text"],
        )
        header.add_widget(badge)
        item.add_widget(header)

        columns = MDBoxLayout(size_hint_y=None, adaptive_height=True, spacing=dp(12))

        left_col = MDBoxLayout(orientation="vertical", size_hint_y=None, adaptive_height=True, spacing=dp(2))
        left_col.add_widget(MDLabel(
            text=score_text,
            font_style="Subtitle1",
            bold=True,
            size_hint_y=None,
            adaptive_height=True,
        ))
        left_col.add_widget(MDLabel(
            text=matches_text,
            theme_text_color="Secondary",
            size_hint_y=None,
            adaptive_height=True,
        ))
        columns.add_widget(left_col)

        right_col = MDBoxLayout(orientation="vertical", size_hint_x=0.42, size_hint_y=None, adaptive_height=True, spacing=dp(2))
        if right_meta_bits:
            for bit in right_meta_bits[:2]:
                right_col.add_widget(MDLabel(
                    text=bit,
                    halign="right",
                    theme_text_color="Secondary",
                    size_hint_y=None,
                    adaptive_height=True,
                    shorten=True,
                    shorten_from="right",
                ))
        else:
            right_col.add_widget(MDLabel(
                text="Toque para abrir no app",
                halign="right",
                theme_text_color="Secondary",
                size_hint_y=None,
                adaptive_height=True,
            ))
        columns.add_widget(right_col)
        item.add_widget(columns)

        progress_row = MDBoxLayout(size_hint_y=None, height=dp(18), spacing=dp(8))
        bar = MDProgressBar(value=percent or 0.0, max=100, size_hint_y=None, height=dp(8))
        try:
            bar.color = palette["bar"]
        except Exception:
            setattr(bar, "color", palette["bar"])
        try:
            bar.back_color = palette["bar_bg"]
        except Exception:
            setattr(bar, "back_color", palette["bar_bg"])
        progress_row.add_widget(bar)
        progress_row.add_widget(MDLabel(
            text=percent_text or "—",
            size_hint_x=None,
            width=dp(46),
            halign="right",
            theme_text_color="Secondary",
            font_style="Caption",
        ))
        item.add_widget(progress_row)
        return item

    def open_char_from_stalker_list(self, name: str):
        self.open_char_from_account_list(name)

    def open_char_stalker_source(self):
        home = self._get_home_screen()
        url = getattr(home, "char_stalker_source_url", "") if home is not None else ""
        if not url:
            self.toast("Sem link do Tibia Stalker para abrir agora.")
            return
        try:
            webbrowser.open(url)
        except Exception:
            log_current_exception(prefix="[char] falha ao abrir Tibia Stalker no navegador")
            self.toast("Não foi possível abrir o Tibia Stalker.")
