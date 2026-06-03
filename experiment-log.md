# Log do experimento — Pond S7M10

## Resumo

| # | run_id | commit_sha | descrição | status | duração total | hipótese | observação |
|---|--------|-----------|-----------|--------|---------------|----------|------------|
| 1 | 26889692930 | c16deeb | baseline (7 testes, cache on, sequencial) | ✅ | 33s | rápido, ~1-2min, install dominante | passou rápido (lint 10s + test 15s); install foi mais rápido que esperado mesmo na 1ª run |
| 2 | 26890173516 | 4e759e3 | teste falhando (status_code errado) | ❌ | 29s | lint passa, test falha | confirmado: lint 8s ✅, test 14s ❌; artifact 641B (junit registrou falha) |
| 3 | 26890350804 | 4f61d57 | fix do teste anterior | ✅ | 35s | volta verde, install rápido (cache hit) | verde confirmado mas total +2s vs Run 1 — cache NÃO acelerou tanto; variabilidade do runner já visível |
| 4 | 26890470856 | 105e85f | +20 testes parametrizados | ✅ | 37s | test_count ~27, job test +alguns seg | test_count=27, job test 16s (+4s vs Run 3) ~200ms/teste, artifact 475B |
| 5 | 26890700597 | 2a3598b | +100 testes | ✅ | 33s | test_count ~107, job test sobe mais | ⚠️ INESPERADO: test=16s, IGUAL à Run 4. Não escalou linear (esperado ~32s); overhead fixo do pytest domina, 100 POSTs em SQLite :memory: somam <1s |
| 6 | 26890917608 | ae3b503 | teste lento (sleep 5s) | ✅ | 35s | job test +5s | test 16→19s = +3s (não +5s); runner jitter ~2s absorveu parte; sleep escala linear como esperado |
| 7 | 26891429817 | b5a78d8 | cache pip desligado | ✅ | 37s | install dispara em ambos jobs | ⚠️ INESPERADO: test +2s só (19→21s), lint igual. Cache pip ~irrelevante p/ deps pequenas no runner GitHub |
| 8 | 26891585287 | d52df13 | cache pip religado | ✅ | 39s | 1ª run = cache miss (lento ainda) | test 21→19s (−2s) e lint 7→8s; total subiu 37→39s mesmo com cache; cache pip ~negligível confirmado |
| 9 | 26891782877 | 667228b | jobs lint e test em paralelo | ✅ | 24s | total ≈ max(lint, test) | confirmado: total 39→24s (−15s = −38%); lint 8s + test 18s paralelos; ganho > do que qualquer cache |
| 10 | 26891901602 | d455ce7 | lint falhando (import não usado) | ❌ | 23s | lint falha rápido | lint 10s ❌ (F401), test 18s ✅ paralelo; workflow ❌; em modo sequencial test nem teria iniciado |
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
Link da run: https://github.com/Renan-coding/pond-s7m10-cicd/actions/runs/26890700597
Hipótese: `test_count` ~107, job test sobe mais — DB roundtrip por teste vira gargalo.
Observação: ⚠️ **RESULTADO INESPERADO**. `test_count` = 107 (confirma), mas job test = 16s — **idêntico à Run 4 (27 testes)**. Esperava ~32s assumindo escala linear ~200ms/teste. Realidade: 100 POSTs em SQLite `:memory:` somam <1s; overhead fixo (`pytest` collection, import FastAPI, SQLAlchemy setup, TestClient warm-up) domina. A regressão linear "tempo × #testes" desabou. Artifact subiu de 475B → 714B — XML do JUnit cresceu com cada `<testcase>`, mas isso é negligível no tempo. Lição: para gargalo real de tempo, o número de testes só importa quando cada teste tem custo individual significativo (I/O, rede, sleep).

### Run 6 — Teste lento
Mudança: adicionar `test_slow` com `time.sleep(5)` em `tests/test_tasks.py`.
Link da run: https://github.com/Renan-coding/pond-s7m10-cicd/actions/runs/26890917608
Hipótese: job test +5s lineares. Bom material para o cálculo de tempo médio.
Observação: confirmado direcionalmente. Job test 16s → 19s (+3s, não +5s esperado). Diferença de ~2s vem do jitter do runner (visto também em Run 3 vs Run 1: ±2-5s sem mudança real). Importante: ao contrário da Run 5 (100 testes rápidos sem efeito mensurável), o `time.sleep(5)` SIM aparece — confirma que tempo de pipeline é dominado por operações que efetivamente bloqueiam, não pela contagem de testes.

