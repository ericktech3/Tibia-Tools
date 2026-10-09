"""Histórico de buscas de personagens."""
from features.char._common import (
    dp, MDDropdownMenu, log_current_exception,
)


class CharHistoryMixin:
    def _get_char_history(self) -> list[str]:
        hist = self._prefs_get("char_history", []) or []
        if not isinstance(hist, list):
            return []
        out = []
        for value in hist:
            item = str(value or "").strip()
            if item:
                out.append(item)
        return out

    def _add_to_char_history(self, name: str) -> None:
        name = (name or "").strip()
        if not name:
            return
        try:
            hist = [h for h in self._get_char_history() if h.strip().lower() != name.lower()]
            hist.insert(0, name)
            self._prefs_set("char_history", hist[:12])
        except Exception:
            log_current_exception(prefix=f"[char] falha ao salvar histórico: {name}")

    def open_char_history_menu(self):
        home = self._get_home_screen()
        ids = getattr(home, "ids", None) if home is not None else None
        anchor = ids.get("char_name") if hasattr(ids, "get") else None
        if anchor is None:
            return

        hist = self._get_char_history()
        if not hist:
            self.toast("Sem histórico ainda.")
            return

        def pick(selected: str):
            char_name = ids.get("char_name") if hasattr(ids, "get") else None
            if char_name is None:
                return
            char_name.text = selected
            self._safe_menu_dismiss("_menu_char_history")
            try:
                char_name.focus = True
            except Exception:
                log_current_exception(prefix="[char] falha ao focar histórico")

        menu_items = [
            {
                "viewclass": "OneLineListItem",
                "text": item,
                "on_release": (lambda selected=item: pick(selected)),
            }
            for item in hist
        ]

        self._safe_menu_dismiss("_menu_char_history")
        self._menu_char_history = MDDropdownMenu(
            caller=anchor,
            items=menu_items,
            width_mult=4,
            max_height=dp(320),
        )
        self._menu_char_history.open()
