# Robô de vagas — Europa

Coleta vagas de BI/Dados na Europa e no Brasil, filtra o que um candidato no Brasil consegue
de fato pegar (remoto de LATAM, relocação com visto, ou vaga brasileira remota/em Brasília),
dá nota de aderência e manda um digest diário separado por região. Roda sozinho no GitHub Actions, de segunda a sexta às 06h (Brasília).

**Não acessa o LinkedIn.** As vagas do LinkedIn vêm dos alertas que o próprio LinkedIn
manda para o seu Gmail; o robô só lê a sua caixa de entrada.

## Fluxo
1. **Coleta**: Arbeitnow, Remotive, RemoteOK, Himalayas, Adzuna (Europa + Brasil), Gupy (Brasil),
   alertas do LinkedIn por e-mail e páginas de vagas de empresas (Greenhouse, Lever, Ashby).
2. **Triagem** (`triage.py`): nota 0–100 por título, skills, elegibilidade (remoto global, visto), idioma e piso salarial.
3. **IA** (opcional): as vagas que passam no pré-filtro recebem nota, resumo em PT e a indicação do CV (BI ou DA).
4. **Saída**: `digests/AAAA-MM-DD.md`, e-mail opcional e `data/jobs.csv` para o Power BI.

## Instalação (≈15 min)
1. Crie um repositório **privado** no GitHub e suba esta pasta.
2. Em *Settings → Secrets and variables → Actions*, cadastre os secrets que quiser usar:

| Secret | Para quê | Obrigatório? |
|---|---|---|
| `ANTHROPIC_API_KEY` | nota por IA (console.anthropic.com) | recomendado |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | vagas da Alemanha, Holanda, Espanha etc. (developer.adzuna.com, grátis) | recomendado |
| `GMAIL_USER`, `GMAIL_APP_PASSWORD` | ler os alertas de vaga do LinkedIn | recomendado |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `DIGEST_TO` | digest por e-mail | opcional |

   Para o Gmail: `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=465`, `SMTP_PASS` = **senha de app** (exige verificação em 2 etapas).
3. Em *Actions → Robô de vagas → Run workflow*, rode a primeira vez manualmente.

Sem nenhum secret, o robô já funciona: coleta, faz a triagem heurística e grava o digest no repositório.

## Alertas do LinkedIn
1. No LinkedIn, pesquise a vaga (ex.: "Power BI"), aplique filtros (local, remoto) e ative
   **"Criar alerta de vaga"**, com frequência **diária** e envio **por e-mail**.
   Sugestão: um alerta para União Europeia, um para Portugal e um para Brasil (remoto).
2. No Google, crie uma **senha de app** (myaccount.google.com → Segurança → Verificação em
   duas etapas → Senhas de app) e use em `GMAIL_APP_PASSWORD`.
3. Os alertas trazem só título, empresa e local; por isso a nota dessas vagas pesa os
   filtros que você mesmo definiu no alerta.

## Ajustes no `config.yaml`
- **Brasil** (`brazil`): piso mensal em R$, cidades aceitas para presencial/híbrido e a penalidade para outras cidades.
- **Pisos salariais**: vagas sem salário divulgado não são descartadas.
- **Empresas-alvo**: adicione os identificadores em `greenhouse.boards`, `lever.companies` e `ashby.boards` (ficam na URL da página de vagas da empresa).
- **Palavras-chave e bloqueios**: termos que restringem por país ou por idioma (alemão, holandês…).

## Testar localmente sem rede
```bash
pip install -r requirements.txt
python -m job_bot.main --fixtures tests/fixtures.json --db /tmp/teste.db
python -m tests.test_linkedin      # testes do leitor de e-mails do LinkedIn
```

## Status das vagas (coluna `status`)
`new` · `below_floor` · `discard` · `applied` · `interview` · `rejected` · `offer` · `ignored`.
A marcação de candidatura entra na próxima fase, com a geração de CV e carta por vaga.

## Foco no LinkedIn (padrão desde out/2026)
As outras fontes estão desligadas no `config.yaml` (o código continua lá; basta `enabled: true`).
A qualidade das vagas depende dos **alertas** que você cria no LinkedIn, porque eles são o filtro de entrada:

| Alerta | Palavras-chave | Local | Filtros |
|---|---|---|---|
| Europa remoto | `"power bi" OR "BI developer" OR "business intelligence"` | União Europeia | Remoto · Pleno-sênior · Últimas 24h |
| Portugal | `"power bi" OR "analista de dados" OR "data analyst"` | Portugal | Remoto e híbrido |
| Alemanha/Holanda c/ visto | `"power bi" OR "BI developer"` | Alemanha (repita p/ Holanda) | Pleno-sênior |
| Brasil remoto | `"power bi" OR "analista de BI" OR "analista de dados"` | Brasil | Remoto |
| Brasília | `"power bi" OR "analista de dados"` | Brasília | Presencial e híbrido |

Teste a busca antes de salvar o alerta; frequência **diária**, envio **por e-mail**.
Os alertas trazem título, empresa, local, modelo (remoto/híbrido), salário quando informado e se a vaga
aceita **Candidatura simplificada**. O robô não acessa o LinkedIn: só lê esses e-mails no seu Gmail.

### Candidaturas automáticas
Quando você se candidata pelo LinkedIn, ele manda um e-mail "sua candidatura foi enviada para…".
O robô lê esse e-mail e acrescenta sozinho a linha `aplicado` em `data/candidaturas.csv`
(observação `auto: e-mail do LinkedIn`). Desligue com `track_applications: false`.

### Kit de candidatura
No relatório, o botão **kit** de cada vaga abre:
- qual currículo usar (BI, Data Analyst ou português);
- dois textos de apresentação (EN/PT) já com o nome da vaga e da empresa, editáveis e com contador de caracteres;
- respostas prontas para as perguntas comuns da Candidatura simplificada (`kit.yaml`).

Respostas privadas (telefone, pretensão salarial) ficam em `config.local.yaml → kit_private` e
**só aparecem no relatório gerado na sua máquina**, nunca na página pública.

### Vagas antigas ou encerradas
- O relatório mostra a idade da vaga e, por padrão, só as dos últimos 21 dias (`report.max_age_days`).
- Vaga preenchida ou com link quebrado: botão **encerrada** → cole a linha em `data/candidaturas.csv`.

## Registrar candidaturas
1. No relatório, clique em **copiar p/ candidaturas** na vaga em que você se candidatou.
2. Cole a linha em `data/candidaturas.csv` (pelo VS Code ou direto no site do GitHub, inclusive no celular):
   ```
   id,status,data,observacao
   n26:7012345,aplicado,2026-10-07,indicação do fulano
   ```
3. Status aceitos: `aplicado`, `entrevista`, `recusado`, `oferta`, `encerrada`, `ignorar`. Para avançar uma vaga, edite o status na mesma linha.
4. Na próxima execução, a vaga sai do digest e aparece no filtro **Minhas candidaturas** do relatório.
   As colunas `status`, `applied_at` e `notes` também vão para o `data/jobs.csv` (base do painel Power BI do funil).
