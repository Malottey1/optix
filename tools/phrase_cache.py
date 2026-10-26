"""Fill the phrasing cache for the showcase match with the live Azure OpenAI deployment.

    python -m tools.phrase_cache --max-calls 60      # live: one call per claim (en, es, fr together)
    python -m tools.phrase_cache --replay            # offline: cache only, zero calls

One model call per published showcase claim, serial, at most MAX_CALLS (60), in demo priority:
the Fan view's top cards, then revised claims, then pattern cards, then stream order. Every reply
goes through agents/output_guard.py; only accepted sentences are cached (agents.phraser), rejected
ones fall back to the template and are listed. The committed UI data (web/public/data) stays
template-based: this tool reads it and writes only data/phrasing-cache and its --out report.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from agents.config import load_env

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "web" / "public" / "data"
LANGS = ("en", "es", "fr")
MAX_CALLS = 60


def showcase_claims() -> list:
    """The published claim behind each showcase insight, in demo priority order."""
    from engine.personalize import personalize
    stream = [json.loads(x) for x in (DATA / "insights.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    attempts = [json.loads(x) for x in (DATA / "claims.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    by_id = {a["claim"]["claim_id"]: a for a in attempts}
    revised = {a["claim"]["claim_id"] for a in attempts if a.get("revision_of")}
    fan = [i["insight_id"] for i in personalize(stream, {"mode": "fan"})]
    rank = lambda i: (i["insight_id"] not in fan, fan.index(i["insight_id"]) if i["insight_id"] in fan else 0,
                      i["claim_id"] not in revised, i["insight_type"] != "tactical_pattern", i["clock"]["start_sec"])
    out, seen = [], set()
    for i in sorted(stream, key=rank):
        if i["claim_id"] in by_id and i["claim_id"] not in seen:
            seen.add(i["claim_id"])
            out.append(by_id[i["claim_id"]]["claim"])
    return out


def phrase_all(phraser, claims) -> dict:
    from agents.narrative import NarrativeAgent
    agent = NarrativeAgent(lambda *a, **k: None, LANGS, phraser)
    out = {}
    for c in claims:
        text = agent.write(c)
        res = agent.last_phrase
        out[c["claim_id"]] = dict(template_key=c["template_key"], source=res.source, rejected=res.guard_rejected,
                                  rendered={l: text.rendered[l]["casual"] for l in LANGS})
    return out


def make_phraser(live: bool, max_calls: int):
    from agents.phraser import AzureChatClient, AzureOpenAIPhraser, PhrasingCache, configured_model, known_entities
    from engine.tables import load
    known, names = known_entities(load(ROOT / "data" / "showcase"))
    if live:
        client = AzureChatClient()
        return AzureOpenAIPhraser(client, known, names, cache=PhrasingCache(), max_calls=max_calls), client
    return AzureOpenAIPhraser(None, known, names, cache=PhrasingCache(), offline=True, model=configured_model()), None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max-calls", type=int, default=MAX_CALLS)
    ap.add_argument("--first", type=int, default=None, help="only the first N claims in priority order")
    ap.add_argument("--replay", action="store_true", help="offline: cached sentences only, no call")
    ap.add_argument("--out", type=Path, required=True, help="JSON report (keep it outside web/public/data)")
    a = ap.parse_args(argv)
    load_env()
    claims = showcase_claims()[: a.first]
    phraser, client = make_phraser(not a.replay, min(a.max_calls, MAX_CALLS))
    rows = phrase_all(phraser, claims)
    rep = dict(claims=len(claims), calls=phraser.calls, tokens=getattr(client, "tokens", None),
               accepted=sum(v in ("model", "cache") for r in rows.values() for v in r["source"].values()),
               rejected=[dict(claim_id=c, lang=l, text=t, problems=p) for c, l, t, p in phraser.rejected],
               rows=rows)
    a.out.write_text(json.dumps(rep, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    print(f"claims {rep['claims']}, calls {rep['calls']}, accepted sentences {rep['accepted']}, "
          f"rejected model sentences {len(rep['rejected'])}, tokens {rep['tokens']}")
    return rep


if __name__ == "__main__":
    main()
