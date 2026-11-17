"""Bradesco sem navegador: pedido, assinaturas (processo e cálculo), leitura do cálculo, engrenagem e login."""
from __future__ import annotations

from decimal import Decimal

import pytest

import operadoras
from nucleo import configuracao as cfgrobo
from nucleo.estado import Estado
from nucleo.modelo import PlanoAlvo
from operadoras.bradesco import extracao as ex
from operadoras.bradesco.etapas import _opcao_acomodacao
from operadoras.bradesco.pedido import Processo
from operadoras.bradesco.planilha import ErroPedido

OP = operadoras.obter("bradesco")
CFG = OP.config({"geral": {"pasta_saida": "saida", "modo_visual": False, "janela_escondida": "headless",
                           "lentidao_ms": 0, "mapear": False, "pausa_entre_pedidos_s": 0},
                 "operadoras": {"bradesco": {}}})
VIDEO = {"cnpj": "11.222.333/0001-81", "vidas_0_18": 1, "vidas_34_38": 2, "idades_0_18": "0",
         "planos": "Nacional Plus 4x | Quarto; Nacional III"}

TEXTO_CALCULO = """Cálculo de Seguro SPG
Número do Processo\t15977143\tReembolso Específico (exceto Nacional Plus e Premium)
Perfil 1: Sócios
Plano Saúde\tNacional Plus\tCódigo do Plano: TPN4 COPART\tRegião: São Paulo Capital\tCoparticipação: 30%\tReembolso Completo
Faixa Etária\tSaúde(R$)\tSaúde Conjugado(R$)\tDental Conjugado(R$)\tQtd\tSaúde\tConjugado Saúde\tDental\tSaúde + Dental
Até 18 anos\tR$ 1.155,96\tR$ 1.155,96\tR$ 22,13\t1\tR$ 1.155,96\tR$ 1.155,96\tR$ 22,13\tR$ 1.178,09
19 a 23\tR$ 1.364,03\tR$ 1.364,03\tR$ 22,13\t0\tR$ 0,00\tR$ 0,00\tR$ 0,00\tR$ 0,00
34 a 38\tR$ 2.257,84\tR$ 2.257,84\tR$ 22,13\t2\tR$
4.515,68\tR$ 4.515,68\tR$ 44,26\tR$ 4.559,94
59 adiante\tR$ 6.935,24\tR$ 6.935,24\tR$ 22,13\t0\tR$ 0,00\tR$ 0,00\tR$ 0,00\tR$ 0,00
Total\t\t\t\t3\tR$ 5.671,64\tR$ 5.671,64\tR$ 66,39\tR$ 5.738,03
Totais Saúde
Total de Vidas\t3
Prêmio Saúde\tR$ 5.671,64
Taxa Kit Digital\tR$ 0,00
I.O.F. Saúde\tR$ 134,99
Total 1ª Parcela\tR$ 5.806,63
Demais Parcelas\tR$ 5.806,63
Totais Conjugado
Total de Vidas\t3
Prêmio Saúde\tR$ 5.671,64
Prêmio Dental\tR$ 66,39
Total Geral\tR$ 5.738,03
Total 1ª Parcela\tR$ 5.873,02
"""


def _pedido(**extra):
    return OP.montar_pedido({**VIDEO, **extra}, CFG, linha=2)


def test_pedido_do_video_com_os_padroes_da_newport():
    p = _pedido()
    assert (p.cnpj, p.total_vidas, p.idades) == ("11222333000181", 3, {"0 - 18": [0]})
    assert [x.rotulo() for x in p.planos] == ["Nacional Plus 4x | Quarto", "Nacional III | Quarto"]
    assert (p.coparticipacao, p.dental, p.adesao, p.cobertura) == ("com", "Sem plano dental", "Compulsória", "Top")
    assert (p.categoria, p.sucursal, p.codigo_corretor, p.ramo) == ("Sócios e Diretores", "978", "438451", "OUTROS")
    assert (p.angariacao, p.corretagem) == ("3 Primeiras Parcelas 100%", "2% vitalício a partir da 4ª parcela")
    assert not p.transferencia and not p.desconto_folha and p.desconto_comissao == ""
    assert OP.qtd_cotacoes(p) == 2 and OP.qtd_cotacoes(_pedido(coparticipacao="as_duas")) == 4


