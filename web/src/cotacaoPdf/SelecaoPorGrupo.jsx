import { useCallback, useEffect, useMemo, useState } from "react";

import {
  mensagemErroOperador,
  obterSelecaoPorGrupo,
  salvarSelecaoPorGrupo,
} from "../api";
import {
  abreviarAcomodacao,
  textoConfirmacaoRemocao,
  textoRelatoRemocao,
} from "./utils.js";
import {
  alternarPlano,
  avisoSelecaoVazia,
  visaoSelecaoPorGrupo,
  seloGrupo,
  subtituloGrupo,
  textoResumoGrupo,
  planosAtribuidosDoGrupo,
} from "./selecaoPorGrupo.js";

function AbaGrupo({ grupo, ativo, onSelecionar }) {
  const selo = seloGrupo(grupo);
  return (
    <button
      type="button"
      className="grupo-aba"
      aria-current={ativo ? "page" : undefined}
      onClick={() => onSelecionar(grupo.subgrupo_id)}
    >
      <span className="grupo-aba-nome">{grupo.plano_nome}</span>
      <span className="grupo-aba-sub">{subtituloGrupo(grupo)}</span>
      <span
        className={`grupo-aba-selo ${
          selo.vazio ? "selo-vazio" : selo.herdado ? "selo-herdado" : "selo-ok"
        }`}
      >
        {selo.texto}
      </span>
    </button>
  );
}

