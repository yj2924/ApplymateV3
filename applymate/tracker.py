"""SQLite application tracker."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from .profile import DATA_DIR

DB_PATH = DATA_DIR / "applications.db"
STATUSES = ["Saved", "Applied", "Online Assessment", "Interview", "Offer", "Rejected", "Withdrawn"]
COLUMNS = ["company", "role", "location", "url", "status", "verdict", "preferred_rate",
           "applied_on", "deadline", "follow_up_on", "notes", "jd_text", "resume_md", "cover_letter"]


def _conn(path: Path | None = None) -> sqlite3.Connection:
    path = path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.execute(f"""CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        {", ".join(f"{col} TEXT" for col in COLUMNS)},
        created_at TEXT, updated_at TEXT)""")
    return c


def add(record: dict, path: Path | None = None) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    rec = {k: record.get(k, "") for k in COLUMNS}
    rec["status"] = rec["status"] or "Saved"
    if rec["status"] == "Applied" and not rec["applied_on"]:
        rec["applied_on"] = date.today().isoformat()
    if rec["applied_on"] and not rec["follow_up_on"]:
        rec["follow_up_on"] = (date.fromisoformat(rec["applied_on"]) + timedelta(days=7)).isoformat()
    with _conn(path) as c:
        cur = c.execute(
            f"INSERT INTO applications ({', '.join(COLUMNS)}, created_at, updated_at) "
            f"VALUES ({', '.join('?' * (len(COLUMNS) + 2))})",
            [rec[k] for k in COLUMNS] + [now, now])
        return cur.lastrowid


def update(app_id: int, fields: dict, path: Path | None = None) -> None:
    fields = {k: v for k, v in fields.items() if k in COLUMNS}
    if fields.get("status") == "Applied" and not fields.get("applied_on"):
        current = get(app_id, path)
        if current and not current.get("applied_on"):
            fields["applied_on"] = date.today().isoformat()
            fields.setdefault("follow_up_on", (date.today() + timedelta(days=7)).isoformat())
    if not fields:
        return
    fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
    with _conn(path) as c:
        c.execute(f"UPDATE applications SET {', '.join(f'{k}=?' for k in fields)} WHERE id=?",
                  list(fields.values()) + [app_id])


def delete(app_id: int, path: Path | None = None) -> None:
    with _conn(path) as c:
        c.execute("DELETE FROM applications WHERE id=?", (app_id,))


def get(app_id: int, path: Path | None = None) -> dict | None:
    with _conn(path) as c:
        row = c.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
    return dict(row) if row else None


def all_rows(path: Path | None = None) -> list[dict]:
    with _conn(path) as c:
        return [dict(r) for r in c.execute("SELECT * FROM applications ORDER BY updated_at DESC")]


def import_rows(rows: list[dict], replace: bool = False, path: Path | None = None) -> int:
    with _conn(path) as c:
        if replace:
            c.execute("DELETE FROM applications")
    for r in rows:
        add({k: ("" if r.get(k) is None else str(r.get(k))) for k in COLUMNS}, path)
    return len(rows)


def due_soon(rows: list[dict], days: int = 7) -> list[dict]:
    """Deadlines or follow-ups within `days`, for still-open applications."""
    today = date.today()
    out = []
    for r in rows:
        if r["status"] in ("Offer", "Rejected", "Withdrawn"):
            continue
        for kind in ("deadline", "follow_up_on"):
            try:
                d = date.fromisoformat(r.get(kind) or "")
            except ValueError:
                continue
            if r["status"] != "Saved" and kind == "deadline":
                continue  # deadline no longer matters once applied
            if kind == "follow_up_on" and r["status"] == "Saved":
                continue
            if d <= today + timedelta(days=days):
                out.append({"id": r["id"], "company": r["company"], "role": r["role"],
                            "kind": kind, "date": d.isoformat(), "overdue": d < today})
    return sorted(out, key=lambda x: x["date"])
