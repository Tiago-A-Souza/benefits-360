import { useCallback, useEffect, useMemo, useState } from "react";
import {
  aplicarExtracaoCotacao,
  atualizarCampoExtracao,
  confirmarLoteExtracao,
  importarCotacaoPdf,
  listarExtracoesCotacao,
  obterExtracaoCotacao,
  obterResumoPlanoAtual,
  removerExtracaoCotacao,
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
      : situacao.codigo === "revisao" || situacao.codigo === "selecionado"
        ? "badge--alerta"
        : "badge--muted";
  return <span className={`badge ${cls}`}>{situacao.rotulo}</span>;
}

function opcaoJaNoComparativo(op, opcoesComparativo) {
  return opcoesComparativo.some((o) => o.extracao_opcao_id === op.id);
}

function estadoExibicaoOpcao(op, opcoesComparativo) {
  if (opcaoJaNoComparativo(op, opcoesComparativo)) {
    return { codigo: "adicionado", rotulo: "Adicionado ao comparativo" };
  }
  if (op.selecionada_para_comparativo) {
    return { codigo: "selecionado", rotulo: "Selecionado" };
  }
  return { codigo: "disponivel", rotulo: "Disponível" };
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
            {opsGrupo.map((op) => {
              const estado = estadoExibicaoOpcao(op, opcoesComparativo);
              const adicionado = estado.codigo === "adicionado";
              const est = formatarEstimativaSiscor(op, quantidades, siscorCtx);
              return (
                <div
                  key={op.id}
                  className={`linha-plano-selecao${op.selecionada_para_comparativo ? " linha-plano-selecao--marcada" : ""}${adicionado ? " linha-plano-selecao--adicionada" : ""}`}
                >
                  <label className="linha-plano-check">
                    <input
                      type="checkbox"
                      checked={Boolean(op.selecionada_para_comparativo || adicionado)}
                      disabled={adicionado}
                      onChange={(e) => onToggle(op.id, e.target.checked)}
                      aria-label={`Selecionar ${nomePlanoExibicao(op)}`}
                    />
                  </label>
                  <span className="linha-plano-nome">{nomePlanoExibicao(op)}</span>
                  <span className="linha-plano-meta">{inferirAcomodacao(op)}</span>
                  <span className="linha-plano-meta">{rotuloRegime(op)}</span>
                  <span className={`linha-plano-meta${est.destacarGrupo ? " estimativa-indisponivel" : ""}`}>
                    {est.texto}
                  </span>
                  <BadgeSituacao situacao={estado} />
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

function RevisaoPlano({ op, quantidades, siscorCtx, onSalvarCampo, onConfirmarTabela }) {
  const faixasPorIndice = Object.fromEntries((op.tabela || []).map((fx) => [fx.faixa, fx]));
  let subtotal = 0;
  const sit = situacaoOpcao(op);
  const temPop = quantidades && Object.values(quantidades).some((q) => q > 0);
  const estimativaIndisponivel = siscorCtx?.exigeEscolha || !temPop;

  return (
    <div className="cartao cartao--interno revisao-plano">
      <h4>{nomePlanoExibicao(op)}</h4>
      <p className="muted">
        {inferirAcomodacao(op)} · {rotuloRegime(op)}
      </p>

      <table className="tabela-conferencia tabela-faixas">
        <thead>
          <tr>
            <th>Faixa</th>
            <th>Valor unitário</th>
            <th>Qtd (SISCOR)</th>
            <th>Subtotal linha</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {ROTULOS_FAIXA.map((rotulo, idx) => {
            const fx = faixasPorIndice[idx];
            const qtd = quantidades?.[idx] ?? fx?.quantidade?.inteiro ?? 0;
            const val = fx?.valor?.centavos;
            const linha = val != null && qtd > 0 ? val * qtd : null;
            if (linha) subtotal += linha;
            return (
              <tr key={idx}>
                <td>{rotulo}</td>
                <td>
                  {val != null ? centavosParaReaisExibicao(val) : "—"}
                  {fx?.valor && !fx.valor.confirmado && fx.valor.estado !== "ausente" && (
                    <button
                      type="button"
                      className="link"
                      onClick={() =>
                        onSalvarCampo(fx.valor.id, { confirmado: true })
                      }
                    >
                      Confirmar
                    </button>
                  )}
                </td>
                <td>{qtd || "—"}</td>
                <td>{linha != null ? centavosParaReaisExibicao(linha) : "—"}</td>
                <td>
                  {fx?.valor && (
                    <button
                      type="button"
                      className="link"
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
                      Corrigir faixa
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <p>
        <strong>Subtotal estimado:</strong>{" "}
        {estimativaIndisponivel
          ? siscorCtx?.exigeEscolha
            ? "Estimativa indisponível até selecionar o grupo"
            : "—"
          : centavosParaReaisExibicao(subtotal)}
      </p>

      <div className="resumo-financeiro-plano">
        <span>Prêmio: {op.premio_saude?.centavos != null ? centavosParaReaisExibicao(op.premio_saude.centavos) : "—"}</span>
        <span>IOF: {op.iof?.centavos != null ? centavosParaReaisExibicao(op.iof.centavos) : "—"}</span>
        <span>Total: {resumoFinanceiroOpcao(op)}</span>
      </div>

      <p className={op.reconciliacao?.ok ? "reconciliacao ok" : "muted"}>
        {rotuloReconciliacao(op)}
      </p>

      {op.reconciliacao?.divergencias?.length > 0 && (
        <div className="pendencias-box">
          <strong>Divergências</strong>
          <ul>
            {(op.reconciliacao.divergencias || []).map((d, i) => (
              <li key={i}>{d.descricao}</li>
            ))}
          </ul>
        </div>
      )}

      <button
        type="button"
        className="secundario"
        disabled={sit.bloqueiaConfirmacao}
        onClick={() => onConfirmarTabela(op)}
      >
        Confirmar tabela completa
      </button>
      {sit.bloqueiaConfirmacao && (
        <p className="alerta">
          Confirmação bloqueada: {sit.motivos.join("; ")}. Corrija ou confira no PDF antes de confirmar.
        </p>
      )}

      <PainelAuditoria op={op} onSalvarCampo={onSalvarCampo} />
    </div>
  );
}

export default function CotacaoPdfPanel({
  estudoId,
  onAplicado,
  cestaGlobal = [],
  setCestaGlobal,
  opcoesComparativo = [],
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
    () => opcoesAtivas.filter((o) => o.selecionada_para_comparativo && !opcaoJaNoComparativo(o, opcoesComparativo)),
    [opcoesAtivas, opcoesComparativo]
  );

  function sincronizarCesta(idExtracao, opcoes, doc) {
    if (!setCestaGlobal) return;
    setCestaGlobal((prev) => {
      const restantes = prev.filter((x) => x.extracaoId !== idExtracao);
      const novos = opcoes
        .filter((o) => o.selecionada_para_comparativo && !opcaoJaNoComparativo(o, opcoesComparativo))
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
      if (ultimoId) abrirDocumento(ultimoId);
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
    }
  }

  async function handleRemoverExtracao(ex) {
    const aplicados = opcoesComparativo.filter((o) => o.extracao_id === ex.id);
    let texto = "Remover esta cotação do estudo?";
    if (aplicados.length) {
      texto = `Esta cotação já gerou ${aplicados.length} plano(s) no comparativo. Os planos e associações derivados também serão removidos. Deseja continuar?`;
    }
    if (!window.confirm(texto)) return;
    setCarregando(true);
    setErro(null);
    try {
      const res = await removerExtracaoCotacao(estudoId, ex.id);
      if (res.aprovacao_invalidada) {
        setMsg("Cotação removida. A aprovação anterior foi invalidada — revise o estudo.");
      } else {
        setMsg(res.mensagem || "Cotação removida.");
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

  async function salvarCampo(campoId, patch) {
    if (!extracaoId || !campoId) return;
    await atualizarCampoExtracao(estudoId, extracaoId, campoId, patch);
    await recarregarDetalhe();
  }

  async function handleToggle(opcaoId, selecionada) {
    await selecionarOpcaoExtracao(estudoId, extracaoId, opcaoId, selecionada);
    const d = await obterExtracaoCotacao(estudoId, extracaoId);
    setDetalhe(d);
    const ativas = (d.opcoes || []).filter((o) => !o.excluida);
    sincronizarCesta(extracaoId, ativas, d.documento);
  }

  async function handleConfirmarTabela(op) {
    const sit = situacaoOpcao(op);
    if (sit.bloqueiaConfirmacao) {
      setErro(`Não é possível confirmar «${nomePlanoExibicao(op)}»: ${sit.motivos.join("; ")}.`);
      return;
    }
    for (const fx of op.tabela || []) {
      const qtdSiscor = quantidades[fx.faixa];
      if (fx.valor?.centavos != null && !fx.valor.confirmado) {
        await salvarCampo(fx.valor.id, { confirmado: true });
      }
      if (fx.quantidade && qtdSiscor > 0) {
        await salvarCampo(fx.quantidade.id, {
          inteiro: qtdSiscor,
          confirmado: true,
        });
      }
    }
    setMsg(`Tabela de «${nomePlanoExibicao(op)}» confirmada.`);
  }

  async function handleConfirmarLote() {
    await confirmarLoteExtracao(estudoId, extracaoId);
    await recarregarDetalhe();
    setMsg("Campos prontos confirmados em lote.");
  }

  async function handleAdicionarComparativo() {
    setErro(null);
    setBloqueios([]);
    if (selecionadas.length === 0) {
      setErro("Selecione ao menos um plano antes de adicionar ao comparativo.");
      return;
    }
    try {
      const res = await aplicarExtracaoCotacao(estudoId, extracaoId);
      setMsg(
        res.opcoes_adicionadas || res.opcoes_atualizadas
          ? `${res.opcoes_adicionadas || 0} plano(s) adicionado(s) ao comparativo.`
          : "Nenhuma alteração."
      );
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

  return (
    <div className="cotacao-pdf-panel">
      <div
        className={`upload-zona${dragAtivo ? " upload-zona--ativa" : ""}`}
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
          processarUploads(pdfs);
        }}
      >
        <FilePickerButton
          accept="application/pdf"
          multiple
          disabled={carregando}
          onFiles={processarUploads}
        >
          {carregando ? "Processando PDF…" : "Adicionar cotação em PDF"}
        </FilePickerButton>
        <p className="muted upload-dica">Arraste um ou mais PDFs ou use o botão acima.</p>
      </div>

      {fase === "lista" && (
        <div className="documentos-pdf-grid">
          {extracoes.length === 0 && (
            <p className="muted">Nenhuma cotação importada ainda.</p>
          )}
          {extracoes.map((ex) => {
            const qtd = ex.opcoes?.filter((o) => !o.excluida).length ?? 0;
            const selCount =
              ex.opcoes?.filter((o) => o.selecionada_para_comparativo && !o.excluida).length ?? 0;
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
                  {selCount > 0 && <li>{selCount} selecionada(s)</li>}
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
                  <button
                    type="button"
                    className="secundario btn-compacto"
                    onClick={() => handleRemoverExtracao(ex)}
                    disabled={carregando}
                  >
                    Remover do estudo
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}

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
            <button type="button" className="secundario" onClick={voltarLista}>
              ← Voltar aos documentos
            </button>
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
                selecionados={{ filtros, setFiltro }}
                opcoesComparativo={opcoesComparativo}
                onToggle={handleToggle}
              />

              <div className="acoes-lote">
                <button
                  type="button"
                  disabled={selecionadas.length === 0}
                  onClick={() => setFase("revisao")}
                >
                  Revisar {selecionadas.length} plano(s) selecionado(s)
                </button>
                <button
                  type="button"
                  disabled={selecionadas.length === 0}
                  onClick={handleAdicionarComparativo}
                >
                  Adicionar {selecionadas.length} plano(s) ao comparativo
                </button>
              </div>
            </>
          )}

          {fase === "revisao" && (
            <>
              <div className="campos-documento-comuns cartao cartao--interno">
                <h4>Confirmações do documento</h4>
                <div className="campos-comuns-grid">
                  <div>
                    <span className="muted">Operadora</span>
                    <p>{docAberto?.operadora_detectada || "—"}</p>
                  </div>
                  <div>
                    <span className="muted">Validade</span>
                    <p>
                      {detalhe.validade_oficial?.data ||
                        selecionadas[0]?.validade_oficial?.data ||
                        "—"}
                    </p>
                    {detalhe.validade_oficial && !detalhe.validade_oficial.confirmado && (
                      <button
                        type="button"
                        className="link"
                        onClick={() =>
                          salvarCampo(detalhe.validade_oficial.id, { confirmado: true })
                        }
                      >
                        Confirmar validade
                      </button>
                    )}
                  </div>
                  <div>
                    <span className="muted">Tipo fiscal (confirme em cada plano se diferir)</span>
                    <p className="muted">Seguradora ou operadora — revise na tabela abaixo.</p>
                  </div>
                </div>
              </div>

              {selecionadas.map((op) => (
                <RevisaoPlano
                  key={op.id}
                  op={op}
                  quantidades={quantidades}
                  siscorCtx={siscorCtx}
                  onSalvarCampo={salvarCampo}
                  onConfirmarTabela={handleConfirmarTabela}
                />
              ))}

              <div className="acoes-lote">
                <button type="button" className="secundario" onClick={() => setFase("selecao")}>
                  ← Ajustar seleção
                </button>
                <button type="button" className="secundario" onClick={handleConfirmarLote}>
                  Confirmar lote (campos prontos)
                </button>
                <button type="button" onClick={handleAdicionarComparativo}>
                  Adicionar {selecionadas.length} plano(s) ao comparativo
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