def test_pedido_sem_idade_nas_faixas_que_o_portal_pede_e_recusado():
    with pytest.raises(ErroPedido) as e:
        _pedido(idades_0_18="")
    assert "pede a idade de cada pessoa" in str(e.value)
    with pytest.raises(ErroPedido) as e:
        _pedido(vidas_59_mais=1, idades_59_mais="45")
    assert "fora da faixa 59+" in str(e.value)
    with pytest.raises(ErroPedido):
        _pedido(planos="Nacional Plus 4x | Apartamento")      # Bradesco: Quarto ou Enfermaria
    with pytest.raises(ErroPedido):
        _pedido(dental="Ouro")


def test_processo_e_calculo_tem_chaves_diferentes_e_estaveis(tmp_path):
    estado = Estado(tmp_path / "estado.json")
    com, sem = _pedido(coparticipacao="as_duas").na_versao("com"), _pedido(coparticipacao="as_duas").na_versao("sem")
    # As duas versões são o MESMO processo e cálculos diferentes.
    assert estado.chave(Processo(com), "Processo", "") == estado.chave(Processo(sem), "Processo", "")
    assert estado.chave(com, "Nacional Plus 4x", "Quarto") != estado.chave(sem, "Nacional Plus 4x", "Quarto")
    # A versão "com" de um pedido "Com e sem" é o mesmo cálculo de um pedido só "com".
    assert estado.chave(com, "Nacional Plus 4x", "Quarto") == estado.chave(_pedido(), "Nacional Plus 4x", "Quarto")
    # O dental muda o cálculo e (só na chave de registro, 10/11) o processo, exceto o "Padrão Doc 1" das chaves antigas;
    # as vidas mudam os dois.
    doc_white = _pedido(dental="Padrão Doc White")
    assert estado.chave(Processo(doc_white), "Processo", "") != estado.chave(Processo(_pedido()), "Processo", "")
    assert estado.chave(Processo(_pedido(dental="Padrão Doc 1")), "Processo", "") != estado.chave(
        Processo(_pedido(dental="Sem plano dental")), "Processo", "")
    assert estado.chave(doc_white, "Nacional III", "Quarto") != estado.chave(_pedido(), "Nacional III", "Quarto")
    outro = _pedido(vidas_34_38=3)
    assert estado.chave(Processo(outro), "Processo", "") != estado.chave(Processo(_pedido()), "Processo", "")
    # O id do pedido e a pasta não entram.
    assert estado.chave(_pedido(id="X"), "Nacional III", "Quarto") == estado.chave(_pedido(), "Nacional III", "Quarto")


def test_le_o_calculo_do_video_e_confere():
    assert ex.ler_numero_processo(TEXTO_CALCULO) == "15977143"
    assert ex.ler_numero_processo("Processo #15977143 Cotação com Reembolso Específico.") == "15977143"
    tabela, totais = ex.ler_tabela_calculo(TEXTO_CALCULO), ex.ler_totais(TEXTO_CALCULO)
    assert tabela["0 - 18"] == {"valor_vida": Decimal("1155.96"), "qtd": 1, "total": Decimal("1155.96")}
    assert tabela["34 - 38"]["qtd"] == 2 and tabela["59+"]["qtd"] == 0
    assert (totais["premio"], totais["iof"], totais["total1"], totais["vidas"]) == (
        Decimal("5671.64"), Decimal("134.99"), Decimal("5806.63"), 3)
    assert ex.ler_totais_conjugado(TEXTO_CALCULO) == {"dental": Decimal("66.39"), "total_geral": Decimal("5738.03"),
                                                      "total1": Decimal("5873.02")}
    assert ex.ler_perfil(TEXTO_CALCULO) == {"plano": "Nacional Plus", "codigo": "TPN4 COPART", "coparticipacao": "30%"}
    vidas = {"0 - 18": 1, "34 - 38": 2}
    assert ex.conferir_calculo(tabela, vidas, totais, Decimal("0.0238"), Decimal("0.05")) == []
    erros = ex.conferir_calculo(tabela, {"0 - 18": 1, "34 - 38": 3}, totais, Decimal("0.0238"), Decimal("0.05"))
    assert any("34 - 38" in e for e in erros)
    assert ex.iof(Decimal("2448.93"), Decimal("0.0238")) == Decimal("58.28")        # 2º cálculo do vídeo


