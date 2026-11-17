"""Amil sem navegador: pedido, chaves do registro, leitura e conferência dos valores do vídeo, engrenagem e nome do PDF."""
from __future__ import annotations

from decimal import Decimal

import pytest

import operadoras
from nucleo import configuracao as cfgrobo
from nucleo.estado import Estado
from nucleo.modelo import PlanoAlvo
from nucleo.saidas import nome_pdf_destino
from operadoras.amil import extracao as ex
from operadoras.amil.pedido import NOME_OPORTUNIDADE, Oportunidade
from operadoras.amil.planilha import ErroPedido
from operadoras.amil.simulador.servidor import PLANOS, calcular, reais

OP = operadoras.obter("amil")
CFG = OP.config({"geral": {"pasta_saida": "saida", "modo_visual": False, "janela_escondida": "headless",
                           "lentidao_ms": 0, "mapear": False, "pausa_entre_pedidos_s": 0},
                 "operadoras": {"amil": {}}})
VIDEO = {"cnpj": "11.222.333/0001-81", "vidas_0_18": 1, "vidas_34_38": 2, "vidas_59_mais": 1,
         "planos": "PLATINUM R1 COPART; AMIL BLACK I R1 COPART; AMIL S2500 R1 QP COPART", "apelido": "calandrini"}
TOL = Decimal("0.05")


def _pedido(**extra):
    return OP.montar_pedido({**VIDEO, **extra}, CFG, linha=2)


# ---- o pedido ----------------------------------------------------------------------------------------------------------

def test_pedido_do_video_com_os_padroes_da_newport():
    p = _pedido()
    assert (p.cnpj, p.total_vidas, p.coligacao, p.corretor, p.supervisor, p.dental) == (
        "11222333000181", 4, "Não", "EDLAINE ABREU SOARES", "", True)
    assert [a.nome for a in p.planos] == ["PLATINUM R1 COPART", "AMIL BLACK I R1 COPART", "AMIL S2500 R1 QP COPART"]
    assert p.vidas["0 - 18"] == 1 and p.vidas["34 - 38"] == 2 and p.vidas["59+"] == 1
    assert OP.qtd_cotacoes(p) == 3 and OP.versoes(p) == [(p, "")]


def test_planos_ignoram_a_familia_da_tela_e_repetidos():
    p = _pedido(planos="PLATINUM R1 COPART | Platinum; platinum r1 copart; AMIL BLACK I R1 COPART | Black")
    assert [a.nome for a in p.planos] == ["PLATINUM R1 COPART", "AMIL BLACK I R1 COPART"]
    assert all(a.acomodacao is None for a in p.planos)


@pytest.mark.parametrize("campos, trecho", [
    ({"cnpj": "11.222.333/0001-82"}, "CNPJ"),
    ({"vidas_34_38": 0, "vidas_0_18": 1, "vidas_59_mais": 0}, "fora do intervalo 2 a 29"),
    ({"vidas_34_38": 40}, "fora do intervalo 2 a 29"),
    ({"planos": ""}, "planos vazio"),
    ({"dental": "talvez"}, "dental"),
    ({"vidas_0_18": "x"}, "vidas_0_18"),
])
def test_pedido_invalido_diz_o_problema(campos, trecho):
    with pytest.raises(ErroPedido) as e:
        _pedido(**campos)
    assert any(trecho in x for x in e.value.problemas)


def test_dental_do_pedido_vale_sobre_o_padrao_da_engrenagem():
    assert _pedido(dental="nao").dental is False and _pedido(dental="sim").dental is True


# ---- chaves do registro ---------------------------------------------------------------------------------------------------

