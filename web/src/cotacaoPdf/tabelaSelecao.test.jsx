/** Grade da etapa 3: alinhamento, acomodação curta, Copart. condicional, sem Δ %. */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

globalThis.React = React;

import { TabelaSelecaoCompacta } from "../CotacaoPdfPanel.jsx";
import {
  abreviarAcomodacao,
  agruparOpcoes,
  formatarDiferencaReferencia,
  ocultaColunaCopart,
} from "./utils.js";

function opcao(id, nome, extras = {}) {
  return {
    id,
    plano_nome: { texto: nome },
    acomodacao: extras.acomodacao ? { texto: extras.acomodacao } : { texto: "Apartamento" },
    regime_copart: { texto: extras.regime || "sem" },
    copart_percentual: extras.pct != null ? { inteiro: extras.pct } : null,
    selecionada_para_comparativo: Boolean(extras.selecionada),
    tabela: extras.tabela || [],
  };
}

function renderTabela({ templateId, opcoes, estimativasMotor, referenciaCentavos }) {
  return renderToStaticMarkup(
    <TabelaSelecaoCompacta
      opcoes={opcoes}
      templateId={templateId}
      quantidades={{ "0 a 18": 1 }}
      siscorCtx={{ exigeEscolha: false, totalGrupos: 1, grupoSelecionado: true }}
      estimativasMotor={estimativasMotor}
      referenciaCentavos={referenciaCentavos}
      selecionados={{
        filtros: { busca: "", acomodacao: "", regime: "", regiao: "" },
        setFiltro: () => {},
      }}
      opcoesComparativo={[]}
      onToggle={() => {}}
    />
  );
}

describe("abreviarAcomodacao", () => {
  it("troca Apartamento e Enfermaria por Apt. e Enf.", () => {
    expect(abreviarAcomodacao("Apartamento")).toBe("Apt.");
    expect(abreviarAcomodacao("Enfermaria")).toBe("Enf.");
    expect(abreviarAcomodacao("—")).toBe("—");
  });
});

describe("ocultaColunaCopart", () => {
  it("só some quando a seção já tem título de regime", () => {
    expect(ocultaColunaCopart("Sem coparticipação")).toBe(true);
    expect(ocultaColunaCopart("Coparticipação 30%")).toBe(true);
    expect(ocultaColunaCopart(null)).toBe(false);
    expect(ocultaColunaCopart("")).toBe(false);
  });
});

describe("agruparOpcoes", () => {
  it("agrupa SulAmérica e Porto; as demais ficam numa lista só", () => {
    const ops = [opcao("a", "Plano A")];
    expect(agruparOpcoes(ops, "porto-pme-1")[0].titulo).toBe("Sem coparticipação");
    expect(agruparOpcoes(ops, "sulamerica-pme-1")[0].titulo).toBe("Sem coparticipação");
    expect(agruparOpcoes(ops, "amil-pme-1")[0].titulo).toBe(null);
  });
});

describe("TabelaSelecaoCompacta", () => {
  const diamante = 9069135;
  const ouro = 3277183;
  const prata = 2305834;
  const referenciaDeltaExemplo = diamante - 6134600;

  it("cabeçalho numérico usa a mesma classe de alinhamento à direita", () => {
    const html = renderTabela({
      templateId: "amil-pme",
      opcoes: [opcao("d", "Diamante")],
      estimativasMotor: { d: diamante },
      referenciaCentavos: referenciaDeltaExemplo,
    });
    expect(html).toMatch(/linha-plano-meta--valor">Mensal est\.</);
    expect(html).toMatch(/linha-plano-meta--valor">Δ R\$</);
    expect(html).not.toContain("Δ %");
  });

  it("mostra R$ 90.691,35 na mensal e +R$ 61.346,00 na Δ R$, sem Δ %", () => {
    const html = renderTabela({
      templateId: "amil-pme",
      opcoes: [opcao("d", "Diamante Mais 1 Q")],
      estimativasMotor: { d: diamante },
      referenciaCentavos: referenciaDeltaExemplo,
    });
    expect(html).toContain("R$ 90.691,35");
    expect(html).toContain("+R$ 61.346,00");
    expect(html).not.toContain("Δ %");
    const delta = formatarDiferencaReferencia(diamante, referenciaDeltaExemplo);
    expect(html).not.toContain(delta.textoPct);
  });

  it("repete Copart. só quando não há título de seção", () => {
    const ops = [
      opcao("a", "Plano Apt", { acomodacao: "Apartamento" }),
      opcao("e", "Plano Enf", { acomodacao: "Enfermaria" }),
    ];
    const semGrupo = renderTabela({
      templateId: "amil-pme",
      opcoes: ops,
      estimativasMotor: { a: diamante, e: prata },
      referenciaCentavos: referenciaDeltaExemplo,
    });
    expect(semGrupo).toContain("Copart.");
    expect(semGrupo).toContain("Sem coparticipação");

    const comGrupo = renderTabela({
      templateId: "porto-pme-1",
      opcoes: ops,
      estimativasMotor: { a: diamante, e: prata },
      referenciaCentavos: referenciaDeltaExemplo,
    });
    expect(comGrupo).toContain("Sem coparticipação");
    expect(comGrupo).toContain("grupo-planos-titulo");
    const aposTitulo = comGrupo.split("grupo-planos-titulo")[1];
    expect(aposTitulo).not.toContain("Copart.");
  });

  it("abrevia acomodação e guarda o nome completo no title", () => {
    const html = renderTabela({
      templateId: "amil-pme",
      opcoes: [
        opcao("a", "Plano Apt", { acomodacao: "Apartamento" }),
        opcao("e", "Plano Enf", { acomodacao: "Enfermaria" }),
      ],
      estimativasMotor: { a: ouro, e: prata },
      referenciaCentavos: 4847931,
    });
    expect(html).toContain(">Apt.<");
    expect(html).toContain(">Enf.<");
    expect(html).toContain('title="Apartamento"');
    expect(html).toContain('title="Enfermaria"');
    expect(html).not.toContain("Apartame…");
  });

  it("não altera os mensais do S750 (Diamante, Ouro, Prata)", () => {
    const html = renderTabela({
      templateId: "amil-pme",
      opcoes: [
        opcao("diamante", "Diamante"),
        opcao("ouro", "Ouro"),
        opcao("prata", "Prata"),
      ],
      estimativasMotor: { diamante, ouro, prata },
      referenciaCentavos: 2938676,
    });
    expect(html).toContain("R$ 90.691,35");
    expect(html).toContain("R$ 32.771,83");
    expect(html).toContain("R$ 23.058,34");
  });
});
