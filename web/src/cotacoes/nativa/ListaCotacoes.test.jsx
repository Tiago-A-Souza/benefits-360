import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import ListaCotacoes from "./ListaCotacoes.jsx";
import TabelaCotacoes from "./TabelaCotacoes.jsx";
import Conexoes from "./Conexoes.jsx";
import { OPERADORAS } from "./fixtureOperadoras";
import { FILTROS_LISTA, formatarValorRobo } from "./regrasNova";

globalThis.React = React;

const COTA = {
  id: 11,
  cnpj: "11444777000161",
  razao_social: "Empresa Teste",
  plano: "Especial Mais",
  acomodacao: "Apartamento",
  total_com_iof: 58.16,
  protocolo: "8601801",
  status: "OK",
  tem_pdf: true,
  criado_em: "2026-11-17T12:00:00",
  operadora: "sulamerica",
};

describe("ListaCotacoes e Conexões", () => {
  it("filtros da lista são os do RPA", () => {
    expect(FILTROS_LISTA.map(([, t]) => t)).toEqual(["Emitidas", "Não emitidas", "Ensaios", "Tudo"]);
  });

  it("tabela lista mostra empresa, data, seleção, PDF e centavos", () => {
    const html = renderToStaticMarkup(
      <TabelaCotacoes
        cotacoes={[COTA]}
        empresa
        data
        selecao={new Set()}
        cotarDeNovo
        onCotarDeNovo={() => {}}
        operadoras={OPERADORAS}
      />,
    );
    expect(html).toContain("Empresa Teste");
    expect(html).toContain("Especial Mais");
    expect(html).toContain("Baixar PDF");
    expect(html).toContain("Abrir pasta");
    expect(html).toContain("cotar de novo");
    expect(html).toContain("Quando");
    expect(html).toContain(formatarValorRobo(58.16));
    expect(html).not.toContain("Newport");
  });

  it("lista vazia ainda mostra título e busca (sem fetch no SSR)", () => {
    const html = renderToStaticMarkup(<ListaCotacoes operadoras={OPERADORAS} />);
    expect(html).toContain("Cotações");
    expect(html).toContain("Tudo o que o robô já cotou");
    expect(html).toContain("Emitidas");
    expect(html).toContain("Buscar por empresa");
  });

  it("conexões mostram status, login e link do robô em outra aba", () => {
    const html = renderToStaticMarkup(
      <Conexoes
        operadoras={OPERADORAS}
        conexao={{ sulamerica: "desconectado" }}
        urlRobo="http://127.0.0.1:8600"
      />,
    );
    expect(html).toContain("Conexões");
    expect(html).toContain("SulAmérica");
    expect(html).toContain("Desconectado");
    expect(html).toContain("http://127.0.0.1:8600/#/robo/sulamerica");
    expect(html).toContain("abre o robô local em outra aba");
    expect(html).toContain("Configurar no robô");
  });
});
