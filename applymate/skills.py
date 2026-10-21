"""Skill taxonomy: canonical skill names and the phrases that signal them in a JD."""
from __future__ import annotations

import re

# canonical name -> regex alternatives (lower-case). Word boundaries are added
# automatically for ASCII patterns; Chinese patterns are matched as substrings.
TAXONOMY: dict[str, list[str]] = {
    "Python": [r"python", r"pandas", r"numpy"],
    "SQL": [r"sql", r"mysql", r"postgres(?:ql)?", r"hive ?ql"],
    "R": [r"\br\b(?! ?&)", r"rstudio", r"r shiny"],
    "Excel": [r"excel", r"spreadsheets?"],
    "VBA": [r"vba"],
    "Tableau": [r"tableau"],
    "Power BI": [r"power ?bi"],
    "Spark": [r"spark", r"pyspark", r"databricks"],
    "Hadoop/Hive": [r"hadoop", r"\bhive\b", r"map ?reduce"],
    "AWS": [r"\baws\b", r"amazon web services", r"\bs3\b", r"redshift"],
    "Azure": [r"azure"],
    "GCP": [r"\bgcp\b", r"google cloud", r"bigquery"],
    "Git": [r"\bgit\b", r"github", r"version control"],
    "Machine Learning": [r"machine learning", r"\bml\b", r"机器学习", r"random forest", r"xgboost",
                          r"decision tree", r"classification", r"regression model"],
    "Deep Learning": [r"deep learning", r"pytorch", r"tensorflow", r"neural net", r"深度学习"],
    "Statistics": [r"statistic", r"统计", r"hypothesis test", r"inference"],
    "A/B Testing": [r"a/?b test", r"experiment(?:ation|al design|s)?", r"实验设计", r"ab ?实验"],
    "Causal Inference": [r"causal", r"因果"],
    "Time Series": [r"time[- ]series", r"forecast", r"时间序列"],
    "Data Visualization": [r"visuali[sz]", r"dashboard", r"看板", r"可视化"],
    "LLM / GenAI": [r"\bllm", r"large language model", r"generative ai", r"genai", r"大模型",
                     r"prompt", r"\brag\b", r"agent", r"智能体"],
    "Product Management": [r"product manag", r"roadmap", r"backlog", r"产品经理", r"需求文档", r"\bprd\b"],
    "Stakeholder Management": [r"stakeholder", r"cross[- ]functional", r"跨部门"],
    "Financial Modeling": [r"financial model", r"\bdcf\b", r"valuation", r"\blbo\b", r"估值"],
    "Risk Management": [r"risk", r"风控", r"风险"],
    "Backtesting": [r"backtest", r"回测"],
    "Communication": [r"communicat", r"沟通", r"presentation"],
    "Mandarin": [r"mandarin", r"chinese", r"中文", r"普通话"],
    "C++": [r"c\+\+"],
    "Java": [r"\bjava\b"],
    "CFA": [r"\bcfa\b"],
}

_COMPILED = {
    name: [re.compile(p if p.startswith("\\b") or not p.isascii() else rf"(?<![a-z]){p}", re.I) for p in pats]
    for name, pats in TAXONOMY.items()
}


def skills_in(text: str) -> set[str]:
    """Canonical skills mentioned anywhere in text."""
    found = set()
    for name, pats in _COMPILED.items():
        if any(p.search(text) for p in pats):
            found.add(name)
    return found


def normalize(skill: str) -> str:
    """Map a free-text skill from the user's profile to its canonical name if we know it."""
    hits = skills_in(skill)
    if len(hits) == 1:
        return hits.pop()
    for name in TAXONOMY:
        if name.lower() == skill.strip().lower():
            return name
    return skill.strip()
