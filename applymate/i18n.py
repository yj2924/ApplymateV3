"""Tiny bilingual string table (English / 简体中文)."""

STRINGS = {
    "nav_screen": ("Screen a job", "岗位筛选与材料"),
    "nav_tracker": ("Tracker", "投递追踪"),
    "nav_profile": ("Profile & rules", "档案与规则"),
    "nav_data": ("Import / export", "导入 / 导出"),
    "language": ("Language", "语言"),
    "api_key": ("Anthropic API key (optional)", "Anthropic API Key（可选）"),
    "api_help": ("Without a key everything runs on the rule engine. With a key, Claude parses the JD into "
                 "structured JSON and polishes the letter; any AI output that fails validation is discarded.",
                 "不填也能完整使用（规则引擎）。填了会用 Claude 把 JD 解析成结构化 JSON 并润色求职信；"
                 "未通过校验的 AI 输出会被自动丢弃。"),
    "demo_banner": ("You are using the demo profile (a fictional candidate). Replace it in Profile & rules.",
                    "当前是示例档案（虚构候选人）。请到「档案与规则」换成你自己的信息。"),
    "company": ("Company", "公司"), "role": ("Role", "岗位"), "location": ("Location", "地点"),
    "url": ("Job link", "岗位链接"), "deadline": ("Deadline", "截止日期"),
    "jd": ("Paste the job description", "粘贴职位描述 (JD)"),
    "load_sample": ("Load a sample JD", "载入示例 JD"),
    "why_company": ("Why this company? (one specific sentence, optional)", "为什么是这家公司？（一句具体的话，可选）"),
    "run": ("Run screening", "开始筛选"),
    "verdict": ("Verdict", "结论"),
    "v_recommended": ("✅ Recommended", "✅ 推荐投递"),
    "v_caution": ("⚠️ Apply with caution", "⚠️ 谨慎投递"),
    "v_not_recommended": ("🟠 Not recommended (preferred hit rate too low)", "🟠 不推荐（加分项命中率过低）"),
    "v_do_not_apply": ("⛔ Do not apply (hard requirement failed)", "⛔ 不投（硬性条件不满足）"),
    "pref_rate": ("Preferred-qualification hit rate", "加分项命中率"),
    "checklist": ("Requirement checklist", "逐条资格核对"),
    "cat_hard": ("Hard rule", "硬性条件"), "cat_required": ("Required", "必须项"), "cat_preferred": ("Preferred", "加分项"),
    "requirement": ("Requirement (from JD)", "JD 原文"), "status": ("Status", "状态"), "evidence": ("Evidence / gap", "依据 / 差距"),
    "missing": ("Skills the JD asks for that you do not have", "JD 要求而你没有的技能"),
    "resume": ("Tailored resume", "定制简历"), "letter": ("Cover letter", "求职信"),
    "skills_field": ("Skills to paste into the application form", "网申表 Skills 栏可直接粘贴"),
    "download_resume": ("Download resume (.docx)", "下载简历 (.docx)"),
    "download_letter": ("Download cover letter (.docx)", "下载求职信 (.docx)"),
    "fact_check": ("Fact check", "事实校验"),
    "fact_ok": ("Every number in the letter appears in your profile.", "求职信中的每个数字都能在档案中找到。"),
    "fact_bad": ("Numbers not found in your profile: ", "档案中找不到的数字："),
    "save": ("Save to tracker", "保存到追踪表"), "saved": ("Saved as #", "已保存，编号 #"),
    "status_label": ("Status", "状态"),
    "no_apps": ("No applications yet. Screen a job first.", "还没有记录，先去筛选一个岗位。"),
    "metrics_total": ("Tracked", "总数"), "metrics_applied": ("Applied", "已投"),
    "metrics_interview": ("Interviews", "面试"), "metrics_offer": ("Offers", "Offer"),
    "due": ("Due in the next 7 days", "未来 7 天待办"), "overdue": ("overdue", "已逾期"),
    "kind_deadline": ("application deadline", "申请截止"), "kind_follow_up_on": ("follow up", "跟进"),
    "edit": ("Edit an application", "编辑记录"), "update": ("Update", "更新"), "delete": ("Delete", "删除"),
    "notes": ("Notes", "备注"), "follow_up": ("Follow-up date", "跟进日期"),
    "profile_json": ("Full profile (JSON)", "完整档案（JSON）"),
    "profile_help": ("Bullets are the only facts ApplyMate may use. Tag each bullet with skills so screening "
                     "can cite evidence. Skill `show`: always | if_required | never; add `bullets_too: true` to apply the "
                     "rule to bullets that mention the skill. Bullet options: `show: never`, `only_if_jd_has: [skills]`. "
                     "Add `*_zh` fields (e.g. `org_zh`, `text_zh`) for the Chinese resume.",
                     "经历要点是 ApplyMate 唯一能用的事实来源。给每条要点打上技能标签，筛选时才能引用证据。"
                     "技能 show 字段：always 一直写 | if_required 只在 JD 必须项要求时写 | never 永不写；加 `bullets_too: true` 后，"
                     "提到该技能的经历要点也按同样规则隐藏。单条要点可设 `show: never` 或 `only_if_jd_has: [技能]`。"
                     "加上 `*_zh` 字段（如 `org_zh`、`text_zh`）即可生成中文简历。"),
    "rules": ("Screening rules", "筛选规则"),
    "max_years": ("Max years of experience you accept", "可接受的最高经验年限要求"),
    "threshold": ("Minimum preferred hit rate", "加分项最低命中率"),
    "blocked": ("Blocked companies (one per line)", "不投的公司（每行一个）"),
    "needs_sponsor": ("I need visa sponsorship", "我需要签证担保"),
    "enroll": ("Reject roles that require current enrollment", "排除要求在读的岗位"),
    "save_profile": ("Save profile", "保存档案"), "reset_demo": ("Reset to demo profile", "恢复示例档案"),
    "profile_saved": ("Profile saved.", "档案已保存。"), "json_error": ("Invalid JSON: ", "JSON 格式错误："),
    "export": ("Export", "导出"), "import": ("Import", "导入"), "replace": ("Replace existing records", "清空后替换"),
    "imported": ("Imported rows: ", "已导入条数："),
    "parser_note": ("Parser", "解析方式"),
    "resume_lang": ("Resume language", "简历语言"),
    "auto_trimmed": ("Trimmed to fit one page: ", "为控制在一页已自动去掉："),
    "editor_help": ("Tick or untick bullets, or edit their wording. Only rewrite facts that are already true; "
                    "the fact check flags any number not in your profile.",
                    "勾选或取消要点，也可以直接改措辞。只能改写已有的真实经历；出现档案里没有的数字会被标红。"),
    "col_use": ("Use", "使用"), "col_where": ("Experience / project", "经历 / 项目"), "col_text": ("Bullet", "要点"),
    "one_page_ok": ("Fits on one page.", "一页以内。"),
    "one_page_bad": ("Needs {} pages. Untick a bullet or shorten one.", "需要 {} 页，请取消或缩短一些要点。"),
    "download_pdf": ("Download resume (.pdf)", "下载简历 (.pdf)"),
    "preview": ("Preview", "预览"),
    "offline": ("Reject roles whose test or interview must be in person", "排除笔试或面试只能线下参加的岗位"),
    "relocate": ("Say I am open to relocating in cover letters", "求职信中写明愿意搬迁"),
    "target_roles": ("Target directions (one per line)", "目标方向（每行一个）"),
    "stretch": ("Stretch directions (flagged, not blocked)", "冲刺方向（提示但不排除）"),
    "excluded": ("Excluded role keywords", "排除的岗位关键词"),
    "limits": ("Application limits per company", "各公司投递上限"),
    "limits_help": ("Counted from your tracker (anything beyond Saved). period_days defaults to 365.",
                    "按追踪表里已投递（不含「已保存」）的记录计数。period_days 留空默认 365 天。"),
}


def t(key: str, lang: str) -> str:
    en, zh = STRINGS.get(key, (key, key))
    return zh if lang == "zh" else en
