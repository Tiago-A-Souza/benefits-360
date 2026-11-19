# Prontidão para produção — piloto Benefits 360 (corretores Newport)

> Só leitura do estado em **2026-11-18**, `master` @ `a7401e5` (tag `benefits-logos-operadoras-v1`).  
> Escopo: colocar o **Benefits** (estudos comparativos + Cotações nativa) nas mãos dos corretores **antes** de integrar o robô na nuvem.  
> Esforços em horas são julgamento de engenharia (não há métrica no repo).  
> Gravidade: **bloqueia** = o piloto hospedado/operacional não deve começar; **importante** = risco financeiro, jurídico ou operacional no primeiro mês; **pode esperar** = backlog conhecido.

**Premissa de arquitetura hoje:** o produto ainda é um **serviço local/on-prem**. SQLite em disco, uploads e HTML em pasta, CORS só `localhost:5173/5174`, Cotações no navegador falando com `127.0.0.1:8600`. Auth (Fase 3B) já existe para multi-usuário **se** `NEWPORT_MODO=real` + Supabase. O robô permanece **na máquina** até haver ponte/nuvem.

---

## A — Motor, cálculo e regras

| ID | Item | Status | Evidência | Gravidade | Horas |
|----|------|--------|-----------|-----------|-------|
| A1 | Motor financeiro (IOF 238 bps, half-up, centavos, `por_vida_entao_soma`) | **resolvido** (piloto) | `newport_motor/`; suítes A–H; ATEF/Anistia/IVTEC no `CONTEXTO-NOVA-CONVERSA.md`; `RELATORIO-IMPLEMENTACAO.md` §1.1 | — | 0 |
| A2 | Motor **aprovado para produção** (checkpoint formal) | **aberto** | `RELATORIO-IMPLEMENTACAO.md` §10: «Motor não aprovado para produção»; `docs/handoff-ia/03-MOTOR-CALCULO.md` | importante | 8–16 (revisão Wesley/financeiro + ata; sem mudar código) |
| A3 | `quantidade_cotada` × vidas atribuídas | **aberto** | Motor não cruza (`RELATORIO-IMPLEMENTACAO.md:65`; addendum `docs/07` §5). Compilador só exige o campo (`APP-QTD-001` em `finance_validation.py:126-133`), sem bater com a população | importante | 12–20 |
| A4 | Caso dourado financeiro (cotação alinhada à população SISCOR) | **aberto** | `RELATORIO-ETAPA-2.1.md` §7; `docs/06` I-05: cotação de 5 vidas ≠ SISCOR 41 — **não** usar como dourado | importante | 16–24 (montar corpus + oráculo; depende de PDF real) |
| A5 | Revisor / confirmação extra acima da faixa homologada (H-01) | **parcial** | Motor: H-01 alerta, calcula, sem truncar (`validations.py`; addendum 0.2.2). UI traduz «Confirme com o revisor» (`motor_out.py:1338-1345`). Aprovação **não** exige checkbox extra para H-01 — só `confirmo_conteudo` + nome (`services/snapshot.py`) | importante | 6–10 |
| A6 | Estratégias `soma_entao_aplica` / `no_total` | **resolvido** (bloqueadas) | B-07 se não for `por_vida_entao_soma` (`RELATORIO-IMPLEMENTACAO.md` §1.1; `validations.py:101-115`) | — | 0 no piloto |
| A7 | Reajuste negativo | **resolvido** (bloqueado) | B-07; não homologado no piloto | pode esperar | 0 |
| A8 | Faixa 1–29 / estudos >29 (Anistia 41) | **parcial** | H-01 alerta; W-11 (homologação formal Wesley do addendum) pendente (`docs/07` §4) | importante | 2–4 (decisão) + A5 |
| A9 | DPs DP-01…DP-14 ainda `provisória` | **aberto** | `CADERNO-DECISOES-PROVISORIAS-v0.2.md`; DP-13 marca entregável **RASCUNHO INTERNO**. PolicySet é registry in-memory, não tabelas SQL (`policy/registry.py` vs caderno §1) | bloqueia **entregável oficial ao cliente**; não bloqueia uso interno com banner | 20–40 (reuniões Wesley; flip de status) |
| A10 | Extração PDF «homologada» | **aberto** | `extracao_financeira_homologada` **sempre False** (`maturidade.py:58`) | importante | 8–16 por família após goldens reais |
| A11 | Parser Bradesco fora de `FAMILIAS` | **aberto** | `parsers/bradesco.py` existe; `_registrar_familias` só amil/omint/porto/sulamerica (`template_families.py:78-79`) | importante se o piloto cotar Bradesco por PDF | 4–8 |
| A12 | Formato misto (renovação + vidas novas no mesmo estudo; EVOPE) | **aberto** | `CONTEXTO-NOVA-CONVERSA.md` backlog; um formato por estudo | pode esperar (se o piloto for renovação simples) | 40–80 |
| A13 | Validade da cotação em cenário misto | **aberto** | `REGISTRO-TECNICO-ALTERACOES.md` §12: usa só a 1ª atribuição | pode esperar | 6–10 |
| A14 | Deduplicar planos idênticos entre PDFs | **aberto** | Registro §12 «Correções mapeadas» | pode esperar | 8–12 |
| A15 | Tipo fiscal legado (estudos gravados antes da correção IOF) | **aberto** | Registro §12 | importante em base real já importada | 4–8 (varredura + correção assistida) |
| A16 | Seguro novo E2E | **parcial** | Motor existe; UI alinhada (`alinhar-seguro-novo`); `AGENTS.md` ainda pede autorização para «seguro novo» de produção | pode esperar se o piloto for só renovação | 16–24 |
| A17 | PPTX/PDF de produção | **aberto** (proibido sem autorização) | `AGENTS.md`; `delivery_storage.py` «não implementado»; HTML é o entregável | pode esperar se o piloto aceitar HTML | 40–80 **após** autorização |
| A18 | `faixa_override` morto | **aberto** | Campo no modelo; cálculo usa `faixa_em` | pode esperar | 2 |
| A19 | Banner SSE de versão nativa vs robô local | **aberto** | `docs/PENDENCIAS-PROJETO.md` | importante quando Benefits for hospedado e o robô ficar no PC | 8–12 |

