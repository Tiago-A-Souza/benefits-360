import { useEffect, useState } from "react";
import { listarEstudos, obterConfig } from "./api";
import CenarioPanel from "./CenarioPanel";
import ComparativoPanel from "./ComparativoPanel";
import ConfigEstudo from "./ConfigEstudo";
import PropostaPanel from "./PropostaPanel";
import HistoricoPanel from "./HistoricoPanel";
import RevisaoApresentacaoPanel from "./RevisaoApresentacaoPanel";
import SiscorPanel from "./SiscorPanel";
import { PASSOS } from "./constants";

const ESTUDO_PADRAO = "demo-12";

export default function App() {
  const [config, setConfig] = useState(null);
  const [passo, setPasso] = useState(1);
  const [estudoId, setEstudoId] = useState(ESTUDO_PADRAO);
  const [estudos, setEstudos] = useState([]);

  useEffect(() => {
    obterConfig().then(setConfig).catch(() => {});
    listarEstudos().then((ids) => {
      setEstudos(ids);
      if (ids.length && !ids.includes(estudoId)) setEstudoId(ids[0]);
    });
  }, []);

  function recarregarEstudos() {
    listarEstudos().then(setEstudos);
  }

  return (
    <div className="pagina pagina--larga">
      <header>
        <h1>Sistema de Estudos Newport</h1>
        <p className="sub">
          {config?.modo === "real"
            ? "Modo operacional — dados em armazenamento privado local"
            : "Modo demonstração — dados fictícios"}
          {config?.versao ? ` · v${config.versao}` : ""}
        </p>
      </header>

      <nav className="wizard">
        {PASSOS.map((p) => (
          <button
            key={p.id}
            type="button"
            className={passo === p.id ? "wizard-passo ativo" : "wizard-passo"}
            onClick={() => setPasso(p.id)}
          >
            <span className="wizard-num">{p.id}</span>
            {p.titulo}
          </button>
        ))}
      </nav>

      <div className="cartao cartao--toolbar">
        <label htmlFor="estudo-global">Estudo ativo</label>
        <select
          id="estudo-global"
          value={estudoId}
          onChange={(e) => setEstudoId(e.target.value)}
        >
          {estudos.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
      </div>

      {passo === 1 && (
        <SiscorPanel
          estudoId={estudoId}
          onEstudoId={setEstudoId}
          onEstudosChange={recarregarEstudos}
        />
      )}
      {passo === 2 && <ConfigEstudo estudoId={estudoId} onSalvo={recarregarEstudos} />}
      {passo === 3 && <PropostaPanel estudoId={estudoId} onSalvo={recarregarEstudos} />}
      {passo === 4 && <CenarioPanel estudoId={estudoId} onSalvo={recarregarEstudos} />}
      {passo === 5 && <ComparativoPanel estudoId={estudoId} />}
      {passo === 6 && <RevisaoApresentacaoPanel estudoId={estudoId} />}
      {passo === 7 && <HistoricoPanel estudoId={estudoId} />}

      <div className="wizard-nav">
        {passo > 1 && (
          <button type="button" className="secundario" onClick={() => setPasso(passo - 1)}>
            ← Etapa anterior
          </button>
        )}
        {passo < 7 && (
          <button type="button" onClick={() => setPasso(passo + 1)}>
            Próxima etapa →
          </button>
        )}
      </div>
    </div>
  );
}
