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

export default function PlanosSelecionadosPanel({ estudoId, onSalvo }) {
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
      <section className="secao-fluxo">
        <h2>Correspondência com os planos atuais</h2>
        <p className="lead muted">
          Com um único plano atual, as propostas são sincronizadas automaticamente na etapa
          anterior.
        </p>
      </section>
    );
  }

  return (
    <section className="secao-fluxo">
      <h2>Atribuição de propostas por cenário</h2>
      <p className="lead">
        Cada cenário representa uma coluna do comparativo e deve indicar qual proposta substitui
        cada plano atual. Por padrão, o cenário <em>i</em> aplica a proposta <em>i</em> a todos os
        subgrupos — ajuste célula a célula quando funcionários e diretoria recebem propostas
        distintas.
      </p>

      {rascunho.opcoes_proposta.length === 0 && (
        <p className="alerta">Nenhum plano no comparativo — volte a «Cotações» e adicione opções.</p>
      )}

      <div className="matriz-cenarios">
        {rascunho.opcoes_proposta.map((op, i) => {
          const celulas = matriz[i] || {};
          const preview = rotuloCenario(
            rascunho,
            subgrupos.map((sg) => ({
              opcao_plano_id: celulas[sg.id] || op.id,
            }))
          );
          return (
            <article key={op.id} className="cenario-matriz-bloco">
              <header className="cenario-matriz-cabecalho">
                <strong>Cenário {i + 1}</strong>
                <span className="muted">Coluna: {preview}</span>
              </header>
              <table className="tabela-matriz-cenarios">
                <thead>
                  <tr>
                    <th scope="col">Plano atual (subgrupo)</th>
                    <th scope="col">Proposta atribuída</th>
                  </tr>
                </thead>
                <tbody>
                  {subgrupos.map((sg) => {
                    const opId = celulas[sg.id] || op.id;
                    const opSel = rascunho.opcoes_proposta.find((o) => o.id === opId);
                    const acSg = acomodacaoDe(sg);
                    const acOp = acomodacaoDe(opSel);
                    const diverge = acSg && acOp && acSg !== acOp;
                    return (
                      <tr key={sg.id} className={diverge ? "matriz-linha-aviso" : undefined}>
                        <td>
                          <strong>{sg.plano_nome}</strong>
                          <span className="muted"> · {sg.operadora || "—"}</span>
                          {acSg && (
                            <span className="muted"> · {rotuloAcomodacao(acSg)}</span>
                          )}
                        </td>
                        <td>
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
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
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
        <p className="alerta">Complete a atribuição de proposta para cada subgrupo antes de confirmar.</p>
      )}

      <button type="button" onClick={handleSalvar} disabled={matrizIncompleta}>
        Confirmar atribuições
      </button>
      {msg && <p className="ok">{msg}</p>}
      {erro && <p className="erro">{erro}</p>}
    </section>
  );
}
