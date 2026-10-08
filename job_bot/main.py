"""Execução diária: coleta → triagem → IA → digest → CSV."""
import argparse
import json
import os
from collections import Counter

import yaml

from . import db, digest, linkedin, llm, report, sources, tracking, triage
from .common import AuthError, load_rates


def _merge(base, extra):
    for k, v in (extra or {}).items():
        base[k] = _merge(base.get(k, {}), v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return base


def load_config(path="config.yaml"):
    """config.yaml (público) + config.local.yaml (privado, fora do Git).
    No GitHub, o conteúdo privado vem do secret CONFIG_PRIVADO."""
    cfg = yaml.safe_load(open(path, encoding="utf-8"))
    if os.getenv("CONFIG_PRIVADO"):
        _merge(cfg, yaml.safe_load(os.environ["CONFIG_PRIVADO"]))
    elif os.path.exists("config.local.yaml"):
        _merge(cfg, yaml.safe_load(open("config.local.yaml", encoding="utf-8")))
    else:
        print("  - sem config.local.yaml/CONFIG_PRIVADO: usando valores padrão públicos")
    return cfg


def run(config_path="config.yaml", db_path="data/jobs.db", fixtures=None):
    cfg = load_config(config_path)
    rates = load_rates() if not fixtures else {"EUR": 1.0, "USD": 0.86, "GBP": 1.17, "BRL": 0.17}
    con = db.connect(db_path)
    for row in con.execute("SELECT * FROM jobs WHERE region IS NULL").fetchall():  # vagas da versão anterior
        con.execute("UPDATE jobs SET region=? WHERE id=?", (triage.region_of(dict(row)), row["id"]))

    # 1. coleta
    collected = []
    if fixtures:
        collected = json.load(open(fixtures, encoding="utf-8"))
    else:
        for name, fn in sources.ALL.items():
            scfg = cfg["sources"].get(name, {})
            if not scfg.get("enabled"):
                continue
            try:
                jobs = fn(scfg, rates)
            except AuthError as e:
                print(f"  ! {name}: credencial inválida ou acesso negado ({e}), pulando")
                continue
            except Exception as e:  # noqa: BLE001 — uma fonte com problema não derruba as outras
                print(f"  ! {name}: erro inesperado ({e}), pulando")
                continue
            print(f"  {name}: {len(jobs)} vagas")
            collected += jobs

    # 2. triagem
    stats = Counter()
    for job in collected:
        if not job.get("title") or not job.get("url"):
            continue
        s, reasons, status, region = triage.score(job, cfg, rates)
        if db.insert_if_new(con, job, s, reasons, status, region):
            stats[status] += 1
    con.commit()
    print(f"  novas: {dict(stats)}")

    # 3. IA
    if cfg["llm"]["enabled"] and not llm.provider_key(cfg):
        print(f"  - IA ({cfg['llm'].get('provider', 'anthropic')}): sem chave, pulando")
    elif cfg["llm"]["enabled"]:
        pending = con.execute("""SELECT * FROM jobs WHERE status='new' AND llm_score IS NULL AND heur_score >= ?
                                 ORDER BY heur_score DESC LIMIT ?""",
                              (cfg["llm"]["min_heuristic_score"], cfg["llm"]["max_per_run"])).fetchall()
        rated, fails = 0, 0
        for j in pending:
            try:
                res = llm.rate(dict(j), cfg)
            except AuthError as e:
                print(f"  ! IA: {e}; interrompendo avaliação (o resto segue)")
                break
            if not res:
                fails += 1
                if fails >= 3 and not rated:
                    print("  ! IA: 3 falhas seguidas, interrompendo avaliação (o resto segue)")
                    break
                continue
            if res:
                rated += 1
                con.execute("UPDATE jobs SET llm_score=?, llm_summary=?, llm_red_flags=?, cv_variant=? WHERE id=?",
                            (int(res.get("score", 0)), res.get("summary_pt"), "; ".join(res.get("red_flags") or []),
                             res.get("cv_variant"), j["id"]))
        con.commit()
        print(f"  IA avaliou: {rated} de {len(pending)} na fila")

    # 3b. candidaturas: confirmações por e-mail do LinkedIn + o que você registrou no CSV
    n_auto = tracking.register_auto(con, linkedin.LAST_APPLIED)
    if n_auto:
        print(f"  candidaturas novas detectadas no e-mail: {n_auto}")
    n_track = tracking.apply(con)
    con.commit()
    if n_track:
        print(f"  candidaturas registradas: {n_track}")

    # 4. digest e CSV
    n = digest.build(con, cfg)
    con.commit()
    db.export_csv(con, "data/jobs.csv")
    print(f"  relatório: data/relatorio.html ({report.build(con, cfg)} vagas no banco)")
    print(f"  digest: {n} vagas")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", help="JSON com vagas de teste (sem rede)")
    ap.add_argument("--db", default="data/jobs.db")
    a = ap.parse_args()
    run(db_path=a.db, fixtures=a.fixtures)
