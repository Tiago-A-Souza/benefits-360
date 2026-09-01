import { describe, expect, it } from "vitest";

import {
  ROSCA_CIRCUNFERENCIA,
  derivarGraficos,
  descricaoBarras,
  descricaoRosca,
  intensidadeBarra,
  percentuaisInteiros,
  rotuloCurto,
} from "./graficosFaixas.js";

// Fixtures geradas por `montar_tabela_faixas_cotacao` e travadas em
// tests/test_graficos_etapa1.py — mesma fonte da tabela da etapa 1.
import anistia41 from "./__fixtures__/tabelaAnistia41.json";
import ivtec12ComSexo from "./__fixtures__/tabelaIvtec12ComSexo.json";
import mesmaFaixa from "./__fixtures__/tabelaMesmaFaixa.json";
import semSexo12 from "./__fixtures__/tabelaSemSexo12.json";
import sexoParcial from "./__fixtures__/tabelaSexoParcial.json";
import tresIguais from "./__fixtures__/tabelaTresIguais.json";
import trezentas from "./__fixtures__/tabela300Vidas.json";
import umaVida from "./__fixtures__/tabelaUmaVida.json";

function fatia(rosca, chave) {
  return rosca.todas.find((f) => f.chave === chave);
}

function somaColunas(tabela, campos) {
  return tabela.linhas.reduce(
    (soma, ln) => soma + campos.reduce((s, c) => s + (ln[c] || 0), 0),
    0,
  );
}

describe("rosca de sexo", () => {
  it("Anistia: 29 femininos e 12 masculinos", () => {
    const { rosca } = derivarGraficos(anistia41);
    expect(rosca.total).toBe(41);
    expect(fatia(rosca, "feminino").valor).toBe(29);
    expect(fatia(rosca, "masculino").valor).toBe(12);
    expect(fatia(rosca, "nao_informado")).toBeUndefined();
  });

  it("lê as mesmas células que a tabela exibe", () => {
    const { rosca } = derivarGraficos(anistia41);
    expect(fatia(rosca, "feminino").valor).toBe(
      somaColunas(anistia41, ["tit_f", "dep_f"]),
    );
    expect(fatia(rosca, "masculino").valor).toBe(
      somaColunas(anistia41, ["tit_m", "dep_m"]),
    );
    expect(rosca.total).toBe(anistia41.total_vidas);
  });

  it("uma vida só: fatia cheia, sem sobra de arco", () => {
    const { rosca } = derivarGraficos(umaVida);
    expect(rosca.total).toBe(1);
    expect(rosca.fatias).toHaveLength(1);
    expect(rosca.fatias[0].completa).toBe(true);
    expect(rosca.fatias[0].percentual).toBe(100);
  });

  it("todas do mesmo sexo: 100% de um lado, 0% sem desenhar risco", () => {
    const { rosca } = derivarGraficos(umaVida);
    expect(fatia(rosca, "masculino").valor).toBe(0);
    expect(fatia(rosca, "masculino").percentual).toBe(0);
    // A fatia de zero fica fora do desenho — só aparece na legenda.
    expect(rosca.fatias.map((f) => f.chave)).toEqual(["feminino"]);
  });

  it("arcos consecutivos cobrem a circunferência sem folga", () => {
    const { rosca } = derivarGraficos(anistia41);
    const ultima = rosca.fatias[rosca.fatias.length - 1];
    expect(ultima.offset + ultima.comprimento).toBeCloseTo(
      ROSCA_CIRCUNFERENCIA,
      6,
    );
  });
});

describe("percentuais", () => {
  it("somam exatamente 100 com três terços", () => {
    const { rosca } = derivarGraficos(tresIguais);
    const pcts = rosca.todas.map((f) => f.percentual);
    expect(pcts).toEqual([34, 33, 33]);
    expect(pcts.reduce((s, v) => s + v, 0)).toBe(100);
  });

  it("somam 100 em todas as bases", () => {
    for (const tabela of [anistia41, ivtec12ComSexo, sexoParcial, trezentas]) {
      const { rosca } = derivarGraficos(tabela);
      const soma = rosca.todas.reduce((s, f) => s + f.percentual, 0);
      expect(soma).toBe(100);
    }
  });

  it("não empresta percentual para categoria vazia", () => {
    expect(percentuaisInteiros([1, 1, 1])).toEqual([34, 33, 33]);
    expect(percentuaisInteiros([1, 0])).toEqual([100, 0]);
    expect(percentuaisInteiros([0, 0])).toEqual([0, 0]);
  });
});

