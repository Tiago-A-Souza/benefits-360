# Sistema de Estudos Newport

Plataforma da **Newport Consultoria de Benefícios** para montar **estudos comparativos financeiros** de planos de saúde corporativos. O produto substitui, com trilha auditável, o trabalho que hoje depende de especialistas: importar a base de beneficiários, ler cotações em PDF, calcular cenários e entregar um documento HTML que o cliente usa na decisão de renovação ou troca de operadora.

Faixa operacional homologada no piloto: **1 a 29 vidas** por estudo (configurável; o motor não impõe teto técnico). Estágio atual do repositório: **ETAPA 2.8.1** — persistência histórica, snapshot com hash, aprovação local e apresentação HTML autocontida. API **2.8.2**, renderer **html@2.13.8**.

Documentação normativa para implementação continua em `docs/01`–`docs/04`, `AGENTS.md` e `REGISTRO-TECNICO-ALTERACOES.md`. Este README é a porta de entrada; ele não substitui esses arquivos.

---

## O que é um estudo de saúde

Quando uma empresa vai **renovar** o contrato de plano de saúde ou **contratar cobertura nova**, a consultoria compara o que ela paga hoje (ou pagaria) com propostas de outras operadoras ou produtos. Esse comparativo — valores por faixa etária, totais mensais e anuais, reajuste do contrato vigente, IOF quando couber — é o **estudo de saúde** que este sistema produz.

**Atores:**

- **Empresa contratante** — decide com base no estudo.
- **Beneficiários** — titulares e dependentes; cada um tem idade, parentesco e, na renovação, um plano vigente.
- **Operadoras e seguradoras** — Amil, Porto Seguro, SulAmérica, Bradesco, Hapvida/NotreDame, entre outras no escopo do piloto.
- **Corretor** — intermedia cotações; os PDFs costumam vir por esse canal.
- **Consultoria (Newport)** — importa a posição cadastral, valida dados, monta cenários, revisa números e entrega o documento.

**Renovação** parte de uma **base atual** (planilha SISCOR ou equivalente): quem está no plano, quanto paga, qual operadora. O sistema aplica o **reajuste** acordado ou estimado e compara com propostas novas.

**Seguro novo** não tem plano vigente na base: só cotações. A jornada omite fatura/reajuste do atual e compara propostas entre si.

**Grupos de beneficiários** existem porque a mesma empresa costuma ter **planos diferentes por categoria** — por exemplo funcionários em um produto e diretoria em outro. O motor trata cada grupo (subgrupo) com tabela e totais próprios; o comparativo exige que cada **cenário** atribua uma proposta a **todos** os grupos com vidas, ou o cálculo bloqueia de forma explícita.

**Exemplo real usado na validação — Anistia Internacional:** 41 vidas, **36** no plano Amil S750 (funcionários) e **5** no Amil ONE S2500 (diretoria), comparando contra três propostas Porto (Bronze Brasil I Q, Prata Mais I Q, Ouro Mais I Q). Vinte e quatro valores desse estudo estão travados em gabarito de teste, além de dezenas de relações internas de coerência no documento.

Outros estudos de referência: **ATEF** (3 vidas, renovação simples) e **IVTEC** (12 vidas, seguro novo, duas propostas Amil).

---

## O que o sistema faz

Fluxo guiado em etapas (wizard). Em cada uma: o que entra, o que sai, e o que **não** pode acontecer.

### 1. Base atual (SISCOR)

**Entra:** planilha Excel da posição cadastral (layout piloto com colunas obrigatórias: cliente, segurado, parentesco, nascimento, plano, operadora, valor, status, etc.).

**Sai:** candidata de importação linha a linha; após conferência, vidas e subgrupos no rascunho do estudo.

**Não pode:** truncar beneficiários silenciosamente; descartar faixas inteiras do total porque os valores unitários misturam dentro da faixa; gravar PII no Git. Modo **demo** usa `.data/`; modo **real** grava em `.private/runtime/`.

### 2. Plano atual

**Entra:** subgrupos derivados da base, reajuste (`reajuste_bps`), tipo fiscal (operadora vs seguradora), regime de coparticipação, data de referência para idade.

