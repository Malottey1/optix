"""Phrasing layer: turns an already-verified claim into sentences. It runs after the Verifier and
never sees an event, only the language-independent claim object.

  TemplatePhraser     the default: fills agents/templates/<lang>.json (exactly the old behaviour).
  AzureOpenAIPhraser  asks a chat model deployed in Azure AI Foundry / Azure OpenAI for the
                      viewer-facing ("casual") sentence in each language. Every reply passes the
                      deterministic output guard (agents/output_guard.py); a reply that fails, or is
                      not valid JSON, is replaced by the template sentence for that language and the
                      rejection is recorded. The "analyst" tone always stays the exact template.

Accepted model sentences are cached in data/phrasing-cache/ (keyed by claim hash, model and prompt
version, with where they came from), so tests and the demo replay them offline and identically.
The model client is injected (`ModelClient`); `AzureChatClient` is the real one, built from
environment variables with Microsoft Entra ID auth (DefaultAzureCredential, e.g. `az login`) and an
API-key fallback only when AZURE_OPENAI_API_KEY is set. A key is never logged.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from . import output_guard
from .narrative import fmt, render

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "phrasing-cache"
PROMPT_VERSION = "p4"            # p2: observational wording; p3: rates "<value> per 100"; p4: context fields in words
MAX_CALLS = 60                      # hard cap of model calls per process run
TEMPERATURE = 0.2

SYSTEM_PROMPT = """You write one short sentence per language for a football match-insights feed.
You receive a VERIFIED claim object (JSON). Rules, all mandatory:
- Use ONLY the facts in the claim. Do not add, compute, round, estimate or change any number.
- Every number in the claim's "params" must appear exactly as given in "numbers" for that language
  (same digits, same decimal separator); write no other number, no ordinal and no year.
- A param whose name ends in _100 is a rate per hundred: quote it as the value followed by "per 100"
  with 100 in digits (English "15.4 per 100", Spanish "15,4 por cada 100", French "15,4 pour 100").
- game_state, window, zone and scope are context, not figures: describe them in words without any digit
  (for example "while leading comfortably", "in the second half"); never write seconds or a goal margin.
- Mention only the teams and players named in the claim.
- Describe the past and present only: no predictions, no outcomes, no betting language.
- Say only what was recorded (played, completed, switched, won back, conceded). Never say why a
  team or player did something, what they intended, or that one thing caused another.
