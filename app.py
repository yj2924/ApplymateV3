"""ApplyMate: Streamlit front end."""
import io
import json
import re
from datetime import date

import pandas as pd
import streamlit as st

from applymate import __version__, export, llm, tracker
from applymate.i18n import t
from applymate.jd_parser import parse_jd
from applymate.profile import DEMO_PROFILE, is_demo, load_profile, save_profile
from applymate.samples import SAMPLES
from applymate.screening import FAIL, PASS, UNKNOWN, WARN, screen
from applymate.tailor import (Tailored, bullet_allowed, draft_cover_letter, required_skills, tailor,
                              unsupported_numbers)

st.set_page_config(page_title="ApplyMate", page_icon="🧭", layout="wide")

if "profile" not in st.session_state:
    st.session_state.profile = load_profile()
profile = st.session_state.profile

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("🧭 ApplyMate")
    lang = "zh" if st.radio("Language / 语言", ["English", "中文"], horizontal=True) == "中文" else "en"
    _ = lambda k: t(k, lang)
    pages = ["nav_screen", "nav_tracker", "nav_profile", "nav_data"]
    page = st.radio("nav", pages, format_func=_, label_visibility="collapsed")
    st.divider()
    api_key = st.text_input(_("api_key"), type="password", help=_("api_help"))
    st.caption(f"v{__version__} · rule engine + optional Claude")

if is_demo(profile):
    st.info(_("demo_banner"), icon="🧪")

ICON = {PASS: "✅", WARN: "⚠️", FAIL: "❌", UNKNOWN: "❔"}


# ------------------------------------------------------------------ resume editor
CJK = re.compile(r"[\u4e00-\u9fff]")


def _editor_rows(tl: Tailored, jd, lang: str) -> list[dict]:
    """Every allowed bullet of every block; the ones ApplyMate picked are ticked, the rest can be ticked back on."""
    req = required_skills(jd)
    rows = []
    for kind, picked_blocks, all_blocks in (("experiences", tl.experiences, profile.get("experiences", [])),
                                            ("projects", tl.projects, profile.get("projects", []))):
        picked_names = {b.get("org") or b.get("name") for b in picked_blocks}
        for block in all_blocks:
            name = block.get("org") or block.get("name")
            if kind == "projects" and block.get("show") == "never":
                continue
            chosen = next((b for b in picked_blocks if (b.get("org") or b.get("name")) == name), None)
            chosen_texts = [b["text"] for b in chosen["bullets"]] if chosen else []
            allowed = [b for b in block.get("bullets", []) if bullet_allowed(b, profile, req)]
            allowed.sort(key=lambda b: chosen_texts.index(b["text"]) if b["text"] in chosen_texts else 99)
            for b in allowed:
                rows.append({"use": b["text"] in chosen_texts and name in picked_names, "section": kind,
                             "where": name, "text": export._zh(b, "text", lang), "_src": b["text"]})
    return rows


def _edited_tailored(rows: list[dict], skills: list[str], lang: str) -> Tailored:
    exps, projs = [], []
    for kind, out in (("experiences", exps), ("projects", projs)):
        for block in profile.get(kind, []):
            name = block.get("org") or block.get("name")
            bullets = [{"text": r["text"], "text_zh": r["text"]} for r in rows
                       if r["section"] == kind and r["where"] == name and r["use"] and str(r["text"]).strip()]
            if kind == "experiences" or bullets:
                out.append({**block, "bullets": bullets})
    return Tailored(exps, projs, skills)


