import unittest

from integrations.tibiastalker import extract_stalker_candidates


class TibiaStalkerUiFieldsTests(unittest.TestCase):
    def test_high_medium_low_confidence_labels_from_scores(self):
        payload = {
            'possibleCharacters': [
                {'name': 'High', 'score': 98},
                {'name': 'Medium', 'score': 62},
                {'name': 'Low', 'score': 18},
            ]
        }
        rows = extract_stalker_candidates(payload, target_name='Target')
        labels = {row['name']: row.get('confidence_label') for row in rows}
        self.assertEqual(labels['High'], 'VERY HIGH')
        self.assertEqual(labels['Medium'], 'MEDIUM')
        self.assertEqual(labels['Low'], 'LOW')

    def test_extract_candidates_adds_display_fields(self):
        payload = {
            'correlations': [
                {
                    'otherCharacterName': 'Foo',
                    'numberOfMatches': 20,
                    'First match date': '2024-01-01',
                    'Last match date': '2024-05-01',
                }
            ]
        }
        rows = extract_stalker_candidates(payload, target_name='Bar')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIn('display_percent', row)
        self.assertIn('display_percent_text', row)
        self.assertIn('confidence_label', row)
        self.assertTrue(row['display_percent'] > 0)
        self.assertTrue(row['display_percent_text'].endswith('%'))
        self.assertIn(row['confidence_label'], {'VERY HIGH', 'MEDIUM', 'LOW'})


if __name__ == '__main__':
    unittest.main()
