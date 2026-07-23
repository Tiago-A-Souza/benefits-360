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
  const [detalhesAbertos, setDetalhesAbertos] = useState(false);
  const [confirmacaoFinal, setConfirmacaoFinal] = useState(false);
  const [erro, setErro] = useState(null);
  const [msg, setMsg] = useState(null);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (!estudoId) return;
    Promise.all([
      obterRascunho(estudoId),
      obterPendencias(estudoId),
      obterResumoPlanoAtual(estudoId).catch(() => null),
    ])
      .then(([r, p, resumo]) => {
        setRascunho(r);
        setPendencias(p);
        setResumoAtual(resumo);
        setConfirmacaoFinal(
          Boolean(
            r.escolhas?.baseline_escolhido?.confirmado &&
              r.escolhas?.precedencia_atual_vida?.confirmado
          )
        );
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
      } else if (campo === "precedencia") {
        copia.escolhas.precedencia_atual_vida.valor = valor;
      }
      return copia;
    });
  }

  async function handleSalvar() {
    if (!rascunho) return;
    setSalvando(true);
    setErro(null);
    const copia = structuredClone(rascunho);
    copia.escolhas.baseline_escolhido.confirmado = confirmacaoFinal;
    copia.escolhas.precedencia_atual_vida.confirmado = confirmacaoFinal;
    try {
      await salvarRascunho(estudoId, copia);
      setRascunho(copia);
      setPendencias(await obterPendencias(estudoId));
      setMsg("Informações do plano atual salvas.");
      onSalvo?.();
    } catch (e) {
      setErro(e.message);
    } finally {
      setSalvando(false);
    }
  }

  if (!rascunho) return <p className="muted">Carregando plano atual…</p>;

  return (
    <section className="secao-fluxo">
      <h2>Plano atual</h2>
      <p className="lead">
        Confirme os dados do contrato vigente e como a Newport fará a comparação com as novas cotações.
      </p>

      {rascunho.subgrupos_atuais.length === 0 && (
        <p className="alerta">Importe a base SISCOR na etapa anterior.</p>
      )}

      {rascunho.subgrupos_atuais.map((sg, idx) => (
        <div key={sg.id} className="bloco-secao">
          <h3>Dados do contrato — {sg.plano_nome || `Plano ${idx + 1}`}</h3>
          <div className="grid-compacto">
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
              Adesão dos funcionários
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
              Reajuste previsto na renovação (%)
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

      <div className="bloco-secao">
        <h3>Como faremos a comparação</h3>
        <p className="muted">Escolha a referência do contrato e a origem dos valores atuais.</p>
        <div className="cartoes-escolha">
          <label className={`cartao-escolha${rascunho.escolhas.baseline_escolhido.valor === "vigente" ? " cartao-escolha--ativo" : ""}`}>
            <input
              type="radio"
              name="baseline"
              checked={rascunho.escolhas.baseline_escolhido.valor === "vigente"}
              onChange={() => atualizarEscolha("baseline", "vigente")}
            />
            <strong>Contrato vigente</strong>
            <span className="muted">Valores atuais sem aplicar reajuste negociado.</span>
          </label>
          <label className={`cartao-escolha${rascunho.escolhas.baseline_escolhido.valor === "reajustado" ? " cartao-escolha--ativo" : ""}`}>
            <input
              type="radio"
              name="baseline"
              checked={rascunho.escolhas.baseline_escolhido.valor === "reajustado"}
              onChange={() => atualizarEscolha("baseline", "reajustado")}
            />
            <strong>Contrato reajustado</strong>
            <span className="muted">Inclui o reajuste informado para a renovação.</span>
          </label>
        </div>
        <div className="cartoes-escolha">
          <label className={`cartao-escolha${rascunho.escolhas.precedencia_atual_vida.valor === "valor_fatura" ? " cartao-escolha--ativo" : ""}`}>
            <input
              type="radio"
              name="precedencia"
              checked={rascunho.escolhas.precedencia_atual_vida.valor === "valor_fatura"}
              onChange={() => atualizarEscolha("precedencia", "valor_fatura")}
            />
            <strong>Valores importados do SISCOR</strong>
            <span className="muted">Usa o valor de fatura de cada beneficiário.</span>
          </label>
          <label className={`cartao-escolha${rascunho.escolhas.precedencia_atual_vida.valor === "tabela_atual" ? " cartao-escolha--ativo" : ""}`}>
            <input
              type="radio"
              name="precedencia"
              checked={rascunho.escolhas.precedencia_atual_vida.valor === "tabela_atual"}
              onChange={() => atualizarEscolha("precedencia", "tabela_atual")}
            />
            <strong>Tabela oficial do plano</strong>
            <span className="muted">Usa a tabela tarifária cadastrada do contrato.</span>
          </label>
        </div>
        <label>
          Data usada para calcular as idades
          <input
            type="date"
            value={rascunho.escolhas.data_referencia_idade || ""}
            onChange={(e) => atualizarEscolha("data_referencia_idade", e.target.value)}
          />
        </label>
      </div>

      <div className="bloco-secao">
        <button
          type="button"
          className="secundario btn-compacto"
          onClick={() => setDetalhesAbertos((v) => !v)}
        >
          {detalhesAbertos ? "Ocultar detalhes fiscais e técnicos" : "Detalhes fiscais e técnicos"}
        </button>
        {detalhesAbertos &&
          rascunho.subgrupos_atuais.map((sg, idx) => (
            <div key={sg.id} className="grid-compacto">
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
                O valor informado já inclui IOF?
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
            </div>
          ))}
      </div>

      {resumoAtual?.total_calculado_reais && (
        <p className="muted">
          Total mensal observado na base: <strong>{resumoAtual.total_calculado_reais}</strong>
        </p>
      )}

      <label className="checkbox confirmacao-final">
        <input
          type="checkbox"
          checked={confirmacaoFinal}
          onChange={(e) => setConfirmacaoFinal(e.target.checked)}
        />
        Revisei e confirmo as informações do plano atual.
      </label>

      {pendencias.length > 0 && (
        <ul className="pendencias">
          {pendencias.slice(0, 3).map((p, i) => (
            <li key={i} className={`pendencia pendencia--${p.tipo}`}>
              {p.titulo}
            </li>
          ))}
        </ul>
      )}

      <button type="button" onClick={handleSalvar} disabled={salvando}>
        {salvando ? "Salvando…" : "Salvar plano atual"}
      </button>
      {msg && <p className="ok">{msg}</p>}
      {erro && <p className="erro">{erro}</p>}

      <datalist id="operadoras-list">
        {OPERADORAS.map((o) => (
          <option key={o} value={o} />
        ))}
      </datalist>
    </section>
  );
}