def resume_tab(run) -> str:
    tl, jd = run["tl"], run["jd"]
    default_lang = 1 if CJK.search(run["meta"]["jd_text"]) else 0
    rlang = "zh" if st.radio(_("resume_lang"), ["English", "中文"], index=default_lang, horizontal=True,
                             key=f"rl_{st.session_state.run_id}") == "中文" else "en"
    if run.get("trimmed"):
        st.caption(_("auto_trimmed") + "; ".join(run["trimmed"]))
    st.caption(_("editor_help"))
    rows = _editor_rows(tl, jd, rlang)
    edited = st.data_editor(
        pd.DataFrame(rows), hide_index=True, width="stretch", key=f"ed_{st.session_state.run_id}_{rlang}",
        column_order=["use", "where", "text"], disabled=["where"],
        column_config={"use": st.column_config.CheckboxColumn(_("col_use"), width="small"),
                       "where": st.column_config.TextColumn(_("col_where"), width="medium"),
                       "text": st.column_config.TextColumn(_("col_text"), width="large")})
    skills_txt = st.text_input(_("skills_field"), ", ".join(tl.skills), key=f"sk_{st.session_state.run_id}")
    skills = [x.strip() for x in skills_txt.split(",") if x.strip()]
    final = _edited_tailored(edited.to_dict("records"), skills, rlang)

    bad = unsupported_numbers(" ".join(r["text"] for r in edited.to_dict("records") if r["use"]), profile)
    if bad:
        st.error(_("fact_bad") + ", ".join(bad))
    pages = export.page_count(profile, final, rlang)
    if pages == 1:
        st.success(_("one_page_ok"))
    else:
        st.error(_("one_page_bad").format(pages))

    stem = export.file_stem(profile, "resume", run["meta"]["company"], run["meta"]["role"])
    d1, d2 = st.columns(2)
    d1.download_button(_("download_resume"), export.resume_docx(profile, final, rlang), file_name=stem + ".docx")
    d2.download_button(_("download_pdf"), export.resume_pdf(profile, final, rlang), file_name=stem + ".pdf",
                       mime="application/pdf")
    md = export.resume_markdown(profile, final, rlang)
    with st.expander(_("preview")):
        st.markdown(md)
    return md


# ------------------------------------------------------------------ screen a job
def page_screen():
    st.header(_("nav_screen"))
    sample = st.selectbox(_("load_sample"), ["—"] + list(SAMPLES))
    pre = SAMPLES.get(sample, {})
    c1, c2, c3 = st.columns(3)
    company = c1.text_input(_("company"), value=pre.get("company", ""))
    role = c2.text_input(_("role"), value=pre.get("role", ""))
    location = c3.text_input(_("location"), value=pre.get("location", ""))
    c4, c5 = st.columns([3, 1])
    url = c4.text_input(_("url"))
    deadline = c5.date_input(_("deadline"), value=None)
    jd_text = st.text_area(_("jd"), value=pre.get("jd", ""), height=260)
    why = st.text_input(_("why_company"))

    if st.button(_("run"), type="primary", disabled=not jd_text.strip()):
        jd, note = None, "Rule-based parser"
        if api_key:
            with st.spinner("Claude…"):
                jd, note = llm.extract_requirements(jd_text, api_key)
        jd = jd or parse_jd(jd_text)
        result = screen(jd, profile, company, role, history=tracker.all_rows())
        tl = tailor(jd, profile)
        lang0 = "zh" if re.search(r"[\u4e00-\u9fff]", jd_text) else "en"
        tl, trimmed = export.fit_one_page(profile, tl, lang0)
        letter = draft_cover_letter(company, role, jd, profile, tl, result.missing_skills, why)
        letter_note = ""
        if api_key and result.verdict != "do_not_apply":
            with st.spinner("Claude…"):
                letter, letter_note = llm.polish_letter(letter, profile, api_key)
        st.session_state.run_id = st.session_state.get("run_id", 0) + 1
        st.session_state.run = dict(jd=jd, result=result, tl=tl, letter=letter, note=note,
                                    letter_note=letter_note, trimmed=trimmed, meta=dict(company=company, role=role,
                                    location=location, url=url, deadline=deadline, jd_text=jd_text))

    run = st.session_state.get("run")
    if not run:
        return
    result, tl = run["result"], run["tl"]

    st.divider()
    m1, m2, m3 = st.columns([2, 1, 1])
    m1.subheader(f"{_('verdict')}: {_('v_' + result.verdict)}")
    if result.preferred_rate is not None:
        m2.metric(_("pref_rate"), f"{result.preferred_rate:.0%}", help=f"n = {result.preferred_total}")
    m3.caption(f"{_('parser_note')}: {run['note']}")

    st.markdown(f"#### {_('checklist')}")
    rows = [{_("status"): ICON[c.status], "": _("cat_" + c.category), _("requirement"): c.requirement,
             _("evidence"): c.detail} for c in result.checks]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if result.missing_skills:
        st.warning(f"{_('missing')}: {', '.join(result.missing_skills)}")

    tab1, tab2, tab3 = st.tabs([_("resume"), _("letter"), _("skills_field")])
    with tab1:
        resume_md = resume_tab(run)
    with tab2:
        if run["letter_note"]:
            st.caption(run["letter_note"])
        letter = st.text_area(_("letter"), value=run["letter"], height=340, label_visibility="collapsed")
        bad = unsupported_numbers(letter, profile)
        if bad:
            st.error(_("fact_bad") + ", ".join(bad))
        else:
            st.success(_("fact_ok"))
        st.download_button(_("download_letter"), export.cover_letter_docx(profile, letter),
                           file_name=export.file_stem(profile, "cover letter", run["meta"]["company"],
                                                      run["meta"]["role"]) + ".docx")
    with tab3:
        st.code(", ".join(tl.skills), language=None)

    st.divider()
    s1, s2 = st.columns([1, 3])
    status = s1.selectbox(_("status_label"), tracker.STATUSES)
    if s2.button(_("save")):
        meta = run["meta"]
        new_id = tracker.add({**meta, "deadline": meta["deadline"].isoformat() if meta["deadline"] else "",
                              "status": status, "verdict": result.verdict,
                              "preferred_rate": "" if result.preferred_rate is None else f"{result.preferred_rate:.2f}",
                              "resume_md": resume_md, "cover_letter": letter})
        st.success(f"{_('saved')}{new_id}")


