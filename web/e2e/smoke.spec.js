import { test, expect } from "@playwright/test";
import {
  CENARIOS_ROBO,
  coletarFalhas,
  interceptarApi,
  interceptarRobo,
  instalarSessaoDemo,
  assertTelaViva,
} from "./helpers.js";

const ABAS_COTACOES = [
  { botao: "Início", trecho: "Cotar uma empresa", hash: "#/inicio" },
  { botao: "Nova cotação", trecho: "Nova cotação", hash: "#/nova" },
  { botao: "Cotações", trecho: "Cotações", hash: "#/cotacoes" },
  { botao: "Importar planilha", trecho: "Importar planilha", hash: "#/importar" },
  { botao: "Conexões", trecho: "Conexões", hash: "#/conexoes" },
  { botao: "Ajustes dos robôs", trecho: "Robôs", hash: "#/robos" },
  { botao: "Ajuda", trecho: "Ajuda", hash: "#/ajuda" },
];

async function abrirApp(page, cenarioRobo) {
  const falhas = coletarFalhas(page);
  await interceptarApi(page);
  await interceptarRobo(page, cenarioRobo);
  await instalarSessaoDemo(page);
  await page.goto("/");
  await expect(page.locator("#root")).not.toBeEmpty();
  return falhas;
}

function navSistema(page) {
  return page.getByRole("navigation", { name: "Navegação do sistema" });
}

function navAbasCotacoes(page) {
  return page.getByRole("navigation", { name: "Cotações" });
}

async function irCotacoes(page) {
  await navSistema(page).getByRole("button", { name: "Cotações", exact: true }).click();
  await page.waitForTimeout(200);
}

