"""Digest diário: arquivo Markdown no repositório + e-mail opcional."""
import html
import re
import os
import smtplib
from datetime import date
from email.mime.text import MIMEText

QUERY = """SELECT *, COALESCE(llm_score, heur_score) AS final FROM jobs
WHERE status='new' AND notified=0 AND COALESCE(llm_score, heur_score) >= ?
ORDER BY final DESC"""

REGIONS = [("EU", "🇪🇺 Europa"), ("GLOBAL", "🌍 Remoto global / LATAM"), ("BR", "🇧🇷 Brasil"), ("OUTRA", "Outras")]


def _salary(j):
    lo, hi = j["salary_min_eur"], j["salary_max_eur"]
    if not (lo or hi):
        return "não divulgado"
    return f"€{(lo or hi):,.0f}–{(hi or lo):,.0f}/ano".replace(",", ".")


def _item(j):
    blob = (j["title"] + " " + (j["description"] or "")).lower()
    variant = j["cv_variant"] or ("BI" if re.search(r"\bbi\b|power bi|business intelligence|dashboard", blob) else "DA")
    cv = {"BI": "CV BI Developer", "DA": "CV Data Analyst"}[variant]
    if j["region"] == "BR":
        cv = "CV em português"
    why = j["llm_summary"] or j["heur_reasons"]
    flags = f"\n  - ⚠️ {j['llm_red_flags']}" if j["llm_red_flags"] else ""
    md = [f"### [{j['final']}] {j['title']} — {j['company']}",
          f"- {j['location'] or '—'} · {'remoto' if j['remote'] else 'presencial/híbrido'} · {_salary(j)} · {j['source']}",
          f"- {cv} · {why}{flags}", f"- {j['url']}", ""]
    li = (f"<li><b>[{j['final']}] <a href='{html.escape(j['url'] or '')}'>{html.escape(j['title'])}</a></b>"
          f" — {html.escape(j['company'])}<br><small>{html.escape(j['location'] or '')} · {_salary(j)} · {cv}"
          f"<br>{html.escape(why or '')}</small></li>")
    return md, li


def build(con, cfg):
    rows = con.execute(QUERY, (cfg["digest"]["min_score"],)).fetchall()
    per_region = cfg["digest"].get("max_per_region", 10)
    today = date.today().isoformat()
    md, body, sent = [f"# Vagas — {today}", ""], [], []
    for code, label in REGIONS:
        group = [j for j in rows if (j["region"] or "OUTRA") == code][:per_region]
        if not group:
            continue
        md += [f"## {label} ({len(group)})", ""]
        body.append(f"<h3>{label}</h3><ol>")
        for j in group:
            m, li = _item(j)
            md += m
            body.append(li)
            sent.append(j)
        body.append("</ol>")
    from datetime import datetime
    md[0] = f"# Vagas — {today} · execução das {datetime.now():%H:%M}"
    md.insert(2, f"{len(sent)} vagas novas com nota ≥ {cfg['digest']['min_score']}.\n")
    os.makedirs("digests", exist_ok=True)
    path = f"digests/{today}.md"
    prev = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    with open(path, "w", encoding="utf-8") as f:  # execuções do mesmo dia ficam no mesmo arquivo, a mais recente no topo
        f.write("\n".join(md) + ("\n\n---\n\n" + prev if prev else ""))
    link = cfg["digest"].get("report_url")
    if link:
        body.insert(0, f"<p><a href='{html.escape(link)}'>Abrir relatório completo</a></p>")
    if sent:
        _email(f"Robô de vagas: {len(sent)} novas ({today})", "".join(body))
    con.executemany("UPDATE jobs SET notified=1 WHERE id=?", [(j["id"],) for j in sent])
    return len(sent)


def _email(subject, body_html):
    host, user, pwd, to = (os.getenv(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "DIGEST_TO"))
    if not all([host, user, pwd, to]):
        print("  - e-mail não configurado, digest só no repositório")
        return
    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    with smtplib.SMTP_SSL(host, int(os.getenv("SMTP_PORT", "465"))) as s:
        s.login(user, pwd)
        s.send_message(msg)
    print(f"  - e-mail enviado para {to}")
