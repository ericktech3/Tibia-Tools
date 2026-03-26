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

SIGNLESS_FLAT_TEXT_HTML = """
<html>
  <body>
    Date Exp change Vocation rank Lvl Experience Time on-line Avg exp per hour
    2026-03-17 19,498,268 554 (+1) 555 1,500,000,000 1h 10,000/h
    2026-03-18 31 554 554 1,500,000,031 0
    2026-03-19 5,231,733 555 (+1) 555 1,505,231,764 2h 100/h
    2026-03-20 0 555 555 1,505,231,764 0
    2026-03-21 0 555 555 1,505,231,764 0
    2026-03-22 5,197 555 555 1,505,236,961 0
    2026-03-23 19,129,284 556 (+1) 556 1,524,366,245 0
    Total in month 434,905,872 29 0
  </body>
</html>
"""


class GuildStatsSignlessFlatTextRegressionTests(unittest.TestCase):
    @patch("integrations.tibiadata._fetch_guildstats_exp_html", return_value=SIGNLESS_FLAT_TEXT_HTML)
    def test_prefers_leading_unsigned_exp_before_trailing_zero(self, _mock_fetch_html):
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


WRONG_TAB_HTML = """
<html>
  <body>
    <div>Menu</div>
    <div>Character History Experience Time online Highscore Deaths</div>
    <div>Elder Aegir - Elder Druid (Serdebra)</div>
    <div>Former worlds: 2025-02-03 Antica</div>
    <div>GuildStats.eu</div>
  </body>
</html>
"""


class GuildStatsRejectWrongTabTests(unittest.TestCase):
    @patch("integrations.tibiadata._new_browser_session")
    @patch("integrations.tibiadata._session_get_text")
    def test_fetch_exp_html_rejects_non_experience_html_even_when_tab_request_returns_200(self, mock_session_get, mock_new_session):
        fake_session = object()
        mock_new_session.return_value = fake_session

        def side_effect(session, url, timeout, headers=None):
            self.assertIs(session, fake_session)
            if "tab=9" in url:
                return WRONG_TAB_HTML
            return BASE_CHARACTER_HTML

        mock_session_get.side_effect = side_effect

        html = _fetch_guildstats_exp_html("Elder Aegir", timeout=12)
        self.assertEqual(html, "")


FALSE_POSITIVE_ZERO_HTML = """
<html>
  <body>
    <div>Elder Aegir - Elder Druid (Serdebra)</div>
    <div>History 2026-03-17 0 2026-03-18 0 2026-03-19 0</div>
    <div>Deaths 2026-03-20 0</div>
  </body>
</html>
"""


class GuildStatsFalsePositiveGuardTests(unittest.TestCase):
    @patch("integrations.tibiadata._fetch_guildstats_exp_html", return_value=FALSE_POSITIVE_ZERO_HTML)
    def test_does_not_fabricate_zero_rows_from_non_experience_flat_text(self, _mock_fetch_html):
        rows = fetch_guildstats_exp_changes("Elder Aegir", light_only=True)
        self.assertEqual(rows, [])

BASE_PAGE_WITH_EMBEDDED_EXP_TABLE_HTML = """
<html>
  <body>
    <div>Character History Experience Time online Highscore Deaths</div>
    <table class="exp-history responsive">
      <tr><th>Date</th><th>Change</th><th>Lvl</th><th>Time on-line</th></tr>
      <tr><td data-sort="2026-03-22">03-22</td><td data-sort="5197">+5,197</td><td>555</td><td>0</td></tr>
      <tr><td data-sort="2026-03-23">03-23</td><td data-sort="19129284">+19,129,284</td><td>556 (+1)</td><td>3h</td></tr>
    </table>
  </body>
</html>
"""


class GuildStatsEmbeddedBasePageFallbackTests(unittest.TestCase):
    @patch("integrations.tibiadata._new_browser_session")
    @patch("integrations.tibiadata._session_get_text")
    def test_fetch_exp_html_can_fall_back_to_base_page_when_it_already_contains_exp_table(self, mock_session_get, mock_new_session):
        fake_session = object()
        mock_new_session.return_value = fake_session

        def side_effect(session, url, timeout, headers=None):
            self.assertIs(session, fake_session)
            if "tab=9" in url:
                return WRONG_TAB_HTML
            return BASE_PAGE_WITH_EMBEDDED_EXP_TABLE_HTML

        mock_session_get.side_effect = side_effect

        html = _fetch_guildstats_exp_html("Elder Aegir", timeout=12)
        plain = _html_to_plain_text(html)
        self.assertIn("03-23", plain)
        self.assertIn("+19,129,284", plain)


SHORT_DATE_ONLY_EXP_HTML = """
<html>
  <body>
    <div>Date Change Time on-line Avg exp per hour</div>
    <div>03-22 +5,197 0 0</div>
    <div>03-23 +19,129,284 3h 6,376,428/h</div>
    <div>Total in month +434,905,872</div>
  </body>
</html>
"""


