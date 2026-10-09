import { useCallback, useEffect, useId, useRef, useState } from "react";
import { obterMatrizEstimativa, obterRascunho, salvarRascunho } from "./api";
import { novoId } from "./constants";
import { mensagemLacunasAtribuicao, rotuloOpcaoComDiff, rotuloOpcaoNome } from "./fluxo/avancoEtapa";
import { classeDiffEstimativa, formatarDiffCentavos } from "./money";
import { atribuicaoForaDaSelecao, opcoesParaDropdown } from "./opcoesPorGrupo";

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

function acomodacaoInformada(entidade) {
  return normalizarAcomodacao(entidade?.acomodacao);
}

function avisosAcomodacaoCenarios(rascunho, cenarios, subgrupos) {
  const divergencias = [];
  const incompletos = [];
  const vistosDiv = new Set();
  const vistosInc = new Set();
  for (const cenario of cenarios) {
    for (const sg of subgrupos) {
      const atr = (cenario.atribuicoes || []).find((a) => a.alvo_id === sg.id);
      if (!atr?.opcao_plano_id) continue;
      const op = rascunho.opcoes_proposta.find((o) => o.id === atr.opcao_plano_id);
      if (!op) continue;
      const acSg = acomodacaoInformada(sg);
      const acOp = acomodacaoInformada(op);
      if (acSg && acOp && acSg !== acOp) {
        const msg =
          `«${sg.plano_nome}» é ${rotuloAcomodacao(acSg)}; a proposta atribuída «${op.plano_nome}» é ${rotuloAcomodacao(acOp)}. A comparação de preço não é equivalente.`;
        if (!vistosDiv.has(msg)) {
          vistosDiv.add(msg);
          divergencias.push(msg);
        }
      } else if (!acSg || !acOp) {
        let msg;
        if (!acSg && !acOp) {
          msg = `Comparação de acomodação não realizada entre «${sg.plano_nome}» e «${op.plano_nome}»: nenhum dos lados informado.`;
        } else if (!acSg) {
          msg = `Comparação de acomodação não realizada para «${sg.plano_nome}»: acomodação do plano vigente não informada.`;
        } else {
          msg = `Comparação de acomodação não realizada para «${op.plano_nome}»: acomodação da proposta não informada.`;
        }
        if (!vistosInc.has(msg)) {
          vistosInc.add(msg);
          incompletos.push(msg);
        }
      }
    }
  }
  return { divergencias, incompletos };
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

function diffOpcaoNoSubgrupo(matriz, subgrupoId, opcaoId) {
  const cel = (matriz?.celulas || []).find(
    (c) => c.subgrupo_id === subgrupoId && c.opcao_id === opcaoId
  );
  return cel?.diff_centavos ?? null;
}

function acomodacaoRotuloOpcao(opcao) {
  const ac = acomodacaoInformada(opcao);
  return ac ? rotuloAcomodacao(ac) : null;
}

function RotuloOpcaoComDiff({ nome, acomodacaoRotulo, diffCentavos }) {
  const nomeTexto = rotuloOpcaoNome(nome, acomodacaoRotulo);
  const diffTexto = formatarDiffCentavos(diffCentavos);
  const diffClasse = classeDiffEstimativa(diffCentavos);
  return (
    <span className="mapping-select-rotulo">
      <span className="mapping-select-nome">{nomeTexto}</span>
      {diffTexto ? (
        <span className={`mapping-select-diff ${diffClasse}`}>{diffTexto}</span>
      ) : null}
    </span>
  );
}

function SelectOpcaoComDiff({ value, opcoes, matriz, subgrupoId, ariaLabel, onChange }) {
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(0);
  const rootRef = useRef(null);
  const listId = useId();
  const itens = [{ id: "", placeholder: true }, ...opcoes];
  const selecionada = opcoes.find((o) => o.id === value);

  useEffect(() => {
    if (!aberto) return undefined;
    const onDoc = (e) => {
      if (!rootRef.current?.contains(e.target)) setAberto(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [aberto]);

  useEffect(() => {
    if (!aberto) return;
    const idx = itens.findIndex((it) => it.id === (value || ""));
    setAtivo(idx < 0 ? 0 : idx);
    // Só reposiciona o destaque ao abrir ou ao mudar a escolha.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aberto, value]);

  const escolher = (id) => {
    onChange(id);
    setAberto(false);
  };

  const onKeyDown = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      setAberto(false);
      return;
    }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!aberto) {
        setAberto(true);
        return;
      }
      setAtivo((i) => {
        if (e.key === "ArrowDown") return Math.min(i + 1, itens.length - 1);
        return Math.max(i - 1, 0);
      });
      return;
    }
    if ((e.key === "Enter" || e.key === " ") && aberto) {
      e.preventDefault();
      const it = itens[ativo];
      if (it) escolher(it.placeholder ? "" : it.id);
    }
  };

  return (
    <div
      className={`mapping-select${aberto ? " mapping-select--aberto" : ""}`}
      ref={rootRef}
    >
      <button
        type="button"
        className="mapping-select-btn"
        aria-haspopup="listbox"
        aria-expanded={aberto}
        aria-controls={listId}
        aria-label={ariaLabel}
        title={
          selecionada
            ? rotuloOpcaoComDiff(
                selecionada.plano_nome || selecionada.id,
                acomodacaoRotuloOpcao(selecionada),
                diffOpcaoNoSubgrupo(matriz, subgrupoId, selecionada.id)
              )
            : "Escolha o plano…"
        }
        onClick={() => setAberto((v) => !v)}
        onKeyDown={onKeyDown}
      >
        {selecionada ? (
          <RotuloOpcaoComDiff
            nome={selecionada.plano_nome || selecionada.id}
            acomodacaoRotulo={acomodacaoRotuloOpcao(selecionada)}
            diffCentavos={diffOpcaoNoSubgrupo(matriz, subgrupoId, selecionada.id)}
          />
        ) : (
          <span className="mapping-select-placeholder">Escolha o plano…</span>
        )}
      </button>
      {aberto ? (
        <ul id={listId} role="listbox" className="mapping-select-menu">
          {itens.map((it, idx) => {
            const escolhido = (it.id || "") === (value || "");
            if (it.placeholder) {
              return (
                <li key="__vazio">
                  <button
                    type="button"
                    role="option"
                    aria-selected={escolhido}
                    className={`mapping-select-item${idx === ativo ? " mapping-select-item--ativo" : ""}`}
                    onMouseEnter={() => setAtivo(idx)}
                    onClick={() => escolher("")}
                  >
                    <span className="mapping-select-placeholder">Escolha o plano…</span>
                  </button>
                </li>
              );
            }
            return (
              <li key={it.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={escolhido}
                  className={`mapping-select-item${idx === ativo ? " mapping-select-item--ativo" : ""}`}
                  onMouseEnter={() => setAtivo(idx)}
                  onClick={() => escolher(it.id)}
                >
                  <RotuloOpcaoComDiff
                    nome={it.plano_nome || it.id}
                    acomodacaoRotulo={acomodacaoRotuloOpcao(it)}
                    diffCentavos={diffOpcaoNoSubgrupo(matriz, subgrupoId, it.id)}
                  />
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

export default function PlanosSelecionadosPanel({
  estudoId,
  etapaIndice = 4,
  totalEtapas = 5,
  onSalvo,
  onRegistrarAvanco,
}) {
  const [rascunho, setRascunho] = useState(null);
  const [cenarios, setCenarios] = useState([]);
  const [erro, setErro] = useState(null);
  const [msg, setMsg] = useState(null);
  const [matrizEstimativa, setMatrizEstimativa] = useState(null);

  useEffect(() => {
    if (!estudoId) return;
    obterRascunho(estudoId)
      .then((r) => {
        const sgs = subgruposComVidas(r);
        const iniciais = garantirCenariosIniciais(r, sgs);
        setCenarios(iniciais);
        setRascunho({ ...r });
      })
      .catch((e) => {
        setErro(e.message);
        setRascunho(null);
      });
    obterMatrizEstimativa(estudoId)
      .then(setMatrizEstimativa)
      .catch(() => setMatrizEstimativa(null));
  }, [estudoId]);

  const handleSalvar = useCallback(async () => {
    if (!rascunho) {
      setErro("Adicione planos ao comparativo");
      return false;
    }
    const sgs = subgruposComVidas(rascunho);
    if (sgs.length <= 1) {
      onSalvo?.();
      return true;
    }
    const ops = rascunho.opcoes_proposta || [];
    const lacunas = cenarios.map((c) => lacunasCenario(c, sgs, ops));
    if (lacunas.some((l) => l.length > 0)) {
      setErro(mensagemLacunasAtribuicao(lacunas));
      return false;
    }
    if (!ops.length) {
      setErro("Adicione planos ao comparativo");
      return false;
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
      return true;
    } catch (e) {
      setErro(e.message);
      return false;
    }
  }, [rascunho, cenarios, estudoId, onSalvo]);

  useEffect(() => {
    if (!onRegistrarAvanco) return undefined;
    return onRegistrarAvanco(handleSalvar);
  }, [onRegistrarAvanco, handleSalvar]);

  if (!rascunho) {
    return (
      <section className="etapa-fluxo">
        {erro ? (
          <p className="erro">{erro}</p>
        ) : (
          <p className="muted">Carregando atribuições…</p>
        )}
      </section>
    );
  }

  const subgrupos = subgruposComVidas(rascunho);
  const multiplosPlanosAtuais = subgrupos.length > 1;
  const opcoes = rascunho.opcoes_proposta || [];

  const lacunasPorCenario = cenarios.map((c) =>
    lacunasCenario(c, subgrupos, opcoes)
  );
  const incompleto = lacunasPorCenario.some((l) => l.length > 0);
  const mensagemFalta = incompleto
    ? mensagemLacunasAtribuicao(lacunasPorCenario)
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

  const { divergencias: avisosDivergencia, incompletos: avisosIncompletos } =
    avisosAcomodacaoCenarios(rascunho, cenarios, subgrupos);

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
                  const opcoesSg = opcoesParaDropdown(
                    opcoes,
                    matrizEstimativa,
                    sg.id,
                    opId
                  );
                  const foraDaSelecao = atribuicaoForaDaSelecao(
                    opcoes,
                    matrizEstimativa,
                    sg.id,
                    opId
                  );
                  const acSg = acomodacaoInformada(sg);
                  const acOp = acomodacaoInformada(opSel);
                  const diverge = acSg && acOp && acSg !== acOp;
                  const incompletoAc = (!acSg || !acOp) && opId;
                  const vidasSg = (rascunho.vidas || []).filter(
                    (v) => v.incluida && v.subgrupo_atual_id === sg.id
                  ).length;
                  return (
                    <div
                      key={sg.id}
                      className={`mapping${diverge ? " mapping--aviso" : ""}${incompletoAc ? " mapping--info" : ""}`}
                    >
                      <div className="current">
                        <b>{sg.plano_nome}</b>
                        <small>
                          {sg.operadora || "—"}
                          {vidasSg ? ` · ${vidasSg} vidas` : ""}
                          {acSg ? ` · ${rotuloAcomodacao(acSg)}` : ""}
                        </small>
                      </div>
                      <SelectOpcaoComDiff
                        value={opId}
                        opcoes={opcoesSg}
                        matriz={matrizEstimativa}
                        subgrupoId={sg.id}
                        ariaLabel={`Cotação para ${sg.plano_nome} no cenário ${i + 1}`}
                        onChange={(id) => atualizarAtribuicao(i, sg.id, id)}
                      />
                      {foraDaSelecao && (
                        <p className="alerta alerta-inline">
                          {`«${foraDaSelecao}» não está entre os planos escolhidos para «${sg.plano_nome}» na etapa 3. Escolha um dos planos do grupo ou inclua este na seleção dele.`}
                        </p>
                      )}
                      {incompletoAc && !diverge && (
                        <p className="alerta alerta-inline alerta-inline--info">
                          Acomodação incompleta — informe na etapa «Plano atual» e na conferência
                          do PDF para comparar.
                        </p>
                      )}
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

      {avisosDivergencia.length > 0 && (
        <div className="alerta">
          <strong>Acomodação divergente</strong>
          <ul>
            {avisosDivergencia.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {avisosIncompletos.length > 0 && (
        <div className="notice notice--blue">
          <div className="notice-icon" aria-hidden="true">
            i
          </div>
          <div>
            <strong>Acomodação incompleta</strong>
            <ul>
              {avisosIncompletos.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {mensagemFalta && <p className="alerta">{mensagemFalta}</p>}

      <div className="action-bar">
        <div className="action-left">
          {msg && <span className="action-note ok-inline">{msg}</span>}
          {erro && <span className="action-note erro-inline">{erro}</span>}
        </div>
      </div>
    </section>
  );
}
