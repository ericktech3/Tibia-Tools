import unittest
from unittest.mock import patch

from integrations.tibiadata import fetch_guildstats_exp_changes


DIV_BASED_EXP_HTML = """
<html>
  <body>
    <div>Former worlds: Antica (03-02-2025) at level 450</div>
    <div>Date Exp change Vocation rank Lvl Experience Time on-line Avg exp per hour</div>
    <div>2026-03-18 +452,409 660 (-1) 330 592,164,432 0</div>
    <div>2026-03-19 0 660 330 592,164,432 0</div>
    <div>2026-03-20 -2,248,219 660 330 589,916,213 8h</div>
    <div>Total in month -1,795,810</div>
  </body>
</html>
"""


class GuildStatsExpHistoryTests(unittest.TestCase):
    @patch("integrations.tibiadata._get_text", return_value=DIV_BASED_EXP_HTML)
    def test_light_only_parses_div_based_experience_history(self, _mock_get_text):
        rows = fetch_guildstats_exp_changes("Elder Tree", light_only=True)
        self.assertEqual(
            rows,
            [
                {"date": "2026-03-18", "exp_change": "+452,409", "exp_change_int": 452409},
                {"date": "2026-03-19", "exp_change": "0", "exp_change_int": 0},
                {"date": "2026-03-20", "exp_change": "-2,248,219", "exp_change_int": -2248219},
            ],
        )


if __name__ == "__main__":
    unittest.main()


TWO_ROW_TABLE_HTML = """
<html>
  <body>
    <table>
      <tr><th>Date</th><th>Exp change</th><th>Lvl</th></tr>
      <tr><td>2026-03-20</td><td>+452,409</td><td>330</td></tr>
      <tr><td>2026-03-21</td><td>0</td><td>330</td></tr>
    </table>
  </body>
</html>
"""


class GuildStatsSmallHistoryTests(unittest.TestCase):
    @patch("integrations.tibiadata._get_text", return_value=TWO_ROW_TABLE_HTML)
    def test_light_only_accepts_history_with_two_rows(self, _mock_get_text):
        rows = fetch_guildstats_exp_changes("Elder Tree", light_only=True)
        self.assertEqual(
            rows,
            [
                {"date": "2026-03-20", "exp_change": "+452,409", "exp_change_int": 452409},
                {"date": "2026-03-21", "exp_change": "0", "exp_change_int": 0},
            ],
        )


class _FakeCell:
    def __init__(self, text: str):
        self._text = text

    def get_text(self, sep: str = " ", strip: bool = True):
        return self._text


class _FakeTr:
    def __init__(self, cells):
        self._cells = [_FakeCell(c) for c in cells]

    def find_all(self, tags):
        return self._cells


class _FakeSoup:
    def find_all(self, tag):
        if tag == 'tr':
            return [_FakeTr(["2026-03-20", "gain +452,409", "330"]), _FakeTr(["2026-03-21", "stable 0", "330"])]
        if tag == 'table':
            return []
        return []


class GuildStatsAndroidFallbackTests(unittest.TestCase):
    @patch("integrations.tibiadata.BeautifulSoup", return_value=_FakeSoup())
    @patch("integrations.tibiadata._get_text", return_value="<html></html>")
    def test_light_only_falls_back_to_beautifulsoup_when_fast_path_fails(self, _mock_get_text, _mock_bs4):
        rows = fetch_guildstats_exp_changes("Elder Tree", light_only=True)
        self.assertEqual(
            rows,
            [
                {"date": "2026-03-20", "exp_change": "gain +452,409", "exp_change_int": 452409},
                {"date": "2026-03-21", "exp_change": "stable 0", "exp_change_int": 0},
            ],
        )