def test_chaves_da_oportunidade_e_da_cotacao_sao_estaveis(tmp_path):
    estado = Estado(tmp_path / "estado.json")
    p = _pedido()
    plat = PlanoAlvo("PLATINUM R1 COPART")
    # a oportunidade é a empresa: outras vidas, outro plano, outro dental NÃO mudam a chave
    k_opp = estado.chave(Oportunidade(p), NOME_OPORTUNIDADE, "")
    assert k_opp == estado.chave(Oportunidade(_pedido(vidas_34_38=3, dental="nao", planos="PRATA QC COPART")),
                                 NOME_OPORTUNIDADE, "")
    assert k_opp != estado.chave(Oportunidade(_pedido(cnpj="49.418.533/0001-87")), NOME_OPORTUNIDADE, "")
    # a cotação: a empresa + as vidas + o corretor + o dental (+ o plano)
    k_cot = estado.chave(p, plat.nome, "")
    assert k_cot == estado.chave(_pedido(id="X", apelido="outro", pasta_destino=None), plat.nome, "")   # id e apelido não entram
    assert k_cot != estado.chave(_pedido(vidas_34_38=3), plat.nome, "")
    assert k_cot != estado.chave(_pedido(dental="nao"), plat.nome, "")
    assert k_cot != estado.chave(p, "AMIL BLACK I R1 COPART", "")
    # o item da oportunidade e o da cotação são chaves diferentes
    assert k_opp != k_cot


# ---- valores do vídeo (Seção 3 do mapa) -----------------------------------------------------------------------------------

@pytest.mark.parametrize("plano, mensal, geral, apos12, selo", [
    ("PLATINUM R1 COPART", "4769.00", "2384.50", "4827.00", True),
    ("AMIL BLACK I R1 COPART", "8453.10", "4226.55", "8511.10", True),
    ("AMIL S2500 R1 QP COPART", "8847.02", "8847.02", "8905.02", False),
])
def test_simulador_e_conferencia_batem_com_os_valores_do_video(plano, mensal, geral, apos12, selo):
    c = calcular(plano, [1, 0, 0, 0, 2, 0, 0, 0, 0, 1], True)
    assert (str(c["mensal"]), str(c["total_geral"]), str(c["apos_12"]), c["selo"]) == (mensal, geral, apos12, selo)
    assert ex.conferir_grade({"0 - 18": 1, "34 - 38": 2, "59+": 1}, [1, 0, 0, 0, 2, 0, 0, 0, 0, 1], c["valores"],
                             c["subtotais"], 4, c["mensal"], TOL) == []


def _texto_revisao(plano="PLATINUM R1 COPART", mensal="4.769,00", geral="2.384,50", apos12="4.827,00", selo=True,
                   dental12="58,00", corretor="EDLAINE ABREU SOARES"):
    desconto = ("Desconto 50%\n1ª e 2ª parcela\t" if selo else "")
    linha = (f"{plano}\t4\tPlano elegível R$ {mensal} R$ {geral}\tR$ {mensal}" if selo else f"{plano}\t4\tR$ {mensal}")
    total = (f"Total\t4\tR$ {mensal} R$ {geral}\tR$ {mensal}" if selo else f"Total\t4\tR$ {mensal}")
    return f"""Cotação
Resumo Geral
COT-5185118
OPORTUNIDADE
OPP-5147302 - CALANDRINI HEALTHSPAN LTDA
DATA DE VALIDADE
17/10/2026, 13:30
DATA DE CRIAÇÃO
16/10/2026, 13:30
CORRETOR
{corretor}
TABELA
Compulsória
Nome do Plano Médico\tQuantidade de Vidas\t{desconto}Valor/mês
{linha}
{total}
Nome do Plano Dental\tQuantidade de Vidas\tValor
DENTAL BRONZE PJ PROMO\t4\tR$ 0,00
Total\t4\tR$ 0,00
Total Geral\tR$ {geral}
O desconto de 50% é aplicado somente nas 2 (duas) primeiras mensalidades.
Total Geral após 12 Meses
*Nesse valor não está calculado o reajuste
R$ {apos12}*
Nome do Plano Dental\tQuantidade de Vidas\tValor
DENTAL BRONZE PJ PROMO\t4\tR$ {dental12}
Total\t4\tR$ {dental12}
"""


