#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
source .env
python -m job_bot.main
open data/relatorio.html
