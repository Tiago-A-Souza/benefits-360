import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import NovaCotacao from "./NovaCotacao.jsx";
import Confirmacao from "./Confirmacao.jsx";
import FaixaCodigo from "./FaixaCodigo.jsx";
import TabelaCotacoes from "./TabelaCotacoes.jsx";
import Andamento from "./Andamento.jsx";
import { CNPJ_OK, OPERADORAS } from "./fixtureOperadoras";

globalThis.React = React;

describe("NovaCotacao — markup a partir da API", () => {
  it("mostra faixas, ajuda, planos e botões ensaio/emitir", () => {
    const html = renderToStaticMarkup(
      <NovaCotacao operadoras={OPERADORAS} urlRobo="http://127.0.0.1:8600" />,
    );
    expect(html).toContain("Nova cotação");
    expect(html).toContain("O robô busca a razão social no portal pelo CNPJ.");
    expect(html).toContain("Vidas por faixa etária");
    expect(html).toContain("0 - 18");
    expect(html).toContain("Nas faixas com * o portal pede a idade");
    expect(html).toContain("SulAmérica");
    expect(html).toContain("Especial Mais");
    expect(html).toContain("Ensaiar sem emitir");
    expect(html).toContain("Gerar 2 cotações");
    expect(html).toContain("Escolher pasta");
    expect(html).toContain("Mudar só nesta cotação");
    expect(html).toContain("SULAMERICA");
    expect(html).not.toContain("Newport");
  });
});

describe("Confirmacao", () => {
  it("começa com OK desabilitado (atraso de 500 ms)", () => {
    const html = renderToStaticMarkup(
      <Confirmacao titulo="Gerar 1 cotação na SulAmérica?" texto={["Cada cotação gera um protocolo."]} ok="Gerar 1 cotação" onFechar={() => {}} />,
    );
    expect(html).toContain("Gerar 1 cotação na SulAmérica?");
    expect(html).toContain("disabled");
    expect(html).toContain("Voltar");
  });
});

describe("FaixaCodigo", () => {
  it("aparece quando a operadora espera o código", () => {
    const html = renderToStaticMarkup(
      <FaixaCodigo conexao={{ sulamerica: "aguardando_codigo" }} operadoras={OPERADORAS} />,
    );
    expect(html).toContain("Digite o código que chegou");
    expect(html).toContain("SulAmérica");
    expect(html).toContain("Enviar código");
  });

  it("some quando ninguém espera código", () => {
    const html = renderToStaticMarkup(
      <FaixaCodigo conexao={{ sulamerica: "conectado" }} operadoras={OPERADORAS} />,
    );
    expect(html).toBe("");
  });
});

describe("TabelaCotacoes", () => {
  it("mostra plano, protocolo, selo e valor sem float", () => {
    const html = renderToStaticMarkup(
      <TabelaCotacoes
        operadoras={OPERADORAS}
        cotacoes={[
          {
            id: 1,
            operadora: "sulamerica",
            plano: "Especial Mais",
            acomodacao: "Apartamento",
            versao: "com",
            total_com_iof: "1234.56",
            protocolo: "P1",
            status: "OK",
            tem_pdf: true,
            cnpj: CNPJ_OK,
          },
        ]}
      />,
    );
    expect(html).toContain("Especial Mais");
    expect(html).toContain("com coparticipação");
    expect(html).toContain("R$");
    expect(html).toContain("1.234,56");
    expect(html).toContain("Emitida");
    expect(html).toContain("Baixar PDF");
    expect(html).toContain("Abrir pasta");
  });
});

describe("Andamento — pedido ausente e rodando", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        headers: { get: () => "application/json" },
        json: async () => ({ erro: "não encontrado" }),
      }),
    );
    vi.stubGlobal(
      "EventSource",
      class {
        close() {}
      },
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("pedido não encontrado", () => {
    const html = renderToStaticMarkup(
      <Andamento trabalhoId={99} operadoras={OPERADORAS} />,
    );
    expect(html).toContain("Carregando o pedido");
  });
});
