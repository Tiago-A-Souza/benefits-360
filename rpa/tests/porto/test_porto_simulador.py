"""Robô da Porto contra o simulador local: ensaio no passo 3, 2 cotações, PDF, queda, anti-duplicar, parar.

O Gerar orçamento dos testes abaixo liga emissao_liberada SÓ no config do teste. O padrão da operadora
continua falso. O simulador conta cliques proibidos; se o robô acionar algum, o teste falha.
"""
from __future__ import annotations

import json

import pytest
import yaml
from openpyxl import Workbook, load_workbook

from operadoras.porto.simulador.servidor import Simulador, calcular

FAIXAS = ["0_18", "19_23", "24_28", "29_33", "34_38", "39_43", "44_48", "49_53", "54_58", "59_mais"]
COLUNAS = ["id", "cnpj", "apelido", "seguro_novo", "congenere_atual"] + [f"vidas_{f}" for f in FAIXAS] + [
    "idades_0_18", "planos", "pasta_destino"]
PEDIDO = dict(id="P1", cnpj="11.222.333/0001-81", apelido="PADARIA", seguro_novo="nao",
              congenere_atual="NOTREDAME", vidas_0_18=1, vidas_34_38=2, vidas_59_mais=1,
              idades_0_18="0", planos="Ouro Mais I")


@pytest.fixture()
def sim():
    s = Simulador().iniciar()
    yield s
    s.parar()


@pytest.fixture(autouse=True)
def login_falso():
    from nucleo.credenciais import Cofre, CofreMemoria
    CofreMemoria.esvaziar()
    Cofre("porto", memoria=True).guardar(cpf=Simulador.CPF, senha=Simulador.SENHA, susep=Simulador.SUSEP)
    yield
    CofreMemoria.esvaziar()


def _pedido(**campos):
    base = {c: "" for c in COLUNAS}
    base.update({f"vidas_{f}": 0 for f in FAIXAS})
    base.update(campos)
    return [base[c] for c in COLUNAS]


def _preparar(tmp_path, sim, linhas, monkeypatch, liberada=False, **extra):
    monkeypatch.chdir(tmp_path)
    secao = {"urls": {"login": sim.url_login, "cotador": sim.url_home},
             "tempos": {"timeout_login_ms": 20000, "timeout_tela_ms": 15000, "timeout_emissao_ms": 20000,
                        "timeout_download_ms": 15000},
             "emissao_liberada": liberada}
    secao.update(extra)
    cfg = {"geral": {"pasta_saida": "saida", "modo_visual": False, "lentidao_ms": 0, "pausa_entre_pedidos_s": 0},
           "teste": {"cofre": "memoria"}, "operadoras": {"porto": secao}}
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    wb = Workbook()
    ws = wb.active
    ws.append(COLUNAS)
    for linha in linhas:
        ws.append(linha)
    wb.save(tmp_path / "cotacoes.xlsx")


def _rodar(*extra):
    import main
    return main.main(["--config", "config.yaml", "--operadora", "porto", "--planilha", "cotacoes.xlsx", *extra])


def _resultados(tmp_path):
    ws = load_workbook(tmp_path / "saida" / "porto" / "resultados.xlsx")["cotacoes"]
    linhas = list(ws.iter_rows(values_only=True))
    return [dict(zip(linhas[0], linha)) for linha in linhas[1:]]


def _estado(tmp_path):
    return json.loads((tmp_path / "saida" / "porto" / "estado.json").read_text(encoding="utf-8"))


def _logs(tmp_path) -> str:
    return "".join(p.read_text(encoding="utf-8") for p in sorted((tmp_path / "saida" / "porto" / "logs").glob("*.log")))


def _nada_proibido(sim):
    """Falha se o robô clicar em qualquer ação irreversível ou proibida."""
    assert sim.elaborar_proposta_cliques == 0
    assert sim.adicionar_proposta_cliques == 0
    assert sim.remissao_cliques == 0
    assert sim.editar_cliques == 0
    assert sim.duplicar_cliques == 0


def _sessao(tmp_path, pw, ensaio=False, parar=None, avisar=None, reemitir=()):
    import operadoras
    from nucleo.estado import Estado
    from nucleo.navegador import Mapeador, abrir
    from nucleo.registro import carregar_config, configurar_log

    op = operadoras.obter("porto")
    cfg = op.config(carregar_config(tmp_path / "config.yaml"))
    pasta = tmp_path / "saida" / "porto"
    log = configurar_log(pasta / "logs")
    contexto, page = abrir(pw, cfg)
    s = op.nova_sessao(cfg, log, contexto, page, Estado(pasta / "estado.json"),
                       op.resultados(pasta / "resultados.xlsx", log), Mapeador(pasta, False, log), ensaio,
                       avisar=avisar, parar=parar, reemitir=reemitir)
    pedidos, _ = op.ler_planilha(tmp_path / "cotacoes.xlsx", cfg)
    return op, s, contexto, pedidos


