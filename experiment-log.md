# Log do experimento — Pond S7M10

## Resumo

| # | run_id | commit_sha | descrição | status | duração total | hipótese | observação |
|---|--------|-----------|-----------|--------|---------------|----------|------------|
| 1 | 26889692930 | c16deeb | baseline (7 testes, cache on, sequencial) | ✅ | 33s | rápido, ~1-2min, install dominante | passou rápido (lint 10s + test 15s); install foi mais rápido que esperado mesmo na 1ª run |
| 2 | 26890173516 | 4e759e3 | teste falhando (status_code errado) | ❌ | 29s | lint passa, test falha | confirmado: lint 8s ✅, test 14s ❌; artifact 641B (junit registrou falha) |
| 3 | 26890350804 | 4f61d57 | fix do teste anterior | ✅ | 35s | volta verde, install rápido (cache hit) | verde confirmado mas total +2s vs Run 1 — cache NÃO acelerou tanto; variabilidade do runner já visível |
| 4 | 26890470856 | 105e85f | +20 testes parametrizados | ✅ | 37s | test_count ~27, job test +alguns seg | test_count=27, job test 16s (+4s vs Run 3) ~200ms/teste, artifact 475B |
| 5 |  |  | +100 testes | ⬜ |  | test_count ~107, job test sobe mais | |
| 6 |  |  | teste lento (sleep 5s) | ⬜ |  | job test +5s | |
| 7 |  |  | cache pip desligado | ⬜ |  | install dispara em ambos jobs | |
| 8 |  |  | cache pip religado | ⬜ |  | 1ª run = cache miss (lento ainda) | |
| 9 |  |  | jobs lint e test em paralelo | ⬜ |  | total ≈ max(lint, test) | |
| 10 |  |  | lint falhando (import não usado) | ⬜ |  | lint falha rápido | |
| 11 |  |  | dependência pesada (pandas+numpy) | ⬜ |  | cache miss + download = install lento | |
| 12 |  |  | re-run sem mudança (workflow_dispatch) | ⬜ |  | tempo diferente da 11 (variabilidade) | |

## Variações detalhadas

### Run 1 — Baseline
Configuração inicial: 7 testes pytest, cache pip ligado, jobs sequenciais (`test` precisa de `lint`).
Link da run: https://github.com/Renan-coding/pond-s7m10-cicd/actions/runs/26889692930
Hipótese: pipeline verde, ~1-2 minutos, etapa "Install dependencies" dominante por ser primeiro run (cache miss).
Observação: duração total 33s (lint 10s, test 15s, ~8s overhead de setup/checkout). Mais rápido que o estimado — install não foi o gargalo mesmo sem cache prévio, provavelmente porque o pool de wheels do PyPI + bandwidth do runner GitHub é alto. Artifact `test-report-26889692930.zip` (386B) gerado. 7 testes passaram.

### Run 2 — Teste falhando
Mudança: `tests/test_tasks.py` — `test_create` espera status 200 (era 201).
Link da run: https://github.com/Renan-coding/pond-s7m10-cicd/actions/runs/26890173516
Hipótese: job `lint` passa, job `test` falha, workflow vermelho. Artifact `report.xml` ainda é gerado (`if: always()`).
Observação: confirmado integralmente. Lint passou em 8s (mais rápido que Run 1 — cache pip hit reduziu install). Test rodou 14s e falhou (`AssertionError: 201 != 200`). Artifact gerado mesmo com falha (641B vs 386B da Run 1 — tag `<failure>` adiciona bytes). Total 29s vs 33s da Run 1 — pequena melhora pelo cache.

### Run 3 — Fix
Mudança: reverter `test_create` para status 201.
Link da run: https://github.com/Renan-coding/pond-s7m10-cicd/actions/runs/26890350804
Hipótese: pipeline volta verde, install rápido (cache hit do hash idêntico ao da run 1).
Observação: verde como esperado, mas duração 35s — MAIOR que Run 1 (33s) e Run 2 (29s). Lint 13s vs 8s (Run 2). Cache hit não trouxe ganho dramático — sugere que `pip install` no cenário com poucas deps já era barato, e a variação observada (~5-7s) reflete principalmente jitter do runner GitHub. Primeiro indício de variabilidade material entre execuções idênticas.

### Run 4 — +20 testes parametrizados
Mudança: criar `tests/test_bulk.py` com 20 testes parametrizados de POST /tasks.
Link da run: https://github.com/Renan-coding/pond-s7m10-cicd/actions/runs/26890470856
Hipótese: `test_count` sobe para ~27, duração do job test sobe alguns segundos.
Observação: confirmado. `test_count` = 27. Job test 16s vs 12s da Run 3 → ~200ms por teste novo (POST + DB write + asserções). Artifact subiu para 475B (mais `<testcase>` no JUnit XML). Lint igual a Run 3 (13s) — espaço de busca do ruff cresceu pouco.

### Run 5 — +100 testes
Mudança: `range(20)` → `range(100)` em `test_bulk.py`.
Link da run:
Hipótese: `test_count` ~107, job test sobe mais — DB roundtrip por teste vira gargalo.
Observação:

### Run 6 — Teste lento
Mudança: adicionar `test_slow` com `time.sleep(5)` em `tests/test_tasks.py`.
Link da run:
Hipótese: job test +5s lineares. Bom material para o cálculo de tempo médio.
Observação:

### Run 7 — Cache desligado
Mudança: remover `cache: 'pip'` + `cache-dependency-path` de ambos os jobs em `ci.yml`.
Link da run:
Hipótese: passo "Install" dispara ~15-30s em cada job — pip baixa todos os wheels.
Observação:

### Run 8 — Cache religado
Mudança: restaurar `cache: 'pip'` + `cache-dependency-path`.
Link da run:
Hipótese: cache miss na 1ª run (GitHub recria entrada após gap). Pode parecer tão lento quanto a run 7. **Possível resultado inesperado**.
Observação:

### Run 9 — Jobs em paralelo
Mudança: remover `needs: lint` do job `test` em `ci.yml`.
Link da run:
Hipótese: duração total ≈ max(lint, test) ao invés de lint+test.
Observação:

### Run 10 — Lint falhando
Mudança: adicionar `import os` não usado em `app/main.py`.
Link da run:
Hipótese: ruff falha rápido (F401). Test ainda roda em paralelo — pode passar — mas workflow vermelho.
Observação:

### Run 11 — Dependência pesada
Mudança: reverter import inútil; adicionar `pandas==2.2.2` e `numpy==2.1.0` em `requirements.txt`.
Link da run:
Hipótese: cache miss (hash mudou) + download dessas libs = install ~30-60s.
Observação:

### Run 12 — Re-run via workflow_dispatch
Mudança: nenhuma — disparo manual.
Link da run:
Hipótese: tempo diferente da run 11 mesmo com cache hit total — variabilidade do runner GitHub. **Resultado inesperado para o relatório**.
Observação:

## Hipótese × observação

Preencher após coletar todas as runs:

| # | hipótese | observado | match? |
|---|----------|-----------|--------|
| 1 |  |  |  |
| ... |
