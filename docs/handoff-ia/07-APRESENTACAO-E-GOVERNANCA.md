# 07 — Apresentação e governança

Fonte: commit `2a69d4c0bd12e4e8613cb8b085b1dac0c50cb805` — 2026-07-27

Documento operacional para IA sem acesso ao código. Snapshot, hash canônico, aprovação, HTML e paridade com o entregável manual Newport.

---

## Fluxo de snapshot (governança)

Sequência obrigatória (`AGENTS.md:40`; espelhada na UI `RevisaoApresentacaoPanel.jsx:170-172`):

1. **Calcular** — compilador + motor produzem comparativo (pré-requisito; bloqueios impedem snapshot).
2. **Snapshot candidato** — `SnapshotService.gerar_snapshot_candidato` congela payload + hash; estado `candidato`; workflow → `em_conferencia` (`services/snapshot.py:92-117`).
3. **Revisão** — UI exibe resumo do comparativo congelado e detalhes técnicos (hash/payload) (`RevisaoApresentacaoPanel.jsx:190-222`).
4. **Aprovação** — só candidato; exige `confirmo_conteudo` + nome do revisor (`services/snapshot.py:146-160`; UI `RevisaoApresentacaoPanel.jsx:225-264`).
5. **HTML** — somente com snapshot `aprovado` + aprovação válida (`services/apresentacao.py:45-51`; API `api/main.py:755-759`).

Estados do snapshot: `candidato` | `aprovado` | `superado` (`models/snapshot.py:17`).

---

## Hash canônico (SHA-256)

Módulo: `src/newport_app/snapshot/hashing.py`.

Campos do payload canônico — **sem timestamps** (`hashing.py:9-19`, docstring `hashing.py:30-32`):

| Campo | Papel |
|-------|--------|
| `rascunho` | Rascunho congelado |
| `estudo_input` | Entrada tipada do motor |
| `effective_policy` | Políticas efetivas |
| `motor_result` | Resultado do motor |
| `comparativo` | Comparativo de UI |
| `compiler_versao` | Versão do compilador |
| `motor_versao` | Versão registrada no snapshot |
| `policy_set_versao` | Versão do PolicySet |
| `documentos` | Metadados SISCOR/cotação |

- Serialização: `json.dumps(..., sort_keys=True, separators=(",", ":"))` (`hashing.py:22-23`).
- Digest: `hashlib.sha256(...).hexdigest()` (`hashing.py:26-27`).
- `gerado_em` entra no payload persistido mas **fora** do hash (`services/snapshot.py:86-101` vs `extrair_payload_canonico`).

Constante de versão no snapshot: `MOTOR_VERSAO = "0.1.0"` (`models/snapshot.py:10`). Proveniência interna do motor usa string distinta `motor@0.1.2` (`newport_motor/reconciliation.py:354`) — ver divergências em `09`.

---

## Aprovação nunca precede visualização

Três camadas impedem pular a revisão:

| Camada | Mecanismo | Evidência |
|--------|-----------|-----------|
| UI | Checkbox “Confirmo que revisei…”; botão Aprovar desabilitado sem `confirmo`; seção HTML só se `aprovado?.aprovado` | `RevisaoApresentacaoPanel.jsx:253-261`, `267-268`, `115-119` |
| Serviço de aprovação | Rejeita se `not req.confirmo_conteudo` | `services/snapshot.py:152-153` |
| API / geração HTML | Preview exige `snap.estado == "aprovado"`; gerar exige estado aprovado **e** aprovação não invalidada | `api/main.py:755-759`; `services/apresentacao.py:45-51` |

Modelo do request: `confirmo_conteudo: bool = False` (`models/snapshot.py:64`). Autoaprovação exige justificativa (`services/snapshot.py:161-164`; `AGENTS.md:36`).

---

## Geração HTML

Pipeline:

1. `ApresentacaoService.gerar_html` valida aprovação → resolve propostas → `construir_view_model` → `render_html` → grava arquivo via `LocalFileDeliveryStorage` (`services/apresentacao.py:36-103`).
2. Builder: `presentation/builder.py` — `construir_view_model` (`builder.py:208-376`); recalcula por proposta com motor existente (`motor_por_proposta.py`).
3. Renderer: `presentation/html_renderer.py` — `RENDERER_VERSAO = "html@2.8.1"` (`html_renderer.py:16`); `render_html` (`html_renderer.py:165-299`).

### Modos

| Modo | Comportamento | Evidência |
|------|---------------|-----------|
| `faixas` | Tabelas por faixa etária (tit./dep./vidas, vigente, reajustado, colunas de proposta); sem nomes | `html_renderer.py:242-257`; UI “recomendado — sem nomes” `RevisaoApresentacaoPanel.jsx:276-280` |
| `beneficiario` | Tabela por nome/idade/faixa/parentesco + valores; aviso PII no HTML e confirm na UI | `html_renderer.py:220-224`, `259-290`; `RevisaoApresentacaoPanel.jsx:143-147`, `282-290` |

Paginação: até 3 propostas por página (`builder.py:30`; `html_renderer.py:17`).

ViewModel: valores em **centavos**; formatação `R$` só no renderer (`models/presentation.py:1`; `AGENTS.md:34`).

---

## Banner RASCUNHO INTERNO

Texto default no ViewModel (`models/presentation.py:117-119`):

> RASCUNHO INTERNO — políticas provisórias sujeitas a homologação.

Renderizado em bloco `.rascunho` no HTML (`html_renderer.py:182`, `218`). Alinhado a DP-13 / regra de ouro do caderno (`docs/01-CADERNO-DECISOES-PROVISORIAS-v0.2.md:38`, `176-179`).

