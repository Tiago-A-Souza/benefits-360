import { useCallback, useEffect, useState } from "react";
import {
  confirmarLoteSiscor,
  importarSiscor,
  obterConferenciaSiscor,
  atualizarLinhaSiscor,
} from "./api";
import FilePickerButton from "./components/FilePickerButton";
import { centavosParaReaisExibicao, reaisTextoParaCentavos } from "./money";

export default function SiscorPanel({ estudoId, onAtualizado }) {
  const [conferencia, setConferencia] = useState(null);
  const [reimportOpções, setReimportOpções] = useState(null);
  const [detalheAberto, setDetalheAberto] = useState(false);
  const [editando, setEditando] = useState(null);
  const [excluindo, setExcluindo] = useState(null);
  const [motivoExclusao, setMotivoExclusao] = useState("");
  const [erro, setErro] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [msg, setMsg] = useState(null);
  const [arrastando, setArrastando] = useState(false);

  const recarregarConferencia = useCallback(() => {
    if (!estudoId) return;
    obterConferenciaSiscor(estudoId)
      .then(setConferencia)
      .catch(() => setConferencia(null))
      .finally(() => onAtualizado?.());
  }, [estudoId, onAtualizado]);

  useEffect(() => {
    recarregarConferencia();
  }, [recarregarConferencia]);

  async function executarImportacao(modo, arquivo) {
    if (!arquivo || !estudoId) return;
    setErro(null);
    setCarregando(true);
    setReimportOpções(null);
    try {
      const res = await importarSiscor(estudoId, arquivo, { modo });
      if (!res.sucesso) {
        setErro(res.erros_arquivo?.[0]?.mensagem || "Planilha rejeitada pelo importador.");
        return;
      }
      setMsg(`Base importada (versão ${res.resumo?.versao}).`);
      recarregarConferencia();
    } catch (err) {
      if (err.status === 409 && err.opcoes?.length) {
        setReimportOpções({ opcoes: err.opcoes, arquivo });
      } else {
        setErro(err.message);
      }
    } finally {
      setCarregando(false);
    }
  }

  async function handleConfirmarLote() {
    setCarregando(true);
    setErro(null);
    try {
      const res = await confirmarLoteSiscor(estudoId);
      const texto =
        res.mensagem ||
        `${res.confirmadas} confirmada(s); ${res.excecoes_restantes} exceção(ões) restante(s).`;
      setMsg(texto);
      recarregarConferencia();
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
    }
  }

  const stats = conferencia?.estatisticas;
  const titulares = stats?.qtd_titulares ?? 0;
  const dependentes = stats?.qtd_dependentes ?? 0;
  const semParentesco = stats?.qtd_sem_parentesco ?? 0;
  const excluidas = stats?.qtd_excluidas ?? 0;
  const temBase = Boolean(stats);

  function abrirEdicao(linha) {
    setEditando({
      ...linha,
      valor_reais:
        linha.valor_centavos != null ? centavosParaReaisExibicao(linha.valor_centavos) : "",
    });
  }

  async function executarExclusao(e) {
    e.preventDefault();
    const motivo = motivoExclusao.trim();
    if (!motivo) {
      setErro("Informe o motivo ao excluir uma vida.");
      return;
    }
    setErro(null);
    setCarregando(true);
    try {
      await atualizarLinhaSiscor(estudoId, excluindo.id, {
        excluida: true,
        motivo_exclusao: motivo,
      });
      setExcluindo(null);
      setMotivoExclusao("");
      setMsg("Beneficiário excluído do estudo.");
      recarregarConferencia();
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
    }
  }

  async function reverterExclusao(linha) {
    setErro(null);
    setCarregando(true);
    try {
      await atualizarLinhaSiscor(estudoId, linha.id, { excluida: false });
      setMsg("Exclusão revertida.");
      recarregarConferencia();
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
    }
  }

  return (
    <section className="secao-fluxo">
      <header className="secao-fluxo-cabecalho">
        <h2>Importar base atual da empresa</h2>
        <p className="lead">
          Envie a Posição Cadastral do SISCOR. O sistema utilizará beneficiários, nascimento,
          parentesco, plano e valor atual para preparar a renovação.
        </p>
      </header>

      <div
        className={[
          "upload-zona",
          temBase ? "upload-zona--compacto" : "",
          arrastando ? "upload-zona--ativa" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        onDragOver={(e) => {
          e.preventDefault();
          setArrastando(true);
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={(e) => {
          e.preventDefault();
          setArrastando(false);
          const f = e.dataTransfer.files?.[0];
          if (f) executarImportacao(undefined, f);
        }}
      >
        <div className="upload-zona-conteudo">
          <span className="upload-zona-icone" aria-hidden="true">
            ↑
          </span>
          <div className="upload-zona-texto">
            <FilePickerButton
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              disabled={carregando || !estudoId}
              onFiles={(files) => executarImportacao(undefined, files[0])}
            >
              {carregando
                ? "Importando…"
                : temBase
                  ? "Substituir planilha do SISCOR"
                  : "Selecionar planilha do SISCOR"}
            </FilePickerButton>
            <p className="upload-dica muted">
              {temBase
                ? "Arraste um novo .xlsx para substituir a base importada."
                : "Ou arraste o arquivo .xlsx para esta área."}
            </p>
          </div>
        </div>
      </div>

      {reimportOpções && (
        <div className="reimportacao cartao cartao--interno">
          <p className="reimportacao-titulo">Reimportação detectada. Como deseja proceder?</p>
          <div className="reimportacao-acoes">
            {reimportOpções.opcoes.map((op) => (
              <button
                key={op}
                type="button"
                className="secundario btn-compacto"
                disabled={carregando}
                onClick={() => executarImportacao(op, reimportOpções.arquivo)}
              >
                {op === "substituir" ? "Substituir base anterior" : "Manter como nova versão"}
              </button>
            ))}
          </div>
        </div>
      )}

      {stats && (
        <div className="resumo-importacao">
          <div className="resumo-kpi">
            <span className="resumo-kpi-valor">{stats.total_linhas_lidas}</span>
            <span className="resumo-kpi-rotulo">Vidas</span>
          </div>
          <div className="resumo-kpi">
            <span className="resumo-kpi-valor">{titulares}</span>
            <span className="resumo-kpi-rotulo">Titulares</span>
          </div>
          <div className="resumo-kpi">
            <span className="resumo-kpi-valor">{dependentes}</span>
            <span className="resumo-kpi-rotulo">Dependentes</span>
          </div>
          {semParentesco > 0 && (
            <div className="resumo-kpi">
              <span className="resumo-kpi-valor">{semParentesco}</span>
              <span className="resumo-kpi-rotulo">Sem parentesco</span>
            </div>
          )}
          {excluidas > 0 && (
            <div className="resumo-kpi resumo-kpi--alerta">
              <span className="resumo-kpi-valor">{excluidas}</span>
              <span className="resumo-kpi-rotulo">Excluídas</span>
            </div>
          )}
          <div className="resumo-kpi">
            <span className="resumo-kpi-valor">{stats.planos_detectados}</span>
            <span className="resumo-kpi-rotulo">Planos</span>
          </div>
          <div
            className={`resumo-kpi${
              stats.linhas_com_excecao > 0 ? " resumo-kpi--alerta" : " resumo-kpi--ok"
            }`}
          >
            <span className="resumo-kpi-valor">{stats.linhas_com_excecao}</span>
            <span className="resumo-kpi-rotulo">Exceções</span>
          </div>
        </div>
      )}

      {conferencia && detalheAberto && (
        <div className="beneficiarios-painel cartao cartao--interno">
          <div className="beneficiarios-painel-cabecalho">
            <h3>Beneficiários importados</h3>
            <button type="button" className="link" onClick={() => setDetalheAberto(false)}>
              Ocultar
            </button>
          </div>
          <div className="tabela-scroll">
            <table className="conferencia">
              <thead>
                <tr>
                  <th>Segurado</th>
                  <th>Plano</th>
                  <th>Valor</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {conferencia.linhas.map((linha) => (
                  <tr
                    key={linha.id}
                    className={[
                      linha.excluida ? "linha-excluida" : "",
                      !linha.excluida && linha.alertas?.length ? "linha-excecao" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <td>{linha.segurado || "—"}</td>
                    <td>{linha.plano || "—"}</td>
                    <td>{centavosParaReaisExibicao(linha.valor_centavos)}</td>
                    <td>
                      {linha.excluida ? (
                        <>
                          Excluída
                          {linha.motivo_exclusao && (
                            <span className="muted"> — {linha.motivo_exclusao}</span>
                          )}
                        </>
                      ) : (
                        linha.registro_confirmado ? "Confirmado" : linha.status_texto || "—"
                      )}
                    </td>
                    <td className="acoes-celula">
                      {linha.excluida ? (
                        <button
                          type="button"
                          className="link"
                          disabled={carregando}
                          onClick={() => reverterExclusao(linha)}
                        >
                          Reverter exclusão
                        </button>
                      ) : (
                        <>
                          <button type="button" className="link" onClick={() => abrirEdicao(linha)}>
                            Editar
                          </button>
                          <button
                            type="button"
                            className="link"
                            onClick={() => {
                              setExcluindo(linha);
                              setMotivoExclusao("");
                              setErro(null);
                            }}
                          >
                            Excluir do estudo
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {excluindo && (
        <form className="cartao cartao--edit" onSubmit={executarExclusao}>
          <h3>Excluir do estudo</h3>
          <p className="muted">
            A vida permanece visível na conferência, mas não entrará no cálculo. Informe o motivo.
          </p>
          <p>
            <strong>{excluindo.segurado || "Beneficiário sem nome"}</strong>
            {excluindo.plano ? ` — ${excluindo.plano}` : ""}
          </p>
          <label>
            Motivo da exclusão
            <textarea
              required
              rows={3}
              value={motivoExclusao}
              onChange={(e) => setMotivoExclusao(e.target.value)}
              placeholder="Ex.: beneficiário desligado, plano encerrado…"
            />
          </label>
          <div className="acoes-edit">
            <button type="submit" disabled={carregando}>
              Confirmar exclusão
            </button>
            <button
              type="button"
              className="secundario"
              disabled={carregando}
              onClick={() => {
                setExcluindo(null);
                setMotivoExclusao("");
              }}
            >
              Cancelar
            </button>
          </div>
        </form>
      )}

      {editando && (
        <form
          className="cartao cartao--edit"
          onSubmit={async (e) => {
            e.preventDefault();
            const nomeVazio = !(editando.segurado || "").trim();
            const valorVazio = !(editando.valor_reais || "").trim();
            if (nomeVazio || valorVazio) {
              const ok = window.confirm(
                "Esta linha ficará com exceção e não entrará no cálculo. Confirmar?"
              );
              if (!ok) return;
            }
            setErro(null);
            setCarregando(true);
            try {
              const patch = {
                segurado: editando.segurado ?? "",
                plano: editando.plano,
              };
              if (valorVazio) {
                patch.valor_centavos = null;
              } else {
                const parsed = reaisTextoParaCentavos(editando.valor_reais);
                if (!parsed.ok) {
                  setErro(parsed.erro);
                  return;
                }
                patch.valor_centavos = parsed.centavos;
              }
              await atualizarLinhaSiscor(estudoId, editando.id, patch);
              setEditando(null);
              recarregarConferencia();
            } catch (err) {
              setErro(err.message);
            } finally {
              setCarregando(false);
            }
          }}
        >
          <h3>Editar beneficiário</h3>
          <label>
            Nome
            <input
              value={editando.segurado || ""}
              onChange={(e) => setEditando({ ...editando, segurado: e.target.value })}
            />
          </label>
          <label>
            Valor (R$)
            <input
              value={editando.valor_reais || ""}
              onChange={(e) => setEditando({ ...editando, valor_reais: e.target.value })}
            />
          </label>
          <div className="acoes-edit">
            <button type="submit">Salvar</button>
            <button type="button" className="secundario" onClick={() => setEditando(null)}>
              Cancelar
            </button>
          </div>
        </form>
      )}

      {conferencia && (
        <footer className="secao-fluxo-rodape siscor-fluxo-rodape">
          <div className="siscor-fluxo-info">
            {msg && <p className="ok">{msg}</p>}
            {erro && <p className="erro">{erro}</p>}
            {!msg && !erro && stats?.linhas_com_excecao > 0 && (
              <p className="siscor-fluxo-aviso">
                {stats.linhas_com_excecao} beneficiário(s) com exceção — revise antes de confirmar.
              </p>
            )}
          </div>
          <div className="secao-fluxo-acoes">
            <button
              type="button"
              className="secundario"
              onClick={() => setDetalheAberto((v) => !v)}
            >
              {detalheAberto ? "Ocultar beneficiários" : "Ver beneficiários"}
            </button>
            <button type="button" onClick={handleConfirmarLote} disabled={carregando}>
              Confirmar beneficiários sem exceção
            </button>
          </div>
        </footer>
      )}

      {!conferencia && msg && <p className="ok">{msg}</p>}
      {!conferencia && erro && <p className="erro">{erro}</p>}
    </section>
  );
}
