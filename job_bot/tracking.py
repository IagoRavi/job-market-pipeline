"""Registro de candidaturas: data/candidaturas.csv, editado por você (VS Code ou site do GitHub).

Colunas: id,status,data,observacao
  id      → o ID da vaga (botão "copiar" no relatório)
  status  → aplicado | entrevista | recusado | oferta | ignorar
"""
import csv
import os

STATUS = {"aplicado": "applied", "entrevista": "interview", "recusado": "rejected",
          "oferta": "offer", "ignorar": "ignored"}
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
