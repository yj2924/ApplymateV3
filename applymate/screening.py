"""Eligibility screening: turn a JD + profile into an auditable checklist and a verdict.

Every check returns the JD sentence it is based on, so the user can see *why*.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .jd_parser import ParsedJD, min_years_required
from .profile import all_bullets, profile_skill_names
from .skills import normalize, skills_in

PASS, WARN, FAIL, UNKNOWN = "pass", "warn", "fail", "unknown"

SPONSOR_BLOCKERS = [
    r"(?:no|not|unable to|cannot|won't|will not|does not|do not)\b[^.\n]{0,60}\bsponsor",
    r"not eligible for (?:visa )?sponsorship",
    r"without (?:the need for |requiring )?(?:visa |employment )?sponsorship",
    r"(?:u\.?s\.?|united states) citizen(?:ship)?\b[^.\n]{0,40}(?:required|only|must)",
    r"must be (?:a )?(?:u\.?s\.?|united states) citizen",
    r"u\.?s\.? person",
    r"(?:active|obtain|eligib\w+ for) (?:a )?(?:us |u\.s\. )?security clearance",
    r"green card holders? only",
    r"不(?:提供|支持)(?:签证|工作签证)",
]
SPONSOR_NEUTRAL = [r"sponsorship (?:is )?available", r"will sponsor", r"visa sponsorship provided"]

ENROLLMENT_PATTERNS = [
    r"currently enrolled", r"returning to (?:school|university|your studies)",
    r"must be (?:a )?(?:current )?student", r"pursuing (?:a|an|your) [^.\n]{0,40}degree[^.\n]{0,30}(?:during|throughout)",
    r"在读", r"实习期间(?:仍)?在校",
]

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
SEASON = {"spring": 5, "summer": 8, "fall": 12, "autumn": 12, "winter": 12}
DATE_TOKEN = r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?|spring|summer|fall|autumn|winter)\s+(20\d\d)"
STAFFING_PATTERNS = [
    r"staffing (?:agency|firm|company)", r"recruiting (?:agency|firm)", r"on behalf of (?:our|a) client",
    r"our client,? (?:a|an|is)", r"placement (?:agency|program|fee)", r"corp[- ]to[- ]corp|\bc2c\b",
    r"contract[- ]to[- ]hire", r"w-?2 contract", r"training (?:and|&) placement", r"人力外包", r"劳务派遣", r"外包岗",
]
OFFLINE_PATTERNS = [r"线下笔试", r"现场笔试", r"线下面试", r"现场面试", r"线下考试", r"现场考核",
                    r"in-person (?:assessment|interview|test)s?\b[^.\n]{0,30}(?:required|only|mandatory)",
                    r"must attend (?:an )?(?:on-?site|in-person)"]
ONLINE_HINT = re.compile(r"线上|在线|远程|视频|online|virtual|remote|zoom|video", re.I)

GRAD_WINDOW_RE = re.compile(rf"graduat\w*[^.\n]{{0,40}}?{DATE_TOKEN}[^.\n]{{0,15}}?(?:and|to|through|-|–|or)\s*{DATE_TOKEN}", re.I)


@dataclass
class Check:
    category: str
    requirement: str
    status: str
    detail: str = ""


@dataclass
class Screening:
    verdict: str                     # recommended | caution | not_recommended | do_not_apply
    checks: list[Check] = field(default_factory=list)
    preferred_rate: float | None = None
    preferred_total: int = 0
    missing_skills: list[str] = field(default_factory=list)


def _ym(token_month: str, year: str) -> int:
    t = token_month.lower().rstrip(".")
    month = SEASON.get(t) or MONTHS.get(t[:3], 6)
    return int(year) * 12 + month


def _profile_ym(value: str) -> int | None:
    m = re.match(r"(20\d\d)-(\d\d)", value or "")
    return int(m.group(1)) * 12 + int(m.group(2)) if m else None


def _sentence_around(text: str, start: int, end: int) -> str:
    left = max(text.rfind(ch, 0, start) for ch in ".\n。") + 1
    rights = [i for i in (text.find(ch, end) for ch in ".\n。") if i != -1]
    right = min(rights) + 1 if rights else len(text)
    return text[left:right].strip()


DEGREE_RE = re.compile(r"degree|bachelor|master|ph\.?d|学历|本科|硕士|博士|专业", re.I)
FIELD_WORDS = {
    "statistics": ["statistic", "统计"], "mathematics": ["math", "数学"], "computer science": ["computer science", "计算机"],
    "economics": ["econom", "经济"], "finance": ["financ", "金融"], "engineering": ["engineering", "工程"],
    "data science": ["data science", "数据科学"], "physics": ["physic", "物理"], "business": ["business", "商"],
}


def _degree_check(line: str, profile: dict) -> Check | None:
    if not DEGREE_RE.search(line):
        return None
    low = line.lower()
    asked = {f for f, keys in FIELD_WORDS.items() if any(k in low for k in keys)}
    degrees = " ".join(e.get("degree", "") for e in profile.get("education", [])).lower()
    have = {f for f, keys in FIELD_WORDS.items() if any(k in degrees for k in keys)}
    ev = "; ".join(e.get("degree", "") for e in profile.get("education", []))
    if not asked or asked & have or "related" in low or "相关" in line:
        return Check("required", line, PASS, f"Education: {ev}")
    return Check("required", line, FAIL, f"Your degree ({ev}) is not in the listed fields")


def _evidence(profile: dict, skill: str) -> str | None:
    for _, block, b in all_bullets(profile):
        if skill in {normalize(s) for s in b.get("skills", [])} or skill in skills_in(b["text"]):
            return f"{block.get('org') or block.get('name')}: {b['text'][:90]}"
    if skill in {normalize(s["name"]) for s in profile.get("skills", []) if s.get("show") != "never"}:
        return "Listed in skills"
    return None


def _line_check(line: str, owned: set[str], profile: dict, category: str) -> Check:
    if category == "required":
        deg = _degree_check(line, profile)
        if deg:
            return deg
    wanted = skills_in(line)
    if not wanted:
        return Check(category, line, UNKNOWN, "No recognisable skill; check manually")
    have = wanted & owned
    missing = wanted - owned
    if not missing:
        ev = _evidence(profile, sorted(have)[0])
        return Check(category, line, PASS, ev or ", ".join(sorted(have)))
    if have and re.search(r"\bor\b|或|/|any of|one of", line, re.I):
        return Check(category, line, PASS, f"Have {', '.join(sorted(have))} (JD accepts alternatives)")
    if have:
        return Check(category, line, WARN, f"Have {', '.join(sorted(have))}; missing {', '.join(sorted(missing))}")
    return Check(category, line, FAIL, f"Missing {', '.join(sorted(missing))}")


def _kw_hit(keywords: list[str], text: str) -> str | None:
    low = text.lower()
    return next((k for k in keywords if k and re.search(rf"(?<![a-z]){re.escape(k.lower())}(?![a-z])", low)), None)


def _direction_check(role: str, jd: ParsedJD, prefs: dict) -> Check | None:
    """Is this role in the user's target direction? Judged on the role title."""
    title = (role or "").strip()
    if not title:
        return None
    bad = _kw_hit(prefs.get("excluded_role_keywords", []), title)
    if bad:
        return Check("hard", f"Role: {title}", FAIL, f"Matches excluded keyword \"{bad}\"")
    stretch = _kw_hit(prefs.get("stretch_role_keywords", []), title)
    if stretch:
        return Check("hard", f"Role: {title}", WARN, f"Stretch direction (\"{stretch}\"): apply only at top firms")
    target = _kw_hit(prefs.get("target_roles", []), title)
    if target:
        return Check("hard", f"Role: {title}", PASS, f"In your target directions ({target})")
    if prefs.get("target_roles"):
        return Check("hard", f"Role: {title}", WARN, "Not one of your target directions; check the actual work")
    return None


