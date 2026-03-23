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
