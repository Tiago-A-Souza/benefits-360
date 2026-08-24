export default function EstudoCabecalho({ resumo, onTrocarEstudo, onHistorico }) {
  return (
    <header className="topbar">
      <div className="topbar-slot topbar-slot--start">
        <img
          className="brand-mark"
          src="/turya-logo.png"
          alt="Turya"
          width={200}
          height={52}
        />
        {resumo && (
          <div className="study-mini">
            <span className="muted">{resumo.titulo}</span>
            <strong>{resumo.empresa || resumo.titulo}</strong>
            <span className={`badge badge--${resumo.status === "aprovado" ? "ok" : "alerta"}`}>
              {resumo.status_exibicao || "Em andamento"}
            </span>
          </div>
        )}
      </div>

      <p className="system-title">Estudo Saúde</p>

      <div className="topbar-slot topbar-slot--end">
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
      </div>
    </header>
  );
}
