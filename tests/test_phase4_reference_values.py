"""Fase 4: confere cálculos contra valores de referência (TibiaWiki / Tibia.com)."""
import unittest
from datetime import date

from core.exp_loss import estimate_death_exp_lost, tibia_total_experience_for_level
from core.stamina import compute_offline_regen
from core import training
from features.char import xp_stats as X


class ExperienceReferenceTests(unittest.TestCase):
    def test_total_experience_known_levels(self):
        # TibiaWiki: level 8 = 4.200, level 100 = 15.694.800, level 200 = 129.389.800
        self.assertEqual(tibia_total_experience_for_level(8), 4_200)
        self.assertEqual(tibia_total_experience_for_level(100), 15_694_800)
        self.assertEqual(tibia_total_experience_for_level(200), 129_389_800)
        self.assertEqual(tibia_total_experience_for_level(2000), 132_933_899_800)

    def test_death_penalty_max_level_200(self):
        # ((200+50)/100) * 50 * (200² - 5*200 + 8) = 4.876.000 (sem redução)
        self.assertEqual(estimate_death_exp_lost(200, blessings=0, promoted=False), 4_876_000)
        # 3,7685% da XP total, como na tabela da TibiaWiki
        pct = 4_876_000 / tibia_total_experience_for_level(200) * 100
        self.assertAlmostEqual(pct, 3.7685, places=3)

    def test_death_penalty_with_promotion_and_blessings(self):
        # promoção 30% + 7 blessings x 8% = 86% de redução
        self.assertEqual(estimate_death_exp_lost(200), round(4_876_000 * 0.14))

    def test_low_level_loses_10_percent(self):
        self.assertEqual(
            estimate_death_exp_lost(20, blessings=0, promoted=False),
            round(0.10 * tibia_total_experience_for_level(20)),
        )


class StaminaReferenceTests(unittest.TestCase):
    def test_normal_regen_3_to_1_plus_10min_delay(self):
        r = compute_offline_regen(30 * 60, 31 * 60)
        self.assertEqual(r.regen_offline_only_min, 180)
        self.assertEqual(r.offline_needed_min, 190)

    def test_green_regen_6_to_1(self):
        r = compute_offline_regen(39 * 60, 42 * 60)
        self.assertEqual(r.regen_offline_only_min, 3 * 60 * 6)

    def test_full_regen_from_zero(self):
        r = compute_offline_regen(0, 42 * 60)
        self.assertEqual(r.regen_offline_only_min, 39 * 60 * 3 + 3 * 60 * 6)


class TrainingReferenceTests(unittest.TestCase):
    def test_exercise_weapon_prices(self):
        self.assertEqual(training.WEAPONS["Standard (500)"]["price_gp"], 347_222)
        self.assertEqual(training.WEAPONS["Enhanced (1800)"]["price_gp"], 1_250_000)
        self.assertEqual(training.WEAPONS["Lasting (14400)"]["price_gp"], 10_000_000)

    def test_skill_points_formula(self):
        # Knight, melee: 50 * 1.1^(nivel-10)
        self.assertAlmostEqual(training._points_to_advance("melee", "melee", "knight", 10), 50.0)
        self.assertAlmostEqual(training._points_to_advance("melee", "melee", "knight", 11), 55.0)
        # Sorcerer, magic level: 1600 * 1.1^ml
        self.assertAlmostEqual(training._points_to_advance("magic", "magic", "sorcerer", 1), 1760.0)


class XpHistoryTests(unittest.TestCase):
    ROWS = [{"date": f"2026-03-{d:02d}", "exp_change_int": d * 1_000_000} for d in range(1, 21)]

    def test_7_day_window_is_exactly_7_days(self):
        s = X.summarize_xp(self.ROWS, today=date(2026, 3, 20))
        # dias 14..20 (7 dias) — antes o app somava 8 dias por engano
        self.assertEqual(s["total_7"], sum(range(14, 21)) * 1_000_000)
        self.assertEqual(len(s["daily_7"]), 7)
        self.assertEqual(s["daily_7"][0][0], date(2026, 3, 20))

    def test_best_day_average_and_lag(self):
        s = X.summarize_xp(self.ROWS, today=date(2026, 3, 25))
        self.assertEqual(s["best_date"], date(2026, 3, 20))
        self.assertEqual(s["avg_7"], round(sum(range(14, 21)) * 1_000_000 / 7))
        self.assertEqual(s["lag_days"], 5)
        self.assertTrue(any("atrasado" in l for l in X.summary_lines(s)))

    def test_missing_days_count_as_zero_and_duplicates_sum(self):
        rows = [{"date": "2026-03-10", "exp_change_int": 5}, {"date": "2026-03-10", "exp_change_int": 5},
                {"date": "2026-03-07", "exp_change_int": -3}, {"date": "lixo"}]
        s = X.summarize_xp(rows, today=date(2026, 3, 10))
        self.assertEqual(dict(s["daily_7"])[date(2026, 3, 10)], 10)
        self.assertEqual(dict(s["daily_7"])[date(2026, 3, 9)], 0)
        self.assertEqual(s["total_7"], 7)
        self.assertEqual(s["active_7"], 1)

    def test_empty(self):
        self.assertFalse(X.summarize_xp([])["ok"])
        self.assertEqual(X.summary_lines({"ok": False}), [])

    def test_formatting(self):
        self.assertEqual(X.fmt_signed(1234567), "+1.234.567")
        self.assertEqual(X.fmt_signed(-5), "-5")
        self.assertEqual(X.fmt_compact(12_345_678), "12,3 kk")

    def test_deaths_summary(self):
        deaths = [{"reason": "Killed by a dragon", "exp_lost": "1,234,000"},
                  {"reason": "Killed by a demon", "xp_lost": "500.000"},
                  {"reason": ""}, "lixo"]
        self.assertEqual(X.summarize_deaths(deaths), {"count": 2, "xp_lost": 1_734_000})


if __name__ == "__main__":
    unittest.main()