**Sai:** plano vigente configurado por grupo, totais vigente e reajustado calculados pelo motor.

**Não pode:** assumir tipo fiscal «seguradora» quando o PDF não declarou (inflava ~2,38% toda cotação de operadora); calcular sem **data de referência** explícita; exibir total «observado» que na verdade já traz reajuste aplicado fora do motor.

### 3. Cotações (PDF)

**Entra:** um ou mais PDFs por operadora (Amil, Porto, SulAmérica, etc. — parsers por família de layout).

**Sai:** opções de proposta com tabelas por faixa etária, metadados (operadora, plano, coparticipação, tipo fiscal quando extraível), alertas de reconciliação com totais impressos no PDF.

**Não pode:** inventar nome de plano a partir de texto institucional; oferecer linha de subtotal Amil como plano; abortar upload em lote no primeiro erro sem mostrar os que subiram; deixar extração vazia sem caminho de entrada manual.

### 4. Correspondência e cenários (renovação multi-plano)

**Entra:** vários subgrupos vigentes e várias propostas.

**Sai:** matriz **cenário × subgrupo** — cada coluna do comparativo é um cenário que escolhe qual proposta vale para cada grupo.

**Não pode:** um cenário «pela metade» (bloqueio B-06); misturar regimes de coparticipação na mesma seção sem separação.

### 5. Comparativo (cálculo)

**Entra:** rascunho compilado + políticas efetivas (`EffectivePolicy`).

**Sai:** resultado do motor puro + adaptador de tela (`ComparativoResponse`): valores por vida, subgrupo, seção por regime de copart, totais.

**Não pode:** alterar regras do motor na aplicação; usar float; pular bloqueios B-01…B-08 quando o dado exige.

### 6. Snapshot, revisão e aprovação

**Entra:** comparativo validado.

**Sai:** snapshot **candidato** com hash SHA-256 sobre payload **canônico** (sem timestamps); após revisão humana, snapshot **aprovado** com nome do revisor e confirmação explícita.

**Não pode:** aprovar sem `confirmo_conteudo`; gerar HTML de cliente antes da aprovação; registrar plano contratado automaticamente após aprovação.

### 7. Apresentação (HTML)

**Entra:** snapshot aprovado, modo faixas ou beneficiário, propostas selecionadas.

**Sai:** arquivo HTML autocontido (**sem JavaScript**), formatação `R$` só no renderer, valores transportados em centavos no ViewModel.

**Não pode:** expor hash, IDs técnicos ou metadados de auditoria no HTML entregue ao cliente; PPTX de produção (fora de escopo autorizado).

Sequência obrigatória: **cálculo → snapshot candidato → revisão → aprovação → HTML**.

---

## Invariantes

Regras que **nunca** devem ser quebradas. O `REGISTRO-TECNICO-ALTERACOES.md` documenta defeitos reais quando cada uma foi violada.

### Dinheiro em centavos inteiros

Valores são `MoneyCents` (inteiro). Taxas em basis points (IOF seguradora = 238 bps) ou decimal exato. **Nunca float.** Se violado: totais não fecham com a fatura do cliente nem com o rodapé do PDF da operadora; erros de arredondamento se acumulam (ex.: três centavos na Anistia entre «por vida então soma» e «sobre o total»).

### Estratégia `por_vida_entao_soma`

Reajuste e IOF aplicam **por vida**, arredondam **por vida**, depois somam. Aplicar taxa sobre o total do subgrupo muda o resultado. Violado: estudo «certo» na planilha Excel e errado no documento Newport.

### Total = soma de todas as vidas conhecidas

Homogeneidade dentro da faixa só afeta se dá para mostrar valor unitário representativo — **não** se a faixa entra no total. Violado (Anistia): 14 de 36 vidas excluídas do total, 35% do valor mensal sumiu enquanto a tela ainda dizia «36 beneficiários».

### Nenhum campo que altera valor recebe default silencioso

`tipo_fiscal` ausente **não** vira «seguradora». `price_basis` desconhecido **bloqueia** até declaração. Violado: IVTEC com Amil inflado ~R$ 89/mês por vida na faixa afetada — sempre desfavorecendo a proposta na comparação.

