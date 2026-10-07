import csv
import hashlib
import re
import sqlite3
from datetime import date

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, dedupe_key TEXT, source TEXT, ext_id TEXT, title TEXT, company TEXT,
  location TEXT, remote INTEGER, url TEXT, description TEXT, tags TEXT, posted_at TEXT,
  salary_min_eur REAL, salary_max_eur REAL, salary_raw TEXT, first_seen TEXT,
  heur_score INTEGER, heur_reasons TEXT, llm_score INTEGER, llm_summary TEXT,
  llm_red_flags TEXT, cv_variant TEXT, region TEXT, status TEXT DEFAULT 'new', notified INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_dedupe ON jobs(dedupe_key);
"""
# status: new | below_floor | discard | applied | interview | rejected | offer | ignored


def connect(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(jobs)")}
    if "region" not in cols:  # banco criado na versão anterior
        con.execute("ALTER TABLE jobs ADD COLUMN region TEXT")
    return con


def dedupe_key(job):
    base = re.sub(r"[^a-z0-9]", "", (job["company"] + job["title"]).lower())
    return hashlib.sha1(base.encode()).hexdigest()[:16]


def insert_if_new(con, job, score, reasons, status, region=None):
    job_id = f"{job['source']}:{job['ext_id']}"
    key = dedupe_key(job)
    if con.execute("SELECT 1 FROM jobs WHERE id=? OR dedupe_key=?", (job_id, key)).fetchone():
        return False
    con.execute(
        """INSERT INTO jobs (id, dedupe_key, source, ext_id, title, company, location, remote, url,
           description, tags, posted_at, salary_min_eur, salary_max_eur, salary_raw, first_seen,
           heur_score, heur_reasons, status, region) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (job_id, key, job["source"], job["ext_id"], job["title"], job["company"], job["location"],
         job["remote"], job["url"], job["description"], job["tags"], job["posted_at"],
         job["salary_min_eur"], job["salary_max_eur"], job["salary_raw"], date.today().isoformat(),
         score, "; ".join(reasons), status, region))
    return True


def export_csv(con, path):
    """CSV sem descrição, pronto para o Power BI."""
    cols = ["id", "source", "title", "company", "location", "remote", "url", "posted_at", "first_seen",
            "region", "salary_min_eur", "salary_max_eur", "heur_score", "llm_score", "cv_variant", "status",
            "heur_reasons", "llm_summary", "applied_at", "notes"]
    have = {r[1] for r in con.execute("PRAGMA table_info(jobs)")}
    sel = ", ".join(c if c in have else f"NULL AS {c}" for c in cols)
    rows = con.execute(f"SELECT {sel} FROM jobs WHERE status != 'discard'").fetchall()
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows([tuple(r) for r in rows])