def test_nome_do_plano_e_acomodacao_do_formulario_antigo():
    assert ex.reembolso_do_card("Benefícios Reembolso Completo (4x tabela) Programa Meu Doutor") == 4
    assert ex.nome_do_plano("Nacional Plus", 4) == "Nacional Plus 4x" and ex.nome_do_plano("Nacional III", 0) == "Nacional III"
    assert ex.separar_reembolso("Nacional Plus 4x") == ("Nacional Plus", 4)
    opcoes_plus = ["Múltiplo 4", "Múltiplo 6", "Múltiplo 8"]
    opcoes_n3 = ["Quarto Privativo", "Múltiplo 2", "Múltiplo 3"]
    assert _opcao_acomodacao(opcoes_plus, PlanoAlvo("Nacional Plus 4x", "Quarto")) == "Múltiplo 4"
    assert _opcao_acomodacao(opcoes_n3, PlanoAlvo("Nacional III", "Quarto")) == "Quarto Privativo"    # vídeo
    assert _opcao_acomodacao(opcoes_n3, PlanoAlvo("Nacional III 2x", "Quarto")) == "Múltiplo 2"
    assert _opcao_acomodacao(["Quarto Privativo", "Enfermaria"], PlanoAlvo("Nacional II", "Enfermaria")) == "Enfermaria"
    assert _opcao_acomodacao(opcoes_plus, PlanoAlvo("Nacional Plus 5x", "Quarto")) is None
    assert ex.copart_do_texto("30%") == "com" and ex.copart_do_texto("Sem coparticipação") == "sem"


def test_nome_do_pdf_como_o_da_sulamerica():
    from nucleo.saidas import nome_pdf_destino
    assert nome_pdf_destino(CFG, "1", "2", "Nacional Plus 4x") == "BRADESCO NACIONAL PLUS 4X.pdf"
    assert nome_pdf_destino(CFG, "1", "2", "Nacional Plus 4x", versao="SEM COPARTICIPACAO") == \
        "BRADESCO NACIONAL PLUS 4X SEM COPARTICIPACAO.pdf"


def test_engrenagem_declara_campos_validos_com_os_padroes_do_video():
    telas = OP.configuracao(CFG)
    assert [t["etapa"] for t in telas] == [e for e, _ in OP.etapas]
    for campo in cfgrobo.campos_por_chave(telas).values():
        valor = cfgrobo.para_tela(campo, cfgrobo.ler(CFG, campo["chave"]))
        cfgrobo.validar(campo, valor)                 # o padrão da Newport passa na validação da tela
    [credenciais] = [c for c in telas[0]["campos"] if c.get("tipo") == "credenciais"]
    assert [(c["chave"], c["rotulo"], c["tipo"]) for c in credenciais["campos"]] == [
        ("documento", "CPF/CNPJ", "cpf_cnpj"), ("cpf", "CPF de acesso", "cpf"), ("senha", "Senha", "senha"),
        ("intermediario_cpf", "CPF do intermediário", "cpf")]
    assert CFG["emissao_liberada"] is False and OP.marcada_na_nova_cotacao(CFG) is False
    assert [c["chave"] for c in OP.campos(CFG)] == ["coparticipacao", "dental", "adesao", "cobertura"]


