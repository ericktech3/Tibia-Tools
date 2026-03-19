import unittest

from integrations.tibiastalker import extract_stalker_candidates


class TibiaStalkerIntegrationTests(unittest.TestCase):
    def test_extract_candidates_from_scores_shape(self):
        payload = {
            "characterName": "Suspect One",
            "scores": [
                {"characterName": "Enemy Main", "score": 98, "world": "Antica"},
                {"characterName": "Enemy Alt", "score": 77.5},
                {"characterName": "Suspect One", "score": 99},
            ],
        }
        rows = extract_stalker_candidates(payload, target_name="Suspect One")
        self.assertEqual([r["name"] for r in rows], ["Enemy Main", "Enemy Alt"])
        self.assertEqual(rows[0]["score_text"], "98")
        self.assertEqual(rows[0]["chance_text"], "98%")
        self.assertEqual(rows[1]["score_text"], "77.5")
        self.assertEqual(rows[1]["chance_text"], "77.5%")

    def test_extract_candidates_from_nested_possible_characters(self):
        payload = {
            "data": {
                "possibleOtherCharacters": [
                    {"name": "Knight Main", "probability": "64.2", "vocation": "Knight", "level": 500},
                    {"name": "Mage Alt", "probability": "55"},
                ]
            }
        }
        rows = extract_stalker_candidates(payload, target_name="")
        self.assertEqual(rows[0]["name"], "Knight Main")
        self.assertEqual(rows[0]["level"], 500)
        self.assertEqual(rows[0]["vocation"], "Knight")

    def test_extract_candidates_deduplicates_by_highest_score(self):
        payload = {
            "scores": [
                {"name": "Dup Char", "score": 10},
                {"name": "Dup Char", "score": 20},
                {"name": "Other", "score": 15},
            ]
        }
        rows = extract_stalker_candidates(payload)
        self.assertEqual(rows[0]["name"], "Dup Char")
        self.assertEqual(rows[0]["score"], 20)


    def test_extract_candidates_supports_fractional_probability_and_alt_key_names(self):
        payload = {
            "results": [
                {"characterName": "Fraction Main", "chancePercentage": 0.642},
                {"characterName": "Alt Key", "matchProbabilityPercent": "88.2"},
            ]
        }
        rows = extract_stalker_candidates(payload)
        self.assertEqual(rows[0]["name"], "Alt Key")
        self.assertEqual(rows[0]["chance_text"], "88.2%")
        self.assertEqual(rows[1]["name"], "Fraction Main")
        self.assertEqual(rows[1]["chance_text"], "64.2%")

    def test_extract_candidates_from_real_tibiastalker_shape(self):
        payload = {
            "name": "Bobeek",
            "world": "Bonel",
            "correlations": [
                {
                    "otherCharacterName": "lidera bobek",
                    "numberOfMatches": 66,
                    "First match date": "2022-12-06",
                    "Last match date": "2023-04-06",
                },
                {
                    "otherCharacterName": "bobek",
                    "numberOfMatches": 23,
                    "First match date": "2022-12-06",
                    "Last match date": "2023-04-10",
                },
            ],
        }
        rows = extract_stalker_candidates(payload, target_name="Bobeek")
        self.assertEqual(rows[0]["name"], "lidera bobek")
        self.assertEqual(rows[0]["matches_count"], 66)
        self.assertEqual(rows[0]["matches_text"], "66 correlações")
        self.assertEqual(rows[0]["last_match_date"], "2023-04-06")


class TibiaStalkerCalibratedScoreTests(unittest.TestCase):
    def test_real_api_shape_produces_calibrated_score_bands(self):
        payload = {
            "name": "Monk Curandeiro",
            "correlations": [
                {"otherCharacterName": "Kina do Erick", "numberOfMatches": 15, "firstMatchDateOnly": "2025-10-30", "lastMatchDateOnly": "2026-03-01"},
                {"otherCharacterName": "Poke Nontabaia", "numberOfMatches": 3, "firstMatchDateOnly": "2026-02-26", "lastMatchDateOnly": "2026-02-26"},
                {"otherCharacterName": "Absolutx", "numberOfMatches": 3, "firstMatchDateOnly": "2025-04-30", "lastMatchDateOnly": "2025-04-30"},
                {"otherCharacterName": "Norte Vini Norte", "numberOfMatches": 2, "firstMatchDateOnly": "2026-02-28", "lastMatchDateOnly": "2026-02-28"},
            ]
        }
        rows = extract_stalker_candidates(payload, target_name="Monk Curandeiro")
        by_name = {row["name"]: row for row in rows}
        self.assertEqual(by_name["Kina do Erick"]["display_percent_text"], "83%")
        self.assertEqual(by_name["Kina do Erick"]["confidence_label"], "VERY HIGH")
        self.assertEqual(by_name["Poke Nontabaia"]["display_percent_text"], "26%")
        self.assertEqual(by_name["Poke Nontabaia"]["confidence_label"], "MEDIUM")
        self.assertEqual(by_name["Absolutx"]["display_percent_text"], "22%")
        self.assertEqual(by_name["Norte Vini Norte"]["confidence_label"], "LOW")


if __name__ == "__main__":
    unittest.main()


class TibiaStalkerEstimatedIndexTests(unittest.TestCase):
    def test_real_shape_computes_estimated_index_from_matches_and_recency(self):
        payload = {
            "name": "Bobeek",
            "world": "Bonel",
            "correlations": [
                {
                    "otherCharacterName": "lidera bobek",
                    "numberOfMatches": 66,
                    "First match date": "2022-12-06",
                    "Last match date": "2023-04-06",
                },
                {
                    "otherCharacterName": "bobek",
                    "numberOfMatches": 23,
                    "First match date": "2022-12-06",
                    "Last match date": "2023-04-10",
                },
            ],
        }
        rows = extract_stalker_candidates(payload, target_name="Bobeek")
        self.assertEqual(rows[0]["name"], "lidera bobek")
        self.assertEqual(rows[0]["estimated_index_text"], "99%")
        self.assertTrue(rows[1]["estimated_index"] < rows[0]["estimated_index"])
        self.assertTrue(rows[1]["estimated_index_text"].endswith("%"))

    def test_official_scores_also_get_estimated_index_proxy_text(self):
        payload = {
            "scores": [
                {"name": "High", "score": 80},
                {"name": "Low", "score": 40},
            ]
        }
        rows = extract_stalker_candidates(payload)
        self.assertEqual(rows[0]["estimated_index_text"], "99%")
        self.assertEqual(rows[1]["estimated_index_text"], "50%")
        self.assertTrue(rows[0]["estimated_index_is_official_proxy"])
