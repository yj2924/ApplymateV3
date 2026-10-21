import copy

import pytest

from applymate.jd_parser import min_years_required, parse_jd
from applymate.profile import DEMO_PROFILE
from applymate.samples import SAMPLES
from applymate.screening import FAIL, PASS, screen
from applymate.tailor import draft_cover_letter, tailor, unsupported_numbers
from applymate import tracker


@pytest.fixture
def profile():
    return copy.deepcopy(DEMO_PROFILE)


def test_parser_splits_sections():
    jd = parse_jd(SAMPLES["Data Scientist, New Grad (good fit)"]["jd"])
    assert len(jd.required) == 3 and len(jd.preferred) == 3 and len(jd.responsibilities) == 3


def test_parser_handles_chinese_numbered_items():
    jd = parse_jd(SAMPLES["数据分析师（中文 JD）"]["jd"])
    assert len(jd.required) == 3 and len(jd.preferred) == 3


@pytest.mark.parametrize("line,years", [
    ("3+ years of experience in analytics", 3),
    ("5-8 years of product management experience", 5),
    ("2 年以上工作经验", 2),
    ("Experience with Python", None),
])
def test_years(line, years):
    got = min_years_required([line])
    assert (got[0] if got else None) == years


def test_good_fit_recommended(profile):
    s = SAMPLES["Data Scientist, New Grad (good fit)"]
    r = screen(parse_jd(s["jd"]), profile, s["company"])
    assert r.verdict == "recommended" and r.preferred_rate == 1.0


def test_no_sponsorship_and_years_fail(profile):
    s = SAMPLES["Senior Analyst (hard fail)"]
    r = screen(parse_jd(s["jd"]), profile, s["company"])
    assert r.verdict == "do_not_apply"
    hard = [c for c in r.checks if c.category == "hard" and c.status == FAIL]
    assert len(hard) == 2


def test_sponsorship_ignored_for_citizens(profile):
    profile["work_authorization"]["needs_sponsorship"] = False
    profile["preferences"]["max_years_required"] = 5
    s = SAMPLES["Senior Analyst (hard fail)"]
    r = screen(parse_jd(s["jd"]), profile, s["company"])
    assert not any(c.category == "hard" and c.status == FAIL for c in r.checks)


def test_blocked_company(profile):
    profile["preferences"]["blocked_companies"] = ["Acme"]
    s = SAMPLES["Data Scientist, New Grad (good fit)"]
    assert screen(parse_jd(s["jd"]), profile, "Acme Analytics").verdict == "do_not_apply"


def test_graduation_window_outside(profile):
    profile["graduation"] = "2025-05"
    s = SAMPLES["Data Scientist, New Grad (good fit)"]
    r = screen(parse_jd(s["jd"]), profile, s["company"])
    assert r.verdict == "do_not_apply"


def test_enrollment_required(profile):
    jd = parse_jd("Requirements\n- Must be currently enrolled in a degree program\n- Python")
    assert screen(jd, profile).verdict == "do_not_apply"


def test_low_preferred_rate(profile):
    s = SAMPLES["数据分析师（中文 JD）"]
    r = screen(parse_jd(s["jd"]), profile, s["company"])
    assert r.verdict == "not_recommended" and r.preferred_rate < 0.8


def test_never_skill_not_shown(profile):
    jd = parse_jd("Requirements\n- SAS and Python")
    assert "SAS" not in tailor(jd, profile).skills


def test_if_required_skill_only_when_asked(profile):
    assert "Mandarin" not in tailor(parse_jd("Requirements\n- Python"), profile).skills
    assert "Mandarin" in tailor(parse_jd("Requirements\n- Python and Mandarin"), profile).skills


def test_letter_uses_only_profile_numbers_and_no_dashes(profile):
    s = SAMPLES["Data Scientist, New Grad (good fit)"]
    jd = parse_jd(s["jd"])
    r = screen(jd, profile, s["company"])
    letter = draft_cover_letter(s["company"], s["role"], jd, profile, tailor(jd, profile), r.missing_skills)
    assert unsupported_numbers(letter, profile) == []
    assert "—" not in letter and "–" not in letter


def test_fact_guard_flags_invented_number(profile):
    assert unsupported_numbers("I improved revenue by 37%", profile) == ["37%"]


def test_tracker_roundtrip(tmp_path):
    db = tmp_path / "t.db"
    i = tracker.add({"company": "A", "role": "DS", "status": "Applied"}, db)
    rec = tracker.get(i, db)
    assert rec["applied_on"] and rec["follow_up_on"]
    tracker.update(i, {"status": "Interview"}, db)
    assert tracker.get(i, db)["status"] == "Interview"
    assert tracker.import_rows([{"company": "B", "role": "DA"}], path=db) == 1
    assert len(tracker.all_rows(db)) == 2


# ---------------------------------------------------------------- v1.1: rules from the original workflow
from datetime import date  # noqa: E402

from applymate import export  # noqa: E402
from applymate.screening import WARN  # noqa: E402

