import { useEffect, useState } from "react";
import { obterRascunho, salvarRascunho, excluirOpcaoPropostaManual } from "./api";
import CotacaoPdfPanel from "./CotacaoPdfPanel";
import { buildPrefillManualFromExtracao } from "./cotacaoPdf/prefillManual";
import {
  BASES_IOF,
  MODALIDADES,
  OPERADORAS,
  REGIMES_COPART,
  TIPOS_FISCAIS,
  ensureRegime,
  novoId,
  tabelaVazia,
} from "./constants";
import { centavosParaReaisTexto, reaisTextoParaCentavos } from "./money";

function novaOpcao() {
  return {
    id: novoId("op"),
    operadora: "",
    plano_nome: "",
    regime_copart_id: null,
    tipo_fiscal: null,
    acomodacao: null,
    modalidade: null,
    tabela: tabelaVazia(),
    premio_saude: null,
    iof: null,
    total_recorrente: null,
    total_primeira_parcela: null,
    subtotal_impresso: null,
    custos_unicos: [],
    validade_oficial: null,
    observacoes: null,
  };
}

function patchCompFinanceiro(prev, campo, texto) {
  if (!texto || !String(texto).trim()) return { ...prev, [campo]: null };
  const conv = reaisTextoParaCentavos(texto);
  if (!conv.ok) return prev;
  return {
    ...prev,
    [campo]: {
      centavos: conv.centavos,
      price_basis: "desconhecido",
      proveniencia: { origem: "manual", extrator_versao: "manual", confirmado: false },
    },
  };
}