- Plain, friendly, one sentence, at most 280 characters, in the requested language.
Reply with JSON only: {"<language code>": "<sentence>", ...} for exactly the requested languages."""

LANG_NAMES = {"en": "English", "es": "Spanish", "fr": "French"}


def model_input(claim: dict) -> dict:
    """What the model sees: the language-independent claim, without evidence ids or timestamps."""
    keep = ("claim_type", "metric", "scope", "subject", "value", "zone", "window", "game_state",
            "supporting_values", "template_key", "params")
    out = {k: claim[k] for k in keep if k in claim}
    v = claim.get("verification") or {}
    out["verification"] = {"status": v.get("status"), "rule_ids": v.get("rule_ids", [])}
    return out


def variant_seed(claim: dict) -> str:
    """The claim id without its attempt suffix: every attempt of one claim, and the same claim in a
    re-run, reads with the same variant."""
    cid = claim.get("claim_id", "")
    return cid.rsplit("_a", 1)[0] if "_a" in cid else cid


def claim_hash(claim: dict) -> str:
    return hashlib.sha256(json.dumps(model_input(claim), sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]


class ModelClient(Protocol):
    model: str

    def complete(self, system: str, user: str) -> str:
        """One chat completion; returns the reply text."""


@dataclass
class PhraseResult:
    rendered: dict                       # language -> tone -> text (what the stream carries)
    phraser: str                         # "template" or "azure-openai"
    source: dict = field(default_factory=dict)          # language -> "template" | "model" | "cache"
    guard_rejected: dict = field(default_factory=dict)  # language -> [problems]


class TemplatePhraser:
    name = "template"

    def phrase(self, claim: dict, languages: tuple) -> PhraseResult:
        rendered = {lang: render(claim["template_key"], claim["params"], lang, variant_seed=variant_seed(claim))
                    for lang in languages}
        return PhraseResult(rendered, self.name, {lang: "template" for lang in languages})


class PhrasingCache:
    """data/phrasing-cache/<model>/<prompt version>/<claim hash>.json; one file per accepted reply."""

    def __init__(self, root: Path = CACHE_DIR):
        self.root = Path(root)

    def path(self, model: str, h: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in model)
        return self.root / safe / PROMPT_VERSION / f"{h}.json"

    def get(self, model: str, claim: dict) -> dict | None:
        p = self.path(model, claim_hash(claim))
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def put(self, model: str, claim: dict, sentences: dict, origin: dict):
        p = self.path(model, claim_hash(claim))
        p.parent.mkdir(parents=True, exist_ok=True)
        old = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"sentences": {}}
        rec = {"claim_hash": claim_hash(claim), "claim_id": claim["claim_id"], "template_key": claim["template_key"],
               "model": model, "prompt_version": PROMPT_VERSION, "sentences": {**old["sentences"], **sentences},
               "origin": origin}
        p.write_text(json.dumps(rec, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8")


class AzureOpenAIPhraser:
    name = "azure-openai"

    def __init__(self, client: ModelClient | None, known_entities: set, names: dict,
                 cache: PhrasingCache | None = None, max_calls: int = MAX_CALLS, offline: bool = False,
                 model: str | None = None):
        self.client, self.known, self.names = client, set(known_entities), dict(names)
        self.cache = cache if cache is not None else PhrasingCache()
        self.max_calls, self.calls, self.offline = max_calls, 0, offline
        # every model sentence the guard rejected: (claim_id, language, text, problems), for reports
        self.rejected: list = []
        # the cache key: the client's model, or (offline) the deployment whose cached replies to replay
        self.model = client.model if client else (model or "offline")

    def _ask(self, claim: dict, languages: tuple) -> tuple[dict | None, str | None]:
        if self.offline or self.client is None:
            return None, "no model client (offline)"
        if self.calls >= self.max_calls:
            return None, f"call cap {self.max_calls} reached"
        self.calls += 1
        numbers = {lang: {k: fmt(v, lang) for k, v in claim["params"].items()
                          if isinstance(v, (int, float)) and not isinstance(v, bool)} for lang in languages}
        user = json.dumps({"languages": {l: LANG_NAMES.get(l, l) for l in languages}, "numbers": numbers,
                           "claim": model_input(claim)}, ensure_ascii=False)
        try:
            reply = self.client.complete(SYSTEM_PROMPT, user)
            data = json.loads(reply)
        except Exception as e:                       # malformed JSON or a failed call: fall back
            return None, f"reply not usable: {type(e).__name__}"
        if not isinstance(data, dict):
            return None, "reply is not a JSON object"
        return data, None

    def phrase(self, claim: dict, languages: tuple) -> PhraseResult:
        base = TemplatePhraser().phrase(claim, languages)
        out = PhraseResult({l: dict(t) for l, t in base.rendered.items()}, self.name,
                           {l: "template" for l in languages})
        cached = self.cache.get(self.model, claim)
        cached = (cached or {}).get("sentences", {})
        want = tuple(l for l in languages if l not in cached)
        data, err = self._ask(claim, want) if want else ({}, None)
        accepted = {}
        for lang in languages:
            if lang in cached:
                text, src = cached[lang], "cache"
            elif data is None:
                out.guard_rejected[lang] = [err]
                continue
            else:
                text, src = data.get(lang), "model"
            problems = output_guard.check(text, claim, lang, self.known, self.names)
            if problems:
                out.guard_rejected[lang] = problems
                if src == "model":
                    self.rejected.append((claim["claim_id"], lang, text, problems))
                continue
            out.rendered[lang]["casual"] = text.strip()
            out.source[lang] = src
            if src == "model":
                accepted[lang] = text.strip()
        if accepted:
            self.cache.put(self.model, claim, accepted, {
                "source": "azure-openai", "deployment": getattr(self.client, "deployment", self.model),
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "guard": "agents/output_guard.py"})
        return out


class AzureChatClient:
    """The real model client: openai.AzureOpenAI against an Azure AI Foundry / Azure OpenAI deployment.
    Configuration from the environment (see .env.example); Entra ID first, key only if set."""

    def __init__(self, endpoint: str | None = None, deployment: str | None = None, api_version: str | None = None):
        from openai import AzureOpenAI          # imported here: the default install does not need it
        self.endpoint = endpoint or os.environ["AZURE_OPENAI_ENDPOINT"]
        self.deployment = deployment or os.environ["AZURE_OPENAI_DEPLOYMENT"]
        self.model = self.deployment
        self.tokens = {"prompt": 0, "completion": 0}
        version = api_version or os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
        key = os.environ.get("AZURE_OPENAI_API_KEY")
        if key:
            self._client = AzureOpenAI(azure_endpoint=self.endpoint, api_key=key, api_version=version)
            self.auth = "api-key"
        else:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider
            token = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
            self._client = AzureOpenAI(azure_endpoint=self.endpoint, azure_ad_token_provider=token, api_version=version)
            self.auth = "entra-id"

    def complete(self, system: str, user: str) -> str:
        r = self._client.chat.completions.create(
            model=self.deployment, temperature=TEMPERATURE, max_tokens=600,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        u = getattr(r, "usage", None)
        if u is not None:                            # token counts, for the run's cost estimate
            self.tokens["prompt"] += getattr(u, "prompt_tokens", 0) or 0
            self.tokens["completion"] += getattr(u, "completion_tokens", 0) or 0
        return r.choices[0].message.content or ""


def configured_model() -> str | None:
    """The deployment name from the environment (also the cache key when replaying offline)."""
    return os.environ.get("AZURE_OPENAI_DEPLOYMENT") or None


def azure_configured() -> bool:
    return bool(os.environ.get("AZURE_OPENAI_ENDPOINT") and os.environ.get("AZURE_OPENAI_DEPLOYMENT"))


def known_entities(ds) -> tuple[set, dict]:
    """Every team code, team name and player name in the dataset, and code -> team name."""
    names = {t["code"]: t["name"] for t in ds.teams.values()}
    known = set(names) | set(names.values()) | {p["name"] for p in ds.players.values()}
    return known, names
