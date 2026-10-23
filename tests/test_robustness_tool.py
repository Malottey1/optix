"""tools/robustness.py runs: its full-league job on a tiny (small) league, end to end, and the
Verifier-case mapping. It was broken for a while by a removed test helper; this keeps it working."""
import json
from pathlib import Path

import tools.robustness as R
from data_gen.generate import main as small_main


def test_verifier_counts_mapping():
    cases = {"claim|shot_spam|true|1": 3, "claim|shot_spam|below_detection|1": 1, "claim|shot_spam|true|0": 2,
             "claim|shot_spam|non_trap|1": 5, "pipeline|shot_spam|true|1": 9, "field_tilt_false_positive": 4,
             "player|wide_forward_passes|1|1": 1, "player|wide_forward_passes|0|0": 7}
    assert R.verifier_counts(cases) == {"shot_spam|1|1": 4, "shot_spam|1|0": 2, "shot_spam|0|1": 5,
                                        "wide_forward_passes|1|1": 1, "wide_forward_passes|0|0": 7}


def test_full_job_and_report_on_a_tiny_league(monkeypatch):
    def tiny(seed, out):
        out = Path(out)
        small_main(seed, out, out.parent / "showcase_unused")
        gt = json.loads((out / "ground_truth.json").read_text())
        gt.setdefault("team_traps", {})          # the small league plants no team traps
        return gt
    monkeypatch.setattr(R, "main_full", tiny)
    full = R._full_job(2026)
    assert full["verifier"] and all(k.count("|") == 2 for k in full["verifier"])
    assert sum(full["verifier"].values()) > 0 and full["recovery"]["volume_passer"]
    text = "\n".join(R._pooled_table([full]))
    assert "| shot_spam |" in text and "| wide_forward_passes | 1 | 1.00 |" in text
