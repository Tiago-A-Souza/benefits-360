import { useEffect, useState } from "react";
import { obterRascunho, salvarRascunho } from "./api";
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
  onSalvo,
  cestaGlobal = [],
  setCestaGlobal,
  opcoesComparativo = [],
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
        f.price_basis = valor;
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

  return (
    <section className="secao-fluxo">
      <h2>Cotações recebidas</h2>
      <p className="lead">
        Importe os PDFs enviados pelas operadoras. Escolha os planos desejados e adicione-os ao comparativo.
      </p>

      {unicoPlanoAtual && nPropostas > 0 && (
        <p className="ok comparativo-resumo">
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
                            value={f.price_basis}
                            onChange={(e) => patchFaixa(i, "price_basis", e.target.value)}
                          >
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

              <button type="button" onClick={handleSalvar}>
                Salvar cotação manual
              </button>
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
