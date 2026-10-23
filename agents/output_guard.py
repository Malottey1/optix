"""Output guard: the deterministic check every model-written sentence must pass before it can reach
the stream or the UI. It never trusts the model; on any problem the caller falls back to the
template sentence for that claim and language.

Checks, per language:
  * numbers: exactly the existing number guard (agents/narrative.number_guard): every numeric param
    of the claim appears, written in the language's own form (decimal comma in es/fr), and no other
    number appears;
  * entities: no team or player outside the claim (a known name or code that is not one of the
    claim's own is rejected);
  * forbidden language: predictions, betting and outcome talk in en/es/fr;
  * length: between MIN_LEN and MAX_LEN characters, one sentence;
  * language: the sentence reads as the requested language (function-word count, see `language_of`).
"""
from __future__ import annotations

import re
import unicodedata

from .narrative import number_guard

MIN_LEN = 20
MAX_LEN = 320

FORBIDDEN = {
    "en": ("will win", "going to win", "set to win", "expected to win", "favourite to", "favorite to", "predict",
           "forecast", "odds", "bet ", "betting", "bookmaker", "wager", "will score", "certain to", "guaranteed"),
    "es": ("ganará", "va a ganar", "van a ganar", "favorito para", "predic", "pronóstico", "cuota", "apuesta",
           "apostar", "marcará", "seguro que gana"),
    "fr": ("gagnera", "va gagner", "vont gagner", "favori pour", "prédi", "pronostic", "cote ", "pari ", "parier",
           "marquera", "gagnant assuré"),
}

# common function words; a sentence is in the language whose words it uses most
STOPWORDS = {
    "en": {"the", "and", "of", "to", "in", "is", "are", "but", "their", "with", "from", "into", "there", "it",
           "on", "at", "this", "that", "only", "than", "have", "has", "times", "league", "per", "by", "for", "them",
           "they", "won", "ball", "pass", "shots", "chances", "after", "before", "when", "while", "more", "made",
           "make", "what", "were", "was", "been", "its", "his", "her", "out", "down", "through", "watch", "keeps",
           "moving", "forward", "plays", "adding", "expected", "threat"},
    "es": {"el", "la", "los", "las", "de", "del", "y", "en", "por", "con", "pero", "que", "una", "un", "su", "sus",
           "es", "son", "más", "al", "liga", "veces", "ha", "han", "para", "sobre", "como", "ocasiones", "tiros",
           "pases", "este", "esta", "desde", "hasta", "entre", "cuando", "pase", "añade", "amenaza", "hacia",
           "delante", "casi", "todos", "banda", "calidad", "da"},
    "fr": {"le", "la", "les", "de", "des", "du", "et", "en", "par", "avec", "mais", "que", "une", "un", "sa", "ses",
           "est", "sont", "plus", "au", "ligue", "fois", "dans", "a", "ont", "pour", "sur", "comme", "occasions",
           "tirs", "cette", "ce", "depuis", "quand", "entre", "il", "elle", "ils", "passe", "ajoute", "menace", "vers", "avant", "presque",
           "toutes", "joue"},
}
WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).casefold()


def language_of(text: str) -> str | None:
    """The language whose function words appear most often (None if no function word at all)."""
    words = [_norm(w) for w in WORD.findall(text)]
    scores = {lang: sum(w in sw for w in words) for lang, sw in STOPWORDS.items()}
    best = max(scores.values())
    if best == 0:
        return None
    top = [lang for lang, s in scores.items() if s == best]
    return top[0] if len(top) == 1 else None


def claim_entities(claim: dict, names: dict) -> set:
    """Names and codes the claim may mention: string params (team codes, player names) and each
    team code's full name (`names`: code -> name)."""
    out = set()
    for v in claim["params"].values():
        if isinstance(v, str):
            out.add(v)
            if v in names:
                out.add(names[v])
    subj = claim.get("subject") or {}
    for k in ("team_code", "player_name"):
        if subj.get(k):
            out.add(subj[k])
            if subj[k] in names:
                out.add(names[subj[k]])
    return out


def check(text: str, claim: dict, language: str, known_entities: set, names: dict | None = None) -> list:
    """Problems with one model-written sentence (empty list = accepted)."""
    if not isinstance(text, str):
        return ["not a string"]
    problems = []
    t = text.strip()
    if not MIN_LEN <= len(t) <= MAX_LEN:
        problems.append(f"length {len(t)} outside {MIN_LEN}-{MAX_LEN}")
    if "\n" in t:
        problems.append("more than one line")
    problems += [f"numbers: {p}" for p in number_guard(t, claim["params"], language)]
    allowed = claim_entities(claim, names or {})
    for ent in sorted(known_entities - allowed, key=len, reverse=True):
        if re.search(rf"(?<![\w]){re.escape(ent)}(?![\w])", t):
            problems.append(f"entity outside the claim: {ent}")
    low = _norm(t)
    problems += [f"forbidden phrase: {p.strip()}" for p in FORBIDDEN.get(language, ()) if p in low]
    got = language_of(t)
    if got != language:
        problems.append(f"language: reads as {got or 'unknown'}, wanted {language}")
    return problems
