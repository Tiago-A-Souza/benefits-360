import { useCallback, useEffect, useMemo, useState } from "react";
import {
  aplicarExtracaoCotacao,
  atualizarCampoExtracao,
  confirmarLoteExtracao,
  importarCotacaoPdf,
  listarExtracoesCotacao,
  obterExtracaoCotacao,
  obterRascunho,
  obterResumoPlanoAtual,
  removerExtracaoCotacao,
  salvarRascunho,
  selecionarOpcaoExtracao,
  urlPdfCotacao,
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
  situacaoOpcao,
  traduzirAlerta,
} from "./cotacaoPdf/utils";

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
              const est = formatarEstimativaSiscor(op, quantidades, siscorCtx);
              const estimado = calcularEstimadoCentavos(op, quantidades);
              const diff = formatarDiferencaReferencia(estimado, referenciaCentavos);
              const estimativaTitulo = est.destacarGrupo
                ? "Estimativa indisponível até selecionar o grupo de beneficiários"
                : undefined;
              const estimativaTexto = est.destacarGrupo ? "Selecione o grupo" : est.texto;
              return (
                <div
                  key={op.id}
                  className={`linha-plano-selecao${op.selecionada_para_comparativo ? " linha-plano-selecao--marcada" : ""}${estado.codigo === "adicionado" ? " linha-plano-selecao--adicionada" : ""}${estado.codigo === "remover" ? " linha-plano-selecao--remover" : ""}`}
                >
                  <label className="linha-plano-check">
                    <input
                      type="checkbox"
                      checked={Boolean(op.selecionada_para_comparativo)}
                      onChange={(e) => onToggle(op.id, e.target.checked)}
                      aria-label={`Selecionar ${nomePlanoExibicao(op)}`}
                    />
                  </label>
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

function RevisaoPlano({ op, quantidades, siscorCtx, onSalvarCampo, onConfirmarTabela, confirmando }) {
  const faixasPorIndice = Object.fromEntries((op.tabela || []).map((fx) => [fx.faixa, fx]));
  let subtotal = 0;
  const sit = situacaoOpcao(op);
  const temPop = quantidades && Object.values(quantidades).some((q) => q > 0);
  const estimativaIndisponivel = siscorCtx?.exigeEscolha || !temPop;
  const regimeAtual = op.regime_copart?.texto || "sem";
  const pctAtual = op.copart_percentual?.inteiro ?? "";

  return (
    <div className="cartao cartao--interno revisao-plano">
      <div className="revisao-plano-cabecalho">
        <span className="revisao-plano-rotulo">Revisão do plano</span>
        <strong className="revisao-plano-nome">{nomePlanoExibicao(op)}</strong>
      </div>

      <div className="campos-revisao-grid">
        <label className="campo-revisao campo-revisao--nome">
          <span>Nome</span>
          <div className="campo-revisao-nome-linha">
            <input
              type="text"
              defaultValue={op.plano_nome?.texto || ""}
              onBlur={(e) => {
                const v = e.target.value.trim();
                if (!v || !op.plano_nome?.id) return;
                const patch = { confirmado: true };
                if (v !== op.plano_nome?.texto) patch.texto = v;
                if (!op.plano_nome.confirmado || patch.texto) {
                  onSalvarCampo(op.plano_nome.id, patch);
                }
              }}
            />
            {op.plano_nome?.estado === "revisar" && !op.plano_nome?.confirmado && (
              <button
                type="button"
                className="secundario btn-compacto"
                onClick={() =>
                  onSalvarCampo(op.plano_nome.id, {
                    texto: op.plano_nome.texto,
                    confirmado: true,
                  })
                }
              >
                Confirmar nome
              </button>
            )}
          </div>
        </label>
        <label className="campo-revisao">
          <span>Acomodação</span>
          <select
            defaultValue={inferirAcomodacao(op)}
            onChange={(e) => {
              if (op.acomodacao?.id) {
                onSalvarCampo(op.acomodacao.id, { texto: e.target.value, confirmado: true });
              }
            }}
          >
            <option value="Enfermaria">Enfermaria</option>
            <option value="Apartamento">Apartamento</option>
          </select>
        </label>
        <label className="campo-revisao">
          <span>Tipo fiscal</span>
          <select
            defaultValue={op.tipo_fiscal?.texto || "seguradora"}
            onChange={(e) => {
              if (op.tipo_fiscal?.id) {
                onSalvarCampo(op.tipo_fiscal.id, { texto: e.target.value, confirmado: true });
              }
            }}
          >
            <option value="seguradora">Seguradora</option>
            <option value="operadora">Operadora</option>
          </select>
        </label>
        <label className="campo-revisao">
          <span>Coparticipação</span>
          <select
            defaultValue={regimeAtual}
            onChange={(e) => {
              if (op.regime_copart?.id) {
                onSalvarCampo(op.regime_copart.id, { texto: e.target.value, confirmado: true });
              }
            }}
          >
            <option value="sem">Sem coparticipação</option>
            <option value="parcial">Coparticipação parcial</option>
            <option value="a_confirmar">A confirmar</option>
          </select>
        </label>
        <label className="campo-revisao">
          <span>% copart.</span>
          <input
            type="number"
            min="0"
            max="100"
            placeholder="—"
            defaultValue={pctAtual}
            onBlur={(e) => {
              if (op.copart_percentual?.id) {
                const n = e.target.value === "" ? null : parseInt(e.target.value, 10);
                onSalvarCampo(op.copart_percentual.id, {
                  inteiro: Number.isNaN(n) ? null : n,
                  confirmado: n != null,
                });
              }
            }}
          />
        </label>
        <label className="campo-revisao">
          <span>Validade</span>
          <input
            type="date"
            defaultValue={op.validade_oficial?.data || ""}
            onBlur={(e) => {
              if (op.validade_oficial?.id && e.target.value) {
                onSalvarCampo(op.validade_oficial.id, { data: e.target.value, confirmado: true });
              }
            }}
          />
        </label>
      </div>

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
              if (linha) subtotal += linha;
              const pendente = fx?.valor && !fx.valor.confirmado && fx.valor.estado !== "ausente";
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
                        {pendente && (
                          <button
                            type="button"
                            className="tabela-faixas-acao"
                            onClick={() => onSalvarCampo(fx.valor.id, { confirmado: true })}
                          >
                            Confirmar
                          </button>
                        )}
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
                              if (conv.ok) onSalvarCampo(fx.valor.id, { centavos: conv.centavos });
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
                : centavosParaReaisExibicao(subtotal)}
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
          <button
            type="button"
            className="secundario btn-compacto revisao-plano-btn-confirmar"
            disabled={sit.bloqueiaConfirmacao || confirmando}
            onClick={() => onConfirmarTabela(op)}
          >
            {confirmando ? "Confirmando…" : "Confirmar tabela"}
          </button>
        </div>
      </div>

      <div className="revisao-plano-auditoria">
        <PainelAuditoria op={op} onSalvarCampo={onSalvarCampo} />
      </div>
    </div>
  );
}

