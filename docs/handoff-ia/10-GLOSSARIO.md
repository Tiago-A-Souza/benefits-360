# 10 — Glossário

Fonte: commit `2a69d4c0bd12e4e8613cb8b085b1dac0c50cb805` — 2026-07-27

Documento operacional para IA sem acesso ao código. Termos de domínio e técnicos com identificador no código.

| Termo PT-BR | Definição | Identificador no código (class/field/enum) |
|-------------|-----------|-------------------------------------------|
| Estudo | Unidade de trabalho do comparativo (rascunho + meta + histórico) | `RascunhoEstudo`; `EstudoMeta`; `EstudoInput` |
| Rascunho | Estado editável JSON do estudo antes/durante o cálculo | `RascunhoEstudo` (`models/draft.py`); `RASCUNHO_VERSAO_ATUAL` |
| Renovação | Formato com plano atual + propostas | `FormatoEstudo.RENOVACAO`; rascunho `formato="renovacao"` |
| Seguro novo | Formato sem bloco “atual”; só propostas (jornada piloto limitada) | `FormatoEstudo.NOVO`; rascunho `formato="novo"` |
| Vida (beneficiário) | Pessoa incluída ou não no cálculo de saúde | `Vida` (`newport_motor/models.py`); `VidaRascunho` |
| Vida incluída | Vida com flag de inclusão no estudo | `Vida.incluida`; `EstudoInput.vidas_incluidas()` |
| Titular / dependente | Parentesco cadastral; não altera fórmula de prêmio | `ParentescoRascunho`; `PARENTESCO_MAP` (SISCOR) |
| Beneficiário (histórico) | Entidade longitudinal de pessoa entre ciclos | `Beneficiario`; `BeneficiarioParticipacao` |
| Beneficiário (apresentação) | Linha do HTML modo detalhado (com nome) | `BeneficiarioApresentacao`; modo `"beneficiario"` |
| Seguro de vida | Produto de seguro vida (fora do piloto) — **≠** vida/beneficiário | Sem tipo de domínio; só docs/`AGENTS.md` |
| Subgrupo | Fatia do plano atual (operadora/plano) agrupando vidas | `SubgrupoAtual`; `SubgrupoAtualRascunho` |
| Opção / proposta | Plano cotado candidato à troca | `OpcaoPlano`; `OpcaoPropostaRascunho` |
| Cenário | Conjunto de atribuições opção↔alvo no motor | `Cenario`; `CenarioRascunho`; `AtribuicaoPlano` |
| Atribuição | Liga subgrupo ou vida a uma opção | `AtribuicaoPlano`; `AlvoTipo` (`SUBGRUPO` / `VIDA`) |
| Regime de coparticipação | Classificação comercial do plano (particiona seções) | `RegimeCopart`; `RegimeCopartTipo` (`SEM`, `PARCIAL`, `PERCENTUAL`, `CUSTOMIZADA`); `RegimeCopartRascunho` |
| Coparticipação | Regime acima; **não** calcula % sobre procedimentos no motor | idem; rótulos em `presentation/builder._rotulo_regime` |
| Faixa etária ANS | Índice 0–9 de idade para tabela de preços | `TabelaPrecoFaixa.faixa`; `faixa_em`; `ROTULOS_FAIXA` |
| Faixa override | Campo opcional de faixa forçada; **não usado** no cálculo | `Vida.faixa_override` |
| Tabela de preços | Lista de valores por faixa (proposta ou atual) | `TabelaPrecoFaixa`; `OpcaoPlano.tabela` |
| Quantidade cotada | Qtd declarada na cotação por faixa; **não cruzada** com vidas no motor | `TabelaPrecoFaixa.quantidade_cotada` |
| Reajuste | Percentual anual do plano atual em basis points | `SubgrupoAtual.reajuste_bps`; `SubgrupoAtualRascunho.reajuste_bps` |
| Baseline vigente | Valor atual antes do reajuste (apresentação/comparação) | `BaselineEscolhido.VIGENTE` |
| Baseline reajustado | Valor atual × (1+reajuste); default de apresentação | `BaselineEscolhido.REAJUSTADO` |
| Precedência atual | Quem manda entre fatura e tabela atual | `PrecedenciaAtualVida` (`TABELA_ATUAL`, `VALOR_FATURA`) |
| Price basis | Se o valor já inclui IOF ou não | `PriceBasis` / `PriceBasisRascunho` (`INCLUI_IOF`, `EXCLUI_IOF`, `DESCONHECIDO`) |
| Tipo fiscal | Seguradora (IOF) vs operadora (sem IOF) | `TipoFiscal` (`SEGURADORA`, `OPERADORA`) |
| IOF | Imposto 2,38% = 238 bps sobre base elegível | `RateBasisPoints(238)`; `EffectivePolicy.iof_bps`; `apply_rate_bps` |
| MoneyCents | Dinheiro como inteiro em centavos (nunca float) | `MoneyCents` (`newport_motor/types.py` / `money.py`) |
| RateBasisPoints | Taxa em basis points (inteiro) | `RateBasisPoints` |
| Estratégia de arredondamento | Como aplicar IOF (piloto: por vida então soma) | `RoundingStrategy` (`POR_VIDA_ENTAO_SOMA`, …) |
| Proveniência | Origem/confirmação de um valor financeiro | `ProvenienciaCampo`; `OrigemValor`; `ComponenteFinanceiro` |
| Confirmado | Flag de aceite humano do valor extraído/informado | `ProvenienciaCampo.confirmado`; campos PDF `confirmado=False` no parser |
| EffectivePolicy | Pacote de regras efetivas passado ao motor | `EffectivePolicy` (`newport_motor/policy.py`) |
| PolicySet | Conjunto versionado de políticas (registry app) | `PolicySet`; `PolicySetRegistry`; `POLICY_SET_VERSAO_PADRAO` |
| Policy set versão | Identificador pinado no rascunho/snapshot | `RascunhoEstudo.policy_set_versao`; `SnapshotCalculo.policy_set_versao` |
| Compilador | Rascunho → `EstudoInput` + policy + erros | `draft_compiler.compile`; `COMPILER_VERSAO` |
| Motor | Função pura `calcular(estudo, policy)` | `newport_motor.engine.calcular` |
| Resultado do motor | Saída tipada com cenários, validações, totais | `MotorResult` / modelos em `newport_motor/result.py` |
| Comparativo | Adaptação amigável do resultado para UI | `ComparativoResponse`; `motor_result_para_comparativo` |
| Pendência | Item de bloqueio/alerta para a UI | `PendenciaItem`; `Validacao`; `SeveridadeValidacao` |
| Bloqueio B-02…B-08 | Validações bloqueantes de dado no motor | códigos em `newport_motor/validations.py` |
| B-01 | Aprovação humana — **camada de aplicação**, não motor | `AprovarSnapshotRequest`; docstring `engine.py` / `validations.py:1` |
| B-08 | Estudo sem vidas incluídas (bloqueante) | `validar_escopo_vidas` → código `"B-08"` |
| H-01 | Acima de `max_vidas_homologadas` (alerta) | código `"H-01"` em `validar_escopo_vidas` |
| Faixa homologada | Limite comercial configurável (default 29) | `EffectivePolicy.max_vidas_homologadas`; `PolicySet.max_vidas_homologadas` |
| Snapshot candidato | Congelamento hashável pré-aprovação | `SnapshotCalculo` com `estado="candidato"` |
| Snapshot aprovado | Snapshot liberado para apresentação | `estado="aprovado"`; `snapshot_aprovado_atual` |
| Snapshot superado | Snapshot antigo invalidado por novo ciclo | `estado="superado"` |
| Hash canônico | SHA-256 do payload sem timestamps | `CAMPOS_PAYLOAD_CANONICO`; `hash_snapshot_canonico` |
| Aprovação | Registro de revisor + flags | `AprovacaoSnapshot`; `AprovarSnapshotRequest` |
| Autoaprovação | Revisor = autor; exige justificativa | `auto_aprovacao`; `justificativa` |
| Confirmo conteúdo | Atestado UI/API de revisão integral | `confirmo_conteudo` |
| Confirmação do comparativo | Persistência que desbloqueia apresentação | `ConfirmacaoComparativoRascunho`; `comparativo_confirmacao` |
| Seleção de apresentação | Ordem das propostas no material | `SelecaoApresentacaoRascunho`; `propostas_apresentacao` |
| PresentationViewModel | Modelo neutro (centavos) para render | `PresentationViewModel` (`models/presentation.py`) |
| Modo faixas | HTML agregado por faixa etária (sem nomes) | `modo="faixas"` |
| Modo beneficiário | HTML linha a linha com nomes | `modo="beneficiario"` |
| Entregável | Artefato HTML gerado e persistido | `EntregavelApresentacao` |
| Renderer HTML | Gera string HTML autocontida | `render_html`; `RENDERER_VERSAO` |
| RASCUNHO INTERNO | Banner de políticas provisórias | `aviso_rascunho_interno`; DP-13 |
| Delivery storage | Abstração de armazenamento do arquivo | `DeliveryStorage`; `LocalFileDeliveryStorage` |
| Plano contratado | Registro histórico explícito do plano escolhido | `PlanoContratadoVersao`; `RegistrarPlanoContratadoRequest` |
| Posição cadastral | Versão da base de vidas importada | `PosicaoCadastralVersao` |
| Participação | Vínculo vida do estudo ↔ beneficiário histórico | `BeneficiarioParticipacao` |
| Cliente / ciclo | Agrupamento longitudinal de renovações | `Cliente`; `CicloRenovacao` |
| SISCOR | Planilha de posição cadastral/fatura | `ImportacaoSiscor*`; `siscor_importer` |
| Cotação PDF | Documento de proposta da operadora | `ExtracaoCotacaoCandidata`; `DocumentoCotacao*` |
| Família de template | Layout PDF reconhecido por âncoras | `FamiliaTemplate`; `FAMILIAS` |
| Maturidade de extração | Flags de estágio técnico (≠ homologação $) | `avaliar_maturidade`; `MaturidadeExtracaoResponse` |
| Homologação financeira | Aceite de que valores PDF estão corretos | `extracao_financeira_homologada` (sempre `False`) |
| Operadora (cadastro) | Nome comercial do plano | campos `operadora` em subgrupo/opção |
| Acomodação | Enfermaria/apartamento (metadado) | `acomodacao` em rascunho/apresentação |
| Modalidade | Compulsório vs adesão (metadado) | `modalidade` no rascunho |
| Ressalvas | Textos livres no HTML | `GerarApresentacaoRequest.ressalvas` |
| Rede credenciada | Hospitais/labs por perfil (fora do software) | inexistente no código |
| Reembolso | Regras/tabelas de reembolso (fora do software) | inexistente no código |
| Odonto | Produto odontológico (fora do software) | inexistente no código |
| PPTX | Entregável PowerPoint histórico Newport | não implementado (`AGENTS.md`) |
| Modo demo / real | Isolamento de dados `.data/` vs `.private/` | `NEWPORT_MODO`; `config/runtime.py` |
| Corpus privado | PDFs reais fora do Git para testes | marcador `pytest.mark.private_corpus` |
| Walking skeleton | Testes mínimos de API ponta a ponta | `test_api_walking_skeleton.py` |

---

## ⚠️ NÃO VERIFICADO

1. Sinônimos comerciais Newport usados em slides (ex.: nomes internos de “cenário 1/2”) vs. `Cenario`/`ScenarioSectionResult` — mapeamento verbal não padronizado no código.
2. Termos legacy do `ESPECIFICACAO-TECNICA` v0.1 (RF/RN/C.*) não listados aqui; preferir v0.2+ e este glossário.