# ------------------------------------------------------------------ tracker
def page_tracker():
    st.header(_("nav_tracker"))
    rows = tracker.all_rows()
    if not rows:
        st.info(_("no_apps"))
        return
    df = pd.DataFrame(rows)
    applied_like = df["status"].isin(["Applied", "Online Assessment", "Interview", "Offer", "Rejected"])
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(_("metrics_total"), len(df))
    k2.metric(_("metrics_applied"), int(applied_like.sum()))
    k3.metric(_("metrics_interview"), int(df["status"].isin(["Interview", "Offer"]).sum()))
    k4.metric(_("metrics_offer"), int((df["status"] == "Offer").sum()))

    due = tracker.due_soon(rows)
    if due:
        st.markdown(f"#### ⏰ {_('due')}")
        for d in due:
            flag = f" **({_('overdue')})**" if d["overdue"] else ""
            st.markdown(f"- {d['date']} · #{d['id']} {d['company']} · {d['role']} · {_('kind_' + d['kind'])}{flag}")

    funnel = df["status"].value_counts().reindex(tracker.STATUSES, fill_value=0)
    st.bar_chart(pd.DataFrame({"status": funnel.index, "count": funnel.values}), x="status", y="count",
                 horizontal=True, sort=False, height=260)
    show = ["id", "company", "role", "location", "status", "verdict", "applied_on", "deadline", "follow_up_on", "notes"]
    st.dataframe(df[show], hide_index=True, width="stretch",
                 column_config={"url": st.column_config.LinkColumn()})

    st.markdown(f"#### {_('edit')}")
    sel = st.selectbox("id", df["id"].tolist(),
                       format_func=lambda i: f"#{i} {df.loc[df.id == i, 'company'].iat[0]} · {df.loc[df.id == i, 'role'].iat[0]}")
    rec = tracker.get(sel)
    c1, c2 = st.columns(2)
    new_status = c1.selectbox(_("status_label"), tracker.STATUSES,
                              index=tracker.STATUSES.index(rec["status"]) if rec["status"] in tracker.STATUSES else 0)
    fu = c2.date_input(_("follow_up"), value=date.fromisoformat(rec["follow_up_on"]) if rec.get("follow_up_on") else None)
    notes = st.text_area(_("notes"), value=rec.get("notes") or "")
    b1, b2 = st.columns(2)
    if b1.button(_("update"), type="primary"):
        tracker.update(sel, {"status": new_status, "notes": notes, "follow_up_on": fu.isoformat() if fu else ""})
        st.rerun()
    if b2.button(_("delete")):
        tracker.delete(sel)
        st.rerun()
    with st.expander(_("letter")):
        st.text(rec.get("cover_letter") or "")


