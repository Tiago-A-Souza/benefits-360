# Caracterização do corpus privado de cotações PDF

Etapa pré-homologação dos extratores Porto, SulAmérica e Amil. **Nenhum PDF, texto integral, nome de cliente ou dado pessoal entra no Git** — o corpus fica em `.private/corpus/` (ignorado).

## Execução

```powershell
python scripts/analisar_corpus_cotacoes.py
```

Saídas (privadas, em `.private/golden/`):

- `corpus_caracterizacao.json` — registro sanitizado por documento (hash, operadora, família, maturidade, opções resumidas)
- `corpus_cobertura.json` — matriz de cobertura por família

## Famílias de template

**12 famílias definidas** em `template_families.py`:

| Operadora | ID |
|-----------|-----|
| Porto Seguro | `porto-demonstrativo-27`, `porto-tabela-geral-15` |
| SulAmérica | `sulamerica-pme-sem-cp-13`, `sulamerica-pme-copart-13`, `sulamerica-pme-ajustes-dual`, `sulamerica-pme-sem-cp-v2`, `sulamerica-pme-copart-v1`, `sulamerica-pme-sem-cp-v1`, `sulamerica-pme-copart-pct-11` |
| Amil | `amil-cotacao-texto-4p`, `amil-cotacao-visual-8p` |
| Omint | `omint-ocr-v1` |

No corpus atual (24 PDFs): **10 famílias representadas**, **2 sem documento**:

- `sulamerica-pme-sem-cp-v1` — layout 9–10 pág. com rótulo curto «SEM COPART» (sem «SEM COPARTICIP»)
- `omint-ocr-v1` — sem PDF Omint no corpus

Identificação ocorre **antes** da extração, por âncoras estruturais (títulos, regime de copart, faixa de páginas). Documento não reconhecido → `PDF-TPL-001` / `nao_reconhecido`, sem fallback para outro extrator.

## Níveis de maturidade (distintos)

| Nível | Significado |
|-------|-------------|
| **Template reconhecido** | Família identificada; extrator determinístico acionado |
| **Tabela extraída** | Opções tarifárias localizadas (sem alerta de tabela ausente) |
| **Valores reconciliados** | Somatórios internos coerentes por opção |
| **Proposta pronta para aplicação** | Campos confirmados nas opções alvo |
| **Extração financeira homologada** | *Não* — permanece `false` nesta etapa |

Reconhecer o template **não** significa extração financeira homologada.

## Seleção consciente (Porto / tabelas extensas)

Documentos Porto e qualquer PDF com **mais de 3 planos** na tabela geral:

- exibem todas as **opções encontradas** para revisão;
- **não** aplicam planos automaticamente ao rascunho;
- exigem marcação explícita «Levar ao comparativo» antes de aplicar.

## Testes

- Sintéticos versionados: `tests/fixtures/cotacao_pdf/build_pdfs.py`, `tests/test_template_families.py`
- Aceite privado (hash, `@pytest.mark.private_corpus`): `tests/test_corpus_aceite_privado.py`
