export default function EstudoCabecalho({ resumo, onTrocarEstudo, onHistorico }) {
  if (!resumo) return null;
  return (
    <header className="estudo-cabecalho">
      <div className="estudo-cabecalho-info">
        <h1>{resumo.empresa || resumo.titulo}</h1>
        <p className="estudo-cabecalho-meta">
          {resumo.titulo !== resumo.empresa && resumo.empresa ? (
            <span>{resumo.titulo} · </span>
          ) : null}
          <span>{resumo.formato_exibicao || "Renovação"}</span>
          <span> · {resumo.beneficiarios_rotulo || "0 beneficiários"}</span>
          <span> · </span>
          <span className={`status-pill status-pill--${resumo.status || "em_andamento"}`}>
            {resumo.status_exibicao || "Em andamento"}
          </span>
        </p>
      </div>
      <div className="estudo-cabecalho-acoes">
        <button type="button" className="secundario btn-compacto" onClick={onHistorico}>
          Histórico
        </button>
        <button type="button" className="secundario btn-compacto" onClick={onTrocarEstudo}>
          Trocar estudo
        </button>
      </div>
    </header>
  );
}
