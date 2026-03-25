import unittest
from unittest.mock import patch

from integrations.tibiadata import (
    _fetch_guildstats_exp_html,
    _html_to_plain_text,
    fetch_guildstats_exp_changes,
)


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
    @patch("integrations.tibiadata._fetch_guildstats_exp_html", return_value=DIV_BASED_EXP_HTML)
    def test_light_only_parses_div_based_experience_history(self, _mock_fetch_html):
        rows = fetch_guildstats_exp_changes("Elder Tree", light_only=True)
        self.assertEqual(
            rows,
            [
                {"date": "2026-03-18", "exp_change": "+452,409", "exp_change_int": 452409},
                {"date": "2026-03-19", "exp_change": "0", "exp_change_int": 0},
                {"date": "2026-03-20", "exp_change": "-2,248,219", "exp_change_int": -2248219},
            ],
        )


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
    @patch("integrations.tibiadata._fetch_guildstats_exp_html", return_value=TWO_ROW_TABLE_HTML)
    def test_light_only_accepts_history_with_two_rows(self, _mock_fetch_html):
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
        if tag == "tr":
            return [_FakeTr(["2026-03-20", "gain +452,409", "330"]), _FakeTr(["2026-03-21", "stable 0", "330"])]
        if tag == "table":
            return []
        return []


class GuildStatsAndroidFallbackTests(unittest.TestCase):
    @patch("integrations.tibiadata.BeautifulSoup", return_value=_FakeSoup())
    @patch("integrations.tibiadata._fetch_guildstats_exp_html", return_value="<html></html>")
    def test_light_only_falls_back_to_beautifulsoup_when_fast_path_fails(self, _mock_fetch_html, _mock_bs4):
        rows = fetch_guildstats_exp_changes("Elder Tree", light_only=True)
        self.assertEqual(
            rows,
            [
                {"date": "2026-03-20", "exp_change": "gain +452,409", "exp_change_int": 452409},
                {"date": "2026-03-21", "exp_change": "stable 0", "exp_change_int": 0},
            ],
        )


SCRIPT_BASED_EXP_HTML = """
<html>
  <body>
    <script>
      const expSeries = [
        ["2026-03-20", 452409],
        ["2026-03-21", 0],
        ["2026-03-22", -2248219]
      ];
    </script>
  </body>
</html>
"""


class GuildStatsScriptFallbackTests(unittest.TestCase):
    @patch("integrations.tibiadata._fetch_guildstats_exp_html", return_value=SCRIPT_BASED_EXP_HTML)
    def test_light_only_parses_script_based_experience_history(self, _mock_fetch_html):
        rows = fetch_guildstats_exp_changes("Elder Tree", light_only=True)
        self.assertEqual(
            rows,
            [
                {"date": "2026-03-20", "exp_change": "+452,409", "exp_change_int": 452409},
                {"date": "2026-03-21", "exp_change": "0", "exp_change_int": 0},
                {"date": "2026-03-22", "exp_change": "-2,248,219", "exp_change_int": -2248219},
            ],
        )


RESPONSIVE_EXP_HTML = """
<html>
  <body>
    <div>Menu</div>
    <div>Date Best recorded day * Rank Lvl</div>
    <div>2025-04-21 +9,806,361 7 147</div>
    <div>Level prediction Average daily exp</div>
    <div>Date Exp change Vocation rank Lvl Experience Time on-line Avg exp per hour</div>
    <div>2026-03-10 View on Tibia.com +946,476 162 (+2) 158 64,434,244 0</div>
    <div>2026-03-11 card item +315,053 164 (-2) 159 (+1) 64,749,297 15min 1,260,212/h</div>
    <div>2026-03-12 mobile card 0 165 (-1) 159 65,066,344 0</div>
    <div>Total in month +1,261,529 -8 +1</div>
  </body>
</html>
"""


class GuildStatsResponsiveLayoutTests(unittest.TestCase):
    @patch("integrations.tibiadata._fetch_guildstats_exp_html", return_value=RESPONSIVE_EXP_HTML)
    def test_light_only_parses_current_responsive_text_layout(self, _mock_fetch_html):
        rows = fetch_guildstats_exp_changes("Elder Tree", light_only=True)
        self.assertEqual(
            rows,
            [
                {"date": "2026-03-10", "exp_change": "+946,476", "exp_change_int": 946476},
                {"date": "2026-03-11", "exp_change": "+315,053", "exp_change_int": 315053},
                {"date": "2026-03-12", "exp_change": "0", "exp_change_int": 0},
            ],
        )


REORDERED_RESPONSIVE_EXP_HTML = """
<html>
  <body>
    <div>Date Exp change Vocation rank Lvl Experience Time on-line Avg exp per hour</div>
    <div>2026-03-20 card Rank 167 (+1) Level 556 Change +12,345,678 Experience 889,000,000 Time on-line 1h</div>
    <div>2026-03-21 card Rank 168 (-1) Level 556 Change 0 Experience 889,000,000 Time on-line 0</div>
    <div>Total in month +12,345,678</div>
  </body>
</html>
"""


