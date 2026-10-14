"""Phrase-level tone rules, with bounded negation rather than word counts.

These rules are deliberately finite. They handle common financial phrases and
simple negation; they are not a general language model or truth checker.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ToneCue:
    phrase: str
    polarity: int
    sentence: str


# Longer matches take priority so, e.g., debt growth is not positive growth.
_PHRASES = {
    "debt growth": -1, "debt increased": -1, "debt increase": -1,
    "rising debt": -1, "increasing debt": -1, "debt reduced": 1,
    "debt reduction": 1, "lower debt": 1, "guidance cut": -1,
    "cut guidance": -1, "guidance lowered": -1, "guidance raised": 1,
    "raised guidance": 1, "weak demand": -1, "weak bookings": -1,
    "weak order intake": -1, "declining demand": -1,
    "margin contraction": -1, "lower margins": -1,
    "margin expansion": 1, "regulatory investigation": -1,
    "litigation resolved": 0, "litigation settled": 0,
    "regulatory penalty": -1, "strong": 1, "growth": 1,
    "improved": 1, "improving": 1, "expansion": 1,
    "supportive": 1, "resilient": 1, "upgrade": 1,
    "decline": -1, "declined": -1, "declining": -1,
    "weak": -1, "cut": -1, "attrition": -1,
    "delay": -1, "delayed": -1, "litigation": -1,
    "caution": -1, "downgrade": -1, "loss": -1,
    "losses": -1, "impairment": -1, "deteriorated": -1,
}
_CUE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in sorted(_PHRASES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_CLAUSE_RE = re.compile(r"[,;:!?]|\.(?!\d)|\b(?:but|however|while)\b", re.IGNORECASE)
_NEGATORS = {"no", "not", "never", "without", "neither", "lack", "lacks", "lacking"}


def sentences(text: str) -> list[str]:
    """Return exact source substrings, retaining punctuation and decimal numbers."""
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def negated_before(text: str, start: int, window: int = 4) -> bool:
    """Check recent tokens in the same clause; 'not only' is not negation."""
    prefix = _CLAUSE_RE.split(text[:start])[-1].lower()
    words = re.findall(r"[a-z]+", prefix)[-window:]
    for i, word in enumerate(words):
        if word in _NEGATORS and not (word == "not" and words[i + 1:i + 2] == ["only"]):
            return True
    return False


def negated_after(text: str, end: int) -> bool:
    """Handle common postposed denial without reaching another clause."""
    suffix = _CLAUSE_RE.split(text[end:])[0]
    return bool(re.match(
        r"(?:\s+(?:(?:of|by)\s+)?[+-]?\d+(?:\.\d+)?\s*%)?"
        r"\s+(?:(?:was|is|were|are|has|had|have)\s+)?not\s+"
        r"(?:achieved|reported|observed|realized|realised|confirmed|expected)\b", suffix, re.I
    ))


def tone_cues(text: str) -> list[ToneCue]:
    cues = []
    for sentence in sentences(text):
        for match in _CUE_RE.finditer(sentence):
            phrase = match.group().lower()
            polarity = _PHRASES[phrase]
            if phrase == "growth" and re.match(r"\s+(?:(?:of|by)\s+)?-\d", sentence[match.end():]):
                polarity = -1
            if negated_before(sentence, match.start()) or negated_after(sentence, match.end()):
                # An absent positive is cautionary. An absent negative is
                # neutral: "no litigation" does not prove strong fundamentals.
                polarity = -1 if polarity > 0 else 0
            if polarity:
                cues.append(ToneCue(phrase, polarity, sentence))
    return cues


def tone(text: str) -> tuple[int, int, float]:
    cues = tone_cues(text)
    positive = sum(c.polarity > 0 for c in cues)
    negative = sum(c.polarity < 0 for c in cues)
    return positive, negative, (positive - negative) / (positive + negative + 1)
