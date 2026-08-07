# 04 — Ingestão SISCOR

Fonte: commit `2a69d4c0bd12e4e8613cb8b085b1dac0c50cb805` — 2026-07-27

Documento operacional para IA sem acesso ao código. Descreve o importador de planilha SISCOR (`.xlsx`), conferência e aplicação ao `RascunhoEstudo`.

---

## Whitelist `COLUNAS_OBRIGATORIAS` e descarte de PII

Colunas aceitas no layout piloto (`src/newport_app/siscor_importer/constants.py:5-14`):

| Coluna canônica |
|-----------------|
| `CLIENTE` |
| `SEGURADO` |
| `PARENTESCO` |
| `DATA DE NASCIMENTO` |
| `PLANO` |
| `SEGURADORA` |
| `VALOR` |
| `STATUS SEGURADO` |

`MAPEAMENTO_COLUNAS` é identidade sobre essa tupla (`constants.py:16`).

### Política P9 (docs)

`docs/03-PATCH-v0.2.1.md:63-71` (P9) exige descarte na ingestão dos campos SISCOR não usados: **CPF, endereço, CEP, telefone, nome da mãe, RG, PIS, etc.** — whitelist mantém só `{nome, parentesco, nascimento, plano, valor, status, sexo?}`. Nome permanece porque aparece no slide.

### Comportamento no código

1. Cabeçalhos são normalizados e indexados (`parser.py:146-164`).
2. Se faltar qualquer coluna da whitelist → erro de arquivo `APP-SIS-F05` (`parser.py:166-177`).
3. A linha candidata (`LinhaSiscorCandidata`, `models/siscor_import.py:44-69`) só persiste campos da whitelist (cliente, segurado, parentesco, nascimento, plano, operadora/`SEGURADORA`, valor, status). **Não há campos CPF/RG/endereço/telefone/sexo no modelo de linha.**
4. Colunas extras eventualmente presentes no `.xlsx` podem ser lidas no dicionário temporário `valores`, mas **não são gravadas** na candidata nem no rascunho — efeito prático de whitelist/descarte de PII alinhado a P9.
5. Ao aplicar (`siscor_mapper/apply.py:111-122`), só vão para `VidaRascunho`: nome, nascimento, parentesco, inclusão, subgrupo, valor_fatura confirmado.

`sexo?` aparece na política P9 como opcional; **não está** em `COLUNAS_OBRIGATORIAS` nem em `LinhaSiscorCandidata` — não é ingestado nesta implementação.

---

## Normalizações

### Cabeçalho (NBSP e espaços Unicode)

`normalizar_cabecalho` (`normalize.py:11-20`):

- Regex `_RE_ESPACOS_CABECALHO` colapsa tab, CR/LF, NBSP (`\u00A0`), espaços Unicode diversos em um espaço simples.
- Resultado: `strip().upper()`.

Usado no parse do header (`parser.py:149`).

### Parentesco

`PARENTESCO_MAP` (`constants.py:20-29`) + `normalizar_parentesco` (`normalize.py:32-39`):

| Texto (upper) | Enum rascunho |
|---------------|---------------|
| `TITULAR` | `titular` |
| `CÔNJUGE` / `CONJUGE` | `conjuge` |
| `FILHO` / `FILHA` / `FILHO(A)` | `filho` |
| `COMPANHEIRO` / `COMPANHEIRO(A)` | `companheiro` |

Texto vazio → alerta. Texto não mapeado → mantém texto, `parentesco=None` → `APP-SIS-008`.

### Status → inclusão

`STATUS_ATIVO = "ATIVO"` (`constants.py:18`).  
`normalizar_status` (`normalize.py:23-29`): só `"ATIVO"` (case-insensitive via `.upper()`) produz status normalizado; demais textos retornam `(texto, None)`.

No parser: `incluida = status_norm == "ATIVO"` (`parser.py:343`). Só ATIVO sugere inclusão; outros status reconhecidos como texto mas sem normalização → alerta `APP-SIS-005`.

### Valor → centavos (`Decimal`, não float)

`valor_para_centavos` (`money.py:1-32`):

- Módulo documentado: *“nunca float”* (`money.py:1`).
- Aceita `Decimal`, `int`, `float` (convertido via `Decimal(str(valor))`), string BR (`1.234,56` → remove `.` milhar, vírgula→ponto).
- `centavos = int((dec * 100).quantize(Decimal("1"), ROUND_HALF_UP))`.
- Negativo → `None` (alerta `APP-SIS-012` no parser quando string começa com `-`).
- `bool` rejeitado.

