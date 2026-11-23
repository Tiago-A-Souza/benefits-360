# Planos × rede — tabela de equivalência

A coluna SiscorNet **não** é nome de plano no cotador. A tela Nova cotação não
manda esse rótulo ao robô — ver `docs/COTACAO-NOVA-BUSCA-PLANOS.md`.

Arquivo versionado: `planos_rede_aliases.csv`. Nenhum mapeamento manual vive em `.py`.

## Formato

Separador `;`, UTF-8 com BOM (como as outras bases).

```
operadora;plano_cotacao;coluna_rede;fonte;atualizado_em
```

- **operadora** — canônica (`regras_comerciais.py`, lista `OPERADORAS_CANONICAS` + extras
  usados na rede: mesmas de cotação).
- **plano_cotacao** — nome exatamente como aparece na cotação / estudo (casamento por
  `normalizar_cabecalho`).
- **coluna_rede** — rótulo abreviado da coluna na base SiscorNet (Matriz_Hospital). Na
  Amil, o prefixo comercial `PRATA AO PLATINUM` pode ser omitido; o sistema casa pelo
  **final** do rótulo completo, dentro da operadora.
- **fonte** / **atualizado_em** — rastreabilidade (planilha validada, data).

## Manutenção

Produto novo que a regra automática não resolve: **uma linha a mais** neste CSV.

Um teste valida o arquivo contra a base de rede real:

- operadora fora da lista canônica → falha com número da linha;
- duplicata `(operadora, plano_cotacao)` → falha;
- `coluna_rede` que não casa com exatamente uma coluna da base → falha.

Variável opcional para o caminho da planilha SiscorNet nos testes:
`NEWPORT_REDE_XLSX` (default: arquivo local do comparativo nacional).

## Resolução em runtime

Ordem fixa (`planos_rede.py`):

1. Entrada na tabela de aliases (estado **alias**).
2. Regra automática em `casamento_rede.py` (estado **regra**).
3. Sem coluna (estado **sem_rede**).

A tabela tem precedência sobre a regra automática.
