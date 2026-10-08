"""Utilidades compartilhadas: HTTP, limpeza de texto, salário e câmbio."""
import html
import re
import time
import xml.etree.ElementTree as ET

import requests

class AuthError(Exception):
    """Credencial ausente ou inválida (HTTP 401/403): não adianta tentar de novo."""


UA = {"User-Agent": "robo-vagas/1.0 (busca pessoal de emprego; contato via GitHub)"}


def get_json(url, params=None, headers=None, retries=2):
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers={**UA, **(headers or {})}, timeout=30)
            if r.status_code == 404:
                return None
            if r.status_code in (401, 403):
                raise AuthError(f"HTTP {r.status_code} em {url.split('?')[0]}")
            if 400 <= r.status_code < 500 and r.status_code != 429:
                print(f"  ! HTTP {r.status_code} em {url}")
                return None
            r.raise_for_status()
            return r.json()
        except AuthError:
            raise
        except Exception as e:  # noqa: BLE001
            if attempt == retries:
                print(f"  ! falha em {url}: {e}")
                return None
            time.sleep(2 * (attempt + 1))


def clean_html(text):
    if not text:
        return ""
    text = html.unescape(str(text))
    text = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def norm(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


# ---------- câmbio (BCE, gratuito) ----------
_FALLBACK_TO_EUR = {"EUR": 1.0, "USD": 0.86, "GBP": 1.17, "PLN": 0.23, "CHF": 1.07, "BRL": 0.17}


def load_rates():
    """Retorna {moeda: quanto vale 1 unidade em EUR} usando a taxa diária do BCE."""
    rates = dict(_FALLBACK_TO_EUR)
    try:
        r = requests.get("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml", timeout=20)
        root = ET.fromstring(r.content)
        for cube in root.iter():
            if cube.get("currency") and cube.get("rate"):
                rates[cube.get("currency")] = 1 / float(cube.get("rate"))
    except Exception as e:  # noqa: BLE001
        print(f"  ! câmbio BCE indisponível, usando fallback: {e}")
    return rates


def to_annual_eur(value, currency, rates, period=None):
    """Converte para EUR/ano. period: 'year'|'month'|'hour'|None (inferido pelo valor)."""
    if value in (None, "", 0):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if period is None:
        period = "hour" if v < 300 else "month" if v < 15000 else "year"
    v *= {"hour": 1800, "day": 220, "week": 46, "month": 12}.get(period, 1)
    return round(v * rates.get((currency or "EUR").upper(), 1.0))


_CUR = {"r$": "BRL", "brl": "BRL", "$": "USD", "€": "EUR", "£": "GBP", "usd": "USD", "eur": "EUR", "gbp": "GBP"}


def parse_salary_text(text, rates):
    """'$60k - $80k' / '€50,000 – 65,000' -> (min_eur, max_eur). Estimativa."""
    if not text:
        return None, None
    t = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", text.lower())  # 10.000 → 10000
    t = t.replace(",", "")
    cur = next((c for s, c in _CUR.items() if s in t), "USD")
    nums = []
    for n, k in re.findall(r"(\d+(?:\.\d+)?)\s*(k)?", t):
        v = float(n) * (1000 if k else 1)
        if v >= 10:
            nums.append(v)
    if not nums:
        return None, None
    period = ("hour" if re.search(r"hour|hora|/h", t) else "month" if re.search(r"month|mês|mes\b|/m", t)
              else "year" if re.search(r"year|/yr|/y\b|ano", t) else None)
    vals = [to_annual_eur(v, cur, rates, period) for v in nums[:2]]
    return min(vals), max(vals)
