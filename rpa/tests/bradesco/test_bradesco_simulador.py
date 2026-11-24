"""Robô da Bradesco (Playwright) contra o simulador local: a LÓGICA do processo (um por empresa), dos cálculos
(Alterar Cotação), do registro que impede gerar de novo e do PDF pela janela Imprimir. Os seletores do portal real
são a calibragem (ensaio com prints)."""
from __future__ import annotations

import json

import pytest
import yaml
from openpyxl import Workbook, load_workbook

from operadoras.bradesco.simulador.servidor import Simulador

FAIXAS = ["0_18", "19_23", "24_28", "29_33", "34_38", "39_43", "44_48", "49_53", "54_58", "59_mais"]
COLUNAS = (["id", "cnpj", "coparticipacao", "dental"] + [f"vidas_{f}" for f in FAIXAS]
           + ["idades_0_18", "idades_59_mais", "planos", "pasta_destino"])
PEDIDO_VIDEO = dict(id="B1", cnpj="11.222.333/0001-81", coparticipacao="com", vidas_0_18=1, vidas_34_38=2,
                    idades_0_18="0", planos="Nacional Plus 4x | Quarto")


@pytest.fixture()
def sim():
    s = Simulador().iniciar()
    yield s
    s.parar()


@pytest.fixture(autouse=True)
def login_falso():
    """O robô entra no simulador com o login FALSO dele, num cofre só de memória."""
    from nucleo.credenciais import Cofre, CofreMemoria
    CofreMemoria.esvaziar()
    Cofre("bradesco", memoria=True).guardar(documento=Simulador.DOCUMENTO, cpf=Simulador.CPF_ACESSO, senha=Simulador.SENHA,
                                            intermediario_cpf=Simulador.CPF_INTERMEDIARIO)
    yield
    CofreMemoria.esvaziar()


def _pedido(**campos):
    base = {c: "" for c in COLUNAS}
    base.update({f"vidas_{f}": 0 for f in FAIXAS})
    base.update(campos)
    return [base[c] for c in COLUNAS]


def _preparar(tmp_path, sim, linhas, monkeypatch, liberada=True, **extra):
    monkeypatch.chdir(tmp_path)
    secao = {"urls": {"login": sim.url_login, "cotador": sim.url_cotador},
             "tempos": {"timeout_login_ms": 20000, "timeout_tela_ms": 15000, "timeout_emissao_ms": 20000,
                        "timeout_download_ms": 15000},
             "emissao_liberada": liberada,
             "padroes": {"email_corretora": "contato@corretora-treino.local"}}
    secao.update(extra)
    cfg = {"geral": {"pasta_saida": "saida", "modo_visual": False, "lentidao_ms": 0, "pausa_entre_pedidos_s": 0},
           "teste": {"cofre": "memoria"}, "operadoras": {"bradesco": secao}}
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    wb = Workbook()
    ws = wb.active
    ws.append(COLUNAS)
    for l in linhas:
        ws.append(l)
    wb.save(tmp_path / "cotacoes.xlsx")


def _rodar(*extra):
    import main
    return main.main(["--config", "config.yaml", "--operadora", "bradesco", "--planilha", "cotacoes.xlsx", *extra])


def _resultados(tmp_path, aba="cotacoes"):
    ws = load_workbook(tmp_path / "saida" / "bradesco" / "resultados.xlsx")[aba]
    linhas = list(ws.iter_rows(values_only=True))
    return [dict(zip(linhas[0], l)) for l in linhas[1:]]


def _estado(tmp_path):
    return json.loads((tmp_path / "saida" / "bradesco" / "estado.json").read_text(encoding="utf-8"))


