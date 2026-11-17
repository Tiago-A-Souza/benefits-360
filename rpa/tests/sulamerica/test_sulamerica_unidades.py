"""SulAmérica: as partes que não dependem do navegador (planilha, extração, pedido, registro...)."""
import re
from decimal import Decimal

import pytest
from openpyxl import Workbook

from operadoras.sulamerica import extracao as ex
from nucleo.estado import Estado
from nucleo.modelo import ROTULOS, PlanoAlvo
from operadoras.sulamerica.planilha import criar_modelo, ler_planilha
from nucleo.saidas import nome_pdf_destino, nome_plano_arquivo
from nucleo.texto import cnpj_valido, dinheiro, norm, rx

CFG = {
    "padroes": {"cuidado_360": "sim", "tipo_contratacao": "compulsoria"},
    "criterio_plano": {"tipo": "menor_preco", "quantidade": 1},
    "congeneres_de_para": {"NotreDame Intermédica": "NOTREDAME"},
    "saida": {"nomes_arquivo": {"Executivo R1": "EXECUTIVO"},
              "nome_pdf_destino": "SULAMERICA {plano_arquivo}.pdf"},
}


# ---------- texto ----------

def test_rx_ignora_acento_e_caixa():
    assert rx("Cotação enviada com sucesso").search("Cotacao enviada com sucesso!")
    assert rx("Cotação emitida com sucesso").search("COTAÇÃO EMITIDA COM SUCESSO!")
    assert rx("Continuar", exato=True).search("  Continuar ")
    assert not rx("Continuar", exato=True).search("Continuar agora")
    assert rx("Login Cotador SulAmerica").search("login   cotador sulamérica")


# ---------- extração (valores reais do vídeo) ----------

CARD = """Especial Mais
Apartamento
557 - AHO - Compulsória - 24 meses
Com coparticipação
R$ 2.443,46 / mês
Selecionar plano"""

COMPARACAO = """Especial Mais
Apartamento
557 - AHO - Compulsória - 24 meses
Com coparticipação
R$ 2.443,46 / mês
Faixas\tQtd\tValores
0 - 18
1
R$ 521,90
R$ 521,90 / vida
19 - 23
0
R$ 652,37 / vida
24 - 28
0
R$ 808,94 / vida
29 - 33
0
R$ 897,92 / vida
34 - 38
2
R$ 1.921,56
R$ 960,78 / vida
39 - 43
0
R$ 1.114,50 / vida
44 - 48
0
R$ 1.332,27 / vida
49 - 53
0
R$ 1.561,42 / vida
54 - 58
0
R$ 1.858,87 / vida
59+
0
R$ 3.120,00 / vida
Adicionar mais planos
Voltar para seleção"""

RESUMO = """Resumo da Simulação
Confirme as informações antes de prosseguir
Saúde + Vida
Total sem IOF:
R$ 2.443,46
Vida:
R$ 0
IOF:
R$ 58,16
Total:
R$ 2.501,62
Odonto
Total sem IOF:
R$ 0
IOF:
R$ 0
Total:
R$ 0"""


def test_card_plano():
    p = ex.ler_card_plano(CARD)
    assert (p.nome, p.acomodacao, p.preco) == ("Especial Mais", "Apartamento", Decimal("2443.46"))
    assert "24 meses" in p.descricao and p.coparticipacao == "Com coparticipação"


def test_tabela_comparacao_confere_com_o_card():
    t = ex.ler_tabela_comparacao(COMPARACAO)
    assert list(t) == ROTULOS
    assert t["0 - 18"] == {"qtd": 1, "valor_vida": Decimal("521.90"), "subtotal": Decimal("521.90")}
    assert t["34 - 38"]["subtotal"] == Decimal("1921.56")
    vidas = {r: 0 for r in ROTULOS} | {"0 - 18": 1, "34 - 38": 2}
    assert ex.conferir_tabela(t, vidas, Decimal("2443.46"), Decimal("0.05")) == []
    erradas = vidas | {"34 - 38": 3}
    assert ex.conferir_tabela(t, erradas, Decimal("2443.46"), Decimal("0.05"))


def test_tabela_comparacao_numa_linha_so():
    # Mesmo conteúdo, com a tabela "achatada" numa linha (outro layout de HTML).
    achatada = " ".join(COMPARACAO.split())
    t = ex.ler_tabela_comparacao(achatada)
    assert t == ex.ler_tabela_comparacao(COMPARACAO)
    assert ex.ler_faixas_idades("0 - 18 0/1 59+ 2/2 Completo\nIdade\n0 - 18 1/1") == {
        "0 - 18": (0, 1), "59+": (2, 2)}


