"""Translation (after verification) and personalization on the showcase stream."""
import re

import pytest

from agents.narrative import NarrativeAgent, fmt, labels, languages, number_guard, numeric_params, render, templates
from agents.personalization import PersonalizationAgent, UserProfile
from agents.personalize import lines
from agents.stream import InsightStream
from data_gen.generate import main as generate
from engine.claims import build_claim
from engine.tables import load

MID = "m_showcase"
PLACEHOLDER = re.compile(r"\{(\w+)\}")


@pytest.fixture(scope="module")
def stream(tmp_path_factory):
    root = tmp_path_factory.mktemp("translation")
    generate(2026, root / "season", root / "showcase")
    ds = load(root / "showcase", baseline="season", season_dir=root / "season")
    s = InsightStream(ds, MID, languages=("en", "es", "fr"))
    s.run()
    return s, ds


def test_three_languages_with_the_same_templates_and_placeholders():
    assert languages() == ["en", "es", "fr"]
    en = templates("en")
    for lang in ("es", "fr"):
        tr = templates(lang)
        assert set(tr) == set(en), lang
        for key, t in en.items():
            for tone in ("analyst", "casual"):
                assert set(PLACEHOLDER.findall(tr[key][tone])) == set(PLACEHOLDER.findall(t[tone])), (lang, key, tone)
        assert set(labels(lang)["lane"]) == set(labels("en")["lane"])


def test_every_rendered_string_carries_every_numeric_param(stream):
    s, _ = stream
    assert s.insights
    for ins in s.insights:
        text = ins["text"]
        assert text["number_guard_passed"] is True
        assert set(text["rendered"]) == {"en", "es", "fr"}
        for lang, tones in text["rendered"].items():
            for tone, sentence in tones.items():
                assert not number_guard(sentence, text["params"], lang), (ins["insight_id"], lang, tone, sentence)
                for k, v in numeric_params(text["params"]).items():
                    assert fmt(v, lang) in sentence or fmt(abs(v), lang) in sentence, (lang, tone, k, sentence)


def test_decimal_comma_and_translated_labels():
    p = {"team": "NTG", "amount": 1.1, "shots": 19, "xg_per_shot": 0.058}
    assert "0,058" in render("xg.volume_vs_value", p, "es")["analyst"]
    assert "1,1" in render("xg.volume_vs_value", p, "fr")["casual"]
    assert "0.058" in render("xg.volume_vs_value", p, "en")["analyst"]
    m = {"attacker": "AUR", "defender": "NTG", "lane": "left_flank", "attack_share": 38.3, "league_share": 22.9,
         "concede_completion": 81.1, "league_completion": 73.5}
    assert "flanco izquierdo" in render("matchup.weak_flank", m, "es")["analyst"]
    assert "flanc gauche" in render("matchup.weak_flank", m, "fr")["casual"]
    assert "left flank" not in render("matchup.weak_flank", m, "fr")["analyst"]


def test_guard_catches_a_translation_that_changes_a_number():
    p = {"team": "NTG", "amount": 1.1, "shots": 19, "xg_per_shot": 0.058}
    assert number_guard("NTG : 1,1 xG sur 19 tirs, 0,058 xG par tir.", p, "fr") == []
    assert number_guard("NTG : 1,1 xG sur 18 tirs, 0,058 xG par tir.", p, "fr") == \
        ["param shots=19 missing", "number 18 is not a param"]
    # a dot where French writes a comma is a different number string, so it is caught too
    assert "param amount=1,1 missing" in number_guard("NTG : 1.1 xG sur 19 tirs, 0,058 xG par tir.", p, "fr")


def test_translation_only_after_verification(stream):
    s, ds = stream
    view = s.orc.state.view(ds)
    pending = build_claim(view, "xg", "match", {"kind": "team", "id": "t_aur"}, match_id=MID, template_key="xg.stat",
                          param_values=("amount",), extra_params={"team": "AUR"})
    with pytest.raises(ValueError):
        NarrativeAgent(lambda *a, **k: None, ("en", "es", "fr")).write(pending)


# ---------- personalization ----------

def test_analyst_and_casual_differ_but_share_numbers(stream):
    s, _ = stream
    agent = PersonalizationAgent()
    a = agent.select(s.insights, UserProfile(mode="analyst", language="es"))
    c = agent.select(s.insights, UserProfile(mode="casual", language="es"))
    for x, y in zip(a, c):
        assert x["insight_id"] == y["insight_id"] and x["display"]["text"] != y["display"]["text"]
        nums = numeric_params(x["text"]["params"])
        for v in nums.values():
            assert fmt(abs(v), "es") in x["display"]["text"] and fmt(abs(v), "es") in y["display"]["text"]


def test_player_focus_mode(stream):
    s, _ = stream
    out = PersonalizationAgent().select(s.insights, UserProfile(player_focus="NTG_07", mode="analyst"))
    assert out and all(i["player_ids"] == ["NTG_07"] for i in out)
    assert any(i["insight_type"] == "volume_vs_value" for i in out)   # the volume passer's honest stat


def test_single_metric_mode(stream):
    s, _ = stream
    out = PersonalizationAgent().select(s.insights, UserProfile(single_metric="perimeter_lock"))
    assert out and {i["insight_type"] for i in out} == {"perimeter_lock"}
    assert all(i["display"]["context_chip"]["note_key"] == "field_tilt.trailing_vs_deep_block" for i in out)


def test_favorite_club_mode_orders_and_marks(stream):
    s, _ = stream
    out = PersonalizationAgent().select(s.insights, UserProfile(favorite_club="NTG"))
    assert len(out) == len(s.insights)
    assert {i["insight_id"] for i in out if i["display"]["favorite"]} == \
        {i["insight_id"] for i in s.insights if i["teams"]["primary"] == "NTG"}
    for a, b in zip(out, out[1:]):
        if a["clock"]["start_sec"] == b["clock"]["start_sec"]:
            assert a["display"]["favorite"] or not b["display"]["favorite"]


def test_unknown_language_falls_back_to_english(stream):
    s, _ = stream
    out = PersonalizationAgent().select(s.insights[:3], UserProfile(language="de"))
    assert all(i["display"]["language"] == "en" for i in out)


def test_personalize_cli_lines(stream):
    s, _ = stream
    out = lines(s.insights, UserProfile(mode="casual", language="fr", favorite_club="NTG"))
    assert len(out) == len(s.insights) and any("[context:" in x for x in out)
