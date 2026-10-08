"""Registro de candidaturas: data/candidaturas.csv, editado por você (VS Code ou site do GitHub).

Colunas: id,status,data,observacao
  id      → o ID da vaga (botão "copiar" no relatório)
  status  → aplicado | entrevista | recusado | oferta | encerrada | ignorar
            (encerrada = vaga preenchida, link quebrado ou sem candidatura possível)
"""
import csv
import os

STATUS = {"aplicado": "applied", "entrevista": "interview", "recusado": "rejected",
          "oferta": "offer", "encerrada": "closed", "ignorar": "ignored"}
PATH = "data/candidaturas.csv"


def apply(con, path=PATH):
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write("id,status,data,observacao\n")
        return 0
    cols = {r[1] for r in con.execute("PRAGMA table_info(jobs)")}
    for c in ("applied_at", "notes"):
        if c not in cols:
            con.execute(f"ALTER TABLE jobs ADD COLUMN {c} TEXT")
    n = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            job_id = (row.get("id") or "").strip()
            st = (row.get("status") or "").strip().lower()
            if not job_id:
                continue
            if st not in STATUS:
                print(f"  ! candidaturas.csv linha {i}: status '{st}' inválido (use {', '.join(STATUS)})")
                continue
            cur = con.execute("UPDATE jobs SET status=?, applied_at=?, notes=?, notified=1 WHERE id=?",
                              (STATUS[st], (row.get("data") or "").strip(), (row.get("observacao") or "").strip(), job_id))
            if cur.rowcount == 0:
                print(f"  ! candidaturas.csv linha {i}: vaga '{job_id}' não encontrada no banco")
            else:
                n += 1
    return n


def register_auto(con, applied, path=PATH):
    """Candidaturas confirmadas por e-mail do LinkedIn → linha 'aplicado' no CSV (se ainda não houver)."""
    if not applied:
        return 0
    import datetime as dt
    known = set()
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8-sig") as f:
            known = {(r.get("id") or "").strip() for r in csv.DictReader(f)}
    added = []
    for a in applied:
        job_id = f"linkedin:{a['id']}"
        if job_id in known:
            continue
        if not con.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone():
            con.execute("""INSERT INTO jobs (id, dedupe_key, source, ext_id, title, company, location, remote, url,
                           description, tags, posted_at, first_seen, heur_score, heur_reasons, status, region, notified)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                        (job_id, job_id, "linkedin", a["id"], a.get("title") or "(vaga do LinkedIn)",
                         a.get("company") or "", a.get("location") or "", 0,
                         f"https://www.linkedin.com/jobs/view/{a['id']}/", "", "candidatura via LinkedIn",
                         a.get("date", ""), dt.date.today().isoformat(), 0, "registrada pelo e-mail", "applied",
                         None))
        added.append([job_id, "aplicado", a.get("date", ""), "auto: e-mail do LinkedIn"])
        known.add(job_id)
    if added:
        new_file = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            if new_file:
                f.write("id,status,data,observacao\n")
            csv.writer(f).writerows(added)
    return len(added)
