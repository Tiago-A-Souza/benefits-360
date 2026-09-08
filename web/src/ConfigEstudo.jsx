import { useEffect, useRef, useState } from "react";
import {
  obterPendencias,
  obterRascunho,
  obterResumoPlanoAtual,
  obterSugestaoReajustePme,
  salvarRascunho,
} from "./api";
import {
  ACOMODACOES,
  MODALIDADES,
  REGIMES_COPART,
  TIPOS_FISCAIS,
  ensureRegime,
} from "./constants";

function originaisReajuste(rascunho) {
  const mapa = {};
  for (const sg of rascunho?.subgrupos_atuais || []) {
    mapa[sg.id] = sg.reajuste_bps ?? null;
  }
  return mapa;
}

function aplicarSugestoesReajuste(rascunho, porPlano, originais, editados) {
  if (!rascunho || rascunho.formato === "novo") return rascunho;
  const porId = Object.fromEntries((porPlano || []).map((s) => [s.subgrupo_id, s]));
  const copia = structuredClone(rascunho);
  let mudou = false;
  for (const sg of copia.subgrupos_atuais || []) {
    if (editados.has(sg.id)) continue;
    if (originais[sg.id] != null) continue;
    const sugerido = porId[sg.id]?.reajuste_bps ?? null;
    if (sg.reajuste_bps !== sugerido) {
      sg.reajuste_bps = sugerido;
      mudou = true;
    }
  }
  return mudou ? copia : rascunho;
}

function textoOrigemReajuste(sg, sugestaoPme) {
  if (!sugestaoPme) return null;
  const item = (sugestaoPme.por_plano || []).find((s) => s.subgrupo_id === sg.id);
  const periodo = item?.periodo || sugestaoPme.periodo;
  const partes = [];
  if (periodo) partes.push(`Período ${periodo}`);
  if (sugestaoPme.vidas_incluidas >= sugestaoPme.limiar_vidas) {
    partes.push(
      `${sugestaoPme.vidas_incluidas} vidas incluídas — informe o reajuste (não há índice ANS único)`
    );
  } else if (item?.origem === "tabela_pme" && item.reajuste_pct_exibicao) {
    const nome = item.operadora_canonica || sg.operadora;
    partes.push(`Tabela PME · ${nome} ${item.reajuste_pct_exibicao}% (prêmio)`);
  } else if (!sugestaoPme.periodo && !item?.periodo) {
    if (!sugestaoPme.data_referencia_idade) {
      partes.push("Sem data de referência não há período de reajuste");
    }
  }
  return partes.length ? partes.join(" · ") : null;
}

