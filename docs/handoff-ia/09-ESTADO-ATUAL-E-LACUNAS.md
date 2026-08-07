# 09 — Estado atual e lacunas

Fonte: commit `2a69d4c0bd12e4e8613cb8b085b1dac0c50cb805` — 2026-07-27

Documento operacional para IA sem acesso ao código. O que funciona ponta a ponta, stubs, inventário de `pass`/`não implementado`, bugs conhecidos, divergências doc×código, riscos e próximos passos.

---

## O que funciona end-to-end hoje

Jornada operacional (git ≥ **ETAPA 3.0** + hotfixes 3.0.1–3.0.3 + correções de comparativo/apresentação até `2a69d4c`):

1. Gestão de estudos / wizard reformulado (`855ed7b` ETAPA 3.0).
2. Importação e conferência SISCOR (incl. hotfixes de migração/IOF/referência).
3. Extração/conferência de cotação PDF (famílias Porto/SulAmérica/Amil/Omint; hotfixes SulAmérica/Porto).
4. Compilação → cálculo → comparativo multi-proposta → **confirmação** persistida.
5. Snapshot candidato (hash) → revisão → aprovação local → HTML faixas/beneficiário.
6. Histórico longitudinal (clientes, ciclos, posições, vínculos, plano contratado sob demanda).

### DIVERGÊNCIA de estágio documentado

| Fonte | Afirma |
|-------|--------|
| `git log` | `ETAPA 3.0` (`855ed7b`) + HOTFIX 3.0.1–3.0.3 + commits de tela 5 / confirmação até `2a69d4c` |
| `AGENTS.md:5` | Ainda: **«ETAPA 2.8.1 concluída»** |

Tratar `AGENTS.md` como **desatualizado** quanto ao rótulo de etapa; o código e o histórico git prevalecem.

---

## Stubs e não implementados

| Item | Evidência |
|------|-----------|
| Contrato futuro de entrega hospedada | Docstring: «não implementado nesta etapa» — `presentation/delivery_storage.py:1`; `LocalFileDeliveryStorage.url_acesso` → `None` (`delivery_storage.py:32-33`) |
| Renderer PPTX/PDF | `AGENTS.md:24` |
| Auth corporativa, link público, cloud, seguro novo (produção) | `AGENTS.md:24-28` |
| Parser Bradesco **fora** de `FAMILIAS` | Arquivo `parsers/bradesco.py` existe; registro em `_registrar_familias` não o inclui (`template_families.py:78-79`) |
| Corpos `pass` em classes de exceção de serviço | Ver inventário abaixo (marcadores de tipo, não TODOs) |

---

## Inventário TODO / FIXME / `pass` / «não implementado»

### Marcadores `TODO` / `FIXME`

Busca no código e docs de produto (excluindo este handoff): **nenhuma ocorrência** encontrada com esses literais.

### Classes de exceção com corpo `pass`

| file:line | Classe |
|-----------|--------|
| `services/calculo.py:21-22` | `EstudoNaoEncontradoError` |
| `services/snapshot.py:31-32` | `SnapshotNaoEncontradoError` |
| `services/snapshot.py:35-36` | `SnapshotBloqueadoError` |
| `services/snapshot.py:39-40` | `AprovacaoInvalidaError` |
| `services/comparativo_ui.py:9-10` | `SelecaoApresentacaoInvalidaError` |
| `services/comparativo_confirmacao.py:19-20` | `ConfirmacaoComparativoInvalidaError` |
| `services/extracao_cotacao.py:33-34` | `EstudoNaoEncontradoError` |
| `services/extracao_cotacao.py:37-38` | `ExtracaoNaoEncontradaError` |
| `services/extracao_cotacao.py:41-42` | `CampoNaoEncontradoError` |
| `services/extracao_cotacao.py:45-46` | `OpcaoNaoEncontradaError` |
| `services/importacao_siscor.py:56-57` | `EstudoNaoEncontradoError` |
| `services/importacao_siscor.py:72-73` | `ModoImportacaoInvalidoError` |
| `services/importacao_siscor.py:76-77` | `LinhaNaoEncontradaError` |
| `services/importacao_siscor.py:80-81` | `ExclusaoSemMotivoError` |
| `services/importacao_siscor.py:84-85` | `LinhaIncompletaConfirmacaoError` |

(Nota: `HistoricoPersistenciaError`, `ImportacaoRequerDecisaoError`, `AplicacaoExtracaoError` têm `__init__` próprio — não são `pass` vazio.)

### «não implementado» literal

| file:line | Texto |
|-----------|-------|
| `presentation/delivery_storage.py:1` | «não implementado nesta etapa» |
| `AGENTS.md:24` | Renderer PPTX/PDF «não implementado» |

---

## Bugs conhecidos / soft spots

