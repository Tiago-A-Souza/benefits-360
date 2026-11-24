import { RotuloNav } from "./layout/IconeNav";

/** Itens de navegação fora do fluxo de estudo — presentes nas barras laterais. */
export default function NavegacaoFerramentas({
  ativo,
  onMeusEstudos,
  onSimularRede,
  onCotacoes,
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
              <RotuloNav icone="estudos">Meus estudos</RotuloNav>
            </button>
          </li>
        )}
        {onVoltarEstudo && (
          <li>
            <button type="button" aria-pressed={false} onClick={onVoltarEstudo}>
              <RotuloNav icone="voltar">
                {rotuloEstudo ? `Voltar ao estudo · ${rotuloEstudo}` : "Voltar ao estudo"}
              </RotuloNav>
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
            <RotuloNav icone="simular">Simular rede</RotuloNav>
          </button>
        </li>
        {onCotacoes && (
          <li>
            <button
              type="button"
              aria-pressed={ativo === "cotacoes"}
              aria-current={ativo === "cotacoes" ? "page" : undefined}
              onClick={onCotacoes}
            >
              <RotuloNav icone="cotacoes">Cotações</RotuloNav>
            </button>
          </li>
        )}
      </ul>
    </nav>
  );
}