export default function CotacaoPdfPanel({
  estudoId,
  onAplicado,
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
  const [confirmandoOpcaoId, setConfirmandoOpcaoId] = useState(null);

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

  function abrirDocumento(id) {
    setExtracaoId(id);
    setFase("selecao");
    setFiltros({ busca: "", acomodacao: "", regime: "", regiao: "" });
    setErro(null);
    setMsg(null);
    setBloqueios([]);
    obterExtracaoCotacao(estudoId, id).then((d) => {
      setDetalhe(d);
      const ativas = (d.opcoes || []).filter((o) => !o.excluida);
      sincronizarCesta(id, ativas, d.documento);
    });
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
  }

  async function processarUploads(files) {
    if (!files.length) return;
    setCarregando(true);
    setErro(null);
    let ultimoId = null;
    try {
      for (const file of files) {
        const res = await importarCotacaoPdf(estudoId, file);
        ultimoId = res.extracao_id;
        setMsg(
          res.sucesso
            ? `${file.name}: ${res.opcoes_encontradas} opção(ões) encontrada(s).`
            : `${file.name} recebido (${res.estado}).`
        );
      }
      recarregar();
      onAplicado?.();
      if (ultimoId) abrirDocumento(ultimoId);
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
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

  async function confirmarCampoOpcao(campo, patch = { confirmado: true }) {
    if (!campo?.id || campo.confirmado || campo.estado === "ausente") return;
    await salvarCampo(campo.id, patch, { recarregar: false });
  }

  async function handleConfirmarTabela(op) {
    if (confirmandoOpcaoId) return;
    const sit = situacaoOpcao(op);
    if (sit.bloqueiaConfirmacao) {
      setErro(`Não é possível confirmar «${nomePlanoExibicao(op)}»: ${sit.motivos.join("; ")}.`);
      return;
    }
    setConfirmandoOpcaoId(op.id);
    setErro(null);
    try {
      for (const fx of op.tabela || []) {
        if (fx.quantidade?.id && !fx.quantidade.confirmado) {
          const qtd = quantidades[fx.faixa] ?? fx.quantidade.inteiro ?? 0;
          await salvarCampo(
            fx.quantidade.id,
            { inteiro: qtd, confirmado: true },
            { recarregar: false }
          );
        }
        if (fx.valor?.id && fx.valor.estado !== "ausente" && !fx.valor.confirmado && fx.valor.centavos != null) {
          await confirmarCampoOpcao(fx.valor);
        }
      }
      await confirmarCampoOpcao(op.plano_nome);
      await confirmarCampoOpcao(op.operadora);
      await confirmarCampoOpcao(op.regime_copart);
      await confirmarCampoOpcao(op.tipo_fiscal);
      await confirmarCampoOpcao(op.acomodacao);
      if (op.copart_percentual?.id && op.copart_percentual.inteiro != null) {
        await confirmarCampoOpcao(op.copart_percentual);
      }
      for (const nome of ["premio_saude", "iof", "total_recorrente", "subtotal_impresso", "total_primeira_parcela"]) {
        await confirmarCampoOpcao(op[nome]);
      }
      await recarregarDetalhe();
      setMsg(`Tabela de «${nomePlanoExibicao(op)}» confirmada.`);
    } catch (err) {
      setErro(err.message || "Não foi possível confirmar a tabela.");
      await recarregarDetalhe();
    } finally {
      setConfirmandoOpcaoId(null);
    }
  }

  async function handleToggle(opcaoId, selecionada) {
    await selecionarOpcaoExtracao(estudoId, extracaoId, opcaoId, selecionada);
    const d = await obterExtracaoCotacao(estudoId, extracaoId);
    setDetalhe(d);
    const ativas = (d.opcoes || []).filter((o) => !o.excluida);
    sincronizarCesta(extracaoId, ativas, d.documento);
  }

  async function handleConfirmarDocumentoSelecionados() {
    if (!detalhe || selecionadas.length === 0) return;
    setErro(null);
    try {
      if (detalhe.validade_oficial?.id && !detalhe.validade_oficial.confirmado) {
        await salvarCampo(detalhe.validade_oficial.id, { confirmado: true }, { recarregar: false });
      }
      for (const op of selecionadas) {
        await confirmarCampoOpcao(op.operadora);
        await confirmarCampoOpcao(op.tipo_fiscal);
      }
      await recarregarDetalhe();
      setMsg("Dados do documento confirmados para os planos selecionados.");
    } catch (err) {
      setErro(err.message || "Não foi possível confirmar os dados do documento.");
      await recarregarDetalhe();
    }
  }

  async function handleConfirmarTipoFiscalDocumento() {
    await handleConfirmarDocumentoSelecionados();
  }

  async function handleConfirmarLote() {
    await confirmarLoteExtracao(estudoId, extracaoId);
    await recarregarDetalhe();
    setMsg("Campos prontos confirmados em lote.");
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
                          <a
                            className="btn-link secundario btn-compacto"
                            href={urlPdfCotacao(estudoId, doc.id)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Ver PDF
                          </a>
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

      {fase !== "lista" && detalhe && (
        <div className="documento-pdf-aberto">
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

          {fase === "selecao" && (
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
                <span className="doc-confirmacoes-rotulo">Confirmações do documento</span>
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
                {(detalhe.validade_oficial && !detalhe.validade_oficial.confirmado) ||
                selecionadas.some(
                  (op) =>
                    (op.tipo_fiscal && !op.tipo_fiscal.confirmado) ||
                    (op.operadora && !op.operadora.confirmado)
                ) ? (
                  <div className="doc-confirmacoes-acoes">
                    <button
                      type="button"
                      className="secundario btn-compacto"
                      onClick={handleConfirmarDocumentoSelecionados}
                    >
                      Confirmar dados do documento
                    </button>
                    {detalhe.validade_oficial && !detalhe.validade_oficial.confirmado && (
                      <span className="muted doc-confirmacoes-dica">
                        Inclui validade, operadora e tipo fiscal.
                      </span>
                    )}
                  </div>
                ) : null}
              </div>

              {selecionadas.map((op) => (
                <RevisaoPlano
                  key={op.id}
                  op={op}
                  quantidades={quantidades}
                  siscorCtx={siscorCtx}
                  onSalvarCampo={salvarCampo}
                  onConfirmarTabela={handleConfirmarTabela}
                  confirmando={confirmandoOpcaoId === op.id}
                />
              ))}

              <div className="revisao-fluxo-rodape">
                <div className="revisao-fluxo-secundarias">
                  <button type="button" className="link revisao-fluxo-voltar" onClick={() => setFase("selecao")}>
                    ← Ajustar seleção
                  </button>
                  <span className="revisao-fluxo-sep" aria-hidden="true">
                    ·
                  </span>
                  <button type="button" className="link" onClick={handleConfirmarLote}>
                    Confirmar campos prontos
                  </button>
                </div>
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
      )}

      {bloqueios.length > 0 && (
        <div className="pendencias-box">
          <strong>Planos não aplicados</strong>
          <ul>
            {bloqueios.map((b) => (
              <li key={b.opcao_id || b.plano}>
                <strong>{b.plano}</strong>
                <ul>
                  {b.motivos.map((m, i) => (
                    <li key={i}>{m}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      )}

      {msg && <p className="ok">{msg}</p>}
      {erro && <p className="erro">{erro}</p>}
    </div>
  );
}