class GuildStatsShortDateDetectionTests(unittest.TestCase):
    @patch("integrations.tibiadata._fetch_guildstats_exp_html", return_value=SHORT_DATE_ONLY_EXP_HTML)
    def test_accepts_short_mm_dd_layout_when_exp_context_is_present(self, _mock_fetch_html):
        rows = fetch_guildstats_exp_changes("Elder Aegir", light_only=True)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["exp_change_int"], 5197)
        self.assertEqual(rows[1]["exp_change_int"], 19129284)
        self.assertRegex(rows[0]["date"], r"^\d{4}-03-22$")
        self.assertRegex(rows[1]["date"], r"^\d{4}-03-23$")

CLIPPED_SECTION_ZERO_HTML = """
<html>
  <body>
    <div>Character History Experience Time online Highscore Deaths</div>
    <div>03-17 +19,498,268 554 (+1) 1,500,000,000 1h</div>
    <div>03-18 +31 554 1,500,000,031 0</div>
    <div>03-19 +5,231,733 555 (+1) 1,505,231,764 2h</div>
    <div>03-20 0 555 1,505,231,764 0</div>
    <div>03-21 0 555 1,505,231,764 0</div>
    <div>03-22 +5,197 555 1,505,236,961 0</div>
    <div>03-23 +19,129,284 556 (+1) 1,524,366,245 0</div>
    <div>Average daily exp</div>
    <div>03-24 0 556 1,524,366,245 0</div>
    <div>03-25 0 556 1,524,366,245 0</div>
    <div>Total in month +434,905,872</div>
  </body>
</html>
"""


class GuildStatsFlatTextCandidateSelectionTests(unittest.TestCase):
    @patch("integrations.tibiadata._fetch_guildstats_exp_html", return_value=CLIPPED_SECTION_ZERO_HTML)
    def test_prefers_full_flattened_text_when_section_slice_loses_earlier_rows(self, _mock_fetch_html):
        rows = fetch_guildstats_exp_changes("Monk Curandeiro", light_only=True)
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
                {"date": "2026-03-24", "exp_change": "0", "exp_change_int": 0},
                {"date": "2026-03-25", "exp_change": "0", "exp_change_int": 0},
            ],
        )


BASE_PAGE_TEASER_EXP_HTML = """
<html>
  <body>
    <div>Character History Experience Time online Highscore Deaths</div>
    <div>Date Exp change Vocation rank Lvl Experience Time on-line Avg exp per hour</div>
    <div>03-21 0 555 555 1,505,231,764 0</div>
    <div>03-22 +5,197 555 555 1,505,236,961 0</div>
    <div>03-23 +19,129,284 556 (+1) 556 1,524,366,245 0</div>
  </body>
</html>
"""

FULL_EXP_TAB_HTML = """
<html>
  <body>
    <table class="exp-history">
      <tr><th>Date</th><th>Exp change</th><th>Vocation rank</th><th>Lvl</th><th>Experience</th></tr>
      <tr><td data-sort="2026-03-17">03-17</td><td data-sort="19498268">+19,498,268</td><td>554 (+1)</td><td>554</td><td>1,500,000,000</td></tr>
      <tr><td data-sort="2026-03-18">03-18</td><td data-sort="31">+31</td><td>554</td><td>554</td><td>1,500,000,031</td></tr>
      <tr><td data-sort="2026-03-19">03-19</td><td data-sort="5231733">+5,231,733</td><td>555 (+1)</td><td>555</td><td>1,505,231,764</td></tr>
      <tr><td data-sort="2026-03-20">03-20</td><td data-sort="0">0</td><td>555</td><td>555</td><td>1,505,231,764</td></tr>
      <tr><td data-sort="2026-03-21">03-21</td><td data-sort="0">0</td><td>555</td><td>555</td><td>1,505,231,764</td></tr>
      <tr><td data-sort="2026-03-22">03-22</td><td data-sort="5197">+5,197</td><td>555</td><td>555</td><td>1,505,236,961</td></tr>
      <tr><td data-sort="2026-03-23">03-23</td><td data-sort="19129284">+19,129,284</td><td>556 (+1)</td><td>556</td><td>1,524,366,245</td></tr>
    </table>
  </body>
</html>
"""


class GuildStatsBaseTeaserFallbackOrderingTests(unittest.TestCase):
    @patch("integrations.tibiadata._new_browser_session")
    @patch("integrations.tibiadata._session_get_text")
    def test_fetch_exp_html_tries_tab_urls_before_base_html_teaser(self, mock_session_get, mock_new_session):
        fake_session = object()
        mock_new_session.return_value = fake_session

        calls = []

        def side_effect(session, url, timeout, headers=None):
            self.assertIs(session, fake_session)
            calls.append(url)
            if "tab=9" in url:
                return FULL_EXP_TAB_HTML
            return BASE_PAGE_TEASER_EXP_HTML

        mock_session_get.side_effect = side_effect

        html = _fetch_guildstats_exp_html("Monk Curandeiro", timeout=12)
        plain = _html_to_plain_text(html)

        self.assertTrue(any("tab=9" in url for url in calls))
        self.assertIn("03-17", plain)
        self.assertIn("+19,498,268", plain)
