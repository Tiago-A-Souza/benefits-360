import { useCallback, useEffect, useMemo, useState } from "react";
import {
  confirmarLoteSiscor,
  importarSiscor,
  obterConferenciaSiscor,
  atualizarLinhaSiscor,
} from "./api";
import FilePickerButton from "./components/FilePickerButton";
import {
  formatarPctHint,
  montarTabelaPlanosBase,
} from "./fluxo/resumoPlanoUi";
import TabelaFaixasCotacao from "./fluxo/TabelaFaixasCotacao";
import { centavosParaReaisExibicao, reaisTextoParaCentavos } from "./money";

export default function SiscorPanel({
  estudoId,
  etapaIndice = 1,
  totalEtapas = 5,
  resumoPlanoAtual,
  onAtualizado,
  onRegistrarAvanco,
}) {
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
      return res;
    } catch (err) {
      setErro(err.message);
      return null;
    } finally {
      setCarregando(false);
    }
  }

  const confirmarParaAvancar = useCallback(async () => {
    if (!conferencia?.linhas?.length) {
      setErro("Importe a planilha SISCOR");
      return false;
    }
    const res = await handleConfirmarLote();
    if (!res) return false;
    if ((res.excecoes_restantes || 0) > 0) {
      setErro(`${res.excecoes_restantes} exceção(ões) na base`);
      return false;
    }
    if ((res.confirmadas || 0) === 0) {
      setErro("Confirme os beneficiários");
      return false;
    }
    return true;
  }, [conferencia, estudoId]);

  useEffect(() => {
    if (!onRegistrarAvanco) return undefined;
    return onRegistrarAvanco(confirmarParaAvancar);
  }, [onRegistrarAvanco, confirmarParaAvancar]);

  const stats = conferencia?.estatisticas;
  const titulares = stats?.qtd_titulares ?? 0;
  const dependentes = stats?.qtd_dependentes ?? 0;
  const semParentesco = stats?.qtd_sem_parentesco ?? 0;
  const excluidas = stats?.qtd_excluidas ?? 0;
  const temBase = Boolean(stats);
  const totalVidas = stats?.total_linhas_lidas ?? 0;
  const excecoes = stats?.linhas_com_excecao ?? 0;
  const confirmadas = stats?.confirmadas ?? 0;
  const baseValidada = temBase && excecoes === 0 && confirmadas > 0;

  const linhasPlanos = useMemo(
    () => montarTabelaPlanosBase(conferencia, resumoPlanoAtual),
    [conferencia, resumoPlanoAtual]
  );

  const totaisTabela = useMemo(() => {
    if (!linhasPlanos.length) return null;
    return {
      titulares: linhasPlanos.reduce((s, r) => s + (r.titulares ?? 0), 0),
      dependentes: linhasPlanos.reduce((s, r) => s + (r.dependentes ?? 0), 0),
      vidas: linhasPlanos.reduce((s, r) => s + (r.vidas ?? 0), 0),
      vigente: resumoPlanoAtual?.total_vigente_reais || null,
      reajustado: resumoPlanoAtual?.total_reajustado_reais || null,
    };
  }, [linhasPlanos, resumoPlanoAtual]);

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

  const zonaUpload = (
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
  );

  return (
    <section className="etapa-fluxo">
      <div className="page-head">
        <div>
          <div className="page-kicker">
            Etapa {etapaIndice} de {totalEtapas}
          </div>
          <h1>Base atual</h1>
          <p className="lead">
            Revise a base importada do SISCOR antes de avançar. O sistema usa beneficiários,
            vínculo, plano e valor atual para montar o estudo.
          </p>
        </div>
        {baseValidada && <span className="badge badge--ok">Base validada</span>}
        {temBase && !baseValidada && excecoes > 0 && (
          <span className="badge badge--alerta">Exceções pendentes</span>
        )}
        {temBase && !baseValidada && excecoes === 0 && confirmadas === 0 && (
          <span className="badge badge--muted">Aguardando confirmação</span>
        )}
      </div>

      {!temBase && zonaUpload}

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
        <>
          <div className="metrics">
            <div className="metric">
              <small>Vidas</small>
              <strong className="num">{stats.total_linhas_lidas}</strong>
              <span className="hint">todos os beneficiários</span>
            </div>
            <div className="metric">
              <small>Titulares</small>
              <strong className="num">{titulares}</strong>
              <span className="hint">{formatarPctHint(titulares, totalVidas) || "—"}</span>
            </div>
            <div className="metric">
              <small>Dependentes</small>
              <strong className="num">{dependentes}</strong>
              <span className="hint">{formatarPctHint(dependentes, totalVidas) || "—"}</span>
            </div>
            {semParentesco > 0 && (
              <div className="metric">
                <small>Sem parentesco</small>
                <strong className="num">{semParentesco}</strong>
                <span className="hint">revisar vínculo</span>
              </div>
            )}
            {excluidas > 0 && (
              <div className="metric metric--alerta">
                <small>Excluídas</small>
                <strong className="num">{excluidas}</strong>
                <span className="hint">fora do cálculo</span>
              </div>
            )}
            <div className="metric">
              <small>Planos</small>
              <strong className="num">{stats.planos_detectados}</strong>
              <span className="hint">grupos vigentes</span>
            </div>
            <div
              className={`metric${excecoes > 0 ? " metric--alerta" : " metric--good"}`}
            >
              <small>Exceções</small>
              <strong className="num">{excecoes}</strong>
              <span className="hint">
                {excecoes === 0 ? "nenhuma pendência" : "revise antes de confirmar"}
              </span>
            </div>
          </div>

          {conferencia.tabela_faixas_cotacao && (
            <TabelaFaixasCotacao tabela={conferencia.tabela_faixas_cotacao} />
          )}

          <div className="panel">
            <div className="panel-head">
              <div>
                <h2>Base importada</h2>
                <p>Arquivo processado e pronto para o estudo.</p>
              </div>
              <FilePickerButton
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                disabled={carregando || !estudoId}
                onFiles={(files) => executarImportacao(undefined, files[0])}
                className="btn-compacto secundario"
              >
                Substituir planilha
              </FilePickerButton>
            </div>
            <div className="panel-body">
              <div className="file-line">
                <div className="file-ico" aria-hidden="true">
                  XLSX
                </div>
                <div className="file-main">
                  <b>Posição cadastral SISCOR</b>
                  <small>
                    Versão {conferencia.versao}
                    {conferencia.estado ? ` · ${conferencia.estado.replace(/_/g, " ")}` : ""}
                  </small>
                </div>
                <span className="badge badge--ok">Processado</span>
              </div>

              {excecoes === 0 && totalVidas > 0 && (
                <div className="notice notice--green">
                  <div className="notice-icon" aria-hidden="true">
                    ✓
                  </div>
                  <div>
                    <b>
                      {totalVidas} {totalVidas === 1 ? "vida lida" : "vidas lidas"}
                      {excluidas > 0 ? `, ${excluidas} excluída(s) do estudo` : ", nenhuma descartada"}
                    </b>
                    <p>
                      {confirmadas > 0
                        ? "A base está confirmada e pronta para as próximas etapas."
                        : "A base está consistente — confirme os beneficiários para continuar."}
                    </p>
                  </div>
                </div>
              )}

              {excecoes > 0 && (
                <div className="notice notice--amber">
                  <div className="notice-icon" aria-hidden="true">
                    !
                  </div>
                  <div>
                    <b>
                      {excecoes} {excecoes === 1 ? "exceção" : "exceções"} na base
                    </b>
                    <p>Revise os beneficiários com pendência antes de confirmar o lote.</p>
                  </div>
                </div>
              )}

              {linhasPlanos.length > 0 && (
                <div className="table-wrap">
                  <table className="num tabela-fluxo">
                    <thead>
                      <tr>
                        <th>Plano vigente</th>
                        <th className="right">Titulares</th>
                        <th className="right">Dependentes</th>
                        <th className="right">Vidas</th>
                        <th className="right">Valor vigente</th>
                        <th className="right">Valor reajustado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {linhasPlanos.map((row) => (
                        <tr key={row.id || row.nome}>
                          <td>
                            <span className="cell-main">{row.nome || "—"}</span>
                          </td>
                          <td className="right">{row.titulares ?? "—"}</td>
                          <td className="right">{row.dependentes ?? "—"}</td>
                          <td className="right">{row.vidas ?? "—"}</td>
                          <td className="right">{row.vigente || "—"}</td>
                          <td className="right">{row.reajustado || "—"}</td>
                        </tr>
                      ))}
                      {totaisTabela && (
                        <tr className="total-row">
                          <td>Total da base</td>
                          <td className="right">{totaisTabela.titulares}</td>
                          <td className="right">{totaisTabela.dependentes}</td>
                          <td className="right">{totaisTabela.vidas}</td>
                          <td className="right">{totaisTabela.vigente || "—"}</td>
                          <td className="right">{totaisTabela.reajustado || "—"}</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          <div className="panel panel-flat">
            <div className="panel-body">
              <div className="upload-area">
                <div className="upload-area-esq">
                  <div className="upload-icon" aria-hidden="true">
                    ↑
                  </div>
                  <div>
                    <h3>Quer substituir a base?</h3>
                    <p className="muted">
                      Arraste outra planilha .xlsx do SISCOR aqui ou escolha um arquivo.
                    </p>
                  </div>
                </div>
                <FilePickerButton
                  accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  disabled={carregando || !estudoId}
                  onFiles={(files) => executarImportacao(undefined, files[0])}
                >
                  Escolher arquivo
                </FilePickerButton>
              </div>
            </div>
          </div>
        </>
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
                      ) : linha.registro_confirmado ? (
                        "Confirmado"
                      ) : (
                        linha.status_texto || "—"
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
        <div className="action-bar">
          <div className="action-left">
            <button
              type="button"
              className="secundario"
              onClick={() => setDetalheAberto((v) => !v)}
            >
              {detalheAberto ? "Ocultar beneficiários" : "Ver beneficiários"}
            </button>
            {confirmadas > 0 && (
              <span className="action-note">
                {confirmadas} {confirmadas === 1 ? "beneficiário confirmado" : "beneficiários confirmados"}
              </span>
            )}
            {msg && <span className="action-note ok-inline">{msg}</span>}
            {erro && <span className="action-note erro-inline">{erro}</span>}
            {!msg && !erro && excecoes > 0 && (
              <span className="action-note">
                {excecoes} beneficiário(s) com exceção — revise antes de confirmar.
              </span>
            )}
          </div>
        </div>
      )}

      {!conferencia && msg && <p className="ok">{msg}</p>}
      {!conferencia && erro && <p className="erro">{erro}</p>}
    </section>
  );
}