---

## B — Rede credenciada / SiscorNet (Wesley)

| ID | Item | Status | Evidência | Gravidade | Horas |
|----|------|--------|-----------|-----------|-------|
| B1 | Recorte geográfico (município + capital vs praça principal Newport) | **aberto** (provisório) | `REGISTRO` §12: `CRITERIO_RECORTE_GEOGRAFICO = MUNICIPIO_E_CAPITAL_UF`; Anistia: prática Newport ~praça principal, pipeline gera centenas de principais | importante | 4 decisão + 8–16 código se mudar |
| B2 | Regras comerciais: Unimed os Bandeirantes | **aberto** | Nome não localizado; aliases `Unimed dos Bandeirantes` / `Unimed Bandeirantes` (`REGISTRO` §12) | pode esperar | 1 (Wesley) |
| B3 | Hapvida vs NotreDame (Smart vs Advance/Premium/Infinity) | **parcial** | Valores iguais por confirmação Wesley; **não** usados para casar operadora | pode esperar | 2 |
| B4 | Coluna do plano vigente nas regras contratuais | **aberto** | Só operadoras das cotações; Tiago já perguntou (Amil atual ausente) | importante para o documento | 6–10 |
| B5 | Rascunhos demo sem UF/CIDADE (aba Rede vazia) | **parcial** | Importados antes da fase B; aviso pede reimportar. Estudos **reais** novos com UF/CIDADE funcionam | pode esperar no demo; **importante** se copiar demo para real sem reimportar | 2–4 (procedimento) |
| B6 | SiscorNet lista hospitais fechados (Santa Genoveva, Santa Helena) | **aberto** (base) | `principal=sim` os exclui da visão enxuta; base bruta permanece | pode esperar | 2 (Wesley/curadoria CSV) |
| B7 | Equivalência plano cotação ↔ matriz rede | **parcial** | `docs/planos_rede_aliases.csv` (Wesley 2026-09-27); estados `rede_nao_mapeada` existem | importante | contínuo; 4–8 por lote de planos novos |
| B8 | Homologação privada SISCOR (layout da corretora em produção) | **aberto** | `RELATORIO-ETAPA-2.3.md`: implementação ok, homologação privada pendente | importante | 8–16 (Wesley + 1 planilha real por versão) |

