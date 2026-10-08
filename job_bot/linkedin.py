"""LinkedIn via e-mail (sem acessar o LinkedIn): lê a sua caixa do Gmail por IMAP.

1. Alertas de vaga  → vagas novas (título, empresa, local, modelo, salário, Candidatura simplificada).
2. Confirmações de candidatura ("your application was sent to…") → registro automático
   em data/candidaturas.csv como 'aplicado'.
"""
import datetime as dt
import email
import imaplib
import os
import re
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from .common import AuthError, clean_html

JOB_ID = re.compile(r"linkedin\.com/(?:comm/)?jobs/view/(?:[^/\s\"'?]*-)?(\d{6,})")
SALARY = re.compile(r"([€$£]|R\$|brl|eur|usd)\s?[\d.,]+\s?[kK]?.*?(/\s?(yr|ano|mo|mês|mes|hr|hora)|per|por)?", re.I)
APPLIED_SUBJECT = re.compile(r"application was sent|candidatura foi enviada|you applied|você se candidatou", re.I)
ALERT_NAME = re.compile(r"(?:job alert for|alerta de vagas? (?:para|de))\s+[\"“]?(.+?)[\"”]?(?:\s+(?:in|em)\s+(.+))?$", re.I)

NOISE = re.compile(
    r"^(view job|ver vaga|see all jobs|ver todas|apply|candidate-se|promoted|promovida|"
    r"this company is actively hiring|esta empresa está contratando|actively recruiting|recrutando ativamente|"
    r"be an early applicant|seja um dos primeiros|new|nova|top applicant|\d+\s*(connections?|conex|school alumni|"
    r"company alumni|ex-alunos|applicants?|candidaturas?|candidatos?)|.*alumni work here|.*ex-alunos trabalham)",
    re.I)
EASY_APPLY = re.compile(r"^(easy apply|candidatura simplificada)$", re.I)
WORKPLACE = [("remote", ("remote", "remoto")), ("hybrid", ("hybrid", "híbrido", "hibrido")),
             ("on-site", ("on-site", "onsite", "presencial"))]


def _decode(value):
    try:
        return str(make_header(decode_header(value or "")))
    except Exception:  # noqa: BLE001
        return value or ""


def _workplace(location):
    low = location.lower()
    return next((code for code, words in WORKPLACE if any(w in low for w in words)), "")


def _block_to_job(job_id, lines):
    """Recebe as linhas de um bloco de vaga (sem o link) e separa os campos."""
    easy, salary, fields = False, "", []
    for ln in lines:
        if EASY_APPLY.match(ln):
            easy = True
        elif SALARY.match(ln) and len(ln) < 60:
            salary = ln
        elif not NOISE.match(ln):
            fields.append(ln)
    if not fields:
        return None
    title = fields[0]
    company, location = (fields[1] if len(fields) > 1 else ""), (fields[2] if len(fields) > 2 else "")
    for sep in (" · ", " • "):  # formato "Empresa · Local"
        if sep in company:
            company, rest = company.split(sep, 1)
            location = location or rest
            break
    return {"id": job_id, "title": title, "company": company, "location": location,
            "easy_apply": easy, "salary": salary, "workplace": _workplace(location)}


def parse_text(text):
    """Alertas em texto puro: blocos 'Título / Empresa / Local / ... / View job: <link>'."""
    jobs, lines = [], [ln.strip() for ln in text.splitlines()]
    for i, ln in enumerate(lines):
        m = JOB_ID.search(ln)
        if not m:
            continue
        block = []
        for prev in reversed(lines[max(0, i - 12):i]):
            if prev.startswith("---") or JOB_ID.search(prev):
                break
            if not prev:
                if block:
                    break
                continue
            block.insert(0, prev)
        job = _block_to_job(m.group(1), block)
        if job:
            jobs.append(job)
    return jobs


def parse_html(raw):
    """Plano B (e-mail só em HTML): o título é o texto do link da vaga; o resto vem logo depois."""
    jobs, seen = [], set()
    anchors = list(re.finditer(r'<a [^>]*href="([^"]*jobs/view/[^"]*)"[^>]*>(.*?)</a>', raw, re.S | re.I))
    for k, a in enumerate(anchors):
        m = JOB_ID.search(a.group(1))
        title = clean_html(a.group(2)).strip()
        if not m or not title or m.group(1) in seen or len(title) > 150 or NOISE.match(title):
            continue
        seen.add(m.group(1))
        nxt = anchors[k + 1].start() if k + 1 < len(anchors) else a.end() + 1500
        after = [ln.strip() for ln in clean_html(raw[a.end():nxt]).splitlines() if ln.strip()]
        job = _block_to_job(m.group(1), [title] + after[:6])
        if job:
            jobs.append(job)
    return jobs