class GuildStatsReorderedCardLayoutTests(unittest.TestCase):
    @patch("integrations.tibiadata._fetch_guildstats_exp_html", return_value=REORDERED_RESPONSIVE_EXP_HTML)
    def test_light_only_ignores_rank_deltas_and_finds_exp_later_in_block(self, _mock_fetch_html):
        rows = fetch_guildstats_exp_changes("Elder Tree", light_only=True)
        self.assertEqual(
            rows,
            [
                {"date": "2026-03-20", "exp_change": "+12,345,678", "exp_change_int": 12345678},
                {"date": "2026-03-21", "exp_change": "0", "exp_change_int": 0},
            ],
        )


BASE_CHARACTER_HTML = """
<html>
  <body>
    <ul>
      <li><a href="/character?nick=Elder+Tree&tab=9">Experience</a></li>
    </ul>
  </body>
</html>
"""


class GuildStatsPreflightSessionTests(unittest.TestCase):
    @patch("integrations.tibiadata._new_browser_session")
    @patch("integrations.tibiadata._session_get_text")
    def test_fetch_exp_html_prefetches_character_page_then_uses_same_session_for_tab(self, mock_session_get, mock_new_session):
        fake_session = object()
        mock_new_session.return_value = fake_session

        calls = []

        def side_effect(session, url, timeout, headers=None):
            calls.append(url)
            self.assertIs(session, fake_session)
            if "tab=9" in url:
                return DIV_BASED_EXP_HTML
            return BASE_CHARACTER_HTML

        mock_session_get.side_effect = side_effect

        html = _fetch_guildstats_exp_html("Elder Tree", timeout=12)
        plain = _html_to_plain_text(html)

        self.assertIn("Date Exp change", plain)
        self.assertGreaterEqual(len(calls), 2)
        self.assertIn("character?lang=en&nick=Elder+Tree", calls[0])
        self.assertIn("tab=9", calls[1])


if __name__ == "__main__":
    unittest.main()

DUPLICATE_ZERO_TABLE_HTML = """
<html>
  <body>
    <table class="mobile-shadow-copy">
      <tr><th>Date</th><th>Time on-line</th><th>Lvl</th></tr>
      <tr><td data-sort="2026-03-17">03-17</td><td>0</td><td>554</td></tr>
      <tr><td data-sort="2026-03-18">03-18</td><td>0</td><td>554</td></tr>
      <tr><td data-sort="2026-03-19">03-19</td><td>0</td><td>555 (+1)</td></tr>
      <tr><td data-sort="2026-03-20">03-20</td><td>0</td><td>555</td></tr>
      <tr><td data-sort="2026-03-21">03-21</td><td>0</td><td>555</td></tr>
      <tr><td data-sort="2026-03-22">03-22</td><td>0</td><td>555</td></tr>
      <tr><td data-sort="2026-03-23">03-23</td><td>0</td><td>556 (+1)</td></tr>
    </table>

    <table class="exp-history">
      <tr><th>Date</th><th>Exp change</th><th>Lvl</th></tr>
      <tr><td data-sort="2026-03-17">03-17</td><td data-sort="19498268">+19,498,268</td><td>554 (+1)</td></tr>
      <tr><td data-sort="2026-03-18">03-18</td><td data-sort="31">+31</td><td>554</td></tr>
      <tr><td data-sort="2026-03-19">03-19</td><td data-sort="5231733">+5,231,733</td><td>555 (+1)</td></tr>
      <tr><td data-sort="2026-03-20">03-20</td><td data-sort="0">0</td><td>555</td></tr>
      <tr><td data-sort="2026-03-21">03-21</td><td data-sort="0">0</td><td>555</td></tr>
      <tr><td data-sort="2026-03-22">03-22</td><td data-sort="5197">+5,197</td><td>555</td></tr>
      <tr><td data-sort="2026-03-23">03-23</td><td data-sort="19129284">+19,129,284</td><td>556 (+1)</td></tr>
    </table>
  </body>
</html>
"""


class GuildStatsDuplicateTableRegressionTests(unittest.TestCase):
    @patch("integrations.tibiadata._fetch_guildstats_exp_html", return_value=DUPLICATE_ZERO_TABLE_HTML)
    def test_prefers_labeled_exp_table_over_duplicate_zero_shadow_table(self, _mock_fetch_html):
        rows = fetch_guildstats_exp_changes("Elder Aegir", light_only=True)
        self.assertEqual(
            rows,
            [
                {"date": "2026-03-17", "exp_change": "+19,498,268", "exp_change_int": 19498268},
                {"date": "2026-03-18", "exp_change": "+31", "exp_change_int": 31},
                {"date": "2026-03-19", "exp_change": "+5,231,733", "exp_change_int": 5231733},
                {"date": "2026-03-20", "exp_change": "0", "exp_change_int": 0},
                {"date": "2026-03-21", "exp_change": "0", "exp_change_int": 0},
                {"date": "2026-03-22", "exp_change": "+5,197", "exp_change_int": 5197},
                {"date": "2026-03-23", "exp_change": "+19,129,284", "exp_change_int": 19129284},
            ],
        )
