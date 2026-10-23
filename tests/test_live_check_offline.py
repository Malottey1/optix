"""tools/azure_live_check without Azure settings: it reports "not run" and makes no call."""
from tools import azure_live_check as L


def test_not_configured_writes_a_not_run_report(tmp_path, monkeypatch):
    for k in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(L, "load_env", lambda: [])
    monkeypatch.setattr(L, "run_live", lambda *a: (_ for _ in ()).throw(AssertionError("must not call")))
    out = tmp_path / "r.md"
    assert L.main(["--out", str(out)]) is None
    text = out.read_text()
    assert "Not run: no Azure configuration present" in text and "az login" in text
    assert "AZURE_OPENAI_ENDPOINT and/or AZURE_OPENAI_DEPLOYMENT not set" in text


def test_the_live_report_names_no_secret():
    r = dict(deployment="dep", auth="entra-id", calls=2, spans=[{}],
             rows=[dict(claim_id="c", template_key="k", source={l: "model" for l in L.LANGS}, guard_rejected={},
                        number_guard_passed=True, casual={l: "s" for l in L.LANGS})])
    text = L.report(r, [])
    assert "2 model calls (cap 10)" in text
    assert not any(x in text for x in ("api_key=", "Bearer ", "AccountKey", "openai.azure.com", "InstrumentationKey="))


def test_live_claims_come_from_the_verified_replay():
    cs = L._claims()
    assert 0 < len(cs) <= 3 and all(c["verification"]["status"].startswith("published") for c in cs)
