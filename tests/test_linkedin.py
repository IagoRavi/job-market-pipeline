"""Testes do leitor de e-mails do LinkedIn (sem rede). Rode: python -m tests.test_linkedin"""
from email.message import EmailMessage

from job_bot import linkedin as L


def mail(subject, text=None, html=None, date="Wed, 07 Oct 2026 08:15:00 +0000"):
    m = EmailMessage()
    m["Subject"], m["From"], m["Date"] = subject, "jobalerts-noreply@linkedin.com", date
    if text:
        m.set_content(text)
    if html:
        (m.add_alternative if text else m.set_content)(html, subtype="html")
    return m


ALERT_EN = """Your job alert for power bi in European Union
30+ new jobs match your preferences.

BI Developer
Acme GmbH
Berlin, Berlin, Germany (Remote)
€55K/yr - €70K/yr
This company is actively hiring
Easy Apply
View job: https://www.linkedin.com/comm/jobs/view/4012345678/?trackingId=abc

---------------------------------------------------------

Senior Data Analyst
Beta B.V.
Amsterdam, North Holland, Netherlands (Hybrid)
3 connections
View job: https://www.linkedin.com/comm/jobs/view/4012345679/?trk=x

---------------------------------------------------------
"""

ALERT_PT = """Seu alerta de vagas para analista de dados em Brasil
Mais de 10 novas vagas correspondem às suas preferências.

Analista de BI Pleno
Banco XYZ · Brasília, Distrito Federal, Brasil (Remoto)
R$ 12.000 - R$ 15.000/mês
Candidatura simplificada
Ver vaga: https://www.linkedin.com/comm/jobs/view/4099999999/?trk=x
"""

ALERT_HTML = """<table><tr><td><a href="https://www.linkedin.com/comm/jobs/view/4055555555/?x=1"><img src=a></a></td>
<td><a href="https://www.linkedin.com/comm/jobs/view/4055555555/?x=1">Power BI Consultant</a>
<p>Gamma S.A. · Lisbon, Portugal (Remote)</p><p>Easy Apply</p></td></tr>
<tr><td><a href="https://www.linkedin.com/comm/jobs/view/4066666666/">View job</a></td></tr></table>"""

APPLIED = """Your application was sent to Acme GmbH

BI Developer
Acme GmbH
Berlin, Berlin, Germany (Remote)
Applied on October 7, 2026
View job: https://www.linkedin.com/comm/jobs/view/4012345678/

Jobs similar to this one

Data Analyst
Other Co
Munich, Germany
View job: https://www.linkedin.com/comm/jobs/view/4077777777/
"""


def check(label, got, expected):
    ok = all(got.get(k) == v for k, v in expected.items())
    print(("OK   " if ok else "FALHA"), label, "" if ok else f"\n      esperado {expected}\n      obtido   { {k: got.get(k) for k in expected} }")
    return ok


def main():
    res = []
    kind, jobs = L.parse_message(mail("BI Developer at Acme GmbH and 29 more", ALERT_EN))
    res.append(check("EN: tipo alerta, 2 vagas", {"k": kind, "n": len(jobs)}, {"k": "alert", "n": 2}))
    res.append(check("EN: vaga 1", jobs[0], {"id": "4012345678", "title": "BI Developer", "company": "Acme GmbH",
                     "location": "Berlin, Berlin, Germany (Remote)", "workplace": "remote", "easy_apply": True,
                     "salary": "€55K/yr - €70K/yr", "alert": "power bi", "alert_area": "European Union",
                     "date": "2026-10-07"}))
    res.append(check("EN: vaga 2 (ignora '3 connections')", jobs[1], {"title": "Senior Data Analyst",
                     "company": "Beta B.V.", "workplace": "hybrid", "easy_apply": False}))

    kind, jobs = L.parse_message(mail("Analista de BI Pleno no Banco XYZ", ALERT_PT))
    res.append(check("PT: 'Empresa · Local', salário em R$", jobs[0], {"title": "Analista de BI Pleno",
                     "company": "Banco XYZ", "location": "Brasília, Distrito Federal, Brasil (Remoto)",
                     "workplace": "remote", "easy_apply": True, "salary": "R$ 12.000 - R$ 15.000/mês",
                     "alert": "analista de dados", "alert_area": "Brasil"}))

    kind, jobs = L.parse_message(mail("Power BI Consultant at Gamma", html=ALERT_HTML))
    res.append(check("HTML: 1 vaga, ignora link 'View job'", {"n": len(jobs)}, {"n": 1}))
    res.append(check("HTML: campos", jobs[0], {"id": "4055555555", "title": "Power BI Consultant",
                     "company": "Gamma S.A.", "location": "Lisbon, Portugal (Remote)", "easy_apply": True}))

    kind, job = L.parse_message(mail("Iago, your application was sent to Acme GmbH", APPLIED))
    res.append(check("Confirmação: pega só a vaga aplicada", {"k": kind, **job},
                     {"k": "applied", "id": "4012345678", "title": "BI Developer", "company": "Acme GmbH",
                      "date": "2026-10-07"}))
    kind, job = L.parse_message(mail("=?UTF-8?Q?Iago=2C_sua_candidatura_foi_enviada_para_Banco_XYZ?=",
                                     "https://www.linkedin.com/comm/jobs/view/4099999999/"))
    res.append(check("Confirmação PT (assunto codificado, só link)", {"k": kind, **job},
                     {"k": "applied", "id": "4099999999", "company": "Banco XYZ"}))

    std = L.to_standard({**L.parse_message(mail("x", ALERT_EN))[1][0]})
    res.append(check("Formato padrão", std, {"source": "linkedin", "remote": 1,
                     "url": "https://www.linkedin.com/jobs/view/4012345678/",
                     "tags": "candidatura simplificada, alerta: power bi (European Union), remote"}))
    print(f"\n{sum(res)}/{len(res)} testes ok")
    return all(res)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