export default function ConfigEstudo({ estudoId, etapaIndice = 2, totalEtapas = 5, onSalvo }) {
  const [rascunho, setRascunho] = useState(null);
  const [pendencias, setPendencias] = useState([]);
  const [resumoAtual, setResumoAtual] = useState(null);
  const [confirmacaoFinal, setConfirmacaoFinal] = useState(false);
  const [erro, setErro] = useState(null);
  const [msg, setMsg] = useState(null);
  const [salvando, setSalvando] = useState(false);
  const [sugestaoPme, setSugestaoPme] = useState(null);
  const originaisReajusteRef = useRef({});
  const reajusteEditadoRef = useRef(new Set());

  useEffect(() => {
    if (!estudoId) return;
    Promise.all([
      obterRascunho(estudoId),
      obterPendencias(estudoId),
      obterResumoPlanoAtual(estudoId).catch(() => null),
    ])
      .then(([r, p, resumo]) => {
        originaisReajusteRef.current = originaisReajuste(r);
        reajusteEditadoRef.current = new Set();
        setRascunho(r);
        setPendencias(p);
        setResumoAtual(resumo);
        setSugestaoPme(null);
        setConfirmacaoFinal(
          Boolean(
            r.escolhas?.baseline_escolhido?.confirmado &&
              (!resumo?.exige_escolha_precedencia ||
                r.escolhas?.precedencia_atual_vida?.confirmado)
          )
        );
      })
      .catch((e) => setErro(e.message));
  }, [estudoId]);

  useEffect(() => {
    if (!estudoId || !rascunho || rascunho.formato === "novo") return undefined;
    let cancelado = false;
    obterSugestaoReajustePme(estudoId, rascunho.escolhas?.data_referencia_idade)
      .then((sug) => {
        if (cancelado) return;
        setSugestaoPme(sug);
        setRascunho((prev) =>
          aplicarSugestoesReajuste(
            prev,
            sug?.por_plano,
            originaisReajusteRef.current,
            reajusteEditadoRef.current
          )
        );
      })
      .catch(() => {
        if (!cancelado) setSugestaoPme(null);
      });
    return () => {
      cancelado = true;
    };
  }, [estudoId, rascunho?.formato, rascunho?.escolhas?.data_referencia_idade]);

  function atualizarSubgrupo(idx, campo, valor) {
    setRascunho((prev) => {
      const copia = structuredClone(prev);
      if (campo === "regime_copart_id") {
        ensureRegime(copia, valor);
        copia.subgrupos_atuais[idx].regime_copart_id = `regime-${valor}`;
      } else if (campo === "tipo_fiscal") {
        copia.subgrupos_atuais[idx].tipo_fiscal = valor;
        const atual = copia.subgrupos_atuais[idx].fatura_price_basis;
        if (valor === "operadora" && (atual === "desconhecido" || !atual)) {
          copia.subgrupos_atuais[idx].fatura_price_basis = "nao_aplica";
        } else if (
          valor === "seguradora" &&
          (atual === "desconhecido" || atual === "nao_aplica" || !atual)
        ) {
          copia.subgrupos_atuais[idx].fatura_price_basis = "exclui_iof";
        }
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
    const seguroNovo = copia.formato === "novo";
    const exigePrecedencia = Boolean(resumoAtual?.exige_escolha_precedencia);
    if (seguroNovo) {
      copia.escolhas.baseline_escolhido.confirmado = false;
      copia.escolhas.baseline_escolhido.valor = null;
      copia.escolhas.precedencia_atual_vida.confirmado = false;
      copia.escolhas.precedencia_atual_vida.valor = null;
    } else {
      copia.escolhas.baseline_escolhido.confirmado = confirmacaoFinal;
      if (exigePrecedencia) {
        copia.escolhas.precedencia_atual_vida.confirmado = confirmacaoFinal;
      }
    }
    try {
      await salvarRascunho(estudoId, copia);
      const [r, p, resumo] = await Promise.all([
        obterRascunho(estudoId),
        obterPendencias(estudoId),
        obterResumoPlanoAtual(estudoId).catch(() => null),
      ]);
      setRascunho(r);
      setPendencias(p);
      setResumoAtual(resumo);
      originaisReajusteRef.current = originaisReajuste(r);
      reajusteEditadoRef.current = new Set();
      setConfirmacaoFinal(
        Boolean(
          r.escolhas?.baseline_escolhido?.confirmado &&
            (!resumo?.exige_escolha_precedencia ||
              r.escolhas?.precedencia_atual_vida?.confirmado)
        )
      );
      setMsg(seguroNovo ? "Referência de idades salva." : "Informações do plano atual salvas.");
      onSalvo?.();
    } catch (e) {
      setErro(e.message);
    } finally {
      setSalvando(false);
    }
  }

  function vidasPlano(subgrupoId) {
    return resumoAtual?.planos?.find((p) => p.subgrupo_id === subgrupoId)
      ?.quantidade_beneficiarios;
  }

  const reajusteUnicoPct = (() => {
    const bps = (rascunho?.subgrupos_atuais || [])
      .map((sg) => sg.reajuste_bps)
      .filter((v) => v != null);
    if (!bps.length || !bps.every((v) => v === bps[0])) return null;
    const pct = bps[0] / 100;
    return Number.isInteger(pct)
      ? String(pct)
      : pct.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  })();

  if (!rascunho) return <p className="muted">Carregando plano atual…</p>;

  if (rascunho.formato === "novo") {
    return (
      <section className="etapa-fluxo">
        <div className="page-head">
          <div>
            <div className="page-kicker">
              Etapa {etapaIndice} de {totalEtapas}
            </div>
            <h1>Referência do estudo</h1>
            <p className="lead">
              Seguro novo não possui contrato vigente. Informe apenas a data usada para calcular as
              idades dos beneficiários.
            </p>
          </div>
        </div>

        <div className="panel">
          <div className="panel-body">
            <div className="form-grid form-grid--two">
              <label className="field">
                Data usada para calcular as idades
                <input
                  type="date"
                  value={rascunho.escolhas.data_referencia_idade || ""}
                  onChange={(e) => atualizarEscolha("data_referencia_idade", e.target.value)}
                />
              </label>
            </div>
          </div>
        </div>

        <div className="action-bar">
          <div className="action-left">
            {msg && <span className="action-note ok-inline">{msg}</span>}
            {erro && <span className="action-note erro-inline">{erro}</span>}
          </div>
          <div className="action-right">
            <button type="button" onClick={handleSalvar} disabled={salvando}>
              {salvando ? "Salvando…" : "Salvar referência"}
            </button>
          </div>
        </div>
      </section>
    );
  }

  const nPlanos = rascunho.subgrupos_atuais.length;

  return (
    <section className="etapa-fluxo">
      <div className="page-head">
        <div>
          <div className="page-kicker">
            Etapa {etapaIndice} de {totalEtapas}
          </div>
          <h1>Plano atual</h1>
          <p className="lead">
            Confirme os dados do contrato vigente e defina qual referência será usada para comparar
            as novas cotações.
          </p>
        </div>
        {nPlanos > 0 && (
          <span className="badge badge--ok">
            {nPlanos} {nPlanos === 1 ? "plano identificado" : "planos identificados"}
          </span>
        )}
      </div>

      {nPlanos === 0 && <p className="alerta">Importe a base SISCOR na etapa anterior.</p>}

      {nPlanos > 0 && (
        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>Planos vigentes</h2>
              <p>Edite somente o que estiver diferente do contrato atual.</p>
            </div>
            <span className="badge badge--muted">Dados editáveis</span>
          </div>
          <div className="panel-body">
            {rascunho.subgrupos_atuais.map((sg, idx) => {
              const vidas = vidasPlano(sg.id);
              return (
                <article key={sg.id} className="plan-card">
                  <header className="plan-card-head">
                    <div className="plan-card-title">
                      <span className="plan-index">Plano {idx + 1}</span>
                      <b>
                        {[sg.operadora, sg.plano_nome].filter((p) => (p || "").trim()).join(" · ") ||
                          `Plano ${idx + 1}`}
                      </b>
                    </div>
                    {vidas != null && (
                      <span className="badge badge--blue">
                        {vidas} {vidas === 1 ? "vida" : "vidas"}
                      </span>
                    )}
                  </header>
                  <div className="plan-card-body">
                    <div className="form-grid">
                      <label className="field">
                        Tipo fiscal
                        <select
                          value={sg.tipo_fiscal || ""}
                          onChange={(e) =>
                            atualizarSubgrupo(idx, "tipo_fiscal", e.target.value || null)
                          }
                          className={!sg.tipo_fiscal ? "campo-pendente" : undefined}
                        >
                          <option value="">Selecione…</option>
                          {TIPOS_FISCAIS.map((t) => (
                            <option key={t.value} value={t.value}>
                              {t.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="field">
                        Adesão dos funcionários
                        <select
                          value={sg.modalidade || ""}
                          onChange={(e) =>
                            atualizarSubgrupo(idx, "modalidade", e.target.value || null)
                          }
                        >
                          <option value="">Selecione…</option>
                          {MODALIDADES.map((m) => (
                            <option key={m.value} value={m.value}>
                              {m.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="field">
                        Regime de coparticipação
                        <select
                          value={sg.regime_copart_id?.replace("regime-", "") || ""}
                          onChange={(e) =>
                            atualizarSubgrupo(idx, "regime_copart_id", e.target.value)
                          }
                          className={!sg.regime_copart_id ? "campo-pendente" : undefined}
                        >
                          <option value="">Selecione…</option>
                          {REGIMES_COPART.map((r) => (
                            <option key={r.value} value={r.value}>
                              {r.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="field">
                        Acomodação
                        <select
                          value={sg.acomodacao || ""}
                          onChange={(e) =>
                            atualizarSubgrupo(idx, "acomodacao", e.target.value || null)
                          }
                        >
                          <option value="">Não informada</option>
                          {ACOMODACOES.map((a) => (
                            <option key={a.value} value={a.value}>
                              {a.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="field">
                        Reajuste previsto na renovação{"\u00A0"}(%)
                        <input
                          type="number"
                          step="0.01"
                          value={sg.reajuste_bps != null ? sg.reajuste_bps / 100 : ""}
                          onChange={(e) => {
                            const v = e.target.value;
                            reajusteEditadoRef.current = new Set(reajusteEditadoRef.current).add(
                              sg.id
                            );
                            atualizarSubgrupo(
                              idx,
                              "reajuste_bps",
                              v === "" ? null : Math.round(parseFloat(v) * 100)
                            );
                          }}
                        />
                        {textoOrigemReajuste(sg, sugestaoPme) && (
                          <small className="field-hint origem-reajuste-pme">
                            {textoOrigemReajuste(sg, sugestaoPme)}
                          </small>
                        )}
                      </label>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-head">
          <div>
            <h2>Referência da comparação</h2>
            <p>Escolha qual valor do contrato vigente será usado como base.</p>
          </div>
        </div>
        <div className="panel-body">
          <h3 className="grupo-escolhas-titulo">Referência do contrato</h3>
          <div className="cartoes-escolha">
            <label
              className={`cartao-escolha${
                rascunho.escolhas.baseline_escolhido.valor === "vigente"
                  ? " cartao-escolha--ativo"
                  : ""
              }`}
            >
              <input
                type="radio"
                name="baseline"
                checked={rascunho.escolhas.baseline_escolhido.valor === "vigente"}
                onChange={() => atualizarEscolha("baseline", "vigente")}
              />
              <strong>Contrato vigente</strong>
              <span className="muted">Valores atuais sem aplicar reajuste negociado.</span>
            </label>
            <label
              className={`cartao-escolha${
                rascunho.escolhas.baseline_escolhido.valor === "reajustado"
                  ? " cartao-escolha--ativo"
                  : ""
              }`}
            >
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

          <h3 className="grupo-escolhas-titulo">Origem dos valores atuais</h3>
          {resumoAtual?.exige_escolha_precedencia ? (
            <>
              <p className="alerta">
                {resumoAtual.origem_valores_descricao ||
                  "Tabela e fatura coexistem — escolha qual fonte prevalece."}
              </p>
              <div className="cartoes-escolha">
                <label
                  className={`cartao-escolha${
                    rascunho.escolhas.precedencia_atual_vida.valor === "valor_fatura"
                      ? " cartao-escolha--ativo"
                      : ""
                  }`}
                >
                  <input
                    type="radio"
                    name="precedencia"
                    checked={rascunho.escolhas.precedencia_atual_vida.valor === "valor_fatura"}
                    onChange={() => atualizarEscolha("precedencia", "valor_fatura")}
                  />
                  <strong>Valores importados do SISCOR</strong>
                  <span className="muted">Usa o valor de fatura de cada beneficiário.</span>
                </label>
                <label
                  className={`cartao-escolha${
                    rascunho.escolhas.precedencia_atual_vida.valor === "tabela_atual"
                      ? " cartao-escolha--ativo"
                      : ""
                  }`}
                >
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
            </>
          ) : (
            <p className="origem-valores-info muted">
              {resumoAtual?.origem_valores_descricao ||
                "A origem dos valores atuais será definida automaticamente conforme a base importada."}
            </p>
          )}

          <div className="form-grid form-grid--two form-grid--spaced">
            <label className="field">
              Data usada para calcular as idades
              <input
                type="date"
                value={rascunho.escolhas.data_referencia_idade || ""}
                onChange={(e) => atualizarEscolha("data_referencia_idade", e.target.value)}
              />
              {sugestaoPme?.periodo ? (
                <small className="field-hint periodo-reajuste-pme">
                  Período de reajuste PME: {sugestaoPme.periodo}
                </small>
              ) : (
                <small className="field-hint periodo-reajuste-pme">
                  Esta data define as idades e o período do reajuste PME.
                </small>
              )}
            </label>
          </div>

          {(resumoAtual?.total_vigente_reais || resumoAtual?.total_reajustado_reais) && (
            <div className="money-strip num">
              {resumoAtual.total_vigente_reais && (
                <div className="money-box">
                  <small>Total vigente na base</small>
                  <strong>{resumoAtual.total_vigente_reais}</strong>
                </div>
              )}
              {resumoAtual.total_vigente_reais && resumoAtual.total_reajustado_reais && (
                <div className="money-arrow" aria-hidden="true">
                  →
                </div>
              )}
              {resumoAtual.total_reajustado_reais && (
                <div className="money-box">
                  <small>
                    Total reajustado
                    {reajusteUnicoPct ? ` (+${reajusteUnicoPct}%)` : ""}
                  </small>
                  <strong>{resumoAtual.total_reajustado_reais}</strong>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {pendencias.filter((p) => p.etapa === 2).length > 0 && (
        <ul className="pendencias">
          {pendencias
            .filter((p) => p.etapa === 2)
            .map((p, i) => (
              <li key={p.codigo || i} className={`pendencia pendencia--${p.tipo}`}>
                <strong>{p.titulo}</strong>
                {p.descricao && <p>{p.descricao}</p>}
                {p.codigo === "APP-IMP-001" && (
                  <p className="acao">
                    Em cada plano acima, preencha o campo <strong>Tipo fiscal</strong> (Seguradora
                    ou Operadora).
                  </p>
                )}
              </li>
            ))}
        </ul>
      )}

      <div className="action-bar">
        <div className="action-left">
          <label className="checkbox confirmacao-final">
            <input
              type="checkbox"
              checked={confirmacaoFinal}
              onChange={(e) => setConfirmacaoFinal(e.target.checked)}
            />
            Revisei e confirmo as informações do plano atual.
          </label>
          {msg && <span className="action-note ok-inline">{msg}</span>}
          {erro && <span className="action-note erro-inline">{erro}</span>}
        </div>
        <div className="action-right">
          <button type="button" onClick={handleSalvar} disabled={salvando}>
            {salvando ? "Salvando…" : "Salvar plano atual"}
          </button>
        </div>
      </div>

    </section>
  );
}