### Ausência declarada, nunca suposta

Parentesco, acomodação, operadora não reconhecida: o operador confirma ou corrige. Beneficiários **nunca** vinculados silenciosamente a grupo familiar — sugestão exige confirmação.

### Motor intocável na apresentação

Recálculo por proposta na HTML usa o motor existente; não há «regra paralela» no renderer.

### Governança de entrega

Nenhum documento de cliente sem snapshot aprovado. Hash determinístico sem carimbo de tempo no conteúdo canônico.

### Casamento de nomes (rede e aliases)

Igualdade após `normalizar_cabecalho` — **nunca** «contém». Unimed regional não casa com Seguros Unimed por substring.

---

## Arquitetura

### Motor vs aplicação

`src/newport_motor/` implementa `calcular(estudo, policy) → resultado` como função **pura**: sem FastAPI, sem SQLite, sem PDF. Toda operadora passa pelo mesmo núcleo; variam declarações (`tipo_fiscal`, `price_basis`) e dados de entrada.

`src/newport_app/` compila rascunho JSON → entrada tipada, chama o motor, adapta para UI (`adapters/motor_out.py`), monta ViewModel (`presentation/builder.py`) e renderiza HTML (`presentation/html_renderer.py`).

A separação existe para que correções de parser, UI ou documento **não** reescrevam IOF, faixa etária ou reconciliação sem entrega versionada dedicada.

### Snapshot

O snapshot congela rascunho, entrada do motor, políticas, resultado, comparativo e versões de compilador/motor/policy. O hash SHA-256 cobre só o payload canônico (JSON ordenado, sem `gerado_em`). Aprovação referencia esse hash; alteração material invalida a aprovação anterior.

### Documento HTML sem JavaScript

O entregável é HTML+CSS autocontido para e-mail, impressão ou arquivo estático. Interatividade no produto fica no wizard React; o cliente recebe snapshot estático. Formatação monetária ocorre **somente** no renderer — o ViewModel carrega centavos inteiros.

### Três camadas de paridade

Correções de apresentação precisam bater entre camadas; teste que chama a mesma função duas vezes não substitui isso.

1. **Motor → comparativo de tela** (`adapters/motor_out.py`): mesmos totais que o resultado bruto do motor para a matriz operacional.
2. **Comparativo → ViewModel** (`presentation/paridade_estrutural.py`): mesma estrutura de colunas, regimes, totais e metadados antes do HTML.
3. **ViewModel → HTML** (`presentation/paridade_html.py`): texto renderizado reflete os centavos do ViewModel (gabaritos em `tests/test_paridade_matriz_html.py`, fixture Anistia seis propostas, etc.).

Há ainda paridade do **compilador** de rascunho (`tests/test_draft_compiler_paridade.py`) contra fixtures nativas da aplicação.

### Suíte de testes

Verificação em **25/09/2026** neste repositório:

| Suíte | Resultado |
|--------|-----------|
| **pytest** (`tests/`) | **1298 passed**, 15 skipped (1313 coletados) |
| **vitest** (`web/`) | **131 passed** |

Camadas cobertas:

- **Suítes A–H** — motor puro: tipos, reconciliação B-02, IOF, reajuste, idade/faixa, cenários B-06, pureza, escala 1–29 vidas (`tests/test_suite_*.py`).
- **Compilador, SISCOR, PDF, snapshot, API, etapa 2.8.x** — centenas de testes de integração.
- **Gabaritos de estudos reais** — ATEF, Anistia (dois planos vigentes, múltiplas propostas, reajustes 10% e 12%), IVTEC; valores em centavos em JSON em `tests/fixtures/paridade_matriz/`.
- **Corpus PDF privado** — marcador `private_corpus` para PDFs reais fora do Git (`pytest -m "not private_corpus"` quando o corpus local não existir).

---

## Bases de dados externas (versionadas)

Arquivos mantidos pela Newport, editados no Git — **não** embutidos em `.py` ou `.jsx`.

### Regras comerciais

