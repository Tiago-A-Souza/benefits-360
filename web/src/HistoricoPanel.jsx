import { useCallback, useEffect, useState } from "react";
import {
  confirmarVinculo,
  confirmarVinculoLote,
  criarCliente,
  listarClientes,
  listarCiclosCliente,
  obterHistoricoEstudo,
  obterRascunho,
  registrarPlanoContratado,
  vincularEstudoCliente,
} from "./api";

export default function HistoricoPanel({ estudoId }) {
  const [historico, setHistorico] = useState(null);
  const [rascunho, setRascunho] = useState(null);
  const [clientes, setClientes] = useState([]);
  const [ciclos, setCiclos] = useState([]);
  const [clienteId, setClienteId] = useState("");
  const [cicloId, setCicloId] = useState("");
  const [novoCliente, setNovoCliente] = useState("");
  const [planoForm, setPlanoForm] = useState({
    opcao_proposta_id: "",
    vigencia_inicio: "",
  });
  const [erro, setErro] = useState(null);
  const [ok, setOk] = useState(null);

  const recarregar = useCallback(async () => {
    if (!estudoId) return;
    try {
      const [hist, ras, cls] = await Promise.all([
        obterHistoricoEstudo(estudoId),
        obterRascunho(estudoId),
        listarClientes(),
      ]);
      setHistorico(hist);
      setRascunho(ras);
      setClientes(cls);
      if (hist.estudo.cliente_id) setClienteId(hist.estudo.cliente_id);
      if (hist.estudo.ciclo_id) setCicloId(hist.estudo.ciclo_id);
      if (ras.opcoes_proposta?.length && !planoForm.opcao_proposta_id) {
        setPlanoForm((f) => ({ ...f, opcao_proposta_id: ras.opcoes_proposta[0].id }));
      }
    } catch (e) {
      setErro(e.message);
    }
  }, [estudoId, planoForm.opcao_proposta_id]);

  useEffect(() => {
    recarregar();
  }, [recarregar]);

  useEffect(() => {
    if (!clienteId) {
      setCiclos([]);
      return;
    }
    listarCiclosCliente(clienteId).then(setCiclos).catch(() => setCiclos([]));
  }, [clienteId]);

  async function handleCriarCliente() {
    if (!novoCliente.trim()) return;
    await criarCliente(novoCliente.trim());
    setNovoCliente("");
    recarregar();
  }

  async function handleVincular() {
    setErro(null);
    try {
      await vincularEstudoCliente(estudoId, {
        cliente_id: clienteId,
        ciclo_id: cicloId || null,
        criar_ciclo: !cicloId,
      });
      setOk("Estudo vinculado ao cliente/ciclo.");
      recarregar();
    } catch (e) {
      setErro(e.message);
    }
  }

  async function handleRegistrarPlano(e) {
    e.preventDefault();
    setErro(null);
    try {
      await registrarPlanoContratado(estudoId, planoForm);
      setOk("Plano contratado registrado (ação explícita — não automática).");
      recarregar();
    } catch (err) {
      setErro(err.message);
    }
  }

  async function handleConfirmarSugestao(participacaoId, beneficiarioId) {
    await confirmarVinculo(estudoId, {
      participacao_id: participacaoId,
      acao: "confirmar",
      beneficiario_id: beneficiarioId,
    });
    recarregar();
  }

  async function handleNovoBeneficiario(participacaoId) {
    await confirmarVinculo(estudoId, { participacao_id: participacaoId, acao: "novo" });
    recarregar();
  }

  async function handleConfirmarLote() {
    const ids = (historico?.participacoes || [])
      .filter((p) => p.vinculo_status === "pendente" && p.sugestao_vinculo?.startsWith("sug-"))
      .map((p) => p.id);
    if (!ids.length) return;
    await confirmarVinculoLote(estudoId, { participacao_ids: ids, acao: "confirmar_coerentes" });
    recarregar();
  }

  if (!historico) return <p>Carregando histórico…</p>;

  return (
    <div className="cartao">
      <h2>Histórico longitudinal</h2>
      <p className="sub">
        Posições cadastrais versionadas, vínculos de beneficiários e planos contratados.
        O rascunho JSON é transitório; o histórico aprovado persiste nas tabelas relacionais.
      </p>
      {erro && <p className="erro">{erro}</p>}
      {ok && <p className="ok">{ok}</p>}

      <section className="secao-inline">
        <h3>Cliente e ciclo de renovação</h3>
        <div className="grid-2">
          <label>
            Cliente
            <select value={clienteId} onChange={(e) => setClienteId(e.target.value)}>
              <option value="">— selecione —</option>
              {clientes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </select>
          </label>
          <label>
            Ciclo
            <select value={cicloId} onChange={(e) => setCicloId(e.target.value)}>
              <option value="">Novo ciclo automático</option>
              {ciclos.map((c) => (
                <option key={c.id} value={c.id}>
                  Ciclo {c.numero}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="acoes-linha">
          <input
            type="text"
            placeholder="Novo cliente"
            value={novoCliente}
            onChange={(e) => setNovoCliente(e.target.value)}
          />
          <button type="button" className="secundario" onClick={handleCriarCliente}>
            Criar cliente
          </button>
          <button type="button" onClick={handleVincular} disabled={!clienteId}>
            Vincular estudo
          </button>
        </div>
      </section>

      {historico.ultimo_plano_contratado && (
        <section className="secao-inline cartao--aviso">
          <h3>Último plano contratado (base para próximo ciclo)</h3>
          <p>
            {historico.ultimo_plano_contratado.operadora} —{" "}
            {historico.ultimo_plano_contratado.plano_nome} · vigência{" "}
            {historico.ultimo_plano_contratado.vigencia_inicio}
          </p>
        </section>
      )}

      <section className="secao-inline">
        <h3>Posições cadastrais ({historico.posicoes.length})</h3>
        <ul>
          {historico.posicoes.map((p) => (
            <li key={p.id}>
              v{p.versao} · {p.origem} · {p.criado_em}
            </li>
          ))}
        </ul>
      </section>

      <section className="secao-inline">
        <h3>Beneficiários e vínculos</h3>
        <button type="button" className="secundario" onClick={handleConfirmarLote}>
          Confirmar associações coerentes em lote
        </button>
        <table className="tabela-compacta">
          <thead>
            <tr>
              <th>Nome</th>
              <th>Status</th>
              <th>Faixa</th>
              <th>Valor</th>
              <th>Vínculo</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {historico.participacoes.map((p) => (
              <tr key={p.id}>
                <td>{p.nome}</td>
                <td>{p.status}</td>
                <td>{p.faixa ?? "—"}</td>
                <td>{p.valor_centavos != null ? (p.valor_centavos / 100).toFixed(2) : "—"}</td>
                <td>{p.vinculo_status}</td>
                <td>
                  {p.vinculo_status === "pendente" && (
                    <>
                      {p.sugestao_vinculo?.startsWith("sug-") && (
                        <button
                          type="button"
                          className="secundario"
                          onClick={() =>
                            handleConfirmarSugestao(p.id, p.sugestao_vinculo.slice(4))
                          }
                        >
                          Confirmar sugestão
                        </button>
                      )}
                      <button
                        type="button"
                        className="secundario"
                        onClick={() => handleNovoBeneficiario(p.id)}
                      >
                        Pessoa nova
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="secao-inline">
        <h3>Registrar plano contratado</h3>
        <p className="sub">
          Ação explícita — nunca automática após aprovação do estudo.
        </p>
        <form onSubmit={handleRegistrarPlano} className="grid-2">
          <label>
            Proposta contratada
            <select
              value={planoForm.opcao_proposta_id}
              onChange={(e) =>
                setPlanoForm({ ...planoForm, opcao_proposta_id: e.target.value })
              }
            >
              {(rascunho?.opcoes_proposta || []).map((o) => (
                <option key={o.id} value={o.id}>
                  {o.operadora} — {o.plano_nome}
                </option>
              ))}
            </select>
          </label>
          <label>
            Vigência inicial
            <input
              type="date"
              required
              value={planoForm.vigencia_inicio}
              onChange={(e) =>
                setPlanoForm({ ...planoForm, vigencia_inicio: e.target.value })
              }
            />
          </label>
          <button type="submit">Registrar plano contratado</button>
        </form>
        <ul>
          {historico.planos_contratados.map((pl) => (
            <li key={pl.id}>
              {pl.plano_nome} · {pl.vigencia_inicio} · {pl.criado_em}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
