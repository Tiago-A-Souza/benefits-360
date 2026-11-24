import { createContext, useCallback, useContext, useEffect, useState } from "react";

const ChromeCtx = createContext(null);

export function useAppChrome() {
  return useContext(ChromeCtx);
}

export default function AppChrome({ onSair, children }) {
  const [menuAberto, setMenuAberto] = useState(false);
  const fecharMenu = useCallback(() => setMenuAberto(false), []);
  const alternarMenu = useCallback(() => setMenuAberto((v) => !v), []);

  useEffect(() => {
    const fechar = () => setMenuAberto(false);
    window.addEventListener("hashchange", fechar);
    return () => window.removeEventListener("hashchange", fechar);
  }, []);

  useEffect(() => {
    if (!menuAberto) return undefined;
    function tecla(ev) {
      if (ev.key === "Escape") setMenuAberto(false);
    }
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [menuAberto]);

  return (
    <ChromeCtx.Provider value={{ onSair, menuAberto, fecharMenu, alternarMenu }}>
      <div className={`app-shell${menuAberto ? " app-shell--menu-aberto" : ""}`}>
        <button
          type="button"
          className="app-menu-toggle"
          aria-expanded={menuAberto}
          aria-controls="app-sidebar"
          onClick={alternarMenu}
        >
          {menuAberto ? "Fechar menu" : "Abrir menu"}
        </button>
        {menuAberto ? (
          <button
            type="button"
            className="app-sidebar-backdrop"
            aria-label="Fechar menu"
            onClick={fecharMenu}
          />
        ) : null}
        {children}
      </div>
    </ChromeCtx.Provider>
  );
}