def test_ensaio_vai_ate_o_resultado_e_nao_gera_processo(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    assert _rodar("--ensaio", "--mapear") == 0
    assert sim.processos == {} and sim.finalizacoes == 0
    assert sim.simulacoes == 1                                       # só o Calcular do cotador novo (indicativo)
    [r] = _resultados(tmp_path)
    assert (r["status"], r["plano"], r["acomodacao"]) == ("ENSAIO_OK", "Nacional Plus 4x", "Quarto")
    assert (r["preco_mensal"], r["iof"]) == (5671.64, 134.99)       # valores do vídeo
    assert r["valor_vida_0_18"] == 1155.96 and r["valor_vida_34_38"] == 2257.84
    precos = _resultados(tmp_path, "precos_planos")
    assert {p["plano"] for p in precos} >= {"Nacional Plus 8x", "Nacional Plus 6x", "Nacional Plus 4x", "Nacional III"}


def test_um_plano_com_e_sem_sao_um_processo_e_dois_calculos(tmp_path, sim, monkeypatch):
    destino = tmp_path / "CLIENTE"
    destino.mkdir()
    _preparar(tmp_path, sim, [_pedido(**dict(PEDIDO_VIDEO, coparticipacao="as_duas", pasta_destino=str(destino)))],
              monkeypatch)
    assert _rodar("--confirmar") == 0
    [(numero, processo)] = sim.processos.items()
    assert [(c["nome"], c["acomodacao_antiga"], c["copart"]) for c in processo["calculos"]] == [
        ("Nacional Plus", "Múltiplo 4", True), ("Nacional Plus", "Múltiplo 4", False)]
    assert sim.finalizacoes == 0 and sim.contratacoes == 0           # nunca Finalizar Cálculo
    rs = _resultados(tmp_path)
    assert [(r["plano"], r["coparticipacao"], r["status"], r["protocolo"]) for r in rs] == [
        ("Nacional Plus 4x", "com", "OK", numero), ("Nacional Plus 4x", "sem", "OK", numero)]
    # "Sem plano dental" (padrão, como no vídeo): a 1ª parcela é a do bloco "Totais Saúde" (5.671,64 + 134,99)
    assert (rs[0]["total_sem_iof"], rs[0]["iof"], rs[0]["total_com_iof"]) == (5671.64, 134.99, 5806.63)
    assert sorted(p.name for p in destino.iterdir()) == ["BRADESCO NACIONAL PLUS 4X COM COPARTICIPACAO.pdf",
                                                         "BRADESCO NACIONAL PLUS 4X SEM COPARTICIPACAO.pdf"]
    pdfs = list((tmp_path / "saida" / "bradesco" / "pdfs").glob("*.pdf"))
    assert len(pdfs) == 2 and all(p.read_bytes().startswith(b"%PDF") for p in pdfs)
    itens = _estado(tmp_path)["itens"]
    assert sorted((i["plano"], i["status"], i.get("protocolo")) for i in itens.values()) == [
        ("Nacional Plus 4x", "pdf_ok", numero), ("Nacional Plus 4x", "pdf_ok", numero), ("Processo", "pdf_ok", numero)]


def test_dois_planos_no_mesmo_processo_e_pedir_de_novo_nao_gera_nada(tmp_path, sim, monkeypatch):
    pedido = dict(PEDIDO_VIDEO, planos="Nacional Plus 4x | Quarto; Nacional III | Quarto")
    _preparar(tmp_path, sim, [_pedido(**pedido)], monkeypatch)
    assert _rodar("--confirmar") == 0
    [processo] = sim.processos.values()
    assert [(c["nome"], c["acomodacao_antiga"], c["codigo"]) for c in processo["calculos"]] == [
        ("Nacional Plus", "Múltiplo 4", "TPN4 COPART"), ("Nacional III", "Quarto Privativo", "TN3P COPART")]
    rs = _resultados(tmp_path)
    assert [(r["plano"], r["status"]) for r in rs] == [("Nacional Plus 4x", "OK"), ("Nacional III", "OK")]
    assert (rs[1]["total_sem_iof"], rs[1]["iof"], rs[1]["total_com_iof"]) == (2448.93, 58.28, 2507.21)   # vídeo
    # A mesma planilha de novo: nada é gerado (nem processo, nem cálculo).
    assert _rodar("--confirmar") == 0
    assert len(sim.processos) == 1 and len(sim.calculos) == 2
    assert [r["status"] for r in _resultados(tmp_path)[2:]] == ["PULADO", "PULADO"]
    # Outro plano para a mesma empresa e os mesmos dados: o processo já existe; o robô não gera outro.
    _preparar(tmp_path, sim, [_pedido(**dict(PEDIDO_VIDEO, planos="Nacional Plus 4x | Quarto; Nacional II | Quarto"))],
              monkeypatch)
    assert _rodar("--confirmar") == 3
    assert len(sim.processos) == 1 and len(sim.calculos) == 2
    ultimo = _resultados(tmp_path)[-2:]
    assert [(r["plano"], r["status"]) for r in ultimo] == [("Nacional Plus 4x", "PULADO"), ("Nacional II", "VERIFICAR")]
    assert "já existe" in ultimo[1]["erro"]


def test_sessao_cai_depois_de_gerar_processo_e_nao_gera_outro(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    sim.cair_depois_de_gerar = True
    assert _rodar("--confirmar") == 3
    assert len(sim.processos) == 1
    [r] = _resultados(tmp_path)
    assert r["status"] == "VERIFICAR" and "Acompanhar processos" in r["erro"]
    status = {i["plano"]: i["status"] for i in _estado(tmp_path)["itens"].values()}
    assert status == {"Processo": "emitindo", "Nacional Plus 4x": "emitindo"}
    sim.cair_depois_de_gerar = False
    assert _rodar("--confirmar") == 3                                # de novo: não gera outro processo
    assert len(sim.processos) == 1
    assert _resultados(tmp_path)[-1]["status"] == "VERIFICAR"


def _sessao(tmp_path, pw, ensaio=False, parar=None, avisar=None, reemitir=()):
    import operadoras
    from nucleo.estado import Estado
    from nucleo.navegador import Mapeador, abrir
    from nucleo.registro import carregar_config, configurar_log

    op = operadoras.obter("bradesco")
    cfg = op.config(carregar_config(tmp_path / "config.yaml"))
    pasta = tmp_path / "saida" / "bradesco"
    log = configurar_log(pasta / "logs")
    contexto, page = abrir(pw, cfg)
    s = op.nova_sessao(cfg, log, contexto, page, Estado(pasta / "estado.json"),
                       op.resultados(pasta / "resultados.xlsx", log), Mapeador(pasta, False, log), ensaio,
                       avisar=avisar, parar=parar, reemitir=reemitir)
    pedidos, _ = op.ler_planilha(tmp_path / "cotacoes.xlsx", cfg)
    return op, s, contexto, pedidos


def test_parar_so_entre_telas_e_nunca_durante_o_calculo(tmp_path, sim, monkeypatch):
    from playwright.sync_api import sync_playwright

    from nucleo.navegador import Parado

    pedido = dict(PEDIDO_VIDEO, planos="Nacional Plus 4x | Quarto; Nacional III | Quarto")
    _preparar(tmp_path, sim, [_pedido(**pedido)], monkeypatch)
    pedir = {"parar": False}

    def avisar(tipo, **dados):
        if tipo == "etapa" and dados.get("etapa") == "complementares":
            pedir["parar"] = True      # o corretor clica em Parar logo antes do Gerar processo

    with sync_playwright() as pw:
        op, s, contexto, [p] = _sessao(tmp_path, pw, parar=lambda: pedir["parar"], avisar=avisar)
        try:
            op.login(s)
            with pytest.raises(Parado):
                op.processar(s, p)
        finally:
            contexto.close()
    # O processo e o 1º cálculo saíram (o clique já tinha sido feito: o robô termina e salva o PDF); o 2º não começou.
    assert len(sim.processos) == 1 and len(sim.calculos) == 1
    assert [(r["plano"], r["status"]) for r in _resultados(tmp_path)] == [("Nacional Plus 4x", "OK"),
                                                                       ("Nacional III", "PARADO")]


def test_parar_antes_do_processo_e_continuar_depois(tmp_path, sim, monkeypatch):
    from playwright.sync_api import sync_playwright

    from nucleo.navegador import Parado

    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    pedir = {"parar": False}

    def avisar(tipo, **dados):
        if tipo == "etapa" and dados.get("etapa") == "grupos":
            pedir["parar"] = True

    with sync_playwright() as pw:
        op, s, contexto, [p] = _sessao(tmp_path, pw, parar=lambda: pedir["parar"], avisar=avisar)
        try:
            op.login(s)
            with pytest.raises(Parado):
                op.processar(s, p)
        finally:
            contexto.close()
    assert sim.processos == {}
    assert [r["status"] for r in _resultados(tmp_path)] == ["PARADO"]
    assert _rodar("--confirmar") == 0                                # continuar: pede de novo e sai
    assert len(sim.processos) == 1 and _resultados(tmp_path)[-1]["status"] == "OK"


def test_login_recusado_para_na_primeira_e_nao_tenta_de_novo(tmp_path, sim, monkeypatch):
    from nucleo.credenciais import Cofre
    Cofre("bradesco", memoria=True).guardar(documento=Simulador.DOCUMENTO, cpf=Simulador.CPF_ACESSO, senha="errada-treino-1",
                                            intermediario_cpf=Simulador.CPF_INTERMEDIARIO)
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    assert _rodar("--ensaio") == 5
    assert sim.tentativas_login == 1
    assert Cofre("bradesco", memoria=True).situacao()["recusadas"] is True
    assert _rodar("--ensaio") == 5                                   # nem abre o portal
    assert sim.tentativas_login == 1
    logs = "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "saida" / "bradesco" / "logs").glob("*.log"))
    assert "errada-treino-1" not in logs and Simulador.DOCUMENTO not in logs


def test_codigo_de_verificacao_e_pedido_ao_corretor(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    sim.exigir_codigo = True
    monkeypatch.setattr("builtins.input", lambda *_: sim.codigo)
    assert _rodar("--ensaio") == 0
    assert _resultados(tmp_path)[-1]["status"] == "ENSAIO_OK"


def test_em_calibragem_so_o_ensaio_esta_liberado(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch, liberada=False)
    assert _rodar("--confirmar") == 3
    assert sim.processos == {} and sim.simulacoes == 0
    [r] = _resultados(tmp_path)
    assert r["status"] == "ERRO" and "calibragem" in r["erro"]


def test_emitir_de_novo_a_pedido_do_corretor_gera_um_processo_novo(tmp_path, sim, monkeypatch):
    """"Emitir de novo mesmo assim" (regra 3 do CLAUDE.md, para testes e demonstrações): na Bradesco, um processo novo
    com os cálculos de novo; o antigo vai para "reemitidos". Sem o botão, pedir de novo não gera nada."""
    from playwright.sync_api import sync_playwright

    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    assert _rodar("--confirmar") == 0
    [antigo] = sim.processos
    with sync_playwright() as pw:
        op, s, contexto, [p] = _sessao(tmp_path, pw, reemitir={antigo})
        try:
            op.login(s)
            op.processar(s, p)
        finally:
            contexto.close()
    assert len(sim.processos) == 2 and len(sim.calculos) == 2
    novo = [n for n in sim.processos if n != antigo][0]
    estado = _estado(tmp_path)
    assert sorted((i["plano"], i["status"], i["protocolo"]) for i in estado["itens"].values()) == [
        ("Nacional Plus 4x", "pdf_ok", novo), ("Processo", "pdf_ok", novo)]
    assert sorted(r["item"]["protocolo"] for r in estado["reemitidos"]) == [antigo, antigo]
    assert _resultados(tmp_path)[-1]["status"] == "OK" and _resultados(tmp_path)[-1]["protocolo"] == novo
    assert _rodar("--confirmar") == 0                                # sem o botão: nada de novo
    assert len(sim.processos) == 2 and _resultados(tmp_path)[-1]["status"] == "PULADO"


def test_calculo_que_nao_carrega_nao_deixa_o_processo_sem_numero(tmp_path, sim, monkeypatch):
    """10/11 no portal real: o portal gerou o processo 16097787, mas a página do cálculo não carregou e o registro ficou
    com um processo "emitindo" SEM número (depois marcado à mão, virou pdf_ok sem número e o "Emitir de novo" não
    achava o processo). Agora o número da janela "Processo N gerado!" vai para o registro na hora."""
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    sim.calculo_em_branco = True
    assert _rodar("--confirmar") == 3
    [numero] = sim.processos
    itens = _estado(tmp_path)["itens"]
    assert sorted((i["plano"], i["status"], i["protocolo"]) for i in itens.values()) == [
        ("Nacional Plus 4x", "emitindo", numero), ("Processo", "emitindo", numero)]
    [r] = _resultados(tmp_path)
    assert r["status"] == "VERIFICAR" and numero in r["erro"] and "imprima à mão" in r["erro"].lower()
    logs = "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "saida" / "bradesco" / "logs").glob("*.log"))
    assert f"O portal gerou o processo {numero}" in logs and "Tela:" in logs      # número guardado + tela descrita
    # De novo: o registro bloqueia (não gera outro processo), com o número do processo na mensagem.
    sim.calculo_em_branco = False
    assert _rodar("--confirmar") == 3
    assert len(sim.processos) == 1 and _resultados(tmp_path)[-1]["status"] == "VERIFICAR"


def _logs(tmp_path) -> str:
    return "".join(p.read_text(encoding="utf-8") for p in sorted((tmp_path / "saida" / "bradesco" / "logs").glob("*.log")))


def test_sem_plano_dental_e_o_padrao_e_o_calculo_sai_no_layout_do_video(tmp_path, sim, monkeypatch):
    """Vídeo (69 s): o Padrão Doc 1 já vem marcado e o corretor clica em "Sem plano dental". Com isso a página do
    cálculo tem Saúde Conjugado, Totais Saúde e Totais Conjugado. O identificador é COM COPAY / SEM COPAY."""
    _preparar(tmp_path, sim, [_pedido(**dict(PEDIDO_VIDEO, coparticipacao="as_duas"))], monkeypatch)
    assert _rodar("--confirmar") == 0
    [processo] = sim.processos.values()
    assert [(c["dental_nome"], c["copart"]) for c in processo["calculos"]] == [
        ("Sem plano dental", True), ("Sem plano dental", False)]
    logs = _logs(tmp_path)
    assert "Dental que veio marcado no portal: Padrão Doc 1; pedido: Sem plano dental." in logs
    assert "Dental que ficou marcado: Sem plano dental." in logs
    assert logs.count("Layout da página do cálculo: conjugado") == 2
    assert "Identificador do cálculo: COM COPAY" in logs and "Identificador do cálculo: SEM COPAY" in logs
    assert "Janela Imprimir: layout conjugado; começa com: bradesco saúde / COM COPAY" in logs     # o que vira PDF
    assert "SEM COPAY 16/10/2026" in logs
    mapas = list((tmp_path / "saida" / "bradesco" / "mapa").glob("*/*calculo_imprimir.html"))
    assert len(mapas) == 2 and all("Totais Saúde" in m.read_text(encoding="utf-8") for m in mapas)


def test_com_dental_o_calculo_sai_no_layout_do_dental_e_confere(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**dict(PEDIDO_VIDEO, dental="Padrão Doc 1"))], monkeypatch)
    assert _rodar("--confirmar") == 0
    [r] = _resultados(tmp_path)
    assert r["status"] == "OK"
    assert (r["total_sem_iof"], r["iof"], r["total_com_iof"]) == (5671.64, 134.99, 5873.02)   # real 07/11: com o dental
    logs = _logs(tmp_path)
    assert "Dental que veio marcado no portal: Padrão Doc 1; pedido: Padrão Doc 1." in logs
    assert "Layout da página do cálculo: dental" in logs


def test_sem_plano_dental_e_sem_totais_saude_nao_imprime(tmp_path, sim, monkeypatch):
    """Se o portal mostrar o layout do dental mesmo com "Sem plano dental" (o dental pode ter ficado marcado), o robô
    não imprime e para com o motivo. O processo já existe: fica em Conferir no portal."""
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    sim.layout_com_dental_sempre = True
    assert _rodar("--confirmar") == 3
    [numero] = sim.processos
    [r] = _resultados(tmp_path)
    assert r["status"] == "VERIFICAR" and "Totais Saúde" in r["erro"] and "não imprimiu" in r["erro"]
    assert not list((tmp_path / "saida" / "bradesco" / "pdfs").glob("*.pdf"))
    assert "Janela Imprimir" not in _logs(tmp_path)
    status = {i["plano"]: i["status"] for i in _estado(tmp_path)["itens"].values()}
    assert status == {"Processo": "pdf_ok", "Nacional Plus 4x": "emitida"} and numero


def test_portal_lento_na_pagina_do_calculo_o_robo_espera_e_nao_desiste_em_60_s(tmp_path, sim, monkeypatch):
    """10/11 no portal real: depois de "Processo N gerado!" a página do cálculo levou mais de 100 s; o robô desistia em
    60 s (timeout_tela_ms) com o aviso "válido por 40 dias" cobrindo a tela. Agora espera pelo tempo da emissão
    e fecha o aviso quando aparece. Aqui: página que só carrega depois de 6 s, com timeout_tela_ms de 2 s."""
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    cfg = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    cfg["operadoras"]["bradesco"]["tempos"]["timeout_tela_ms"] = 2000
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    sim.calculo_demora_s = 6
    assert _rodar("--confirmar") == 0
    [r] = _resultados(tmp_path)
    assert r["status"] == "OK" and r["pdf_arquivo"]


def test_modo_de_testes_repete_a_mesma_cotacao_sem_ninguem_liberar(tmp_path, sim, monkeypatch):
    """10/11: o corretor repete a mesma cotação a toda hora na calibragem; o registro (processo "emitindo" de uma
    página que não carregou, ou já concluído) travava o robô na Home e pedia liberação à mão. Com `teste_repetir`, cada
    pedido tira da frente o que o registro tem da empresa e gera um processo novo (o antigo vai para "liberados")."""
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch, teste_repetir=True)
    sim.calculo_em_branco = True                       # 1ª vez: a página não carrega e o processo fica "emitindo"
    assert _rodar("--confirmar") == 3
    [primeiro] = sim.processos
    assert {i["status"] for i in _estado(tmp_path)["itens"].values()} == {"emitindo"}
    sim.calculo_em_branco = False                      # 2ª vez: sem liberar nada, gera um processo novo e conclui
    assert _rodar("--confirmar") == 0
    assert len(sim.processos) == 2 and _resultados(tmp_path)[-1]["status"] == "OK"
    # 3ª vez, o mesmo pedido já concluído: outro processo novo (o antigo fica no histórico)
    assert _rodar("--confirmar") == 0
    assert len(sim.processos) == 3 and _resultados(tmp_path)[-1]["status"] == "OK"
    estado = _estado(tmp_path)
    assert {i["status"] for i in estado["itens"].values()} == {"pdf_ok"} and len(estado["itens"]) == 2
    assert len(estado["liberados"]) >= 4 and primeiro in json.dumps(estado["liberados"])
    assert "MODO DE TESTES" in _logs(tmp_path)