| Arquivo | Conteúdo |
|---------|----------|
| `docs/regras_comerciais_base.csv` | 10 operadoras × 8 regras (carências, adesão, cancelamento, multa, etc.) — 80 células |
| `docs/regras_comerciais_aliases.csv` | Variações de nome → operadora canônica |

**Manutenção:** altere o CSV; `tests/test_regras_comerciais.py` falha se faltar célula, houver duplicata ou operadora fora da lista. Detalhes em `docs/regras_comerciais_README.md`.

**Quem atualiza:** conteúdo comercial validado com Wesley/Newport; aliases quando aparecer grafia nova em cotação.

### Histórico de reajustes PME

| Arquivo | Conteúdo |
|---------|----------|
| `docs/reajustes_pme_base.csv` | Percentuais de reajuste ANS/operadora por período (grupos abaixo de 30 vidas) |

**Manutenção:** editar o CSV; lógica em `src/newport_app/reajuste_pme.py` só lê e sugere — **não** altera valores já confirmados no rascunho. Testes em `tests/test_reajuste_pme.py`.

**Uso:** sugestão na configuração do plano atual; o operador pode aceitar ou sobrescrever.

### Base de rede credenciada (SiscorNet)

**Não versionada no Git** — arquivo Excel externo (ex.: `SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx` em ambiente local). Contém matriz **prestador × plano** (hospitalar/laboratorial), com cabeçalho em quatro linhas (nível, operadora, linha comercial, nome do plano).

**Quem atualiza:** Newport/SiscorNet, conforme contrato comercial; frequência típica alinhada à operação comercial (não há pipeline automático de download no repositório).

**Uso previsto:** comparar redes entre planos cotados (aba futura ou planilha de equivalência). O núcleo financeiro **não** depende dela para calcular prêmio.

**Trocar versão:** substituir o arquivo referenciado localmente; scripts de diagnóstico em `.private/runtime/` apontam para o path absoluto configurado no ambiente. Nenhuma migração SQL — é planilha de referência.

**Casamento automático plano cotação ↔ coluna:** regras incrementais (aliases, coparticipação, acomodação, linha PRO, etc.) em `src/newport_app/presentation/casamento_rede.py`. Sobre **55** combinações plano×estudo reais medidas no banco demo: **38 casam**, **17 não**, **0 ambíguos** (censo com regras Wesley + normalização de caixa e percentual de copart). Os 17 restantes dependem de **planilha de equivalência** validada pelo Wesley — ver seção abaixo.

### Catálogo ANS (investigação, não integrado)

Foi verificado se dados abertos da ANS (`pda-008` características de produtos, ~166 mil linhas) substituem a equivalência manual. **Conclusão:** não resolve — PDFs do corpus não trazem `CD_PLANO` por produto cotado; nomes oficiais ANS são longos e **ambíguos** (dezenas de candidatos por plano SulAmérica); campo de acomodação ANS é Individual/Coletiva, **não** apartamento vs enfermaria. Rede hospitalar ANS (~1,4 GB) tem escala e granularidade diferentes da matriz SiscorNet. Registro da verificação: scripts em `.private/runtime/diag_ans_verificacao.py` (somente leitura).

---

## Em desenvolvimento: rede credenciada

**O que é:** mostrar, por plano cotado, quais prestadores (hospitais, etc.) entram na rede, usando a base SiscorNet alinhada ao que a Newport já usa comercialmente.

**Por que a Newport quer:** o comparativo financeiro sozinho não responde «onde meu colaborador atende»; rede entra na decisão junto com preço.

**Estado:** geografia e colunas da matriz nacional estão mapeadas; casamento automático por nome **parcial** — evolução de 9/55 acertos com regras estritas iniciais para **38/55** após regras Wesley e correções de normalização (caixa do núcleo via `normalizar_cabecalho`; remoção de percentuais 20/30/40/50 da coparticipação). **17** planos ainda exigem mapeamento manual (Amil ONE/S750, linhas PRO Porto sem sufixo regional, SulAmérica Direto/Vital/RC, etc.).

**Bloqueio principal:** nomenclatura comercial da cotação ≠ rótulo da coluna SiscorNet, mesmo quando o produto é o «mesmo» na prática. ANS não elimina o trabalho de equivalência.

