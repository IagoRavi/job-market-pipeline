#!/bin/bash
# Atualiza o projeto a partir do zip extraído em ~/Downloads/robo-vagas.
# RODE DE DENTRO DA PASTA DO PROJETO (ex.: cd ~/Documents/robo-vagas).
# Preserva: data/, digests/, .env, config.local.yaml, .venv e o report_url do config.yaml.
set -e
NOVO="$(cd "${1:-$HOME/Downloads/robo-vagas}" 2>/dev/null && pwd -P)" || { echo "Não achei o projeto novo em ${1:-$HOME/Downloads/robo-vagas}."; exit 1; }
AQUI="$(pwd -P)"
[ -f "$NOVO/job_bot/main.py" ] || { echo "Em $NOVO não há o código novo (extraia o zip lá)."; exit 1; }
[ "$AQUI" != "$NOVO" ] || { echo "Rode de dentro da pasta do projeto (ex.: cd ~/Documents/robo-vagas), não da pasta de Downloads."; exit 1; }
[ -f config.yaml ] && [ -d job_bot ] || { echo "Esta pasta não parece ser o projeto (sem config.yaml/job_bot). Entre nela com cd e rode de novo."; exit 1; }

echo "1/5 Buscando o que o robô salvou no GitHub…"
if [ -d .git ] && git remote get-url origin >/dev/null 2>&1; then git pull --rebase --autostash; else echo "   (sem repositório remoto, pulando)"; fi

echo "2/5 Copiando o código novo…"
URL=$(python3 -c 'import re,sys
try: s=open("config.yaml",encoding="utf-8").read()
except OSError: sys.exit()
m=re.search(r"^[ \t]*report_url:[ \t]*\"([^\"]*)\"", s, re.M)
print(m.group(1) if m else "")')
rm -rf job_bot tests
cp -R "$NOVO/job_bot" "$NOVO/tests" .
mkdir -p .github && cp -R "$NOVO/.github/workflows" .github/
for f in config.yaml kit.yaml README.md requirements.txt rodar.sh atualizar.sh; do
  [ -f "$NOVO/$f" ] && cp "$NOVO/$f" .
done
chmod +x rodar.sh atualizar.sh
mkdir -p data && [ -f data/candidaturas.csv ] || cp "$NOVO/data/candidaturas.csv" data/

echo "3/5 Preservando seu link do relatório…"
if [ -n "$URL" ]; then
  python3 - "$URL" <<'PY'
import re, sys
p = "config.yaml"; s = open(p, encoding="utf-8").read()
s = re.sub(r'(?m)^(\s*report_url:\s*)"[^"]*"', lambda m: f'{m.group(1)}"{sys.argv[1]}"', s)
open(p, "w", encoding="utf-8").write(s)
PY
  echo "   report_url = $URL"
else
  echo "   (nenhum report_url definido antes)"
fi

echo "4/5 Conferindo config.local.yaml…"
if [ -f config.local.yaml ] && ! grep -q '^kit_private:' config.local.yaml && grep -q '^kit_private:' "$NOVO/config.local.yaml"; then
  printf '\n' >> config.local.yaml
  sed -n '/^# Kit de candidatura: respostas PRIVADAS/,$p' "$NOVO/config.local.yaml" >> config.local.yaml
  echo "   seção kit_private acrescentada (preencha o que estiver como PREENCHER)"
else
  echo "   nada a acrescentar"
fi

echo "5/5 Rodando os testes…"
[ -d .venv ] && source .venv/bin/activate
python3 -m tests.test_linkedin | tail -1
echo
echo "Pronto. Agora: ./rodar.sh para testar e, no VS Code, Commit + Sync Changes para enviar ao GitHub."