describe("barras por faixa", () => {
  it("Anistia: dez faixas somando 41 vidas", () => {
    const { barras } = derivarGraficos(anistia41);
    expect(barras.itens).toHaveLength(10);
    expect(barras.total).toBe(41);
    expect(barras.itens.map((i) => i.valor)).toEqual(
      anistia41.linhas.map((l) => l.total),
    );
  });

  it("faixa sem ninguém aparece com zero", () => {
    const { barras } = derivarGraficos(umaVida);
    expect(barras.itens.filter((i) => i.valor === 0)).toHaveLength(9);
    expect(barras.itens.filter((i) => i.valor > 0)).toHaveLength(1);
  });

  it("todas na mesma faixa: uma coluna cheia, as outras zeradas", () => {
    const { barras } = derivarGraficos(mesmaFaixa);
    const cheias = barras.itens.filter((i) => i.fracao === 1);
    expect(cheias).toHaveLength(1);
    expect(cheias[0].valor).toBe(barras.maior);
    expect(barras.itens.filter((i) => i.fracao === 0)).toHaveLength(9);
  });

  it("base grande: a faixa pequena continua com fração própria", () => {
    const { barras } = derivarGraficos(trezentas);
    expect(barras.total).toBe(300);
    const pequena = barras.itens.find((i) => i.valor === 1);
    expect(pequena.fracao).toBeGreaterThan(0);
    expect(pequena.fracao).toBeLessThan(0.01);
    expect(barras.maior).toBe(190);
  });

  it("intensidade acompanha o valor sem inverter ordem", () => {
    const { barras } = derivarGraficos(anistia41);
    const porValor = [...barras.itens].sort((a, b) => a.valor - b.valor);
    for (let i = 1; i < porValor.length; i += 1) {
      expect(porValor[i].intensidade).toBeGreaterThanOrEqual(
        porValor[i - 1].intensidade,
      );
    }
    expect(barras.itens.find((i) => i.valor === barras.maior).intensidade).toBe(1);
  });

  it("a rampa não amontoa os valores baixos sob uma faixa dominante", () => {
    // Distribuição relatada em tela: 1, 3, 4 e 10 vidas, pico de 10. No mapa
    // linear, 1 e 4 saíam quase da mesma cor e só o pico se destacava.
    const de = (v) => intensidadeBarra(v / 10);
    const passoBaixo = de(4) - de(1);
    const passoAlto = de(10) - de(4);
    expect(passoBaixo).toBeGreaterThan(0.2);
    // Nenhum trecho da escala domina o outro por mais que o dobro.
    expect(passoAlto / passoBaixo).toBeLessThan(2);
    // A ordem das quatro continua estrita.
    expect([de(1), de(3), de(4), de(10)]).toEqual(
      [de(1), de(3), de(4), de(10)].slice().sort((a, b) => a - b),
    );
  });

  it("barra vazia não recebe tinta; piso mantém a menor visível", () => {
    expect(intensidadeBarra(0)).toBe(0);
    expect(intensidadeBarra(1)).toBe(1);
    const { barras } = derivarGraficos(trezentas);
    const minima = barras.itens.find((i) => i.valor === 1).intensidade;
    expect(minima).toBeGreaterThan(0.18);
    expect(minima).toBeLessThan(0.3);
    expect(barras.itens.find((i) => i.valor === 0).intensidade).toBe(0);
  });

  it("rótulo curto encurta sem reescrever a faixa", () => {
    expect(rotuloCurto("0 a 18")).toBe("0\u201318");
    expect(rotuloCurto("59+")).toBe("59+");
    const { barras } = derivarGraficos(anistia41);
    expect(barras.itens.map((i) => i.rotulo)).toEqual(
      anistia41.linhas.map((l) => l.rotulo),
    );
  });
});

describe("disponibilidade", () => {
  it("base sem coluna SEXO: nenhum gráfico, nenhum botão", () => {
    expect(derivarGraficos(semSexo12)).toEqual({ disponivel: false });
  });

  it("payload ausente ou vazio não quebra", () => {
    expect(derivarGraficos(null).disponivel).toBe(false);
    expect(derivarGraficos({}).disponivel).toBe(false);
    expect(derivarGraficos({ modo_sexo: "completo", linhas: [] }).disponivel).toBe(
      false,
    );
  });

  it("base com zero vidas não vira gráfico vazio", () => {
    const vazia = {
      ...anistia41,
      linhas: anistia41.linhas.map((l) => ({
        ...l,
        tit_f: 0,
        tit_m: 0,
        dep_f: 0,
        dep_m: 0,
        total: 0,
      })),
    };
    expect(derivarGraficos(vazia).disponivel).toBe(false);
  });
});

describe("sexo parcialmente preenchido", () => {
  it("não distribui entre F e M e não some das barras", () => {
    const { rosca, barras } = derivarGraficos(sexoParcial);
    expect(fatia(rosca, "feminino").valor).toBe(2);
    expect(fatia(rosca, "masculino").valor).toBe(0);
    expect(fatia(rosca, "nao_informado").valor).toBe(2);
    expect(rosca.total).toBe(4);
    expect(barras.total).toBe(sexoParcial.total_vidas);
  });
});

describe("troca de base", () => {
  it("substituir a planilha muda rosca e barras", () => {
    const antes = derivarGraficos(anistia41);
    const depois = derivarGraficos(ivtec12ComSexo);

    expect(fatia(antes.rosca, "feminino").valor).toBe(29);
    expect(fatia(antes.rosca, "masculino").valor).toBe(12);

    expect(fatia(depois.rosca, "feminino").valor).toBe(6);
    expect(fatia(depois.rosca, "masculino").valor).toBe(6);
    expect(depois.rosca.total).toBe(12);

    expect(depois.barras.itens.map((i) => i.valor)).not.toEqual(
      antes.barras.itens.map((i) => i.valor),
    );
    expect(depois.barras.total).toBe(12);
  });
});

describe("alternativa textual", () => {
  it("descreve a rosca com valores e percentuais", () => {
    const { rosca } = derivarGraficos(anistia41);
    const texto = descricaoRosca(rosca);
    expect(texto).toContain("41 vidas");
    expect(texto).toContain("Feminino: 29 (71%)");
    expect(texto).toContain("Masculino: 12 (29%)");
  });

  it("descreve as barras incluindo faixas com zero", () => {
    const { barras } = derivarGraficos(umaVida);
    const texto = descricaoBarras(barras);
    expect(texto).toContain("1 no total");
    expect(texto).toContain("0 a 18: 0");
    expect(texto).toContain("24 a 28: 1");
  });
});
