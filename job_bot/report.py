"""Relatório HTML com TODAS as vagas do banco, com abas por região e filtros.
Abra data/relatorio.html no navegador. Não depende de internet."""
import json

COLS = """id, title, company, location, region, source, remote, url, first_seen,
salary_min_eur, salary_max_eur, COALESCE(llm_score, heur_score) AS score, status,
COALESCE(llm_summary, heur_reasons) AS why, notified, applied_at, notes"""

TEMPLATE = r"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="robots" content="noindex, nofollow"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Robô de vagas</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2433;--mut:#6b7280;--line:#e5e7eb;--acc:#1f4e79;--good:#15803d;--mid:#b45309;--bad:#b91c1c}
@media (prefers-color-scheme:dark){:root{--bg:#111418;--card:#1a1f26;--fg:#e6e9ee;--mut:#9aa3af;--line:#2a313b;--acc:#7fb2e5;--good:#4ade80;--mid:#fbbf24;--bad:#f87171}}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--fg)}
header{padding:20px 24px 8px}h1{margin:0;font-size:20px}header p{margin:4px 0 0;color:var(--mut)}
.tabs{display:flex;gap:6px;flex-wrap:wrap;padding:8px 24px}
.tab{border:1px solid var(--line);background:var(--card);color:var(--fg);padding:6px 12px;border-radius:999px;cursor:pointer}
.tab.on{background:var(--acc);border-color:var(--acc);color:#fff}
.filters{display:flex;gap:10px;flex-wrap:wrap;align-items:center;padding:8px 24px 14px}
.filters input,.filters select{padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg)}
.wrap{padding:0 24px 32px;overflow-x:auto}table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{position:sticky;top:0;background:var(--card);cursor:pointer;white-space:nowrap;font-size:12px;color:var(--mut);text-transform:uppercase}
td.n{font-weight:700;text-align:center}.g{color:var(--good)}.m{color:var(--mid)}.b{color:var(--bad)}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.why{color:var(--mut);font-size:12px;max-width:380px}.pill{font-size:11px;padding:1px 6px;border-radius:4px;border:1px solid var(--line);color:var(--mut);white-space:nowrap}
.new{background:var(--acc);color:#fff;border-color:var(--acc)}
.st{background:var(--good);color:#fff;border-color:var(--good)}
.cp{margin-top:4px;font-size:11px;padding:1px 6px;border:1px solid var(--line);border-radius:4px;background:transparent;color:var(--mut);cursor:pointer}
.cp:hover{color:var(--acc);border-color:var(--acc)}
#toast{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:var(--fg);color:var(--bg);padding:8px 14px;border-radius:6px;opacity:0;transition:opacity .3s;font-size:13px}
</style></head><body>
<header><h1>Robô de vagas</h1><p>Atualizado em __DATE__ · <span id="count"></span></p></header>
<div class="tabs" id="tabs"></div>
<div class="filters">
 <input id="q" placeholder="Buscar título, empresa, local…" size="28">
 <select id="status"><option value="new">Relevantes</option><option value="mine">Minhas candidaturas</option><option value="below_floor">Abaixo do piso salarial</option>
  <option value="discard">Descartadas pelo filtro</option><option value="all">Todas</option></select>
 <select id="source"><option value="">Todas as fontes</option></select>
 <label>Nota mínima <input id="min" type="number" value="0" min="0" max="100" style="width:64px"></label>
 <label><input id="remote" type="checkbox"> Só remotas</label>
</div>
<div class="wrap"><table><thead><tr>
 <th data-k="score">Nota</th><th data-k="title">Vaga</th><th data-k="company">Empresa</th><th data-k="location">Local</th>
 <th data-k="source">Fonte</th><th data-k="salary_max_eur">Salário (€/ano)</th><th data-k="first_seen">Visto em</th><th>Por quê</th>
</tr></thead><tbody id="rows"></tbody></table></div>
<div id="toast"></div>
<script>
const JOBS = __DATA__, TODAY = "__TODAY__";
const MINE = {applied:"aplicado",interview:"entrevista",rejected:"recusado",offer:"oferta"};
function copyLine(id){const d=new Date().toISOString().slice(0,10),t=`${id},aplicado,${d},`;
 (navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(()=>toast("Copiado: "+t),()=>prompt("Copie a linha:",t));}
function toast(m){const e=document.getElementById("toast");e.textContent=m;e.style.opacity=1;setTimeout(()=>e.style.opacity=0,2500);}
const REG = [["ALL","Todas"],["EU","🇪🇺 Europa"],["GLOBAL","🌍 Remoto global / LATAM"],["BR","🇧🇷 Brasil"],["OUTRA","Outras"]];
let tab="ALL", sortK="score", sortDir=-1;
const $=id=>document.getElementById(id), esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
[...new Set(JOBS.map(j=>j.source))].sort().forEach(s=>$("source").insertAdjacentHTML("beforeend",`<option>${esc(s)}</option>`));
function base(){const st=$("status").value,q=$("q").value.toLowerCase(),src=$("source").value,min=+$("min").value||0,rem=$("remote").checked;
 return JOBS.filter(j=>(st==="all"||j.status===st||(st==="mine"&&MINE[j.status]))&&(!src||j.source===src)&&(j.score??0)>=min&&(!rem||j.remote)
  &&(!q||(j.title+" "+j.company+" "+j.location).toLowerCase().includes(q)));}
function render(){const b=base();
 $("tabs").innerHTML=REG.map(([k,l])=>{const n=k==="ALL"?b.length:b.filter(j=>(j.region||"OUTRA")===k).length;
  return `<button class="tab ${k===tab?"on":""}" data-t="${k}">${l} (${n})</button>`}).join("");
 const list=b.filter(j=>tab==="ALL"||(j.region||"OUTRA")===tab).sort((a,c)=>{const x=a[sortK]??"",y=c[sortK]??"";return (x>y?1:x<y?-1:0)*sortDir});
 $("count").textContent=`${list.length} vagas exibidas de ${JOBS.length} no banco`;
 $("rows").innerHTML=list.slice(0,1500).map(j=>{const s=j.score??0,cls=s>=60?"g":s>=40?"m":"b";
  const sal=j.salary_max_eur||j.salary_min_eur?`${Math.round((j.salary_min_eur||j.salary_max_eur)/1000)}–${Math.round((j.salary_max_eur||j.salary_min_eur)/1000)}k`:"—";
  return `<tr><td class="n ${cls}">${s}</td><td><a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a>
   ${j.first_seen===TODAY?' <span class="pill new">hoje</span>':""}${MINE[j.status]?` <span class="pill st">${MINE[j.status]}${j.applied_at?" · "+esc(j.applied_at):""}</span>`:""}
   <br><button class="cp" data-id="${esc(j.id)}" title="Copia a linha para colar em data/candidaturas.csv">copiar p/ candidaturas</button></td><td>${esc(j.company)}</td>
   <td>${esc(j.location)}${j.remote?' <span class="pill">remoto</span>':""}</td><td><span class="pill">${esc(j.source)}</span></td>
   <td>${sal}</td><td style="white-space:nowrap">${esc((j.first_seen||"").split("-").reverse().join("/"))}</td><td class="why">${esc(j.why)}</td></tr>`}).join("");}
document.addEventListener("click",e=>{if(e.target.dataset.id){copyLine(e.target.dataset.id);return}if(e.target.dataset.t){tab=e.target.dataset.t;render()}
 const k=e.target.dataset&&e.target.dataset.k;if(k){sortDir=k===sortK?-sortDir:-1;sortK=k;render()}});
["q","status","source","min","remote"].forEach(id=>$(id).addEventListener("input",render));
render();
</script></body></html>"""


def build(con, path="data/relatorio.html"):
    from datetime import datetime
    have = {r[1] for r in con.execute("PRAGMA table_info(jobs)")}
    cols = COLS if "applied_at" in have else COLS.replace(", applied_at, notes", ", NULL AS applied_at, NULL AS notes")
    rows = [dict(r) for r in con.execute(f"SELECT {cols} FROM jobs")]
    data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("__DATA__", data).replace("__DATE__", datetime.now().strftime("%d/%m/%Y %H:%M")).replace("__TODAY__", datetime.now().strftime("%Y-%m-%d"))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return len(rows)