---

## Códigos de alerta

### Arquivo — `APP-SIS-F01` … `APP-SIS-F07`

| Código | Quando | Mensagem típica | Fonte |
|--------|--------|-----------------|-------|
| `APP-SIS-F01` | Conteúdo vazio ou falha ao abrir workbook | Arquivo vazio/inválido; não foi possível ler | `parser.py:98`, `125` |
| `APP-SIS-F02` | Magic bytes ≠ `PK` (não é `.xlsx` zip) | Deve ser Excel (`.xlsx`) | `parser.py:102-110` |
| `APP-SIS-F03` | Sem linha de cabeçalho | Planilha sem cabeçalho | `parser.py:141` |
| `APP-SIS-F04` | Cabeçalho com coluna duplicada (após normalizar) | Colunas duplicadas | `parser.py:157` |
| `APP-SIS-F05` | Falta coluna obrigatória | Layout piloto incompleto | `parser.py:172` |
| `APP-SIS-F06` | Nenhuma linha utilizável após parse | Sem linhas utilizáveis | `parser.py:386` |
| `APP-SIS-F07` | Célula com fórmula (`data_type == "f"` ou valor começa com `=`) | Informe o valor calculado | `parser.py:205` |

### Linha — `APP-SIS-001` … `012` (**falta `011`**)

| Código | Campo | Condição | Fonte |
|--------|-------|----------|-------|
| `APP-SIS-001` | nascimento | Ausente ou inválida | `parser.py:251-261`; `revalidate.py:63-72` |
| `APP-SIS-002` | nascimento | Data no futuro | `parser.py:267`; `revalidate.py:79` |
| `APP-SIS-003` | valor | Zerado (`== 0`) | `parser.py:320`; `revalidate.py:109` |
| `APP-SIS-004` | plano | Ausente | `parser.py:277`; `revalidate.py:87` |
| `APP-SIS-005` | status | Ausente ou não reconhecido | `parser.py:330-338`; `revalidate.py:115-127` |
| `APP-SIS-006` | linha | Duplicidade (ver seção abaixo) | `duplicidades.py:40` |
| `APP-SIS-007` | segurado | Nome ausente | `parser.py:218`; `revalidate.py:36` |
| `APP-SIS-008` | parentesco | Ausente ou não mapeado | `parser.py:228-236`; `revalidate.py:41-54` |
| `APP-SIS-009` | valor | Ausente ou ilegível | `parser.py:302-314`; `revalidate.py:101` |
| `APP-SIS-010` | operadora | Ausente | `parser.py:289`; `revalidate.py:93` |
| `APP-SIS-011` | — | **Não existe no código** | — |
| `APP-SIS-012` | valor | Negativo | `parser.py:310`; `revalidate.py:105` |

`tem_excecao` = qualquer alerta na linha (`siscor_import.py:72-73`).  
`confirmavel` = não excluída e sem exceção (`siscor_import.py:76-77`).

---

## Subgrupos (plano × operadora)

`montar_subgrupos` (`subgrupos.py:14-30`):

- Chave: `(plano, operadora)`.
- Linha excluída ou sem plano/operadora → `subgrupo_sugerido_id = None`.
- Cada chave gera `SubgrupoSiscorSugerido` com `id` UUID, `plano_nome`, `operadora`, `quantidade_linhas`.
- Após edição: `remontar_subgrupos_candidata` (`subgrupos.py:33-34`).

Na aplicação ao rascunho (`apply.py:83-106`): cria `SubgrupoAtualRascunho` por subgrupo sugerido presente nas vidas aplicáveis; preserva `regime_copart_id` / `tipo_fiscal` / `fatura_price_basis` se já existiam.

---

## Duplicidades

`recalcular_duplicidades` (`duplicidades.py:14-41`):

1. Remove alertas `APP-SIS-006` anteriores.
2. Chave: `(segurado, nascimento, plano)` — só se linha não excluída e os três campos preenchidos.
3. Grupos com `len >= 2`: **todas** as ocorrências recebem `APP-SIS-006` — *“Possível registro duplicado — revise.”*
4. Chamado no parse (`parser.py:393`) e após editar linha (`importacao_siscor.py:540`).

---

## Fluxo: upload → candidata → conferência → confirmar-lote → apply

