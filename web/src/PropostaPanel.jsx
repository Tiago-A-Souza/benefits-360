import { useEffect, useState } from "react";
import { obterRascunho, salvarRascunho } from "./api";
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
    regime_copart_id: "regime-sem",
    tipo_fiscal: "seguradora",
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

function compFinanceiro(centavos, confirmado = false) {
  if (centavos == null) return null;
  return {
    centavos,
    price_basis: "desconhecido",
    proveniencia: { origem: "manual", extrator_versao: "manual", confirmado },
  };
}

export default function PropostaPanel({ estudoId, onSalvo }) {
  const [rascunho, setRascunho] = useState(null);
  const [sel, setSel] = useState(0);
  const [erro, setErro] = useState(null);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    if (!estudoId) return;
    obterRascunho(estudoId)
      .then((r) => {
        if (!r.opcoes_proposta.length) {
          const op = novaOpcao();
          ensureRegime(r, "sem");
          r.opcoes_proposta = [op];
        } else {
          for (const o of r.opcoes_proposta) {
            const tipo = (o.regime_copart_id || "regime-sem").replace("regime-", "");
            ensureRegime(r, tipo);
          }
        }
        setRascunho({ ...r });
      })
      .catch((e) => setErro(e.message));
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
      f[campo] = valor;
      if (campo === "valor_reais") {
        const conv = reaisTextoParaCentavos(valor);
        f.valor_centavos = conv.ok ? conv.centavos : null;
        f.proveniencia.confirmado = false;
      }
      if (campo === "price_basis") {
        f.price_basis = valor;
        f.proveniencia.confirmado = false;
      }
      if (campo === "quantidade_cotada") {
        f.quantidade_cotada = valor === "" ? null : parseInt(valor, 10);
      }
      if (campo === "confirmado") {
        f.proveniencia.confirmado = valor;
      }
      return copia;
    });
  }

  function adicionarOpcao() {
    setRascunho((prev) => {
      const copia = structuredClone(prev);
      ensureRegime(copia, "sem");
      copia.opcoes_proposta.push(novaOpcao());
      return copia;
    });
    setSel(rascunho.opcoes_proposta.length);
  }

  async function handleSalvar() {
    setErro(null);
    try {
      for (const o of rascunho.opcoes_proposta) {
        if (o.regime_copart_id?.startsWith("regime-")) {
          ensureRegime(rascunho, o.regime_copart_id.replace("regime-", ""));
        }
      }
      await salvarRascunho(estudoId, rascunho);
      setMsg("Propostas salvas.");
      onSalvo?.();
    } catch (e) {
      setErro(e.message);
    }
  }

  return (
    <section className="cartao">
      <h2>Propostas manuais</h2>
      <p className="muted">
        Cadastre uma ou mais opções de plano. Campos ausentes permanecem vazios — não use zero inventado.
      </p>

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
                value={op.tipo_fiscal}
                onChange={(e) => patchOpcao({ tipo_fiscal: e.target.value })}
              >
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
                value={op.regime_copart_id?.replace("regime-", "") || "sem"}
                onChange={(e) => {
                  ensureRegime(rascunho, e.target.value);
                  patchOpcao({ regime_copart_id: `regime-${e.target.value}` });
                }}
              >
                {REGIMES_COPART.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Validade da proposta
              <input
                type="date"
                value={op.validade_oficial || ""}
                onChange={(e) => patchOpcao({ validade_oficial: e.target.value || null })}
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

          <h3>Tabela por faixa etária (0–9)</h3>
          <table className="conferencia">
            <thead>
              <tr>
                <th>Faixa</th>
                <th>Valor (R$)</th>
                <th>Qtd. cotada</th>
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

      <datalist id="operadoras-list">
        {OPERADORAS.map((o) => (
          <option key={o} value={o} />
        ))}
      </datalist>

      <button type="button" onClick={handleSalvar} style={{ marginTop: "1rem" }}>
        Salvar propostas
      </button>
      {msg && <p className="ok">{msg}</p>}
      {erro && <p className="erro">{erro}</p>}
    </section>
  );
}
