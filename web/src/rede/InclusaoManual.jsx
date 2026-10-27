import { useEffect, useRef, useState } from "react";
import { buscarRedeInclusao, incluirRedeManual } from "../api";
import CelulaCobertura from "./CelulaCobertura.jsx";

const MIN_CARACTERES = 2;

function rotuloColuna(col) {
  return col.contrato_atual ? `Contrato atual · ${col.plano_nome}` : `${col.operadora} · ${col.plano_nome}`;
}

/**
 * Busca na BASE INTEIRA (sem recorte e sem filtro de especialidade) para incluir
 * um hospital fora dos principais. Buscar não altera a tabela; só «Incluir» altera.
 */
export default function InclusaoManual({ estudoId, onAtualizado }) {
  const [termo, setTermo] = useState("");
  const [resp, setResp] = useState(null);
  const [buscando, setBuscando] = useState(false);
  const [erro, setErro] = useState(null);
  const [incluindo, setIncluindo] = useState(null);
  const seq = useRef(0);

  async function executar(t) {
    const minha = ++seq.current;
    setBuscando(true);
    setErro(null);
    try {
      const r = await buscarRedeInclusao(estudoId, t);
      if (minha === seq.current) setResp(r);
    } catch (e) {
      if (minha === seq.current) {
        setResp(null);
        setErro(e.message);
      }
    } finally {
      if (minha === seq.current) setBuscando(false);
    }
  }

  useEffect(() => {
    const t = termo.trim();
    if (t.length < MIN_CARACTERES) {
      seq.current += 1;
      setResp(null);
      setErro(null);
      setBuscando(false);
      return undefined;
    }
    const h = setTimeout(() => executar(t), 350);
    return () => clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [termo, estudoId]);

  async function incluir(item) {
    const chave = `${item.prestador}|${item.municipio}|${item.bairro}`;
    setIncluindo(chave);
    setErro(null);
    try {
      const nova = await incluirRedeManual(estudoId, item);
      onAtualizado(nova);
      await executar(termo.trim());
    } catch (e) {
      setErro(e.message);
    } finally {
      setIncluindo(null);
    }
  }

  const colunas = resp?.colunas || [];

  return (
    <div className="incl-manual" data-testid="incl-manual">
      <div className="field">
        <label className="cmp-filtro-label" htmlFor="incl-busca">
          Incluir hospital fora dos principais
        </label>
        <input
          id="incl-busca"
          type="search"
          value={termo}
          onChange={(e) => setTermo(e.target.value)}
          placeholder="Busca na base inteira — nome do hospital (ex.: Einstein)"
          autoComplete="off"
        />
        <p className="incl-manual-ajuda">
          Esta busca não filtra as tabelas abaixo: ela varre a base inteira, todos os municípios
          e todas as especialidades. O hospital incluído entra na tabela de todas as seções
          (menos onde já estiver). Nada entra no documento até você clicar em «Incluir».
        </p>
      </div>

      {buscando && <p className="muted">Buscando…</p>}
      {erro && <p className="erro">{erro}</p>}
      {resp?.aviso && !buscando && <p className="muted">{resp.aviso}</p>}

      {resp && resp.resultados.length > 0 && (
        <ul className="incl-manual-lista">
          {resp.resultados.map((it) => {
            const chave = `${it.prestador}|${it.municipio}|${it.bairro}`;
            const bloqueado = it.ja_na_tabela || it.incluido_manual;
            return (
              <li className="incl-manual-item" key={chave}>
                <div className="incl-manual-topo">
                  <div>
                    <span className="incl-manual-nome">{it.prestador_nome || it.prestador}</span>
                    <span className="incl-manual-local">
                      {it.bairro ? `${it.bairro} · ` : ""}
                      {it.municipio_titulo}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="btn-compacto"
                    disabled={bloqueado || incluindo === chave}
                    onClick={() => incluir(it)}
                  >
                    {incluindo === chave
                      ? "Incluindo…"
                      : it.incluido_manual
                        ? "Incluído"
                        : it.ja_na_tabela
                          ? "Na tabela"
                          : "Incluir"}
                  </button>
                </div>
                <div className="incl-manual-selos">
                  {it.ja_na_tabela && <span className="selo selo--info">Já está na tabela</span>}
                  {!it.ja_na_tabela &&
                    !it.incluido_manual &&
                    (it.secoes_ja_presentes || []).length > 0 &&
                    (it.secoes_a_incluir || []).length > 0 && (
                      <span className="selo selo--info">
                        Já está em: {it.secoes_ja_presentes.join(", ")} · entra em:{" "}
                        {it.secoes_a_incluir.join(", ")}
                      </span>
                    )}
                  {it.incluido_manual && <span className="selo selo--manual">Incluído manualmente</span>}
                  {it.fora_recorte && (
                    <span className="selo selo--aviso">Fora do recorte dos beneficiários</span>
                  )}
                  {it.verticalizado && <span className="selo selo--info">Rede verticalizada</span>}
                  {it.fora_criterio && (
                    <span
                      className="selo selo--fora"
                      title="Sem HGER, HD, PSGER ou MAT em nenhum plano"
                    >
                      Fora do critério padrão
                    </span>
                  )}
                  {it.sem_cobertura && (
                    <span className="selo selo--aviso">
                      Nenhum plano do estudo cobre este hospital — entra com as colunas vazias
                    </span>
                  )}
                </div>
                <div className="incl-manual-cobertura">
                  {colunas.map((c) => {
                    const cod = it.celulas?.[c.chave] || "";
                    return (
                      <span
                        key={c.chave}
                        className={cod ? "incl-chip incl-chip--on" : "incl-chip"}
                        title={rotuloColuna(c)}
                      >
                        <span className="incl-chip-plano">{c.plano_nome}</span>
                        <span className="incl-chip-cod">
                          {cod ? <CelulaCobertura texto={cod} /> : "—"}
                        </span>
                      </span>
                    );
                  })}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
