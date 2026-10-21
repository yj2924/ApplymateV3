"""Render tailored content as Markdown, a one-page Word resume, or a PDF; English or Chinese.

Everything is built from one list of layout rows, so the Markdown preview, the .docx, the PDF and
the one-page check all agree on content. The PDF is laid out with real font metrics, which is also
how `page_count` tells you whether the resume fits on one page.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

from .tailor import Tailored

# Page geometry shared by docx and PDF (inches)
PAGE_W, PAGE_H = 8.5, 11.0
MARGIN_TOP, MARGIN_BOTTOM, MARGIN_SIDE = 0.35, 0.3, 0.4
BODY_PT, LEADING = 10, 11.6
BULLET_INDENT = 0.2

LABELS = {
    "en": {"education": "Education", "experience": "Professional Experience", "projects": "Projects",
           "skills_section": "Skills and Interests", "coursework": "Relevant Coursework", "skills": "Skills",
           "interests": "Interests", "gpa": "GPA", "present": "Present", "colon": ": ", "sep": "; ", "list": ", "},
    "zh": {"education": "教育背景", "experience": "实习经历", "projects": "项目经历",
           "skills_section": "技能与兴趣", "coursework": "相关课程", "skills": "技能",
           "interests": "兴趣", "gpa": "GPA", "present": "至今", "colon": "：", "sep": "，", "list": "、"},
}


def _zh(d: dict, key: str, lang: str) -> str:
    """Chinese variant of a field when lang == zh and it exists, else the English one."""
    return (d.get(f"{key}_zh") if lang == "zh" else None) or d.get(key, "") or ""


def _fmt(ym: str, lang: str = "en") -> str:
    m = re.match(r"(\d{4})-(\d{1,2})", ym or "")
    if not m:
        return ym or ""
    if lang == "zh":
        return f"{m.group(1)}.{int(m.group(2)):02d}"
    return date(int(m.group(1)), int(m.group(2)), 1).strftime("%b %Y")


def _span(block: dict, lang: str = "en") -> str:
    end = block.get("end", "")
    return f"{_fmt(block.get('start', ''), lang)} – {_fmt(end, lang) if end else LABELS[lang]['present']}"


def contact_line(profile: dict) -> str:
    parts = [profile.get("phone"), profile.get("email"), profile.get("location"), *profile.get("links", [])]
    return " | ".join(p for p in parts if p)


def file_stem(profile: dict, kind: str, company: str, role: str) -> str:
    """e.g. 'Alex Chen resume Acme Data Scientist'. Characters illegal in file names are removed."""
    raw = " ".join(x for x in (profile.get("name", ""), kind, company, role) if x)
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|]+', " ", raw)).strip()


# ---------------------------------------------------------------- layout rows
@dataclass
class Row:
    kind: str          # name | contact | header | title | sub | bullet
    text: str
    right: str = ""


def layout(profile: dict, t: Tailored, lang: str = "en") -> list[Row]:
    L = LABELS[lang]
    rows = [Row("name", _zh(profile, "name", lang)), Row("contact", contact_line(profile)), Row("header", L["education"])]
    for e in profile.get("education", []):
        rows.append(Row("title", _zh(e, "school", lang), e.get("location", "")))
        gpa = f"{L['sep']}{L['gpa']} {e['gpa']}" if e.get("gpa") else ""
        rows.append(Row("sub", f"{_zh(e, 'degree', lang)}{gpa}", _span(e, lang)))
        courses = e.get("coursework_zh") if lang == "zh" and e.get("coursework_zh") else e.get("coursework")
        if courses:
            rows.append(Row("bullet", f"{L['coursework']}{L['colon']}" + L["list"].join(courses)))
    rows.append(Row("header", L["experience"]))
    for x in t.experiences:
        rows.append(Row("title", _zh(x, "org", lang), x.get("location", "")))
        rows.append(Row("sub", _zh(x, "role", lang), _span(x, lang)))
        rows += [Row("bullet", _zh(b, "text", lang)) for b in x["bullets"]]
    if t.projects:
        rows.append(Row("header", L["projects"]))
        for p in t.projects:
            sub = _zh(p, "subtitle", lang)
            rows.append(Row("title", _zh(p, "name", lang) + (f" | {sub}" if sub else ""), str(p.get("year", ""))))
            rows += [Row("bullet", _zh(b, "text", lang)) for b in p["bullets"]]
    rows.append(Row("header", L["skills_section"]))
    rows.append(Row("bullet", f"{L['skills']}{L['colon']}" + L["list"].join(t.skills)))
    interests = _zh(profile, "interests", lang)
    if interests:
        rows.append(Row("bullet", f"{L['interests']}{L['colon']}{interests}"))
    return rows


def resume_markdown(profile: dict, t: Tailored, lang: str = "en") -> str:
    out = []
    for r in layout(profile, t, lang):
        right = f" ({r.right})" if r.right else ""
        if r.kind == "name":
            out.append(f"# {r.text}")
        elif r.kind == "contact":
            out.append(r.text)
        elif r.kind == "header":
            out += ["", f"## {r.text}"]
        elif r.kind == "title":
            out += ["", f"**{r.text}**{right}"]
        elif r.kind == "sub":
            out.append(f"*{r.text}*{right}")
        else:
            out.append(f"- {r.text}")
    return "\n".join(out)


# ---------------------------------------------------------------- docx
def _rule(paragraph):
    pPr = paragraph._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("val", "single"), ("sz", "6"), ("space", "1"), ("color", "000000")):
        bottom.set(qn(f"w:{k}"), v)
    bdr.append(bottom)
    pPr.append(bdr)


def _para(doc, text="", bold=False, italic=False, size=BODY_PT, align=None, after=0, right=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.space_before = Pt(0)
    if align is not None:
        p.alignment = align
    r = p.add_run(text)
    r.bold, r.italic, r.font.size = bold, italic, Pt(size)
    if right:
        p.paragraph_format.tab_stops.add_tab_stop(Inches(PAGE_W - 2 * MARGIN_SIDE), WD_TAB_ALIGNMENT.RIGHT)
        r2 = p.add_run("\t" + right)
        r2.font.size = Pt(size)
        r2.italic = italic
    return p


def _base_doc(lang: str = "en", margins=(MARGIN_TOP, MARGIN_BOTTOM, MARGIN_SIDE)):
    doc = Document()
    for s in doc.sections:
        s.page_width, s.page_height = Inches(PAGE_W), Inches(PAGE_H)
        s.top_margin, s.bottom_margin = Inches(margins[0]), Inches(margins[1])
        s.left_margin = s.right_margin = Inches(margins[2])
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "SimSun" if lang == "zh" else "Times New Roman")
    st.font.size = Pt(BODY_PT)
    for name in ("Normal", "List Bullet"):
        pf = doc.styles[name].paragraph_format
        pf.line_spacing = 1.0          # the default template uses 1.15; single spacing matches the PDF
        pf.space_after = Pt(0)
    return doc


def resume_docx(profile: dict, t: Tailored, lang: str = "en") -> bytes:
    doc = _base_doc(lang)
    for r in layout(profile, t, lang):
        if r.kind == "name":
            _para(doc, r.text, bold=True, size=16, align=WD_ALIGN_PARAGRAPH.CENTER)
        elif r.kind == "contact":
            _para(doc, r.text, size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
        elif r.kind == "header":
            h = _para(doc, r.text.upper(), bold=True, size=10.5, after=1)
            h.paragraph_format.space_before = Pt(5)
            _rule(h)
        elif r.kind == "title":
            _para(doc, r.text, bold=True, right=r.right)
        elif r.kind == "sub":
            _para(doc, r.text, italic=True, right=r.right)
        else:
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.left_indent = Inches(BULLET_INDENT)
            p.add_run(r.text).font.size = Pt(BODY_PT)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def cover_letter_docx(profile: dict, letter: str) -> bytes:
    doc = _base_doc("en", margins=(0.8, 0.8, 0.9))
    _para(doc, profile.get("name", ""), bold=True, size=14, align=WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc, contact_line(profile), size=10, align=WD_ALIGN_PARAGRAPH.CENTER, after=14)
    _para(doc, date.today().strftime("%B %d, %Y"), size=11, after=10)
    for block in letter.split("\n\n"):
        _para(doc, block, size=11, after=9)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- PDF (reportlab) + page count
# Chinese PDFs embed the first TrueType CJK font found (macOS, Windows, Linux / Streamlit Cloud via
# packages.txt). The built-in STSong-Light is only a last resort: it is not embedded, so some viewers
# cannot show it.
CJK_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Songti.ttc", "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "C:/Windows/Fonts/simsun.ttc", "C:/Windows/Fonts/msyh.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
]
_CJK_FONT: str | None = None


def _cjk_font() -> str:
    global _CJK_FONT
    if _CJK_FONT:
        return _CJK_FONT
    from pathlib import Path
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for path in CJK_FONT_CANDIDATES:
        if not Path(path).exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont("ApplyMateCJK", path, subfontIndex=0))
            _CJK_FONT = "ApplyMateCJK"
            return _CJK_FONT
        except Exception:  # CFF-based or unreadable collection: try the next one
            continue
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    _CJK_FONT = "STSong-Light"
    return _CJK_FONT


def _fonts(lang: str) -> dict:
    if lang == "zh":
        f = _cjk_font()
        return {"regular": f, "bold": f, "italic": f}
    return {"regular": "Times-Roman", "bold": "Times-Bold", "italic": "Times-Italic"}


_TOKEN = re.compile(r"[　-鿿＀-￯]|[^\s　-鿿＀-￯]+|\s+")


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    """Greedy wrap that breaks between words and between any two CJK characters."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    lines, cur = [], ""
    for tok in _TOKEN.findall(text):
        trial = cur + tok
        if stringWidth(trial.rstrip(), font, size) <= width or not cur.strip():
            cur = trial
        else:
            lines.append(cur.rstrip())
            cur = tok.lstrip()
    if cur.strip():
        lines.append(cur.rstrip())
    return lines or [""]


