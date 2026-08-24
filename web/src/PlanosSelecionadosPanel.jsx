import { useEffect, useState } from "react";
import { obterRascunho, salvarRascunho } from "./api";
import { novoId } from "./constants";

function subgruposComVidas(rascunho) {
  const comVidas = new Set();
  for (const v of rascunho.vidas || []) {
    if (v.incluida && v.subgrupo_atual_id) comVidas.add(v.subgrupo_atual_id);
  }
  return (rascunho.subgrupos_atuais || []).filter((sg) => comVidas.has(sg.id));
}

function normalizarAcomodacao(texto) {
  if (!texto) return null;
  const t = String(texto).trim().toLowerCase();
  if (["enfermaria", "qc", "e", "coletivo", "quarto coletivo"].includes(t)) return "enfermaria";
  if (["apartamento", "qp", "q", "privativo", "quarto privativo"].includes(t)) return "apartamento";
  if (t.includes("enfermaria") || /\bqc\b/.test(t)) return "enfermaria";
  if (t.includes("apartamento") || /\bqp\b/.test(t)) return "apartamento";
  return null;
}

function acomodacaoDe(entidade) {
  return (
    normalizarAcomodacao(entidade?.acomodacao) ||
    normalizarAcomodacao(entidade?.plano_nome)
  );
}

function rotuloAcomodacao(canonico) {
  if (canonico === "enfermaria") return "Enfermaria";
  if (canonico === "apartamento") return "Apartamento";
  return "—";
}

function avisosAcomodacaoMatriz(rascunho, matriz) {
  const subgrupos = subgruposComVidas(rascunho);
  const msgs = [];
  const vistos = new Set();
  rascunho.opcoes_proposta.forEach((opColuna, i) => {
    const celulas = matriz[i] || {};
    for (const sg of subgrupos) {
      const opId = celulas[sg.id] || opColuna.id;
      const op = rascunho.opcoes_proposta.find((o) => o.id === opId);
      if (!op) continue;
      const acSg = acomodacaoDe(sg);
      const acOp = acomodacaoDe(op);
      if (!acSg || !acOp || acSg === acOp) continue;
      const msg =
        `«${sg.plano_nome}» é ${rotuloAcomodacao(acSg)}; a proposta atribuída «${op.plano_nome}» é ${rotuloAcomodacao(acOp)}. A comparação de preço não é equivalente.`;
      if (!vistos.has(msg)) {
        vistos.add(msg);
        msgs.push(msg);
      }
    }
  });
  return msgs;
}

function rotuloCenario(rascunho, atribuicoes) {
  const opIds = [];
  const vistos = new Set();
  for (const atr of atribuicoes) {
    if (!atr.opcao_plano_id || vistos.has(atr.opcao_plano_id)) continue;
    vistos.add(atr.opcao_plano_id);
    opIds.push(atr.opcao_plano_id);
  }
  if (!opIds.length) return "Cenário sem proposta";
  const nome = (id) =>
    rascunho.opcoes_proposta.find((o) => o.id === id)?.plano_nome || id;
  if (opIds.length === 1) return nome(opIds[0]);
  return opIds.map(nome).join(" + ");
}

function extrairMatriz(rascunho) {
  const subgrupos = subgruposComVidas(rascunho);
  const matriz = {};
  rascunho.opcoes_proposta.forEach((op, i) => {
    const cenario =
      rascunho.cenarios[i] ||
      rascunho.cenarios.find((c) =>
        c.atribuicoes.some((a) => a.opcao_plano_id === op.id)
      );
    matriz[i] = {};
    for (const sg of subgrupos) {
      const atr = cenario?.atribuicoes?.find((a) => a.alvo_id === sg.id);
      matriz[i][sg.id] = atr?.opcao_plano_id || op.id;
    }
  });
  return matriz;
}