# ------------------------------------------------------------------ profile
def page_profile():
    st.header(_("nav_profile"))
    prefs = profile.setdefault("preferences", {})
    auth = profile.setdefault("work_authorization", {})
    st.markdown(f"#### {_('rules')}")
    c1, c2 = st.columns(2)
    prefs["max_years_required"] = c1.number_input(_("max_years"), 0, 20, int(prefs.get("max_years_required", 0)))
    prefs["preferred_hit_threshold"] = c2.slider(_("threshold"), 0.0, 1.0, float(prefs.get("preferred_hit_threshold", 0.8)), 0.05)
    auth["needs_sponsorship"] = c1.checkbox(_("needs_sponsor"), bool(auth.get("needs_sponsorship")))
    prefs["reject_if_enrollment_required"] = c2.checkbox(_("enroll"), bool(prefs.get("reject_if_enrollment_required", True)))
    prefs["reject_if_offline_only"] = c1.checkbox(_("offline"), bool(prefs.get("reject_if_offline_only", True)))
    writing = profile.setdefault("writing", {})
    writing["willing_to_relocate"] = c2.checkbox(_("relocate"), bool(writing.get("willing_to_relocate")))

    def lines(key, label, col=st):
        val = col.text_area(label, "\n".join(prefs.get(key, [])), height=110)
        prefs[key] = [b.strip() for b in val.splitlines() if b.strip()]

    d1, d2, d3 = st.columns(3)
    lines("target_roles", _("target_roles"), d1)
    lines("stretch_role_keywords", _("stretch"), d2)
    lines("excluded_role_keywords", _("excluded"), d3)
    lines("blocked_companies", _("blocked"))

    st.markdown(f"#### {_('limits')}")
    st.caption(_("limits_help"))
    lim = st.data_editor(pd.DataFrame(prefs.get("application_limits") or [], columns=["company", "max", "period_days", "note"]),
                         num_rows="dynamic", hide_index=True, width="stretch", key="limits")
    prefs["application_limits"] = [
        {k: (int(v) if k in ("max", "period_days") and str(v).strip() not in ("", "nan", "None") else ("" if pd.isna(v) else v))
         for k, v in r.items()} for r in lim.to_dict("records") if str(r.get("company") or "").strip()]

    st.markdown(f"#### {_('profile_json')}")
    st.caption(_("profile_help"))
    raw = st.text_area("profile", json.dumps(profile, ensure_ascii=False, indent=2), height=480,
                       label_visibility="collapsed")
    b1, b2 = st.columns(2)
    if b1.button(_("save_profile"), type="primary"):
        try:
            new = json.loads(raw)
            new["preferences"], new["work_authorization"], new["writing"] = prefs, auth, writing
            save_profile(new)
            st.session_state.profile = new
            st.success(_("profile_saved"))
        except json.JSONDecodeError as e:
            st.error(_("json_error") + str(e))
    if b2.button(_("reset_demo")):
        save_profile(json.loads(json.dumps(DEMO_PROFILE)))
        st.session_state.profile = load_profile()
        st.rerun()


# ------------------------------------------------------------------ import / export
def page_data():
    st.header(_("nav_data"))
    rows = tracker.all_rows()
    st.markdown(f"#### {_('export')}")
    if rows:
        df = pd.DataFrame(rows)
        st.download_button("CSV", df.to_csv(index=False).encode("utf-8-sig"), "applymate.csv", "text/csv")
        st.download_button("JSON", json.dumps(rows, ensure_ascii=False, indent=2).encode(), "applymate.json",
                           "application/json")
    st.markdown(f"#### {_('import')}")
    replace = st.checkbox(_("replace"))
    up = st.file_uploader("CSV / JSON", type=["csv", "json"])
    if up and st.button(_("import")):
        data = json.load(up) if up.name.endswith(".json") else pd.read_csv(io.BytesIO(up.read())).fillna("").to_dict("records")
        st.success(_("imported") + str(tracker.import_rows(data, replace=replace)))


{"nav_screen": page_screen, "nav_tracker": page_tracker, "nav_profile": page_profile, "nav_data": page_data}[page]()
