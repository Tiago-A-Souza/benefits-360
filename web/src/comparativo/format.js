/** Formatação a partir de centavos inteiros — sem parse de strings R$. */

export function formatCentavos(centavos) {
  if (centavos == null || Number.isNaN(centavos)) return "—";
  const sinal = centavos < 0 ? "-" : "";
  const valor = Math.abs(Math.trunc(centavos));
  const reais = Math.floor(valor / 100);
  const cents = valor % 100;
  const inteiro = reais.toLocaleString("pt-BR");
  return `${sinal}R$ ${inteiro},${String(cents).padStart(2, "0")}`;
}

export function formatBps(bps) {
  if (bps == null || Number.isNaN(bps)) return "—";
  const sinal = bps > 0 ? "+" : "";
  const pct = bps / 100;
  const texto = pct.toFixed(1).replace(".", ",");
  return `${sinal}${texto}%`;
}

export const DESTAQUE_LABELS = {
  menor_mensalidade: "Menor mensalidade",
  menor_aumento: "Menor aumento",
  maior_economia: "Maior economia",
  mais_proximo_atual: "Mais próximo do contrato atual",
};

export const FAIXAS_ROTULOS = [
  "0–18",
  "19–23",
  "24–28",
  "29–33",
  "34–38",
  "39–43",
  "44–48",
  "49–53",
  "54–58",
  "59+",
];
