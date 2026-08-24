export default function EstudoCabecalho({ resumo, onTrocarEstudo, onHistorico }) {
  return (
    <header className="topbar">
      <div className="brand-wrap">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            N
          </div>
          <span className="brand-name">Newport</span>
        </div>
        {resumo && (
          <>
            <div className="crumb" aria-hidden="true" />
            <div className="study-mini">
              <span className="muted">{resumo.titulo}</span>
              <strong>{resumo.empresa || resumo.titulo}</strong>
              <span className={`badge badge--${resumo.status === "aprovado" ? "ok" : "alerta"}`}>
                {resumo.status_exibicao || "Em andamento"}
              </span>
            </div>
          </>
        )}
      </div>
      {resumo && (
        <div className="top-actions">
          <button type="button" className="secundario btn-compacto hide-mobile" onClick={onHistorico}>
            Histórico
          </button>
          <button type="button" className="secundario btn-compacto" onClick={onTrocarEstudo}>
            Trocar estudo
          </button>
        </div>
      )}
    </header>
  );
}