export default function SelecaoPorGrupo({
  estudoId,
  onAlterado,
  exigeSelecaoPorGrupo = false,
  grupoAtivo,
  onSelecionarGrupo,
  recargaChave,
  somenteAbas = false,
  esconderAbas = false,
}) {
  const [selecao, setSelecao] = useState(null);
  const [subgrupoAtivo, setSubgrupoAtivo] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState(null);
  const [relato, setRelato] = useState(null);

  const recarregar = useCallback(async () => {
    try {
      const resp = await obterSelecaoPorGrupo(estudoId);
      setErro(null);
      setSelecao(resp);
      return resp;
    } catch (err) {
      setSelecao(null);
      setErro(mensagemErroOperador(err, "Não foi possível carregar a seleção por grupo."));
      return null;
    }
  }, [estudoId]);

  useEffect(() => {
    recarregar();
  }, [recarregar, recargaChave]);

  useEffect(() => {
    const grupos = selecao?.grupos || [];
    if (grupoAtivo && grupos.some((g) => g.subgrupo_id === grupoAtivo)) {
      if (subgrupoAtivo !== grupoAtivo) setSubgrupoAtivo(grupoAtivo);
      return;
    }
    if (grupos.length && !grupos.some((g) => g.subgrupo_id === subgrupoAtivo)) {
      setSubgrupoAtivo(grupos[0].subgrupo_id);
    }
  }, [selecao, subgrupoAtivo, grupoAtivo]);

  const grupo = useMemo(
    () => (selecao?.grupos || []).find((g) => g.subgrupo_id === subgrupoAtivo),
    [selecao, subgrupoAtivo]
  );

  async function gravar(opcaoIds, { confirmarRemocoes = false } = {}) {
    setSalvando(true);
    setErro(null);
    try {
      let resp;
      try {
        resp = await salvarSelecaoPorGrupo(estudoId, {
          subgrupoId: subgrupoAtivo,
          opcaoIds,
          confirmarRemocoes,
        });
      } catch (err) {
        if (!err.impactoRemocao) throw err;
        // Nada foi gravado ainda — mesma porta da re-aplicação de PDF.
        if (!window.confirm(textoConfirmacaoRemocao(err.impactoRemocao))) {
          await recarregar();
          return;
        }
        resp = await salvarSelecaoPorGrupo(estudoId, {
          subgrupoId: subgrupoAtivo,
          opcaoIds,
          confirmarRemocoes: true,
        });
      }
      setSelecao(resp.selecao);
      setRelato(resp.impacto_remocao ? textoRelatoRemocao(resp.impacto_remocao) : null);
      onAlterado?.();
    } catch (err) {
      setErro(mensagemErroOperador(err, "Não foi possível gravar a seleção."));
    } finally {
      setSalvando(false);
    }
  }

  const visao = visaoSelecaoPorGrupo(selecao, erro, exigeSelecaoPorGrupo);
  if (visao !== "tela") {
    if (visao === "erro") {
      return (
        <section className="selecao-grupo cartao">
          <p className="erro">{erro}</p>
        </section>
      );
    }
    return null;
  }

  const catalogoVazio = (selecao.total_catalogo || 0) === 0;
  const planosAtribuidos = planosAtribuidosDoGrupo(grupo);
  const aviso =
    grupo && grupo.selecao_propria && !catalogoVazio
      ? avisoSelecaoVazia(planosAtribuidos.map((p) => p.opcao_id))
      : null;

  function escolherGrupo(id) {
    setSubgrupoAtivo(id);
    onSelecionarGrupo?.(id);
  }

  return (
    <section className="selecao-grupo cartao">
      {!esconderAbas && (
        <header className="selecao-grupo-cabecalho">
          <span className="selecao-grupo-titulo">Planos por grupo de beneficiários</span>
          <span className="muted">
            Cada grupo compete com os planos que você escolher para ele
          </span>
        </header>
      )}

      {!esconderAbas && (
        <div className="grupo-abas">
          {(selecao.grupos || []).map((g) => (
            <AbaGrupo
              key={g.subgrupo_id}
              grupo={g}
              ativo={g.subgrupo_id === subgrupoAtivo}
              onSelecionar={escolherGrupo}
            />
          ))}
        </div>
      )}

      {grupo && <p className="selecao-grupo-contexto">{textoResumoGrupo(grupo)}</p>}

      {catalogoVazio && !somenteAbas && (
        <p className="muted">
          Importe as cotações e, em cada aba, marque os planos daquele grupo. Um
          único confirmar grava os dois.
        </p>
      )}

      {grupo && !grupo.selecao_propria && !catalogoVazio && !somenteAbas && (
        <p className="muted">Este grupo ainda não recebeu planos nesta etapa.</p>
      )}

      {grupo && grupo.selecao_propria && planosAtribuidos.length === 0 && !catalogoVazio && !somenteAbas && (
        <p className="muted">Nenhum plano atribuído a este grupo.</p>
      )}

      {grupo && planosAtribuidos.length > 0 && !somenteAbas && (
        <table className="tabela-selecao-grupo">
          <thead>
            <tr>
              <th>Plano</th>
              <th>Acom.</th>
              <th>Mensal est.</th>
              <th>Δ R$</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {planosAtribuidos.map((p) => (
              <tr key={p.opcao_id} className="linha-escolhida">
                <td>
                  <label className="selecao-grupo-plano">
                    <input
                      type="checkbox"
                      checked
                      disabled={salvando}
                      onChange={() => gravar(alternarPlano(grupo, p.opcao_id))}
                    />
                    <span>
                      <span className="plano-nome">{p.plano_nome || p.opcao_id}</span>
                      {p.operadora && <span className="plano-operadora">{p.operadora}</span>}
                    </span>
                  </label>
                </td>
                <td>{abreviarAcomodacao(p.acomodacao) || "—"}</td>
                <td className="n">{p.estimado_reais || "—"}</td>
                <td className={`n ${p.diff_centavos < 0 ? "delta-neg" : p.diff_centavos > 0 ? "delta-pos" : ""}`}>
                  {p.diff_reais || "—"}
                </td>
                <td>
                  <span className="tag tag-escolhido">Atribuído</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {aviso && !somenteAbas && <p className="alerta-inline">{aviso}</p>}
      {relato && !somenteAbas && (
        <div className="pendencias-box">
          <strong>Planos removidos do comparativo</strong>
          <p>{relato}</p>
        </div>
      )}
      {erro && <p className="erro">{erro}</p>}
    </section>
  );
}
