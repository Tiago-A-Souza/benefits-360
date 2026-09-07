# Regras comerciais — porta de manutenção

Dois arquivos versionados. Nenhum valor de regra vive em `.py` ou `.jsx`.

## Valores — `regras_comerciais_base.csv`

Formato longo, separador `;`, aspas em células com quebra de linha.

```
operadora;regra;valor
```

Uma linha por par `(operadora, regra)`. São 10 operadoras × 8 regras = 80 células.
Nenhuma célula vazia. «Informação pendente» é valor legítimo — entra no documento
como está.

Ordem de exibição das regras (fixa):

1. Redução de Carências
2. Adesão
3. Compulsório
4. Vigência do Contrato
5. Regras De Cancelamento
6. Multa Por Cancelamento
7. Análise de Sinistralidade
8. Inclusão de PJS

Para trocar a regra X da operadora Y: edite **só este arquivo**. Um teste falha
se faltar célula, se houver duplicata, ou se operadora/regra sair da lista
canônica — e aponta o registro.

Hapvida e NotreDame têm os mesmos valores de propósito (confirmação Wesley
Barreiros). Permanecem duas entradas.

## Aliases — `regras_comerciais_aliases.csv`

```
canonica;variacao
```

Uma linha por variação de nome. O casamento **normaliza e compara igualdade** —
nunca «contém». Unimed regional não casa com Seguros Unimed.

Quando aparecer um nome novo de cotação, acrescente uma linha aqui.
