"""The pooled recall checks of tests/test_verifier_full.py on fixed counts (fast): the interval
floor used for claim-level shot_spam still fails a clearly degraded rule."""
from test_verifier_full import pooled_floor_check


def test_interval_floor_passes_the_measured_pool_and_reports_the_point_estimate():
    ok, msg = pooled_floor_check("claim", "shot_spam", 68, 86)
    assert ok
    assert "68/86 = 0.79 [0.69-0.86]" in msg


def test_interval_floor_fails_a_degraded_rule_with_half_the_true_cases_missed():
    # the same pool with half of the 68 hits flipped to misses: 34/86
    ok, msg = pooled_floor_check("claim", "shot_spam", 68 - 34, 86)
    assert not ok, msg
    assert "34/86 = 0.40" in msg


def test_point_floors_are_unchanged_for_the_other_rules_and_levels():
    assert not pooled_floor_check("pipeline", "shot_spam", 69, 86)[0]      # 0.80 < 0.81 point floor
    assert pooled_floor_check("pipeline", "shot_spam", 71, 86)[0]          # 0.83, as measured
    assert not pooled_floor_check("claim", "field_tilt_with_lead", 40, 139)[0]
