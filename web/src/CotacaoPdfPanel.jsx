import { useCallback, useEffect, useMemo, useState } from "react";
import {
  aplicarExtracaoCotacao,
  atualizarCampoExtracao,
  descartarExtracaoCotacao,
  importarCotacaoPdf,
  listarExtracoesCotacao,
  obterExtracaoCotacao,
  estimarPropostasExtracao,
  obterRascunho,
  obterResumoPlanoAtual,
  removerExtracaoCotacao,
  reverterDescarteExtracaoCotacao,
  salvarRascunho,
  selecionarOpcaoExtracao,
  carregarPdfCotacaoBlob,
  mensagemErroOperador,
  registrarDiagnostico,
} from "./api";
import {
  proximaExtracaoPendente,
  resumoSelecaoDocumento,
  rotuloDocumentoExtracao,
} from "./fluxo/cotacoesPendentes";
import FilePickerButton from "./components/FilePickerButton";
import {
  centavosParaReaisExibicao,
  centavosParaReaisTexto,
  classeDiffEstimativa,
  reaisTextoParaCentavos,
} from "./money";
import {
  ROTULOS_FAIXA,
  agruparOpcoes,
  contextoSiscorSimulacao,
  exigeSelecaoConsciente,
  filtrarOpcoes,
  formatarDataUpload,
  calcularEstimadoCentavos,
  formatarDiferencaReferencia,
  formatarEstimativaSiscor,
  abreviarAcomodacao,
  inferirAcomodacao,
  inferirRegiao,
  ocultaColunaCopart,
  mapaQuantidadesFaixa,
  nomePlanoExibicao,
  resumoFinanceiroOpcao,
  rotuloEstado,
  rotuloReconciliacao,
  rotuloRegime,
  resumirMotivosBloqueio,
  situacaoOpcao,
  textoConfirmacaoRemocao,
  textoRelatoRemocao,
  traduzirAlerta,
} from "./cotacaoPdf/utils";
import SelecaoPorGrupo from "./cotacaoPdf/SelecaoPorGrupo.jsx";
import {
  aposUltimoPdfDeveVoltarLista,
  avancoDeveRevelarSelecaoPorGrupo,
} from "./cotacaoPdf/selecaoPorGrupo.js";
import {
  executarUploadLote,
  formatarResumoUploads,
  primeiroUploadComSucesso,
} from "./cotacaoPdf/uploadLote";
import { ACOMODACOES, REGIMES_COPART, TIPOS_FISCAIS } from "./constants";

function rotuloTipoFiscal(texto) {
  if (texto === "operadora") return "Operadora";
  if (texto === "seguradora") return "Seguradora";
  return null;
}

function BadgeSituacao({ situacao }) {
  const cls =
    situacao.codigo === "pronto" || situacao.codigo === "adicionado"
      ? "badge--ok"
      : situacao.codigo === "revisao" ||
          situacao.codigo === "selecionado" ||
          situacao.codigo === "remover"
        ? "badge--alerta"
        : "badge--muted";
  return <span className={`badge ${cls}`}>{situacao.rotulo}</span>;
}

function opcaoJaNoComparativo(op, opcoesComparativo) {
  return opcoesComparativo.some((o) => o.extracao_opcao_id === op.id);
}

function estadoExibicaoOpcao(op, opcoesComparativo) {
  const adicionado = opcaoJaNoComparativo(op, opcoesComparativo);
  if (adicionado && op.selecionada_para_comparativo) {
    return { codigo: "adicionado", rotulo: "No comparativo" };
  }
  if (adicionado && !op.selecionada_para_comparativo) {
    return { codigo: "remover", rotulo: "Será removido" };
  }
  if (op.selecionada_para_comparativo) {
    return { codigo: "selecionado", rotulo: "Selecionado" };
  }
  return { codigo: "disponivel", rotulo: "Disponível" };
}

function metaGrupoComparativo(extracaoId, opcoes, extracoes, documentosCotacao) {
  const extracao = extracoes.find((e) => e.id === extracaoId);
  if (extracao) {
    const doc = extracao.documento;
    return {
      titulo: doc?.nome_arquivo || doc?.operadora_detectada || "Cotação PDF",
      estado: "ativo",
      extracao,
      doc,
    };
  }
  const docId = opcoes[0]?.documento_cotacao_id;
  const docRasc = (documentosCotacao || []).find((d) => d.id === docId);
  if (docRasc) {
    return {
      titulo: docRasc.operadora || "Cotação PDF",
      estado: "aplicado",
      extracao: null,
      doc: docRasc,
    };
  }
  return {
    titulo: "Cotação PDF",
    estado: "orfao",
    extracao: null,
    doc: null,
  };
}

function ComparativoResumo({
  opcoesComparativo,
  extracoes,
  documentosCotacao = [],
  onEditarSelecao,
  onRemoverPlano,
  onRemoverPdf,
  onRemoverGrupoOrfao,
  carregando,
}) {
  const opcoesPdf = opcoesComparativo.filter((o) => o.extracao_id);
  if (!opcoesPdf.length) return null;

  const porExtracao = new Map();
  for (const op of opcoesPdf) {
    const chave = op.extracao_id;
    if (!porExtracao.has(chave)) porExtracao.set(chave, []);
    porExtracao.get(chave).push(op);
  }

  return (
    <section className="comparativo-resumo" aria-label="Planos já no comparativo">
      <header className="comparativo-resumo-cabecalho">
        <h3>No comparativo</h3>
        <p className="muted">
          Use <strong>Editar seleção</strong> para marcar ou desmarcar planos desta cotação. Para
          alterar valores, revise a tabela na etapa seguinte. Para excluir tudo de uma vez, use{" "}
          <strong>Remover PDF</strong> ou os botões abaixo.
        </p>
      </header>
      {[...porExtracao.entries()].map(([extracaoId, opcoes]) => {
        const meta = metaGrupoComparativo(extracaoId, opcoes, extracoes, documentosCotacao);
        const { titulo, estado, extracao } = meta;
        const subtituloExtra =
          estado === "ativo"
            ? ""
            : estado === "aplicado"
              ? " · cotação aplicada ao comparativo — revisões preservadas (documento registrado no estudo)"
              : " · cotação PDF não está mais vinculada — remova estes planos ou reimporte o arquivo";
        return (
          <article key={extracaoId} className="comparativo-resumo-grupo cartao cartao--interno">
            <header className="comparativo-resumo-grupo-cabecalho">
              <div>
                <strong>{titulo}</strong>
                <p className="muted">
                  {opcoes.length} plano{opcoes.length !== 1 ? "s" : ""} no comparativo
                  {subtituloExtra}
                </p>
              </div>
              {estado === "ativo" ? (
                <div className="comparativo-resumo-grupo-acoes">
                  <button
                    type="button"
                    className="secundario btn-compacto"
                    disabled={carregando}
                    onClick={() => onEditarSelecao(extracao)}
                  >
                    Editar seleção
                  </button>
                  <button
                    type="button"
                    className="btn-remover"
                    disabled={carregando}
                    onClick={() => onRemoverPdf(extracao)}
                  >
                    Remover PDF
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  className="btn-remover"
                  disabled={carregando}
                  onClick={() => onRemoverGrupoOrfao(opcoes)}
                >
                  Remover planos
                </button>
              )}
            </header>
            <ul className="comparativo-resumo-lista">
              {opcoes.map((op) => (
                <li key={op.id} className="comparativo-resumo-item">
                  <span>{op.plano_nome || "Plano sem nome"}</span>
                  <button
                    type="button"
                    className="link comparativo-resumo-remover"
                    disabled={carregando}
                    onClick={() => onRemoverPlano(op)}
                    title="Remover só este plano do comparativo"
                  >
                    Remover
                  </button>
                </li>
              ))}
            </ul>
          </article>
        );
      })}
    </section>
  );
}