def _bodies(msg):
    text = html = ""
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True) or b""
        content = payload.decode(part.get_content_charset() or "utf-8", "replace")
        if ctype == "text/plain" and not text:
            text = content
        elif ctype == "text/html" and not html:
            html = content
    return text, html


def _alert_name(text, subject):
    for ln in (text or "").splitlines()[:8]:
        m = ALERT_NAME.search(ln.strip())
        if m:
            return m.group(1).strip(), (m.group(2) or "").strip()
    return "", ""


def parse_message(msg):
    """Classifica um e-mail do LinkedIn e devolve ('alert', vagas) ou ('applied', vaga) ou (None, None)."""
    subject = _decode(msg.get("Subject"))
    try:
        sent = parsedate_to_datetime(msg.get("Date")).date().isoformat()
    except Exception:  # noqa: BLE001
        sent = dt.date.today().isoformat()
    text, html = _bodies(msg)

    if APPLIED_SUBJECT.search(subject):
        # A confirmação traz a vaga aplicada primeiro; depois podem vir "vagas parecidas".
        jobs = parse_text(text) if text else []
        jobs = jobs or (parse_html(html) if html else [])
        if not jobs:
            m = JOB_ID.search(text + html)
            if not m:
                return None, None
            jobs = [{"id": m.group(1), "title": "", "company": "", "location": ""}]
        first = jobs[0]
        if not first["company"]:
            m = re.search(r"(?:sent to|enviada para)\s+(.+)$", subject, re.I)
            first["company"] = m.group(1).strip() if m else ""
        first["date"] = sent
        return "applied", first

    jobs = parse_text(text) if text else []
    if not jobs and html:
        jobs = parse_html(html)
    query, area = _alert_name(text or clean_html(html), subject)
    for j in jobs:
        j.update(date=sent, alert=query, alert_area=area)
    return ("alert", jobs) if jobs else (None, None)


LAST_APPLIED = []  # preenchido a cada coleta; lido pelo main para registrar candidaturas


def fetch(cfg):
    """Conecta no Gmail e devolve (vagas_dos_alertas, candidaturas_confirmadas)."""
    user = os.getenv("GMAIL_USER") or os.getenv("SMTP_USER")
    pwd = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("SMTP_PASS")
    if not (user and pwd):
        print("  - linkedin: sem GMAIL_USER/GMAIL_APP_PASSWORD, pulando")
        return [], []
    since = (dt.date.today() - dt.timedelta(days=cfg.get("days_back", 3))).strftime("%d-%b-%Y")
    alerts, applied, seen = [], [], set()
    with imaplib.IMAP4_SSL("imap.gmail.com") as m:
        try:
            m.login(user, pwd)
        except imaplib.IMAP4.error as e:
            raise AuthError(f"login IMAP recusado: {e}") from e
        m.select("INBOX", readonly=True)
        senders = list(cfg.get("senders", [])) + (cfg.get("application_senders", [])
                                                  if cfg.get("track_applications", True) else [])
        for sender in dict.fromkeys(senders):
            _, ids = m.search(None, "FROM", f'"{sender}"', "SINCE", since)
            for mid in ids[0].split():
                _, data = m.fetch(mid, "(RFC822)")
                kind, payload = parse_message(email.message_from_bytes(data[0][1]))
                if kind == "alert":
                    for j in payload:
                        if j["id"] not in seen:
                            seen.add(j["id"])
                            alerts.append(j)
                elif kind == "applied" and cfg.get("track_applications", True):
                    applied.append(payload)
    return alerts, applied


def to_standard(j):
    """Converte para o formato padrão das outras fontes."""
    tags = []
    if j.get("easy_apply"):
        tags.append("candidatura simplificada")
    if j.get("alert"):
        tags.append(f"alerta: {j['alert']}" + (f" ({j['alert_area']})" if j.get("alert_area") else ""))
    if j.get("workplace"):
        tags.append(j["workplace"])
    return {
        "source": "linkedin", "ext_id": j["id"], "title": j["title"], "company": j["company"],
        "url": f"https://www.linkedin.com/jobs/view/{j['id']}/", "location": j["location"],
        "remote": int(j.get("workplace") == "remote"), "description": "", "tags": ", ".join(tags),
        "posted_at": j.get("date", ""), "salary_min_eur": None, "salary_max_eur": None,
        "salary_raw": j.get("salary", ""),
    }


def collect(cfg, rates):
    from .common import parse_salary_text
    alerts, applied = fetch(cfg)
    LAST_APPLIED[:] = applied
    out = []
    for j in alerts:
        std = to_standard(j)
        if std["salary_raw"]:
            std["salary_min_eur"], std["salary_max_eur"] = parse_salary_text(std["salary_raw"], rates)
        out.append(std)
    if applied:
        print(f"  linkedin: {len(applied)} confirmação(ões) de candidatura no e-mail")
    return out
