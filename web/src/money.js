/** Conversão monetária exata — sem float nem Math.round. */

export function centavosParaReaisTexto(centavos) {
  if (centavos == null || Number.isNaN(centavos)) return "";
  let neg = false;
  let v = centavos;
  if (v < 0) {
    neg = true;
    v = -v;
  }
  const reais = Math.trunc(v / 100);
  const cents = v % 100;
  const texto = `${reais},${String(cents).padStart(2, "0")}`;
  return neg ? `-${texto}` : texto;
}

export function centavosParaReaisExibicao(centavos) {
  if (centavos == null) return "—";
  let neg = centavos < 0;
  let v = neg ? -centavos : centavos;
  const reais = Math.trunc(v / 100);
  const cents = v % 100;
  const inteiro = String(reais).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const sinal = neg ? "-" : "";
  return `${sinal}R$ ${inteiro},${String(cents).padStart(2, "0")}`;
}

/** Formata um diff já calculado no backend. Não subtrai nem estima. */
export function formatarDiffCentavos(centavos) {
  if (centavos == null) return null;
  const texto = centavosParaReaisExibicao(Math.abs(centavos));
  if (centavos > 0) return `+${texto}`;
  if (centavos < 0) return `-${texto}`;
  return texto;
}

/** Mesma regra do HTML: negativo (economia) verde, positivo (acréscimo) vermelho. */
export function classeDiffEstimativa(centavos) {
  if (centavos == null) return null;
  if (centavos < 0) return "cmp-valor--economia";
  if (centavos > 0) return "cmp-valor--aumento";
  return "cmp-valor--neutro";
}

export function reaisTextoParaCentavos(texto) {
  if (texto == null) return { ok: false, erro: "Informe um valor." };
  const bruto = String(texto).trim().replace(/\s/g, "");
  if (!bruto) return { ok: false, erro: "Informe um valor." };

  let negativo = false;
  let s = bruto;
  if (s.startsWith("-")) {
    negativo = true;
    s = s.slice(1);
  }
  if (!/^\d[\d.,]*$/.test(s)) {
    return { ok: false, erro: "Use apenas números, vírgula ou ponto." };
  }

  let parteInteira = s;
  let parteDecimal = "00";

  if (s.includes(",")) {
    const idx = s.lastIndexOf(",");
    parteInteira = s.slice(0, idx).replace(/\./g, "") || "0";
    parteDecimal = s.slice(idx + 1);
  } else if (s.includes(".")) {
    const idx = s.lastIndexOf(".");
    const depois = s.slice(idx + 1);
    if (depois.length <= 2) {
      parteInteira = s.slice(0, idx).replace(/\./g, "") || "0";
      parteDecimal = depois;
    } else {
      parteInteira = s.replace(/\./g, "");
    }
  }

  if (!/^\d+$/.test(parteInteira) || (parteDecimal && !/^\d+$/.test(parteDecimal))) {
    return { ok: false, erro: "Valor monetário inválido." };
  }

  parteDecimal = (parteDecimal + "00").slice(0, 2);
  const centavos =
    parseInt(parteInteira, 10) * 100 + parseInt(parteDecimal.slice(0, 2), 10);
  if (Number.isNaN(centavos)) {
    return { ok: false, erro: "Valor monetário inválido." };
  }
  if (centavos < 0 || negativo) {
    return { ok: false, erro: "Valor negativo não é permitido." };
  }
  return { ok: true, centavos };
}
