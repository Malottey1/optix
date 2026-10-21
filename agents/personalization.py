"""Personalization agent: chooses what a viewer sees from the same verified stream.

Selection only, never regeneration: the stream already carries every language and both tones,
and filtering never changes a number. A profile has a mode (analyst or casual), a favorite club,
a focused player, a single chosen metric (an insight_type) and a language.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserProfile:
    mode: str = "casual"                 # "analyst" or "casual"
    language: str = "en"
    favorite_club: str | None = None     # team code: their insights first
    player_focus: str | None = None      # player_id: only insights involving the player
    single_metric: str | None = None     # insight_type: only that type

    def __post_init__(self):
        if self.mode not in ("analyst", "casual"):
            raise ValueError(f"unknown mode {self.mode!r}")


class PersonalizationAgent:
    name = "personalization"

    def __init__(self, log=None):
        self.log = log

    def select(self, insights: list, profile: UserProfile) -> list:
        """Insights for this viewer, each with `display` = (text, context chip) in their mode and
        language. Order: clock, with the favorite club's insights first at the same clock."""
        out = []
        for ins in insights:
            if profile.player_focus and profile.player_focus not in (ins.get("player_ids") or []):
                continue
            if profile.single_metric and ins["insight_type"] != profile.single_metric:
                continue
            rendered = ins["text"]["rendered"]
            lang = profile.language if profile.language in rendered else "en"
            out.append(dict(ins, display={"language": lang, "mode": profile.mode,
                                          "text": rendered[lang][profile.mode],
                                          "context_chip": ins.get("context_chip"),
                                          "favorite": ins["teams"]["primary"] == profile.favorite_club}))
        out.sort(key=lambda i: (i["clock"]["start_sec"], not i["display"]["favorite"]))
        if self.log:
            self.log(self.name, "selected", n_in=len(insights), n_out=len(out), mode=profile.mode,
                     language=profile.language, favorite_club=profile.favorite_club,
                     player_focus=profile.player_focus, single_metric=profile.single_metric)
        return out
