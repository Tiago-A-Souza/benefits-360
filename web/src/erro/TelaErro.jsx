import EstudoCabecalho from "../EstudoCabecalho";
import NavegacaoFerramentas from "../NavegacaoFerramentas";

export default function TelaErro({
  modo = "pagina",
  contexto = "",
  onTentar,
  onVoltarEstudos,
  onSair,
}) {
  const corpo = (
    <div className="tela-erro" role="alert">
      <h1>Esta tela não carregou</h1>
      <p>
        Algo deu errado nesta parte do Benefits. Os seus estudos e o menu continuam no lugar; nada foi
        apagado.
      </p>
      {contexto ? <p className="muted">Onde: {contexto}</p> : null}
      <div className="tela-erro-acoes">
        <button type="button" onClick={onTentar}>
          Tentar de novo
        </button>
        <button type="button" className="secundario" onClick={onVoltarEstudos}>
          Voltar aos estudos
        </button>
      </div>
    </div>
  );

  if (modo === "painel") {
    return <div className="tela-erro-painel">{corpo}</div>;
  }

  return (
    <div className="app-shell">
      <EstudoCabecalho resumo={null} onSair={onSair} />
      <div className="lista-shell">
        <aside className="lista-rail app-sidebar">
          <NavegacaoFerramentas
            ativo="estudos"
            onMeusEstudos={onVoltarEstudos}
            onSimularRede={onVoltarEstudos}
            onCotacoes={onVoltarEstudos}
          />
        </aside>
        <main className="lista-main">{corpo}</main>
      </div>
    </div>
  );
}