def test_cofre_da_bradesco_e_separado_do_da_sulamerica():
    from nucleo.credenciais import Cofre, CofreMemoria
    from operadoras.bradesco.simulador.servidor import Simulador as SimB
    from operadoras.sulamerica.simulador.servidor import Simulador as SimS

    CofreMemoria.esvaziar()
    sul, bra = Cofre("sulamerica", memoria=True), Cofre("bradesco", memoria=True)
    assert (sul.servico, bra.servico) == ("NewportCotacoes/sulamerica", "NewportCotacoes/bradesco")
    sul.guardar(SimS.CPF, SimS.EMAIL, SimS.SENHA)
    bra.guardar(documento="11.444.777/0001-61", cpf="111.444.777-35", senha=SimB.SENHA,
                intermediario_cpf="529.982.247-25")
    assert bra.ler()["documento"] == SimB.DOCUMENTO and bra.ler()["intermediario_cpf"] == SimB.CPF_INTERMEDIARIO
    bra.apagar()
    assert sul.ler()["cpf"] == SimS.CPF and not bra.situacao()["guardadas"]
    CofreMemoria.esvaziar()


def test_le_os_valores_por_faixa_do_card_do_portal_real():
    """Portal real 07/11: FAIXA | Qtd | Tabela | Subtotal, um item por linha (Nacional Plus 4x, 3 vidas)."""
    texto = chr(10).join(['Valores por faixa etária', 'FAIXA', 'Qtd', 'Tabela', 'Subtotal', '0-18', '1', 'R$ 930,53', 'R$ 930,53']
                         + ['19-23', '0', 'R$ 1.098,03', '-', '34-38', '2', 'R$ 1.817,53', 'R$ 3.635,06', '59+', '0', 'R$ 5.582,77', '-'])
    valores = ex.ler_valores_card(texto)
    assert valores == {"0 - 18": Decimal("930.53"), "19 - 23": Decimal("1098.03"), "34 - 38": Decimal("1817.53"),
                       "59+": Decimal("5582.77")}
    assert valores["0 - 18"] + 2 * valores["34 - 38"] == Decimal("4565.59")       # o preço do card


def test_le_o_calculo_do_portal_real():
    """Portal real 07/11 (processo 16088364, Nacional III): tabela sem a coluna "Conjugado" e um quadro "Totais" só,
    com a 1ª parcela já com o dental (2.448,93 + 66,39 + 58,28 = 2.573,60)."""
    texto = chr(10).join(['Cálculo de Seguro SPG', 'Número do Processo\t16088364\tReembolso Específico (exceto Nacional Plus e Premium)', 'Perfil 1: Sócios', 'Plano Saúde\tNacional III\tCódigo do Plano: TN3P COPART\tRegião: São Paulo Capital\tCoparticipação: 30%\tReembolso Específico', 'Plano Dental\tPadrão DOC I', 'Valores Unitários', 'Faixa Etária\tSaúde(R$)\tDental(R$)\tQtd\tSaúde\tDental\tSaúde + Dental', 'Até 18 anos\tR$ 499,13\tR$ 22,13\t1\tR$ 499,13\tR$ 22,13\tR$ 521,26', '19 a 23\tR$ 588,97\tR$ 22,13\t0\tR$ 0,00\tR$ 0,00\tR$ 0,00', '34 a 38\tR$ 974,90\tR$ 22,13\t2\tR$ 1.949,80\tR$ 44,26\tR$ 1.994,06', '59 adiante\tR$ 2.994,54\tR$ 22,13\t0\tR$ 0,00\tR$ 0,00\tR$ 0,00', 'Total\t\t\t3\tR$ 2.448,93\tR$ 66,39\tR$ 2.515,32', 'Totais', 'Total de Vidas\t3', 'Prêmio Saúde\tR$ 2.448,93', 'Prêmio Dental\tR$ 66,39', 'Total Geral\tR$ 2.515,32', 'Taxa Kit Digital\tR$ 0,00', 'I.O.F. Saúde\tR$ 58,28', 'Total 1ª Parcela\tR$ 2.573,60', 'Demais Parcelas\tR$ 2.573,60', 'Alterar Cotação\tImprimir\tFinalizar Cálculo'])
    assert ex.ler_numero_processo(texto) == "16088364"
    tabela, totais = ex.ler_tabela_calculo(texto), ex.ler_totais(texto)
    assert tabela["0 - 18"] == {"valor_vida": Decimal("499.13"), "qtd": 1, "total": Decimal("499.13")}
    assert tabela["34 - 38"]["total"] == Decimal("1949.80") and tabela["59+"]["qtd"] == 0
    assert (totais["premio"], totais["dental"], totais["iof"], totais["total1"], totais["vidas"]) == (
        Decimal("2448.93"), Decimal("66.39"), Decimal("58.28"), Decimal("2573.60"), 3)
    assert ex.conferir_calculo(tabela, {"0 - 18": 1, "34 - 38": 2}, totais, Decimal("0.0238"), Decimal("0.05")) == []
    assert ex.ler_perfil(texto) == {"plano": "Nacional III", "codigo": "TN3P COPART", "coparticipacao": "30%"}


