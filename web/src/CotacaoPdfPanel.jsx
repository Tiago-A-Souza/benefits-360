import { useCallback, useEffect, useMemo, useState } from "react";
import {
  aplicarExtracaoCotacao,
  atualizarCampoExtracao,
  importarCotacaoPdf,
  listarExtracoesCotacao,
  obterExtracaoCotacao,
  estimarPropostasExtracao,
  obterRascunho,
  obterResumoPlanoAtual,
  removerExtracaoCotacao,
  salvarRascunho,
  selecionarOpcaoExtracao,
  carregarPdfCotacaoBlob,
  mensagemErroOperador,
  registrarDiagnostico,
} from "./api";
import FilePickerButton from "./components/FilePickerButton";
import {
  centavosParaReaisExibicao,
  centavosParaReaisTexto,
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
  inferirAcomodacao,
  inferirRegiao,
  mapaQuantidadesFaixa,
  nomePlanoExibicao,
  resumoFinanceiroOpcao,
  rotuloEstado,
  rotuloReconciliacao,
  rotuloRegime,
  resumirMotivosBloqueio,
  situacaoOpcao,
  traduzirAlerta,
} from "./cotacaoPdf/utils";
import {
  executarUploadLote,
  formatarResumoUploads,
  primeiroUploadComSucesso,
} from "./cotacaoPdf/uploadLote";

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
        "upload-zona",
        compacto ? "upload-zona--compacto" : "",
        dragAtivo ? "upload-zona--ativa" : "",
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
      <div className="upload-zona-conteudo">
        {!compacto && (
          <span className="upload-zona-icone" aria-hidden="true">
            ↑
          </span>
        )}
        <div className="upload-zona-texto">
          <FilePickerButton
            accept="application/pdf"
            multiple
            disabled={carregando}
            onFiles={onUpload}
          >
            {carregando
              ? "Processando PDF…"
              : compacto
                ? "Enviar outro PDF"
                : "Adicionar cotação em PDF"}
          </FilePickerButton>
          <p className="upload-dica muted">
            {compacto
              ? "Arraste um PDF ou use o botão."
              : "Arraste um ou mais PDFs ou use o botão acima."}
          </p>
        </div>
      </div>
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

