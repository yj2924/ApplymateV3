"""Tailor resume content and draft a cover letter from profile facts only."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .jd_parser import ParsedJD
from .skills import normalize, skills_in

STOP = set("""a an the and or of to in for with on at by from as is are be this that we you your our will
our their it its into using use across more than per who what how able strong experience work team""".split())


def _keywords(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z+/#.-]{2,}", text.lower()) if w not in STOP}


def _score(bullet: dict, jd_skills: set[str], jd_words: set[str]) -> float:
    tagged = {normalize(s) for s in bullet.get("skills", [])} | skills_in(bullet["text"])
    skill_hits = len(tagged & jd_skills)
    word_hits = len(_keywords(bullet["text"]) & jd_words)
    has_number = 1 if re.search(r"\d", bullet["text"]) else 0
    return skill_hits * 3 + word_hits * 0.5 + has_number * 0.5


@dataclass
class Tailored:
    experiences: list[dict] = field(default_factory=list)   # blocks with re-ranked bullets
    projects: list[dict] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    jd_skills: set[str] = field(default_factory=set)


def bullet_allowed(b: dict, profile: dict, jd_skills: set[str]) -> bool:
    # jd_skills here means the skills the JD *requires* (see required_skills)
    """Per-bullet rules.

    - show: "never" hides the bullet for every JD.
    - only_if_jd_has: [skills] keeps it only when the JD asks for one of them.
    - A skill entry with "bullets_too": true extends its never / if_required rule to bullets whose text
      mentions that skill, so "don't write SQL unless the JD requires it" also hides SQL bullets.
    """
    if b.get("show") == "never":
        return False
    need = {normalize(s) for s in b.get("only_if_jd_has", [])}
    if need and not need & jd_skills:
        return False
    rules = {normalize(s["name"]): s.get("show", "always") for s in profile.get("skills", [])
             if s.get("bullets_too")}
    for sk in skills_in(b["text"]):
        rule = rules.get(sk)
        if rule == "never" or (rule == "if_required" and sk not in jd_skills):
            return False
    return True


def required_skills(jd: ParsedJD) -> set[str]:
    """Skills in the required section (whole JD if no section was found). Drives if_required rules."""
    return skills_in("\n".join(jd.required)) if jd.required else skills_in(jd.raw)


def tailor(jd: ParsedJD, profile: dict, max_bullets: int = 3, max_projects: int = 2) -> Tailored:
    jd_skills = skills_in(jd.raw)
    req = required_skills(jd)
    jd_words = _keywords(jd.raw)

    exps = []
    # Keep every experience (and its original order): dropping jobs leaves unexplained gaps.
    for block in profile.get("experiences", []):
        allowed = [b for b in block.get("bullets", []) if bullet_allowed(b, profile, req)]
        ranked = sorted(allowed, key=lambda b: _score(b, jd_skills, jd_words), reverse=True)
        exps.append({**block, "bullets": ranked[:max_bullets]})

    projects_in = [{**p, "bullets": [b for b in p.get("bullets", []) if bullet_allowed(b, profile, req)]}
                   for p in profile.get("projects", []) if p.get("show") != "never"]
    scored_projects = sorted(
        projects_in,
        key=lambda p: max((_score(b, jd_skills, jd_words) for b in p.get("bullets", [])), default=0),
        reverse=True,
    )
    projects = [p for p in scored_projects[:max_projects]
                if any(_score(b, jd_skills, jd_words) > 0 for b in p.get("bullets", []))]

    skills = []
    for s in profile.get("skills", []):
        canon = normalize(s["name"])
        show = s.get("show", "always")
        if show == "never":
            continue
        if show == "if_required" and canon not in req:
            continue
        skills.append((canon in jd_skills, s["name"]))
    skills.sort(key=lambda x: not x[0])  # JD hits first, original order otherwise
    return Tailored(exps, projects, [name for _, name in skills], jd_skills)


# ---------------------------------------------------------------- cover letter
def _clean(text: str, no_dashes: bool) -> str:
    if no_dashes:
        text = re.sub(r"\s*[—–]\s*", ", ", text).replace(" -- ", ", ")
    return text


def _sentence(bullet_text: str) -> str:
    t = bullet_text.strip().rstrip(".")
    return t[0].lower() + t[1:] if t else t


def _month_name(ym: str) -> str:
    m = re.match(r"(20\d\d)-(\d\d)", ym or "")
    if not m:
        return ym or ""
    import calendar
    return f"{calendar.month_name[int(m.group(2))]} {m.group(1)}"


def draft_cover_letter(company: str, role: str, jd: ParsedJD, profile: dict, t: Tailored,
                       missing_skills: list[str], why_company: str = "") -> str:
    no_dashes = profile.get("writing", {}).get("no_dashes", True)
    edu = profile.get("education", [{}])[0]
    company = company or "your company"
    role = role or "this role"

    top = [(b, block) for block in t.experiences for b in block["bullets"][:1]]
    degree = edu.get("degree", "degree")
    article = "an" if re.match(r"[AEIOU]|M[AS]\b|MBA", degree) else "a"
    p1 = (f"I am applying for the {role} position at {company}. "
          f"{why_company.strip() + ' ' if why_company.strip() else ''}"
          f"I am completing {article} {degree} at {edu.get('school', 'my university')}, "
          f"and the work this role describes is the work I have enjoyed most so far.")

    first = top[0] if top else None
    p2 = ""
    if first:
        b, block = first
        p2 = f"As a {block['role']} at {block['org']}, I {_sentence(b['text'])}."
        if len(first[1]["bullets"]) > 1:
            p2 += f" I also {_sentence(first[1]['bullets'][1]['text'])}."

    p3_bits = [f"At {block['org']}, I {_sentence(b['text'])}." for b, block in top[1:3]]
    if missing_skills:
        gap = " or ".join(missing_skills[:2])
        it = "them" if len(missing_skills[:2]) > 1 else "it"
        p3_bits.append(f"I have not yet used {gap} professionally, and I am ready to learn {it} quickly on the job.")
    p3 = " ".join(p3_bits)

    avail = _month_name(profile.get("available_from", ""))
    relocate = profile.get("writing", {}).get("willing_to_relocate")
    p4 = (f"I can start in {avail}" if avail else "I can start soon") + \
         (", am open to relocating," if relocate else "") + \
         f" and would welcome the chance to contribute to {company}. Thank you for your consideration."

    paras = [p for p in (p1, p2, p3, p4) if p]
    sign = profile.get("writing", {}).get("sign_off", "Sincerely,")
    letter = "Dear Hiring Team,\n\n" + "\n\n".join(paras) + f"\n\n{sign}\n{profile.get('name', '')}"
    return _clean(letter, no_dashes)


# ---------------------------------------------------------------- fact guard
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?%?")


def profile_numbers(profile: dict) -> set[str]:
    blob = []
    for kind in ("experiences", "projects"):
        for block in profile.get(kind, []):
            blob += [b["text"] for b in block.get("bullets", [])]
            blob += [block.get("start", ""), block.get("end", ""), block.get("year", "")]
    for e in profile.get("education", []):
        blob += [e.get("gpa", ""), e.get("start", ""), e.get("end", "")]
    blob += [profile.get("available_from", ""), profile.get("graduation", "")]
    return {n.replace(",", "") for n in NUM_RE.findall(" ".join(blob))}


def unsupported_numbers(text: str, profile: dict) -> list[str]:
    """Numbers in generated text that do not appear anywhere in the profile (likely hallucinated)."""
    known = profile_numbers(profile)
    known |= {k.rstrip("%") for k in known}
    out = []
    for n in NUM_RE.findall(text):
        k = n.replace(",", "")
        if k not in known and k.rstrip("%") not in known and not re.fullmatch(r"20\d\d|[1-9]", k):
            out.append(n)
    return out