Rede, reembolso, odonto e seguro de vida **como produtos** continuam fora do núcleo financeiro; a aba Rede **já existe** no HTML/etapa 5 (fases D1/D2 + seleção no sistema). Não é bloqueante para calcular prêmio; é bloqueante só se o piloto prometer comparativo de rede fiel ao material Newport.

---

## C — Segurança e dependências

| ID | Item | Status | Evidência | Gravidade | Horas |
|----|------|--------|-----------|-----------|-------|
| C1 | Login real (Supabase JWT) + dono por estudo | **parcial** (código pronto) | Merge `5ea8054` Fase 3B: `/api/saude` público; demais `/api/*` exigem JWT (`auth/middleware.py`); `usuario_id` nas tabelas listadas (migração 3.1.0). Demo **bypassa** auth (`usuario_demo`) | bloqueia se o piloto for multi-corretor **sem** `NEWPORT_MODO=real` | 4–8 (env + teste com N corretores) |
| C2 | CORS só localhost | **aberto** | `api/main.py:317-325` origens `5173/5174`. Domínio de produção **não** está na lista | **bloqueia** hospedagem | 2–4 |
| C3 | `NEWPORT_MODO=demo` em servidor compartilhado | **aberto** (risco operacional) | Demo = um usuário `"demo"`, sem JWT. `auth/startup.py` recusa real sem `SUPABASE_URL` | **bloqueia** | 1 (checklist de subida) |
| C4 | Vulnerabilidades npm | **aberto** | `npm audit` em `web/` (2026-11-18): **9** (2 critical, 4 high, 3 moderate). Critical: **vitest/tinypool** (ferramenta de teste, não o `dist`). High: nanoid, postcss, source-map-js, vite. `RELATORIO-ETAPA-2.1.md` §7: atualizar **antes** de expor o piloto em rede; **não** `npm audit fix --force` | **bloqueia** se expuser `vite --host`; **importante** no `npm run build` + API | 8–16 (upgrade controlado Vite 6 / vitest 3+, retestar) |
| C5 | Papéis Analista vs Revisor (DP-14) | **parcial** | Aprovação pede `revisor_nome` texto livre + autoaprovação com justificativa. Sem RBAC Supabase, qualquer logado autoaprova | importante | 12–20 |
| C6 | Dados compartilhados vs por usuário | **parcial** | Por usuário: estudos, rascunhos, snapshots, SISCOR, extrações, histórico (`TABELAS_POR_USUARIO*` em `migration.py:714-730`). **Compartilhados** (leitura): CSVs de rede/regras/reajuste, código, `schema_migrations`. Catálogos SiscorNet **não** são por corretor | ok para piloto (catálogo único Newport) | 0 |
| C7 | HTML entregável: fetch+blob (não `<a href>` sem token) | **resolvido** | 3B `e66895b`; teste `api.auth.test.js` | — | 0 |
| C8 | Senha do portal no cofre local (não no Benefits) | **resolvido** (desenho) | Cotações nativa → robô `127.0.0.1:8600`; Benefits não guarda senha | — | 0 |
| C9 | Telas nativas abrindo robô antigo `#/...` | **resolvido** (docs atrasados) | `TELAS_ROBO_NAO_PORTADAS = []` (`regrasNova.js:491`); testes em `Restante.test.jsx`. `PENDENCIAS-PROJETO.md` ainda cita o defeito | — | 0 (só atualizar a pendência) |
| C10 | Teste intermitente Bradesco simulador | **aberto** | 1/192 (`PENDENCIAS-PROJETO.md`) | pode esperar | 4–8 se reaparecer |
| C11 | Auth corporativa Newport (SSO) | **aberto** | `AGENTS.md` proíbe sem autorização; hoje é conta Supabase | pode esperar no piloto pequeno | 24–40 **após** autorização |
| C12 | Link público / cloud storage | **aberto** (proibido) | `LocalFileDeliveryStorage.url_acesso` → `None` | pode esperar | — |

