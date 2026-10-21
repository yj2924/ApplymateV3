"""Split a raw job description into sections and extract structured signals.

Works on English and Chinese JDs. Pure Python, no network.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Section headers we recognise. Order matters: preferred patterns are checked
# before required ones because "preferred qualifications" contains "qualifications".
PREFERRED_HEADERS = [
    r"preferred qualifications?", r"nice to have", r"bonus (points|qualifications)",
    r"pluses?", r"what would be great", r"desired (skills|qualifications)", r"preferred",
    r"加分项", r"优先条件", r"优先考虑",
]
REQUIRED_HEADERS = [
    r"(basic|minimum|required) qualifications?", r"requirements?", r"what you(?:'ll)? bring",
    r"who you are", r"what we look for", r"qualifications?", r"you have",
    r"任职要求", r"任职资格", r"岗位要求", r"招聘条件", r"基本要求",
]
RESP_HEADERS = [
    r"responsibilities", r"what you(?:'ll)? do", r"the role", r"your role", r"key duties",
    r"岗位职责", r"工作职责", r"职位描述",
]

BULLET_RE = re.compile(r"^\s*(?:[-*•·●▪]|\d+[.)、]|[（(]?\d+[)）])\s*")


@dataclass
class ParsedJD:
    raw: str
    responsibilities: list[str] = field(default_factory=list)
    required: list[str] = field(default_factory=list)
    preferred: list[str] = field(default_factory=list)
    other: list[str] = field(default_factory=list)

    @property
    def lower(self) -> str:
        return self.raw.lower()


def _classify_header(line: str) -> str | None:
    text = line.strip().strip(":：").lower()
    if len(text) > 60:
        return None
    for pat in PREFERRED_HEADERS:
        if re.fullmatch(rf"[\W\d]*{pat}[\W]*", text):
            return "preferred"
    for pat in RESP_HEADERS:
        if re.fullmatch(rf"[\W\d]*{pat}[\W]*", text):
            return "responsibilities"
    for pat in REQUIRED_HEADERS:
        if re.fullmatch(rf"[\W\d]*{pat}[\W]*", text):
            return "required"
    return None


def _split_items(line: str) -> list[str]:
    """Chinese JDs often pack several numbered items into one line: 1、... 2、..."""
    parts = re.split(r"(?:(?<=[；;。])|^)\s*\d+[、.)]\s*", line)
    return [p.strip(" ；;。") for p in parts if p and p.strip(" ；;。")]


def parse_jd(text: str) -> ParsedJD:
    jd = ParsedJD(raw=text)
    bucket = "other"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        header = _classify_header(line)
        if header:
            bucket = header
            continue
        # "Preferred: SQL, Tableau" inline style
        m = re.match(r"^(preferred|nice to have|加分项|优先)[:：]\s*(.+)$", line, re.I)
        if m:
            jd.preferred.extend(_split_items(m.group(2)))
            continue
        item = BULLET_RE.sub("", line)
        items = _split_items(item) if re.search(r"\d+、", item) else [item]
        getattr(jd, bucket).extend(i for i in items if len(i) > 2)
    # A JD with no headers at all: treat every line as a requirement candidate.
    if not (jd.required or jd.preferred or jd.responsibilities):
        jd.required = jd.other[:]
    return jd


# ---------------------------------------------------------------- signals
YEARS_RE = re.compile(
    r"(\d+)\s*\+?\s*(?:-|–|to)?\s*(\d+)?\s*\+?\s*years?(?:\s+of)?(?:\s+\w+){0,4}\s+(?:experience|exp\.?)",
    re.I,
)
YEARS_CN_RE = re.compile(r"(\d+)\s*年(?:以上|及以上)?[^，。；\n]{0,8}(?:工作)?经验")


def min_years_required(lines: list[str]) -> tuple[int, str] | None:
    """Largest minimum-years requirement found in the given lines."""
    best = None
    for line in lines:
        for m in list(YEARS_RE.finditer(line)) + list(YEARS_CN_RE.finditer(line)):
            years = int(m.group(1))
            if years == 0 or years > 20:
                continue
            if best is None or years > best[0]:
                best = (years, line.strip())
    return best
