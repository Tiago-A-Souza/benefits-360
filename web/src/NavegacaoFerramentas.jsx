/** Itens de navegação fora do fluxo de estudo — presentes nas barras laterais. */
export default function NavegacaoFerramentas({
  ativo,
  onMeusEstudos,
  onSimularRede,
  onVoltarEstudo,
  rotuloEstudo,
}) {
  return (
    <nav className="nav-ferramentas" aria-label="Navegação do sistema">
      <p className="lista-rail-lb">Navegar</p>
      <ul className="lista-filtros">
        {onMeusEstudos && (
          <li>
            <button
              type="button"
              aria-pressed={ativo === "estudos"}
              aria-current={ativo === "estudos" ? "page" : undefined}
              onClick={onMeusEstudos}
            >
              Meus estudos
            </button>
          </li>
        )}
        {onVoltarEstudo && (
          <li>
            <button type="button" aria-pressed={false} onClick={onVoltarEstudo}>
              {rotuloEstudo ? `← Voltar ao estudo · ${rotuloEstudo}` : "← Voltar ao estudo"}
            </button>
          </li>
        )}
        <li>
          <button
            type="button"
            aria-pressed={ativo === "simular"}
            aria-current={ativo === "simular" ? "page" : undefined}
            onClick={onSimularRede}
          >
            Simular rede
          </button>
        </li>
      </ul>
    </nav>
  );
}
