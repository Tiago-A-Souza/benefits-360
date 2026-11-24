/** Ícones vazados (stroke) da barra lateral. `aria-hidden` — o rótulo do botão já descreve a ação. */

const TRAÇO = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

const CAMINHOS = {
  estudos: (
    <>
      <path d="M4 8h6.2l1.6 2H20v9.2A1.8 1.8 0 0 1 18.2 21H5.8A1.8 1.8 0 0 1 4 19.2Z" />
      <path d="M4 8V6.8A1.8 1.8 0 0 1 5.8 5h4.1L11.5 7" />
    </>
  ),
  simular: (
    <>
      <circle cx="7" cy="8" r="2.2" />
      <circle cx="17" cy="8" r="2.2" />
      <circle cx="12" cy="17.2" r="2.2" />
      <path d="M9 8.6 11 15.1M15 8.6l-2 6.5M9.4 8h5.2" />
    </>
  ),
  cotacoes: (
    <>
      <path d="M14 3.5H7.5A1.5 1.5 0 0 0 6 5v14a1.5 1.5 0 0 0 1.5 1.5h9A1.5 1.5 0 0 0 18 19V8Z" />
      <path d="M14 3.5V8h4.5" />
      <path d="M9 12.5h6M9 16h4" />
    </>
  ),
  voltar: (
    <>
      <path d="M11 6 5 12l6 6" />
      <path d="M5 12h14" />
    </>
  ),
  inicio: (
    <>
      <path d="M4.5 11 12 4.5 19.5 11" />
      <path d="M6.5 10.2V19h4.2v-5h2.6v5h4.2v-8.8" />
    </>
  ),
  nova: (
    <>
      <path d="M14 3.5H7.5A1.5 1.5 0 0 0 6 5v14a1.5 1.5 0 0 0 1.5 1.5h9A1.5 1.5 0 0 0 18 19V8Z" />
      <path d="M14 3.5V8h4.5" />
      <path d="M12 12.2v4.4M9.8 14.4h4.4" />
    </>
  ),
  lista: (
    <>
      <path d="M9 7h11M9 12h11M9 17h11" />
      <circle cx="5.2" cy="7" r="1.1" />
      <circle cx="5.2" cy="12" r="1.1" />
      <circle cx="5.2" cy="17" r="1.1" />
    </>
  ),
  importar: (
    <>
      <rect x="4" y="5" width="16" height="14" rx="1.6" />
      <path d="M4 10h16M10 5v14M16 5v14" />
    </>
  ),
  conexoes: (
    <>
      <path d="M9.6 14.4a3.6 3.6 0 0 1 0-5.1l2.3-2.3a3.6 3.6 0 0 1 5.1 5.1l-1.2 1.2" />
      <path d="M14.4 9.6a3.6 3.6 0 0 1 0 5.1l-2.3 2.3a3.6 3.6 0 0 1-5.1-5.1l1.2-1.2" />
    </>
  ),
  robos: (
    <>
      <path d="M5 7h14M5 12h14M5 17h14" />
      <circle cx="10" cy="7" r="1.8" />
      <circle cx="15.5" cy="12" r="1.8" />
      <circle cx="9.2" cy="17" r="1.8" />
    </>
  ),
  ajuda: (
    <>
      <circle cx="12" cy="12" r="8.2" />
      <path d="M9.4 9.5a2.6 2.6 0 1 1 3.5 2.4c-.7.4-1.2 1-1.2 1.8" />
      <path d="M12 17.2v.1" />
    </>
  ),
  todos: (
    <>
      <rect x="4" y="4" width="6.5" height="6.5" rx="1.2" />
      <rect x="13.5" y="4" width="6.5" height="6.5" rx="1.2" />
      <rect x="4" y="13.5" width="6.5" height="6.5" rx="1.2" />
      <rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.2" />
    </>
  ),
  andamento: (
    <>
      <circle cx="12" cy="12" r="8.2" />
      <path d="M12 7.8V12l3.2 2" />
    </>
  ),
  aprovado: (
    <>
      <circle cx="12" cy="12" r="8.2" />
      <path d="M8.2 12.2 11 15l4.8-5.4" />
    </>
  ),
  renovacao: (
    <>
      <path d="M4.2 11.2A8 8 0 0 1 17.8 7.2L20 5v6h-6" />
      <path d="M19.8 12.8A8 8 0 0 1 6.2 16.8L4 19v-6h6" />
    </>
  ),
  seguro: (
    <>
      <path d="M12 3.4 19.2 6.6v6c0 4.4-3.2 7.4-7.2 9-4-1.6-7.2-4.6-7.2-9v-6Z" />
      <path d="M12 10.2v4.2M9.9 12.3h4.2" />
    </>
  ),
  historico: (
    <>
      <path d="M4 8.2V4.2h4" />
      <path d="M4.6 4.8A8.2 8.2 0 1 1 4 12" />
      <path d="M12 8.8V13l2.8 1.6" />
    </>
  ),
  sair: (
    <>
      <path d="M10 19.2H6.4A1.6 1.6 0 0 1 4.8 17.6V6.4A1.6 1.6 0 0 1 6.4 4.8H10" />
      <path d="M13 12h7.2" />
      <path d="M17.2 8.6 20.6 12l-3.4 3.4" />
    </>
  ),
  busca: (
    <>
      <circle cx="11" cy="11" r="6.2" />
      <path d="m16 16 4.2 4.2" />
    </>
  ),
};

export default function IconeNav({ nome }) {
  const desenho = CAMINHOS[nome];
  if (!desenho) return null;
  return (
    <svg
      className="nav-icone"
      viewBox="0 0 24 24"
      width="16"
      height="16"
      aria-hidden="true"
      {...TRAÇO}
    >
      {desenho}
    </svg>
  );
}

export function RotuloNav({ icone, children }) {
  return (
    <span className="lista-filtros-lb">
      <IconeNav nome={icone} />
      {children}
    </span>
  );
}