def test_le_o_numero_da_janela_processo_gerado():
    """Portal real 10/11: a janela do cotador mostra o número antes de a página do cálculo carregar."""
    texto = ("Processo 16097787 gerado! Tipo de reembolso: Específico Você será redirecionado para as próximas etapas "
             "do Emissão Expressa SPG.")
    assert ex.ler_processo_gerado(texto) == "16097787"
    assert ex.ler_processo_gerado("Processo #15977143 Cotação com Reembolso Específico.") is None
    assert ex.ler_processo_gerado("") is None


def test_layout_do_calculo_conjugado_ou_dental():
    assert ex.tem_totais_saude(TEXTO_CALCULO) and ex.layout_do_calculo(TEXTO_CALCULO) == "conjugado"
    real = "Cálculo de Seguro SPG\nPlano Dental Padrão DOC I\nTotais\nTotal de Vidas 3\nPrêmio Saúde R$ 2.448,93"
    assert not ex.tem_totais_saude(real) and ex.layout_do_calculo(real) == "dental"
    assert ex.layout_do_calculo("Cálculo de Seguro SPG") == "desconhecido"


def test_dental_e_identificador_padroes_da_engrenagem():
    padroes = CFG["padroes"]
    assert (padroes["dental"], padroes["identificador_com"], padroes["identificador_sem"]) == (
        "Sem plano dental", "COM COPAY", "SEM COPAY")
    chaves = [c.get("chave") for e in OP.configuracao(CFG) for c in e["campos"]]
    assert "padroes.identificador_com" in chaves and "padroes.identificador_sem" in chaves


def test_dental_entra_na_chave_do_processo_so_quando_nao_e_o_padrao_doc_1():
    """Só a chave de registro: o Padrão Doc 1 mantém a chave antiga (as já gravadas continuam valendo); outro dental
    (ex.: "Sem plano dental", o padrão do vídeo) é outro processo. A chave do cálculo não muda de formato."""
    antigo = _pedido(dental="Padrão Doc 1")
    sem = _pedido(dental="Sem plano dental")
    premium = _pedido(dental="Premium Top 1")
    assert "dentalproc" not in antigo.assinatura_processo()
    assert antigo.assinatura().endswith("|copart=com|dental=padrao doc 1")
    assert sem.assinatura_processo().endswith("|dentalproc=sem plano dental")
    assert len({antigo.assinatura_processo(), sem.assinatura_processo(), premium.assinatura_processo()}) == 3
    # a chave do cálculo não repete o dental da chave do processo
    assert "dentalproc" not in sem.assinatura() and sem.assinatura().endswith("|copart=com|dental=sem plano dental")
    # o mesmo pedido continua com a mesma chave (a proteção contra repetir não some)
    assert sem.assinatura_processo() == _pedido(dental="Sem plano dental").assinatura_processo()


def test_modo_de_testes_vem_desligado_e_esta_na_engrenagem():
    assert CFG.get("teste_repetir") is False
    chaves = [c.get("chave") for e in OP.configuracao(CFG) for c in e["campos"]]
    assert "teste_repetir" in chaves

