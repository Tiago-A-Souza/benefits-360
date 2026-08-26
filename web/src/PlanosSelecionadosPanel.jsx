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

function cenarioVazio(subgrupos) {
  return {
    id: novoId("c"),
    rotulo: null,
    atribuicoes: subgrupos.map((sg) => ({
      id: novoId("a"),
      alvo_tipo: "subgrupo",
      alvo_id: sg.id,
      opcao_plano_id: "",
    })),
  };
}

function garantirCenariosIniciais(rascunho, subgrupos) {
  if ((rascunho.cenarios || []).length > 0) return rascunho.cenarios;
  return [cenarioVazio(subgrupos)];
}

function lacunasCenario(cenario, subgrupos, opcoes) {
  const opIds = new Set((opcoes || []).map((o) => o.id));
  const faltando = [];
  for (const sg of subgrupos) {
    const atr = (cenario.atribuicoes || []).find((a) => a.alvo_id === sg.id);
    if (!atr?.opcao_plano_id || !opIds.has(atr.opcao_plano_id)) {
      faltando.push(sg.plano_nome || sg.id);
    }
  }
  return faltando;
}

function avisosAcomodacaoCenarios(rascunho, cenarios, subgrupos) {
  const msgs = [];
  const vistos = new Set();
  for (const cenario of cenarios) {
    for (const sg of subgrupos) {
      const atr = (cenario.atribuicoes || []).find((a) => a.alvo_id === sg.id);
      if (!atr?.opcao_plano_id) continue;
      const op = rascunho.opcoes_proposta.find((o) => o.id === atr.opcao_plano_id);
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
  }
  return msgs;
}

export default function PlanosSelecionadosPanel({
  estudoId,
  etapaIndice = 4,
  totalEtapas = 5,
  onSalvo,
}) {
  const [rascunho, setRascunho] = useState(null);
  const [cenarios, setCenarios] = useState([]);
  const [erro, setErro] = useState(null);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    if (!estudoId) return;
    obterRascunho(estudoId)
      .then((r) => {
        const sgs = subgruposComVidas(r);
        const iniciais = garantirCenariosIniciais(r, sgs);
        setCenarios(iniciais);
        setRascunho({ ...r });
      })
      .catch((e) => setErro(e.message));
  }, [estudoId]);

  if (!rascunho) return <p className="muted">Carregando atribuições…</p>;

  const subgrupos = subgruposComVidas(rascunho);
  const multiplosPlanosAtuais = subgrupos.length > 1;
  const opcoes = rascunho.opcoes_proposta || [];

  const lacunasPorCenario = cenarios.map((c) =>
    lacunasCenario(c, subgrupos, opcoes)
  );
  const incompleto = lacunasPorCenario.some((l) => l.length > 0);
  const mensagemFalta = incompleto
    ? lacunasPorCenario
        .map((faltando, i) =>
          faltando.length
            ? `Cenário ${i + 1}: falta escolher cotação para ${faltando.join(", ")}`
            : null
        )
        .filter(Boolean)
        .join(" · ")
    : null;

  function atualizarAtribuicao(indiceCenario, subgrupoId, opcaoId) {
    setCenarios((prev) =>
      prev.map((c, i) => {
        if (i !== indiceCenario) return c;
        const atribuicoes = (c.atribuicoes || []).map((a) =>
          a.alvo_id === subgrupoId ? { ...a, opcao_plano_id: opcaoId } : a
        );
        const temSlot = atribuicoes.some((a) => a.alvo_id === subgrupoId);
        if (!temSlot) {
          atribuicoes.push({
            id: novoId("a"),
            alvo_tipo: "subgrupo",
            alvo_id: subgrupoId,
            opcao_plano_id: opcaoId,
          });
        }
        return {
          ...c,
          atribuicoes,
          rotulo: rotuloCenario(rascunho, atribuicoes),
        };
      })
    );
    setMsg(null);
  }

  function adicionarCenario() {
    setCenarios((prev) => [...prev, cenarioVazio(subgrupos)]);
    setMsg(null);
  }

  function removerCenario(indice) {
    setCenarios((prev) => {
      if (prev.length <= 1) return prev;
      return prev.filter((_, i) => i !== indice);
    });
    setMsg(null);
  }

  async function handleSalvar() {
    setErro(null);
    if (incompleto) {
      setErro(mensagemFalta || "Complete todas as escolhas antes de confirmar.");
      return;
    }
    try {
      const copia = structuredClone(rascunho);
      copia.cenarios = cenarios.map((c) => ({
        ...c,
        rotulo: rotuloCenario(rascunho, c.atribuicoes || []),
      }));
      await salvarRascunho(estudoId, copia);
      setRascunho(copia);
      setCenarios(copia.cenarios);
      setMsg("Atribuições confirmadas.");
      onSalvo?.();
    } catch (e) {
      setErro(e.message);
    }
  }

  const avisosAcomodacao = avisosAcomodacaoCenarios(rascunho, cenarios, subgrupos);

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
            Monte cada coluna do comparativo. Em um mesmo cenário, cada plano vigente pode
            apontar para uma cotação diferente — por exemplo S750 em Prata e ONE S2500 em Ouro.
          </p>
        </div>
        {cenarios.length > 0 && (
          <span className="badge badge--blue">
            {cenarios.length} {cenarios.length === 1 ? "cenário" : "cenários"}
          </span>
        )}
      </div>

      <div className="notice">
        <div className="notice-icon" aria-hidden="true">
          i
        </div>
        <div>
          <b>Um cenário = uma coluna no comparativo</b>
          <p>
            Escolha, plano a plano, qual cotação da etapa anterior entra nessa coluna. Não é
            obrigatório usar a mesma cotação em todos os planos — misturar é o caso normal
            quando os planos vigentes têm níveis diferentes.
          </p>
        </div>
      </div>

      {opcoes.length === 0 && (
        <p className="alerta">Nenhum plano no comparativo — volte a «Cotações» e adicione opções.</p>
      )}

      <div className="scenario-grid">
        {cenarios.map((cenario, i) => {
          const faltando = lacunasPorCenario[i] || [];
          const completo = faltando.length === 0;
          const preview = rotuloCenario(rascunho, cenario.atribuicoes || []);
          const vazioTotal = (cenario.atribuicoes || []).every((a) => !a.opcao_plano_id);
          return (
            <article key={cenario.id} className="scenario">
              <div className="scenario-head">
                <div>
                  <strong>Cenário {i + 1}</strong>
                  <small>
                    {vazioTotal
                      ? "Escolha uma cotação para cada plano vigente abaixo"
                      : `Coluna: ${preview}`}
                  </small>
                </div>
                <div className="scenario-head-actions">
                  <span className={`badge ${completo ? "badge--ok" : "badge--alerta"}`}>
                    {completo ? "Completo" : "Incompleto"}
                  </span>
                  {cenarios.length > 1 && (
                    <button
                      type="button"
                      className="secundario scenario-remover"
                      onClick={() => removerCenario(i)}
                    >
                      Remover
                    </button>
                  )}
                </div>
              </div>
              <div className="scenario-body">
                {subgrupos.map((sg) => {
                  const atr = (cenario.atribuicoes || []).find((a) => a.alvo_id === sg.id);
                  const opId = atr?.opcao_plano_id || "";
                  const opSel = opcoes.find((o) => o.id === opId);
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
                        onChange={(e) => atualizarAtribuicao(i, sg.id, e.target.value)}
                        aria-label={`Cotação para ${sg.plano_nome} no cenário ${i + 1}`}
                      >
                        <option value="">Escolha a cotação…</option>
                        {opcoes.map((opcao) => (
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

      <div className="action-bar action-bar--cenarios">
        <button type="button" className="secundario" onClick={adicionarCenario}>
          Adicionar cenário
        </button>
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

      {mensagemFalta && <p className="alerta">{mensagemFalta}</p>}

      <div className="action-bar">
        <div className="action-left">
          {msg && <span className="action-note ok-inline">{msg}</span>}
          {erro && <span className="action-note erro-inline">{erro}</span>}
        </div>
        <div className="action-right">
          <button type="button" onClick={handleSalvar} disabled={incompleto || !opcoes.length}>
            Confirmar atribuições
          </button>
        </div>
      </div>
    </section>
  );
}
