import { useEffect, useState } from "react";
import { obterRascunho, salvarRascunho } from "./api";
import { novoId } from "./constants";

function subgrupoDaOpcao(cenarios, opcaoId) {
  for (const c of cenarios) {
    const atr = c.atribuicoes.find((a) => a.opcao_plano_id === opcaoId);
    if (atr) return atr.alvo_id;
  }
  return "";
}

function cenarioDaOpcao(cenarios, opcaoId) {
  for (const c of cenarios) {
    if (c.atribuicoes.some((a) => a.opcao_plano_id === opcaoId)) return c;
  }
  return null;
}

function montarCenarios(rascunho, mapaOpcaoSubgrupo) {
  const { subgrupos_atuais, opcoes_proposta, cenarios } = rascunho;
  if (!opcoes_proposta.length) return cenarios;

  return opcoes_proposta
    .map((op, i) => {
      const sgId =
        subgrupos_atuais.length === 1
          ? subgrupos_atuais[0].id
          : mapaOpcaoSubgrupo[op.id];
      if (!sgId) return null;

      const existente = cenarioDaOpcao(cenarios, op.id);
      const atrExistente = existente?.atribuicoes[0];

      return {
        id: existente?.id || cenarios[i]?.id || novoId("c"),
        rotulo: op.plano_nome || `Comparativo ${i + 1}`,
        atribuicoes: [
          {
            id: atrExistente?.id || novoId("a"),
            alvo_tipo: "subgrupo",
            alvo_id: sgId,
            opcao_plano_id: op.id,
          },
        ],
      };
    })
    .filter(Boolean);
}

export default function PlanosSelecionadosPanel({ estudoId, onSalvo }) {
  const [rascunho, setRascunho] = useState(null);
  const [mapaOpcaoSubgrupo, setMapaOpcaoSubgrupo] = useState({});
  const [erro, setErro] = useState(null);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    if (!estudoId) return;
    obterRascunho(estudoId)
      .then((r) => {
        const mapa = {};
        for (const op of r.opcoes_proposta) {
          mapa[op.id] = subgrupoDaOpcao(r.cenarios, op.id);
        }
        setMapaOpcaoSubgrupo(mapa);
        setRascunho({ ...r });
      })
      .catch((e) => setErro(e.message));
  }, [estudoId]);

  if (!rascunho) return <p className="muted">Carregando correspondências…</p>;

  const multiplosPlanosAtuais = rascunho.subgrupos_atuais.length > 1;

  function atualizarComparacao(opcaoId, subgrupoId) {
    setMapaOpcaoSubgrupo((prev) => ({ ...prev, [opcaoId]: subgrupoId }));
  }

  async function handleSalvar() {
    setErro(null);
    try {
      const copia = structuredClone(rascunho);
      copia.cenarios = montarCenarios(copia, mapaOpcaoSubgrupo);
      await salvarRascunho(estudoId, copia);
      setRascunho(copia);
      setMsg("Correspondências confirmadas.");
      onSalvo?.();
    } catch (e) {
      setErro(e.message);
    }
  }

  const comparacaoIncompleta =
    multiplosPlanosAtuais &&
    rascunho.opcoes_proposta.some((op) => !mapaOpcaoSubgrupo[op.id]);

  return (
    <section className="secao-fluxo">
      <h2>Correspondência com os planos atuais</h2>
      <p className="lead">
        Indique com qual contrato vigente cada proposta será comparada. Todas as opções precisam de
        correspondência antes do cálculo.
      </p>

      {rascunho.opcoes_proposta.length === 0 && (
        <p className="alerta">Nenhum plano no comparativo — volte a «Cotações» e adicione opções.</p>
      )}

      <ul className="lista-planos-comparativo">
        {rascunho.opcoes_proposta.map((op) => (
          <li key={op.id} className="plano-comparativo-item">
            <div className="plano-comparativo-cabecalho">
              <strong>{op.plano_nome || "Plano sem nome"}</strong>
              <span className="badge badge--ok">Adicionado ao comparativo</span>
            </div>
            <p className="muted">
              {op.operadora || "—"}
              {op.extracao_id ? " · importado de PDF" : " · entrada manual"}
            </p>

            <label>
              Com qual plano atual deseja comparar esta opção?
              <select
                value={mapaOpcaoSubgrupo[op.id] || ""}
                onChange={(e) => atualizarComparacao(op.id, e.target.value)}
              >
                <option value="">Selecione…</option>
                {rascunho.subgrupos_atuais.map((sg) => (
                  <option key={sg.id} value={sg.id}>
                    {sg.plano_nome} ({sg.operadora})
                  </option>
                ))}
              </select>
            </label>
          </li>
        ))}
      </ul>

      {comparacaoIncompleta && (
        <p className="alerta">Selecione o plano atual para cada opção antes de confirmar.</p>
      )}

      <button type="button" onClick={handleSalvar} disabled={comparacaoIncompleta}>
        Confirmar correspondências
      </button>
      {msg && <p className="ok">{msg}</p>}
      {erro && <p className="erro">{erro}</p>}
    </section>
  );
}