def test_resumo_e_iof():
    r = ex.ler_resumo(RESUMO)
    assert r == {"total_sem_iof": Decimal("2443.46"), "vida": Decimal("0.00"),
                 "iof": Decimal("58.16"), "total": Decimal("2501.62")}
    assert ex.conferir_resumo(r, Decimal("2443.46"), Decimal("0.0238"), Decimal("0.05")) == []
    # O portal arredonda o IOF por vida: 12,42 + 2 x 22,87 = 58,16 (2,38% do total daria 58,15)
    tabela = ex.ler_tabela_comparacao(COMPARACAO)
    assert ex.iof_por_vida(tabela, Decimal("0.0238")) == Decimal("58.16")
    assert ex.conferir_resumo(r, Decimal("2443.46"), Decimal("0.0238"), Decimal("0"),
                              ex.iof_por_vida(tabela, Decimal("0.0238"))) == []
    # Executivo R1 do vídeo: 4.592,88 -> IOF 109,31 -> 4.702,19
    r2 = {"total_sem_iof": Decimal("4592.88"), "vida": Decimal("0"), "iof": Decimal("109.31"),
          "total": Decimal("4702.19")}
    assert ex.conferir_resumo(r2, Decimal("4592.88"), Decimal("0.0238"), Decimal("0.05")) == []


def test_protocolo_status_razao_idades():
    assert ex.ler_protocolo("COTAÇÃO EMITIDA COM SUCESSO!\nProtocolo Saúde: nº 8601234") == "8601234"
    assert ex.ler_status_vidas("1/3 vidas (faltam 2)") == 1
    assert ex.ler_status_vidas("3 vidas distribuídas") == 3
    assert ex.ler_razao_social("Dados da Empresa:\nCNPJ\n49...\nRazão Social\nEMPRESA EXEMPLO LTDA") == \
        "EMPRESA EXEMPLO LTDA"
    texto_idades = ("Especifique as idades para Saúde\nAdicione a idade...\n0 - 18\n1/1\n✓ Completo\n"
                    "Idade\n0\nQuantidade\n1\nIdades adicionadas\n0 - 18\n1/1\nIdade\nQtd.\n0\n1")
    assert ex.ler_faixas_idades(texto_idades) == {"0 - 18": (1, 1)}


# ---------- planilha ----------

def _planilha(tmp_path, linhas):
    wb = Workbook()
    ws = wb.active
    cab = list(dict.fromkeys(k for l in linhas for k in l))   # união das colunas de todas as linhas
    ws.append(cab)
    for l in linhas:
        ws.append([l.get(c) for c in cab])
    caminho = tmp_path / "p.xlsx"
    wb.save(caminho)
    return caminho


def _linha(**extra):
    base = {"id": "A1", "cnpj": "11.222.333/0001-81", "seguro_novo": "nao", "congenere_atual": "NotreDame Intermédica",
            "vigencia_meses": 24, "coparticipacao": "com", "idades_0_18": "0",
            "planos": "Especial Mais | Apartamento; Executivo R1 (apartamento)"}
    for chave in ["0_18", "19_23", "24_28", "29_33", "34_38", "39_43", "44_48", "49_53", "54_58", "59_mais"]:
        base[f"vidas_{chave}"] = 0
    base["vidas_0_18"], base["vidas_34_38"] = 1, 2
    base.update(extra)
    return base


def test_planilha_valida(tmp_path):
    pedidos, erros = ler_planilha(_planilha(tmp_path, [_linha()]), CFG)
    assert erros == []
    p = pedidos[0]
    assert p.cnpj == "11222333000181" and p.total_vidas == 3 and p.congenere == "NOTREDAME"
    assert p.tipo_contratacao == "Compulsória" and p.cuidado_360 is True
    assert [x.rotulo() for x in p.planos] == ["Especial Mais | Apartamento", "Executivo R1 | Apartamento"]
    assert p.idades == {"0 - 18": [0]}


def test_planilha_erros(tmp_path):
    destino = tmp_path / "COTACOES"
    destino.mkdir()
    linhas = [
        _linha(id="B1", vidas_34_38=0),                       # 1 vida só
        _linha(id="B2", cnpj="11.222.333/0001-82"),           # dígito errado
        _linha(id="B3", seguro_novo="nao", congenere_atual=""),
        _linha(id="B4", idades_0_18="25"),                    # idade fora da faixa
        _linha(id="B5", coparticipacao="parcial"),
        _linha(id="B6", cnpj=11222333000181),                 # número do Excel: aceito
        _linha(id="B7", planos=""),                           # planos vazio não vira "menor preço" sozinho
        _linha(id="B8", planos="menor_preco:2", pasta_destino=str(destino)),
        _linha(id="B9", pasta_destino=str(tmp_path / "NAO_EXISTE")),
    ]
    pedidos, erros = ler_planilha(_planilha(tmp_path, linhas), CFG)
    por_id = {e.id: e.mensagem for e in erros}
    assert "fora do intervalo 3 a 29" in por_id["B1"]
    assert "inválido" in por_id["B2"]
    assert "congenere_atual é obrigatória" in por_id["B3"]
    assert "fora da faixa" in por_id["B4"]
    assert "use com, sem ou as_duas" in por_id["B5"]
    assert "planos vazio" in por_id["B7"]
    assert "pasta_destino não existe" in por_id["B9"]
    assert [p.id for p in pedidos] == ["B6", "B8"]
    assert pedidos[1].criterio_quantidade == 2 and pedidos[1].planos == []


def test_planilha_recusa_coluna_desconhecida(tmp_path):
    linha = _linha()
    linha["Tipo de contratação"] = linha.pop("id")            # nome errado: seria ignorado em silêncio
    with pytest.raises(ValueError, match="colunas não reconhecidas"):
        ler_planilha(_planilha(tmp_path, [linha]), CFG)