```
POST /importar-siscor
  → parse_planilha_siscor (parser)
  → ImportacaoSiscorCandidata (estado aguardando conferência)
  → arquivo salvo em uploads/{documento_id}.xlsx
GET  /conferencia-siscor
  → linhas + estatísticas + subgrupos
PATCH /conferencia-siscor/linhas/{id}
  → edição / confirmação individual / exclusão com motivo
  → revalidar_linha + recalcular_duplicidades + remontar_subgrupos
  → aplicar_candidata_ao_rascunho (parcial, só confirmadas)
POST /conferencia-siscor/confirmar-lote
  → marca confirmáveis como confirmadas
  → aplicar_candidata_ao_rascunho
  → persiste rascunho (+ posição cadastral histórica se houver)
```

### Detalhes de serviço

**Upload** (`ImportacaoSiscorService.importar_planilha`, `services/importacao_siscor.py:265-340`):

- Limite de bytes na API (`main.py:334-338`) via `LIMITE_UPLOAD_BYTES`.
- Se já há dados/candidata e `modo` omitido → `ImportacaoRequerDecisaoError` / HTTP 409 com opções (`importacao_siscor.py:281-287`; `main.py:346-353`).
- Parse falho → `sucesso=False` + `erros_arquivo` (sem persistir candidata).
- Sucesso → salva arquivo, marca candidata ativa, opcionalmente zera rascunho em `substituir`.

**Conferência** (`obter_conferencia`, `importacao_siscor.py:342-359`): devolve linhas, subgrupos, correspondências sugeridas (reimport `nova_versao`).

**Confirmar lote** (`confirmar_lote`, `importacao_siscor.py:361-429`):

- Idempotente se posição histórica já existe para a importação.
- Só linhas `confirmavel` (sem alerta, não excluídas).
- `aplicar_candidata_ao_rascunho` (`apply.py:74-127`): exige `registro_confirmado`, sem exceção, segurado/plano/operadora/nascimento ISO válidos; valor_fatura só se `valor_confirmado`.

**Apply linha a linha** (`_linha_aplicavel`, `apply.py:37-48`): excluída / não confirmada / com exceção → ignorada.

---

## Reimportação: `substituir` / `nova_versao`

`MODOS_REIMPORTACAO_VALIDOS = {"substituir", "nova_versao"}` (`importacao_siscor.py:48`).

| Situação | Comportamento |
|----------|----------------|
| Já há dados e `modo=None` | 409 + opções: se há confirmações anteriores → só `["nova_versao"]`; senão → `["substituir"]` (`importacao_siscor.py:281-287`) |
| `modo` inválido | `ModoImportacaoInvalidoError` → 400 (`main.py:354-358`) |
| `substituir` | Candidata ativa → `estado="substituida"`, desativa; versão incrementa; rascunho zerado (`importacao_siscor.py:314-327`) |
| `nova_versao` | Versão = anterior+1; mantém anterior como referência; sugere correspondências por (segurado, nascimento, plano) com confiança `"baixa"` (`importacao_siscor.py:205-229`, `293-295`) |

---

## Maturidade

| Aspecto | Estado | Evidência |
|---------|--------|-----------|
| Parser + whitelist + conferência + apply + API + UI | **implementado** | `RELATORIO-ETAPA-2.3.md:4`, módulos `siscor_importer/*`, `siscor_mapper/apply.py`, endpoints `main.py:323-424`, `SiscorPanel.jsx` |
| Homologação privada com planilhas reais | **pendente** | `RELATORIO-ETAPA-2.3.md:4` — *“homologação privada ainda pendente”* |
| Corpus/fixtures reais no Git | Fora do repositório (política geral de corpus privado) | `tests/fixtures/README.md` |

---

## ⚠️ NÃO VERIFICADO

Itens não confirmados neste handoff a partir do commit citado:

- Layout SISCOR exportado por versão específica do sistema corretora em produção (além do piloto documentado).
- Homologação operacional com planilhas reais de clientes (status explícito: pendente).
- Presença/ausência de coluna `sexo` em exports reais (P9 menciona opcional; código não ingere).
- Comportamento de fórmulas Excel já “cacheadas” vs. só fórmula viva (parser rejeita células com fórmula; `data_only=True` no workbook paralelo).
- Retenção de arquivos `.xlsx` em `uploads/` e política de purge (P9 fala retenção configurável; implementação de purge **não** descrita neste fluxo).
