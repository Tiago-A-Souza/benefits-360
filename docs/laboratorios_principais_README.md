# Laboratórios principais — marcas do bloco Labs

Arquivo: `laboratorios_principais_base.csv`. Uma linha por **marca** da proposta
comercial (não por unidade da `Matriz_Laboratorio`).

## Formato

Separador `;`, UTF-8 com BOM. Padrões múltiplos vão entre aspas.

```
marca;padroes_nome;ufs;ativo
```

- **marca** — rótulo da linha no bloco Labs (ordem do CSV = ordem de exibição).
- **padroes_nome** — substrings casadas no nome SiscorNet após `normalizar_cabecalho`
  (acento/caixa). Vários padrões separados por `;`.
- **ufs** — vazio = todas as UFs; senão só unidades daquelas UFs (`RJ` ou `SP;RJ`).
- **ativo** — `sim` / `nao`.

Uma marca só entra no estudo se alguma unidade casada existir no recorte
geográfico das vidas. Hospitais que aparecem na aba de laboratório **não** entram
neste bloco — só as marcas deste CSV.