def test_ensaio_para_no_passo_3_sem_gerar_orcamento(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO)], monkeypatch, liberada=False)
    assert _rodar("--ensaio") == 0
    assert sim.cotacoes == {}
    assert sim.gerar_orcamento_cliques == 0
    assert sim.emitir_sem_medicamentos_cliques == 0
    assert sim.susep_escolhida == Simulador.SUSEP
    [r] = _resultados(tmp_path)
    assert r["plano"] == "Ouro Mais I" and r["status"] == "ENSAIO_OK"
    assert "sem Gerar orçamento" in (r["erro"] or "")
    assert "ENSAIO na Porto" in _logs(tmp_path)
    _nada_proibido(sim)


def test_ensaio_com_dois_planos_cria_duas_cotacoes_independentes_e_nao_duplica(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**dict(PEDIDO, planos="Ouro Mais I; P470"))], monkeypatch)
    assert _rodar("--ensaio") == 0
    rs = _resultados(tmp_path)
    assert [(r["plano"], r["status"]) for r in rs] == [("Ouro Mais I", "ENSAIO_OK"), ("P470", "ENSAIO_OK")]
    assert sim.cotacoes == {} and sim.gerar_orcamento_cliques == 0 and sim.duplicar_cliques == 0
    _nada_proibido(sim)


def test_gerar_orcamento_recusado_sem_flag_mesmo_com_confirmar(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO)], monkeypatch, liberada=False)
    assert _rodar("--confirmar") != 0
    assert sim.gerar_orcamento_cliques == 0 and sim.cotacoes == {}
    [r] = _resultados(tmp_path)
    assert r["status"] == "ERRO" and "calibragem" in (r["erro"] or r["etapa_erro"] or "")
    _nada_proibido(sim)


def test_dois_planos_duas_cotacoes_com_pdf(tmp_path, sim, monkeypatch):
    cliente = tmp_path / "cliente"
    cliente.mkdir()
    _preparar(tmp_path, sim, [_pedido(**dict(PEDIDO, planos="Ouro Mais I; P470", pasta_destino=str(cliente)))],
              monkeypatch, liberada=True)
    assert _rodar("--confirmar") == 0
    assert len(sim.cotacoes) == 2 and sim.downloads >= 2
    rs = _resultados(tmp_path)
    assert [(r["plano"], r["status"]) for r in rs] == [("Ouro Mais I", "OK"), ("P470", "OK")]
    p470 = calcular("P470", {"0 - 18": 1, "34 - 38": 2, "59+": 1})
    assert [r["total_com_iof"] for r in rs] == [4721.72, float(p470["total"])]
    assert sim.duplicar_cliques == 0
    _nada_proibido(sim)


def test_erro_de_pdf_passa_na_segunda_tentativa(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO)], monkeypatch, liberada=True)
    sim.falhas_pdf_restantes = 1
    assert _rodar("--confirmar") == 0
    [r] = _resultados(tmp_path)
    assert r["status"] == "OK"
    assert "tentativa" in _logs(tmp_path).lower() or sim.downloads == 1
    _nada_proibido(sim)


def test_queda_depois_de_gerar_recupera_pela_lista_sem_gerar_outra(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO)], monkeypatch, liberada=True)
    sim.cair_depois_de_gerar = True
    rc = _rodar("--confirmar")
    assert rc != 0
    assert len(sim.cotacoes) == 1 and sim.gerar_orcamento_cliques == 1
    gerar_antes = sim.gerar_orcamento_cliques
    assert _rodar("--confirmar") == 0
    assert len(sim.cotacoes) == 1
    assert sim.gerar_orcamento_cliques == gerar_antes
    assert _resultados(tmp_path)[-1]["status"] == "OK"
    _nada_proibido(sim)


def test_pedir_de_novo_nao_duplica(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO)], monkeypatch, liberada=True)
    assert _rodar("--confirmar") == 0
    assert _rodar("--confirmar") == 0
    assert len(sim.cotacoes) == 1
    assert [r["status"] for r in _resultados(tmp_path)] == ["OK", "PULADO"]
    _nada_proibido(sim)


def test_parar_e_continuar_no_ensaio(tmp_path, sim, monkeypatch):
    from playwright.sync_api import sync_playwright

    from nucleo.navegador import Parado

    _preparar(tmp_path, sim, [_pedido(**PEDIDO)], monkeypatch)
    pedir = {"parar": False}

    def avisar(tipo, **dados):
        if tipo == "etapa" and dados.get("etapa") == "planos":
            pedir["parar"] = True

    with sync_playwright() as pw:
        op, s, contexto, [p] = _sessao(tmp_path, pw, ensaio=True, parar=lambda: pedir["parar"], avisar=avisar)
        try:
            op.login(s)
            with pytest.raises(Parado):
                op.processar(s, p)
        finally:
            contexto.close()
    assert sim.gerar_orcamento_cliques == 0 and sim.cotacoes == {}
    assert [r["status"] for r in _resultados(tmp_path)] == ["PARADO"]
    assert _rodar("--ensaio") == 0
    assert _resultados(tmp_path)[-1]["status"] == "ENSAIO_OK"
    _nada_proibido(sim)


def test_captcha_para_sem_burlar(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO)], monkeypatch)
    sim.exigir_captcha = True
    assert _rodar("--ensaio") != 0
    logs = _logs(tmp_path)
    assert "captcha" in logs.lower() or "recaptcha" in logs.lower()
    assert sim.cotacoes == {}
    _nada_proibido(sim)
