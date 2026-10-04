# Hospitais principais — porta de manutenção

Arquivo: `hospitais_principais_base.csv`. Um registro por linha da aba
`Matriz_Hospital` (1.071 linhas). A coluna `prestador` repete o nome **exatamente**
como na planilha SiscorNet — chave de junção com o município (`uf` + `municipio`).

## Formato

Separador `;`, UTF-8 com BOM.

```
uf;municipio;zona;prestador;principal;confianca;rede_verticalizada;especialidades;observacao
```

- **principal** — `sim` / `nao` (391 marcados como principais na curadoria Wesley).
- **rede_verticalizada** — quando preenchida, o prestador só conta como coberto
  nas colunas da operadora correspondente (Hapvida, Amil, etc.).

Linhas repetidas no CSV para o mesmo `(prestador, município)` são **mescladas** na
carga (principal = OR das linhas).

## Troca mensal

Substitua o XLSX SiscorNet (`SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx`)
e regenere ou ajuste este CSV para bater com os nomes da matriz.

Testes em `tests/test_rede_fase_c.py` falham informando o **número da linha** se o CSV
estiver malformado ou se algum prestador do CSV não existir na matriz.