export default function PropostaPanel({
  estudoId,
  etapaIndice = 3,
  totalEtapas = 5,
  onSalvo,
  onRegistrarAvanco,
  cestaGlobal = [],
  setCestaGlobal,
  opcoesComparativo = [],
  extracoes = [],
  subgruposAtuais = [],
}) {
  const [rascunho, setRascunho] = useState(null);
  const [sel, setSel] = useState(0);
  const [manualAberto, setManualAberto] = useState(false);
  const [erro, setErro] = useState(null);
  const [msg, setMsg] = useState(null);

  function recarregar() {
    obterRascunho(estudoId)
      .then((r) => {
        if (!r.opcoes_proposta.length && manualAberto) {
          r.opcoes_proposta = [novaOpcao()];
        }
        for (const o of r.opcoes_proposta) {
          if (o.regime_copart_id) {
            ensureRegime(r, o.regime_copart_id.replace("regime-", ""));
          }
        }
        setRascunho({ ...r });
      })
      .catch((e) => setErro(e.message));
  }

  useEffect(() => {
    if (!estudoId) return;
    recarregar();
  }, [estudoId]);

  if (!rascunho) return <p className="muted">Carregando cotações…</p>;

  const planosAtuais = subgruposAtuais.length
    ? subgruposAtuais
    : rascunho.subgrupos_atuais || [];
  const nPropostas = rascunho.opcoes_proposta.length;
  const unicoPlanoAtual = planosAtuais.length === 1;
  const nomePlanoAtual =
    planosAtuais[0]?.plano_nome || planosAtuais[0]?.operadora || "plano atual";

  const op = rascunho.opcoes_proposta[sel];

  function patchOpcao(mut) {
    setRascunho((prev) => {
      const copia = structuredClone(prev);
      Object.assign(copia.opcoes_proposta[sel], mut);
      return copia;
    });
  }

  function patchFaixa(faixaIdx, campo, valor) {
    setRascunho((prev) => {
      const copia = structuredClone(prev);
      const f = copia.opcoes_proposta[sel].tabela[faixaIdx];
      if (!f.proveniencia) {
        f.proveniencia = { origem: "manual", extrator_versao: "manual", confirmado: false };
      }
      if (campo === "valor_reais") {
        const conv = reaisTextoParaCentavos(valor);
        f.valor_centavos = conv.ok ? conv.centavos : null;
        f.proveniencia.confirmado = false;
      } else if (campo === "price_basis") {
        f.price_basis = valor || "desconhecido";
        f.proveniencia.confirmado = false;
      } else if (campo === "quantidade_cotada") {
        f.quantidade_cotada = valor === "" ? null : parseInt(valor, 10);
      } else if (campo === "confirmado") {
        f.proveniencia.confirmado = valor;
      }
      return copia;
    });
  }

  function patchComp(campo, texto) {
    setRascunho((prev) => patchCompFinanceiro(prev, campo, texto));
  }

  function adicionarOpcao(prefill) {
    setManualAberto(true);
    setRascunho((prev) => {
      const copia = structuredClone(prev);
      const opcao = { ...novaOpcao(), ...(prefill || {}) };
      copia.opcoes_proposta.push(opcao);
      if (prefill?.documento_cotacao_id) {
        const docs = copia.documentos_cotacao || [];
        const jaExiste = docs.some((d) => d.id === prefill.documento_cotacao_id);
        if (!jaExiste && prefill._documento_meta) {
          copia.documentos_cotacao = [...docs, prefill._documento_meta];
        }
      }
      setSel(copia.opcoes_proposta.length - 1);
      return copia;
    });
  }

  function abrirManualDesdeExtracao(detalhe, doc) {
    const prefill = buildPrefillManualFromExtracao(detalhe, doc);
    if (doc?.id) {
      prefill._documento_meta = {
        id: doc.id,
        nome_arquivo: doc.nome_arquivo || "cotação.pdf",
        hash_sha256: doc.hash_sha256 || null,
        template_id: doc.template_id || null,
        operadora_detectada: doc.operadora_detectada || null,
      };
    }
    adicionarOpcao(prefill);
    setMsg("Formulário manual aberto com os dados lidos do PDF. Complete as tarifas e salve.");
  }

  async function handleSalvar() {
    setErro(null);
    try {
      await salvarRascunho(estudoId, rascunho);
      setMsg("Cotação manual salva.");
      onSalvo?.();
    } catch (e) {
      setErro(e.message);
    }
  }

  async function handleExcluirManual() {
    const atual = rascunho.opcoes_proposta[sel];
    if (!atual || atual.extracao_id) return;
    const rotulo = atual.plano_nome || atual.operadora || "esta cotação manual";
    if (!window.confirm(`Excluir «${rotulo}»? Ela sairá do comparativo.`)) {
      return;
    }
    setErro(null);
    try {
      const salvo = await excluirOpcaoPropostaManual(estudoId, atual.id);
      setRascunho(salvo);
      const manuaisIdx = salvo.opcoes_proposta
        .map((o, i) => (!o.extracao_id ? i : -1))
        .filter((i) => i >= 0);
      if (manuaisIdx.length === 0) {
        setManualAberto(false);
        setSel(0);
      } else {
        const preferido =
          manuaisIdx.find((i) => i >= sel) ?? manuaisIdx[manuaisIdx.length - 1];
        setSel(preferido);
      }
      setMsg(`Cotação «${rotulo}» excluída.`);
      onSalvo?.();
    } catch (e) {
      setErro(e.message);
    }
  }

  const nPdfs = extracoes.length;
  const nOpcoesEncontradas = extracoes.reduce(
    (s, ex) => s + (ex.opcoes?.filter((o) => !o.excluida).length || 0),
    0
  );
  const operadoras = [
    ...new Set(
      extracoes
        .map((ex) => ex.documento?.operadora_detectada)
        .filter(Boolean)
    ),
  ];
  const comErro = extracoes.filter((ex) => ex.estado === "erro").length;

  return (
    <section className="etapa-fluxo">
      <div className="page-head">
        <div>
          <div className="page-kicker">
            Etapa {etapaIndice} de {totalEtapas}
          </div>
          <h1>Cotações</h1>
          <p className="lead">
            Importe os PDFs recebidos das operadoras, confira a leitura e escolha quais planos
            entram no comparativo.
          </p>
        </div>
      </div>

      {(nPdfs > 0 || nPropostas > 0) && (
        <div className="metrics">
          <div className="metric">
            <small>PDFs importados</small>
            <strong className="num">{nPdfs}</strong>
            <span className="hint">
              {nPdfs === 0
                ? "nenhum ainda"
                : extracoes.every((e) => e.estado === "extraido" || e.descartada)
                  ? "todos extraídos"
                  : "em revisão"}
            </span>
          </div>
          <div className="metric">
            <small>Opções encontradas</small>
            <strong className="num">{nOpcoesEncontradas}</strong>
            <span className="hint">no catálogo dos PDFs</span>
          </div>
          <div className="metric">
            <small>Selecionados</small>
            <strong className="num">{nPropostas}</strong>
            <span className="hint">no comparativo</span>
          </div>
          {operadoras.length > 0 && (
            <div className="metric">
              <small>Operadoras</small>
              <strong className="num">{operadoras.length}</strong>
              <span className="hint">{operadoras.join(" e ")}</span>
            </div>
          )}
          <div className={`metric${comErro > 0 ? " metric--alerta" : " metric--good"}`}>
            <small>Importações</small>
            <strong>{comErro > 0 ? `${comErro} erro(s)` : "OK"}</strong>
            <span className="hint">
              {comErro > 0 ? "revise os PDFs com falha" : "sem erro de leitura"}
            </span>
          </div>
        </div>
      )}

      {unicoPlanoAtual && nPropostas > 0 && (
        <p className="ok comparativo-resumo-aviso">
          {nPropostas === 1
            ? `1 proposta será comparada com ${nomePlanoAtual}.`
            : `${nPropostas} propostas serão comparadas com ${nomePlanoAtual}.`}
        </p>
      )}

      <CotacaoPdfPanel
        estudoId={estudoId}
        onAplicado={() => {
          recarregar();
          onSalvo?.();
        }}
        onPreencherManualmente={abrirManualDesdeExtracao}
        onRegistrarAvanco={onRegistrarAvanco}
        exigeSelecaoPorGrupo={planosAtuais.length > 1}
        cestaGlobal={cestaGlobal}
        setCestaGlobal={setCestaGlobal}
        opcoesComparativo={opcoesComparativo}
        documentosCotacao={rascunho.documentos_cotacao || []}
      />

      <div className="contingencia-manual">
        <button
          type="button"
          className="link"
          onClick={() => {
            setManualAberto((v) => !v);
            if (!manualAberto && !rascunho.opcoes_proposta.filter((o) => !o.extracao_id).length) {
              adicionarOpcao();
            }
          }}
        >
          {manualAberto
            ? "Ocultar preenchimento manual"
            : "Não foi possível importar? Preencher manualmente."}
        </button>
      </div>

      {manualAberto && (
        <div className="bloco-secao">
          <div className="acoes-lote">
            {rascunho.opcoes_proposta
              .map((o, i) => ({ o, i }))
              .filter(({ o }) => !o.extracao_id)
              .map(({ o, i }) => (
                <button
                  key={o.id}
                  type="button"
                  className={i === sel ? "aba ativa" : "aba"}
                  onClick={() => setSel(i)}
                >
                  {o.plano_nome || o.operadora || `Cotação ${i + 1}`}
                </button>
              ))}
            <button type="button" className="secundario btn-compacto" onClick={() => adicionarOpcao()}>
              + Nova cotação manual
            </button>
          </div>

          {op && !op.extracao_id && (
            <>
              <div className="grid-compacto">
                <label>
                  Operadora
                  <input
                    list="operadoras-list"
                    value={op.operadora}
                    onChange={(e) => patchOpcao({ operadora: e.target.value })}
                  />
                </label>
                <label>
                  Nome do plano
                  <input
                    value={op.plano_nome}
                    onChange={(e) => patchOpcao({ plano_nome: e.target.value })}
                  />
                </label>
                <label>
                  Tipo fiscal
                  <select
                    value={op.tipo_fiscal || ""}
                    onChange={(e) => patchOpcao({ tipo_fiscal: e.target.value || null })}
                  >
                    <option value="">Selecione…</option>
                    {TIPOS_FISCAIS.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Regime de coparticipação
                  <select
                    value={op.regime_copart_id?.replace("regime-", "") || ""}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v) ensureRegime(rascunho, v);
                      patchOpcao({ regime_copart_id: v ? `regime-${v}` : null });
                    }}
                  >
                    <option value="">Selecione…</option>
                    {REGIMES_COPART.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Acomodação
                  <input
                    value={op.acomodacao || ""}
                    onChange={(e) => patchOpcao({ acomodacao: e.target.value || null })}
                  />
                </label>
                <label>
                  Adesão dos funcionários
                  <select
                    value={op.modalidade || ""}
                    onChange={(e) => patchOpcao({ modalidade: e.target.value || null })}
                  >
                    <option value="">Selecione…</option>
                    {MODALIDADES.map((m) => (
                      <option key={m.value} value={m.value}>
                        {m.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <details className="detalhes-recolhidos">
                <summary>Tabela por faixa etária</summary>
                <table className="conferencia">
                  <thead>
                    <tr>
                      <th>Faixa</th>
                      <th>Valor (R$)</th>
                      <th>Qtd.</th>
                      <th>IOF</th>
                    </tr>
                  </thead>
                  <tbody>
                    {op.tabela.map((f, i) => (
                      <tr key={f.faixa}>
                        <td>{f.faixa}</td>
                        <td>
                          <input
                            value={
                              f.valor_centavos != null
                                ? centavosParaReaisTexto(f.valor_centavos)
                                : ""
                            }
                            onChange={(e) => patchFaixa(i, "valor_reais", e.target.value)}
                          />
                        </td>
                        <td>
                          <input
                            type="number"
                            min="0"
                            value={f.quantidade_cotada ?? ""}
                            onChange={(e) => patchFaixa(i, "quantidade_cotada", e.target.value)}
                          />
                        </td>
                        <td>
                          <select
                            value={
                              f.price_basis === "inclui_iof" || f.price_basis === "exclui_iof"
                                ? f.price_basis
                                : ""
                            }
                            onChange={(e) => patchFaixa(i, "price_basis", e.target.value)}
                            className={
                              f.price_basis !== "inclui_iof" && f.price_basis !== "exclui_iof"
                                ? "campo-pendente"
                                : undefined
                            }
                          >
                            <option value="">Selecione…</option>
                            {BASES_IOF.map((b) => (
                              <option key={b.value} value={b.value}>
                                {b.label}
                              </option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>

              <div className="acoes-lote">
                <button type="button" onClick={handleSalvar}>
                  Salvar cotação manual
                </button>
                <button type="button" className="btn-remover" onClick={handleExcluirManual}>
                  Excluir cotação
                </button>
              </div>
            </>
          )}
        </div>
      )}

      <datalist id="operadoras-list">
        {OPERADORAS.map((o) => (
          <option key={o} value={o} />
        ))}
      </datalist>
      {msg && <p className="ok">{msg}</p>}
      {erro && <p className="erro">{erro}</p>}
    </section>
  );
}