GOOD = SAMPLES["Data Scientist, New Grad (good fit)"]


def _hard(r, status):
    return [c for c in r.checks if c.category == "hard" and c.status == status]


def test_excluded_direction_blocks(profile):
    r = screen(parse_jd(GOOD["jd"]), profile, GOOD["company"], role="Research Scientist, NLP")
    assert r.verdict == "do_not_apply" and "research scientist" in _hard(r, FAIL)[0].detail


def test_internship_title_blocked_but_internal_is_not(profile):
    jd = parse_jd(GOOD["jd"])
    assert screen(jd, profile, role="Data Science Internship").verdict == "do_not_apply"
    assert screen(jd, profile, role="Internal Audit Data Analyst").verdict != "do_not_apply"


def test_stretch_direction_is_flagged_not_blocked(profile):
    r = screen(parse_jd(GOOD["jd"]), profile, GOOD["company"], role="Quantitative Researcher")
    assert r.verdict == "caution" and _hard(r, WARN)


def test_target_direction_passes(profile):
    r = screen(parse_jd(GOOD["jd"]), profile, GOOD["company"], role="Data Scientist, New Grad")
    assert r.verdict == "recommended" and _hard(r, PASS)


def test_application_limit(profile):
    today = date.today().isoformat()
    history = [{"company": "Initech", "status": "Applied", "applied_on": today},
               {"company": "Initech Labs", "status": "Interview", "applied_on": today}]
    r = screen(parse_jd(GOOD["jd"]), profile, "Initech", history=history)
    assert r.verdict == "do_not_apply" and "2 of 2" in _hard(r, FAIL)[0].detail
    r = screen(parse_jd(GOOD["jd"]), profile, "Initech", history=history[:1])
    assert r.verdict != "do_not_apply"


def test_staffing_firm_warns(profile):
    jd = parse_jd("We are a staffing agency hiring on behalf of our client.\n" + GOOD["jd"])
    assert screen(jd, profile, "TalentCo").verdict == "caution"


def test_offline_only_assessment_fails_but_online_option_warns(profile):
    jd = parse_jd("笔试安排：统一线下笔试，地点北京。\n" + GOOD["jd"])
    assert screen(jd, profile).verdict == "do_not_apply"
    jd = parse_jd("笔试安排：线下笔试，海外同学可线上参加。\n" + GOOD["jd"])
    assert screen(jd, profile).verdict == "caution"


def test_sql_bullets_follow_sql_rule(profile):
    no_sql = tailor(parse_jd("Requirements\n- Python and statistics"), profile, max_bullets=9)
    with_sql = tailor(parse_jd("Requirements\n- Python and SQL"), profile, max_bullets=9)
    text = lambda t: " ".join(b["text"] for x in t.experiences for b in x["bullets"])  # noqa: E731
    assert "SQL" not in text(no_sql) and "SQL" not in no_sql.skills
    assert "Queried order history in SQL" in text(with_sql) and "SQL" in with_sql.skills
    assert "reconcile 15 transaction tables" not in text(with_sql)  # show: never


def test_letter_mentions_relocation(profile):
    jd = parse_jd(GOOD["jd"])
    letter = draft_cover_letter("Acme", "DS", jd, profile, tailor(jd, profile), [])
    assert "open to relocating" in letter
    profile["writing"]["willing_to_relocate"] = False
    assert "relocat" not in draft_cover_letter("Acme", "DS", jd, profile, tailor(jd, profile), [])


def test_file_name_has_company_and_role(profile):
    assert export.file_stem(profile, "resume", "Acme", "Data Scientist / ML") == "Alex Chen resume Acme Data Scientist ML"


def test_demo_resume_is_one_page_in_both_languages(profile):
    t = tailor(parse_jd(GOOD["jd"]), profile)
    for lang in ("en", "zh"):
        assert export.page_count(profile, t, lang) == 1
        assert export.resume_pdf(profile, t, lang).startswith(b"%PDF")
        assert export.resume_docx(profile, t, lang)[:2] == b"PK"


def test_chinese_resume_uses_chinese_fields(profile):
    md = export.resume_markdown(profile, tailor(parse_jd(GOOD["jd"]), profile), "zh")
    assert "## 实习经历" in md and "统计学硕士，GPA" in md and "2025.09 – 2026.12" in md


def test_fit_one_page_trims_overlong_resume(profile):
    long = {"text": "Built and validated a statistical model on a large dataset with Python and documented every "
                    "assumption for review by the analytics team and business stakeholders", "skills": ["Python"]}
    profile["experiences"] = [{**profile["experiences"][0], "org": f"Org {i}", "bullets": [long] * 5} for i in range(6)]
    t = tailor(parse_jd(GOOD["jd"]), profile, max_bullets=5)
    assert export.page_count(profile, t) > 1
    fitted, removed = export.fit_one_page(profile, t)
    assert export.page_count(profile, fitted) == 1 and removed
    assert len(fitted.experiences) == 6  # never drops a whole job
