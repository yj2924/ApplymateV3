"""Optional Claude integration.

Two jobs, both with validation and an automatic fallback to the rule engine:
1. extract_requirements: JD -> strict JSON {responsibilities, required, preferred}
2. polish_letter: rewrite the template letter, then reject the rewrite if it
   introduces any number that is not in the profile (hallucination guard).
"""
from __future__ import annotations

import json
import re

from .jd_parser import ParsedJD
from .tailor import unsupported_numbers

MODEL = "claude-sonnet-4-5"

EXTRACT_PROMPT = """Split this job description into three lists of short, verbatim requirement sentences.
Return ONLY a JSON object with exactly these keys:
{"responsibilities": [string], "required": [string], "preferred": [string]}
Rules: copy wording from the JD, do not paraphrase or invent; "preferred" holds anything marked
preferred / nice to have / a plus / bonus / 优先 / 加分; "required" holds minimum or basic qualifications.

JOB DESCRIPTION:
"""

POLISH_PROMPT = """Rewrite this cover letter so it reads naturally and specifically for the role.
Hard rules:
- Use ONLY facts already in the letter. Do not add numbers, tools, employers or achievements.
- Keep four short paragraphs, the greeting and the sign-off.
- Never use em dashes or en dashes.
- Under 330 words.
Return only the letter text.

LETTER:
"""


def _client(api_key: str):
    import anthropic  # imported lazily so the app runs without the package
    return anthropic.Anthropic(api_key=api_key)


def _text(resp) -> str:
    return "".join(getattr(b, "text", "") for b in resp.content)


def extract_requirements(jd_text: str, api_key: str) -> tuple[ParsedJD | None, str]:
    try:
        resp = _client(api_key).messages.create(
            model=MODEL, max_tokens=1500,
            messages=[{"role": "user", "content": EXTRACT_PROMPT + jd_text}],
        )
        raw = _text(resp)
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0)) if m else None
        if not isinstance(data, dict) or not all(isinstance(data.get(k), list) for k in ("required", "preferred")):
            return None, "LLM output failed schema validation; used rule-based parser"
        clean = lambda xs: [str(x).strip() for x in xs if str(x).strip()]
        return ParsedJD(raw=jd_text, responsibilities=clean(data.get("responsibilities", [])),
                        required=clean(data["required"]), preferred=clean(data["preferred"])), "Parsed with Claude"
    except Exception as e:  # network, auth, package missing...
        return None, f"Claude unavailable ({type(e).__name__}); used rule-based parser"


def polish_letter(letter: str, profile: dict, api_key: str) -> tuple[str, str]:
    try:
        resp = _client(api_key).messages.create(
            model=MODEL, max_tokens=1200,
            messages=[{"role": "user", "content": POLISH_PROMPT + letter}],
        )
        new = _text(resp).strip()
    except Exception as e:
        return letter, f"Claude unavailable ({type(e).__name__}); kept template letter"
    bad = unsupported_numbers(new, profile)
    if bad:
        return letter, f"Rejected AI rewrite: it introduced numbers not in your profile ({', '.join(bad[:3])})"
    if re.search(r"[—–]", new):
        new = re.sub(r"\s*[—–]\s*", ", ", new)
    return new, "Polished with Claude (fact check passed)"