---

## D — Infraestrutura de hospedagem

| ID | Item | Status | Evidência | Gravidade | Horas |
|----|------|--------|-----------|-----------|-------|
| D1 | Decisão «onde roda o piloto» (2.6) | **aberto** | `docs/05` §7: Newport (infra); SQLite vs Postgres | **bloqueia** | 4 (decisão) |
| D2 | SQLite em disco efêmero (PaaS sem volume) | **aberto** | `estudos.db`, `importacoes.db`, `cotacoes.db` em `.private/runtime/` (`config/paths.py`). Sem volume persistente **apaga estudos** | **bloqueia** qualquer host sem disco | 8–16 (volume + paths) ou 40–80 (Postgres, fora do piloto mínimo) |
| D3 | Uploads, PDFs, HTML entregável | **aberto** no host | `uploads/`, `cotacoes/`, `entregaveis/` no mesmo runtime. `url_acesso` nulo — o corretor **baixa** o HTML, não abre link | **bloqueia** se o disco morrer; ok se volume + download | 4–8 |
| D4 | Backup | **parcial** | Backup **só na migração** (`backup_banco` em `migration.py`). Sem job diário, sem restore testado, sem off-site | **bloqueia** (PII + trabalho comercial) | 8–16 |
| D5 | HTTPS / domínio | **aberto** | App local HTTP. JWT Supabase em HTTP é inaceitável fora de localhost | **bloqueia** internet / Wi-Fi de escritório | 4–8 (reverse proxy) |
| D6 | Variáveis de ambiente | **parcial** | `.env.example`: `SUPABASE_URL`, `SUPABASE_JWT_SECRET` (legado). Front: `VITE_SUPABASE_*`. Real: `NEWPORT_MODO=real`, `NEWPORT_PRIVATE_RUNTIME`, `BENEFITS_DONO_LEGADO_ID` (nunca no Git). CORS/origem de produção **não** tem env | **bloqueia** | 4 |
| D7 | Logs | **parcial** | `diagnostico.jsonl` local (`paths.py`); princípio anti-PII documentado. Sem agregação, retenção nem acesso do operador | importante | 8 |
| D8 | Cotações com Benefits **hospedado** e robô **local** | **aberto** | Navegador chama `127.0.0.1:8600` (`rpaClient.js`). No cloud, isso é o **servidor**, não o PC do corretor. Branch `rpa-ponte-api` também é o **processo 8002** falando com o robô da **mesma máquina** | **bloqueia Cotações no piloto hospedado**; não bloqueia estudos se o robô ficar fora | 16–32 (agente local no PC) **ou** manter Cotações só no desktop |
| D9 | Compatibilidade de versão Benefits ↔ robô local | **aberto** | `PENDENCIAS-PROJETO.md` (proposta não implementada) | importante se misturar versões | 8–12 |
| D10 | Postgres / multi-instância | **aberto** | Arquitetura-alvo `docs/05` §6; não implementado | pode esperar (1 VM + SQLite + backup basta no piloto) | — |

---

## E — Dados pessoais / LGPD

O que o sistema **guarda** (modo real, após importação SISCOR confirmada):