def test_le_e_confere_a_revisao_do_video():
    rev = ex.ler_revisao(_texto_revisao())
    assert (rev["cot"], rev["opp"], rev["selo_50"], rev["vidas"]) == ("COT-5185118", "OPP-5147302", True, 4)
    assert (rev["mensal"], rev["total_geral"], rev["total_12_meses"], rev["dental_12_meses"]) == (
        Decimal("4769.00"), Decimal("2384.50"), Decimal("4827.00"), Decimal("58.00"))
    assert (rev["validade"], rev["tabela"], rev["corretor"]) == ("17/10/2026 13:30", "Compulsória", "EDLAINE ABREU SOARES")
    assert ex.conferir_revisao(rev, "PLATINUM R1 COPART", 4, "EDLAINE ABREU SOARES", Decimal("4769.00"), TOL, True) == []
    s2500 = ex.ler_revisao(_texto_revisao("AMIL S2500 R1 QP COPART", "8.847,02", "8.847,02", "8.905,02", selo=False))
    assert s2500["selo_50"] is False and s2500["mensal"] == Decimal("8847.02")
    assert ex.conferir_revisao(s2500, "AMIL S2500 R1 QP COPART", 4, "EDLAINE ABREU SOARES", Decimal("8847.02"), TOL, True) == []


@pytest.mark.parametrize("texto, trecho", [
    (_texto_revisao(geral="2.400,00"), "Total Geral é 2400.00"),                          # selo de 50% e não é a metade
    (_texto_revisao(selo=False, geral="2.384,50"), "sem desconto era esperado"),           # sem selo o Total Geral = mensal
    (_texto_revisao(apos12="4.800,00"), "após 12 Meses"),                                  # após 12 meses = total + dental
    (_texto_revisao(corretor="OUTRA PESSOA"), "corretor"),
    (_texto_revisao(plano="PRATA QC COPART"), "não aparece na revisão"),
])
def test_revisao_que_nao_confere_e_barrada(texto, trecho):
    problemas = ex.conferir_revisao(ex.ler_revisao(texto), "PLATINUM R1 COPART", 4, "EDLAINE ABREU SOARES",
                                    Decimal("4769.00"), TOL, True)
    assert any(trecho in x for x in problemas), problemas


def test_grade_que_nao_confere_e_barrada():
    c = calcular("PLATINUM R1 COPART", [1, 0, 0, 0, 2, 0, 0, 0, 0, 1], True)
    esperado = {"0 - 18": 1, "34 - 38": 2, "59+": 1}
    assert any("o portal está com 0" in x for x in ex.conferir_grade(
        esperado, [1, 0, 0, 0, 0, 0, 0, 0, 0, 1], c["valores"], c["subtotais"], 4, c["mensal"], TOL))
    assert any("não é o Valor Total" in x for x in ex.conferir_grade(
        esperado, [1, 0, 0, 0, 2, 0, 0, 0, 0, 1], c["valores"], c["subtotais"], 4, c["mensal"] + 1, TOL))
    assert any("não mostrou valor por vida" in x for x in ex.conferir_grade(
        esperado, [1, 0, 0, 0, 2, 0, 0, 0, 0, 1], [Decimal(0)] * 10, [Decimal(0)] * 10, 4, Decimal(0), TOL))


def test_totais_da_grade_e_lista_de_cotacoes_da_oportunidade():
    assert ex.ler_totais_da_grade("Total de Vidas: 4 · Valor Total: R$ 4.769,00") == (4, Decimal("4769.00"))
    # a caixa do aditivo (depois da grade) tem os próprios totais e não conta
    assert ex.ler_totais_da_grade("Valor Total: R$ 2.078,49 Total de Vidas: 3 Valor Total: R$ 2.078,49 "
                                  "Aditivos do Plano Total de Vidas: 3 Valor Total: R$ 0,00") == (3, Decimal("2078.49"))
    assert ex.ler_cotacoes_da_oportunidade("COT-5185118\tR$ 4.769,00\t4\tConcluída\nCOT-5185125\tR$ 0,00\t0\tEm Digitação") == [
        {"cot": "COT-5185118", "valor": Decimal("4769.00"), "vidas": 4, "status": "Concluída"},
        {"cot": "COT-5185125", "valor": Decimal("0.00"), "vidas": 0, "status": "Em Digitação"}]
    assert ex.ler_numero_do_painel("Número da Oportunidade: OPP-5147302", "OPP") == "OPP-5147302"
    assert ex.ler_numero_do_painel("Número da Cotação:\nCOT-5185118", "COT") == "COT-5185118"
    assert reais(Decimal("4769")) == "R$ 4.769,00"


