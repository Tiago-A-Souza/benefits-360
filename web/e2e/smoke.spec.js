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
  { botao: "Início", trecho: "Cotar uma empresa" },
  { botao: "Nova cotação", trecho: "Nova cotação" },
  { botao: "Cotações", trecho: "Cotações" },
  { botao: "Importar planilha", trecho: "Importar planilha" },
  { botao: "Conexões", trecho: "Conexões" },
  { botao: "Ajustes dos robôs", trecho: "Robôs" },
  { botao: "Ajuda", trecho: "Ajuda" },
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
  await checar("Meus estudos");

  await navSistema(page).getByRole("button", { name: "Simular rede", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Simular rede" })).toBeVisible();
  await checar("Simular rede");

  await irMeusEstudos(page);
  await irCotacoes(page);
  await checar("Cotações (entrada)");

  for (const aba of ABAS_COTACOES) {
    await navAbasCotacoes(page).getByRole("button", { name: aba.botao, exact: true }).click();
    await expect(page.locator("main").getByText(aba.trecho).first()).toBeVisible({ timeout: 10000 });
    await checar(`Cotações · ${aba.botao}`);
  }

  await irMeusEstudos(page);
  await page.getByRole("button", { name: "Continuar", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Base atual|Referência/i })).toBeVisible({ timeout: 10000 });
  await checar("Etapa 1");

  const etapas = page.locator("nav[aria-label='Etapas do estudo'] button");
  const n = await etapas.count();
  expect(n).toBeGreaterThanOrEqual(5);
  for (let i = 0; i < n; i += 1) {
    await etapas.nth(i).click();
    await page.waitForTimeout(250);
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
  const falhas = coletarFalhas(page);
  await interceptarApi(page);
  await interceptarRobo(page, CENARIOS_ROBO.antigo);
  await instalarSessaoDemo(page);
  await page.goto("/#/conexoes");
  await expect(page.getByRole("heading", { name: "Conexões" })).toBeVisible({ timeout: 15000 });
  await assertTelaViva(page, "hash conexoes");
  expect(falhas.excecoes, falhas.excecoes.join(" | ")).toEqual([]);
  expect(falhas.errosConsole, falhas.errosConsole.join(" | ")).toEqual([]);
});
