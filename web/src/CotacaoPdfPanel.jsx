import { useEffect, useState } from "react";
import {
  aplicarExtracaoCotacao,
  atualizarCampoExtracao,
  confirmarLoteExtracao,
  excluirOpcaoExtracao,
  importarCotacaoPdf,
  listarExtracoesCotacao,
  obterExtracaoCotacao,
  selecionarOpcaoExtracao,
} from "./api";
import {
  centavosParaReaisExibicao,
  centavosParaReaisTexto,
  reaisTextoParaCentavos,
} from "./money";

const ROTULOS_FAIXA = [
  "0 a 18",
  "19 a 23",
  "24 a 28",
  "29 a 33",
  "34 a 38",
  "39 a 43",
  "44 a 48",
  "49 a 53",
  "54 a 58",
  "59+",
];

function badgeEstado(estado) {
  if (estado === "revisar") return "alerta";
  if (estado === "confirmar") return "ok";
  return "muted";
}

function CampoConferencia({ campo, onSalvar, tipo = "auto" }) {
  const [editando, setEditando] = useState(false);
  const [valorLocal, setValorLocal] = useState("");
  const [erroLocal, setErroLocal] = useState(null);

  if (!campo) {
    return (
      <tr className="campo-ausente">
        <td colSpan={4} className="muted">
          Campo ausente no documento
        </td>
      </tr>
    );
  }

  function valorExibido() {
    if (campo.centavos != null) return centavosParaReaisExibicao(campo.centavos);
    if (campo.data) return campo.data;
    if (campo.inteiro != null) return String(campo.inteiro);
    return campo.texto || "—";
  }

  function iniciarEdicao() {
    if (campo.centavos != null) {
      setValorLocal(centavosParaReaisTexto(campo.centavos));
    } else if (campo.inteiro != null) {
      setValorLocal(String(campo.inteiro));
    } else {
      setValorLocal(campo.texto || campo.data || "");
    }
    setErroLocal(null);
    setEditando(true);
  }

  async function salvar() {
    const patch = {};
    if (tipo === "money" || campo.centavos != null) {
      const conv = reaisTextoParaCentavos(valorLocal);
      if (!conv.ok) {
        setErroLocal(conv.erro);
        return;
      }
      patch.centavos = conv.centavos;
    } else if (tipo === "int" || campo.inteiro != null) {
      const n = parseInt(valorLocal, 10);
      if (Number.isNaN(n) || n < 0) {
        setErroLocal("Informe um número inteiro válido.");
        return;
      }
      patch.inteiro = n;
    } else if (tipo === "date") {
      patch.data = valorLocal;
    } else {
      patch.texto = valorLocal;
    }
    await onSalvar(campo.id, patch);
    setEditando(false);
  }

  return (
    <tr className={`campo-extracao campo-extracao--${campo.estado}`}>
      <td>
        <strong>{campo.rotulo}</strong>
        <div className={`badge badge--${badgeEstado(campo.estado)}`}>{campo.estado}</div>
      </td>
      <td>
        {editando ? (
          <>
            <input value={valorLocal} onChange={(e) => setValorLocal(e.target.value)} />
            {erroLocal && <p className="erro">{erroLocal}</p>}
          </>
        ) : (
          valorExibido()
        )}
        {campo.price_basis && <div className="muted">Base: {campo.price_basis}</div>}
      </td>
      <td className="evidencia-col">
        {campo.evidencia?.pagina != null && <div>Pág. {campo.evidencia.pagina}</div>}
        {campo.evidencia?.trecho && (
          <p className="muted evidencia">{campo.evidencia.trecho.slice(0, 160)}</p>
        )}
      </td>
      <td className="acoes-campo">
        {editando ? (
          <>
            <button type="button" className="link" onClick={salvar}>
              Salvar
            </button>
            <button type="button" className="link" onClick={() => setEditando(false)}>
              Cancelar
            </button>
          </>
        ) : (
          <>
            <button type="button" className="link" onClick={iniciarEdicao}>
              Corrigir
            </button>
            {!campo.confirmado && (
              <button
                type="button"
                className="link"
                onClick={() => onSalvar(campo.id, { confirmado: true })}
              >
                Confirmar
              </button>
            )}
            {campo.confirmado && <span className="ok">✓</span>}
          </>
        )}
      </td>
    </tr>
  );
}

