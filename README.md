# pond-s7m10-cicd-lab

Experimento de instrumentação CI/CD — Ponderada S7M10.

Mini TODO API em FastAPI usada como cobaia para medir comportamento de pipeline
no GitHub Actions: tempo total, tempo por job, impacto de cache, paralelismo,
falhas, etc.

## Estrutura

```
.
├── .github/workflows/ci.yml   # pipeline CI (lint + test)
├── app/                       # FastAPI TODO API
├── tests/                     # pytest
├── scripts/                   # coleta de métricas + gráficos (Parte 2)
├── data/                      # CSV/JSON gerados
├── figures/                   # gráficos PNG
├── evidence/                  # screenshots das runs
├── experiment-log.md          # registro manual das execuções
└── report.md                  # relatório técnico (Parte 2)
```

## Rodar local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest
ruff check app tests
```

## Reproduzir a coleta de métricas

```bash
cp .env.example .env  # preencher GITHUB_TOKEN (fine-grained, Actions+Contents read)
pip install -r scripts/requirements.txt
python scripts/collect_metrics.py --env .env --out data/
python scripts/plot.py --summary data/runs_summary.csv --long data/runs_long.csv --out figures/
```

## Documentos do experimento

- `experiment-log.md` — log manual das 12+ execuções (run_id, commit, hipótese, observação).
- `report.md` — relatório técnico final com gráficos, análise das 8 perguntas e discussão de limitações.