function montarCenarios(rascunho, matriz) {
  const { opcoes_proposta, cenarios } = rascunho;
  if (!opcoes_proposta.length) return cenarios;

  const subgrupos = subgruposComVidas(rascunho);
  if (!subgrupos.length) return cenarios;

  return opcoes_proposta.map((op, i) => {
    const existente =
      cenarios[i] ||
      cenarios.find((c) => c.atribuicoes.some((a) => a.opcao_plano_id === op.id));
    const celulas = matriz[i] || {};

    const atribuicoes = subgrupos.map((sg) => {
      const atrExistente = existente?.atribuicoes.find((a) => a.alvo_id === sg.id);
      return {
        id: atrExistente?.id || novoId("a"),
        alvo_tipo: "subgrupo",
        alvo_id: sg.id,
        opcao_plano_id: celulas[sg.id] || op.id,
      };
    });

    return {
      id: existente?.id || cenarios[i]?.id || novoId("c"),
      rotulo: rotuloCenario(rascunho, atribuicoes),
      atribuicoes,
    };
  });
}

function contarCorrespondencias(rascunho, matriz, subgrupos) {
  let preenchidas = 0;
  const total = rascunho.opcoes_proposta.length * subgrupos.length;
  rascunho.opcoes_proposta.forEach((op, i) => {
    for (const sg of subgrupos) {
      if (matriz[i]?.[sg.id] || op.id) preenchidas += 1;
    }
  });
  return { preenchidas, total };
}