function CampoSelect({ campo, onSalvar, opcoes, label }) {
  return (
    <tr className={`campo-extracao campo-extracao--${campo?.estado || "ausente"}`}>
      <td>
        <strong>{campo?.rotulo || label}</strong>
        {campo && <div className={`badge badge--${badgeEstado(campo.estado)}`}>{campo.estado}</div>}
      </td>
      <td>
        <select
          value={campo?.texto || ""}
          onChange={(e) => {
            if (!campo) return;
            onSalvar(campo.id, { texto: e.target.value, confirmado: false });
          }}
          disabled={!campo}
        >
          <option value="">— selecione —</option>
          {opcoes.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </td>
      <td className="evidencia-col">
        {campo?.evidencia?.pagina != null && <div>Pág. {campo.evidencia.pagina}</div>}
        {campo?.evidencia?.trecho && (
          <p className="muted evidencia">{campo.evidencia.trecho.slice(0, 120)}</p>
        )}
      </td>
      <td>
        {campo && !campo.confirmado && (
          <button
            type="button"
            className="link"
            disabled={!campo.texto}
            onClick={() => onSalvar(campo.id, { confirmado: true })}
          >
            Confirmar
          </button>
        )}
        {campo?.confirmado && <span className="ok">✓</span>}
      </td>
    </tr>
  );
}

function OpcaoExtracao({ op, estudoId, documentoId, onSalvarCampo, onExcluir, exigeSelecao, onSelecionar }) {
  if (op.excluida) {
    return (
      <div className="cartao cartao--interno opcao-excluida">
        <p className="muted">Opção excluída — não entrará no comparativo.</p>
      </div>
    );
  }

  const faixasPorIndice = Object.fromEntries(op.tabela.map((fx) => [fx.faixa, fx]));

  return (
    <div className="cartao cartao--interno opcao-extracao">
      <div className="opcao-header">
        {exigeSelecao && (
          <label className="opcao-selecao">
            <input
              type="checkbox"
              checked={Boolean(op.selecionada_para_comparativo)}
              onChange={(e) => onSelecionar(op.id, e.target.checked)}
            />
            Levar ao comparativo
          </label>
        )}
        <h4>{op.plano_nome?.texto || "Opção extraída"}</h4>
        <button type="button" className="secundario" onClick={() => onExcluir(op.id)}>
          Excluir opção
        </button>
      </div>

      {documentoId && estudoId && (
        <p>
          <a
            href={`/api/estudos/${estudoId}/documentos-cotacao/${documentoId}/pdf`}
            target="_blank"
            rel="noreferrer"
          >
            Ver PDF enviado
          </a>
        </p>
      )}

      <table className="tabela-conferencia">
        <thead>
          <tr>
            <th>Campo</th>
            <th>Valor</th>
            <th>Evidência</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          <CampoConferencia campo={op.operadora} onSalvar={onSalvarCampo} />
          <CampoConferencia campo={op.plano_nome} onSalvar={onSalvarCampo} />
          <CampoConferencia campo={op.acomodacao} onSalvar={onSalvarCampo} />
          <CampoSelect
            label="Modalidade"
            campo={op.modalidade}
            onSalvar={onSalvarCampo}
            opcoes={[
              { value: "empresarial", label: "Empresarial" },
              { value: "adesao", label: "Adesão" },
            ]}
          />
          <CampoSelect
            label="Tipo fiscal"
            campo={op.tipo_fiscal}
            onSalvar={onSalvarCampo}
            opcoes={[
              { value: "seguradora", label: "Seguradora" },
              { value: "operadora", label: "Operadora" },
            ]}
          />
          <CampoSelect
            label="Regime de coparticipação"
            campo={op.regime_copart}
            onSalvar={onSalvarCampo}
            opcoes={[
              { value: "sem", label: "Sem coparticipação" },
              { value: "parcial", label: "Parcial" },
              { value: "percentual", label: "Percentual" },
              { value: "customizada", label: "Customizada" },
            ]}
          />
          <CampoConferencia campo={op.copart_percentual} onSalvar={onSalvarCampo} tipo="int" />
          <CampoConferencia campo={op.validade_oficial} onSalvar={onSalvarCampo} tipo="date" />
          <CampoConferencia campo={op.subtotal_impresso} onSalvar={onSalvarCampo} tipo="money" />
          <CampoConferencia campo={op.premio_saude} onSalvar={onSalvarCampo} tipo="money" />
          <CampoConferencia campo={op.iof} onSalvar={onSalvarCampo} tipo="money" />
          <CampoConferencia campo={op.total_recorrente} onSalvar={onSalvarCampo} tipo="money" />
          <CampoConferencia campo={op.total_primeira_parcela} onSalvar={onSalvarCampo} tipo="money" />
          {op.custos_unicos?.map((c) => (
            <CampoConferencia key={c.id} campo={c} onSalvar={onSalvarCampo} tipo="money" />
          ))}
          <CampoConferencia campo={op.observacoes} onSalvar={onSalvarCampo} />
        </tbody>
      </table>

      <h5>Faixas etárias</h5>
      <table className="tabela-conferencia tabela-faixas">
        <thead>
          <tr>
            <th>Faixa</th>
            <th>Valor unitário</th>
            <th>Quantidade</th>
            <th>Evidência</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {ROTULOS_FAIXA.map((rotulo, idx) => {
            const fx = faixasPorIndice[idx];
            if (!fx) {
              return (
                <tr key={idx} className="campo-ausente">
                  <td>{rotulo}</td>
                  <td colSpan={4} className="muted">
                    Não extraída
                  </td>
                </tr>
              );
            }
            return (
              <tr key={idx} className="faixa-row">
                <td>{rotulo}</td>
                <td>
                  {fx.valor.centavos != null ? centavosParaReaisExibicao(fx.valor.centavos) : "—"}
                  {!fx.valor.confirmado && fx.valor.estado !== "ausente" && (
                    <button type="button" className="link" onClick={() => onSalvarCampo(fx.valor.id, { confirmado: true })}>
                      Confirmar valor
                    </button>
                  )}
                </td>
                <td>
                  {fx.quantidade.inteiro != null ? fx.quantidade.inteiro : "—"}
                  {!fx.quantidade.confirmado && fx.quantidade.estado !== "ausente" && (
                    <button type="button" className="link" onClick={() => onSalvarCampo(fx.quantidade.id, { confirmado: true })}>
                      Confirmar qtd
                    </button>
                  )}
                </td>
                <td className="evidencia-col">
                  {fx.valor.evidencia?.pagina != null && <div>Pág. {fx.valor.evidencia.pagina}</div>}
                  {fx.valor.evidencia?.trecho && (
                    <p className="muted">{fx.valor.evidencia.trecho.slice(0, 100)}</p>
                  )}
                </td>
                <td>
                  <button
                    type="button"
                    className="link"
                    onClick={() => {
                      const v = prompt("Valor unitário (R$):", centavosParaReaisTexto(fx.valor.centavos));
                      if (v == null) return;
                      const conv = reaisTextoParaCentavos(v);
                      if (conv.ok) onSalvarCampo(fx.valor.id, { centavos: conv.centavos });
                    }}
                  >
                    Corrigir valor
                  </button>
                  <button
                    type="button"
                    className="link"
                    onClick={() => {
                      const v = prompt("Quantidade:", fx.quantidade.inteiro ?? "");
                      if (v == null) return;
                      onSalvarCampo(fx.quantidade.id, { inteiro: parseInt(v, 10) });
                    }}
                  >
                    Corrigir qtd
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {op.reconciliacao && (
        <div className={`reconciliacao ${op.reconciliacao.ok ? "ok" : "pendencias-box"}`}>
          <strong>Reconciliação financeira</strong>
          <ul className="muted">
            {op.reconciliacao.subtotal_calculado_centavos != null && (
              <li>
                Subtotal calculado:{" "}
                {centavosParaReaisExibicao(op.reconciliacao.subtotal_calculado_centavos)}
              </li>
            )}
            {op.reconciliacao.total_recorrente_calculado_centavos != null && (
              <li>
                Total calculado:{" "}
                {centavosParaReaisExibicao(op.reconciliacao.total_recorrente_calculado_centavos)}
              </li>
            )}
          </ul>
          {!op.reconciliacao.ok && op.reconciliacao.divergencias?.length > 0 && (
            <ul>
              {op.reconciliacao.divergencias.map((d, i) => (
                <li key={i}>{d.descricao}</li>
              ))}
            </ul>
          )}
          {op.reconciliacao.ok && <p className="ok">Valores consistentes.</p>}
        </div>
      )}
    </div>
  );
}

export default function CotacaoPdfPanel({ estudoId, onAplicado }) {
  const [extracoes, setExtracoes] = useState([]);
  const [sel, setSel] = useState(null);
  const [detalhe, setDetalhe] = useState(null);
  const [erro, setErro] = useState(null);
  const [msg, setMsg] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [bloqueios, setBloqueios] = useState([]);

  function recarregar() {
    listarExtracoesCotacao(estudoId)
      .then((r) => setExtracoes(r.extracoes || []))
      .catch(() => setExtracoes([]));
  }

  async function recarregarDetalhe() {
    if (!sel) return;
    const d = await obterExtracaoCotacao(estudoId, sel);
    setDetalhe(d);
  }

  useEffect(() => {
    if (!estudoId) return;
    recarregar();
  }, [estudoId]);

  useEffect(() => {
    if (!sel) {
      setDetalhe(null);
      return;
    }
    obterExtracaoCotacao(estudoId, sel)
      .then(setDetalhe)
      .catch((e) => setErro(e.message));
  }, [estudoId, sel]);

  async function handleUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setCarregando(true);
    setErro(null);
    setBloqueios([]);
    try {
      const res = await importarCotacaoPdf(estudoId, file);
      setMsg(
        res.sucesso
          ? `Template reconhecido (${res.template_id || res.operadora}) — ${res.opcoes_encontradas} opção(ões) encontrada(s). Revise e selecione antes de aplicar.`
          : `PDF recebido (${res.estado}). Revise ou use entrada manual.`
      );
      recarregar();
      setSel(res.extracao_id);
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
      e.target.value = "";
    }
  }

  async function salvarCampo(campoId, patch) {
    if (!sel || !campoId) return;
    setErro(null);
    try {
      if (patch.criar) {
        setErro("Campo ausente — use Corrigir em um campo existente ou informe via API.");
        return;
      }
      await atualizarCampoExtracao(estudoId, sel, campoId, patch);
      await recarregarDetalhe();
    } catch (err) {
      setErro(err.message);
    }
  }

  async function handleConfirmarLote() {
    setErro(null);
    await confirmarLoteExtracao(estudoId, sel);
    await recarregarDetalhe();
    setMsg("Campos sem alerta confirmados em lote (campos em revisão ficaram pendentes).");
  }

  async function handleAplicar() {
    setErro(null);
    setBloqueios([]);
    try {
      const res = await aplicarExtracaoCotacao(estudoId, sel);
      const partes = [];
      if (res.opcoes_adicionadas) partes.push(`${res.opcoes_adicionadas} nova(s)`);
      if (res.opcoes_atualizadas) partes.push(`${res.opcoes_atualizadas} atualizada(s)`);
      setMsg(partes.length ? `Propostas aplicadas: ${partes.join(", ")}.` : "Nenhuma alteração.");
      if (res.bloqueios?.length) setBloqueios(res.bloqueios);
      onAplicado?.();
    } catch (err) {
      if (err.bloqueios) setBloqueios(err.bloqueios);
      setErro(err.message);
    }
  }

  async function handleSelecionarOpcao(opcaoId, selecionada) {
    if (!sel) return;
    await selecionarOpcaoExtracao(estudoId, sel, opcaoId, selecionada);
    await recarregarDetalhe();
  }

  async function handleExcluirOpcao(opcaoId) {
    await excluirOpcaoExtracao(estudoId, sel, opcaoId);
    await recarregarDetalhe();
    setMsg("Opção marcada como excluída.");
  }

  const docId = detalhe?.documento?.id;
  const exigeSelecao =
    detalhe?.documento?.template_id?.startsWith("porto-") ||
    (detalhe?.opcoes?.filter((o) => !o.excluida).length || 0) > 3;

  return (
    <section className="cartao cartao--interno">
      <h3>Importar cotações (PDF)</h3>
      <p className="muted">
        Envie PDFs de Porto, SulAmérica, Amil, Bradesco ou Omint. Reconhecer o template não
        homologa a extração financeira. Confirme campos e selecione conscientemente quais planos
        levar ao comparativo quando a tabela geral listar muitos planos.
      </p>
      <label className="upload-label">
        <input type="file" accept="application/pdf" onChange={handleUpload} disabled={carregando} />
        {carregando ? "Processando PDF…" : "Selecionar PDF de cotação"}
      </label>

      {extracoes.length > 0 && (
        <ul className="lista-extracoes">
          {extracoes.map((ex) => (
            <li key={ex.id}>
              <button type="button" className="link" onClick={() => setSel(ex.id)}>
                {ex.documento?.operadora_detectada || "Documento"} — {ex.estado} (v{ex.versao})
              </button>
            </li>
          ))}
        </ul>
      )}

      {detalhe && (
        <>
          {detalhe.documento?.template_id && (
            <p className="muted">
              Template: <strong>{detalhe.documento.template_id}</strong> — opções extraídas para
              revisão; aplicar ao rascunho só após confirmação (e seleção quando necessário).
            </p>
          )}
          {exigeSelecao && (
            <p className="alerta">
              Este documento lista vários planos na tabela geral. Marque apenas os que o cliente
              deseja comparar — nenhum plano é aplicado automaticamente.
            </p>
          )}
          {detalhe.alertas?.map((a, i) => (
            <p key={i} className="alerta">
              {a.codigo ? `[${a.codigo}] ` : ""}
              {a.mensagem}
            </p>
          ))}
          {detalhe.opcoes?.map((op) => (
            <OpcaoExtracao
              key={op.id}
              op={op}
              estudoId={estudoId}
              documentoId={docId}
              onSalvarCampo={salvarCampo}
              onExcluir={handleExcluirOpcao}
              exigeSelecao={exigeSelecao}
              onSelecionar={handleSelecionarOpcao}
            />
          ))}
          <div className="acoes-lote">
            <button type="button" className="secundario" onClick={handleConfirmarLote}>
              Confirmar lote (somente sem alerta)
            </button>
            <button type="button" onClick={handleAplicar}>
              Aplicar opções confirmadas ao rascunho
            </button>
          </div>
          {bloqueios.length > 0 && (
            <div className="pendencias-box">
              <strong>Opções não aplicadas</strong>
              <ul>
                {bloqueios.map((b) => (
                  <li key={b.opcao_id}>
                    <strong>{b.plano}</strong>
                    <ul>
                      {b.motivos.map((m, i) => (
                        <li key={i}>{m}</li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
      {msg && <p className="ok">{msg}</p>}
      {erro && <p className="erro">{erro}</p>}
    </section>
  );
}
