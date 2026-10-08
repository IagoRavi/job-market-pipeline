"""Relatório HTML com todas as vagas do banco: abas por região, filtros, idade da vaga,
kit de candidatura (textos e respostas prontas) e botões para registrar candidaturas.
Abra data/relatorio.html no navegador. Não depende de internet."""
import json
import os
from datetime import datetime

import yaml

COLS = ["id", "title", "company", "location", "region", "source", "remote", "url", "first_seen", "posted_at",
        "tags", "cv_variant", "salary_min_eur", "salary_max_eur", "salary_raw", "status", "notified",
        "applied_at", "notes"]

TEMPLATE = r"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="robots" content="noindex, nofollow"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Robô de vagas</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2433;--mut:#6b7280;--line:#e5e7eb;--acc:#1f4e79;--good:#15803d;--mid:#b45309;--bad:#b91c1c;--soft:#eef3f8}
@media (prefers-color-scheme:dark){:root{--bg:#111418;--card:#1a1f26;--fg:#e6e9ee;--mut:#9aa3af;--line:#2a313b;--acc:#7fb2e5;--good:#4ade80;--mid:#fbbf24;--bad:#f87171;--soft:#202833}}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--fg)}
header{padding:20px 16px 8px}h1{margin:0;font-size:20px}header p{margin:4px 0 0;color:var(--mut)}
.tabs{display:flex;gap:6px;flex-wrap:wrap;padding:8px 16px}
.tab{border:1px solid var(--line);background:var(--card);color:var(--fg);padding:6px 12px;border-radius:999px;cursor:pointer;font-size:13px}
.tab.on{background:var(--acc);border-color:var(--acc);color:#fff}
.filters{display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:8px 16px 14px}
.filters input,.filters select{padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg);font-size:13px}
.wrap{padding:0 16px 32px;overflow-x:auto}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:var(--card);cursor:pointer;white-space:nowrap;font-size:12px;color:var(--mut);text-transform:uppercase}
td.n{font-weight:700;text-align:center}.g{color:var(--good)}.m{color:var(--mid)}.b{color:var(--bad)}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.why{color:var(--mut);font-size:12px;max-width:360px}
.pill{font-size:11px;padding:1px 6px;border-radius:4px;border:1px solid var(--line);color:var(--mut);white-space:nowrap;display:inline-block;margin:2px 2px 0 0}
.new{background:var(--acc);color:#fff;border-color:var(--acc)}.st{background:var(--good);color:#fff;border-color:var(--good)}
.old{color:var(--bad);border-color:var(--bad)}
.acts{margin-top:6px;display:flex;gap:4px;flex-wrap:wrap}
.btn{font-size:11px;padding:2px 8px;border:1px solid var(--line);border-radius:4px;background:transparent;color:var(--mut);cursor:pointer}
.btn:hover{color:var(--acc);border-color:var(--acc)}.btn.pri{background:var(--acc);color:#fff;border-color:var(--acc)}
#toast{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:var(--fg);color:var(--bg);padding:8px 14px;border-radius:6px;opacity:0;transition:opacity .3s;font-size:13px;z-index:20;max-width:90vw}
#kit{position:fixed;inset:0;background:rgba(0,0,0,.45);display:none;align-items:flex-start;justify-content:center;padding:24px 12px;overflow-y:auto;z-index:10}
#kit.on{display:flex}
.box{background:var(--card);border-radius:10px;max-width:760px;width:100%;padding:18px 18px 22px;border:1px solid var(--line)}
.box h2{margin:0 0 2px;font-size:17px}.box h3{margin:18px 0 8px;font-size:13px;text-transform:uppercase;color:var(--mut)}
.box .sub{color:var(--mut);font-size:13px}
.box textarea{width:100%;min-height:190px;border:1px solid var(--line);border-radius:6px;padding:10px;font-family:inherit;font-size:13px;line-height:1.45;background:var(--bg);color:var(--fg)}
.txt{background:var(--soft);border-radius:8px;padding:10px;margin-bottom:10px}
.txt .hd{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap}
.qa{display:grid;grid-template-columns:1fr auto;gap:4px 10px;align-items:center;border-bottom:1px solid var(--line);padding:6px 0}
.qa .q{font-size:12px;color:var(--mut)}.qa .a{font-size:13px}
.close{float:right;font-size:20px;line-height:1;border:0;background:transparent;color:var(--mut);cursor:pointer}
.lang{display:inline-flex;gap:4px;margin-left:6px}
.note{font-size:12px;color:var(--mut);margin-top:6px}
.mob{display:none;color:var(--mut);font-size:12px;margin-top:2px}
@media (max-width:860px){table{font-size:13px}th:nth-child(3),td:nth-child(3),th:nth-child(4),td:nth-child(4),th:nth-child(5),td:nth-child(5),th:nth-child(8),td:nth-child(8){display:none}.mob{display:block}th{white-space:normal;font-size:11px}th,td{padding:8px 5px}td.n{padding-left:4px;padding-right:4px}.wrap,header,.tabs,.filters{padding-left:12px;padding-right:12px}}
</style></head><body>
<header><h1>Robô de vagas</h1><p>Atualizado em __DATE__ · <span id="count"></span></p></header>
<div class="tabs" id="tabs"></div>
<div class="filters">
 <input id="q" placeholder="Buscar título, empresa, local…" size="24">
 <select id="status">
  <option value="new">Relevantes</option><option value="mine">Minhas candidaturas</option>
  <option value="closed">Encerradas</option><option value="below_floor">Abaixo do piso salarial</option>
  <option value="discard">Descartadas pelo filtro</option><option value="all">Todas</option></select>
 <select id="source"><option value="">Todas as fontes</option></select>
 <select id="age"><option value="7">Até 7 dias</option><option value="14">Até 14 dias</option>
  <option value="21">Até 21 dias</option><option value="30">Até 30 dias</option><option value="0">Qualquer data</option></select>
 <label>Nota ≥ <input id="min" type="number" value="0" min="0" max="100" style="width:58px"></label>
 <label><input id="remote" type="checkbox"> Só remotas</label>
</div>
<div class="wrap"><table><thead><tr>
 <th data-k="score">Nota</th><th data-k="title">Vaga</th><th data-k="company">Empresa</th><th data-k="location">Local</th>
 <th data-k="source">Fonte</th><th data-k="salary_max_eur">Salário (€/ano)</th><th data-k="age">Publicada</th><th>Por quê</th>
</tr></thead><tbody id="rows"></tbody></table></div>

<div id="kit"><div class="box" id="kitbox"></div></div>
<div id="toast"></div>
<script>
const JOBS = __DATA__, KIT = __KIT__, CFG = __CFG__, TODAY = "__TODAY__";
const MINE = {applied:"aplicado",interview:"entrevista",rejected:"recusado",offer:"oferta"};
const REG = [["ALL","Todas"],["EU","🇪🇺 Europa"],["GLOBAL","🌍 Remoto global / LATAM"],["BR","🇧🇷 Brasil"],["OUTRA","Outras"]];
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let tab = "ALL", sortK = "score", sortDir = -1, current = null, lang = "en";

const dayMs = 864e5, t0 = Date.parse(TODAY);
JOBS.forEach(j => {
  const d = j.posted_at || j.first_seen;
  j.age = d ? Math.max(0, Math.round((t0 - Date.parse(d.slice(0, 10))) / dayMs)) : null;
  const blob = (j.title + " " + (j.tags || "")).toLowerCase();
  j.cv = j.region === "BR" ? "PT" : (j.cv_variant || (/\bbi\b|power bi|business intelligence|dashboard/.test(blob) ? "BI" : "DA"));
  j.easy = /candidatura simplificada/.test(j.tags || "");
});

[...new Set(JOBS.map(j => j.source))].sort().forEach(s => $("source").insertAdjacentHTML("beforeend", `<option>${esc(s)}</option>`));
if (CFG.default_source && JOBS.some(j => j.source === CFG.default_source)) $("source").value = CFG.default_source;
if ([7,14,21,30].includes(CFG.max_age_days)) $("age").value = String(CFG.max_age_days);

function ageText(a){ return a == null ? "—" : a === 0 ? "hoje" : a === 1 ? "ontem" : `há ${a} dias`; }
function base(){
  const st = $("status").value, q = $("q").value.toLowerCase(), src = $("source").value,
        min = +$("min").value || 0, rem = $("remote").checked, maxAge = +$("age").value;
  return JOBS.filter(j =>
    (st === "all" || j.status === st || (st === "mine" && MINE[j.status])) &&
    (!src || j.source === src) && (j.score ?? 0) >= min && (!rem || j.remote) &&
    (!maxAge || st === "mine" || j.age == null || j.age <= maxAge) &&
    (!q || (j.title + " " + j.company + " " + j.location).toLowerCase().includes(q)));
}
function render(){
  const b = base();
  $("tabs").innerHTML = REG.map(([k, l]) => {
    const n = k === "ALL" ? b.length : b.filter(j => (j.region || "OUTRA") === k).length;
    return `<button class="tab ${k === tab ? "on" : ""}" data-t="${k}">${l} (${n})</button>`;
  }).join("");
  const list = b.filter(j => tab === "ALL" || (j.region || "OUTRA") === tab).sort((a, c) => {
    const x = a[sortK] ?? "", y = c[sortK] ?? ""; return (x > y ? 1 : x < y ? -1 : 0) * sortDir; });
  $("count").textContent = `${list.length} vagas exibidas de ${JOBS.length} no banco`;
  $("rows").innerHTML = list.slice(0, 1500).map(j => {
    const s = j.score ?? 0, cls = s >= 60 ? "g" : s >= 40 ? "m" : "b";
    const lo = j.salary_min_eur || j.salary_max_eur, hi = j.salary_max_eur || j.salary_min_eur;
    const sal = lo ? `${Math.round(lo / 1000)}–${Math.round(hi / 1000)}k` : (j.salary_raw ? esc(j.salary_raw) : "—");
    const pills = [
      j.first_seen === TODAY ? '<span class="pill new">nova hoje</span>' : "",
      MINE[j.status] ? `<span class="pill st">${MINE[j.status]}${j.applied_at ? " · " + esc(j.applied_at) : ""}</span>` : "",
      j.status === "closed" ? '<span class="pill old">encerrada</span>' : "",
      j.easy ? '<span class="pill">candidatura simplificada</span>' : "",
      j.age != null && j.age > 21 && !MINE[j.status] ? '<span class="pill old">antiga, pode ter fechado</span>' : ""].join("");
    return `<tr><td class="n ${cls}">${s}</td>
      <td><a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a>
        <div class="mob">${esc(j.company)} · ${esc(j.location)}</div>${pills}
        <div class="acts"><button class="btn pri" data-kit="${esc(j.id)}">kit</button>
        <button class="btn" data-copy="${esc(j.id)}" data-st="aplicado" title="Copia a linha para data/candidaturas.csv">apliquei</button>
        <button class="btn" data-copy="${esc(j.id)}" data-st="encerrada" title="Vaga preenchida ou link quebrado">encerrada</button></div></td>
      <td>${esc(j.company)}</td><td>${esc(j.location)}${j.remote ? ' <span class="pill">remoto</span>' : ""}</td>
      <td><span class="pill">${esc(j.source)}</span></td><td>${sal}</td>
      <td style="white-space:nowrap">${ageText(j.age)}</td><td class="why">${esc(j.why)}</td></tr>`;
  }).join("") || '<tr><td colspan="8" style="color:var(--mut);padding:24px">Nenhuma vaga com esses filtros. Tente "Qualquer data" ou "Todas as fontes".</td></tr>';
}

function fill(t, j){
  if (!j.company) t = t.replaceAll(" ({company})", "");
  return t.replaceAll("{title}", j.title).replaceAll("{company}", j.company || "your company").trim();
}
function openKit(id){
  current = JOBS.find(j => j.id === id); if (!current) return;
  lang = current.region === "BR" ? "pt" : "en"; drawKit(); $("kit").classList.add("on");
}
function drawKit(){
  const j = current, texts = (KIT.texts || {})[lang] || [], answers = (KIT.answers || {})[lang] || [],
        priv = (KIT.private || {})[lang] || [], cvName = (KIT.cv || {})[j.cv] || j.cv;
  const qa = rows => rows.map((r, i) => `<div class="qa"><div><div class="q">${esc(r[0])}</div><div class="a">${esc(r[1])}</div></div>
      <button class="btn" data-val="${esc(r[1])}">copiar</button></div>`).join("");
  $("kitbox").innerHTML = `<button class="close" data-close="1" aria-label="Fechar">×</button>
    <h2>${esc(j.title)}</h2><div class="sub">${esc(j.company)} · ${esc(j.location)} · <a href="${esc(j.url)}" target="_blank" rel="noopener">abrir vaga</a></div>
    <h3>Currículo</h3><div>Use o <b>${esc(cvName)}</b>${j.easy ? " · esta vaga aceita Candidatura simplificada" : ""}</div>
    <h3>Texto de apresentação <span class="lang">
      <button class="btn ${lang === "en" ? "pri" : ""}" data-lang="en">EN</button>
      <button class="btn ${lang === "pt" ? "pri" : ""}" data-lang="pt">PT</button></span></h3>
    ${texts.map((t, i) => { const body = fill(t.body, j); return `<div class="txt"><div class="hd">
      <div><b>${esc(t.label)}</b> <span class="sub">· ${esc(t.hint || "")}</span></div>
      <div><span class="sub" id="cc${i}">${body.length} caracteres</span> <button class="btn pri" data-ta="ta${i}">copiar</button></div></div>
      <textarea id="ta${i}" data-cc="cc${i}">${esc(body)}</textarea></div>`; }).join("")}
    <div class="note">Os textos podem ser editados aqui antes de copiar. Se o formulário tiver limite de caracteres, use a versão menor.</div>
    <h3>Respostas prontas</h3>${qa(answers)}
    ${priv.length ? `<h3>Privadas (só no relatório local)</h3>${qa(priv)}` : ""}
    <div class="acts" style="margin-top:14px"><button class="btn" data-copy="${esc(j.id)}" data-st="aplicado">apliquei</button>
      <button class="btn" data-copy="${esc(j.id)}" data-st="encerrada">encerrada</button></div>`;
}

function copy(text, msg){
  const done = () => toast(msg || "Copiado");
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, () => prompt("Copie:", text));
  else { const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select();
         try { document.execCommand("copy"); done(); } catch (e) { prompt("Copie:", text); } t.remove(); }
}
function toast(m){ const e = $("toast"); e.textContent = m; e.style.opacity = 1; clearTimeout(toast.t); toast.t = setTimeout(() => e.style.opacity = 0, 2600); }

document.addEventListener("click", e => {
  const d = e.target.dataset || {};
  if (d.kit) return openKit(d.kit);
  if (d.close || e.target.id === "kit") return $("kit").classList.remove("on");
  if (d.lang) { lang = d.lang; return drawKit(); }
  if (d.ta) return copy($(d.ta).value, "Texto copiado");
  if (d.val !== undefined) return copy(d.val, "Resposta copiada");
  if (d.copy) { const line = `${d.copy},${d.st},${TODAY},`;
    return copy(line, `Copiado: ${line} → cole em data/candidaturas.csv`); }
  if (d.t) { tab = d.t; return render(); }
  if (d.k) { sortDir = d.k === sortK ? -sortDir : -1; sortK = d.k; return render(); }
});
document.addEventListener("input", e => { if (e.target.dataset.cc) $(e.target.dataset.cc).textContent = e.target.value.length + " caracteres"; });
document.addEventListener("keydown", e => { if (e.key === "Escape") $("kit").classList.remove("on"); });
["q","status","source","age","min","remote"].forEach(id => $(id).addEventListener("input", render));
render();
</script></body></html>"""


def _load_kit(cfg, path="kit.yaml"):
    kit = {}
    if os.path.exists(path):
        kit = yaml.safe_load(open(path, encoding="utf-8")) or {}
    # respostas privadas: só no relatório local, nunca no GitHub Actions/Pages
    if not os.getenv("GITHUB_ACTIONS") and (cfg or {}).get("kit_private"):
        kit["private"] = cfg["kit_private"]
    return kit


def build(con, cfg=None, path="data/relatorio.html"):
    have = {r[1] for r in con.execute("PRAGMA table_info(jobs)")}
    sel = ", ".join(c if c in have else f"NULL AS {c}" for c in COLS)
    score = "COALESCE(llm_score, heur_score) AS score" if "llm_score" in have else "heur_score AS score"
    why = "COALESCE(llm_summary, heur_reasons) AS why" if "llm_summary" in have else "heur_reasons AS why"
    rows = [dict(r) for r in con.execute(f"SELECT {sel}, {score}, {why} FROM jobs")]
    rep = (cfg or {}).get("report", {})
    js = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")  # noqa: E731
    now = datetime.now()
    html = (TEMPLATE.replace("__DATA__", js(rows)).replace("__KIT__", js(_load_kit(cfg)))
            .replace("__CFG__", js({"default_source": rep.get("default_source", ""),
                                    "max_age_days": rep.get("max_age_days", 21)}))
            .replace("__DATE__", now.strftime("%d/%m/%Y %H:%M")).replace("__TODAY__", now.strftime("%Y-%m-%d")))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return len(rows)
