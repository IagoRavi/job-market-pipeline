"""Coletores. Cada um devolve uma lista de dicts no formato padrão:
source, ext_id, title, company, location, remote, url, description,
tags, posted_at, salary_min_eur, salary_max_eur, salary_raw
"""
import datetime as dt
import email
import imaplib
import os
import re
import time

from .common import AuthError, clean_html, get_json, parse_salary_text, to_annual_eur


def _job(source, ext_id, title, company, url, **kw):
    return {
        "source": source, "ext_id": str(ext_id), "title": (title or "").strip(),
        "company": (company or "").strip(), "url": url,
        "location": kw.get("location") or "", "remote": int(bool(kw.get("remote"))),
        "description": clean_html(kw.get("description"))[:20000],
        "tags": ", ".join(kw.get("tags") or []), "posted_at": kw.get("posted_at") or "",
        "salary_min_eur": kw.get("smin"), "salary_max_eur": kw.get("smax"),
        "salary_raw": kw.get("salary_raw") or "",
    }


def _ts(v):
    try:
        v = float(v)
        if v > 1e12:
            v /= 1000
        return dt.datetime.fromtimestamp(v, dt.timezone.utc).date().isoformat()
    except (TypeError, ValueError):
        return str(v or "")[:10]


def arbeitnow(cfg, rates):
    out = []
    for page in range(1, cfg.get("max_pages", 3) + 1):
        data = get_json("https://www.arbeitnow.com/api/job-board-api", {"page": page})
        if not data or not data.get("data"):
            break
        for j in data["data"]:
            out.append(_job("arbeitnow", j.get("slug"), j.get("title"), j.get("company_name"), j.get("url"),
                            location=j.get("location"), remote=j.get("remote"), description=j.get("description"),
                            tags=(j.get("tags") or []) + (j.get("job_types") or []), posted_at=_ts(j.get("created_at"))))
    return out


def remotive(cfg, rates):
    out = []
    for cat in cfg.get("categories", ["data"]):
        data = get_json("https://remotive.com/api/remote-jobs", {"category": cat})
        for j in (data or {}).get("jobs", []):
            smin, smax = parse_salary_text(j.get("salary"), rates)
            out.append(_job("remotive", j.get("id"), j.get("title"), j.get("company_name"), j.get("url"),
                            location=j.get("candidate_required_location"), remote=True,
                            description=j.get("description"), tags=j.get("tags"),
                            posted_at=str(j.get("publication_date", ""))[:10],
                            smin=smin, smax=smax, salary_raw=j.get("salary")))
    return out


def remoteok(cfg, rates):
    out = []
    for tag in cfg.get("tags", ["data"]):
        data = get_json("https://remoteok.com/api", {"tag": tag})
        for j in (data or [])[1:]:  # o 1º item é o aviso legal da API
            if not isinstance(j, dict) or not j.get("id"):
                continue
            out.append(_job("remoteok", j.get("id"), j.get("position"), j.get("company"), j.get("url"),
                            location=j.get("location") or "Remote", remote=True,
                            description=j.get("description"), tags=j.get("tags"),
                            posted_at=str(j.get("date", ""))[:10],
                            smin=to_annual_eur(j.get("salary_min"), "USD", rates, "year"),
                            smax=to_annual_eur(j.get("salary_max"), "USD", rates, "year")))
    return out


def himalayas(cfg, rates):
    out = []
    for page in range(cfg.get("max_pages", 5)):
        data = get_json("https://himalayas.app/jobs/api", {"limit": 20, "offset": page * 20})
        jobs = (data or {}).get("jobs") or []
        if not jobs:
            break
        for j in jobs:
            cur = j.get("currency") or "USD"
            loc = ", ".join(j.get("locationRestrictions") or []) or "Worldwide"
            out.append(_job("himalayas", j.get("guid") or j.get("applicationLink"), j.get("title"),
                            j.get("companyName"), j.get("applicationLink") or j.get("guid"),
                            location=loc, remote=True, description=j.get("description") or j.get("excerpt"),
                            tags=j.get("categories"), posted_at=_ts(j.get("pubDate")),
                            smin=to_annual_eur(j.get("minSalary"), cur, rates, "year"),
                            smax=to_annual_eur(j.get("maxSalary"), cur, rates, "year")))
    return out


def greenhouse(cfg, rates):
    out = []
    for board in cfg.get("boards", []):
        data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", {"content": "true"})
        for j in (data or {}).get("jobs", []):
            loc = (j.get("location") or {}).get("name", "")
            out.append(_job("greenhouse", f"{board}:{j.get('id')}", j.get("title"), board, j.get("absolute_url"),
                            location=loc, remote="remote" in loc.lower(), description=j.get("content"),
                            posted_at=str(j.get("updated_at", ""))[:10]))
    return out