async function irMeusEstudos(page) {
  await page.getByRole("button", { name: "Meus estudos", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Meus estudos" })).toBeVisible();
  await expectHash(page, "#/estudos");
}

async function expectHash(page, hash) {
  await expect.poll(async () => page.evaluate(() => window.location.hash)).toBe(hash);
}

async function abrirAppEm(page, cenarioRobo, caminho) {
  const falhas = coletarFalhas(page);
  await interceptarApi(page);
  await interceptarRobo(page, cenarioRobo);
  await instalarSessaoDemo(page);
  await page.goto(caminho);
  await expect(page.locator("#root")).not.toBeEmpty();
  return falhas;
}

async function varrerRotas(page, falhas, nomeCenario) {
  const checar = async (dica) => {
    await assertTelaViva(page, `${nomeCenario} · ${dica}`);
    if (falhas.excecoes.length) {
      throw new Error(`Exceção não tratada em ${nomeCenario} · ${dica}: ${falhas.excecoes.join(" | ")}`);
    }
    if (falhas.errosConsole.length) {
      throw new Error(`Erro no console em ${nomeCenario} · ${dica}: ${falhas.errosConsole.join(" | ")}`);
    }
  };

  await expect(page.getByRole("heading", { name: "Meus estudos" })).toBeVisible({ timeout: 15000 });
  await expectHash(page, "#/estudos");
  await expect(page.locator("header.topbar")).toHaveCount(0);
  await expect(page.getByText("Estudo Saúde")).toHaveCount(0);
  await expect(page.getByRole("img", { name: "Turya" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sair", exact: true })).toBeVisible();
  await expect(page.getByText("V1.0.0", { exact: true })).toBeVisible();
  await expect(page.getByText("RASCUNHO INTERNO")).toHaveCount(0);
  await checar("Meus estudos");

  await navSistema(page).getByRole("button", { name: "Simular rede", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Simular rede" })).toBeVisible();
  await expectHash(page, "#/simular-rede");
  await checar("Simular rede");

  await irMeusEstudos(page);
  await irCotacoes(page);
  await expectHash(page, "#/cotacoes");
  await checar("Cotações (entrada)");

  for (const aba of ABAS_COTACOES) {
    await navAbasCotacoes(page).getByRole("button", { name: aba.botao, exact: true }).click();
    await expect(page.locator("main").getByText(aba.trecho).first()).toBeVisible({ timeout: 10000 });
    await expectHash(page, aba.hash);
    await checar(`Cotações · ${aba.botao}`);
  }

  await irMeusEstudos(page);
  await expectHash(page, "#/estudos");
  await page.getByRole("button", { name: "Continuar", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Base atual|Referência/i })).toBeVisible({ timeout: 10000 });
  await expectHash(page, "#/estudos/demo-1/etapa/1");
  await checar("Etapa 1");

  const navEtapas = page.locator("nav[aria-label='Etapas do estudo']");
  await expect(navEtapas.getByRole("button").first()).toBeVisible();
  const n = await navEtapas.getByRole("button").count();
  expect(n).toBeGreaterThanOrEqual(5);
  for (let i = 0; i < n; i += 1) {
    await navEtapas.getByRole("button").nth(i).click();
    await expectHash(page, `#/estudos/demo-1/etapa/${i + 1}`);
    await checar(`Etapa ${i + 1}`);
  }
}

for (const [nome, cenario] of Object.entries(CENARIOS_ROBO)) {
  test(`fumaça · robô ${nome}`, async ({ page }) => {
    const falhas = await abrirApp(page, cenario);
    if (nome === "off") {
      await expect(page.getByRole("heading", { name: "Meus estudos" })).toBeVisible({ timeout: 15000 });
      await assertTelaViva(page, "off · Meus estudos");
      await navSistema(page).getByRole("button", { name: "Cotações", exact: true }).click();
      await expect(page.getByText(/não está ligado|não está no ar/i).first()).toBeVisible({ timeout: 10000 });
      await assertTelaViva(page, "off · Cotações");
      for (const aba of ABAS_COTACOES) {
        await navAbasCotacoes(page).getByRole("button", { name: aba.botao, exact: true }).click();
        await page.waitForTimeout(150);
        await assertTelaViva(page, `off · ${aba.botao}`);
      }
      await page.getByRole("button", { name: "Meus estudos", exact: true }).click();
      await navSistema(page).getByRole("button", { name: "Simular rede", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Simular rede" })).toBeVisible();
      await assertTelaViva(page, "off · Simular rede");
      await page.getByRole("button", { name: "Meus estudos", exact: true }).click();
      await page.getByRole("button", { name: "Continuar", exact: true }).click();
      const etapas = page.locator("nav[aria-label='Etapas do estudo'] button");
      const n = await etapas.count();
      for (let i = 0; i < n; i += 1) {
        await etapas.nth(i).click();
        await page.waitForTimeout(200);
        await assertTelaViva(page, `off · etapa ${i + 1}`);
      }
      if (falhas.excecoes.length) throw new Error(falhas.excecoes.join(" | "));
      if (falhas.errosConsole.length) throw new Error(falhas.errosConsole.join(" | "));
      return;
    }
    await varrerRotas(page, falhas, nome);
  });
}

test("hash #/conexoes após login não fica em branco", async ({ page }) => {
  const falhas = await abrirAppEm(page, CENARIOS_ROBO.antigo, "/#/conexoes");
  await expect(page.getByRole("heading", { name: "Conexões" })).toBeVisible({ timeout: 15000 });
  await expectHash(page, "#/conexoes");
  await assertTelaViva(page, "hash conexoes");
  expect(falhas.excecoes, falhas.excecoes.join(" | ")).toEqual([]);
  expect(falhas.errosConsole, falhas.errosConsole.join(" | ")).toEqual([]);
});

test("URL direta bate com a tela e não deixa o hash preso em Cotações", async ({ page }) => {
  const falhas = await abrirAppEm(page, CENARIOS_ROBO.real, "/#/conexoes");
  await expect(page.getByRole("heading", { name: "Conexões" })).toBeVisible({ timeout: 15000 });
  await expectHash(page, "#/conexoes");

  await irMeusEstudos(page);
  await assertTelaViva(page, "Meus estudos após Conexões");

  await page.goto("/#/simular-rede");
  await expect(page.getByRole("heading", { name: "Simular rede" })).toBeVisible({ timeout: 15000 });
  await expectHash(page, "#/simular-rede");
  await assertTelaViva(page, "URL Simular rede");

  await page.goto("/#/estudos");
  await expect(page.getByRole("heading", { name: "Meus estudos" })).toBeVisible({ timeout: 15000 });
  await expectHash(page, "#/estudos");
  await assertTelaViva(page, "URL Meus estudos");

  await page.goto("/#/estudos/demo-1/etapa/1");
  await expect(page.getByRole("heading", { name: /Base atual|Referência/i })).toBeVisible({ timeout: 15000 });
  await expectHash(page, "#/estudos/demo-1/etapa/1");
  await expect(page.getByText("Demo Ltda").first()).toBeVisible();
  await assertTelaViva(page, "URL etapa 1");

  await page.goto("/#/estudos/demo-1/etapa/3");
  await expectHash(page, "#/estudos/demo-1/etapa/3");
  await assertTelaViva(page, "URL etapa 3");

  await page.goto("/#/nao-existe");
  await expect(page.getByRole("heading", { name: "Esta página não existe" })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("Demo Ltda")).toHaveCount(0);
  await assertTelaViva(page, "URL inválida");

  await page.goto("/#/estudos/outro-user-99/etapa/1");
  await expect(page.getByRole("heading", { name: "Estudo não encontrado" })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/não foi encontrado ou você não tem acesso/i)).toBeVisible();
  await expect(page.getByText("Demo Ltda")).toHaveCount(0);
  await assertTelaViva(page, "estudo sem acesso");

  expect(falhas.excecoes, falhas.excecoes.join(" | ")).toEqual([]);
  expect(falhas.errosConsole, falhas.errosConsole.join(" | ")).toEqual([]);
});
