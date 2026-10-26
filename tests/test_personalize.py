"""engine.personalize: the shared config, golden cases (shared with web/src/lib/personalize.test.ts),
and the guarantees: same objects and numbers in and out, determinism, empty profile = the stream.
Also the showcase's compact event file (agents/showcase_events.py) and the "Player so far" golden
counts, recomputed here straight from data/showcase."""
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from agents import showcase_events
from engine.personalize import CONFIG, personalize, personalize_fixtures
from tools import personalize_golden as G

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
GOLDEN = json.loads((FIX / "personalize_golden.json").read_text(encoding="utf-8"))
SO_FAR = json.loads((FIX / "player_so_far_golden.json").read_text(encoding="utf-8"))
STREAM = [json.loads(x) for x in (ROOT / "out" / "insights.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def test_config_conforms_to_its_schema_and_names_real_icons_and_keys():
    schema = json.loads((ROOT / "contracts" / "personalization.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    assert not list(Draft202012Validator(schema).iter_errors(CONFIG))
    icons = (ROOT / "web" / "src" / "icons" / "names.ts").read_text()
    i18n = (ROOT / "web" / "src" / "lib" / "i18n-final.ts").read_text()
    for m in CONFIG["metrics"].values():
        assert f'"{m["icon"]}"' in icons
    for key in CONFIG["glossary"].values():
        assert i18n.count(f"  {key}:") == 3, key                 # en, es, fr
    assert CONFIG["modes"]["fan"]["max_cards"] == 5 and CONFIG["modes"]["analyst"]["max_cards"] is None
    assert not set(CONFIG["metrics"]) & set(CONFIG["not_offered"])


def test_every_offered_metric_has_a_series_in_the_data():
    ui = json.loads((ROOT / "web" / "public" / "data" / "ui.json").read_text())
    tl = json.loads((ROOT / "web" / "public" / "data" / "timeline.json").read_text())
    final = json.loads((ROOT / "web" / "public" / "data" / "matches" / "m_001.json").read_text())
    src = {"timeline.momentum": tl["momentum"], "ui.visuals.shots": ui["visuals"]["shots"],
           "ui.visuals.rhythm": ui["visuals"]["rhythm"], "ui.visuals.stress": ui["visuals"]["stress"]}
    for name, m in CONFIG["metrics"].items():
        assert src[m["series"]], name
        assert m["final"] == (m["series"] == "timeline.momentum")
    assert final["momentum"]                                       # the one series a played match carries
    types = {i["insight_type"] for i in STREAM}
    assert all(set(m["families"]) & types for m in CONFIG["metrics"].values())


def test_golden_fixture_is_current():
    golden, so_far = G.build()
    assert golden == GOLDEN, "rerun python -m tools.personalize_golden"
    assert so_far == SO_FAR, "rerun python -m tools.personalize_golden"


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda c: json.dumps(c["profile"], sort_keys=True))
def test_golden_cases(case):
    out = personalize(GOLDEN["stream"], case["profile"], GOLDEN["involved"])
    assert [i["insight_id"] for i in out] == case["ids"]


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda c: json.dumps(c["profile"], sort_keys=True))
def test_same_objects_and_numbers_in_and_out_and_deterministic(case):
    before = copy.deepcopy(STREAM)
    out = personalize(STREAM, case["profile"], GOLDEN["involved"])
    assert STREAM == before                                         # input untouched
    ids = {id(i) for i in STREAM}
    assert all(id(i) in ids for i in out)                           # the very same claim objects
    assert len({i["insight_id"] for i in out}) == len(out)
    assert out == personalize(copy.deepcopy(STREAM), case["profile"], GOLDEN["involved"])
    assert [i["insight_id"] for i in out] == case["ids"]


def test_empty_profile_and_plain_analyst_are_the_unpersonalized_stream():
    assert personalize(STREAM, {}) == STREAM
    assert personalize(STREAM, None) == STREAM
    assert personalize(STREAM, {"mode": "analyst", "language": "fr"}) == STREAM


def test_fan_caps_at_five_and_clubs_come_first():
    fan = personalize(STREAM, {"mode": "fan", "clubs": ["NTG"]})
    assert len(fan) == 5 and all(i["teams"]["primary"] == "NTG" for i in fan)
    rows = [{"id": "a", "home": "AUR", "away": "CAL"}, {"id": "b", "home": "HAR", "away": "NTG"}]
    assert [f["id"] for f in personalize_fixtures(rows, ["NTG"])] == ["b", "a"]
    assert personalize_fixtures(rows, []) == rows


def test_showcase_event_file_copies_the_events():
    f = showcase_events.build(ROOT / "data" / "showcase")
    committed = json.loads((ROOT / "web" / "public" / "data" / "matches" / "events-m_showcase.json").read_text())
    assert f == committed, "rerun python -m agents.showcase_events and npm run data"
    rows = G._csv("events.csv")
    assert len(f["rows"]) == len(rows)
    c = f["cols"]
    by_n = {r[c.index("n")]: r for r in f["rows"]}
    for e in rows:
        r = by_n[int(e["event_id"].rsplit("_e", 1)[1])]
        assert r[c.index("clock_sec")] == int(e["clock_sec"])
        assert f["types"][r[c.index("type")]] == e["event_type"]
        assert (f["players"][r[c.index("player")]] if r[c.index("player")] is not None else "") == e["player_id"]
        assert all(isinstance(v, int) or v is None for v in r)


@pytest.mark.parametrize("case", SO_FAR["cases"], ids=lambda c: f'{c["player"]}@{c["clock"]}')
def test_player_so_far_counts_recomputed_from_the_csvs(case):
    """Independent recount (shots.csv xG, passes.csv key passes) against the exported event rows."""
    f = showcase_events.build(ROOT / "data" / "showcase")
    c, t = f["cols"], case["clock"]
    pi = f["players"].index(case["player"])
    mine = [r for r in f["rows"] if r[c.index("player")] == pi and r[c.index("clock_sec")] <= t]
    ty = lambda r: f["types"][r[c.index("type")]]
    assert case["counts"]["passes"] == sum(ty(r) == "pass" for r in mine)
    assert case["counts"]["shots"] == sum(ty(r) == "shot" for r in mine)
    assert case["counts"]["key_passes"] == sum(r[c.index("key")] for r in mine)
    assert case["counts"]["cards"] == sum(ty(r) == "card" for r in mine)
    assert case["counts"]["subs"] == sum(ty(r) == "substitution" and pi in (r[c.index("player")], r[c.index("related")])
                                         for r in f["rows"] if r[c.index("clock_sec")] <= t)
    ui = json.loads((ROOT / "web" / "public" / "data" / "ui.json").read_text())
    xg = sum(s[6] for s in ui["visuals"]["shots"] if s[3] == case["player"] and s[1] <= t)
    assert round(xg, 2) == case["counts"]["xg"]
