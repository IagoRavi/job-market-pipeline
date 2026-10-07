"""Nota de aderência por IA (opcional). Provedores: anthropic (pago) ou github/gemini/groq (camada gratuita)."""
import json
import os
import re

import requests

from .common import AuthError

PROMPT = """You are screening job postings for this candidate:

{profile}

Job posting:
TITLE: {title}
COMPANY: {company}
LOCATION: {location} | REMOTE: {remote}
SALARY (EUR/yr, may be empty): {smin} - {smax}
DESCRIPTION:
{description}

Answer ONLY with a JSON object, no markdown:
{{"score": <0-100 overall fit, weighting skills match AND whether a Brazil-based candidate can realistically be hired (remote from Brazil, or relocation with visa sponsorship)>,
 "can_hire_from_brazil": "yes" | "no" | "unclear",
 "cv_variant": "BI" | "DA",
 "summary_pt": "<2 frases em português: por que combina ou não>",
 "red_flags": ["<curto, em português>"]}}
cv_variant: "BI" if the role centers on Power BI/dashboards/reporting, "DA" if it centers on SQL/Python/pipelines/analysis."""


PROVIDERS = {
    # nome: (url, variável de ambiente com a chave, modelo padrão)
    "anthropic": ("https://api.anthropic.com/v1/messages", "ANTHROPIC_API_KEY", "claude-haiku-4-5-20251001"),
    "github": ("https://models.github.ai/inference/chat/completions", "GITHUB_TOKEN", "openai/gpt-4.1-mini"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "GEMINI_API_KEY", "gemini-2.5-flash"),
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY", "llama-3.3-70b-versatile"),
}


def provider_key(cfg):
    name = cfg["llm"].get("provider", "anthropic")
    return os.getenv(PROVIDERS[name][1]) if name in PROVIDERS else None


def rate(job, cfg):
    name = cfg["llm"].get("provider", "anthropic")
    url, key_env, default_model = PROVIDERS[name]
    key = os.getenv(key_env)
    if not key:
        return None
    model = cfg["llm"].get("model") or default_model
    prompt = PROMPT.format(
        profile=cfg["profile"], title=job["title"], company=job["company"], location=job["location"],
        remote="yes" if job["remote"] else "no", smin=job["salary_min_eur"] or "", smax=job["salary_max_eur"] or "",
        description=(job["description"] or "")[:6000])
    try:
        if name == "anthropic":
            r = requests.post(url, timeout=60, json={"model": model, "max_tokens": 400,
                              "messages": [{"role": "user", "content": prompt}]},
                              headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
        else:  # API no formato OpenAI (GitHub Models, Gemini, Groq)
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            if name == "github":
                headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
            r = requests.post(url, timeout=60, json={"model": model, "max_tokens": 400, "temperature": 0,
                              "messages": [{"role": "user", "content": prompt}]}, headers=headers)
        if r.status_code in (401, 403):
            raise AuthError(f"HTTP {r.status_code} em {name}")
        if r.status_code == 429:
            raise AuthError(f"limite gratuito de {name} atingido por hoje (HTTP 429)")
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        try:
            j = r.json()
        except ValueError:
            raise RuntimeError(f"resposta não é JSON (HTTP {r.status_code}): {r.text[:300]!r}") from None
        text = ("".join(b.get("text", "") for b in j["content"]) if name == "anthropic"
                else j["choices"][0]["message"]["content"])
        if not (text or "").strip():
            raise RuntimeError(f"resposta vazia do modelo: {str(j)[:300]}")
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0) if m else text)
        if data.get("can_hire_from_brazil") == "no":
            data["score"] = min(int(data.get("score", 0)), 30)
        return data
    except AuthError:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"  ! IA falhou para {job['id']}: {e}")
        return None
