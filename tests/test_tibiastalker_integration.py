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


if __name__ == "__main__":
    unittest.main()