| Dado | Onde | Necessário ao cálculo? | Nota |
|------|------|------------------------|------|
| Nome do segurado | `vidas[].nome`, `beneficiarios.nome`, `beneficiario_participacao.nome`, HTML modo `beneficiario` | sim (slide / grupo familiar) | Permitido pelo plano 2.3 (D-P2) |
| Data de nascimento | mesmas tabelas + rascunho | sim (idade/faixa ANS) | Permitido |
| Parentesco, sexo | rascunho / participação | faixa tit/dep; sexo opcional | |
| Plano, operadora, valor fatura (centavos) | rascunho / participação | sim | dado comercial, não PII clássico |
| UF, cidade | `VidaRascunho` (opcional) | recorte de rede | |
| **CPF do titular** | `VidaRascunho.cpf_titular` se a planilha tiver a coluna | **não** para o prêmio; usado como chave de grupo familiar | **além** da whitelist mínima do patch P9 (`docs/03`); constante opcional `CPF TITULAR` em `siscor_importer/constants.py:18` |
| Matrícula, nome do titular, tipo de vida | rascunho opcional | vínculo familiar | |
| Cliente (razão / apelido) | `estudos_meta`, `clientes` | sim | |
| Login do corretor | Supabase (e-mail) | auth | fora do SQLite de estudos |
| Senha de portal de operadora | **não** no Benefits (cofre Windows / memória do robô) | — | |

**Não** devem entrar (descarte na ingestão, P9): CPF do próprio segurado (salvo o titular opcional acima), RG, endereço, CEP, telefone, e-mail do beneficiário, nome da mãe, PIS.

| ID | Item | Status | Evidência | Gravidade | Horas |
|----|------|--------|-----------|-----------|-------|
| E1 | Minimização (whitelist SISCOR) | **parcial** | Patch P9 vs `cpf_titular` opcional persistido | importante | 4–8 (decisão: mascarar/hash vs manter) |
| E2 | HTML modo beneficiário com nomes | **resolvido** (aviso) | Confirm na UI; modo `faixas` sem nomes é o recomendado | importante (disciplina: não mandar modo beneficiário ao cliente sem DPA) | 2 (orientação operacional) |
| E3 | Base legal / DPA / registro de tratamento | **aberto** (fora do código) | Plano 2.3 pede persistir só o necessário; não há texto de política no repo | **bloqueia** jurídico do piloto com dados reais | 8–16 (Newport/jurídico; não é ticket de código) |
| E4 | Logs sem PII | **parcial** | `diagnostico.py` anti-PII; snapshots JSON no SQLite **contêm** o rascunho (nomes, nascimentos, CPF titular se importado) | importante | 4 (revisar dump de diagnóstico) |
| E5 | Git / zip sem `.private/` | **resolvido** (processo) | `.gitignore`; `CONTEXTO` alerta `git archive` | — | 0 |

---

## F — Branches não mergeadas

Estado: `git log master..<branch>` em 2026-11-18.

### `integracao-regras-grupo-familiar` (1 commit à frente: `fa6f1dc`)

Junta, num único commit de integração, a aba **Regras contratuais** (CSV + casamento por igualdade) e o **grupo familiar compacto/paginado**. **Não mergear na master** foi a mensagem do commit.

Na master **já existem** `presentation/regras_comerciais.py`, CSVs e uso no HTML. A branch parece um **recorte de integração** antigo vs. o que entrou por outras frentes. Diff atual: +963/−38 (CSV, testes `test_regras_comerciais.py`, renderer). **Risco de conflito** se mergeada agora. Gravidade: **pode esperar**. Esforço para reconciliar: 8–16 h. Não é pré-requisito do piloto.

### `rede-etapa5-alternativa` (1 commit: `1f0bb0d`)

Só **documentação** (`CONTEXTO-NOVA-CONVERSA.md`, `REGISTRO-TECNICO-ALTERACOES.md`) pós-merge da etapa 5 de rede. O código da seleção de rede no sistema **já está na master**. Gravidade: **pode esperar** (arquivar/apagar depois). Horas: 0,5.

### `rpa-ponte-api` (1 commit: `a0968aa`)

Ponte `/api/rpa` no Benefits 8002: whitelist de rotas para o robô local, sem CORS no browser, sem Origin/Cookie/Authorization nas mutações; desktop (pasta) de fora.