def _draw(c, x, y, text, font, size, align="left", fake_bold=False):
    """drawString with alignment; fake_bold strokes the glyphs for fonts that have no bold face."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    w = stringWidth(text, font, size)
    x = x - w if align == "right" else x - w / 2 if align == "center" else x
    t = c.beginText(x, y)
    t.setFont(font, size)
    if fake_bold:
        c.setLineWidth(size * 0.035)
    t.setTextRenderMode(2 if fake_bold else 0)   # render mode persists in the PDF state, so always set it
    t.textOut(text)
    c.drawText(t)


def _render_pdf(rows: list[Row], lang: str, reserve: float = 0) -> tuple[bytes, int]:
    from reportlab.lib.units import inch
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    F = _fonts(lang)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W * inch, PAGE_H * inch))
    left, right = MARGIN_SIDE * inch, (PAGE_W - MARGIN_SIDE) * inch
    top, bottom = (PAGE_H - MARGIN_TOP) * inch, MARGIN_BOTTOM * inch + reserve
    pages, y = 1, top

    def line_feed(h):
        nonlocal y, pages
        if y - h < bottom:
            c.showPage()
            pages += 1
            y = top
        y -= h

    fb = lang == "zh"   # CJK fonts here have no bold face
    mid = (left + right) / 2
    for r in rows:
        if r.kind == "name":
            line_feed(19)
            _draw(c, mid, y + 4, r.text, F["bold"], 16, "center", fb)
        elif r.kind == "contact":
            for ln in _wrap(r.text, F["regular"], 9.5, right - left):
                line_feed(11)
                _draw(c, mid, y + 2.5, ln, F["regular"], 9.5, "center")
            y -= 2
        elif r.kind == "header":
            line_feed(5 + 12.5)
            _draw(c, left, y + 3, r.text.upper() if lang == "en" else r.text, F["bold"], 10.5, fake_bold=fb)
            c.setLineWidth(0.6)
            c.line(left, y + 0.5, right, y + 0.5)
            y -= 1
        elif r.kind in ("title", "sub"):
            font = F["bold"] if r.kind == "title" else F["italic"]
            rf = F["regular"] if r.kind == "title" else F["italic"]
            rw = stringWidth(r.right, rf, BODY_PT) + 8 if r.right else 0
            for i, ln in enumerate(_wrap(r.text, font, BODY_PT, right - left - rw)):
                line_feed(LEADING)
                _draw(c, left, y + 2.5, ln, font, BODY_PT, fake_bold=fb and r.kind == "title")
                if i == 0 and r.right:
                    _draw(c, right, y + 2.5, r.right, rf, BODY_PT, "right")
        else:
            x = left + BULLET_INDENT * inch
            for i, ln in enumerate(_wrap(r.text, F["regular"], BODY_PT, right - x - 10)):
                line_feed(LEADING)
                if i == 0:
                    c.circle(x + 2, y + 5.3, 1.3, stroke=0, fill=1)
                _draw(c, x + 10, y + 2.5, ln, F["regular"], BODY_PT)
    c.save()
    return buf.getvalue(), pages


def resume_pdf(profile: dict, t: Tailored, lang: str = "en") -> bytes:
    return _render_pdf(layout(profile, t, lang), lang)[0]


# Word and PDF viewers lay text out slightly differently (and Chinese fonts vary by machine), so the
# one-page check keeps a safety margin of a line or two at the bottom of the page.
SAFETY_LINES = {"en": 1.0, "zh": 2.5}


def page_count(profile: dict, t: Tailored, lang: str = "en") -> int:
    """Pages the resume needs, with a safety margin so that 1 here means 1 in Word too."""
    return _render_pdf(layout(profile, t, lang), lang, reserve=SAFETY_LINES[lang] * LEADING)[1]


def fit_one_page(profile: dict, t: Tailored, lang: str = "en", min_bullets: int = 1) -> tuple[Tailored, list[str]]:
    """Drop the lowest-ranked bullets (projects first, then the longest experience) until it fits.

    Returns the trimmed Tailored and a human-readable list of what was removed.
    """
    import copy
    t = copy.deepcopy(t)
    removed: list[str] = []
    while page_count(profile, t, lang) > 1:
        proj = [p for p in t.projects if p["bullets"]]
        if len(t.projects) > 1:
            gone = t.projects.pop()
            removed.append(f"Project: {gone.get('name')}")
            continue
        candidates = [x for x in t.experiences if len(x["bullets"]) > min_bullets]
        if not candidates:
            if proj:
                gone = t.projects.pop()
                removed.append(f"Project: {gone.get('name')}")
                continue
            break
        longest = max(candidates, key=lambda x: len(x["bullets"]))
        b = longest["bullets"].pop()
        removed.append(f"{longest.get('org')}: {b['text'][:60]}…")
    return t, removed
