"""Audit log: hash chain, tamper evidence and the verify command."""
import json

from agents.audit import AuditLog, main, verify


def _log(tmp_path, n=5):
    p = tmp_path / "audit.jsonl"
    log = AuditLog(p, clock=lambda: "2026-01-01T00:00:00.000+00:00")
    for i in range(n):
        log.append("published", {"claim_id": f"c{i}", "status": "published"})
    return p


def test_an_untouched_chain_verifies(tmp_path, capsys):
    p = _log(tmp_path)
    assert verify(p) == []
    assert main(["verify", str(p)]) == 0
    assert "chain intact, 5 records" in capsys.readouterr().out


def test_reopening_appends_to_the_same_chain(tmp_path):
    p = _log(tmp_path, 3)
    AuditLog(p).append("published", {"claim_id": "c3"})
    assert verify(p) == [] and len(p.read_text().splitlines()) == 4


def test_altering_one_record_breaks_verification(tmp_path, capsys):
    p = _log(tmp_path)
    lines = p.read_text().splitlines()
    rec = json.loads(lines[2])
    rec["data"]["status"] = "blocked"
    lines[2] = json.dumps(rec, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")
    assert any("line 3" in x for x in verify(p))
    assert main(["verify", str(p)]) == 1
    assert "BROKEN" in capsys.readouterr().out


def test_rehashing_an_altered_record_still_breaks_the_next_link(tmp_path):
    from agents.audit import _digest
    p = _log(tmp_path)
    lines = p.read_text().splitlines()
    rec = json.loads(lines[1])
    rec["data"]["claim_id"] = "forged"
    rec["hash"] = _digest(rec)
    lines[1] = json.dumps(rec, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")
    assert any("line 3: prev" in x for x in verify(p))


def test_deleting_or_reordering_is_detected(tmp_path):
    p = _log(tmp_path)
    lines = p.read_text().splitlines()
    p.write_text("\n".join(lines[:2] + lines[3:]) + "\n")
    assert verify(p)
    p2 = _log(tmp_path / "b")
    l2 = p2.read_text().splitlines()
    l2[1], l2[2] = l2[2], l2[1]
    p2.write_text("\n".join(l2) + "\n")
    assert verify(p2)


def test_env_loader_sets_only_missing_names_and_returns_no_values(tmp_path, monkeypatch):
    from agents.config import load_env
    f = tmp_path / ".env"
    f.write_text("# comment\nOPTIX_TEST_A=1\nexport OPTIX_TEST_B='two'\nOPTIX_TEST_C=\n")
    monkeypatch.setenv("OPTIX_TEST_A", "kept")
    monkeypatch.delenv("OPTIX_TEST_B", raising=False)
    names = load_env(f)
    import os
    assert names == ["OPTIX_TEST_B"] and os.environ["OPTIX_TEST_B"] == "two" and os.environ["OPTIX_TEST_A"] == "kept"
    monkeypatch.delenv("OPTIX_TEST_B")


def test_stream_audit_log_has_one_record_per_insight(tmp_path):
    from agents.stream import InsightStream
    from data_gen.generate import main as generate
    from engine.tables import load
    generate(2026, tmp_path / "season", tmp_path / "showcase")
    ds = load(tmp_path / "showcase", baseline="season", season_dir=tmp_path / "season")
    s = InsightStream(ds, "m_showcase", audit=AuditLog(tmp_path / "audit.jsonl"))
    s.run()
    recs = [json.loads(l) for l in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert [r["data"]["claim_id"] for r in recs] == [i["claim_id"] for i in s.insights]
    assert verify(tmp_path / "audit.jsonl") == []
