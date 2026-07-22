import { useCallback, useEffect, useState } from "react";
import {
  confirmarLoteSiscor,
  criarEstudo,
  importarSiscor,
  listarEstudos,
  obterConferenciaSiscor,
  atualizarLinhaSiscor,
} from "./api";

function centavosParaReais(centavos) {
  if (centavos == null) return "—";
  return (centavos / 100).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function reaisParaCentavos(texto) {
  if (!texto || !String(texto).trim()) return null;
  const n = Number(String(texto).replace(/\./g, "").replace(",", "."));
  if (Number.isNaN(n)) return null;
  return Math.round(n * 100);
}

export default function SiscorPanel({ estudoId, onEstudoId, onEstudosChange }) {
  const [estudos, setEstudos] = useState([]);
  const [novoId, setNovoId] = useState("");
  const [novoTitulo, setNovoTitulo] = useState("");
  const [arquivo, setArquivo] = useState(null);
  const [conferencia, setConferencia] = useState(null);
  const [reimportOpções, setReimportOpções] = useState(null);
  const [editando, setEditando] = useState(null);
  const [erro, setErro] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [msg, setMsg] = useState(null);

  const recarregarEstudos = useCallback(() => {
    listarEstudos()
      .then(setEstudos)
      .catch((e) => setErro(e.message));
  }, []);

  const recarregarConferencia = useCallback(() => {
    if (!estudoId) return;
    obterConferenciaSiscor(estudoId)
      .then(setConferencia)
      .catch(() => setConferencia(null));
  }, [estudoId]);

  useEffect(() => {
    recarregarEstudos();
  }, [recarregarEstudos]);

  useEffect(() => {
    recarregarConferencia();
  }, [recarregarConferencia]);

  async function handleCriarEstudo(e) {
    e.preventDefault();
    setErro(null);
    setCarregando(true);
    try {
      await criarEstudo(novoId.trim(), novoTitulo.trim() || novoId.trim());
      onEstudoId(novoId.trim());
      setNovoId("");
      setNovoTitulo("");
      recarregarEstudos();
      onEstudosChange?.();
      setMsg("Estudo criado.");
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
    }
  }

  async function executarImportacao(modo) {
    if (!arquivo || !estudoId) return;
    setErro(null);
    setCarregando(true);
    setReimportOpções(null);
    try {
      const res = await importarSiscor(estudoId, arquivo, { modo });
      if (!res.sucesso) {
        setErro(
          res.erros_arquivo?.[0]?.mensagem || "Planilha rejeitada pelo importador."
        );
        return;
      }
      setMsg(`Importação v${res.resumo?.versao} registrada.`);
      recarregarConferencia();
      onEstudosChange?.();
    } catch (err) {
      if (err.status === 409 && err.opcoes?.length) {
        setReimportOpções(err.opcoes);
      } else {
        setErro(err.message);
      }
    } finally {
      setCarregando(false);
    }
  }

  async function handleImportar() {
    await executarImportacao(undefined);
  }

  async function handleConfirmarLote() {
    setCarregando(true);
    setErro(null);
    try {
      const res = await confirmarLoteSiscor(estudoId);
      setMsg(
        `${res.confirmadas} confirmada(s); ${res.excecoes_restantes} exceção(ões) restante(s).`
      );
      recarregarConferencia();
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
    }
  }

  async function handleConfirmarLinha(linhaId) {
    setCarregando(true);
    try {
      await atualizarLinhaSiscor(estudoId, linhaId, { confirmar: true });
      recarregarConferencia();
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
    }
  }

  async function handleSalvarEdicao(e) {
    e.preventDefault();
    if (!editando) return;
    setCarregando(true);
    setErro(null);
    const patch = {
      segurado: editando.segurado,
      nascimento: editando.nascimento,
      parentesco_texto: editando.parentesco_texto,
      plano: editando.plano,
      operadora: editando.operadora,
      status_texto: editando.status_texto,
      incluida: editando.incluida_sugerida,
      excluida: editando.excluida,
      motivo_exclusao: editando.motivo_exclusao || null,
    };
    const centavos = reaisParaCentavos(editando.valor_reais);
    if (centavos != null) patch.valor_centavos = centavos;
    try {
      await atualizarLinhaSiscor(estudoId, editando.id, patch);
      setEditando(null);
      recarregarConferencia();
      setMsg("Linha atualizada — confirme novamente se necessário.");
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
    }
  }

  const stats = conferencia?.estatisticas;

  return (
    <section className="cartao siscor">
      <h2>Importação SISCOR</h2>
      <p className="muted">
        Importe a planilha piloto, revise exceções e confirme vidas antes do comparativo.
      </p>

      <form className="form-linha" onSubmit={handleCriarEstudo}>
        <div className="grid-2">
          <label>
            Novo estudo (id)
            <input value={novoId} onChange={(e) => setNovoId(e.target.value)} />
          </label>
          <label>
            Título
            <input value={novoTitulo} onChange={(e) => setNovoTitulo(e.target.value)} />
          </label>
        </div>
        <button type="submit" disabled={carregando || !novoId.trim()}>
          Criar estudo vazio
        </button>
      </form>

      <label htmlFor="estudo-siscor">Estudo ativo</label>
      <select
        id="estudo-siscor"
        value={estudoId}
        onChange={(e) => onEstudoId(e.target.value)}
      >
        {estudos.map((id) => (
          <option key={id} value={id}>
            {id}
          </option>
        ))}
      </select>

      <div className="importacao">
        <label>
          Planilha .xlsx
          <input
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(e) => setArquivo(e.target.files?.[0] || null)}
          />
        </label>
        <button
          type="button"
          onClick={handleImportar}
          disabled={carregando || !arquivo || !estudoId}
        >
          Importar SISCOR
        </button>
      </div>

      {reimportOpções && (
        <div className="reimportacao">
          <p>Reimportação detectada. Escolha conscientemente:</p>
          {reimportOpções.map((op) => (
            <button
              key={op}
              type="button"
              className="secundario"
              disabled={carregando}
              onClick={() => executarImportacao(op)}
            >
              {op === "substituir" ? "Substituir candidata" : "Nova versão candidata"}
            </button>
          ))}
        </div>
      )}

      {stats && (
        <div className="stats">
          <span>{stats.total_linhas_lidas} linhas</span>
          <span>{stats.planos_detectados} plano(s)</span>
          <span>{stats.linhas_com_excecao} exceção(ões)</span>
          <span>{stats.confirmadas} confirmada(s)</span>
        </div>
      )}

      {conferencia && (
        <>
          <div className="acoes-lote">
            <button type="button" onClick={handleConfirmarLote} disabled={carregando}>
              Confirmar lote (sem exceções)
            </button>
          </div>
          <div className="tabela-scroll">
            <table className="conferencia">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Segurado</th>
                  <th>Plano</th>
                  <th>Valor</th>
                  <th>Status</th>
                  <th>Alertas</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {conferencia.linhas.map((linha) => (
                  <tr
                    key={linha.id}
                    className={[
                      linha.excluida ? "linha-excluida" : "",
                      linha.alertas?.length ? "linha-excecao" : "",
                      linha.registro_confirmado ? "linha-confirmada" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <td>{linha.numero_linha}</td>
                    <td>{linha.segurado || "—"}</td>
                    <td>{linha.plano || "—"}</td>
                    <td>{centavosParaReais(linha.valor_centavos)}</td>
                    <td>{linha.status_texto || "—"}</td>
                    <td>
                      {linha.alertas?.length ? (
                        <ul className="alertas-inline">
                          {linha.alertas.map((a) => (
                            <li key={a.codigo}>{a.codigo}</li>
                          ))}
                        </ul>
                      ) : (
                        "OK"
                      )}
                    </td>
                    <td className="acoes-celula">
                      <button
                        type="button"
                        className="link"
                        onClick={() =>
                          setEditando({
                            ...linha,
                            valor_reais:
                              linha.valor_centavos != null
                                ? (linha.valor_centavos / 100).toFixed(2).replace(".", ",")
                                : "",
                          })
                        }
                      >
                        Editar
                      </button>
                      {!linha.registro_confirmado && !linha.excluida && (
                        <button
                          type="button"
                          className="link"
                          disabled={linha.alertas?.length > 0}
                          onClick={() => handleConfirmarLinha(linha.id)}
                        >
                          Confirmar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {editando && (
        <form className="cartao cartao--edit" onSubmit={handleSalvarEdicao}>
          <h3>Editar linha {editando.numero_linha}</h3>
          <div className="grid-2">
            <label>
              Segurado
              <input
                value={editando.segurado || ""}
                onChange={(e) => setEditando({ ...editando, segurado: e.target.value })}
              />
            </label>
            <label>
              Nascimento (AAAA-MM-DD)
              <input
                value={editando.nascimento || ""}
                onChange={(e) => setEditando({ ...editando, nascimento: e.target.value })}
              />
            </label>
            <label>
              Parentesco
              <input
                value={editando.parentesco_texto || ""}
                onChange={(e) =>
                  setEditando({ ...editando, parentesco_texto: e.target.value })
                }
              />
            </label>
            <label>
              Plano
              <input
                value={editando.plano || ""}
                onChange={(e) => setEditando({ ...editando, plano: e.target.value })}
              />
            </label>
            <label>
              Operadora
              <input
                value={editando.operadora || ""}
                onChange={(e) => setEditando({ ...editando, operadora: e.target.value })}
              />
            </label>
            <label>
              Status
              <input
                value={editando.status_texto || ""}
                onChange={(e) => setEditando({ ...editando, status_texto: e.target.value })}
              />
            </label>
            <label>
              Valor (R$)
              <input
                value={editando.valor_reais || ""}
                onChange={(e) => setEditando({ ...editando, valor_reais: e.target.value })}
              />
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={editando.incluida_sugerida}
                onChange={(e) =>
                  setEditando({ ...editando, incluida_sugerida: e.target.checked })
                }
              />
              Incluída no estudo
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={editando.excluida}
                onChange={(e) => setEditando({ ...editando, excluida: e.target.checked })}
              />
              Excluída da importação
            </label>
          </div>
          {editando.excluida && (
            <label>
              Motivo da exclusão (obrigatório)
              <input
                required
                value={editando.motivo_exclusao || ""}
                onChange={(e) =>
                  setEditando({ ...editando, motivo_exclusao: e.target.value })
                }
              />
            </label>
          )}
          <div className="acoes-edit">
            <button type="submit" disabled={carregando}>
              Salvar edição
            </button>
            <button type="button" className="secundario" onClick={() => setEditando(null)}>
              Cancelar
            </button>
          </div>
        </form>
      )}

      {msg && <p className="ok">{msg}</p>}
      {erro && <p className="erro">{erro}</p>}
    </section>
  );
}