`politicas_provisorias: bool = True` no ViewModel (`presentation.py:116`).

---

## OBRIGATÓRIA — Paridade com entregável manual

Referência de produto: entregável manual Newport com 12 partes; escopo financeiro do piloto vs. fora de escopo em `docs/04-HANDOFF-IMPLEMENTACAO.md:17-19` e `docs/02-ESPECIFICACAO-IMPLEMENTACAO-SEGURA-v0.2.md:191`.

| Parte | Status | O que o sistema produz hoje | Evidência file:line | Gap vs entregável manual |
|-------|--------|-----------------------------|---------------------|--------------------------|
| 1. Projeção Financeira Cenário 1 | **parcial** | Comparativo financeiro + HTML por faixas/regime (1ª seção de regime / totais gerais) | `builder.py:231-301`; `html_renderer.py:242-257` | Não é PPTX; layout ≠ slides manuais; um “cenário” comercial ≠ `Cenario` do motor necessariamente |
| 2. Projeção Financeira Cenário 2 | **parcial** | Segunda (e demais) seções por regime de copart no mesmo HTML | `builder.py:31`, `_ORDEM_REGIMES`; `secoes_regime` | Mesmo gap; não há dois arquivos/slides nomeados “Cenário 1/2” |
| 3. Coparticipação | **parcial** | Particiona seções e exibe rótulo/meta (“Coparticipação: …”); **não** calcula % sobre atos | `builder.py:34-40`, `44-50`; `html_renderer.py:32-33` | Sem tabela de procedimentos/atos de copart |
| 4. Procedimentos Reembolsáveis | **inexistente** | Nada | Fora de escopo `docs/04:19` | Parte inteira ausente |
| 5. Reembolso | **inexistente** | Nada | `docs/02:191`; domínio `01-DOMINIO-NEGOCIO.md` (reembolso) | Parte inteira ausente |
| 6. Rede Básico | **só previsto em doc** | Nada no software | `docs/04:19` | Parte inteira ausente |
| 7. Rede Intermediário | **só previsto em doc** | Nada | idem | idem |
| 8. Rede Gerencial | **só previsto em doc** | Nada | idem | idem |
| 9. Rede Diretoria | **só previsto em doc** | Nada | idem | idem |
| 10. Regras Comerciais | **parcial** | Lista opcional `ressalvas` no HTML (“Ressalvas comerciais”) | `presentation.py:115`; `html_renderer.py:292-296`; request `models/snapshot.py:77` | Sem módulo de regras contratuais estruturadas |
| 11. Odonto | **inexistente** | Nada | `docs/04:19` | Parte inteira ausente |
| 12. Vida (seguro de vida) | **inexistente** | Nada de seguro de vida | `AGENTS.md:25`; `docs/04:19` | **Não confundir** com `Vida`/beneficiários do estudo de saúde (`newport_motor/models.py` `Vida`) |

---

## Registro de plano contratado (ação explícita)

Invariante: **nunca** automático após aprovação (`AGENTS.md:38`).

- Endpoint: `POST /api/estudos/{estudo_id}/plano-contratado` (`api/main.py:853-867`).
- Request: `RegistrarPlanoContratadoRequest` — `opcao_proposta_id`, vigências, metadados opcionais (`models/historico.py:131-139`).
- Persistência: `HistoricoRepository.registrar_plano_contratado` → `INSERT INTO planos_contratados` + auditoria `acao="registrar"` (`repository/historico.py:667-747`).
- Listagem: `GET .../planos-contratados` (`api/main.py:869-876`).

---

## Classificações de maturidade (apresentação / governança)

| Área | Classificação | Evidência |
|------|---------------|-----------|
| Snapshot candidato + hash SHA-256 | **implementado** | `services/snapshot.py`; `snapshot/hashing.py` |
| Aprovação local provisória (`auto_aprovacao`) | **implementado** (sem auth corporativa) | `models/snapshot.py:61-65`; `AGENTS.md:24-25` |
| HTML faixas / beneficiário | **implementado** | `builder.py`; `html_renderer.py` |
| Banner RASCUNHO INTERNO | **implementado** | `presentation.py:117-119` |
| PPTX / PDF de produção | **inexistente** | `AGENTS.md:24` |
| Delivery hospedada (URL autenticada) | **parcial** — ABC + `LocalFileDeliveryStorage`; docstring “não implementado” para contrato futuro remoto | `delivery_storage.py:1-33` (`url_acesso` retorna `None`) |
| Extração financeira PDF homologada | **sempre False** | `cotacao_pdf/maturidade.py` (`extracao_financeira_homologada`) |
| Motor em produção | **não aprovado** (piloto) | `RELATORIO-IMPLEMENTACAO.md` §10 |
| PolicySet como tabelas relacionais `PolicyEntry` | **inexistente** no SQLite; registry in-memory | `policy/registry.py:13-41`; caderno `docs/01:27-30` |

---

## ⚠️ NÃO VERIFICADO

1. Se a UI força scroll/abertura do payload completo antes do checkbox `confirmo_conteudo` (API só exige o boolean).
2. Paridade visual HTML × master PPTX em `Apresentacao-Template/` (não comparado pixel a pixel neste handoff).
3. Se `ressalvas` comerciais têm catálogo padronizado Newport ou são texto livre ad hoc na UI.
4. Comportamento de invalidação de entregáveis HTML já gerados quando o snapshot é superado (campo `invalidado` existe; fluxo UI completo não auditado ponta a ponta).