### Run 7 — Cache desligado
Mudança: remover `cache: 'pip'` + `cache-dependency-path` de ambos os jobs em `ci.yml`.
Link da run: https://github.com/Renan-coding/pond-s7m10-cicd/actions/runs/26891429817
Hipótese: passo "Install" dispara ~15-30s em cada job — pip baixa todos os wheels.
Observação: ⚠️ **RESULTADO INESPERADO**. Job test 19s → 21s (+2s); lint manteve 7s. Diferença muito menor que o estimado (~15-30s). Deps deste projeto (`fastapi`, `sqlalchemy`, `pydantic`, `pytest`, `httpx`, `ruff`) totalizam ~30MB de wheels. Bandwidth do runner GitHub vs PyPI é muito alto (centenas de Mbps), então download desses pacotes leva poucos segundos. **Conclusão**: cache pip é uma otimização prematura para projetos com dependências leves; o ganho só compensa em stacks pesadas (PyTorch, pandas+numpy compiladas, etc). Material direto para resposta à pergunta "Houve diferença significativa entre execuções com e sem cache?".

### Run 8 — Cache religado
Mudança: restaurar `cache: 'pip'` + `cache-dependency-path`.
Link da run: https://github.com/Renan-coding/pond-s7m10-cicd/actions/runs/26891585287
Hipótese: cache miss na 1ª run (GitHub recria entrada após gap). Pode parecer tão lento quanto a run 7. **Possível resultado inesperado**.
Observação: cache miss não foi notável (test 21s → 19s, lint 7s → 8s — diferença <2s). Total 39s vs 37s da Run 7 — **com cache ligado o pipeline foi LIGEIRAMENTE MAIS LENTO**, dentro do envelope de variabilidade. Reforça a conclusão da Run 7: cache pip não traz ganho material nesta stack. Triplet Run 6 (cache ON, sem mudança) = 35s, Run 7 (cache OFF) = 37s, Run 8 (cache ON religado) = 39s — variação de 4s sem relação clara com o cache.

### Run 9 — Jobs em paralelo
Mudança: remover `needs: lint` do job `test` em `ci.yml`.
Link da run: https://github.com/Renan-coding/pond-s7m10-cicd/actions/runs/26891782877
Hipótese: duração total ≈ max(lint, test) ao invés de lint+test.
Observação: **confirmado com folga**. Total 39s (Run 8) → 24s (Run 9) = −15s (−38%). Lint (8s) e test (18s) rodaram simultaneamente; total ≈ max(jobs) + ~6s de overhead único de provisionamento. UI do GitHub mostra os 2 jobs empilhados sem seta entre eles (visual claro de execução paralela). **Achado mais forte do experimento até aqui**: paralelizar jobs sequenciais traz ganho muito maior (15s) que qualquer otimização de cache observada (≤2s). Custo: jobs paralelos consomem o dobro de minutos-runner, mas latência de feedback cai pela metade — tradeoff geralmente compensa.

### Run 10 — Lint falhando
Mudança: adicionar `import os` não usado em `app/main.py`.
Link da run: https://github.com/Renan-coding/pond-s7m10-cicd/actions/runs/26891901602
Hipótese: ruff falha rápido (F401). Test ainda roda em paralelo — pode passar — mas workflow vermelho.
Observação: confirmado integralmente. Lint quebrou em 10s (F401 `os` imported but unused, exit code 1). Test rodou em paralelo, passou em 18s. Workflow status = Failure por conta do lint, mas test gerou artifact normal (725B, sem `<failure>`). **Vantagem do paralelismo emergiu naturalmente aqui**: em modo sequencial (`needs: lint`), o test nem seria iniciado e o desenvolvedor só veria o erro do lint — em paralelo, ele recebe AMBAS as informações em uma rodada (lint quebrado + testes funcionando), economizando uma iteração de feedback.

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
