"""Extract a bounded set of financial statements from exact passages.

Every template says what the source states, not what is independently true.
Unsupported formats, units, negated metrics and ambiguous quantities are omitted.
"""

import re
from dataclasses import dataclass

from vibefinance.analysis.text import negated_after, negated_before, sentences


@dataclass(frozen=True)
class FinancialFact:
    key: str
    value: float | None
    unit: str | None
    text: str
    polarity: int
    source_span: str


_NUMBER = r"(?P<number>[+-]?\d+(?:\.\d+)?)"
_METRIC = r"(?P<metric>operating profit|net profit|revenue|profit|net debt|debt)"
_CHANGE = r"(?P<direction>growth|grew|improved|increased|increase|rose|decline|declined|decreased|decrease|fell|reduced|reduction|cut)"
_METRIC_CHANGE = re.compile(
    rf"\b{_METRIC}\s+{_CHANGE}(?:\s+(?:of|by))?\s+{_NUMBER}\s*%",
    re.IGNORECASE,
)
_CHANGE_METRIC = re.compile(
    rf"\b{_CHANGE}\s+{_METRIC}(?:\s+(?:of|by))?\s+{_NUMBER}\s*%",
    re.IGNORECASE,
)
_MARGIN_MOVE = re.compile(
    r"\b(?P<metric>operating margin|net margin|profit margin|margins?)\s+"
    r"(?:improved|rose|increased|declined|fell|decreased)?\s*(?:from)\s+"
    r"(?P<before>\d+(?:\.\d+)?)\s*%\s+to\s+(?P<after>\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)
_MARGIN_LEVEL = re.compile(
    r"\b(?P<metric>operating margin|net margin|profit margin|margins?)\s+"
    rf"(?:was|were|at|of|stood at)\s+{_NUMBER}\s*%",
    re.IGNORECASE,
)
_DEBT_AMOUNT = re.compile(
    r"\b(?P<metric>net debt|debt)\s+(?:was|of|stood at|at)\s+"
    r"(?:INR|Rs\.?|₹)\s*(?P<number>\d+(?:\.\d+)?)\s+(?P<unit>crore|billion|million)\b",
    re.IGNORECASE,
)
_QUALITATIVE = (
    (r"\b(?:guidance\s+(?:cut|lowered|reduced)|(?:cut|lowered|reduced)\s+guidance)\b", "guidance_cut", "guidance cut", -1),
    (r"\b(?:guidance\s+(?:raised|upgraded|increased)|(?:raised|upgraded|increased)\s+guidance)\b", "guidance_raised", "guidance raised", 1),
    (r"\b(?:guidance\s+(?:maintained|unchanged)|maintained\s+guidance)\b", "guidance_maintained", "guidance unchanged", 0),
    (r"\b(?:litigation|regulatory investigation|regulatory penalty|regulatory fine)\b", "legal_regulatory_risk", "legal or regulatory risk mentioned", -1),
    (r"\b(?:litigation resolved|litigation settled)\b", "legal_resolution", "litigation resolution mentioned", 0),
    (r"\b(?:weak demand|weak bookings|weak order intake|declining demand)\b", "demand_weakness", "demand or order weakness mentioned", -1),
    (r"\b(?:resilient margins|margin expansion|lower margins|margin contraction)\b", "margin_commentary", None, None),
)
_DOWN = {"decline", "declined", "decreased", "decrease", "fell", "reduced", "reduction", "cut"}


def _context(sentence: str) -> str:
    # Avoid upgrading an estimate/scenario to an observed result.
    if re.search(r"\b(?:forecast|forecasts|expected|expects|projection|projects|target|targets|guidance)\b", sentence, re.I):
        return "Source outlook statement"
    return "Source statement"


def extract_financial_facts(text: str) -> list[FinancialFact]:
    facts = []
    seen = set()

    def add(key, value, unit, description, polarity, span, sentence):
        canonical = f"{_context(sentence)} — {description}."
        identity = (key, value, unit, canonical)
        if identity not in seen:
            facts.append(FinancialFact(key, value, unit, canonical, polarity, span))
            seen.add(identity)

    for sentence in sentences(text):
        for pattern in (_METRIC_CHANGE, _CHANGE_METRIC):
            for match in pattern.finditer(sentence):
                if negated_before(sentence, match.start()) or negated_after(sentence, match.end()):
                    continue
                metric = match["metric"].lower()
                value = float(match["number"])
                if match["direction"].lower() in _DOWN:
                    # A negative amount paired with "decline" is ambiguous;
                    # omit it rather than turn two negatives into growth.
                    if value < 0:
                        continue
                    value = -value
                polarity = 1 if value > 0 else -1 if value < 0 else 0
                if metric.endswith("debt"):
                    polarity *= -1
                add(metric.replace(" ", "_") + "_change_pct", value, "percent_change",
                    f"{metric} change {value:+g}%", polarity, match.group(), sentence)
        for match in _MARGIN_MOVE.finditer(sentence):
            if negated_before(sentence, match.start()):
                continue
            metric = match["metric"].lower()
            before, after = float(match["before"]), float(match["after"])
            if max(before, after) > 100:
                continue
            delta = round(after - before, 10)
            add(metric.replace(" ", "_") + "_change_pp", delta, "percentage_points",
                f"{metric} changed from {before:g}% to {after:g}% ({delta:+g} percentage points)",
                1 if delta > 0 else -1 if delta < 0 else 0, match.group(), sentence)
        for match in _MARGIN_LEVEL.finditer(sentence):
            if negated_before(sentence, match.start()) or not 0 <= float(match["number"]) <= 100:
                continue
            metric, value = match["metric"].lower(), float(match["number"])
            add(metric.replace(" ", "_") + "_level_pct", value, "percent_level",
                f"{metric} {value:g}%", 0, match.group(), sentence)
        for match in _DEBT_AMOUNT.finditer(sentence):
            if negated_before(sentence, match.start()):
                continue
            metric, value, unit = match["metric"].lower(), float(match["number"]), match["unit"].lower()
            add(metric.replace(" ", "_") + "_amount", value, "INR_" + unit,
                f"{metric} INR {value:g} {unit}", 0, match.group(), sentence)
        for pattern, key, description, polarity in _QUALITATIVE:
            for match in re.finditer(pattern, sentence, re.IGNORECASE):
                if negated_before(sentence, match.start()):
                    continue
                if key == "legal_regulatory_risk" and re.match(r"\s+(?:resolved|settled)\b", sentence[match.end():], re.I):
                    continue
                if key == "margin_commentary":
                    description = match.group().lower()
                    polarity = -1 if description in {"lower margins", "margin contraction"} else 1
                add(key, None, None, description, polarity, match.group(), sentence)
    return facts