---

## Em aberto

Resumo do **§12** de `REGISTRO-TECNICO-ALTERACOES.md` — lista completa e histórico lá.

| Tema | Por que continua aberto |
|------|-------------------------|
| Confirmações Wesley (regras comerciais, Hapvida/NotreDame, «Unimed os Bandeirantes») | Conteúdo comercial, não bug de código |
| Operadora do **plano vigente** nas regras contratuais do HTML | Decisão de produto: hoje só entram operadoras das cotações |
| Validade de cotação em cenário misto | Só opção de referência; teste 333 pendente |
| Parser Bradesco em produção | Existe, não registrado em `FAMILIAS` — afeta estudos Lunvox/IVTEC completos |
| PPTX, rede/reembolso/odonto/vida no entregável de 12 partes | Fora de escopo do piloto; HTML é o entregável real |
| Renderer PPTX/PDF unificado ao ViewModel | Próximo passo **quando autorizado** (`AGENTS.md`) |
| Autenticação, cloud, link público | Explicitamente não autorizado na etapa atual |
| Código morto em `html_renderer.py` (Bloco 2) | Limpeza adiada |
| Campos do rascunho ainda não mapeados ao HTML (tipo fiscal vigente, subtotal impresso, etc.) | Paridade parcial vigente vs proposta |

Defeitos conhecidos de apresentação exigem **teste de paridade entre camadas**, não só pytest verde.

---

## Como rodar

Pré-requisitos: Python 3.12+ com venv em `.venv`, Node.js para o frontend.

### Backend (API)

Na raiz do repositório:

```powershell
.\.venv\Scripts\python.exe -m uvicorn newport_app.api.main:app --reload --port 8002
```

O Vite proxy envia `/api` para **127.0.0.1:8002** (`web/vite.config.js`). Se uma sessão antiga ainda escutar na porta, mate o processo antes de testar — senão o browser mostra código velho.

### Frontend (desenvolvimento)

```powershell
cd web
npm install
npm run dev
```

Abrir **http://localhost:5173** (porta fixa `strictPort: true`). Validar renderização sempre nesta porta; outras portas ou `dist` desatualizado já causaram falso «bug corrigido».

### Modos

| Variável | Valor | Efeito |
|----------|--------|--------|
| `NEWPORT_MODO` | `demo` (default) | Banco e uploads em `.data/` |
| `NEWPORT_MODO` | `real` | Estudos e uploads em `.private/runtime/` |

Corpus de PDFs reais: `.private/corpus/` (nunca versionado). Override: `NEWPORT_CORPUS_COTACOES`.

### Testes

```powershell
.\.venv\Scripts\python.exe -m pytest
cd web
npm run test -- --run
```

Testes que dependem de PDFs privados: `pytest -m "not private_corpus"`.

Exemplos HTML de demonstração (modo autorizado): `python scripts/gerar_exemplos_html.py` → `.private/runtime/entregaveis/exemplos-2.8/` ou equivalente em demo.

---

## Leitura recomendada

| Ordem | Documento |
|-------|-----------|
| 1 | `docs/04-HANDOFF-IMPLEMENTACAO.md` |
| 2 | `docs/02-ESPECIFICACAO-IMPLEMENTACAO-SEGURA-v0.2.md` |
| 3 | `docs/03-PATCH-v0.2.1.md` (prevalece sobre 01/02 onde divergir) |
| 4 | `docs/07-ADDENDUM-FAIXA-HOMOLOGACAO-v0.2.2.md` (vidas) |
| 5 | `AGENTS.md` — regras para agentes e invariantes resumidos |
| 6 | `REGISTRO-TECNICO-ALTERACOES.md` — histórico de defeitos e validação |
| 7 | `docs/handoff-ia/` — API, SISCOR, apresentação, testes (referência operacional) |

---

## Licença e dados

Somente dados **fictícios ou anonimizados** entram no Git. Não versionar CPF, endereço, telefone ou qualquer PII. Estudos reais e corpus de cotações ficam em `.private/` ou equivalente local.
