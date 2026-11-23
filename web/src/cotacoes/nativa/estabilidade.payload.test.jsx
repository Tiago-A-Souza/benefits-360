import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import AjustesRobos from "./AjustesRobos.jsx";
import Conexoes from "./Conexoes.jsx";
import NovaCotacao from "./NovaCotacao.jsx";
import Andamento from "./Andamento.jsx";
import { TabelaResultado } from "../../simularRede/SimularRede.jsx";
import { TabelaLabs } from "../../simularRede/SimularLabs.jsx";

globalThis.React = React;

const OP_SEM_CAMPOS = { id: "amil", nome: "Amil", produto: "PME", conexao: "desconectado" };

describe("payload antigo / incompleto não derruba o render", () => {
  it("Conexoes aceita operadoras sem campos e conexao nula", () => {
    const html = renderToStaticMarkup(
      <Conexoes operadoras={[OP_SEM_CAMPOS]} conexao={null} indisponiveis={null} />
    );
    expect(html).toContain("Conexões");
    expect(html).toContain("Amil");
  });

  it("Conexoes aceita operadoras como objeto", () => {
    const html = renderToStaticMarkup(
      <Conexoes operadoras={{ operadoras: [OP_SEM_CAMPOS] }} conexao={{}} />
    );
    expect(html).toContain("Conexões");
  });

  it("Ajustes aceita operadora sem campos", () => {
    const html = renderToStaticMarkup(
      <AjustesRobos operadoras={[OP_SEM_CAMPOS]} conexao={null} />
    );
    expect(html).toContain("Robôs");
  });

  it("Nova cotação aceita operadora sem campos", () => {
    const html = renderToStaticMarkup(
      <NovaCotacao operadoras={[OP_SEM_CAMPOS]} conexao={{}} />
    );
    expect(html).toContain("Nova cotação");
  });

  it("Andamento aceita operadora sem etapas", () => {
    const html = renderToStaticMarkup(
      <Andamento
        trabalhoId={1}
        operadoras={[OP_SEM_CAMPOS]}
        conexaoExterna={{}}
      />
    );
    expect(html).toMatch(/Carregando o pedido|Pedido não encontrado|Pedido/i);
  });

  it("Simular rede e labs aceitam resposta vazia", () => {
    expect(renderToStaticMarkup(<TabelaResultado resp={null} />)).toContain("Nenhum resultado");
    expect(renderToStaticMarkup(<TabelaLabs resp={null} />)).toContain("Nenhum resultado");
    expect(
      renderToStaticMarkup(<TabelaResultado resp={{}} />)
    ).toContain("Prestador");
    expect(renderToStaticMarkup(<TabelaLabs resp={{}} />)).toContain("Laboratório");
  });
});