def lever(cfg, rates):
    out = []
    for company in cfg.get("companies", []):
        for j in get_json(f"https://api.lever.co/v0/postings/{company}", {"mode": "json"}) or []:
            cats = j.get("categories") or {}
            sr = j.get("salaryRange") or {}
            period = {"per-year-salary": "year", "per-month-salary": "month", "per-hour-wage": "hour"}.get(sr.get("interval"))
            out.append(_job("lever", f"{company}:{j.get('id')}", j.get("text"), company, j.get("hostedUrl"),
                            location=cats.get("location"), remote=j.get("workplaceType") == "remote",
                            description=j.get("descriptionPlain") or j.get("description"),
                            tags=[cats.get("team") or "", cats.get("commitment") or ""], posted_at=_ts(j.get("createdAt")),
                            smin=to_annual_eur(sr.get("min"), sr.get("currency"), rates, period),
                            smax=to_annual_eur(sr.get("max"), sr.get("currency"), rates, period)))
    return out


def ashby(cfg, rates):
    out = []
    for board in cfg.get("boards", []):
        data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{board}", {"includeCompensation": "true"})
        for j in (data or {}).get("jobs", []):
            comp = (j.get("compensation") or {}).get("compensationTierSummary") or ""
            smin, smax = parse_salary_text(comp, rates)
            out.append(_job("ashby", f"{board}:{j.get('id')}", j.get("title"), board, j.get("jobUrl"),
                            location=j.get("location"), remote=j.get("isRemote"),
                            description=j.get("descriptionPlain") or j.get("descriptionHtml"),
                            posted_at=str(j.get("publishedAt", ""))[:10], smin=smin, smax=smax, salary_raw=comp))
    return out


_ADZUNA_CUR = {"gb": "GBP", "pl": "PLN", "ch": "CHF", "br": "BRL"}


def adzuna(cfg, rates):
    app_id, app_key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        print("  - adzuna: sem credenciais, pulando")
        return []
    out = []
    for cc in cfg.get("countries", []):
        for q in cfg.get("queries", []):
            data = get_json(f"https://api.adzuna.com/v1/api/jobs/{cc}/search/1",
                            {"app_id": app_id, "app_key": app_key, "what": q, "results_per_page": 50,
                             "max_days_old": 14, "content-type": "application/json"})
            cur = _ADZUNA_CUR.get(cc, "EUR")
            for j in (data or {}).get("results", []):
                out.append(_job("adzuna", f"{cc}:{j.get('id')}", j.get("title"),
                                (j.get("company") or {}).get("display_name"), j.get("redirect_url"),
                                location=f"{(j.get('location') or {}).get('display_name', '')} ({cc.upper()})",
                                remote="remote" in (j.get("title", "") + j.get("description", "")).lower(),
                                description=j.get("description"), posted_at=str(j.get("created", ""))[:10],
                                smin=to_annual_eur(j.get("salary_min"), cur, rates, "year"),
                                smax=to_annual_eur(j.get("salary_max"), cur, rates, "year")))
    return out


# ---------------------------------------------------------------- Brasil
GUPY_ENDPOINTS = [
    ("https://employability-portal.gupy.io/api/v1/jobs", lambda kw, off: {"jobName": kw, "offset": off, "limit": 10}),
    ("https://portal.api.gupy.io/api/job", lambda kw, off: {"name": kw, "offset": off, "limit": 10}),
    ("https://portal.api.gupy.io/api/v1/jobs", lambda kw, off: {"jobName": kw, "offset": off, "limit": 10}),
]


def gupy(cfg, rates):
    """Portal público da Gupy (maior ATS do Brasil). Exige palavra-chave; 10 vagas por página."""
    endpoint = None
    candidates = list(GUPY_ENDPOINTS)
    if cfg.get("endpoint"):  # endpoint informado no config.yaml tem prioridade
        qp = cfg.get("query_param", "jobName")
        candidates.insert(0, (cfg["endpoint"], lambda kw, off: {qp: kw, "offset": off, "limit": 10}))
    for url, params in candidates:  # descobre qual endpoint está ativo
        if (get_json(url, params("power bi", 0), retries=0) or {}).get("data") is not None:
            endpoint = (url, params)
            break
    if not endpoint:
        print("  ! gupy: nenhum endpoint conhecido respondeu")
        return []
    url, params = endpoint
    out = []
    for kw in cfg.get("keywords", []):
        for page in range(cfg.get("max_pages", 5)):
            jobs = (get_json(url, params(kw, page * 10)) or {}).get("data") or []
            if not jobs:
                break
            for j in jobs:
                wt = (j.get("workplaceType") or "").lower()
                loc = ", ".join(x for x in [j.get("city"), j.get("state"), "Brasil"] if x)
                out.append(_job("gupy", j.get("id"), j.get("name"),
                                j.get("careerPageName") or j.get("companyName"), j.get("jobUrl"),
                                location=f"{loc} ({wt or 'n/i'})",
                                remote=wt == "remote" or j.get("isRemoteWork"),
                                description=j.get("description"), posted_at=str(j.get("publishedDate", ""))[:10]))
            time.sleep(0.3)
    return out