def test_modelo_gerado_e_valido(tmp_path):
    caminho = tmp_path / "modelo.xlsx"
    criar_modelo(caminho)
    pedidos, erros = ler_planilha(caminho, CFG)
    assert erros == [] and len(pedidos) == 1


# ---------- estado (nunca reemitir) ----------

def test_estado_bloqueia_reemissao(tmp_path):
    pedidos, _ = ler_planilha(_planilha(tmp_path, [_linha()]), CFG)
    p = pedidos[0]
    est = Estado(tmp_path / "estado.json")
    k = est.chave(p, "Especial Mais", "Apartamento")
    assert est.pode_emitir(k)
    est.registrar(k, p, "Especial Mais", "Apartamento", "emitindo")
    assert not Estado(tmp_path / "estado.json").pode_emitir(k)     # persiste em disco
    est.registrar(k, p, "Especial Mais", "Apartamento", "emitida", protocolo="8601234")
    est.registrar(k, p, "Especial Mais", "Apartamento", "pdf_ok", pdf="x.pdf")
    with pytest.raises(RuntimeError):
        est.registrar(k, p, "Especial Mais", "Apartamento", "emitindo")
    assert est.liberar(k) and est.pode_emitir(k)


def test_com_e_sem_coparticipacao_vira_duas_cotacoes_por_plano(tmp_path):
    """"as_duas" (planilha, tela ou configuração): 2 cotações por plano, na ordem com, sem. Cada versão é a
    cotação real de uma coparticipação: a versão "com" tem a mesma chave de um pedido "com"."""
    from operadoras.sulamerica import SulAmerica
    from operadoras.sulamerica.etapas import com_versoes

    linhas = [_linha(id="C1", coparticipacao="as_duas"), _linha(id="C2", coparticipacao="Com e sem"),
              _linha(id="C3", coparticipacao="AMBAS"), _linha(id="C4", coparticipacao="com")]
    pedidos, erros = ler_planilha(_planilha(tmp_path, linhas), CFG)
    assert erros == [] and [p.coparticipacao for p in pedidos] == ["as_duas", "as_duas", "as_duas", "com"]
    duas, so_com = pedidos[0], pedidos[3]
    op = SulAmerica()
    assert op.qtd_cotacoes(duas) == 4 and op.qtd_cotacoes(so_com) == 2          # 2 planos
    assert [x.rotulo_completo() for x in com_versoes(duas, duas.planos)] == [
        "Especial Mais | Apartamento | com coparticipação", "Especial Mais | Apartamento | sem coparticipação",
        "Executivo R1 | Apartamento | com coparticipação", "Executivo R1 | Apartamento | sem coparticipação"]
    assert com_versoes(so_com, so_com.planos) == so_com.planos
    assert duas.na_versao("com").assinatura() == so_com.assinatura()
    assert duas.na_versao("sem").assinatura() != so_com.assinatura()
    est = Estado(tmp_path / "estado.json")
    assert est.chave(duas.na_versao("com"), "Especial Mais", "Apartamento") == est.chave(so_com, "Especial Mais", "Apartamento")
    assert [t for _, t in op.versoes(duas)] == ["com coparticipação", "sem coparticipação"]
    # padrão da Newport: com e sem
    assert SulAmerica.PADRAO_CONFIG["padroes"]["coparticipacao"] == "as_duas"
    import yaml
    from pathlib import Path as _P
    cfg = yaml.safe_load((_P(__file__).resolve().parents[2] / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["operadoras"]["sulamerica"]["padroes"]["coparticipacao"] == "as_duas"
    campo = next(c for c in op.campos(SulAmerica.PADRAO_CONFIG) if c["chave"] == "coparticipacao")
    assert [o[0] for o in campo["opcoes"]] == ["sem", "com", "as_duas"] and campo["padrao"] == "as_duas"
    assert campo["opcoes"][2][1] == "Com e sem" and campo["multiplica"] == {"as_duas": 2}


def test_o_que_o_robo_aprende_do_portal(tmp_path):
    """O maxlength real do campo de senha, lido a cada login, vira o limite do Guardar na engrenagem."""
    from nucleo.configuracao import aprendido, aprender
    from operadoras.sulamerica import SulAmerica

    pasta = tmp_path / "saida" / "sulamerica"
    assert aprendido(pasta) == {}
    cfg = dict(SulAmerica.PADRAO_CONFIG, saida={"pasta": str(pasta)})
    senha_max = lambda: SulAmerica().configuracao(cfg)[0]["campos"][0]["senha_max"]   # noqa: E731
    assert senha_max() == 16                                   # até o portal dizer outro
    aprender(pasta, "senha_max", 20)
    assert aprendido(pasta) == {"senha_max": 20} and senha_max() == 20
    assert not list(pasta.glob("*.tmp"))


def test_nome_do_pdf_com_a_versao_da_coparticipacao():
    from nucleo.configuracao import problema_no_nome_pdf
    from nucleo.saidas import nome_pdf_destino

    assert nome_pdf_destino(CFG, "1", "2", "Especial Mais") == "SULAMERICA ESPECIAL MAIS.pdf"
    assert nome_pdf_destino(CFG, "1", "2", "Especial Mais", versao="COM COPARTICIPACAO") == \
        "SULAMERICA ESPECIAL MAIS COM COPARTICIPACAO.pdf"
    assert nome_pdf_destino(CFG, "1", "2", "Direto Nacional", "Apartamento", versao="SEM COPARTICIPACAO") == \
        "SULAMERICA DIRETO NACIONAL APARTAMENTO SEM COPARTICIPACAO.pdf"
    outro = dict(CFG, saida=dict(CFG["saida"], nome_pdf_destino="{versao} - SULAMERICA {plano_arquivo}.pdf"))
    assert nome_pdf_destino(outro, "1", "2", "Executivo R1", versao="SEM COPARTICIPACAO") == \
        "SEM COPARTICIPACAO - SULAMERICA EXECUTIVO.pdf"
    so_plano = dict(CFG, saida=dict(CFG["saida"], nome_pdf_destino="{plano}.pdf"))
    assert nome_pdf_destino(so_plano, "1", "2", "Especial Mais", versao="COM COPARTICIPACAO") == \
        "Especial Mais COM COPARTICIPACAO.pdf"
    assert problema_no_nome_pdf("SULAMERICA {plano_arquivo} {versao}.pdf") == ""


def test_emitir_de_novo_so_com_o_protocolo_concluido(tmp_path):
    """"Emitir de novo mesmo assim": o item antigo vai para "reemitidos" na mesma gravação do "emitindo";
    com outro protocolo (ou item que não está concluído) nada é gravado e o robô não clica em emitir."""
    pedidos, _ = ler_planilha(_planilha(tmp_path, [_linha()]), CFG)
    p = pedidos[0]
    est = Estado(tmp_path / "estado.json")
    k = est.chave(p, "Especial Mais", "Apartamento")
    est.registrar(k, p, "Especial Mais", "Apartamento", "emitindo")
    with pytest.raises(RuntimeError):     # emissão incerta: nunca reemite
        est.registrar(k, p, "Especial Mais", "Apartamento", "emitindo", substituir_protocolo="8601234")
    est.registrar(k, p, "Especial Mais", "Apartamento", "emitida", protocolo="8601234")
    est.registrar(k, p, "Especial Mais", "Apartamento", "pdf_ok", pdf="x.pdf")
    with pytest.raises(RuntimeError):     # protocolo que o corretor não viu
        est.registrar(k, p, "Especial Mais", "Apartamento", "emitindo", substituir_protocolo="1111111")
    assert est.item(k)["status"] == "pdf_ok" and "reemitidos" not in est.dados
    est.registrar(k, p, "Especial Mais", "Apartamento", "emitindo", substituir_protocolo="8601234")
    novo = Estado(tmp_path / "estado.json")
    assert novo.item(k)["status"] == "emitindo" and novo.item(k)["reemissao_de"] == "8601234"
    assert "protocolo" not in novo.item(k) and not novo.pode_emitir(k)   # o novo volta a bloquear
    [antigo] = novo.dados["reemitidos"]
    assert antigo["chave"] == k and antigo["item"]["protocolo"] == "8601234"


def test_estado_chave_e_a_cotacao_real(tmp_path):
    pedidos, _ = ler_planilha(_planilha(tmp_path, [_linha()]), CFG)
    p = pedidos[0]
    est = Estado(tmp_path / "estado.json")
    k = est.chave(p, "Especial Mais", "Apartamento")
    est.registrar(k, p, "Especial Mais", "Apartamento", "pdf_ok")
    # Grafia sem acomodação ou outro id de linha: é a mesma cotação.
    assert est.procurar(p, PlanoAlvo("Especial Mais"))[0] == k
    p.id = "L9"
    assert est.chave(p, "especial  mais", "APARTAMENTO") == k
    # "Especial Mais Vital" é outro plano.
    assert est.procurar(p, PlanoAlvo("Especial Mais Vital")) is None
    # Parâmetros diferentes (12 meses, outras idades): outra cotação, liberada.
    p.vigencia_meses = 12
    assert est.procurar(p, PlanoAlvo("Especial Mais")) is None and est.pode_emitir(est.chave(p, "Especial Mais", "Apartamento"))
    p.vigencia_meses, p.idades = 24, {"0 - 18": [5]}
    assert est.procurar(p, PlanoAlvo("Especial Mais")) is None


def test_estado_criterio_por_parametros(tmp_path):
    pedidos, _ = ler_planilha(_planilha(tmp_path, [_linha(planos="menor_preco")]), CFG)
    p = pedidos[0]
    est = Estado(tmp_path / "estado.json")
    est.salvar_planos_resolvidos(p, ["Direto Nacional | Enfermaria"])
    assert est.planos_resolvidos(p) == ["Direto Nacional | Enfermaria"]
    p.vidas["19 - 23"] = 1                                     # mudou a distribuição: resolve de novo
    assert est.planos_resolvidos(p) is None


def test_nomes_de_arquivo():
    assert nome_plano_arquivo("Executivo R1", CFG) == "EXECUTIVO"
    assert nome_plano_arquivo("Especial Mais", CFG) == "ESPECIAL MAIS"
    assert nome_pdf_destino(CFG, "1", "2", "Especial Mais") == "SULAMERICA ESPECIAL MAIS.pdf"
    assert norm("  Clássico  100 ") == "classico 100"


RESUMO_COMPLETO = RESUMO + """
Informações da Empresa
CNPJ: 11.222.333/0001-81
Características da Cotação
Saúde
Vidas: 3
Produto: 557 - AHO
Tipo de contratação: Compulsória
Vigência contratual:
24 meses
Operadora de origem / anterior: NOTREDAME
Coparticipação: Com coparticipação"""


def test_caracteristicas_do_resumo(tmp_path):
    c = ex.ler_caracteristicas(RESUMO_COMPLETO)
    assert c["vidas"] == "3" and c["vigencia"] == "24 meses" and c["operadora"] == "NOTREDAME"
    pedidos, _ = ler_planilha(_planilha(tmp_path, [_linha()]), CFG)
    p = pedidos[0]
    assert ex.conferir_caracteristicas(c, p) == []
    p.coparticipacao, p.vigencia_meses = "sem", 12
    assert len(ex.conferir_caracteristicas(c, p)) == 2
    assert ex.conferir_caracteristicas({}, p)              # sem o bloco: falha fechada
    assert ex.ler_plano_resumo("Planos Saúde\nEspecial Mais\n557 - AHO") == "Especial Mais"
    # descrição com travessão também é lida
    card = ex.ler_card_plano("Especial Vital\nApartamento\n557 – AHO – CBO – 12 meses\nSem coparticipação\nR$ 1,00")
    assert card.descricao.startswith("557")


# ---------- configuração com várias operadoras e trava ----------

def test_config_multi_operadora(tmp_path):
    import operadoras
    from nucleo.registro import carregar_config
    (tmp_path / "c.yaml").write_text(
        "geral:\n  pasta_saida: dados\n  modo_visual: false\n"
        "operadoras:\n  sulamerica:\n    tempos:\n      timeout_tela_ms: 1234\n"
        "    arquivos:\n      nomes_arquivo:\n        Executivo R1: EXECUTIVO\n", encoding="utf-8")
    total = carregar_config(tmp_path / "c.yaml", {"operadoras": {"sulamerica": {"padroes": {"cuidado_360": "nao"}}}})
    cfg = operadoras.obter("sulamerica").config(total)
    assert cfg["saida"]["pasta"] == str(tmp_path / "dados" / "sulamerica")      # uma pasta por operadora
    assert cfg["execucao"]["timeout_tela_ms"] == 1234 and cfg["execucao"]["modo_visual"] is False
    assert cfg["execucao"]["timeout_emissao_ms"] == 180000                      # padrão da operadora
    assert cfg["padroes"]["cuidado_360"] == "nao"                               # ajuste vindo da tela
    assert cfg["saida"]["nomes_arquivo"] == {"Executivo R1": "EXECUTIVO"}
    assert [o.id for o in operadoras.ativas(total)] == ["sulamerica"]


def test_retencao_apaga_so_arquivos_vencidos_do_robo(tmp_path):
    import os
    import time

    from nucleo.retencao import limpar
    velho = time.time() - 100 * 86400
    arquivos = {
        "sulamerica/pdfs/SULAMERICA_1_2.pdf": True,     # vence
        "sulamerica/logs/execucao_1.log": True,         # vence
        "sulamerica/mapa/exec1/01_login.png": True,     # vence
        "sulamerica/estado.json": False,                # nunca: impede reemissão
        "sulamerica/resultados.xlsx": False,
        "sulamerica/perfil_navegador/logs/x.log": False,  # sessão do navegador
    }
    for rel in arquivos:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
        os.utime(p, (velho, velho))
    novo = tmp_path / "sulamerica/pdfs/SULAMERICA_1_3.pdf"
    novo.write_text("x")
    assert limpar(tmp_path, 90) == 3
    for rel, some in arquivos.items():
        assert (tmp_path / rel).exists() is not some, rel
    assert novo.exists()
    assert not (tmp_path / "sulamerica/mapa/exec1").exists()   # pasta vazia sai junto
    assert limpar(tmp_path, 0) == 0                            # 0 desliga


def test_pdf_do_mesmo_plano_em_duas_acomodacoes_nao_se_sobrescreve():
    cfg = {"saida": {"nome_pdf_destino": "SULAMERICA {plano_arquivo}.pdf", "nomes_arquivo": {}}}
    assert nome_pdf_destino(cfg, "1", "2", "Direto Nacional") == "SULAMERICA DIRETO NACIONAL.pdf"
    assert nome_pdf_destino(cfg, "1", "2", "Direto Nacional", "Enfermaria") == "SULAMERICA DIRETO NACIONAL ENFERMARIA.pdf"


def test_registro_da_versao_anterior_e_levado_para_a_pasta_da_operadora(tmp_path):
    from nucleo.registro import carregar_config, migrar_legado
    (tmp_path / "config.yaml").write_text("geral: {pasta_saida: saida}\noperadoras: {sulamerica: {}}\n", encoding="utf-8")
    saida = tmp_path / "saida"
    (saida / "pdfs").mkdir(parents=True)
    (saida / "estado.json").write_text('{"itens": {"k": {"status": "pdf_ok"}}}', encoding="utf-8")
    total = carregar_config(tmp_path / "config.yaml")
    migrar_legado(total)
    assert (saida / "sulamerica" / "estado.json").exists() and (saida / "sulamerica" / "pdfs").is_dir()
    assert not (saida / "estado.json").exists()
    (saida / "estado.json").write_text("{}", encoding="utf-8")   # dois registros: não adivinha, para
    with pytest.raises(RuntimeError, match="dois registros"):
        migrar_legado(total)


def test_linha_apagada_nos_ajustes_some_mesmo_se_veio_do_config(tmp_path):
    from nucleo.registro import carregar_config
    (tmp_path / "config.yaml").write_text(
        'operadoras:\n  sulamerica:\n    congeneres_de_para: {"Notre Dame": "NOTREDAME", "Bradesco": "BRADESCO SAUDE"}\n'
        '    arquivos: {nomes_arquivo: {"Executivo R1": "EXECUTIVO"}}\n', encoding="utf-8")
    total = carregar_config(tmp_path / "config.yaml", {"operadoras": {"sulamerica": {
        "congeneres_de_para": {"Bradesco": "BRADESCO SAUDE"}, "arquivos": {"nomes_arquivo": {}}}}})
    assert total["operadoras"]["sulamerica"]["congeneres_de_para"] == {"Bradesco": "BRADESCO SAUDE"}
    assert total["operadoras"]["sulamerica"]["arquivos"]["nomes_arquivo"] == {}


# ---------- configuração do robô pelo corretor ----------

def test_todo_campo_da_engrenagem_existe_na_configuracao_da_operadora():
    """Um erro de digitação numa chave faria a engrenagem mostrar um campo que o robô nunca lê."""
    from pathlib import Path
    import operadoras
    from nucleo import configuracao as c
    from nucleo.registro import carregar_config
    total = carregar_config(Path(__file__).resolve().parents[2] / "config.yaml")
    for op in operadoras.todas():
        cfg = op.config(total)
        telas = op.configuracao(cfg)
        assert [t["etapa"] for t in telas] == [e for e, _ in op.etapas]   # mesma ordem do Andamento
        for campo in c.campos_por_chave(telas).values():
            valor = c.ler(cfg, campo["chave"])
            assert valor is not None, campo["chave"]
            assert c.validar(campo, c.para_tela(campo, valor)) is not None   # o padrão passa na validação


def test_validacao_dos_campos_da_engrenagem():
    from nucleo import configuracao as c
    vig = {"tipo": "escolha", "opcoes": [["12", "12 meses"], ["24", "24 meses"]]}
    assert c.validar(vig, "12") == "12"
    with pytest.raises(ValueError):
        c.validar(vig, "36")
    assert c.validar({"tipo": "escolha", "inteiro": True, "opcoes": [["300000", "5 min"]]}, "300000") == 300000
    assert c.validar({"tipo": "sim_nao", "booleano": True}, "nao") is False
    with pytest.raises(ValueError, match="plano_arquivo"):
        c.validar({"tipo": "texto", "validar": "nome_pdf"}, "SULAMERICA.pdf")
    assert c.validar({"tipo": "faixas"}, ["59+", "0 - 18"]) == ["0 - 18", "59+"]
    with pytest.raises(ValueError):
        c.validar({"tipo": "faixas"}, ["0 - 17"])
    assert c.validar({"tipo": "planos"}, ["Especial Mais | apartamento"]) == ["Especial Mais | Apartamento"]
    with pytest.raises(ValueError):
        c.validar({"tipo": "planos"}, ["Especial Mais"])
    assert c.validar({"tipo": "pares"}, {" Notre ": "NOTREDAME", "": "x"}) == {"Notre": "NOTREDAME"}
    with pytest.raises(ValueError):
        c.validar({"tipo": "numero", "minimo": 1, "maximo": 10}, 11)
    secao = {}
    c.gravar(secao, "tempos.timeout_login_ms", 600000)
    assert secao == {"tempos": {"timeout_login_ms": 600000}}
    assert c.ler({"execucao": {"timeout_login_ms": 600000}}, "tempos.timeout_login_ms") == 600000


def test_planilha_vazia_usa_a_configuracao_do_robo(tmp_path):
    cfg = dict(CFG, padroes=dict(CFG["padroes"], vigencia_meses="12", coparticipacao="sem",
                                 planos=["Executivo R1 | Apartamento"], produto="557 - AHO"))
    pedidos, erros = ler_planilha(_planilha(tmp_path, [_linha(vigencia_meses="", coparticipacao="", planos="")]), cfg)
    assert erros == []
    [p] = pedidos
    assert (p.vigencia_meses, p.coparticipacao) == (12, "sem")
    assert [x.rotulo() for x in p.planos] == ["Executivo R1 | Apartamento"]
    cfg["padroes"]["planos_modo"] = "menor_preco"
    [p] = ler_planilha(_planilha(tmp_path, [_linha(planos="")]), dict(cfg, criterio_plano={"quantidade": 2}))[0]
    assert p.criterio_quantidade == 2 and p.planos == []


def test_outro_produto_e_outra_cotacao_mas_as_chaves_antigas_continuam_valendo(tmp_path):
    [p] = ler_planilha(_planilha(tmp_path, [_linha()]), CFG)[0]
    antiga = p.assinatura()
    assert "produto" not in antiga          # 557 - AHO: igual às chaves já gravadas
    p.produto = "999 - OUTRO"
    assert p.assinatura() != antiga


def test_login_guardado_antes_da_separacao_continua_valendo():
    """O cofre da SulAmérica guarda {cpf, email, senha, quando} desde antes da separação: nada é migrado."""
    import json as _json

    from nucleo.credenciais import Cofre, CofreMemoria
    from operadoras.sulamerica.simulador.servidor import Simulador

    CofreMemoria.esvaziar()
    cofre = Cofre("sulamerica", memoria=True)
    assert [c["chave"] for c in cofre.campos] == ["cpf", "email", "senha"]
    CofreMemoria().set_password(cofre.servico, cofre.usuario, _json.dumps(
        {"cpf": Simulador.CPF, "email": Simulador.EMAIL, "senha": Simulador.SENHA, "quando": "2026-11-05T10:00:00"}))
    assert cofre.situacao() == {"guardadas": True, "email_mascarado": "co***@***.local",
                                "quando": "2026-11-05T10:00:00", "recusadas": False}
    assert cofre.ler()["cpf"] == Simulador.CPF
    CofreMemoria.esvaziar()


# ---------- espera do conteúdo da tela (15/11: o título troca antes do corpo) ----------

class _PaginaQueDemora:
    """Mostra o texto da tela anterior `vezes` leituras e só depois o da tela nova (o portal troca URL e título antes)."""

    def __init__(self, antigo: str, novo: str, vezes: int):
        self.textos = [antigo] * vezes + [novo]
        self.leituras = 0

    def locator(self, _seletor):
        pagina = self

        class _Corpo:
            def inner_text(self):
                texto = pagina.textos[min(pagina.leituras, len(pagina.textos) - 1)]
                pagina.leituras += 1
                return texto
        return _Corpo()


def _sessao_falsa(pagina, timeout_ms=5000):
    import logging
    from types import SimpleNamespace
    return SimpleNamespace(page=pagina, cfg={"execucao": {"timeout_tela_ms": timeout_ms}}, log=logging.getLogger("t"))


def test_comparacao_espera_a_tabela_aparecer_em_vez_de_ler_a_tela_anterior():
    from operadoras.sulamerica import etapas as et

    antigo = "Planos disponíveis\n14 opções encontradas • 1 selecionado(s)\nEspecial 100 R1"
    novo = "Comparação de Planos\nEspecial 100 R1\nFaixas\n0 - 18\n1\nR$ 100,00\nR$ 100,00"
    pagina = _PaginaQueDemora(antigo, novo, vezes=3)
    pronto = lambda t: bool(re.search(r"\bfaixas\b", t, re.I)) and bool(ex.ler_tabela_comparacao(t))
    assert not pronto(antigo) and pronto(novo)
    assert et._esperar_conteudo(_sessao_falsa(pagina), "comparacao", pronto, "Comparação") == novo
    assert pagina.leituras == 4                       # leu a tela velha 3 vezes e esperou, em vez de falhar na 1ª


def test_espera_de_conteudo_desiste_no_tempo_da_tela_e_devolve_o_ultimo_texto():
    import time

    from operadoras.sulamerica import etapas as et

    pagina = _PaginaQueDemora("velho", "velho", vezes=1000)
    inicio = time.monotonic()
    texto = et._esperar_conteudo(_sessao_falsa(pagina, timeout_ms=1200), "comparacao", lambda t: False, "Comparação")
    assert texto == "velho" and 1.0 <= time.monotonic() - inicio < 4      # não trava: quem chamou confere e falha fechado


# ---------- card do plano: layout antigo (só o total) e novo (por vida + "Total estimado") ----------

def test_card_do_plano_usa_o_total_nos_dois_layouts_do_portal():
    """15/11: o portal passou a mostrar 'R$ 627,45 por vida / mês' e, abaixo, 'Total estimado: R$ 1.882,35 / mês (3 vidas)'.
    O robô comparava o 1º valor com a soma das faixas (o total) e parava com 'soma das faixas 1882.35 difere de 627.45'."""
    cabeca = "Selecionar plano\nEspecial 100 R1\nApartamento\n557 - AHO - Compulsória - 24 meses\nCom coparticipação\n"
    antigo = ex.ler_card_plano(cabeca + "R$\n1.882,35\n/ mês\nSelecionar plano")
    novo = ex.ler_card_plano(cabeca + "R$\n627,45\npor vida / mês\nTotal estimado: R$ 1.882,35 / mês (3 vidas)\nSelecionar plano")
    for card in (antigo, novo):
        assert (card.nome, card.acomodacao, card.preco) == ("Especial 100 R1", "Apartamento", Decimal("1882.35"))
        assert card.descricao.startswith("557 - AHO") and card.coparticipacao == "Com coparticipação"
    # e a conferência da Comparação bate com o total (1 vida de 0-18 + 2 de 34-38), como no portal de 15/11
    tabela = {r: {"qtd": 0, "valor_vida": Decimal("500"), "subtotal": None} for r in ROTULOS}
    tabela["0 - 18"] = {"qtd": 1, "valor_vida": Decimal("402.05"), "subtotal": Decimal("402.05")}
    tabela["34 - 38"] = {"qtd": 2, "valor_vida": Decimal("740.15"), "subtotal": Decimal("1480.30")}
    assert ex.conferir_tabela(tabela, {"0 - 18": 1, "34 - 38": 2}, novo.preco, Decimal("0.05")) == []


def test_tela_de_modulos_na_url_da_cotacao_emitida_nao_e_tomada_por_emitida(monkeypatch):
    """15/11: depois de 'Sair da cotação' o portal novo mostra 'Selecione um módulo' em Simulador.aspx?Token=...; só pela URL o
    robô achava que era a cotação emitida e o pedido seguinte falhava procurando 'Voltar para a home'."""
    import logging
    from types import SimpleNamespace

    from operadoras.sulamerica import fluxo

    url = "https://os11.sulamerica.com.br/SaudeCotador/Simulador.aspx?Token=abc%2F&InFlgViaSimulador=True"
    s = SimpleNamespace(page=SimpleNamespace(url=url), cfg={"execucao": {"timeout_tela_ms": 2000}}, log=logging.getLogger("t"),
                        t=lambda chave: 2000)
    monkeypatch.setattr(fluxo, "tela_modulos_visivel", lambda page: True)
    assert fluxo.identificar_etapa(s) == "modulos"
    monkeypatch.setattr(fluxo, "tela_modulos_visivel", lambda page: False)     # a página da emissão de verdade
    assert fluxo.identificar_etapa(s) == "emitida"


def test_tela_travada_antes_do_resumo_recarrega_a_pagina_uma_vez(monkeypatch):
    """15/11: o portal novo trocava a URL mas mantinha o corpo da tela anterior (sem rede pendente nem erro de JS)."""
    from nucleo.navegador import ErroFluxo
    from operadoras.sulamerica import telas

    prazos = []

    class Pagina:
        recarregou = 0

        def get_by_text(self, _t):
            return "titulo"

        def reload(self, **_k):
            self.recarregou += 1

    def esperar_visivel(loc, ms, descricao, etapa=""):
        prazos.append(("antes", ms))
        raise ErroFluxo(f"não encontrei '{descricao}'", etapa)           # a tela não veio no 1º prazo

    depois = []
    monkeypatch.setattr(telas, "pular_tour_sempre", lambda p: None)
    monkeypatch.setattr(telas, "esperar_sem_skeleton", lambda p, t=0: None)
    monkeypatch.setattr(telas, "fechar_guia", lambda p: False)
    monkeypatch.setattr(telas, "esperar_visivel", esperar_visivel)
    monkeypatch.setattr(telas, "_esperar_titulo_ou_reinicio", lambda page, titulo, etapa, ms: depois.append((etapa, ms)))
    cfg = {"execucao": {"timeout_tela_ms": 150000}}

    pagina = Pagina()
    telas.esperar_tela(pagina, "cuidado_360", cfg)
    assert pagina.recarregou == 1 and prazos == [("antes", 15000)] and depois == [("cuidado_360", 135000)]

    # o portal voltou ao começo depois do F5: o fluxo é avisado (retoma o pedido de lá)
    def reiniciou(page, titulo, etapa, ms):
        raise telas.TelaReiniciou(etapa)
    monkeypatch.setattr(telas, "_esperar_titulo_ou_reinicio", reiniciou)
    pagina = Pagina()
    with pytest.raises(telas.TelaReiniciou):
        telas.esperar_tela(pagina, "vidas", cfg)
    assert pagina.recarregou == 1

    # no resumo (e na emissão) o robô nunca recarrega
    pagina = Pagina()
    with pytest.raises(ErroFluxo):
        telas.esperar_tela(pagina, "resumo", cfg)
    assert pagina.recarregou == 0


def test_versao_do_cotador_vem_do_hash_dos_arquivos_principais():
    """06/11 e 15/11 (reais): o hash do layout e do webpack mudou quando o portal foi atualizado."""
    comum = ["/_next/static/chunks/4bd1b696-409494caf8c83275.js", "/_next/static/chunks/main-app-81e2fc36ff2aee1e.js",
             "https://www.googletagmanager.com/gtm.js?id=GTM-54KKXMMH", "/_Incapsula_Resource?SWJIYLWA=719d"]
    antes = ex.build_do_portal(comum + ["/_next/static/chunks/app/layout-5fa774eed9865fe3.js",
                                         "/_next/static/chunks/webpack-4735324ad98ba825.js"])
    depois = ex.build_do_portal(comum + ["/_next/static/chunks/app/layout-81e004a62e521a8e.js",
                                          "/_next/static/chunks/webpack-538ae9ec35e27b8e.js"])
    assert antes != depois and "webpack-538ae9ec35e27b8e.js" in depois and "main-app-81e2fc36ff2aee1e.js" in depois
    assert ex.build_do_portal(["/algo/outro.js", None]) == "" and ex.build_do_portal([]) == ""