**Não resolve** Benefits na nuvem + robô no PC do corretor: o 8002 na nuvem não alcança o `127.0.0.1` do corretor. Só ajuda se API e robô estão **na mesma máquina** (hoje o nativo já fala direto `5173 → 8600`). Gravidade para este piloto (pré-robô-nuvem): **pode esperar**. Útil depois, ou como agente instalado no desktop. Horas se retomar: 8–12 + produto.

Outras branches locais (`benefits-*` já mergeadas, `etapa5-*`, `rpa-*`, etc.) **não** entram neste recorte.

---

## Bloqueantes para o piloto — ordem sugerida

Pressuposto: **piloto interno dos corretores Newport**, dados reais, HTML como entregável, **robô continua local**, Benefits pode ser **1 servidor da Newport** (não PaaS efêmero) **ou** cada corretor no PC.

### Se o piloto for **hospedado** (vários corretores, um Benefits)

1. **D1** — Decidir onde roda (1 VM Newport com disco persistente vs cada desktop). Sem isso o resto não fecha.  
2. **D2 + D3 + D4** — Volume persistente para os 3 SQLite + uploads/PDFs/HTML; backup diário com restore ensaiado.  
3. **D5 + D6 + C2 + C3** — HTTPS, domínio, `NEWPORT_MODO=real`, `SUPABASE_URL` + anon no front, `BENEFITS_DONO_LEGADO_ID` se houver legado, CORS com a origem real (não localhost).  
4. **C1** — Ensaio: dois corretores, estudos isolados, 401 sem token, HTML só via blob.  
5. **E3** — OK jurídico (tratamento de nome/nascimento/CPF titular) **antes** de importar posição cadastral real.  
6. **D8** — **Cotações:** ou o piloto hospedado **não inclui** o robô (estudos-only), ou cada corretor usa Cotações **só no PC** (stack local 5173+8002+8600). Não misturar UI cloud com 8600 local sem agente.  
7. **C4** — Não expor `vite dev` na rede; servir `web/dist` pela API; upgrade controlado das deps de build.  
8. **A9** — Manter banner **RASCUNHO INTERNO** até Wesley homologar DPs; comunicar que o HTML **não** substitui o PPTX Newport neste piloto.  
9. **A5 + A8** — Se o piloto incluir grupos >29 vidas: checkbox/atestado H-01 na aprovação.  
10. **A3 + A4** — Antes de confiar em PDF extraído: cruzar `quantidade_cotada` e ter 1 caso dourado da população real.

### Se o piloto for **só desktop** (cada corretor instala, como hoje)

Bloqueantes enxutos: **C3** (nunca demo com dados reais), **D4** (backup da pasta `.private/runtime`), **E3**, **A9** (banner), **C4** (não `--host` na internet). C2/D5/D8 deixam de bloquear. Cotações nativa já funciona com o robô local.

---

## Não bloqueia o piloto (backlog consciente)

PPTX; formato misto EVOPE; Bradesco em `FAMILIAS` (se o piloto não depender de PDF Bradesco); SSO corporativo; Postgres; robô na nuvem; merge das três branches da seção F; validade mista; goldens sintéticos vs layout real; teste Bradesco intermitente; `faixa_override`.

---

## Fontes

`docs/PENDENCIAS-PROJETO.md`, `CONTEXTO-NOVA-CONVERSA.md`, `REGISTRO-TECNICO-ALTERACOES.md` §12, `RELATORIO-IMPLEMENTACAO.md`, `RELATORIO-ETAPA-2.1.md` §7, `RELATORIO-ETAPA-2.3.md`, `CADERNO-DECISOES-PROVISORIAS-v0.2.md`, `docs/05`, `docs/07`, `docs/handoff-ia/09` e `CONSOLIDADO.md`, `AGENTS.md`, código em `auth/`, `config/paths.py`, `template_families.py`, `maturidade.py`, `npm audit` em `web/` (2026-11-18), `git branch` / diffs das três branches.
