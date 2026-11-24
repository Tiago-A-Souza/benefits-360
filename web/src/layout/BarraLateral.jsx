import { commitBuild, rotuloVersao } from "../versaoProduto";
import { useAppChrome } from "./AppChrome";
import IconeNav from "./IconeNav";

export default function BarraLateral({ children }) {
  const chrome = useAppChrome();
  const onSair = chrome?.onSair;
  const commit = commitBuild();
  const versao = rotuloVersao();

  return (
    <aside id="app-sidebar" className="lista-rail app-sidebar">
      <div className="app-sidebar-marca">
        <img
          className="brand-mark"
          src="/turya-logo.png"
          alt="Turya"
          width={200}
          height={52}
        />
      </div>
      <div className="app-sidebar-corpo">{children}</div>
      <footer className="app-sidebar-rodape">
        {onSair ? (
          <button type="button" className="btn-sair-sidebar" onClick={onSair}>
            <IconeNav nome="sair" />
            Sair
          </button>
        ) : null}
        <p className="app-versao" title={commit ? `build ${commit}` : undefined}>
          {versao}
        </p>
      </footer>
    </aside>
  );
}
