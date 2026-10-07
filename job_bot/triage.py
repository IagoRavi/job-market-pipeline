"""Pré-filtro e nota heurística (0–100). Explica cada ponto em `reasons`.
Retorna (nota, motivos, status, região) — região: BR | EU | GLOBAL | OUTRA."""
import re

from .common import norm

DE_HINTS = ["germany", "deutschland", "berlin", "munich", "münchen", "hamburg", "frankfurt", "cologne",
            "köln", "stuttgart", "düsseldorf", "leipzig", "dresden", "nuremberg", "nürnberg", "(de)"]
EU_HINTS = ["europe", "european union", "emea", "cet", "cest", "portugal", "lisbon", "lisboa", "porto",
            "spain", "madrid", "barcelona", "netherlands", "amsterdam", "ireland", "dublin", "france", "paris",
            "austria", "vienna", "poland", "warsaw", "belgium", "italy", "sweden", "denmark", "finland",
            "czech", "united kingdom", "london", "(gb)", "(nl)", "(es)", "(fr)", "(at)"] + DE_HINTS
BR_HINTS = ["brasil", "brazil", "(br)", "são paulo", "sao paulo", "rio de janeiro", "belo horizonte",
            "brasília", "brasilia", "distrito federal", "curitiba", "porto alegre", "recife", "salvador",
            "florianópolis", "fortaleza", "goiânia", "campinas"]
GLOBAL_HINTS = ["worldwide", "anywhere", "global", "latam", "latin america", "americas"]
GERMAN_WORDS = re.compile(r"\b(und|wir|die|der|für|mit|kenntnisse|erfahrung|sie|ihre|bewerbung)\b")


def _has(text, terms):
    return [t for t in terms if t in text]


def region_of(job):
    loc = norm(job["location"])
    if job["source"] == "gupy" or _has(loc, BR_HINTS):
        return "BR"
    if _has(loc, EU_HINTS):
        return "EU"
    if job["remote"] and (not loc or _has(loc, GLOBAL_HINTS) or loc in ("remote", "remoto")):
        return "GLOBAL"
    return "OUTRA"


def score(job, cfg, rates=None):
    kw, el, sal, br = cfg["keywords"], cfg["eligibility"], cfg["salary"], cfg.get("brazil", {})
    title = norm(job["title"])
    text = norm(" ".join([job["title"], job["description"], job["tags"], job["location"]]))
    loc = norm(job["location"])
    region = region_of(job)
    reasons, s = [], 0

    if _has(title, kw["title_exclude"]):
        return 0, ["título excluído"], "discard", region
    if _has(title, kw["title_strong"]):
        s += 40; reasons.append("título forte")
    elif _has(title, kw["title_weak"]):
        s += 20; reasons.append("título relacionado")
    else:
        return 0, ["título fora do escopo"], "discard", region

    skill_pts = sum(w for k, w in kw["skills"].items() if re.search(rf"(?<![a-z]){re.escape(k)}(?![a-z])", text))
    s += min(skill_pts, 30)
    if skill_pts:
        reasons.append(f"skills +{min(skill_pts, 30)}")

    # LinkedIn: o alerta só traz título/empresa/local; os filtros do alerta são seus
    if job["source"] == "linkedin":
        s += 20; reasons.append("alerta LinkedIn (seus filtros)")

    # elegibilidade por região
    if region == "BR":
        home = br.get("home_cities", [])
        if job["remote"]:
            s += 20; reasons.append("remoto no Brasil")
        elif _has(loc, home):
            s += 15; reasons.append("Brasília")
        else:
            s -= br.get("onsite_elsewhere_penalty", 25); reasons.append("presencial/híbrido fora de Brasília")
    else:
        if job["remote"] and _has(text, el["remote_ok"]):
            s += 20; reasons.append("remoto aceita LATAM/global")
        if _has(text, el["relocation_ok"]):
            s += 20; reasons.append("menciona visto/relocação")
        if region == "EU":
            s += 5; reasons.append("Europa")
        if b := _has(text, el["blockers"]):
            s -= 40; reasons.append(f"restrição: {b[0]}")
        if b := _has(text, el["language_blockers"]):
            s -= 30; reasons.append(f"idioma: {b[0]}")
        if len(GERMAN_WORDS.findall(norm(job["description"][:1500]))) >= 12:
            s -= 40; reasons.append("descrição em alemão")

    if re.search(r"\b(junior|júnior|jr\.?)(?![a-z])", title):
        s -= 10; reasons.append("júnior")

    # salário
    smax = job.get("salary_max_eur") or job.get("salary_min_eur")
    if smax:
        floor, target = None, None
        if region == "BR":
            brl = (rates or {}).get("BRL")
            if brl and br.get("min_monthly_brl"):
                floor = br["min_monthly_brl"] * 12 * brl
        elif job["remote"]:
            floor, target = sal["remote_min_annual_eur"], sal["remote_target_annual_eur"]
        elif _has(loc, DE_HINTS):
            floor, target = sal["germany_min_annual_eur"], sal["germany_min_annual_eur"] * 1.1
        else:
            floor = sal["relocation_min_annual_eur"]
        if floor and smax < floor:
            return max(s, 0), reasons + [f"salário abaixo do piso (€{smax:,.0f}/ano)"], "below_floor", region
        if target and smax >= target:
            s += 10; reasons.append("salário acima do alvo")

    return max(0, min(100, s)), reasons, "new", region
