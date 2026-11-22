"""Porto sem navegador: pedido, chaves, conferência dos valores fictícios, engrenagem e emissão bloqueada."""
from __future__ import annotations

from decimal import Decimal

import pytest

import operadoras
from nucleo.estado import Estado
from nucleo.modelo import PlanoAlvo
from operadoras.porto import extracao as ex
from operadoras.porto.pedido import COMISSAO_K001
from operadoras.porto.planilha import ErroPedido
from operadoras.porto.simulador.servidor import calcular

OP = operadoras.obter("porto")
CFG = OP.config({"geral": {"pasta_saida": "saida", "modo_visual": False, "janela_escondida": "headless",
                           "lentidao_ms": 0, "mapear": False, "pausa_entre_pedidos_s": 0},
                 "operadoras": {"porto": {}}})
FICTICIO = {"cnpj": "11.222.333/0001-81", "vidas_0_18": 1, "vidas_34_38": 2, "vidas_59_mais": 1,
            "idades_0_18": "0", "congenere_atual": "NOTREDAME", "planos": "Ouro Mais I; P470",
            "apelido": "PADARIA"}
TOL = Decimal("0.05")


def _pedido(**extra):
    return OP.montar_pedido({**FICTICIO, **extra}, CFG, linha=2)


def test_pedido_ficticio_com_os_padroes():
    p = _pedido()
    assert (p.cnpj, p.total_vidas, p.congenere, p.comissao, p.coparticipacao) == (
        "11222333000181", 4, "NotreDame Intermédica", COMISSAO_K001, "com")
    assert [a.nome for a in p.planos] == ["Ouro Mais I", "P470"]
    assert p.idades["0 - 18"] == [0]
    assert OP.qtd_cotacoes(p) == 2
    assert CFG.get("emissao_liberada") is False


def test_emissao_liberada_nao_vem_ligada_no_padrao():
    assert Porto_padrao_false()


def Porto_padrao_false() -> bool:
    return OP.PADRAO_CONFIG["emissao_liberada"] is False and OP.marcada_na_nova_cotacao(CFG) is False


@pytest.mark.parametrize("campos, trecho", [
    ({"cnpj": "11.222.333/0001-82"}, "CNPJ"),
    ({"vidas_34_38": 0, "vidas_0_18": 1, "vidas_59_mais": 0}, "fora do intervalo 3 a 29"),
    ({"planos": ""}, "planos vazio"),
    ({"idades_0_18": ""}, "idades_0_18"),
    ({"congenere_atual": "", "seguro_novo": "nao"}, "operadora atual"),
])
def test_pedido_invalido_diz_o_problema(campos, trecho):
    with pytest.raises(ErroPedido) as e:
        _pedido(**campos)
    assert any(trecho in x for x in e.value.problemas)


def test_chave_anti_reemissao_nao_muda_com_id_nem_apelido(tmp_path):
    estado = Estado(tmp_path / "estado.json")
    p = _pedido()
    k = estado.chave(p, "Ouro Mais I", "Apartamento")
    assert k == estado.chave(_pedido(id="X", apelido="outro"), "Ouro Mais I", "Apartamento")
    assert k != estado.chave(_pedido(vidas_34_38=3, idades_0_18="0"), "Ouro Mais I", "Apartamento")
    assert k != estado.chave(p, "P470", "Apartamento")
    assert k != estado.chave(_pedido(coparticipacao="sem"), "Ouro Mais I", "Apartamento")


def test_conferencia_secao3_ouro_mais_i_4_vidas():
    calc = calcular("Ouro Mais I", {"0 - 18": 1, "34 - 38": 2, "59+": 1})
    assert (calc["subtotal"], calc["taxa"], calc["iof"], calc["total"]) == (
        Decimal("4591.96"), Decimal("20.00"), Decimal("109.76"), Decimal("4721.72"))
    assert ex.conferir_detalhes(4, calc["faixas"], {"0 - 18": 1, "34 - 38": 2, "59+": 1},
                                calc["subtotal"], calc["taxa"], calc["iof"], calc["total"],
                                Decimal("0.0238"), Decimal("5.00"), TOL) == []


def test_conferencia_secao3_ouro_max_e_p470_3_vidas():
    ouro = calcular("Ouro Max I", {"0 - 18": 1, "34 - 38": 2})
    p470 = calcular("P470", {"0 - 18": 1, "34 - 38": 2})
    assert p470["total"] == Decimal("2179.37")
    assert p470["taxa"] == Decimal("15.00")
    assert abs(ouro["total"] - Decimal("2918.21")) <= Decimal("0.05")
    assert ouro["iof"] == Decimal("67.84")


def test_ler_detalhes_do_texto():
    texto = """A cotação nº 9000001 foi calculada com sucesso.
Sub-total: R$ 4.591,96
Taxa de inscrição: R$ 20,00
IOF Saúde: R$ 109,76
Valor total mensal: R$ 4.721,72
"""
    d = ex.ler_detalhes(texto)
    assert d["numero"] == "9000001"
    assert d["total"] == Decimal("4721.72")


def test_engrenagem_declara_credenciais_cpf_senha_e_nao_emite():
    conf = {e["etapa"]: e for e in OP.configuracao(CFG)}
    login = conf["login"]["campos"][0]
    assert login["tipo"] == "credenciais"
    assert [c["chave"] for c in login["campos"]] == ["cpf", "senha"]
    assert "Gerar orçamento" in conf["orcamento"]["faz"]
    assert "Elaborar proposta" in conf["orcamento"]["faz"]


def test_seletores_nao_expoe_clique_de_proposta_ou_duplicar():
    import inspect
    from operadoras.porto import seletores as sel
    fonte = inspect.getsource(sel)
    for proibido in ("Elaborar proposta", "Adicionar à Proposta", "Duplicar orçamento", "Editar"):
        assert f"name={proibido!r}" not in fonte
        assert f'name="{proibido}"' not in fonte
    assert "botao_gerar_orcamento" in fonte
    assert "NUNCA" in sel.__doc__
