import { useEffect, useState } from "react";
import { criarEstudo, listarEstudos } from "./api";

function formatarData(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

export default function MeusEstudos({ onContinuar }) {
  const [estudos, setEstudos] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [modal, setModal] = useState(false);
  const [nomeEmpresa, setNomeEmpresa] = useState("");
  const [nomeEstudo, setNomeEstudo] = useState("");
  const [criando, setCriando] = useState(false);

  function recarregar() {
    setCarregando(true);
    listarEstudos()
      .then(setEstudos)
      .catch((e) => setErro(e.message))
      .finally(() => setCarregando(false));
  }

  useEffect(() => {
    recarregar();
  }, []);

  async function handleCriar(e) {
    e.preventDefault();
    if (!nomeEmpresa.trim() || !nomeEstudo.trim()) return;
    setCriando(true);
    setErro(null);
    try {
      const res = await criarEstudo({
        titulo: nomeEstudo.trim(),
        nome_empresa: nomeEmpresa.trim(),
      });
      setModal(false);
      setNomeEmpresa("");
      setNomeEstudo("");
      onContinuar(res.id);
    } catch (err) {
      setErro(err.message);
    } finally {
      setCriando(false);
    }
  }

  return (
    <div className="meus-estudos">
      <header className="meus-estudos-cabecalho">
        <div>
          <h1>Meus estudos</h1>
          <p className="muted">Renovações e comparativos de planos de saúde empresariais.</p>
        </div>
        <button type="button" onClick={() => setModal(true)}>
          Criar novo estudo
        </button>
      </header>

      {carregando && <p className="muted">Carregando estudos…</p>}
      {!carregando && estudos.length === 0 && (
        <p className="muted">Nenhum estudo ainda. Crie o primeiro para começar.</p>
      )}

      {!carregando && estudos.length > 0 && (
        <table className="tabela-estudos">
          <thead>
            <tr>
              <th>Empresa</th>
              <th>Estudo</th>
              <th>Tipo</th>
              <th>Vidas</th>
              <th>Status</th>
              <th>Última alteração</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {estudos.map((e) => (
              <tr key={e.id}>
                <td>{e.empresa || "—"}</td>
                <td>{e.titulo}</td>
                <td>{e.formato_exibicao || "Renovação"}</td>
                <td>{e.beneficiarios_rotulo || e.beneficiarios_incluidos || "—"}</td>
                <td>
                  <span className={`status-pill status-pill--${e.status || "em_andamento"}`}>
                    {e.status_exibicao || "Em andamento"}
                  </span>
                </td>
                <td>{formatarData(e.ultima_alteracao)}</td>
                <td>
                  <button type="button" className="secundario btn-compacto" onClick={() => onContinuar(e.id)}>
                    Continuar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="muted tipo-em-breve">Seguro novo — em breve</p>

      {modal && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <form className="modal-cartao" onSubmit={handleCriar}>
            <h2>Novo estudo</h2>
            <p className="muted">Renovação de plano de saúde empresarial.</p>
            <label>
              Nome da empresa
              <input
                required
                value={nomeEmpresa}
                onChange={(ev) => setNomeEmpresa(ev.target.value)}
                placeholder="Ex.: Acme Indústria Ltda."
              />
            </label>
            <label>
              Nome do estudo
              <input
                required
                value={nomeEstudo}
                onChange={(ev) => setNomeEstudo(ev.target.value)}
                placeholder="Ex.: Renovação 2026 — 18 vidas"
              />
            </label>
            <div className="modal-acoes">
              <button type="button" className="secundario" onClick={() => setModal(false)}>
                Cancelar
              </button>
              <button type="submit" disabled={criando}>
                {criando ? "Criando…" : "Criar estudo"}
              </button>
            </div>
          </form>
        </div>
      )}

      {erro && <p className="erro">{erro}</p>}
    </div>
  );
}
