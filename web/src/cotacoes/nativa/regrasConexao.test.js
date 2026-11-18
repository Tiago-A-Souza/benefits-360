import { describe, expect, it } from "vitest";
import {
  acaoLoginDoCartao,
  campoCredenciais,
  camposComEspaco,
  corpoLoginParaRobo,
  limparSenhas,
  validarLoginLocal,
  valoresLoginVazios,
} from "./regrasConexao";

const CAMPOS_SUL = [
  { chave: "cpf", rotulo: "CPF", tipo: "cpf", artigo: "o" },
  { chave: "email", rotulo: "E-mail", tipo: "email", mascara: "email", artigo: "o" },
  { chave: "senha", rotulo: "Senha", tipo: "senha", artigo: "a" },
];

describe("regrasConexao", () => {
  it("extrai campos de credenciais das telas do robô", () => {
    const telas = [{ etapa: "login", campos: [{ tipo: "credenciais", senha_max: 16, campos: CAMPOS_SUL }] }];
    expect(campoCredenciais(telas).senha_max).toBe(16);
    expect(campoCredenciais(telas).campos).toHaveLength(3);
  });

  it("monta o corpo e limpa senhas depois", () => {
    const valores = { cpf: "52998224725", email: "a@b.co", senha: "Segredo#1" };
    expect(corpoLoginParaRobo(CAMPOS_SUL, valores)).toEqual(valores);
    expect(limparSenhas(valores, CAMPOS_SUL)).toEqual({ cpf: "52998224725", email: "a@b.co", senha: "" });
    expect(valoresLoginVazios(CAMPOS_SUL).senha).toBe("");
  });

  it("valida CPF e teto da senha", () => {
    expect(validarLoginLocal(CAMPOS_SUL, { cpf: "111", senha: "x" }, 16).length).toBeGreaterThan(0);
    expect(validarLoginLocal(CAMPOS_SUL, { cpf: "52998224725", senha: "12345678901234567" }, 16)[0]).toMatch(/máximo 16/);
    expect(camposComEspaco(CAMPOS_SUL, { email: " a@b.co " })).toHaveLength(1);
  });

  it("ação do cartão: cadastrar, testar, sair", () => {
    expect(acaoLoginDoCartao({ login: { guardadas: false } }, "desconectado").tipo).toBe("cadastrar");
    expect(acaoLoginDoCartao({ login: { guardadas: true, recusadas: true } }, "desconectado").tipo).toBe("atualizar");
    expect(acaoLoginDoCartao({ login: { guardadas: true } }, "desconectado").tipo).toBe("testar");
    const sair = acaoLoginDoCartao({ login: { guardadas: true } }, "conectado", { atual: null, naFila: [] });
    expect(sair).toMatchObject({ tipo: "sair", livre: true });
    expect(acaoLoginDoCartao({ login: { guardadas: true } }, "ocupado", { atual: { id: 1 } }).livre).toBe(false);
  });
});