function TabelaSelecaoCompacta({
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

      {grupos.map(({ titulo, opcoes: opsGrupo }) => (
        <div key={titulo || "geral"} className="grupo-planos">
          {titulo && <h4 className="grupo-planos-titulo">{titulo}</h4>}
          <div className="lista-planos-selecao">
            <div className="linha-plano-selecao linha-plano-selecao--cabecalho" aria-hidden="true">
              <span className="linha-plano-check" />
              <span>Plano</span>
              <span>Acom.</span>
              <span>Copart.</span>
              <span>Mensal est.</span>
              <span>Δ R$</span>
              <span>Δ %</span>
              <span>Status</span>
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
              return (
                <div
                  key={op.id}
                  role="checkbox"
                  aria-checked={Boolean(op.selecionada_para_comparativo)}
                  tabIndex={0}
                  className={`linha-plano-selecao linha-plano-selecao--clicavel${op.selecionada_para_comparativo ? " linha-plano-selecao--marcada" : ""}${estado.codigo === "adicionado" ? " linha-plano-selecao--adicionada" : ""}${estado.codigo === "remover" ? " linha-plano-selecao--remover" : ""}`}
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
                  <span className="linha-plano-meta">{inferirAcomodacao(op)}</span>
                  <span className="linha-plano-meta linha-plano-meta--copart">{rotuloRegime(op)}</span>
                  <span
                    className={`linha-plano-meta linha-plano-meta--valor${est.destacarGrupo ? " estimativa-indisponivel" : ""}`}
                    title={estimativaTitulo}
                  >
                    {estimativaTexto}
                  </span>
                  <span className="linha-plano-meta linha-plano-meta--valor">
                    {diff.indisponivel ? "—" : diff.textoDiff}
                  </span>
                  <span className="linha-plano-meta linha-plano-meta--valor">
                    {diff.indisponivel ? (
                      "—"
                    ) : (
                      <>
                        {diff.textoPct}
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
      ))}
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

  return (
    <div className="cartao cartao--interno revisao-plano">
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
          <dd>{inferirAcomodacao(op)}</dd>
        </div>
        <div>
          <dt>Tipo fiscal</dt>
          <dd>{op.tipo_fiscal?.texto === "operadora" ? "Operadora" : "Seguradora"}</dd>
        </div>
        <div>
          <dt>Coparticipação</dt>
          <dd>{rotuloRegime(op)}</dd>
        </div>
        <div>
          <dt>Validade</dt>
          <dd>{validadeAtual || "—"}</dd>
        </div>
      </dl>

      {validadePendente && (
        <label className="campo-revisao campo-revisao--validade">
          <span>Validade da cotação</span>
          <input
            type="date"
            defaultValue=""
            onBlur={(e) => {
              if (op.validade_oficial?.id && e.target.value) {
                onSalvarCampo(op.validade_oficial.id, { data: e.target.value, confirmado: true });
              }
            }}
          />
          <span className="muted revisao-plano-dica">
            Não encontrada no PDF — informe para concluir a proposta.
          </span>
        </label>
      )}

      {!validadePendente && (
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
  const [dragAtivo, setDragAtivo] = useState(false);
  const [pdfInlineDocumentoId, setPdfInlineDocumentoId] = useState(null);
  const [carregandoDetalhe, setCarregandoDetalhe] = useState(false);
  const [alternandoOpcao, setAlternandoOpcao] = useState(null);
  const [estimativasMotor, setEstimativasMotor] = useState({});

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
    try {
      const res = await aplicarExtracaoCotacao(estudoId, extracaoId);
      if (selecionadas.length === 0) {
        setMsg("Planos desta cotação removidos do comparativo.");
      } else if (res.opcoes_adicionadas || res.opcoes_atualizadas) {
        setMsg(
          `${res.opcoes_adicionadas || 0} adicionado(s), ${res.opcoes_atualizadas || 0} atualizado(s). Agora você pode ir para a próxima etapa.`
        );
      } else {
        setMsg("Comparativo atualizado.");
      }
      if (res.bloqueios?.length) setBloqueios(res.bloqueios);
      if (setCestaGlobal) {
        setCestaGlobal((prev) => prev.filter((x) => x.extracaoId !== extracaoId));
      }
      await recarregarDetalhe();
      onAplicado?.();
    } catch (err) {
      if (err.bloqueios) setBloqueios(err.bloqueios);
      setErro(err.message);
    }
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
            <section className="documentos-pdf-secao" aria-label="PDFs importados">
              <header className="documentos-pdf-secao-cabecalho">
                <h3>PDFs importados</h3>
                <p className="muted">Escolha planos, revise valores ou remova o arquivo.</p>
              </header>
              <div className="documentos-pdf-grid">
                {extracoes.map((ex) => {
                  const qtd = ex.opcoes?.filter((o) => !o.excluida).length ?? 0;
                  const noComparativo = opcoesComparativo.filter((o) => o.extracao_id === ex.id).length;
                  const doc = ex.documento;
                  return (
                    <article key={ex.id} className="documento-pdf-card">
                      <header>
                        <strong>{doc?.operadora_detectada || "Operadora"}</strong>
                        <BadgeSituacao
                          situacao={{
                            codigo: ex.estado === "extraido" ? "pronto" : "revisao",
                            rotulo: rotuloEstado(ex.estado),
                          }}
                        />
                      </header>
                      <ul className="documento-pdf-meta">
                        <li>{doc?.nome_arquivo || "arquivo.pdf"}</li>
                        <li>Enviado: {formatarDataUpload(ex.criado_em)}</li>
                        <li>{qtd} opção(ões) encontrada(s)</li>
                        {noComparativo > 0 && (
                          <li>
                            {noComparativo} no comparativo
                          </li>
                        )}
                      </ul>
                      <div className="documento-pdf-acoes">
                        <button type="button" onClick={() => abrirDocumento(ex.id)}>
                          Escolher planos
                        </button>
                        {doc?.id && (
                          <button
                            type="button"
                            className={`btn-link secundario btn-compacto${pdfInlineDocumentoId === doc.id ? " ativo" : ""}`}
                            onClick={() => togglePdfInline(doc.id)}
                          >
                            {pdfInlineDocumentoId === doc.id ? "Ocultar PDF" : "Ver PDF"}
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
          <div className="documento-pdf-aberto-cabecalho">
            <div>
              <p className="muted">Documento aberto</p>
              <h4>{docAberto?.operadora_detectada || "Cotação PDF"}</h4>
              <p className="muted">
                {docAberto?.template_id && <>Template {docAberto.template_id} · </>}
                {opcoesAtivas.length} opções · enviado {formatarDataUpload(detalhe.criado_em)}
              </p>
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
                        selecionadas[0]?.validade_oficial?.data ||
                        "—"}
                    </dd>
                  </div>
                  <div>
                    <dt>Tipo fiscal</dt>
                    <dd>Seguradora</dd>
                  </div>
                </dl>
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
            </>
          )}
          </div>
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
      {erro && <p className="erro">{erro}</p>}
    </div>
  );
}