# ---- nome do PDF e engrenagem -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("plano, empresa, esperado", [
    ("PLATINUM R1 COPART", "CALANDRINI", "AMIL PLATINUM CALANDRINI.pdf"),
    ("AMIL BLACK I R1 COPART", "CALANDRINI", "AMIL BLACK CALANDRINI.pdf"),
    ("AMIL S2500 R1 QP COPART", "CALANDRINI", "AMIL S2500 CALANDRINI.pdf"),
    ("PLATINUM R1 COPART", "", "AMIL PLATINUM.pdf"),                         # sem nome curto: sem nome
    ("PRATA QC COPART", "ACME", "AMIL PRATA QC COPART ACME.pdf"),             # plano sem apelido: o nome inteiro
])
def test_nome_do_pdf_na_pasta_do_cliente(plano, empresa, esperado):
    assert nome_pdf_destino(CFG, "11222333000181", "COT-5185118", plano, "", versao=empresa.upper()) == esperado


def test_engrenagem_da_amil():
    telas = OP.configuracao(CFG)
    assert [t["etapa"] for t in telas] == [e[0] for e in OP.etapas]
    campos = cfgrobo.campos_por_chave(telas)
    for chave in ("padroes.coligacao", "padroes.corretor", "padroes.supervisor", "padroes.dental_aderir",
                  "arquivos.nome_pdf_destino", "arquivos.nomes_arquivo", "tempos.sair_do_portal_min"):
        assert chave in campos, chave
    assert CFG["padroes"]["corretor"] == "EDLAINE ABREU SOARES" and CFG["emissao_liberada"] is False
    assert cfgrobo.validar(campos["arquivos.nome_pdf_destino"], "AMIL {plano_arquivo} {versao}.pdf")
    with pytest.raises(ValueError):
        cfgrobo.validar(campos["arquivos.nome_pdf_destino"], "AMIL {empresa}.pdf")
    assert [c["chave"] for c in OP.campos_login()] == ["usuario", "senha"]
    assert OP.marcada_na_nova_cotacao(CFG) is False
    assert OP.campos_so_configuracao == ()
    assert [p["nome"] for p in OP.planos_conhecidos()][:2] == ["BRONZE SP COPART", "BRONZE SP MAIS QC COPART"]
    assert {"PLATINUM R1 COPART", "AMIL BLACK I R1 COPART", "AMIL S2500 R1 QP COPART"} <= set(PLANOS)


def test_textos_da_tela_avisam_que_o_ensaio_cria_a_oportunidade():
    textos = OP.textos_tela()
    assert "o ensaio da Amil já cria a oportunidade" in textos["passo_nova"]
    assert "código" in textos["passo_login"] and textos["nome_pdf"] == "AMIL <PLANO> <EMPRESA>.pdf"


def test_planilha_modelo_e_leitura(tmp_path):
    from openpyxl import load_workbook
    caminho = tmp_path / "modelo.xlsx"
    OP.criar_modelo(caminho)
    assert [c.value for c in load_workbook(caminho)["cotacoes"][1]][:4] == ["id", "cnpj", "apelido", "dental"]
    pedidos, erros = OP.ler_planilha(caminho, CFG)
    assert erros == [] and [p.id for p in pedidos] == ["EX-001"] and len(pedidos[0].planos) == 3