| Soft spot | Notas | Evidência |
|-----------|-------|-----------|
| Nome de teste legado `test_b08_mais_de_29_vidas` | Asserta **H-01**, não B-08 | `test_suite_h_formas_escala.py:55-58` |
| Bradesco não entra no identificador de família | Extração por família não seleciona Bradesco | `template_families.py:78-210` vs `parsers/bradesco.py` |
| `quantidade_cotada` vs vidas | Sem verificação no motor | `RELATORIO-IMPLEMENTACAO.md:65` |
| `faixa_override` morto | Campo no modelo; cálculo usa `faixa_em` | `newport_motor/models.py:132`; handoff motor |
| Extração financeira nunca homologada | Flag sempre `False` | `maturidade.py` |
| Aprovação local sem autenticação | Provisória por design | `RevisaoApresentacaoPanel.jsx:171-172`; `AGENTS.md:25` |
| HTML ≠ PPTX master | Entregável cliente ainda não é o formato histórico Newport | `AGENTS.md:24` |

---

## Divergências documentação × código

| ID | Doc diz | Código faz | Evidência |
|----|---------|------------|-----------|
| **B-08** | `docs/04-HANDOFF-IMPLEMENTACAO.md:90` — B-08 «>29 bloqueia» | B-08 = **zero vidas**; > max homologadas = **H-01** alerta | `validations.py:1`, `21-46`; `RELATORIO-IMPLEMENTACAO.md:59`, `180` |
| **B-01** | Docs de handoff antigo falam B-01 no motor | B-01 **adiado** para camada de aplicação (aprovação) | `validations.py:1`; `engine.py:32` |
| **Estágio AGENTS** | ETAPA 2.8.1 | Git em 3.0+ | `AGENTS.md:5` vs `git log` |
| **PolicySet tabelas** | Caderno: `PolicyEntry` / `StudyPolicyChoice` relacionais | Registry in-memory `PolicySet` dataclass; sem tabelas SQL de policy | `docs/01:27-30`; `policy/registry.py:13-41`; `migration.py` só `policy_set_versao` em rascunho/snapshot |
| **`faixa_override`** | Campo no modelo sugere uso | Não lido no cálculo | `models.py:132` (motor) |
| **Versões do motor** | Uma versão semântica esperada | `MOTOR_VERSAO = "0.1.0"` no snapshot vs `extrator_versao="motor@0.1.2"` na proveniência | `models/snapshot.py:10`; `reconciliation.py:354` |
| **`confirmado` default** | Draft/PDF inicia não confirmado | Motor `ProvenienciaCampo.confirmado: bool = True` | `parsers/base.py:49`; `newport_motor/provenance.py:27` |
| **`docs/04` B-08** | Ainda descreve regra pré-1.2.2 | Código e `RELATORIO` + addendum 0.2.2 prevalecem | `docs/04:90` |

---

## Riscos técnicos

1. **Precisão comercial sem PPTX** — HTML piloto pode divergir visualmente do material que o cliente conhece; risco de rejeição operacional.
2. **Homologação financeira PDF sempre falsa** — analista pode tratar extração como “pronta” sem o flag de homologação.
3. **Bradesco órfão** — parser sem família → documentos Bradesco caem em “não reconhecido” no fluxo de famílias.
4. **PolicySet não auditável como tabelas** — evolução de DP via código/registry, não via promoção de linha SQL como no caderno.
5. **Confirmação / hash / snapshot** — cadeia sensível; regressões recentes (`2a69d4c`, `10a5cb6`) mostram acoplamento UI↔API.
6. **Modo real + PII** — modo `beneficiario` grava nomes em HTML local; depende de disciplina operacional (`AGENTS.md:44-48`).
7. **Docs canônicos `docs/01–04` desatualizados** em pontos críticos (B-08) — agentes que lerem só o handoff antigo erram bloqueios.

---

## Próximos passos (impacto ÷ esforço)

Ordenados do melhor retorno relativo:

| Prioridade | Ação | Por quê |
|------------|------|---------|
| 1 | Atualizar `AGENTS.md` (estágio 3.0+) e corrigir menção B-08 em `docs/04` **ou** addendum explícito | Esforço baixo; evita erro sistemático de agentes (`AGENTS.md:30` restringe mover 01–04 — preferir addendum/patch se 04 for intocável) |
| 2 | Registrar família Bradesco em `FAMILIAS` + testes sintéticos | Parser já existe; desbloqueia operadora do escopo declarado |
| 3 | Fechar verificação `quantidade_cotada` × vidas (alerta ou B-xx) | Lacuna financeira explícita no relatório; esforço médio |
| 4 | E2E seguro novo (formato `NOVO`) na UI + testes | Motor parcial; produto incompleto sem jornada |
| 5 | Renderer PPTX a partir do mesmo `PresentationViewModel` | Alto impacto comercial; esforço alto; bloqueado até autorização (`AGENTS.md:23-28`) |
| 6 | Auth corporativa + invalidação de autoaprovação solta | Governança; esforço alto |
| 7 | Módulos rede / reembolso / odonto / seguro de vida | Fora do piloto; esforço muito alto; só após PPTX financeiro estável |

---

## ⚠️ NÃO VERIFICADO

1. Ranking de próximos passos (impacto÷esforço) é julgamento de engenharia deste handoff — não há métricas de esforço no repo.
2. Lista completa de bugs de produção reportados por usuários Newport (só soft spots derivados do código/testes/commits).
3. Se hotfixes 3.0.x fecharam todos os casos Atef/Porto/SISCOR mencionados nas mensagens de commit (não reexecutados aqui).
4. Conteúdo atualizado de `RELATORIO-IMPLEMENTACAO.md` vs. estado pós-3.0 (relatório foca ETAPA 1.x).
