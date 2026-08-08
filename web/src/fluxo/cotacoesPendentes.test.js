import { describe, expect, it } from "vitest";
import {
  avisoAvancoCotacoesPendentes,
  documentosPendentesRevisao,
  proximaExtracaoPendente,
  resumoSelecaoDocumento,
  rotuloDocumentoExtracao,
} from "./cotacoesPendentes";

function ex({
  id,
  operadora,
  numero,
  total = 2,
  marcados = 0,
  descartada = false,
  motivo = null,
}) {
  return {
    id,
    descartada,
    motivo_descarte: motivo,
    numero_cotacao: numero ? { texto: numero } : null,
    documento: { operadora_detectada: operadora, nome_arquivo: `${numero || id}.pdf` },
    opcoes: Array.from({ length: total }, (_, i) => ({
      id: `${id}-op-${i}`,
      excluida: false,
      selecionada_para_comparativo: i < marcados,
    })),
  };
}

describe("cotacoesPendentes", () => {
  it("indica seleção por documento", () => {
    const porto = ex({ id: "p", operadora: "Porto Seguro", numero: "1", total: 36, marcados: 0 });
    const ops = [
      { extracao_id: "p" },
      { extracao_id: "p" },
    ];
    expect(resumoSelecaoDocumento(porto, ops)).toBe("2 de 36 selecionados");
    expect(
      resumoSelecaoDocumento(ex({ id: "s", operadora: "SulAmérica", numero: "7969363-1" }), [])
    ).toBe("nenhum plano selecionado");
  });

  it("aviso lista 2 pendentes quando só 1 tem plano", () => {
    const extracoes = [
      ex({ id: "porto", operadora: "Porto Seguro", numero: "P-1" }),
      ex({ id: "sa1", operadora: "SulAmérica", numero: "7969363-1" }),
      ex({ id: "sa2", operadora: "SulAmérica", numero: "7969408-1" }),
    ];
    const ops = [{ extracao_id: "porto" }, { extracao_id: "porto" }];
    const aviso = avisoAvancoCotacoesPendentes(extracoes, ops);
    expect(aviso).toContain("2 cotação(ões)");
    expect(aviso).toContain("SulAmérica (7969363-1)");
    expect(aviso).toContain("SulAmérica (7969408-1)");
    expect(aviso).not.toContain("Porto Seguro");
  });

  it("documento descartado com motivo não entra no aviso", () => {
    const extracoes = [
      ex({ id: "porto", operadora: "Porto Seguro", numero: "P-1" }),
      ex({
        id: "sa1",
        operadora: "SulAmérica",
        numero: "7969363-1",
        descartada: true,
        motivo: "fora do perfil",
      }),
    ];
    const ops = [{ extracao_id: "porto" }];
    expect(avisoAvancoCotacoesPendentes(extracoes, ops)).toBeNull();
    expect(resumoSelecaoDocumento(extracoes[1], ops)).toBe("Descartada — fora do perfil");
  });

  it("todos resolvidos → nenhum aviso", () => {
    const extracoes = [
      ex({ id: "porto", operadora: "Porto Seguro", numero: "P-1" }),
      ex({
        id: "sa1",
        operadora: "SulAmérica",
        numero: "7969363-1",
        descartada: true,
        motivo: "vencida",
      }),
    ];
    expect(avisoAvancoCotacoesPendentes(extracoes, [{ extracao_id: "porto" }])).toBeNull();
  });

  it("1 documento apenas → sem aviso se tem plano", () => {
    const extracoes = [ex({ id: "unico", operadora: "Porto Seguro", numero: "U-1" })];
    expect(avisoAvancoCotacoesPendentes(extracoes, [{ extracao_id: "unico" }])).toBeNull();
    expect(documentosPendentesRevisao(extracoes, [])).toHaveLength(1);
  });

  it("próximo documento pendente exclui o atual", () => {
    const extracoes = [
      ex({ id: "a", operadora: "Porto", numero: "1" }),
      ex({ id: "b", operadora: "SulAmérica", numero: "2" }),
      ex({ id: "c", operadora: "SulAmérica", numero: "3" }),
    ];
    const prox = proximaExtracaoPendente(extracoes, [{ extracao_id: "a" }], "a");
    expect(prox?.id).toBe("b");
    expect(rotuloDocumentoExtracao(prox)).toBe("SulAmérica (2)");
  });
});
