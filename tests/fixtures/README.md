# tests/fixtures — Regras e formato

Fixtures são o **oráculo de testes** do motor financeiro puro. Elas alimentam as suítes A–H (ver `docs/04-HANDOFF-IMPLEMENTACAO.md` §9).

## Regras de dados (obrigatórias)

- **Somente dados fictícios ou anonimizados** podem entrar no Git.
- **Proibido versionar dados pessoais:** CPF, endereço, CEP, telefone, e-mail, nome da mãe, RG, PIS ou qualquer PII. Nomes, quando necessários, devem ser **fictícios**.
- **Documentos reais (PDFs de cotação, planilhas SISCOR reais) ficam FORA do repositório.** Eles compõem um **corpus privado de integração e homologação**, armazenado fora do Git e acessado apenas em testes controlados.
- Se precisar reproduzir um caso real, **anonimize e sintetize** os dados antes de commitar.

## O que cada fixture precisa declarar

Toda fixture indica, de forma explícita:

1. **Cenário representado** — formato (novo | renovação | renovação 2+ planos); nº de vidas; nº de planos; operadora(s); regime de copart (sem | parcial | percentual | customizada); presença/ausência de totais impressos; `price_basis` de cada componente.
2. **Entradas** — dados tipados de vidas, subgrupos, propostas/opções e a `EffectivePolicy` (data de referência, tolerâncias, estratégia de arredondamento, reajuste).
3. **Resultado esperado** — valores calculados (em centavos), bloqueios esperados (B-01…B-08), alertas esperados, e as seções por regime (`ScenarioSectionResult`) esperadas.

## Formato sugerido

- Um diretório por caso: `tests/fixtures/<caso>/` com `input.json`, `effective_policy.json`, `expected.json` e um `README.md` curto descrevendo o cenário e o porquê do resultado.
- Nomeie os casos pelo que exercitam, ex.: `renovacao_1plano_sem_copart_12vidas`, `renovacao_2planos_copart_misto_29vidas`, `reconciliacao_total_ausente`, `idade_valor_sem_tabela_atual`.
- Cobertura mínima esperada (casos do HANDOFF): **1, 12, 20 e 29 vidas**; **um e dois planos**; copart **sem / parcial / percentual**; caso com **total impresso ausente**; caso de **data de referência ausente** (deve bloquear); caso de **divergência monetária** (alerta e bloqueante).

## Fronteira

- Nada nestas fixtures deve exigir banco, rede, PDF real ou IA. São dados em arquivo, determinísticos, para rodar o motor puro isoladamente.
