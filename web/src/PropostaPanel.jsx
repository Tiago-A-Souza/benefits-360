import { useEffect, useState } from "react";
import { obterRascunho, salvarRascunho } from "./api";
import CotacaoPdfPanel from "./CotacaoPdfPanel";
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

export default function PropostaPanel({ estudoId, onSalvo }) {
  const [rascunho, setRascunho] = useState(null);
  const [sel, setSel] = useState(0);
  const [modo, setModo] = useState("pdf");
  const [erro, setErro] = useState(null);
  const [msg, setMsg] = useState(null);

  function recarregar() {
    obterRascunho(estudoId)
      .then((r) => {
        if (!r.opcoes_proposta.length && modo === "manual") {
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

  if (!rascunho) return <p className="muted">Carregando propostas…</p>;

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

  function adicionarOpcao() {
    setRascunho((prev) => {
      const copia = structuredClone(prev);
      copia.opcoes_proposta.push(novaOpcao());
      return copia;
    });
    setSel(rascunho.opcoes_proposta.length);
    setModo("manual");
  }

  async function handleSalvar() {
    setErro(null);
    try {
      await salvarRascunho(estudoId, rascunho);
      setMsg("Propostas salvas.");
      onSalvo?.();
    } catch (e) {
      setErro(e.message);
    }
  }

  return (
    <section className="cartao">
      <h2>Propostas</h2>
      <p className="muted">
        Priorize a importação de PDFs. Use entrada manual somente como contingência.
      </p>

      <div className="acoes-lote">
        <button
          type="button"
          className={modo === "pdf" ? "aba ativa" : "aba"}
          onClick={() => setModo("pdf")}
        >
          PDFs de cotação
        </button>
        <button
          type="button"
          className={modo === "manual" ? "aba ativa" : "aba"}
          onClick={() => setModo("manual")}
        >
          Entrada manual
        </button>
      </div>

      {modo === "pdf" && (
        <CotacaoPdfPanel estudoId={estudoId} onAplicado={recarregar} />
      )}

      {modo === "manual" && (
        <>
          <div className="acoes-lote">
            {rascunho.opcoes_proposta.map((o, i) => (
              <button
                key={o.id}
                type="button"
                className={i === sel ? "aba ativa" : "aba"}
                onClick={() => setSel(i)}
              >
                {o.plano_nome || o.operadora || `Proposta ${i + 1}`}
              </button>
            ))}
            <button type="button" className="secundario" onClick={adicionarOpcao}>
              + Nova proposta
            </button>
          </div>

          {op && (
            <>
              <div className="grid-2">
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
                    onChange={(e) =>
                      patchOpcao({ tipo_fiscal: e.target.value || null })
                    }
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
                  Modalidade
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
                <label>
                  Validade
                  <input
                    type="date"
                    value={op.validade_oficial || ""}
                    onChange={(e) =>
                      patchOpcao({ validade_oficial: e.target.value || null })
                    }
                  />
                </label>
                <label>
                  Observações
                  <input
                    value={op.observacoes || ""}
                    onChange={(e) => patchOpcao({ observacoes: e.target.value || null })}
                  />
                </label>
              </div>

              <h3>Totais (opcionais)</h3>
              <div className="grid-2">
                {[
                  ["premio_saude", "Prêmio saúde"],
                  ["iof", "IOF"],
                  ["total_recorrente", "Total mensal"],
                  ["total_primeira_parcela", "Primeira parcela"],
                  ["subtotal_impresso", "Subtotal impresso"],
                ].map(([campo, rotulo]) => (
                  <label key={campo}>
                    {rotulo}
                    <input
                      value={
                        op[campo]?.centavos != null
                          ? centavosParaReaisTexto(op[campo].centavos)
                          : ""
                      }
                      onChange={(e) => patchComp(campo, e.target.value)}
                    />
                  </label>
                ))}
              </div>

              <h3>Tabela por faixa (0–9)</h3>
              <table className="conferencia">
                <thead>
                  <tr>
                    <th>Faixa</th>
                    <th>Valor (R$)</th>
                    <th>Qtd.</th>
                    <th>IOF</th>
                    <th>Confirmado</th>
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
                      <td>
                        <input
                          type="checkbox"
                          checked={f.proveniencia?.confirmado || false}
                          onChange={(e) => patchFaixa(i, "confirmado", e.target.checked)}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          <button type="button" onClick={handleSalvar} style={{ marginTop: "1rem" }}>
            Salvar propostas manuais
          </button>
        </>
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
