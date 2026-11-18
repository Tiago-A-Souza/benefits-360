import React from "react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import Ajuda from "./Ajuda.jsx";
import AjustesRobos from "./AjustesRobos.jsx";
import ConfigRobo from "./ConfigRobo.jsx";
import ImportarPlanilha from "./ImportarPlanilha.jsx";
import Inicio from "./Inicio.jsx";
import { OPERADORAS } from "./fixtureOperadoras";
import { TELAS_ROBO_NAO_PORTADAS } from "./regrasNova";
import { saudacao } from "./regrasRestante";

globalThis.React = React;

const dir = dirname(fileURLToPath(import.meta.url));

const TELAS_ROBO = [
  {
    etapa: "login",
    titulo: "Login",
    faz: "Entra no portal sozinho.",
    campos: [
      { tipo: "credenciais", rotulo: "Login no portal", ajuda: "Cofre do Windows." },
      {
        chave: "tempos.sair_do_portal_min",
        rotulo: "Sair do portal depois de (minutos sem pedidos)",
        tipo: "numero",
        minimo: 0,
        maximo: 120,
        valor: 3,
        padrao: 3,
      },
    ],
  },
  {
    etapa: "planos",
    titulo: "Planos",
    faz: "Marca os planos.",
    campos: [
      {
        chave: "padroes.planos_modo",
        rotulo: "Planos que já vêm marcados",
        tipo: "escolha",
        valor: "lista",
        padrao: "lista",
        opcoes: [
          ["lista", "Escolher na lista"],
          ["menor_preco", "Os mais baratos"],
        ],
      },
      {
        chave: "padroes.planos",
        rotulo: "Marcados na Nova cotação",
        tipo: "planos",
        valor: ["Especial Mais | Apartamento"],
        padrao: ["Especial Mais | Apartamento"],
        visivel_se: { "padroes.planos_modo": "lista" },
      },
    ],
  },
];

describe("Início, Ajuda, Importar, Ajustes", () => {
  it("Início mostra tarefas e não aponta senha nem robô antigo", () => {
    const html = renderToStaticMarkup(
      <Inicio
        operadoras={[{ ...OPERADORAS[0], login: { guardadas: false, recusadas: false } }]}
        trabalhoAtual={null}
      />,
    );
    expect(html).toContain(saudacao());
    expect(html).toContain("Nova cotação");
    expect(html).toContain("Importar planilha");
    expect(html).toContain("Cadastre o login da SulAmérica");
    expect(html).toContain("Cadastrar o login");
    expect(html).toContain("Empresas recentes");
    expect(html).toContain("Últimas cotações");
    expect(html).not.toContain("#/robo/");
    expect(html).not.toContain("127.0.0.1:8600");
    expect(html).not.toContain("type=\"password\"");
    expect(html).not.toContain("Newport");
  });

  it("Ajuda lista passos, perguntas e o aviso do simulador", () => {
    const html = renderToStaticMarkup(
      <Ajuda operadoras={OPERADORAS} retencaoDias={90} simulador />,
    );
    expect(html).toContain("Ajuda");
    expect(html).toContain("Do pedido ao PDF");
    expect(html).toContain("Perguntas frequentes");
    expect(html).toContain("Simulador local");
    expect(html).toContain("90 dias");
    expect(html).not.toContain("type=\"password\"");
  });

  it("Importar pede operadora, zona .xlsx e modelo", () => {
    const html = renderToStaticMarkup(<ImportarPlanilha operadoras={OPERADORAS} />);
    expect(html).toContain("Importar planilha");
    expect(html).toContain("SulAmérica");
    expect(html).toContain("Arraste a planilha para cá");
    expect(html).toContain("accept=\".xlsx\"");
    expect(html).toContain("Baixar a planilha modelo");
    expect(html).toContain("como_preencher");
    expect(html).not.toContain("Newport");
  });

  it("Ajustes lista cartões e painel geral, sem cartão de senha", () => {
    const html = renderToStaticMarkup(
      <AjustesRobos
        operadoras={OPERADORAS}
        conexao={{ sulamerica: "desconectado" }}
        indisponiveis={[{ nome: "Porto", motivo: "não carregou" }]}
      />,
    );
    expect(html).toContain("Robôs");
    expect(html).toContain("SulAmérica");
    expect(html).toContain("Para todos os robôs");
    expect(html).toContain("Guardar print de cada tela do portal");
    expect(html).toContain("Mostrar a janela do portal");
    expect(html).toContain("Pasta do robô");
    expect(html).toContain("Indisponível");
    expect(html).toContain("não carregou");
    expect(html).not.toContain("type=\"password\"");
    expect(html).not.toContain("127.0.0.1:8600/#/robo");
  });

  it("ConfigRobo manda login para Conexões e não desenha senha", () => {
    const html = renderToStaticMarkup(
      <ConfigRobo
        opId="sulamerica"
        operadoras={OPERADORAS}
        conexao={{ sulamerica: "conectado" }}
      />,
    );
    expect(html).toContain("Carregando configuração do robô");
    const src = readFileSync(join(dir, "ConfigRobo.jsx"), "utf8");
    expect(src).toContain('tipo === "credenciais"');
    expect(src).toContain("Abrir Conexões");
    expect(src).toContain("/api/robos/");
    expect(src).toContain("PUT");
    expect(src).toContain("DELETE");
    expect(src).not.toMatch(/type=["']password["']/);
    expect(src).not.toContain("/api/credenciais");
    void html;
  });

  it("telas novas não enviam senha nem chamam /api/credenciais", () => {
    for (const nome of ["Inicio.jsx", "Ajuda.jsx", "ImportarPlanilha.jsx", "AjustesRobos.jsx", "ConfigRobo.jsx"]) {
      const src = readFileSync(join(dir, nome), "utf8");
      expect(src).not.toMatch(/\/api\/credenciais/);
      expect(src).not.toMatch(/type=["']password["']/);
      expect(src).not.toContain("localStorage");
    }
  });

  it("seção No robô local some quando tudo está portado", () => {
    expect(TELAS_ROBO_NAO_PORTADAS).toEqual([]);
    const shell = readFileSync(join(dir, "CotacoesNativa.jsx"), "utf8");
    expect(shell).toContain("TELAS_ROBO_NAO_PORTADAS.length");
    expect(shell).toContain("#/inicio");
    expect(shell).toContain("#/importar");
    expect(shell).toContain("#/robos");
    expect(shell).toContain("#/ajuda");
    expect(shell).toContain("?cotacoes-iframe=1");
  });
});

describe("ConfigRobo — markup com dados da API", () => {
  it("não monta os campos sem fetch; o esquema de fixture cobre tipos usados", () => {
    expect(TELAS_ROBO[0].campos[0].tipo).toBe("credenciais");
    expect(TELAS_ROBO[1].campos.some((c) => c.tipo === "planos")).toBe(true);
  });
});
