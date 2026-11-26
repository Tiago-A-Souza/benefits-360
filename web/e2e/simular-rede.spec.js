import { test, expect } from "@playwright/test";
import { coletarFalhas, interceptarApi, interceptarRobo, instalarSessaoDemo } from "./helpers.js";

async function abrirSimular(page) {
  const falhas = coletarFalhas(page);
  const consultas = [];
  page.on("request", (req) => {
    const u = req.url();
    if (u.includes("/api/simular-rede/por-")) consultas.push(u);
  });
  await interceptarApi(page);
  await interceptarRobo(page, { modo: "off" });
  await instalarSessaoDemo(page);
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/#/simular-rede");
  await expect(page.getByRole("heading", { name: "Simular rede" })).toBeVisible();
  return { falhas, consultas };
}

function cardFiltros(page) {
  return page.locator("section.simular-filtros");
}

async function geoDentroDoCard(page) {
  const card = cardFiltros(page);
  await expect(card).toBeVisible();
  for (const nome of ["Estado", "Município", "Zona"]) {
    const campo = page.getByLabel(nome, { exact: true });
    await expect(campo).toBeVisible();
    const boxCard = await card.boundingBox();
    const boxCampo = await campo.boundingBox();
    expect(boxCard && boxCampo).toBeTruthy();
    expect(boxCampo.y).toBeGreaterThanOrEqual(boxCard.y - 1);
    expect(boxCampo.y + boxCampo.height).toBeLessThanOrEqual(boxCard.y + boxCard.height + 2);
  }
}

test.describe("Simular rede — nunca consulta sozinha", () => {
  test.use({ viewport: { width: 1366, height: 768 } });

  test("abre vazia, filtros visíveis, sem chamada de consulta", async ({ page }) => {
    const { consultas } = await abrirSimular(page);
    await expect(page.getByText("Digite um ou mais hospitais")).toBeVisible();
    await expect(page.getByRole("button", { name: "Consultar" })).toBeDisabled();
    await geoDentroDoCard(page);
    expect(consultas).toEqual([]);
  });

  test("Einstein + Consultar não envia operadora/plano e não abre Alice", async ({ page }) => {
    const { consultas } = await abrirSimular(page);
    await page.getByLabel("Hospital").fill("Einstein");
    await expect(page.getByRole("button", { name: "Consultar" })).toBeEnabled();
    await page.getByRole("button", { name: "Consultar" }).click();
    await expect(page.getByText("HOSPITAL ALBERT EINSTEIN")).toBeVisible();
    await expect(page.getByText("MORUMBI")).toBeVisible();
    await expect(page.getByText("Alice Smart")).toHaveCount(0);
    expect(consultas.length).toBeGreaterThan(0);
    const ultima = consultas[consultas.length - 1];
    expect(ultima).toContain("/por-hospital");
    expect(ultima).toMatch(/q=Einstein/i);
    expect(ultima).not.toMatch(/operadoras=/i);
    expect(ultima).not.toMatch(/plano=/i);
  });

  test("Samaritano lista Barra e Botafogo; termo inexistente avisa vazio", async ({ page }) => {
    await abrirSimular(page);
    await page.getByLabel("Hospital").fill("Samaritano");
    await page.getByRole("button", { name: "Consultar" }).click();
    await expect(page.getByText("BARRA DA TIJUCA")).toBeVisible();
    await expect(page.getByText("BOTAFOGO")).toBeVisible();

    await page.getByLabel("Hospital").fill("HxYzNaoExiste");
    await page.getByRole("button", { name: "Consultar" }).click();
    await expect(page.getByText("Nenhum prestador da base corresponde à busca e aos filtros.")).toBeVisible();
  });

  test("Por plano não consulta até escolher os dois; abas não vazam estado", async ({ page }) => {
    const { consultas } = await abrirSimular(page);
    await page.getByRole("tab", { name: /Por plano/ }).click();
    await expect(page.getByText("Escolha operadora e plano")).toBeVisible();
    const nAposPlano = consultas.length;
    await page.getByLabel("Operadora").selectOption("Alice");
    expect(consultas.length).toBe(nAposPlano);
    await page.getByLabel("Plano").selectOption("1");
    await expect.poll(() => consultas.some((u) => u.includes("/por-plano"))).toBe(true);

    await page.getByRole("tab", { name: /Por hospital/ }).click();
    await expect(page.getByText("Digite um ou mais hospitais")).toBeVisible();
    await expect(page.getByLabel("Hospital")).toHaveValue("");

    await page.getByRole("tab", { name: "Laboratórios" }).click();
    await expect(page.getByText("Digite um ou mais laboratórios")).toBeVisible();
    await expect(page.getByText("Ver todos (+")).toHaveCount(0);
    await expect(page.getByText("Porto Seguro / Medservice")).toHaveCount(0);
    const labsAntes = consultas.filter((u) => u.includes("/laboratorios/por-laboratorio")).length;
    expect(labsAntes).toBe(0);

    await page.getByLabel("Marca ou prestador").fill("Delboni");
    await page.getByRole("button", { name: "Consultar" }).click();
    await expect(page.getByText("Delboni")).toBeVisible();
    await expect(page.getByText("Alice Smart")).toHaveCount(0);

    await page.getByRole("tab", { name: "Hospitais" }).click();
    await expect(page.getByText("Digite um ou mais hospitais")).toBeVisible();
    await expect(page.getByText("Delboni")).toHaveCount(0);
  });
});
