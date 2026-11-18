import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import NovaCotacao from "./NovaCotacao.jsx";
import Confirmacao from "./Confirmacao.jsx";
import FaixaCodigo from "./FaixaCodigo.jsx";
import FaixaProblemaLogin from "./FaixaProblemaLogin.jsx";
import FaixaTrabalho from "./FaixaTrabalho.jsx";
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
    expect(html).toContain("nativa-op-cartao");
    expect(html).toContain('data-cor-op="#F08810"');
    expect(html).toContain("--cor-op:#F08810");
    expect(html).toContain('alt="SulAmérica"');
    expect(html).not.toContain("nativa-logo-op-selo");
  });

  it("lista empresas recentes e o atalho cotar de novo", () => {
    const html = renderToStaticMarkup(
      <NovaCotacao
        operadoras={OPERADORAS}
        urlRobo="http://127.0.0.1:8600"
        empresasRecentes={[{ cnpj: CNPJ_OK, apelido: "Padaria do Centro", razao_social: "Padaria Centro Ltda" }]}
      />,
    );
    expect(html).toContain("Empresas recentes");
    expect(html).toContain("Padaria do Centro");
    expect(html).toContain("Cotar de novo");
    expect(html).toContain("nativa-empresas-cnpj");
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

describe("FaixaProblemaLogin e FaixaTrabalho", () => {
  it("mostra cadastro de login e o atalho da engrenagem", () => {
    const html = renderToStaticMarkup(
      <FaixaProblemaLogin
        problema={{ operadora: "sulamerica", motivo: "sem_credenciais" }}
        operadoras={OPERADORAS}
        urlRobo="http://127.0.0.1:8600"
        onFechar={() => {}}
      />,
    );
    expect(html).toContain("Cadastre o login da SulAmérica");
    expect(html).toContain("Abrir o login");
  });

  it("mostra acompanhar quando o robô está em outro pedido", () => {
    const html = renderToStaticMarkup(
      <FaixaTrabalho
        trabalho={{ id: 7 }}
        etapa={{ operadora: "sulamerica", etapa: "vidas", plano: "Especial Mais | Apartamento" }}
        operadoras={OPERADORAS}
        onAcompanhar={() => {}}
      />,
    );
    expect(html).toContain("Robô trabalhando");
    expect(html).toContain("Especial Mais");
    expect(html).toContain("Acompanhar");
  });

  it("mostra parando quando o corretor já pediu para parar", () => {
    const html = renderToStaticMarkup(
      <FaixaTrabalho
        trabalho={{ id: 7, parando: true }}
        etapa={{ operadora: "sulamerica", etapa: "vidas", plano: "Especial Mais | Apartamento" }}
        operadoras={OPERADORAS}
        onAcompanhar={() => {}}
      />,
    );
    expect(html).toContain("Parando o robô");
    expect(html).not.toContain("Robô trabalhando");
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