# ---------------------------------------------------------------- LinkedIn (via e-mail)
_LI_ID = re.compile(r"linkedin\.com/(?:comm/)?jobs/view/(\d+)")


def _parse_linkedin_alert(text):
    """Extrai (id, título, empresa, local) do texto de um alerta de vagas do LinkedIn.
    O texto vem em blocos 'Título / Empresa / Local / ... / link da vaga'."""
    jobs, lines = [], [ln.strip() for ln in text.splitlines()]
    for i, ln in enumerate(lines):
        m = _LI_ID.search(ln)
        if not m:
            continue
        block = []
        for prev in reversed(lines[max(0, i - 8):i]):
            if not prev or _LI_ID.search(prev) or prev.startswith("---"):
                if block:
                    break
                continue
            if prev.lower().startswith(("view job", "ver vaga", "candidatura simplificada", "easy apply",
                                        "promovida", "promoted", "be an early applicant",
                                        "seja um dos primeiros")):
                continue
            block.insert(0, prev)
        block = [b for b in block if not re.match(r"^(\d+ (connections?|conex)|actively recruiting|recrutando)", b, re.I)]
        if block:
            title = block[0]
            company = block[1] if len(block) > 1 else ""
            location = block[2] if len(block) > 2 else ""
            jobs.append((m.group(1), title, company, location))
    return jobs


def _parse_linkedin_html(raw):
    """Plano B: no HTML, o título é o texto do link da vaga; empresa e local vêm logo depois."""
    jobs, seen = [], set()
    anchors = list(re.finditer(r'<a [^>]*href="([^"]*jobs/view/(\d+)[^"]*)"[^>]*>(.*?)</a>', raw, re.S | re.I))
    for k, a in enumerate(anchors):
        title = clean_html(a.group(3)).strip()
        if not title or a.group(2) in seen or len(title) > 150:
            continue
        seen.add(a.group(2))
        nxt = anchors[k + 1].start() if k + 1 < len(anchors) else a.end() + 1500
        after = [ln.strip() for ln in clean_html(raw[a.end():nxt]).splitlines() if ln.strip()]
        parts = re.split(r"\s+[·•]\s+", after[0]) if after else []
        company = parts[0] if parts else ""
        location = parts[1] if len(parts) > 1 else (after[1] if len(after) > 1 else "")
        jobs.append((a.group(2), title, company, location))
    return jobs


def linkedin_alerts(cfg, rates):
    """Lê os e-mails de alerta de vagas que o próprio LinkedIn manda para você.
    Não acessa o LinkedIn: só a sua caixa de entrada (IMAP do Gmail, com senha de app)."""
    user = os.getenv("GMAIL_USER") or os.getenv("SMTP_USER")
    pwd = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("SMTP_PASS")
    if not (user and pwd):
        print("  - linkedin: sem GMAIL_USER/GMAIL_APP_PASSWORD, pulando")
        return []
    since = (dt.date.today() - dt.timedelta(days=cfg.get("days_back", 3))).strftime("%d-%b-%Y")
    out, seen = [], set()
    with imaplib.IMAP4_SSL("imap.gmail.com") as m:
        try:
            m.login(user, pwd)
        except imaplib.IMAP4.error as e:
            raise AuthError(f"login IMAP recusado: {e}") from e
        m.select("INBOX", readonly=True)
        for sender in cfg.get("senders", ["jobalerts-noreply@linkedin.com"]):
            _, ids = m.search(None, "FROM", f'"{sender}"', "SINCE", since)
            for mid in ids[0].split():
                _, msg_data = m.fetch(mid, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                text = ""
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        text = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
                        break
                parsed = _parse_linkedin_alert(text) if text else []
                if not parsed:  # sem parte de texto útil: lê o HTML
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            parsed = _parse_linkedin_html(part.get_payload(decode=True).decode(
                                part.get_content_charset() or "utf-8", "replace"))
                            break
                for job_id, title, company, location in parsed:
                    if job_id in seen:
                        continue
                    seen.add(job_id)
                    out.append(_job("linkedin", job_id, title, company,
                                    f"https://www.linkedin.com/jobs/view/{job_id}/",
                                    location=location, remote=any(w in location.lower() for w in ("remote", "remoto")),
                                    posted_at=dt.date.today().isoformat()))
    return out


ALL = {"arbeitnow": arbeitnow, "remotive": remotive, "remoteok": remoteok, "himalayas": himalayas,
       "greenhouse": greenhouse, "lever": lever, "ashby": ashby, "adzuna": adzuna,
       "gupy": gupy, "linkedin": linkedin_alerts}