function UploadZona({ carregando, dragAtivo, setDragAtivo, compacto, onUpload }) {
  return (
    <div
      className={[
        compacto ? "upload-area" : "upload-zona",
        !compacto && dragAtivo ? "upload-zona--ativa" : "",
        compacto && dragAtivo ? "upload-area--ativa" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      onDragOver={(e) => {
        e.preventDefault();
        setDragAtivo(true);
      }}
      onDragLeave={() => setDragAtivo(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragAtivo(false);
        const pdfs = Array.from(e.dataTransfer.files || []).filter(
          (f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf")
        );
        onUpload(pdfs);
      }}
    >
      {compacto ? (
        <>
          <div className="upload-area-esq">
            <div className="upload-icon" aria-hidden="true">
              PDF
            </div>
            <div>
              <h3>Adicionar outra cotação</h3>
              <p className="muted">
                Arraste um ou mais PDFs de operadoras para ampliar o catálogo.
              </p>
            </div>
          </div>
          <FilePickerButton
            accept="application/pdf"
            multiple
            disabled={carregando}
            onFiles={onUpload}
          >
            {carregando ? "Processando PDF…" : "Escolher PDF"}
          </FilePickerButton>
        </>
      ) : (
        <div className="upload-zona-conteudo">
          <span className="upload-zona-icone" aria-hidden="true">
            ↑
          </span>
          <div className="upload-zona-texto">
            <FilePickerButton
              accept="application/pdf"
              multiple
              disabled={carregando}
              onFiles={onUpload}
            >
              {carregando ? "Processando PDF…" : "Adicionar cotação em PDF"}
            </FilePickerButton>
            <p className="upload-dica muted">
              Arraste um ou mais PDFs ou use o botão acima.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function PainelAuditoria({ op, onSalvarCampo }) {
  const [aberto, setAberto] = useState(false);
  if (!aberto) {
    return (
      <button type="button" className="link auditoria-toggle" onClick={() => setAberto(true)}>
        Evidências e auditoria técnica
      </button>
    );
  }
  return (
    <details className="auditoria-panel" open>
      <summary onClick={() => setAberto(false)}>Evidências e auditoria técnica</summary>
      <p className="muted">ID da opção: {op.id}</p>
      <ul className="auditoria-lista">
        {[op.plano_nome, op.regime_copart, op.premio_saude, op.iof, op.total_recorrente]
          .filter(Boolean)
          .map((campo) => (
            <li key={campo.id}>
              <strong>{campo.rotulo}</strong>
              {campo.evidencia?.pagina != null && <span> — pág. {campo.evidencia.pagina}</span>}
              {campo.evidencia?.coordenadas && (
                <span className="muted"> [{campo.evidencia.coordenadas}]</span>
              )}
              {campo.evidencia?.trecho && (
                <p className="muted evidencia">{campo.evidencia.trecho.slice(0, 200)}</p>
              )}
              {campo.parser_versao && (
                <p className="muted">Parser: {campo.parser_versao}</p>
              )}
            </li>
          ))}
        {op.tabela?.map((fx) => (
          <li key={fx.faixa}>
            Faixa {fx.faixa}: {fx.valor.evidencia?.trecho?.slice(0, 80) || "—"}
          </li>
        ))}
      </ul>
    </details>
  );
}

export function TabelaSelecaoCompacta({
  opcoes,
  templateId,
  quantidades,
  siscorCtx,
  estimativasMotor,
  referenciaCentavos,
  selecionados,
  opcoesComparativo,
  onToggle,
}) {
  const [maisFiltros, setMaisFiltros] = useState(false);
  const filtradas = useMemo(
    () => filtrarOpcoes(opcoes, selecionados.filtros),
    [opcoes, selecionados.filtros]
  );
  const grupos = useMemo(
    () => agruparOpcoes(filtradas, templateId),
    [filtradas, templateId]
  );

  return (
    <>
      <div className="filtros-compactos">
        <input
          type="search"
          className="filtro-busca"
          placeholder="Buscar plano…"
          value={selecionados.filtros.busca}
          onChange={(e) => selecionados.setFiltro("busca", e.target.value)}
        />
        <select
          value={selecionados.filtros.acomodacao}
          onChange={(e) => selecionados.setFiltro("acomodacao", e.target.value)}
        >
          <option value="">Acomodação</option>
          <option value="Enfermaria">Enfermaria</option>
          <option value="Apartamento">Apartamento</option>
        </select>
        <select
          value={selecionados.filtros.regime}
          onChange={(e) => selecionados.setFiltro("regime", e.target.value)}
        >
          <option value="">Coparticipação</option>
          <option value="Sem coparticipação">Sem coparticipação</option>
          <option value="Coparticipação 30%">Coparticipação 30%</option>
        </select>
        <button
          type="button"
          className="secundario btn-compacto"
          onClick={() => setMaisFiltros((v) => !v)}
        >
          {maisFiltros ? "Menos filtros" : "Mais filtros"}
        </button>
        {maisFiltros && (
          <select
            value={selecionados.filtros.regiao}
            onChange={(e) => selecionados.setFiltro("regiao", e.target.value)}
          >
            <option value="">Região (todas)</option>
            <option value="Brasil">Brasil</option>
            <option value="Rio">Rio</option>
            <option value="Nacional">Nacional</option>
          </select>
        )}
      </div>

      {grupos.map(({ titulo, opcoes: opsGrupo }) => {
        const semCopart = ocultaColunaCopart(titulo);
        const gradeCls = `linha-plano-selecao${semCopart ? "" : " linha-plano-selecao--com-copart"}`;
        return (
        <div key={titulo || "geral"} className="grupo-planos">
          {titulo && <h4 className="grupo-planos-titulo">{titulo}</h4>}
          <div className="lista-planos-selecao">
            <div
              className={`${gradeCls} linha-plano-selecao--cabecalho`}
              aria-hidden="true"
            >
              <span className="linha-plano-check" />
              <span>Plano</span>
              <span>Acom.</span>
              {!semCopart && <span>Copart.</span>}
              <span className="linha-plano-meta linha-plano-meta--valor">Mensal est.</span>
              <span className="linha-plano-meta linha-plano-meta--valor">Δ R$</span>
              <span className="linha-plano-status">Status</span>
            </div>
            {opsGrupo.map((op) => {
              const estado = estadoExibicaoOpcao(op, opcoesComparativo);
              const est = formatarEstimativaSiscor(
                op,
                quantidades,
                siscorCtx,
                estimativasMotor?.[op.id]
              );
              const estimado =
                estimativasMotor?.[op.id] ?? calcularEstimadoCentavos(op, quantidades);
              const diff = formatarDiferencaReferencia(estimado, referenciaCentavos);
              const estimativaTitulo = est.destacarGrupo
                ? "Estimativa indisponível até selecionar o grupo de beneficiários"
                : undefined;
              const estimativaTexto = est.destacarGrupo ? "Selecione o grupo" : est.texto;
              const acomodacaoCompleta = inferirAcomodacao(op);
              return (
                <div
                  key={op.id}
                  role="checkbox"
                  aria-checked={Boolean(op.selecionada_para_comparativo)}
                  tabIndex={0}
                  className={`${gradeCls} linha-plano-selecao--clicavel${op.selecionada_para_comparativo ? " linha-plano-selecao--marcada" : ""}${estado.codigo === "adicionado" ? " linha-plano-selecao--adicionada" : ""}${estado.codigo === "remover" ? " linha-plano-selecao--remover" : ""}`}
                  onClick={() => onToggle(op.id, !op.selecionada_para_comparativo)}
                  onKeyDown={(e) => {
                    if (e.key === " " || e.key === "Enter") {
                      e.preventDefault();
                      onToggle(op.id, !op.selecionada_para_comparativo);
                    }
                  }}
                >
                  <span className="linha-plano-check" aria-hidden="true">
                    <input
                      type="checkbox"
                      readOnly
                      tabIndex={-1}
                      checked={Boolean(op.selecionada_para_comparativo)}
                    />
                  </span>
                  <span className="linha-plano-nome" title={nomePlanoExibicao(op)}>
                    {nomePlanoExibicao(op)}
                  </span>
                  <span className="linha-plano-meta linha-plano-meta--acom" title={acomodacaoCompleta}>
                    {abreviarAcomodacao(acomodacaoCompleta)}
                  </span>
                  {!semCopart && (
                    <span className="linha-plano-meta linha-plano-meta--copart">{rotuloRegime(op)}</span>
                  )}
                  <span
                    className={`linha-plano-meta linha-plano-meta--valor${est.destacarGrupo ? " estimativa-indisponivel" : ""}`}
                    title={estimativaTitulo}
                  >
                    {estimativaTexto}
                  </span>
                  <span
                    className={`linha-plano-meta linha-plano-meta--valor${
                      diff.indisponivel ? "" : ` ${classeDiffEstimativa(diff.diffCentavos) || ""}`
                    }`}
                    title={diff.indisponivel ? undefined : diff.rotuloSemantica}
                  >
                    {diff.indisponivel ? (
                      "—"
                    ) : (
                      <>
                        {diff.textoDiff}
                        {diff.rotuloSemantica && (
                          <span className="linha-plano-diff-hint" title={diff.rotuloSemantica}>
                            {" "}
                            {diff.semantica === "economia" ? "↓" : diff.semantica === "acrescimo" ? "↑" : "•"}
                          </span>
                        )}
                      </>
                    )}
                  </span>
                  <span className="linha-plano-status">
                    <BadgeSituacao situacao={estado} />
                  </span>
                </div>
              );
            })}
          </div>
        </div>
        );
      })}
      {filtradas.length === 0 && (
        <p className="muted">Nenhum plano corresponde aos filtros.</p>
      )}
    </>
  );
}

function RevisaoPlano({ op, quantidades, siscorCtx, estimativaMotor, validadeDocumento, onSalvarCampo }) {
  const faixasPorIndice = Object.fromEntries((op.tabela || []).map((fx) => [fx.faixa, fx]));
  let subtotalBruto = 0;
  const sit = situacaoOpcao(op);
  const temPop = quantidades && Object.values(quantidades).some((q) => q > 0);
  const estimativaIndisponivel = siscorCtx?.exigeEscolha || !temPop;
  const subtotal =
    estimativaMotor != null ? estimativaMotor : subtotalBruto;
  const validadeAtual = op.validade_oficial?.data || validadeDocumento || "";
  const validadePendente = !validadeAtual;
  const tipoFiscalAtual = op.tipo_fiscal?.texto || "";
  const tipoFiscalPendente = !tipoFiscalAtual;
  const regimeAtual = op.regime_copart?.texto || "";
  const regimePendente = !regimeAtual;
  const acomodacaoAtual = op.acomodacao?.texto || "";
  const acomodacaoPendente = !acomodacaoAtual;
  const rotuloAcomodacaoAtual =
    ACOMODACOES.find((a) => a.value === acomodacaoAtual)?.label ||
    (acomodacaoAtual ? acomodacaoAtual : null);

  return (
    <div className="cartao cartao--fluxo revisao-plano">
      <div className="revisao-plano-cabecalho">
        <span className="revisao-plano-rotulo">Plano selecionado</span>
        <strong className="revisao-plano-nome">{nomePlanoExibicao(op)}</strong>
      </div>

      <dl className="revisao-plano-resumo">
        <div>
          <dt>Operadora</dt>
          <dd>{op.operadora?.texto || "—"}</dd>
        </div>
        <div>
          <dt>Acomodação</dt>
          <dd>{rotuloAcomodacaoAtual || "A declarar"}</dd>
        </div>
        <div>
          <dt>Tipo fiscal</dt>
          <dd>{rotuloTipoFiscal(tipoFiscalAtual) || "A declarar"}</dd>
        </div>
        <div>
          <dt>Coparticipação</dt>
          <dd>{regimePendente ? "A declarar" : rotuloRegime(op)}</dd>
        </div>
        <div>
          <dt>Validade</dt>
          <dd>{validadeAtual || "—"}</dd>
        </div>
      </dl>

      {tipoFiscalPendente && (
        <label className="campo-revisao">
          <span>Tipo fiscal</span>
          <select
            defaultValue=""
            onChange={(e) => {
              if (op.tipo_fiscal?.id && e.target.value) {
                onSalvarCampo(op.tipo_fiscal.id, {
                  texto: e.target.value,
                  confirmado: true,
                });
              }
            }}
          >
            <option value="">Selecione…</option>
            {TIPOS_FISCAIS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
          <span className="muted revisao-plano-dica">
            O IOF de 2,38% só se aplica a seguradora.
          </span>
        </label>
      )}

      {acomodacaoPendente && (
        <label className="campo-revisao">
          <span>Acomodação</span>
          <select
            defaultValue=""
            onChange={(e) => {
              if (op.acomodacao?.id && e.target.value) {
                onSalvarCampo(op.acomodacao.id, {
                  texto: e.target.value,
                  confirmado: true,
                });
              }
            }}
          >
            <option value="">Selecione…</option>
            {ACOMODACOES.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </select>
          <span className="muted revisao-plano-dica">
            Não extraída do PDF — declare antes de adicionar ao comparativo.
          </span>
        </label>
      )}

      {regimePendente && (
        <label className="campo-revisao">
          <span>Regime de coparticipação</span>
          <select
            defaultValue=""
            onChange={(e) => {
              if (op.regime_copart?.id && e.target.value) {
                onSalvarCampo(op.regime_copart.id, {
                  texto: e.target.value,
                  confirmado: true,
                });
              }
            }}
          >
            <option value="">Selecione…</option>
            {REGIMES_COPART.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
          <span className="muted revisao-plano-dica">
            Não inferido automaticamente — declare antes de adicionar ao comparativo.
          </span>
        </label>
      )}

      {validadePendente && (
        <p className="muted revisao-plano-dica">
          Informe a validade no bloco «Dados do documento» acima — vale para todos os planos
          selecionados desta cotação.
        </p>
      )}

      {!validadePendente && !tipoFiscalPendente && !acomodacaoPendente && !regimePendente && (
        <p className="muted revisao-plano-dica">
          Dados extraídos do PDF. Use <strong>Corrigir</strong> na tabela apenas se algum valor estiver errado.
        </p>
      )}

      <div className="revisao-plano-tabela-wrap">
        <span className="revisao-plano-secao-rotulo">Tabela tarifária (10 faixas)</span>
        <table className="tabela-conferencia tabela-faixas">
          <thead>
            <tr>
              <th className="col-faixa">Faixa</th>
              <th className="col-num">Unitário</th>
              <th className="col-num">Qtd</th>
              <th className="col-num">Subtotal</th>
            </tr>
          </thead>
          <tbody>
            {ROTULOS_FAIXA.map((rotulo, idx) => {
              const fx = faixasPorIndice[idx];
              const qtd = quantidades?.[idx] ?? fx?.quantidade?.inteiro ?? 0;
              const val = fx?.valor?.centavos;
              const linha = val != null && qtd > 0 ? val * qtd : null;
              if (linha) subtotalBruto += linha;
              return (
                <tr
                  key={idx}
                  className={qtd > 0 ? "tabela-faixas-linha--ativa" : "tabela-faixas-linha--vazia"}
                >
                  <td className="col-faixa">{rotulo}</td>
                  <td className="col-num">
                    <div className="tabela-faixas-valor-linha">
                      <span>{val != null ? centavosParaReaisExibicao(val) : "—"}</span>
                      <span className="tabela-faixas-acoes">
                        {fx?.valor && (
                          <button
                            type="button"
                            className="tabela-faixas-acao"
                            onClick={() => {
                              const v = prompt(
                                "Corrigir valor (R$):",
                                val != null ? centavosParaReaisTexto(val) : ""
                              );
                              if (v == null) return;
                              const conv = reaisTextoParaCentavos(v);
                              if (conv.ok) {
                                onSalvarCampo(fx.valor.id, {
                                  centavos: conv.centavos,
                                  confirmado: true,
                                });
                              }
                            }}
                          >
                            Corrigir
                          </button>
                        )}
                      </span>
                    </div>
                  </td>
                  <td className="col-num">{qtd > 0 ? qtd : "—"}</td>
                  <td className="col-num">
                    {linha != null ? centavosParaReaisExibicao(linha) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="revisao-plano-rodape">
        <dl className="revisao-plano-totais">
          <div className="revisao-plano-total--destaque">
            <dt>Subtotal est.</dt>
            <dd>
              {estimativaIndisponivel
                ? siscorCtx?.exigeEscolha
                  ? "Selecione o grupo"
                  : "—"
                : estimativaMotor != null
                  ? centavosParaReaisExibicao(subtotal)
                  : "…"}
            </dd>
          </div>
          <div>
            <dt>Prêmio</dt>
            <dd>
              {op.premio_saude?.centavos != null
                ? centavosParaReaisExibicao(op.premio_saude.centavos)
                : "—"}
            </dd>
          </div>
          <div>
            <dt>IOF</dt>
            <dd>{op.iof?.centavos != null ? centavosParaReaisExibicao(op.iof.centavos) : "—"}</dd>
          </div>
          <div>
            <dt>Total PDF</dt>
            <dd>{resumoFinanceiroOpcao(op)}</dd>
          </div>
        </dl>

        <div className="revisao-plano-status">
          <div className="revisao-plano-status-texto">
            <p
              className={`revisao-plano-reconciliacao${
                op.reconciliacao?.status === "reconciliado"
                  ? " revisao-plano-reconciliacao--ok"
                  : op.reconciliacao?.status === "nao_conferivel"
                    ? " revisao-plano-reconciliacao--info"
                    : op.reconciliacao?.status === "divergente"
                      ? " revisao-plano-reconciliacao--erro"
                      : ""
              }`}
            >
              {rotuloReconciliacao(op)}
            </p>
            {op.reconciliacao?.status === "divergente" && op.reconciliacao?.divergencias?.length > 0 && (
              <ul className="revisao-plano-divergencias">
                {(op.reconciliacao.divergencias || []).map((d, i) => (
                  <li key={i}>{d.descricao}</li>
                ))}
              </ul>
            )}
            {sit.bloqueiaConfirmacao && (
              <p className="revisao-plano-alerta">{sit.motivos.join(" · ")}</p>
            )}
          </div>
        </div>
      </div>

      <div className="revisao-plano-auditoria">
        <PainelAuditoria op={op} onSalvarCampo={onSalvarCampo} />
      </div>
    </div>
  );
}

function VisualizadorPdfInline({ estudoId, documentoId, titulo, onFechar }) {
  const [src, setSrc] = useState(null);
  const [erro, setErro] = useState(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    if (!documentoId) return undefined;
    let ativo = true;
    let blobUrl = null;

    setCarregando(true);
    setErro(null);
    setSrc((anterior) => {
      if (anterior) URL.revokeObjectURL(anterior);
      return null;
    });

    carregarPdfCotacaoBlob(estudoId, documentoId)
      .then((url) => {
        if (!ativo) {
          URL.revokeObjectURL(url);
          return;
        }
        blobUrl = url;
        setSrc(url);
      })
      .catch((e) => {
        if (ativo) setErro(e.message || "Não foi possível carregar o PDF.");
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });

    return () => {
      ativo = false;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [estudoId, documentoId]);

  function abrirNovaAba() {
    if (!src) return;
    window.open(src, "_blank", "noopener,noreferrer");
  }

  if (!documentoId) return null;
  return (
    <aside className="pdf-inline-panel" aria-label="Visualização do PDF">
      <header className="pdf-inline-cabecalho">
        <div>
          <span className="pdf-inline-rotulo">Documento original</span>
          <strong className="pdf-inline-titulo">{titulo || "Cotação PDF"}</strong>
        </div>
        <div className="pdf-inline-acoes">
          <button
            type="button"
            className="link btn-compacto"
            disabled={!src || carregando}
            onClick={abrirNovaAba}
          >
            Abrir em nova aba
          </button>
          <button type="button" className="secundario btn-compacto" onClick={onFechar}>
            Ocultar PDF
          </button>
        </div>
      </header>
      {carregando && <p className="pdf-inline-estado muted">Carregando PDF…</p>}
      {erro && <p className="pdf-inline-estado erro">{erro}</p>}
      {src && !erro && (
        <iframe
          className="pdf-inline-frame"
          title={`PDF: ${titulo || "cotação"}`}
          src={`${src}#toolbar=1&navpanes=0`}
        />
      )}
    </aside>
  );
}

export default function CotacaoPdfPanel({
  estudoId,
  onAplicado,
  onPreencherManualmente,
  onRegistrarAvanco,
  exigeSelecaoPorGrupo = false,
  cestaGlobal = [],
  setCestaGlobal,
  opcoesComparativo = [],
  documentosCotacao = [],
}) {
  const [extracoes, setExtracoes] = useState([]);
  const [fase, setFase] = useState("lista");
  const [extracaoId, setExtracaoId] = useState(null);
  const [detalhe, setDetalhe] = useState(null);
  const [resumoSiscor, setResumoSiscor] = useState(null);
  const [subgrupoSimulacao, setSubgrupoSimulacao] = useState("");
  const [filtros, setFiltros] = useState({
    busca: "",
    acomodacao: "",
    regime: "",
    regiao: "",
  });
  const [erro, setErro] = useState(null);
  const [msg, setMsg] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [bloqueios, setBloqueios] = useState([]);
  const [relatoRemocao, setRelatoRemocao] = useState(null);
  const [dragAtivo, setDragAtivo] = useState(false);
  const [pdfInlineDocumentoId, setPdfInlineDocumentoId] = useState(null);
  const [carregandoDetalhe, setCarregandoDetalhe] = useState(false);
  const [alternandoOpcao, setAlternandoOpcao] = useState(null);
  const [estimativasMotor, setEstimativasMotor] = useState({});
  const [descarteExId, setDescarteExId] = useState(null);
  const [motivoDescarte, setMotivoDescarte] = useState("");
  const [proximoPendenteId, setProximoPendenteId] = useState(null);

  const recarregar = useCallback(() => {
    listarExtracoesCotacao(estudoId)
      .then((r) => {
        const lista = r.extracoes || [];
        lista.sort((a, b) => new Date(b.criado_em) - new Date(a.criado_em));
        setExtracoes(lista);
      })
      .catch(() => setExtracoes([]));
  }, [estudoId]);

  const recarregarDetalhe = useCallback(async () => {
    if (!extracaoId) return;
    const d = await obterExtracaoCotacao(estudoId, extracaoId);
    setDetalhe(d);
  }, [estudoId, extracaoId]);

  useEffect(() => {
    if (!estudoId) return;
    recarregar();
    obterResumoPlanoAtual(estudoId)
      .then(setResumoSiscor)
      .catch(() => setResumoSiscor(null));
  }, [estudoId, recarregar]);

  useEffect(() => {
    if (!extracaoId) {
      setDetalhe(null);
      return;
    }
    obterExtracaoCotacao(estudoId, extracaoId)
      .then(setDetalhe)
      .catch((e) => setErro(e.message));
  }, [estudoId, extracaoId]);

  useEffect(() => {
    if (resumoSiscor?.planos?.length === 1) {
      setSubgrupoSimulacao(resumoSiscor.planos[0].subgrupo_id);
    }
  }, [resumoSiscor]);

  const planoSiscor = useMemo(
    () => resumoSiscor?.planos?.find((p) => p.subgrupo_id === subgrupoSimulacao),
    [resumoSiscor, subgrupoSimulacao]
  );
  const quantidades = useMemo(() => mapaQuantidadesFaixa(planoSiscor), [planoSiscor]);
  const siscorCtx = useMemo(
    () => contextoSiscorSimulacao(resumoSiscor, subgrupoSimulacao),
    [resumoSiscor, subgrupoSimulacao]
  );

  useEffect(() => {
    if (!extracaoId || siscorCtx?.exigeEscolha) {
      setEstimativasMotor({});
      return;
    }
    const temPop = quantidades && Object.values(quantidades).some((q) => q > 0);
    if (!temPop) {
      setEstimativasMotor({});
      return;
    }
    estimarPropostasExtracao(estudoId, extracaoId, quantidades)
      .then((r) => setEstimativasMotor(r.totais || {}))
      .catch(() => setEstimativasMotor({}));
  }, [estudoId, extracaoId, quantidades, siscorCtx?.exigeEscolha]);

  const opcoesAtivas = useMemo(
    () => detalhe?.opcoes?.filter((o) => !o.excluida) || [],
    [detalhe]
  );
  const selecionadas = useMemo(
    () => opcoesAtivas.filter((o) => o.selecionada_para_comparativo),
    [opcoesAtivas]
  );
  const noComparativoDestaExtracao = useMemo(
    () => opcoesComparativo.filter((o) => o.extracao_id === extracaoId),
    [opcoesComparativo, extracaoId]
  );

  function sincronizarCesta(idExtracao, opcoes, doc) {
    if (!setCestaGlobal) return;
    setCestaGlobal((prev) => {
      const restantes = prev.filter((x) => x.extracaoId !== idExtracao);
      const novos = opcoes
        .filter((o) => o.selecionada_para_comparativo)
        .map((o) => ({
          extracaoId: idExtracao,
          opcaoId: o.id,
          nome: nomePlanoExibicao(o),
          operadora: doc?.operadora_detectada || o.operadora?.texto || "",
        }));
      return [...restantes, ...novos];
    });
  }

  function togglePdfInline(documentoId) {
    if (!documentoId) return;
    setPdfInlineDocumentoId((atual) => (atual === documentoId ? null : documentoId));
  }

  function abrirDocumento(id) {
    setExtracaoId(id);
    setFase("selecao");
    setFiltros({ busca: "", acomodacao: "", regime: "", regiao: "" });
    setErro(null);
    setMsg(null);
    setBloqueios([]);
    setPdfInlineDocumentoId(null);
    setCarregandoDetalhe(true);
    obterExtracaoCotacao(estudoId, id)
      .then((d) => {
        setDetalhe(d);
        const ativas = (d.opcoes || []).filter((o) => !o.excluida);
        sincronizarCesta(id, ativas, d.documento);
      })
      .catch((err) => {
        setErro(err.message || "Não foi possível abrir a cotação.");
        setFase("lista");
        setExtracaoId(null);
        setDetalhe(null);
      })
      .finally(() => setCarregandoDetalhe(false));
  }

  async function handleEditarSelecao(ex) {
    setCarregando(true);
    setErro(null);
    setMsg(null);
    try {
      const d = await obterExtracaoCotacao(estudoId, ex.id);
      const idsNoComparativo = new Set(
        opcoesComparativo
          .filter((o) => o.extracao_id === ex.id && o.extracao_opcao_id)
          .map((o) => o.extracao_opcao_id)
      );
      for (const op of (d.opcoes || []).filter((o) => !o.excluida)) {
        const deveriaEstar = idsNoComparativo.has(op.id);
        if (Boolean(op.selecionada_para_comparativo) !== deveriaEstar) {
          await selecionarOpcaoExtracao(estudoId, ex.id, op.id, deveriaEstar);
        }
      }
      abrirDocumento(ex.id);
      setMsg("Marque ou desmarque os planos e clique em Revisar para atualizar o comparativo.");
    } catch (err) {
      setErro(err.message || "Não foi possível abrir a edição da seleção.");
    } finally {
      setCarregando(false);
    }
  }

  function voltarLista() {
    setFase("lista");
    setExtracaoId(null);
    setDetalhe(null);
    setPdfInlineDocumentoId(null);
  }

  useEffect(() => {
    if (!onRegistrarAvanco || !exigeSelecaoPorGrupo) return undefined;
    return onRegistrarAvanco(async () => {
      if (avancoDeveRevelarSelecaoPorGrupo(exigeSelecaoPorGrupo, fase)) {
        voltarLista();
        return false;
      }
      return true;
    });
  }, [onRegistrarAvanco, exigeSelecaoPorGrupo, fase]);

  async function processarUploads(files) {
    if (!files.length) return;
    setCarregando(true);
    setErro(null);
    let primeiroSucessoId = null;
    try {
      const resultados = await executarUploadLote(files, (file) =>
        importarCotacaoPdf(estudoId, file)
      );
      primeiroSucessoId = primeiroUploadComSucesso(resultados);
      const resumo = formatarResumoUploads(resultados);
      setMsg(resumo);
      const falhas = resultados.filter((r) => !r.ok);
      if (falhas.length) {
        setErro(formatarResumoUploads(falhas));
      }
    } catch (err) {
      setErro(err.message || "Falha ao importar cotações.");
    } finally {
      recarregar();
      onAplicado?.();
      setCarregando(false);
      if (primeiroSucessoId) abrirDocumento(primeiroSucessoId);
    }
  }

  async function handleRemoverExtracao(ex) {
    const aplicados = opcoesComparativo.filter((o) => o.extracao_id === ex.id);
    let texto = `Remover o PDF «${ex.documento?.nome_arquivo || "cotação"}»?`;
    if (aplicados.length) {
      texto = `Este PDF gerou ${aplicados.length} plano(s) no comparativo. Remover o PDF também excluirá esses planos. Deseja continuar?`;
    }
    if (!window.confirm(texto)) return;
    setCarregando(true);
    setErro(null);
    try {
      const res = await removerExtracaoCotacao(estudoId, ex.id);
      if (res.aprovacao_invalidada) {
        setMsg("Cotação removida. A aprovação anterior foi invalidada — revise o estudo.");
      } else {
        setMsg(res.mensagem || "PDF removido do estudo.");
      }
      if (extracaoId === ex.id) voltarLista();
      else if (ex.documento?.id === pdfInlineDocumentoId) setPdfInlineDocumentoId(null);
      if (setCestaGlobal) {
        setCestaGlobal((prev) => prev.filter((x) => x.extracaoId !== ex.id));
      }
      recarregar();
      onAplicado?.();
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
    }
  }

  function abrirDescarte(ex) {
    setDescarteExId(ex.id);
    setMotivoDescarte("");
    setErro(null);
    setMsg(null);
    setFase("lista");
    setExtracaoId(null);
    setDetalhe(null);
    setPdfInlineDocumentoId(null);
  }

  async function confirmarDescarte() {
    const motivo = motivoDescarte.trim();
    if (!motivo) {
      setErro("Informe o motivo para não usar esta cotação.");
      return;
    }
    if (!descarteExId) return;
    setCarregando(true);
    setErro(null);
    try {
      const res = await descartarExtracaoCotacao(estudoId, descarteExId, motivo);
      setMsg(res.mensagem || "Cotação marcada como não utilizada.");
      setDescarteExId(null);
      setMotivoDescarte("");
      if (extracaoId === descarteExId) voltarLista();
      if (setCestaGlobal) {
        setCestaGlobal((prev) => prev.filter((x) => x.extracaoId !== descarteExId));
      }
      recarregar();
      onAplicado?.();
    } catch (err) {
      setErro(mensagemErroOperador(err, "Não foi possível descartar a cotação."));
    } finally {
      setCarregando(false);
    }
  }

  async function handleReverterDescarte(ex) {
    setCarregando(true);
    setErro(null);
    try {
      await reverterDescarteExtracaoCotacao(estudoId, ex.id);
      setMsg("Descarte revertido — você pode escolher planos desta cotação.");
      recarregar();
      onAplicado?.();
    } catch (err) {
      setErro(mensagemErroOperador(err, "Não foi possível reverter o descarte."));
    } finally {
      setCarregando(false);
    }
  }

  async function handleRemoverPlanoComparativo(opcao) {
    if (
      !window.confirm(
        `Remover «${opcao.plano_nome || "este plano"}» do comparativo? O PDF permanece importado.`
      )
    ) {
      return;
    }
    setCarregando(true);
    setErro(null);
    try {
      const rascunho = await obterRascunho(estudoId);
      const copia = structuredClone(rascunho);
      copia.opcoes_proposta = copia.opcoes_proposta.filter((o) => o.id !== opcao.id);
      for (const cenario of copia.cenarios) {
        cenario.atribuicoes = cenario.atribuicoes.filter((a) => a.opcao_plano_id !== opcao.id);
      }
      await salvarRascunho(estudoId, copia);
      setMsg(`Plano «${opcao.plano_nome || "sem nome"}» removido do comparativo.`);
      onAplicado?.();
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
    }
  }

  async function handleRemoverGrupoOrfao(opcoes) {
    if (
      !window.confirm(
        `Remover ${opcoes.length} plano(s) do comparativo? O PDF original não está mais listado.`
      )
    ) {
      return;
    }
    setCarregando(true);
    setErro(null);
    try {
      const ids = new Set(opcoes.map((o) => o.id));
      const rascunho = await obterRascunho(estudoId);
      const copia = structuredClone(rascunho);
      copia.opcoes_proposta = copia.opcoes_proposta.filter((o) => !ids.has(o.id));
      for (const cenario of copia.cenarios) {
        cenario.atribuicoes = cenario.atribuicoes.filter((a) => !ids.has(a.opcao_plano_id));
      }
      await salvarRascunho(estudoId, copia);
      setMsg(`${opcoes.length} plano(s) removido(s) do comparativo.`);
      onAplicado?.();
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
    }
  }

  async function salvarCampo(campoId, patch, { recarregar = true } = {}) {
    if (!extracaoId || !campoId) return;
    await atualizarCampoExtracao(estudoId, extracaoId, campoId, patch);
    if (recarregar) await recarregarDetalhe();
  }

  async function handleToggle(opcaoId, selecionada) {
    if (!extracaoId || alternandoOpcao) return;
    setAlternandoOpcao(opcaoId);
    setErro(null);
    try {
      await selecionarOpcaoExtracao(estudoId, extracaoId, opcaoId, selecionada);
      const d = await obterExtracaoCotacao(estudoId, extracaoId);
      setDetalhe(d);
      const ativas = (d.opcoes || []).filter((o) => !o.excluida);
      sincronizarCesta(extracaoId, ativas, d.documento);
    } catch (err) {
      const mensagem = mensagemErroOperador(
        err,
        "Não foi possível atualizar a seleção. Recarregue a cotação e tente de novo."
      );
      setErro(mensagem);
      registrarDiagnostico({
        estudoId,
        etapa: "cotacao_pdf",
        evento: "selecao_opcao_falhou",
        detalhe: {
          extracao_id: extracaoId,
          opcao_id: opcaoId,
          selecionada,
          status_http: err.status ?? null,
          codigo: err.codigo ?? null,
          mensagem,
          corpo: err.body ?? null,
          causa_rede: Boolean(err.causaRede),
        },
      });
    } finally {
      setAlternandoOpcao(null);
    }
  }

  async function handleAdicionarComparativo() {
    setErro(null);
    setBloqueios([]);
    const podeAplicar = selecionadas.length > 0 || noComparativoDestaExtracao.length > 0;
    if (!podeAplicar) {
      setErro("Selecione ao menos um plano antes de adicionar ao comparativo.");
      return;
    }
    const semTipoFiscal = selecionadas.filter((o) => !o.tipo_fiscal?.texto);
    if (semTipoFiscal.length) {
      setErro(
        "Declare o tipo fiscal de cada plano (Operadora ou Seguradora) antes de adicionar ao comparativo."
      );
      return;
    }
    const semRegime = selecionadas.filter((o) => !o.regime_copart?.texto);
    if (semRegime.length) {
      setErro("Declare o regime de coparticipação de cada plano antes de adicionar ao comparativo.");
      return;
    }
    setRelatoRemocao(null);
    try {
      let res;
      try {
        res = await aplicarExtracaoCotacao(estudoId, extracaoId);
      } catch (err) {
        if (!err.impactoRemocao) throw err;
        // Nada foi gravado ainda: o operador decide antes de perder a etapa 4.
        if (!window.confirm(textoConfirmacaoRemocao(err.impactoRemocao))) {
          setMsg("Nenhum plano foi removido — a seleção anterior continua no comparativo.");
          return;
        }
        res = await aplicarExtracaoCotacao(estudoId, extracaoId, {
          confirmarRemocoes: true,
        });
      }
      const listaAtualizada = await listarExtracoesCotacao(estudoId)
        .then((r) => r.extracoes || [])
        .catch(() => extracoes);
      const opsComp = await obterRascunho(estudoId)
        .then((r) => r.opcoes_proposta || [])
        .catch(() => opcoesComparativo);
      const prox = proximaExtracaoPendente(listaAtualizada, opsComp, extracaoId);
      setProximoPendenteId(prox?.id || null);

      if (selecionadas.length === 0) {
        setMsg("Planos desta cotação removidos do comparativo.");
      } else if (res.opcoes_adicionadas || res.opcoes_atualizadas) {
        setMsg(
          prox
            ? `${res.opcoes_adicionadas || 0} adicionado(s), ${res.opcoes_atualizadas || 0} atualizado(s). Há outra cotação pendente de revisão.`
            : `${res.opcoes_adicionadas || 0} adicionado(s), ${res.opcoes_atualizadas || 0} atualizado(s). Comparativo atualizado.`
        );
      } else {
        setMsg(prox ? "Comparativo atualizado. Há outra cotação pendente." : "Comparativo atualizado.");
      }
      if (res.bloqueios?.length) setBloqueios(res.bloqueios);
      if (res.impacto_remocao) setRelatoRemocao(textoRelatoRemocao(res.impacto_remocao));
      if (setCestaGlobal) {
        setCestaGlobal((prev) => prev.filter((x) => x.extracaoId !== extracaoId));
      }
      setExtracoes(listaAtualizada);
      if (aposUltimoPdfDeveVoltarLista(exigeSelecaoPorGrupo, Boolean(prox))) {
        voltarLista();
      } else {
        await recarregarDetalhe();
      }
      onAplicado?.();
    } catch (err) {
      if (err.bloqueios) setBloqueios(err.bloqueios);
      setErro(err.message);
    }
  }

  function irProximoDocumento() {
    if (!proximoPendenteId) return;
    const id = proximoPendenteId;
    setProximoPendenteId(null);
    setMsg(null);
    abrirDocumento(id);
  }

  function setFiltro(campo, valor) {
    setFiltros((f) => ({ ...f, [campo]: valor }));
  }

  const docAberto = detalhe?.documento;
  const extracaoAberta = extracoes.find((e) => e.id === extracaoId);
  const pdfInlineMeta = useMemo(() => {
    if (!pdfInlineDocumentoId) return null;
    const ext = extracoes.find((e) => e.documento?.id === pdfInlineDocumentoId);
    if (ext?.documento) {
      return {
        titulo: ext.documento.nome_arquivo || ext.documento.operadora_detectada || "Cotação PDF",
      };
    }
    const docRasc = (documentosCotacao || []).find((d) => d.id === pdfInlineDocumentoId);
    if (docRasc) {
      return { titulo: docRasc.operadora || "Cotação PDF" };
    }
    if (docAberto?.id === pdfInlineDocumentoId) {
      return {
        titulo: docAberto.nome_arquivo || docAberto.operadora_detectada || "Cotação PDF",
      };
    }
    return { titulo: "Cotação PDF" };
  }, [pdfInlineDocumentoId, extracoes, documentosCotacao, docAberto]);
  const temPdfs = extracoes.length > 0;
  const temNoComparativo = opcoesComparativo.some((o) => o.extracao_id);

  return (
    <div className="cotacao-pdf-panel">
      {fase === "lista" && (
        <>
          <SelecaoPorGrupo
            estudoId={estudoId}
            onAlterado={onAplicado}
            exigeSelecaoPorGrupo={exigeSelecaoPorGrupo}
          />
          <ComparativoResumo
            opcoesComparativo={opcoesComparativo}
            extracoes={extracoes}
            documentosCotacao={documentosCotacao}
            carregando={carregando}
            onEditarSelecao={handleEditarSelecao}
            onRemoverPlano={handleRemoverPlanoComparativo}
            onRemoverPdf={handleRemoverExtracao}
            onRemoverGrupoOrfao={handleRemoverGrupoOrfao}
          />

          {temPdfs && (
            <section className="panel" aria-label="PDFs importados">
              <div className="panel-head">
                <div>
                  <h2>Cotações recebidas</h2>
                  <p>Gerencie os documentos ou abra uma cotação para selecionar planos.</p>
                </div>
              </div>
              <div className="panel-body">
              <div className="quotes-grid">
                {extracoes.map((ex) => {
                  const qtd = ex.opcoes?.filter((o) => !o.excluida).length ?? 0;
                  const doc = ex.documento;
                  const resumoSel = resumoSelecaoDocumento(ex, opcoesComparativo);
                  const rotulo = rotuloDocumentoExtracao(ex);
                  const planosSel = (opcoesComparativo || []).filter(
                    (o) => o.extracao_id === ex.id
                  );
                  const pendente =
                    !ex.descartada &&
                    planosSel.length === 0 &&
                    !(ex.opcoes || []).some((o) => !o.excluida && o.selecionada_para_comparativo);
                  const badgeRotulo = ex.descartada
                    ? "Descartada"
                    : rotuloEstado(ex.estado);
                  const badgeCls = ex.descartada
                    ? "badge--alerta"
                    : ex.estado === "extraido"
                      ? "badge--ok"
                      : "badge--muted";
                  return (
                    <article
                      key={ex.id}
                      className={`quote-card${ex.descartada ? " quote-card--descartada" : ""}${pendente ? " quote-card--pendente" : ""}`}
                    >
                      <div className="quote-top">
                        <div>
                          <b>{doc?.operadora_detectada || "Operadora"}</b>
                          <div className="cell-sub">
                            {rotulo} · {qtd} {qtd === 1 ? "opção" : "opções"}
                          </div>
                        </div>
                        <span className={`badge ${badgeCls}`}>{badgeRotulo}</span>
                      </div>
                      <div className="quote-file">
                        {doc?.nome_arquivo || "arquivo.pdf"} · enviado em{" "}
                        {formatarDataUpload(ex.criado_em)}
                      </div>
                      <p
                        className={`documento-pdf-selecao${pendente ? " documento-pdf-selecao--pendente" : ""}`}
                      >
                        {resumoSel}
                      </p>
                      {planosSel.length > 0 && (
                        <div className="selected-plans">
                          {planosSel.map((op) => (
                            <div key={op.id} className="plan-pill">
                              <span>{op.plano_nome || op.id}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      {descarteExId === ex.id ? (
                        <div className="documento-pdf-descarte">
                          <label>
                            Motivo para não usar esta cotação
                            <input
                              type="text"
                              value={motivoDescarte}
                              onChange={(e) => setMotivoDescarte(e.target.value)}
                              placeholder="Ex.: fora do perfil, vencida, não competitiva"
                              disabled={carregando}
                              autoFocus
                            />
                          </label>
                          <div className="documento-pdf-descarte-acoes">
                            <button type="button" onClick={confirmarDescarte} disabled={carregando}>
                              Confirmar descarte
                            </button>
                            <button
                              type="button"
                              className="btn-link secundario"
                              onClick={() => {
                                setDescarteExId(null);
                                setMotivoDescarte("");
                              }}
                              disabled={carregando}
                            >
                              Cancelar
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="quote-actions">
                            {ex.descartada ? (
                              <button
                                type="button"
                                onClick={() => handleReverterDescarte(ex)}
                                disabled={carregando}
                              >
                                Reverter descarte
                              </button>
                            ) : (
                              <button type="button" onClick={() => abrirDocumento(ex.id)}>
                                Escolher planos
                              </button>
                            )}
                            {doc?.id && (
                              <button
                                type="button"
                                className={`btn-link secundario btn-compacto${pdfInlineDocumentoId === doc.id ? " ativo" : ""}`}
                                onClick={() => togglePdfInline(doc.id)}
                              >
                                {pdfInlineDocumentoId === doc.id ? "Ocultar PDF" : "Ver PDF"}
                              </button>
                            )}
                            {!ex.descartada && (
                              <button
                                type="button"
                                className="btn-link secundario btn-compacto"
                                onClick={() => abrirDescarte(ex)}
                                disabled={carregando}
                              >
                                Não usar esta cotação
                              </button>
                            )}
                          </div>
                          <button
                            type="button"
                            className="btn-remover documento-pdf-remover"
                            onClick={() => handleRemoverExtracao(ex)}
                            disabled={carregando}
                          >
                            Remover PDF
                          </button>
                        </>
                      )}
                    </article>
                  );
                })}
              </div>
              {pdfInlineDocumentoId && fase === "lista" && (
                <VisualizadorPdfInline
                  estudoId={estudoId}
                  documentoId={pdfInlineDocumentoId}
                  titulo={pdfInlineMeta?.titulo}
                  onFechar={() => setPdfInlineDocumentoId(null)}
                />
              )}
              </div>
            </section>
          )}

          {!temPdfs && !temNoComparativo && (
            <p className="muted cotacao-estado-vazio">Nenhuma cotação importada ainda.</p>
          )}
        </>
      )}

      <UploadZona
        carregando={carregando}
        dragAtivo={dragAtivo}
        setDragAtivo={setDragAtivo}
        compacto={fase === "lista" && temPdfs}
        onUpload={processarUploads}
      />

      {fase !== "lista" && !detalhe && carregandoDetalhe && (
        <p className="muted cotacao-estado-vazio">Carregando planos da cotação…</p>
      )}

      {fase !== "lista" && detalhe && (
        <div
          className={`documento-pdf-aberto${pdfInlineDocumentoId ? " documento-pdf-aberto--com-pdf" : ""}`}
        >
          {pdfInlineDocumentoId && (
            <VisualizadorPdfInline
              estudoId={estudoId}
              documentoId={pdfInlineDocumentoId}
              titulo={pdfInlineMeta?.titulo}
              onFechar={() => setPdfInlineDocumentoId(null)}
            />
          )}
          <div className="documento-pdf-conteudo">
          <div className="documento-pdf-aberto-cabecalho document-context">
            <div className="doc-title">
              <div className="file-ico" aria-hidden="true">
                PDF
              </div>
              <div>
                <b>{docAberto?.nome_arquivo || docAberto?.operadora_detectada || "Cotação PDF"}</b>
                <small className="cell-sub">
                  {docAberto?.operadora_detectada || "Operadora"}
                  {docAberto?.template_id ? ` · template ${docAberto.template_id}` : ""}
                  {` · ${opcoesAtivas.length} opções`}
                  {` · enviado ${formatarDataUpload(detalhe.criado_em)}`}
                </small>
              </div>
            </div>
            <div className="documento-pdf-aberto-acoes">
              {docAberto?.id && (
                <button
                  type="button"
                  className={`secundario btn-compacto${pdfInlineDocumentoId === docAberto.id ? " ativo" : ""}`}
                  onClick={() => togglePdfInline(docAberto.id)}
                >
                  {pdfInlineDocumentoId === docAberto.id ? "Ocultar PDF" : "Ver PDF"}
                </button>
              )}
              <button type="button" className="secundario" onClick={voltarLista}>
                ← Voltar aos documentos
              </button>
              {extracaoAberta && !extracaoAberta.descartada && (
                <button
                  type="button"
                  className="secundario btn-compacto"
                  disabled={carregando}
                  onClick={() => abrirDescarte(extracaoAberta)}
                >
                  Não usar esta cotação
                </button>
              )}
              {extracaoAberta && (
                <button
                  type="button"
                  className="btn-remover"
                  disabled={carregando}
                  onClick={() => handleRemoverExtracao(extracaoAberta)}
                >
                  Remover PDF
                </button>
              )}
            </div>
          </div>

          {detalhe.alertas?.length > 0 && (
            <div className="alertas-simples">
              {detalhe.alertas.map((a, i) => (
                <p key={i} className="alerta">
                  {traduzirAlerta(a)}
                </p>
              ))}
            </div>
          )}

          {resumoSiscor?.requer_data_referencia && (
            <p className="alerta">
              Informe a data de referência de idade na configuração do estudo para calcular o
              valor mensal estimado.
            </p>
          )}

          {resumoSiscor?.planos?.length > 1 && (
            <label className={siscorCtx.exigeEscolha ? "siscor-grupo-destaque" : ""}>
              Escolha o grupo de beneficiários para simular:
              <select
                value={subgrupoSimulacao}
                onChange={(e) => setSubgrupoSimulacao(e.target.value)}
              >
                <option value="">— selecione —</option>
                {resumoSiscor.planos.map((p) => (
                  <option key={p.subgrupo_id} value={p.subgrupo_id}>
                    {p.plano_nome} ({p.operadora})
                  </option>
                ))}
              </select>
            </label>
          )}
          {siscorCtx.exigeEscolha && (
            <p className="alerta">Estimativa indisponível até selecionar o grupo de beneficiários.</p>
          )}

          {planoSiscor && (
            <div className="cartao cartao--interno referencia-plano-atual">
              <div className="referencia-plano-cabecalho">
                <div>
                  <span className="referencia-plano-rotulo">Referência do plano atual</span>
                  <strong className="referencia-plano-nome">{planoSiscor.plano_nome}</strong>
                </div>
                <span
                  className={`referencia-plano-badge${planoSiscor.referencia_comparativo === "reajustada" ? " referencia-plano-badge--reajustada" : ""}`}
                >
                  Comparativo:{" "}
                  {planoSiscor.referencia_comparativo === "reajustada" ? "reajustada" : "vigente"}
                </span>
              </div>
              <dl className="referencia-plano-metricas">
                <div>
                  <dt>Beneficiários</dt>
                  <dd>{planoSiscor.quantidade_beneficiarios ?? "—"}</dd>
                </div>
                <div>
                  <dt>Vigente</dt>
                  <dd>{planoSiscor.valor_mensal_vigente_reais || "—"}</dd>
                </div>
                <div>
                  <dt>Reajuste</dt>
                  <dd>{planoSiscor.reajuste_percentual_exibicao || "—"}</dd>
                </div>
                <div>
                  <dt>Reajustado</dt>
                  <dd>{planoSiscor.valor_mensal_reajustado_reais || "—"}</dd>
                </div>
                <div className="referencia-plano-metrica--destaque">
                  <dt>Base do comparativo</dt>
                  <dd>{planoSiscor.referencia_comparativo_reais || "—"}</dd>
                </div>
              </dl>
            </div>
          )}

          {opcoesAtivas.length === 0 && (
            <div className="recuperacao-extracao-vazia cartao cartao--interno">
              <h4>Nenhum plano extraído deste PDF</h4>
              <p className="muted">
                O parser não localizou tabelas de preço utilizáveis. Você pode conferir o PDF e
                digitar os valores manualmente — a cotação continuará vinculada a este documento.
              </p>
              {detalhe.alertas?.length > 0 && (
                <ul className="recuperacao-alertas">
                  {detalhe.alertas.map((a, i) => (
                    <li key={i}>{traduzirAlerta(a)}</li>
                  ))}
                </ul>
              )}
              {onPreencherManualmente && (
                <button
                  type="button"
                  className="recuperacao-manual-btn"
                  onClick={() => onPreencherManualmente(detalhe, docAberto)}
                >
                  Preencher este plano manualmente
                </button>
              )}
            </div>
          )}

          {opcoesAtivas.length > 0 && fase === "selecao" && (
            <>
              <div className="selecao-resumo-bar">
                <strong>
                  Selecionados: {selecionadas.length} de {opcoesAtivas.length}
                </strong>
                {selecionadas.length > 3 && (
                  <span className="alerta-inline">
                    Muitos planos selecionados — o comparativo fica mais legível com até 3.
                  </span>
                )}
              </div>

              {selecionadas.length > 0 && (
                <div className="selecionados-chips">
                  {selecionadas.map((op) => (
                    <span key={op.id} className="chip-plano">
                      {nomePlanoExibicao(op)}
                      <button
                        type="button"
                        className="link"
                        onClick={() => handleToggle(op.id, false)}
                        aria-label="Remover"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}

              <TabelaSelecaoCompacta
                opcoes={opcoesAtivas}
                templateId={docAberto?.template_id}
                quantidades={quantidades}
                siscorCtx={siscorCtx}
                estimativasMotor={estimativasMotor}
                referenciaCentavos={planoSiscor?.referencia_comparativo_centavos}
                selecionados={{ filtros, setFiltro }}
                opcoesComparativo={opcoesComparativo}
                onToggle={handleToggle}
              />

              <div className="selecao-fluxo-rodape">
                <button
                  type="button"
                  disabled={selecionadas.length === 0 && noComparativoDestaExtracao.length === 0}
                  onClick={() => setFase("revisao")}
                >
                  {noComparativoDestaExtracao.length > 0
                    ? `Revisar alterações (${selecionadas.length} selecionado(s))`
                    : `Revisar ${selecionadas.length} plano(s) selecionado(s)`}
                </button>
              </div>
            </>
          )}

          {fase === "revisao" && (
            <>
              <div className="campos-documento-comuns cartao cartao--interno">
                <span className="doc-confirmacoes-rotulo">Dados do documento</span>
                <dl className="doc-confirmacoes-metricas">
                  <div>
                    <dt>Operadora</dt>
                    <dd>{docAberto?.operadora_detectada || "—"}</dd>
                  </div>
                  <div>
                    <dt>Validade</dt>
                    <dd>
                      {detalhe.validade_oficial?.data ||
                        selecionadas.find((o) => o.validade_oficial?.data)?.validade_oficial
                          ?.data ||
                        "—"}
                    </dd>
                  </div>
                  <div>
                    <dt>Tipo fiscal</dt>
                    <dd>
                      {(() => {
                        const tipos = [
                          ...new Set(
                            selecionadas
                              .map((o) => rotuloTipoFiscal(o.tipo_fiscal?.texto))
                              .filter(Boolean)
                          ),
                        ];
                        if (!tipos.length) return "A declarar por plano";
                        return tipos.join(" / ");
                      })()}
                    </dd>
                  </div>
                </dl>
                {(() => {
                  const validadeAtual =
                    detalhe.validade_oficial?.data ||
                    selecionadas.find((o) => o.validade_oficial?.data)?.validade_oficial?.data;
                  const campoValidadeId =
                    detalhe.validade_oficial?.id ||
                    selecionadas.find((o) => o.validade_oficial?.id)?.validade_oficial?.id;
                  if (validadeAtual || !campoValidadeId) return null;
                  return (
                    <label className="campo-revisao campo-revisao--validade">
                      <span>Validade da cotação</span>
                      <input
                        type="date"
                        defaultValue=""
                        onBlur={(e) => {
                          if (e.target.value) {
                            salvarCampo(campoValidadeId, {
                              data: e.target.value,
                              confirmado: true,
                            });
                          }
                        }}
                      />
                      <span className="muted revisao-plano-dica">
                        Não encontrada no PDF — informe uma vez; aplica a todos os{" "}
                        {selecionadas.length} plano(s) selecionado(s) desta cotação.
                      </span>
                    </label>
                  );
                })()}
              </div>

              {selecionadas.map((op) => (
                <RevisaoPlano
                  key={op.id}
                  op={op}
                  quantidades={quantidades}
                  siscorCtx={siscorCtx}
                  estimativaMotor={estimativasMotor?.[op.id]}
                  validadeDocumento={
                    detalhe.validade_oficial?.data ||
                    selecionadas.find((o) => o.validade_oficial?.data)?.validade_oficial?.data
                  }
                  onSalvarCampo={salvarCampo}
                />
              ))}

              <div className="revisao-fluxo-rodape">
                <button type="button" className="link revisao-fluxo-voltar" onClick={() => setFase("selecao")}>
                  ← Ajustar seleção
                </button>
                <button type="button" className="revisao-fluxo-principal" onClick={handleAdicionarComparativo}>
                  {selecionadas.length === 0 && noComparativoDestaExtracao.length > 0
                    ? "Remover planos desta cotação do comparativo"
                    : noComparativoDestaExtracao.length > 0
                      ? `Atualizar ${selecionadas.length} plano(s) no comparativo`
                      : `Adicionar ${selecionadas.length} plano(s) ao comparativo`}
                </button>
              </div>
              {proximoPendenteId && (
                <div className="documento-pdf-proximo">
                  <button type="button" className="revisao-fluxo-principal" onClick={irProximoDocumento}>
                    Próximo documento →
                  </button>
                  <button type="button" className="link" onClick={voltarLista}>
                    ← Voltar aos documentos
                  </button>
                </div>
              )}
            </>
          )}
          </div>
        </div>
      )}

      {relatoRemocao && (
        <div className="pendencias-box">
          <strong>Planos removidos do comparativo</strong>
          <p>{relatoRemocao}</p>
        </div>
      )}

      {bloqueios.length > 0 && (
        <div className="pendencias-box">
          <strong>Planos que não puderam ser adicionados</strong>
          <ul className="bloqueios-resumo">
            {bloqueios.map((b) => {
              const motivos = resumirMotivosBloqueio(b.motivos);
              return (
                <li key={b.opcao_id || b.plano}>
                  <strong>{b.plano}</strong>
                  <ul>
                    {motivos.map((m, i) => (
                      <li key={i}>{m}</li>
                    ))}
                  </ul>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {msg && <p className="ok">{msg}</p>}
      {proximoPendenteId && fase === "lista" && (
        <div className="documento-pdf-proximo">
          <button type="button" className="revisao-fluxo-principal" onClick={irProximoDocumento}>
            Próximo documento →
          </button>
        </div>
      )}
      {erro && <p className="erro">{erro}</p>}
    </div>
  );
}
