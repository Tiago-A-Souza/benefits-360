/** Marca visual das operadoras (logo + cor). O id enviado ao robô continua sulamerica | bradesco | amil. */

export const MARCA_OPERADORAS = {
  sulamerica: {
    nome: "SulAmérica",
    logo: "/operadoras/sulamerica.png",
    cor: "#F26522",
    corSuave: "rgba(242, 101, 34, 0.12)",
  },
  bradesco: {
    nome: "Bradesco",
    logo: "/operadoras/bradesco.svg",
    cor: "#CC092F",
    corSuave: "rgba(204, 9, 47, 0.12)",
  },
  amil: {
    nome: "Amil",
    logo: "/operadoras/amil.png",
    cor: "#0072BC",
    corSuave: "rgba(0, 114, 188, 0.12)",
  },
};

const FALLBACK = {
  nome: "",
  logo: null,
  cor: "#0b1f36",
  corSuave: "rgba(11, 31, 54, 0.12)",
};

export function marcaOperadora(id) {
  const chave = String(id || "").toLowerCase();
  const m = MARCA_OPERADORAS[chave];
  if (!m) return { ...FALLBACK, nome: id || "" };
  return m;
}

export function estiloMarcaOperadora(id) {
  const m = marcaOperadora(id);
  return { "--cor-op": m.cor, "--cor-op-suave": m.corSuave };
}

export function classeCartaoOperadora(ativo) {
  return `nativa-op-cartao${ativo ? " nativa-op-cartao--ativo" : ""}`;
}
