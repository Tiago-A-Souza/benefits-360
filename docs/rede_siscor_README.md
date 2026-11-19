# Base SiscorNet — rede hospitalar

Arquivo: `SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx` (versionado em
`docs/`).

## Abas usadas

| Aba | Uso |
|---|---|
| `Matriz_Hospital` | **Sim** — 1.071 prestadores, 51 municípios |
| `Matriz_Laboratorio` | **Sim** — bloco Labs da etapa 5 / HTML **e** menu Simular rede (marcas em `laboratorios_principais_base.csv`) |
| `Resumo` | Metadados de referência |

Cabeçalho em **quatro linhas** nas colunas de plano; cinco colunas fixas: Prestador,
Classif., Município (`UF.CIDADE`), Bairro, Região.

## Troca mensal

Substitua o `.xlsx` inteiro. Rode a suíte — `tests/test_rede_fase_c.py` valida contagem
e cruzamento com `hospitais_principais_base.csv`.

Variável opcional: `NEWPORT_REDE_XLSX` aponta para outro caminho (CI local).

## Pipeline (código)

1. `rede_matriz_hospital.py` — ingestão
2. `rede_especialidade.py` — filtro HGER / HD / PSGER / MAT
3. `rede_recorte.py` — **critério geográfico** (`CRITERIO_RECORTE_GEOGRAFICO`)
4. `hospitais_principais.py` — marcação principal
5. `rede_visao.py` — junção com `planos_rede_aliases.csv` (fase A)
6. `rede_matriz_laboratorio.py` + `laboratorios_principais.py` + `rede_labs.py` — bloco Labs da etapa 5 (✓ por marca)
7. `rede_consulta_lab.py` — Simular rede, somente leitura: `/api/simular-rede/laboratorios/opcoes`, `/por-laboratorio`, `/por-plano`. Recorte por UF/município do corretor (sem zona, sem H/M/PS). Padrão = marcas do CSV; «ver todos» lista cada prestador (trava de 100 sem geografia). Aviso Porto/Medservice fora de SP/RJ/DF.