export default function PlanosSelecionadosPanel({
  estudoId,
  etapaIndice = 4,
  totalEtapas = 5,
  onSalvo,
}) {
  const [rascunho, setRascunho] = useState(null);
  const [matriz, setMatriz] = useState({});
  const [erro, setErro] = useState(null);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    if (!estudoId) return;
    obterRascunho(estudoId)
      .then((r) => {
        setMatriz(extrairMatriz(r));
        setRascunho({ ...r });
      })
      .catch((e) => setErro(e.message));
  }, [estudoId]);

  if (!rascunho) return <p className="muted">Carregando atribuições…</p>;

  const subgrupos = subgruposComVidas(rascunho);
  const multiplosPlanosAtuais = subgrupos.length > 1;
  const nCenarios = rascunho.opcoes_proposta.length;
  const { preenchidas, total } = contarCorrespondencias(rascunho, matriz, subgrupos);

  function atualizarCelula(indiceCenario, subgrupoId, opcaoId) {
    setMatriz((prev) => ({
      ...prev,
      [indiceCenario]: { ...prev[indiceCenario], [subgrupoId]: opcaoId },
    }));
  }

  async function handleSalvar() {
    setErro(null);
    try {
      const copia = structuredClone(rascunho);
      copia.cenarios = montarCenarios(copia, matriz);
      await salvarRascunho(estudoId, copia);
      setRascunho(copia);
      setMatriz(extrairMatriz(copia));
      setMsg("Atribuições confirmadas.");
      onSalvo?.();
    } catch (e) {
      setErro(e.message);
    }
  }

  const matrizIncompleta =
    multiplosPlanosAtuais &&
    rascunho.opcoes_proposta.some(
      (_, i) => subgrupos.some((sg) => !matriz[i]?.[sg.id])
    );
  const avisosAcomodacao = avisosAcomodacaoMatriz(rascunho, matriz);

  if (!multiplosPlanosAtuais) {
    return (
      <section className="etapa-fluxo">
        <div className="page-head">
          <div>
            <div className="page-kicker">
              Etapa {etapaIndice} de {totalEtapas}
            </div>
            <h1>Correspondência com os planos atuais</h1>
            <p className="lead muted">
              Com um único plano atual, as propostas são sincronizadas automaticamente na etapa
              anterior.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="etapa-fluxo">
      <div className="page-head">
        <div>
          <div className="page-kicker">
            Etapa {etapaIndice} de {totalEtapas}
          </div>
          <h1>Correspondência com os planos atuais</h1>
          <p className="lead">
            Para cada cenário, indique qual proposta substitui cada plano vigente. A estrutura do
            estudo permanece a mesma; aqui você só define as equivalências.
          </p>
        </div>
        {nCenarios > 0 && (
          <span className="badge badge--blue">
            {nCenarios} {nCenarios === 1 ? "cenário" : "cenários"}
          </span>
        )}
      </div>

      <div className="notice">
        <div className="notice-icon" aria-hidden="true">
          i
        </div>
        <div>
          <b>Como funciona</b>
          <p>
            Cada cenário vira uma coluna no comparativo. Por padrão, o mesmo plano é aplicado a
            todos os subgrupos; ajuste apenas quando a proposta correta for diferente.
          </p>
        </div>
      </div>

      {rascunho.opcoes_proposta.length === 0 && (
        <p className="alerta">Nenhum plano no comparativo — volte a «Cotações» e adicione opções.</p>
      )}

      <div className="scenario-grid">
        {rascunho.opcoes_proposta.map((op, i) => {
          const celulas = matriz[i] || {};
          const preview = rotuloCenario(
            rascunho,
            subgrupos.map((sg) => ({
              opcao_plano_id: celulas[sg.id] || op.id,
            }))
          );
          const completo = subgrupos.every((sg) => Boolean(celulas[sg.id] || op.id));
          return (
            <article key={op.id} className="scenario">
              <div className="scenario-head">
                <div>
                  <strong>Cenário {i + 1}</strong>
                  <small>Coluna: {preview}</small>
                </div>
                <span className={`badge ${completo ? "badge--ok" : "badge--alerta"}`}>
                  {completo ? "Completo" : "Incompleto"}
                </span>
              </div>
              <div className="scenario-body">
                {subgrupos.map((sg) => {
                  const opId = celulas[sg.id] || op.id;
                  const opSel = rascunho.opcoes_proposta.find((o) => o.id === opId);
                  const acSg = acomodacaoDe(sg);
                  const acOp = acomodacaoDe(opSel);
                  const diverge = acSg && acOp && acSg !== acOp;
                  const vidasSg = (rascunho.vidas || []).filter(
                    (v) => v.incluida && v.subgrupo_atual_id === sg.id
                  ).length;
                  return (
                    <div
                      key={sg.id}
                      className={`mapping${diverge ? " mapping--aviso" : ""}`}
                    >
                      <div className="current">
                        <b>{sg.plano_nome}</b>
                        <small>
                          {sg.operadora || "—"}
                          {vidasSg ? ` · ${vidasSg} vidas` : ""}
                          {acSg ? ` · ${rotuloAcomodacao(acSg)}` : ""}
                        </small>
                      </div>
                      <select
                        value={opId}
                        onChange={(e) => atualizarCelula(i, sg.id, e.target.value)}
                        aria-label={`Proposta para ${sg.plano_nome} no cenário ${i + 1}`}
                      >
                        {rascunho.opcoes_proposta.map((opcao) => (
                          <option key={opcao.id} value={opcao.id}>
                            {opcao.plano_nome || opcao.id}
                            {acomodacaoDe(opcao)
                              ? ` (${rotuloAcomodacao(acomodacaoDe(opcao))})`
                              : ""}
                          </option>
                        ))}
                      </select>
                      {diverge && (
                        <p className="alerta alerta-inline">
                          {`«${sg.plano_nome}» é ${rotuloAcomodacao(acSg)}; a proposta atribuída é ${rotuloAcomodacao(acOp)}. A comparação de preço não é equivalente.`}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </article>
          );
        })}
      </div>

      {avisosAcomodacao.length > 0 && (
        <div className="alerta">
          <strong>Acomodação divergente</strong>
          <ul>
            {avisosAcomodacao.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {matrizIncompleta && (
        <p className="alerta">
          Complete a atribuição de proposta para cada subgrupo antes de confirmar.
        </p>
      )}

      <div className="action-bar">
        <div className="action-left">
          {total > 0 && (
            <span className="action-note">
              {preenchidas} de {total} correspondências preenchidas
            </span>
          )}
          {msg && <span className="action-note ok-inline">{msg}</span>}
          {erro && <span className="action-note erro-inline">{erro}</span>}
        </div>
        <div className="action-right">
          <button type="button" onClick={handleSalvar} disabled={matrizIncompleta}>
            Confirmar atribuições
          </button>
        </div>
      </div>
    </section>
  );
}
