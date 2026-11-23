import { useEffect, useState } from "react";
import { obterRascunho, salvarRascunho } from "./api";
import { novoId } from "./constants";

export default function CenarioPanel({ estudoId, onSalvo }) {
  const [rascunho, setRascunho] = useState(null);
  const [erro, setErro] = useState(null);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    if (!estudoId) return;
    obterRascunho(estudoId)
      .then((r) => {
        if (!(r.cenarios || []).length) {
          r.cenarios = [
            {
              id: novoId("c"),
              rotulo: "Cenário principal",
              atribuicoes: (r.subgrupos_atuais || []).map((sg) => ({
                id: novoId("a"),
                alvo_tipo: "subgrupo",
                alvo_id: sg.id,
                opcao_plano_id: "",
              })),
            },
          ];
        }
        setRascunho({ ...r });
      })
      .catch((e) => setErro(e.message));
  }, [estudoId]);

  if (!rascunho) return <p className="muted">Carregando associações…</p>;

  const cenario = (rascunho.cenarios || [])[0] || { atribuicoes: [] };

  function atualizarAtribuicao(idx, opcaoId) {
    setRascunho((prev) => {
      const copia = structuredClone(prev);
      copia.cenarios[0].atribuicoes[idx].opcao_plano_id = opcaoId;
      return copia;
    });
  }

  async function handleSalvar() {
    try {
      await salvarRascunho(estudoId, rascunho);
      setMsg("Associações salvas — revise se cada plano atual aponta para a proposta correta.");
      onSalvo?.();
    } catch (e) {
      setErro(e.message);
    }
  }

  return (
    <section className="cartao">
      <h2>Associação dos planos</h2>
      <p className="muted">
        Vincule cada plano atual à proposta correspondente. A correspondência não é automática —
        confirme manualmente.
      </p>

      {(rascunho.subgrupos_atuais || []).length === 0 && (
        <p className="erro">Nenhum plano atual para associar.</p>
      )}
      {(rascunho.opcoes_proposta || []).length === 0 && (
        <p className="erro">Cadastre propostas na etapa anterior.</p>
      )}

      <table className="conferencia">
        <thead>
          <tr>
            <th>Plano atual</th>
            <th>Operadora</th>
            <th>Proposta associada</th>
          </tr>
        </thead>
        <tbody>
          {(rascunho.subgrupos_atuais || []).map((sg) => {
            const atrIdx = cenario.atribuicoes.findIndex((a) => a.alvo_id === sg.id);
            const atr =
              atrIdx >= 0
                ? cenario.atribuicoes[atrIdx]
                : null;
            return (
              <tr key={sg.id}>
                <td>{sg.plano_nome}</td>
                <td>{sg.operadora}</td>
                <td>
                  <select
                    value={atr?.opcao_plano_id || ""}
                    onChange={(e) => {
                      if (atrIdx >= 0) {
                        atualizarAtribuicao(atrIdx, e.target.value);
                      } else {
                        setRascunho((prev) => {
                          const copia = structuredClone(prev);
                          copia.cenarios[0].atribuicoes.push({
                            id: novoId("a"),
                            alvo_tipo: "subgrupo",
                            alvo_id: sg.id,
                            opcao_plano_id: e.target.value,
                          });
                          return copia;
                        });
                      }
                    }}
                  >
                    <option value="">Selecione a proposta…</option>
                    {(rascunho.opcoes_proposta || []).map((op) => (
                      <option key={op.id} value={op.id}>
                        {op.operadora} — {op.plano_nome}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <button type="button" onClick={handleSalvar} style={{ marginTop: "1rem" }}>
        Salvar associações
      </button>
      {msg && <p className="ok">{msg}</p>}
      {erro && <p className="erro">{erro}</p>}
    </section>
  );
}
