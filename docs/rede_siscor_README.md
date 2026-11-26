# Base SiscorNet — rede hospitalar

Arquivo: `SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx` (versionado em
`docs/`). Extração **17/11/2026**, filtrada pelo Wesley (códigos HGER, HD, HCELT,
PSGER, MAT, ACLIN, S_ESP). Extração anterior (05/10, 2.051.317 bytes) está em
`docs/legado/SiscorNet_Comparativo_Nacional_Hospital_Laboratorio_2026-10-05.xlsx`.

A data «Base de …» do Simular rede vem da aba `Resumo` (`extraído em 17/11/2026`),
com fallback para a data de modificação do arquivo.

## Abas usadas

| Aba | Uso |
|---|---|
| `Matriz_Hospital` | **Sim** — 882 prestadores, 56 municípios, 193 colunas de plano |
| `Matriz_Laboratorio` | **Sim** — 1.455 prestadores, 68 municípios; bloco Labs da etapa 5 / HTML **e** menu Simular rede (marcas em `laboratorios_principais_base.csv`) |
| `Resumo` | Metadados de referência e data da extração |

Cabeçalho em **quatro linhas** nas colunas de plano; cinco colunas fixas: Prestador,
Classif., Município (`UF.CIDADE`), Bairro, Região. A linha 1 de classificação do
plano passou de `BASICO` para `Básico` (o ingest não usa essa linha).

Operadora **GNDI** no cabeçalho virou **NOTRE DAME** (alias `NotreDame;NOTRE DAME`
em `regras_comerciais_aliases.csv`). Entraram 4 planos **CNU** (Estilo, Absoluto,
Superior, Exclusivo).

## Filtro de códigos (intencional)

Mantidos só HGER, HD, HCELT, PSGER, MAT, ACLIN e S_ESP. HCELT sozinho **não** conta
como cobertura hospitalar (a regra `_coberto_na_coluna` segue exigindo HGER / HD /
PSGER / MAT). Exceção **CEMA**: 4 linhas com cobertura completa, em amarelo.

## CSV de principais

`hospitais_principais_base.csv` **não** foi refeito nesta troca: 1.071 linhas /
391 principais permanecem. 28 principais e 3 verticalizados saíram da matriz e
ficam órfãos no CSV; 51 pares novos entram sem marcação (não principal). Planilha
de decisão do Wesley: `docs/legado/siscornet-decisao-principais-1711.xlsx`.

## Troca mensal

Substitua o `.xlsx` inteiro (guarde o anterior em `docs/legado/`). Rode a suíte —
`tests/test_rede_fase_c.py` valida contagem e cruzamento com
`hospitais_principais_base.csv`.

Variável opcional: `NEWPORT_REDE_XLSX` aponta para outro caminho (CI local). Se
estiver definida, **ignora** o arquivo em `docs/`.

## Pipeline (código)

1. `rede_matriz_hospital.py` — ingestão
2. `rede_especialidade.py` — filtro HGER / HD / PSGER / MAT
3. `rede_recorte.py` — **critério geográfico** (`CRITERIO_RECORTE_GEOGRAFICO`)
4. `hospitais_principais.py` — marcação principal (órfãos do CSV e hospitais novos sem linha são aceitos)
5. `rede_visao.py` — junção com `planos_rede_aliases.csv` (fase A)
6. `rede_matriz_laboratorio.py` + `laboratorios_principais.py` + `rede_labs.py` — bloco Labs da etapa 5 (✓ por marca)
7. `rede_consulta_lab.py` — Simular rede, somente leitura: `/api/simular-rede/laboratorios/opcoes`, `/por-laboratorio`, `/por-plano`. Recorte por UF/município do corretor (sem zona, sem H/M/PS). Padrão = marcas do CSV; «ver todos» lista cada prestador (trava de 100 sem geografia). Aviso Porto/Medservice fora de SP/RJ/DF.
