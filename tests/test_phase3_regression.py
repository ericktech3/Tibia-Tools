"""Testes de regressão da Fase 3: bosses, boosted e resultado padrão."""
import unittest
from unittest import mock

import requests

from core import result as R
from core.boosted import fetch_boosted, fetch_boosted_result, parse_boosted
from features.bosses import logic as L
from integrations import exevopan
from integrations.parsers.exevopan_parser import parse_bosses

SAMPLE_HTML = (
    "<html><body><div>Ghazbaran</div><div>No chance</div><div>Expected in: 6 days</div>"
    "<div>Ferumbras</div><div>12.5%</div>"
    "<div>Orshabaal</div><div>Sem chance</div><div>Aparecerá em: 1 dia</div></body></html>"
)


def _resp(text="", status=200, json_data=None):
    r = requests.Response()
    r.status_code = status
    r._content = text.encode("utf-8") if json_data is None else __import__("json").dumps(json_data).encode()
    r.encoding = "utf-8"
    return r


class ResultTests(unittest.TestCase):
    def test_classify_errors(self):
        self.assertEqual(R.classify_exception(requests.ConnectionError()), R.OFFLINE)
        self.assertEqual(R.classify_exception(requests.Timeout()), R.TIMEOUT)
        err = requests.HTTPError(response=_resp(status=404))
        self.assertEqual(R.classify_exception(err), R.NOT_FOUND)
        self.assertEqual(R.classify_exception(ValueError()), R.SITE_ERROR)

    def test_messages_are_friendly(self):
        msg = R.Result.failure(R.OFFLINE).user_message()
        self.assertIn("internet", msg)
        self.assertNotIn("Traceback", msg)

    def test_run_safely_never_raises(self):
        def boom():
            raise requests.ConnectionError("x")
        res = R.run_safely(boom)
        self.assertFalse(res.ok)
        self.assertEqual(res.kind, R.OFFLINE)

    def test_format_age(self):
        self.assertEqual(R.format_age(10), "agora")
        self.assertEqual(R.format_age(300), "há 5 min")
        self.assertEqual(R.format_age(7200), "há 2 h")
        self.assertEqual(R.format_age(3 * 86400), "há 3 dia(s)")


class BossParserTests(unittest.TestCase):
    def test_parses_names_chances_and_expected_days(self):
        bosses = {b["boss"]: b for b in parse_bosses(SAMPLE_HTML)}
        self.assertEqual(bosses["Ghazbaran"]["status"], "Expected in: 6 days")
        self.assertEqual(bosses["Ferumbras"]["chance"], "12.5%")
        self.assertEqual(bosses["Ferumbras"]["status"], "")  # não herda do vizinho
        self.assertEqual(bosses["Orshabaal"]["status"], "Expected in: 1 day")

    def test_empty_html(self):
        self.assertEqual(parse_bosses(""), [])


class BossFetchTests(unittest.TestCase):
    def test_success(self):
        with mock.patch.object(exevopan.requests, "get", return_value=_resp(SAMPLE_HTML)):
            res = exevopan.fetch_exevopan_result("Antica")
        self.assertTrue(res.ok)
        self.assertEqual(len(res.data), 3)

    def test_offline_is_explained(self):
        with mock.patch.object(exevopan.requests, "get", side_effect=requests.ConnectionError()):
            res = exevopan.fetch_exevopan_result("Antica")
            self.assertEqual(exevopan.fetch_exevopan_bosses("Antica"), [])  # compatível
        self.assertEqual(res.kind, R.OFFLINE)

    def test_site_down(self):
        with mock.patch.object(exevopan.requests, "get", return_value=_resp("x", status=403)):
            res = exevopan.fetch_exevopan_result("Antica")
        self.assertEqual(res.kind, R.SITE_ERROR)

    def test_page_without_bosses(self):
        with mock.patch.object(exevopan.requests, "get", return_value=_resp("<html>nada</html>")):
            res = exevopan.fetch_exevopan_result("MundoInventado")
        self.assertEqual(res.kind, R.EMPTY)

    def test_empty_world(self):
        self.assertEqual(exevopan.fetch_exevopan_result("  ").kind, R.INVALID_INPUT)


class BossLogicTests(unittest.TestCase):
    BOSSES = [
        {"boss": "Ghazbaran", "chance": "No chance", "status": "Expected in: 6 days"},
        {"boss": "Ferumbras", "chance": "12.5%"},
        {"boss": "Morgaroth", "chance": "High chance"},
        {"boss": "Zulazza", "chance": "Unknown"},
        "lixo",
    ]

    def test_chance_score(self):
        self.assertEqual(L.chance_score("12,5%"), 12.5)
        self.assertEqual(L.chance_score("High chance"), 75.0)
        self.assertEqual(L.chance_score("Sem chance"), 0.0)
        self.assertEqual(L.chance_score(""), 0.0)

    def test_sort_by_chance_default(self):
        names = [L.boss_name(b) for b in L.filter_and_sort(self.BOSSES)]
        self.assertEqual(names[0], "Morgaroth")
        self.assertEqual(len(names), 4)  # ignora item inválido

    def test_filters(self):
        f = lambda flt: [L.boss_name(b) for b in L.filter_and_sort(self.BOSSES, chance_filter=flt)]
        self.assertEqual(f("High"), ["Morgaroth"])
        self.assertEqual(f("No chance"), ["Ghazbaran"])
        self.assertEqual(f("Unknown"), ["Zulazza"])
        self.assertEqual(sorted(f("Low+")), ["Ferumbras", "Morgaroth"])

    def test_search_and_favorites(self):
        res = L.filter_and_sort(self.BOSSES, query="ghaz")
        self.assertEqual([L.boss_name(b) for b in res], ["Ghazbaran"])
        res = L.filter_and_sort(self.BOSSES, favorites=["Zulazza"], fav_only=True)
        self.assertEqual([L.boss_name(b) for b in res], ["Zulazza"])
        res = L.filter_and_sort(self.BOSSES, favorites=["Zulazza"], sort="Favorites first")
        self.assertEqual(L.boss_name(res[0]), "Zulazza")

    def test_secondary_text_shows_days(self):
        self.assertEqual(L.secondary_text(self.BOSSES[0]), "No chance • Expected in: 6 days")


class BoostedTests(unittest.TestCase):
    C = {"creatures": {"boosted": {"name": "Dragon", "image_url": ""}}}
    B = {"boostable_bosses": {"boosted": {"name": "Ghazbaran", "image_url": ""}}}

    def test_parse(self):
        d = parse_boosted(self.C, self.B)
        self.assertEqual((d["creature"], d["boss"]), ("Dragon", "Ghazbaran"))

    def test_parse_changed_format(self):
        with self.assertRaises(ValueError):
            parse_boosted({}, {})

    def test_fetch_success_and_offline(self):
        def fake(url, **kw):
            return _resp(json_data=self.C if "creatures" in url else self.B)
        with mock.patch("core.boosted.requests.get", side_effect=fake):
            res = fetch_boosted_result()
        self.assertTrue(res.ok)
        self.assertEqual(res.data["boss"], "Ghazbaran")
        with mock.patch("core.boosted.requests.get", side_effect=requests.ConnectionError()):
            res = fetch_boosted_result()
            self.assertEqual(res.kind, R.OFFLINE)
            self.assertIsNone(fetch_boosted())


if __name__ == "__main__":
    unittest.main()
