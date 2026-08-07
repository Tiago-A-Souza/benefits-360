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

  const emAndamento = estudos.filter((e) => (e.status || "em_andamento") === "em_andamento").length;

  return (
    <div className="estudos-pagina">
      <section className="estudos-shell">
        <header className="estudos-topo">
          <div>
            <h1>Meus estudos</h1>
            <p>
              Renovações e comparativos de planos de saúde empresariais
              {!carregando && estudos.length > 0 && (
                <>
                  {" "}
                  · {estudos.length} {estudos.length === 1 ? "estudo" : "estudos"}
                  {emAndamento > 0 && ` · ${emAndamento} em andamento`}
                </>
              )}
            </p>
          </div>
          <button type="button" onClick={() => setModal(true)}>
            Criar novo estudo
          </button>
        </header>

        {carregando && (
          <div className="estudos-estado">
            <p className="muted">Carregando estudos…</p>
          </div>
        )}

        {!carregando && estudos.length === 0 && (
          <div className="estudos-estado estudos-vazio">
            <h2>Nenhum estudo ainda</h2>
            <p className="muted">Crie o primeiro comparativo para começar a análise financeira.</p>
            <button type="button" onClick={() => setModal(true)}>
              Criar novo estudo
            </button>
          </div>
        )}

        {!carregando && estudos.length > 0 && (
          <ul className="estudos-lista">
            {estudos.map((e) => {
              const empresa = (e.empresa || "").trim();
              const tipo = e.formato_exibicao || "Renovação";
              const vidas = e.beneficiarios_rotulo || e.beneficiarios_incluidos || "—";
              const status = e.status || "em_andamento";

              return (
                <li key={e.id}>
                  <article className="estudos-item">
                    <div className="estudos-item-identidade">
                      {empresa ? (
                        <p className="estudos-item-empresa">{empresa}</p>
                      ) : (
                        <p className="estudos-item-empresa estudos-item-empresa--vazio">
                          Empresa não informada
                        </p>
                      )}
                      <p className="estudos-item-estudo">{e.titulo}</p>
                      <p className="estudos-item-meta">
                        <span>{tipo}</span>
                        <span>{vidas}</span>
                        <span>
                          <time dateTime={e.ultima_alteracao}>
                            {formatarData(e.ultima_alteracao)}
                          </time>
                        </span>
                      </p>
                    </div>
                    <div className="estudos-item-acoes">
                      <span className={`status-pill status-pill--${status}`}>
                        {e.status_exibicao || "Em andamento"}
                      </span>
                      <button
                        type="button"
                        className="secundario btn-compacto"
                        onClick={() => onContinuar(e.id)}
                      >
                        Continuar
                      </button>
                    </div>
                  </article>
                </li>
              );
            })}
          </ul>
        )}

        <footer className="estudos-rodape">
          <span className="estudos-rodape-tag">Seguro novo</span>
          <span>Disponível em breve</span>
        </footer>
      </section>

      {modal && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <form className="modal-cartao estudos-modal" onSubmit={handleCriar}>
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

      {erro && <p className="erro estudos-erro">{erro}</p>}
    </div>
  );
}