def test_sem_o_modo_de_testes_o_registro_continua_bloqueando(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    sim.calculo_em_branco = True
    assert _rodar("--confirmar") == 3
    sim.calculo_em_branco = False
    assert _rodar("--confirmar") == 3 and len(sim.processos) == 1
    assert "MODO DE TESTES" not in _logs(tmp_path)


def test_parar_vale_na_espera_da_pagina_do_calculo_depois_de_ter_o_numero(tmp_path, sim, monkeypatch):
    """10/11: com a página do cálculo demorando, o corretor clicava em Parar e ouvia "só paro na próxima tela" por
    minutos. Com o número do processo já guardado (o processo existe), esperar a página é ponto seguro para parar."""
    import time

    from playwright.sync_api import sync_playwright

    from nucleo.navegador import Parado

    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    sim.calculo_demora_s = 40
    pedir = {"parar": False}

    def avisar(tipo, **dados):
        if tipo == "etapa" and dados.get("etapa") == "calculo":
            pedir["parar"] = True

    inicio = time.monotonic()
    with sync_playwright() as pw:
        op, s, contexto, [p] = _sessao(tmp_path, pw, parar=lambda: pedir["parar"], avisar=avisar)
        try:
            op.login(s)
            with pytest.raises(Parado):
                op.processar(s, p)
        finally:
            contexto.close()
    assert time.monotonic() - inicio < 35                           # parou na espera, não esperou os 40 s
    [numero] = sim.processos
    itens = _estado(tmp_path)["itens"]
    assert {i["status"] for i in itens.values()} == {"emitindo"} and {i["protocolo"] for i in itens.values()} == {numero}
    assert "Parar pedido enquanto esperava a página do cálculo" in _logs(tmp_path)


def test_aba_do_robo_morta_o_robo_segue_na_aba_que_responde(tmp_path):
    """Aba fechada, ou aberta mas sem responder (TargetClosedError nos quadros): o robô segue em outra aba que responde."""
    from types import SimpleNamespace

    from operadoras.bradesco.etapas import _garantir_pagina

    class TargetClosedError(Exception):
        pass

    class Pagina:
        def __init__(self, fechada, responde, url=""):
            self._f, self._r, self.url = fechada, responde, url
            self.locator = lambda *_: SimpleNamespace(first=SimpleNamespace(get_attribute=self._ler))

        def _ler(self, *_a, **_k):
            if not self._r:
                raise TargetClosedError("Target page, context or browser has been closed")

        def is_closed(self):
            return self._f

    for morta in (Pagina(True, False), Pagina(False, False, "https://x.bradescoseguros.com.br/velha")):
        viva = Pagina(False, True, "https://x.bradescoseguros.com.br/pnegocios/calculo")
        infos, avisos = [], []
        s = SimpleNamespace(page=morta, lugar="velho", contexto=SimpleNamespace(pages=[morta, viva]),
                            log=SimpleNamespace(info=infos.append, warning=avisos.append))
        _garantir_pagina(s)
        assert s.page is viva and s.lugar is None
        assert "não responde" in avisos[0] and "aba 1" in avisos[0] and "responde" in avisos[0]
        assert "seguiu em outra aba" in infos[0]
        _garantir_pagina(s)                                         # viva: não mexe
        assert s.page is viva and len(infos) == 1 and len(avisos) == 1


def test_select_do_formulario_antigo_com_o_rotulo_so_numa_celula_da_tabela():
    """Portal real 10/11 (Alterar Cotação): o rótulo "Plano Saúde *" é uma célula da tabela, sem label ligado ao select;
    o get_by_label não achava nada e a lista de opções vinha vazia. O seletor cai no 1º select depois da célula."""
    from playwright.sync_api import sync_playwright

    from operadoras.bradesco import seletores as sel

    pagina = """<table>
      <tr><td>Tipo de Cotação*</td><td><select><option>Saúde</option></select></td></tr>
      <tr><td>Plano Saúde <span>*</span></td><td><select><option>Nacional III</option><option>Efetivo</option></select></td></tr>
      <tr><td>Acomodação</td><td><select><option>Quarto Privativo</option></select></td></tr>
      <tr><td><label for="c">Coparticipação</label></td><td><select id="c"><option>30%</option><option>Sem coparticipação</option></select></td></tr>
    </table>"""
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(headless=True, channel="chromium")
        try:
            page = navegador.new_page()
            page.set_content(pagina)
            ler = lambda rotulo: [o.strip() for o in sel.select_antigo(page, rotulo).first.locator("option").all_inner_texts()]
            assert ler("Plano Saúde") == ["Nacional III", "Efetivo"]
            assert ler("Acomodação") == ["Quarto Privativo"]
            assert ler("Coparticipação") == ["30%", "Sem coparticipação"]       # com label ligado, continua por ele
        finally:
            navegador.close()


def test_campo_codigo_sucursal_nao_e_tela_de_codigo_de_verificacao():
    """10/11: o mapa não gravou o Alterar Cotação ("tela de código de verificação (campo codigoSucursal)")."""
    from types import SimpleNamespace

    from operadoras.bradesco import _campos_de_cadastro_no_mapa

    class Quadro:
        def evaluate(self, js):
            return False                                            # sem campo de senha na tela

    pagina = SimpleNamespace(frames=[Quadro()], url="https://x.bradescoseguros.com.br/pnegocios/cotacao-spg")
    for campo, esperado in (("codigoSucursal", None), ("codigoVerificacao", "codigo")):
        mapa = SimpleNamespace(_campo_codigo=campo, path_login="/login/x", tela_sensivel=lambda page: "codigo")
        _campos_de_cadastro_no_mapa(mapa)
        assert mapa.tela_sensivel(pagina) == esperado


def test_selects_do_alterar_cotacao_do_portal_real_pelo_name_e_nao_pela_tabela_escondida():
    """Mapa real de 10/11 (18_alterar_form_2): o texto "Plano Saúde" também está numa tabela escondida que vem antes; o
    1º select depois dele era a Categoria Funcional (Administradores, Sócios...). Pelo name, cada rótulo acha o seu."""
    from playwright.sync_api import sync_playwright

    from operadoras.bradesco import extracao as ex
    from operadoras.bradesco import seletores as sel

    pagina = """
    <table style="display:none"><tr><td>Categoria Funcional</td><td>Plano Saúde</td><td>Coparticipação</td>
      <td>Acomodação</td></tr></table>
    <table><tr><td>Categoria Funcional*</td><td><select name="valorPerfil"><option>Selecione...</option>
      <option>Administradores</option><option>Sócios</option></select></td>
      <td>Acomodação*</td><td><select name="acomodacao.acmdEscolhidas" multiple size="4"><option>Quarto Privativo</option>
      <option>Multiplo 2</option><option>Multiplo 3</option></select></td>
      <td>Coparticipação</td><td><select name="fatorModerador.codigo"><option selected>--</option><option>30%</option></select></td></tr>
      <tr><td>Plano Saúde*</td><td><select name="rede.codigo"><option>Selecione...</option><option>Nacional II</option>
      <option>Nacional III</option><option>Nacional Plus</option></select></td></tr></table>"""
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(headless=True, channel="chromium")
        try:
            page = navegador.new_page()
            page.set_content(pagina)
            ler = lambda rotulo: [o.strip() for o in sel.select_antigo(page, rotulo).first.locator("option").all_inner_texts()]
            assert ler("Plano Saúde") == ["Selecione...", "Nacional II", "Nacional III", "Nacional Plus"]
            assert ler("Acomodação") == ["Quarto Privativo", "Multiplo 2", "Multiplo 3"]
            assert ler("Coparticipação") == ["--", "30%"]
            sel.select_antigo(page, "Acomodação").first.select_option(label="Multiplo 2")      # lista múltipla
            assert page.locator("select[name='acomodacao.acmdEscolhidas']").evaluate(
                "e => [...e.selectedOptions].map(o => o.text)") == ["Multiplo 2"]
        finally:
            navegador.close()
    # "--" é a opção sem coparticipação do formulário real
    assert ex.copart_do_texto("--") == "sem" and ex.copart_do_texto("30%") == "com"


def test_fechar_avisos_tira_seguros_friday_mesmo_sem_classe_in():
    """Portal real 18/11: o cartaz da Seguros Friday às vezes abre sem a classe Bootstrap `in`. O robô tem que
    tirá-lo mesmo assim, senão o clique em Cotação SPG nunca chega e o Parar também trava."""
    from playwright.sync_api import sync_playwright

    from operadoras.bradesco.etapas import fechar_avisos

    html = """
    <div class="modal fade pn-modal modal-aviso" role="dialog" style="display:block">
      <button type="button" class="close" aria-label="Close"><i class="icon-nav-fechar"></i></button>
      <p>A Seguros Friday 2026 começou!</p>
      <p>Não quero mais visualizar esta mensagem.</p>
    </div>
    <p id="atrás">Cotação SPG</p>
    """
    with sync_playwright() as pw:
        nav = pw.chromium.launch()
        page = nav.new_page()
        page.set_content(html)
        assert page.get_by_text("Seguros Friday").is_visible()
        fechar_avisos(page)
        assert page.get_by_text("Seguros Friday").first.is_visible() is False
        assert page.get_by_text("Cotação SPG").is_visible()
        nav.close()


def test_fechar_avisos_tira_cartaz_friday_so_com_imagem_ainda_escondido():
    """Portal real 18/11 00:46: o cartaz é uma <img> (sem 'Friday' no innerText) e o Bootstrap só chama
    .modal('show') no window.load. Se o robô exigir visível, o modal nasce depois e cobre o Painel Saúde."""
    from playwright.sync_api import sync_playwright

    from operadoras.bradesco.etapas import fechar_avisos

    html = """
    <div class="modal fade pn-modal modal-aviso" id="modal-comunicacao-x" role="dialog">
      <button type="button" class="close" aria-label="Close" data-analytics-label="Seguros Friday 2026 | Fechar">
        <i class="icon-nav-fechar"></i>
      </button>
      <a data-analytics-label="Seguros Friday 2026"><img src="about:blank" alt=""></a>
      <label>Não quero mais visualizar esta mensagem.
        <input id="checkbox-view" class="checkbox-view" type="checkbox">
      </label>
    </div>
    <p id="atrás">Acesso rápido</p>
    """
    with sync_playwright() as pw:
        nav = pw.chromium.launch()
        page = nav.new_page()
        page.set_content(html)
        assert page.locator("#modal-comunicacao-x").count() == 1
        fechar_avisos(page)
        assert page.locator("#modal-comunicacao-x").first.is_visible() is False
        nav.close()


def test_abrir_cotacao_spg_pelo_submenu_quando_acesso_rapido_esta_vazio():
    """Portal real 15/11 e 18/11: Acesso rápido vazio. O subnav é <div openmenuoptions>Cotações</div> (CSS uppercase)."""
    from playwright.sync_api import sync_playwright

    from operadoras.bradesco.etapas import _abrir_cotacao_spg

    html = """
    <p>Favorite um menu para exibir aqui</p>
    <bspn-fed-sub-menus-out>
      <div openmenuoptions="" onclick="document.getElementById('spg').hidden=false">
        <span>Cotações</span>
      </div>
      <a id="spg" href="/saude/cotacoes/cotacao-spg" hidden
         onclick="event.preventDefault(); this.dataset.aberto='1'">Cotação SPG</a>
    </bspn-fed-sub-menus-out>
    """
    with sync_playwright() as pw:
        nav = pw.chromium.launch()
        page = nav.new_page()
        page.set_content(html)
        _abrir_cotacao_spg(page, 5)
        assert page.locator("#spg").get_attribute("data-aberto") == "1"
        nav.close()


def test_abrir_cotacao_spg_no_dropdown_sem_href_sem_fechar_o_menu():
    """Portal 24/11: Acesso rápido vazio; o item do dropdown é um <p>, não um <a>. Cotações é toggle."""
    from playwright.sync_api import sync_playwright

    from operadoras.bradesco.etapas import _abrir_cotacao_spg

    html = """
    <p>Favorite um menu para exibir aqui</p>
    <div openmenuoptions="" id="cot" onclick="
      var m=document.getElementById('menu'); m.hidden=!m.hidden;">Cotações</div>
    <div id="menu" hidden>
      <div id="spg" onclick="this.dataset.aberto='1'">
        <span>casa</span><span>estrela</span><p>Cotação SPG</p>
      </div>
    </div>
    """
    with sync_playwright() as pw:
        nav = pw.chromium.launch()
        page = nav.new_page()
        page.set_content(html)
        _abrir_cotacao_spg(page, 5)
        assert page.locator("#spg").get_attribute("data-aberto") == "1"
        assert page.locator("#menu").evaluate("e => e.hidden") is False
        nav.close()

