import { useEffect, useState } from "react";
import { obterPendencias, obterRascunho, obterResumoPlanoAtual, salvarRascunho } from "./api";
import {
  BASES_IOF,
  MODALIDADES,
  OPERADORAS,
  REGIMES_COPART,
  TIPOS_FISCAIS,
  ensureRegime,
} from "./constants";

export default function ConfigEstudo({ estudoId, onSalvo }) {
  const [rascunho, setRascunho] = useState(null);
  const [pendencias, setPendencias] = useState([]);
  const [resumoAtual, setResumoAtual] = useState(null);
  const [erro, setErro] = useState(null);
  const [msg, setMsg] = useState(null);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (!estudoId) return;
    setErro(null);
    Promise.all([
      obterRascunho(estudoId),
      obterPendencias(estudoId),
      obterResumoPlanoAtual(estudoId).catch(() => null),
    ])
      .then(([r, p, resumo]) => {
        setRascunho(r);
        setPendencias(p);
        setResumoAtual(resumo);
      })
      .catch((e) => setErro(e.message));
  }, [estudoId]);

  function atualizarSubgrupo(idx, campo, valor) {
    setRascunho((prev) => {
      const copia = structuredClone(prev);
      if (campo === "regime_copart_id") {
        ensureRegime(copia, valor);
        copia.subgrupos_atuais[idx].regime_copart_id = `regime-${valor}`;
      } else {
        copia.subgrupos_atuais[idx][campo] = valor;
      }
      return copia;
    });
  }

  function atualizarEscolha(campo, valor) {
    setRascunho((prev) => {
      const copia = structuredClone(prev);
      if (campo === "data_referencia_idade") {
        copia.escolhas.data_referencia_idade = valor || null;
      } else if (campo === "baseline") {
        copia.escolhas.baseline_escolhido.valor = valor;
      } else if (campo === "baseline_confirmado") {
        copia.escolhas.baseline_escolhido.confirmado = valor;
      } else if (campo === "precedencia") {
        copia.escolhas.precedencia_atual_vida.valor = valor;
      } else if (campo === "precedencia_confirmado") {
        copia.escolhas.precedencia_atual_vida.confirmado = valor;
      }
      return copia;
    });
  }

  async function handleSalvar() {
    if (!rascunho) return;
    setSalvando(true);
    setErro(null);
    try {
      await salvarRascunho(estudoId, rascunho);
      const p = await obterPendencias(estudoId);
      setPendencias(p);
      setMsg("Configuração salva.");
      onSalvo?.();
    } catch (e) {
      setErro(e.message);
    } finally {
      setSalvando(false);
    }
  }

  if (!rascunho) return <p className="muted">Carregando configuração…</p>;

  return (
    <section className="cartao">
      <h2>Configuração do plano atual</h2>
      <p className="muted">
        Informe e confirme os dados de cada plano importado antes de cadastrar propostas.
      </p>

      {rascunho.subgrupos_atuais.length === 0 && (
        <p className="erro">Nenhum plano atual — importe e confirme vidas na etapa anterior.</p>
      )}

      {rascunho.subgrupos_atuais.map((sg, idx) => (
        <div key={sg.id} className="cartao cartao--interno">
          <h3>{sg.plano_nome || `Plano ${idx + 1}`}</h3>
          <div className="grid-2">
            <label>
              Operadora
              <input
                value={sg.operadora || ""}
                onChange={(e) => atualizarSubgrupo(idx, "operadora", e.target.value)}
                list="operadoras-list"
              />
            </label>
            <label>
              Nome do plano
              <input
                value={sg.plano_nome || ""}
                onChange={(e) => atualizarSubgrupo(idx, "plano_nome", e.target.value)}
              />
            </label>
            <label>
              Tipo fiscal
              <select
                value={sg.tipo_fiscal || ""}
                onChange={(e) => atualizarSubgrupo(idx, "tipo_fiscal", e.target.value || null)}
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
              Acomodação
              <input
                value={sg.acomodacao || ""}
                onChange={(e) => atualizarSubgrupo(idx, "acomodacao", e.target.value || null)}
              />
            </label>
            <label>
              Modalidade
              <select
                value={sg.modalidade || ""}
                onChange={(e) => atualizarSubgrupo(idx, "modalidade", e.target.value || null)}
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
              Regime de coparticipação
              <select
                value={sg.regime_copart_id?.replace("regime-", "") || ""}
                onChange={(e) => atualizarSubgrupo(idx, "regime_copart_id", e.target.value)}
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
              Base do valor atual (IOF)
              <select
                value={sg.fatura_price_basis || "desconhecido"}
                onChange={(e) => atualizarSubgrupo(idx, "fatura_price_basis", e.target.value)}
              >
                {BASES_IOF.map((b) => (
                  <option key={b.value} value={b.value}>
                    {b.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Reajuste (%)
              <input
                type="number"
                step="0.01"
                value={sg.reajuste_bps != null ? sg.reajuste_bps / 100 : ""}
                onChange={(e) => {
                  const v = e.target.value;
                  atualizarSubgrupo(
                    idx,
                    "reajuste_bps",
                    v === "" ? null : Math.round(parseFloat(v) * 100)
                  );
                }}
              />
            </label>
          </div>
        </div>
      ))}

      <datalist id="operadoras-list">
        {OPERADORAS.map((o) => (
          <option key={o} value={o} />
        ))}
      </datalist>

      <h3>Escolhas do estudo</h3>
      <div className="grid-2">
        <label>
          Data de referência para idades
          <input
            type="date"
            value={rascunho.escolhas.data_referencia_idade || ""}
            onChange={(e) => atualizarEscolha("data_referencia_idade", e.target.value)}
          />
        </label>
        <label>
          Comparar plano atual contra
          <select
            value={rascunho.escolhas.baseline_escolhido.valor || ""}
            onChange={(e) => atualizarEscolha("baseline", e.target.value || null)}
          >
            <option value="">Selecione…</option>
            <option value="vigente">Contrato vigente</option>
            <option value="reajustado">Contrato reajustado</option>
          </select>
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={rascunho.escolhas.baseline_escolhido.confirmado}
            onChange={(e) => atualizarEscolha("baseline_confirmado", e.target.checked)}
          />
          Confirmo a comparação escolhida
        </label>
        <label>
          Fonte do valor atual por vida
          <select
            value={rascunho.escolhas.precedencia_atual_vida.valor || ""}
            onChange={(e) => atualizarEscolha("precedencia", e.target.value || null)}
          >
            <option value="">Selecione…</option>
            <option value="tabela_atual">Tabela do plano</option>
            <option value="valor_fatura">Valor de fatura informado</option>
          </select>
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={rascunho.escolhas.precedencia_atual_vida.confirmado}
            onChange={(e) => atualizarEscolha("precedencia_confirmado", e.target.checked)}
          />
          Confirmo a fonte do valor atual
        </label>
      </div>

      {resumoAtual?.requer_data_referencia && (
        <p className="alerta">Informe a data de referência para calcular faixas e subtotais observados.</p>
      )}
      {resumoAtual?.planos?.length > 0 && (
        <div className="cartao cartao--interno">
          <h3>Resumo observado do plano atual (SISCOR)</h3>
          <p className="muted">Valores por fatura/vida — não é tabela oficial.</p>
          {resumoAtual.planos.map((pl) => (
            <div key={pl.subgrupo_id}>
              <h4>{pl.plano_nome}</h4>
              <p>Subtotal observado: {pl.subtotal_calculado_reais || "—"}</p>
              <ul>
                {pl.faixas.map((f) => (
                  <li key={f.faixa}>
                    Faixa {f.faixa}: {f.quantidade_vidas} vida(s) — {f.valor_observado_reais || "sem valor único"}
                    {f.alerta_inconsistencia && (
                      <span className="alerta"> {f.alerta_inconsistencia}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <p>
            <strong>Total observado:</strong> {resumoAtual.total_calculado_reais || "—"}
          </p>
        </div>
      )}

      {pendencias.length > 0 && (
        <div className="pendencias-box">
          <h4>Pendências nesta etapa</h4>
          <ul className="pendencias">
            {pendencias.map((p, i) => (
              <li key={i} className={`pendencia pendencia--${p.tipo}`}>
                <strong>{p.titulo}</strong>
                <p>{p.descricao}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      <button type="button" onClick={handleSalvar} disabled={salvando}>
        {salvando ? "Salvando…" : "Salvar configuração"}
      </button>
      {msg && <p className="ok">{msg}</p>}
      {erro && <p className="erro">{erro}</p>}
    </section>
  );
}