def _limit_check(company: str, prefs: dict, history: list[dict]) -> Check | None:
    """Per-company application caps, counted from the tracker (statuses beyond Saved)."""
    from datetime import date, timedelta
    for lim in prefs.get("application_limits", []):
        name = (lim.get("company") or "").strip()
        if not name or name.lower() not in (company or "").lower():
            continue
        cap = int(lim.get("max") or 0)
        days = int(lim.get("period_days") or 365)
        since = date.today() - timedelta(days=days)
        used = 0
        for r in history:
            if name.lower() not in (r.get("company") or "").lower() or r.get("status") in ("Saved", "", None):
                continue
            try:
                when = date.fromisoformat(r.get("applied_on") or "")
            except ValueError:
                when = date.today()
            used += when >= since
        note = f" ({lim['note']})" if lim.get("note") else ""
        detail = f"{used} of {cap} used in the last {days} days{note}"
        return Check("hard", f"Application limit: {name}", FAIL if cap and used >= cap else PASS, detail)
    return None


def screen(jd: ParsedJD, profile: dict, company: str = "", role: str = "",
           history: list[dict] | None = None) -> Screening:
    prefs = profile.get("preferences", {})
    checks: list[Check] = []
    text = jd.raw
    low = jd.lower

    # 0. Role direction, per-company caps, staffing risk, offline-only assessments
    for c in (_direction_check(role, jd, prefs), _limit_check(company, prefs, history or [])):
        if c:
            checks.append(c)
    m = next((m for p in STAFFING_PATTERNS if (m := re.search(p, low))), None)
    if m:
        checks.append(Check("hard", _sentence_around(text, m.start(), m.end()), WARN,
                            "Looks like a staffing / placement firm: confirm the real employer, any fees, W-2 status and who files the visa"))
    if prefs.get("reject_if_offline_only", True):
        m = next((m for p in OFFLINE_PATTERNS if (m := re.search(p, low))), None)
        if m:
            snippet = _sentence_around(text, m.start(), m.end())
            if ONLINE_HINT.search(snippet):
                checks.append(Check("hard", snippet, WARN, "Mentions an in-person step but also an online option; confirm"))
            else:
                checks.append(Check("hard", snippet, FAIL, "Assessment or interview must be taken in person"))

    # 1. Company blocklist
    blocked = [c for c in prefs.get("blocked_companies", []) if c and c.lower() in (company or "").lower()]
    if blocked:
        checks.append(Check("hard", f"Company: {company}", FAIL, "On your blocked-companies list"))

    # 2. Work authorization
    if profile.get("work_authorization", {}).get("needs_sponsorship"):
        hit = next((m for p in SPONSOR_BLOCKERS if (m := re.search(p, low))), None)
        if hit:
            snippet = _sentence_around(text, hit.start(), hit.end())
            checks.append(Check("hard", snippet, FAIL, "JD rules out visa sponsorship / requires citizenship or clearance"))
        elif any(re.search(p, low) for p in SPONSOR_NEUTRAL):
            checks.append(Check("hard", "Visa sponsorship", PASS, "JD says sponsorship is available"))
        else:
            checks.append(Check("hard", "Visa sponsorship", UNKNOWN, "JD is silent; answer the visa question truthfully and verify with the recruiter"))

    # 3. Years of experience (internships do not count)
    scope = jd.required or jd.other
    yrs = min_years_required(scope)
    if yrs and yrs[0] > prefs.get("max_years_required", 0):
        checks.append(Check("hard", yrs[1], FAIL, f"Requires {yrs[0]}+ years; your limit is {prefs.get('max_years_required', 0)}"))

    # 4. Must still be enrolled
    if prefs.get("reject_if_enrollment_required", True):
        m = next((m for p in ENROLLMENT_PATTERNS if (m := re.search(p, low))), None)
        if m:
            snippet = _sentence_around(text, m.start(), m.end())
            checks.append(Check("hard", snippet, FAIL, "Role requires you to still be a student"))

    # 5. Graduation window
    grad = _profile_ym(profile.get("graduation", ""))
    m = GRAD_WINDOW_RE.search(text)
    if m and grad:
        lo, hi = _ym(m.group(1), m.group(2)), _ym(m.group(3), m.group(4))
        ok = lo <= grad <= hi
        checks.append(Check("hard", m.group(0).strip(), PASS if ok else FAIL,
                            f"You graduate {profile.get('graduation')}" + ("" if ok else ", outside the window")))

    # 6. Required qualifications, line by line
    owned = profile_skill_names(profile)
    for line in jd.required:
        checks.append(_line_check(line, owned, profile, "required"))

    # 7. Preferred qualifications hit rate
    pref_checks = [_line_check(line, owned, profile, "preferred") for line in jd.preferred]
    checks.extend(pref_checks)
    scored = [c for c in pref_checks if c.status != UNKNOWN or prefs.get("count_unknown_as_miss", True)]
    rate = None
    if scored:
        hits = sum(1.0 if c.status == PASS else 0.5 if c.status == WARN else 0.0 for c in scored)
        rate = hits / len(scored)

    gap_lines = [c.requirement for c in checks if c.category in ("required", "preferred") and c.status in (WARN, FAIL)]
    missing = sorted({s for line in gap_lines for s in skills_in(line)} - owned)

    # Verdict
    hard_fail = any(c.status == FAIL for c in checks if c.category in ("hard", "required"))
    if hard_fail:
        verdict = "do_not_apply"
    elif rate is not None and rate < prefs.get("preferred_hit_threshold", 0.8):
        verdict = "not_recommended"
    elif any(c.status == WARN for c in checks if c.category in ("hard", "required")):
        verdict = "caution"
    else:
        verdict = "recommended"
    return Screening(verdict, checks, rate, len(scored), missing)
