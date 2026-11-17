"""A tela com a Amil, de ponta a ponta: navegador -> tela (python -m app) -> robô -> simulador do vendasmil.

A tela sobe com as duas operadoras (a SulAmérica só para a tela mostrar as duas; nada é cotado nela) e o simulador da Amil.
Cada teste prepara o que precisa (login falso guardado pela API da própria tela). O código de verificação de 8 dígitos é
pedido NA tela do Newport (mesma faixa da SulAmérica).
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from operadoras.amil.simulador.servidor import Simulador

RAIZ = Path(__file__).resolve().parents[2]
LONGO = 120_000


def _porta_livre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


@pytest.fixture(scope="module")
def amb(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("tela_amil")
    sim = Simulador().iniciar()
    porta = _porta_livre()
    (pasta / "config.yaml").write_text(f"""
geral:
  pasta_saida: "saida"
  modo_visual: false
  lentidao_ms: 0
  pausa_entre_pedidos_s: 0
tela:
  porta: {porta}
teste:
  simulador: true
  cofre: memoria
operadoras:
  sulamerica:
    urls:
      login: "http://127.0.0.1:9/SaudeCotador/LoginGeral.aspx"
  amil:
    urls:
      login: "{sim.url_login}"
      home: "{sim.url_home}"
    tempos:
      sair_do_portal_min: 0
      timeout_login_ms: 20000
      timeout_tela_ms: 15000
      timeout_emissao_ms: 20000
      timeout_download_ms: 15000
""", encoding="utf-8")
    log = open(pasta / "tela.log", "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "app", "--config", str(pasta / "config.yaml"), "--sem-navegador"],
                            cwd=RAIZ, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(150):
        try:
            socket.create_connection(("127.0.0.1", porta), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.2)
    else:
        proc.kill()
        pytest.fail("a tela não subiu: " + (pasta / "tela.log").read_text(encoding="utf-8"))
    base = f"http://127.0.0.1:{porta}"
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        yield {"base": base, "origem": base, "pasta": pasta, "sim": sim, "navegador": navegador}
        navegador.close()
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()
    sim.parar()


@pytest.fixture()
def page(amb):
    ctx = amb["navegador"].new_context(viewport={"width": 1366, "height": 900}, locale="pt-BR")
    p = ctx.new_page()
    erros: list[str] = []
    p.on("pageerror", lambda e: erros.append(f"erro de script: {e}"))
    yield p
    ctx.close()
    assert not erros, erros


def _pedir(amb, metodo: str, caminho: str, corpo=None, tela: bool = False) -> tuple[int, dict]:
    cabecalhos = {"Content-Type": "application/json"}
    if tela:
        cabecalhos.update({"X-Newport-Tela": "1", "Origin": amb["origem"]})
    req = urllib.request.Request(amb["base"] + caminho, data=json.dumps(corpo).encode() if corpo is not None else None,
                                 method=metodo, headers=cabecalhos)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def _guardar_login_falso(amb) -> None:
    status, _ = _pedir(amb, "POST", "/api/credenciais/amil", {"usuario": Simulador.USUARIO, "senha": Simulador.SENHA}, tela=True)
    assert status == 200


def test_engrenagem_da_amil_pede_usuario_e_senha_e_nao_guarda_o_codigo(page, amb):
    _pedir(amb, "DELETE", "/api/credenciais/amil", tela=True)
    page.goto(amb["base"] + "/#/robo/amil?login=1")
    expect(page.locator(".login-estado")).to_contain_text("Nenhum login guardado")
    assert [x.strip() for x in page.locator(".login-campos label").all_inner_texts()] == ["Usuário", "Senha"]
    page.get_by_label("Usuário", exact=True).fill(Simulador.USUARIO)
    page.get_by_label("Senha", exact=True).fill(Simulador.SENHA)
    page.get_by_role("button", name="Guardar", exact=True).click()
    expect(page.locator(".login-estado")).to_contain_text("Login guardado")
    status, r = _pedir(amb, "GET", "/api/credenciais/amil")
    assert status == 200 and r["guardadas"] is True
    assert Simulador.SENHA not in json.dumps(r) and Simulador.CODIGO not in json.dumps(r)
    # a engrenagem tem as telas do portal da Amil, com o corretor, o apelido dos planos e o aviso do ensaio
    page.goto(amb["base"] + "/#/robo/amil")
    expect(page.get_by_text("Nome do corretor")).to_be_visible()
    expect(page.get_by_text("Apelido de cada plano no nome do PDF")).to_be_visible()
    expect(page.get_by_text("o ensaio já cria a oportunidade no portal")).to_be_visible()


def test_nova_cotacao_comeca_sem_a_amil_e_o_ensaio_pede_o_codigo_na_tela(page, amb):
    _guardar_login_falso(amb)
    sim = amb["sim"]
    sim.exigir_codigo = True
    sim.expirar()
    try:
        page.goto(amb["base"] + "/#/nova")
        expect(page.get_by_role("heading", name="Nova cotação")).to_be_visible()
        amil = page.locator("section.operadora").filter(has=page.get_by_text("Amil", exact=True))
        sulamerica = page.locator("section.operadora").filter(has=page.get_by_text("SulAmérica", exact=True))
        chave = amil.get_by_label("Cotar nesta operadora")
        expect(chave).not_to_be_checked()                       # em calibragem: começa desmarcada
        sulamerica.locator("label.chave").filter(has_text="Cotar nesta operadora").click()   # só a Amil nesta cotação
        amil.locator("label.chave").filter(has_text="Cotar nesta operadora").click()
        expect(chave).to_be_checked()
        expect(page.get_by_text("o ensaio da Amil já cria a oportunidade").first).to_be_visible()   # o aviso do ensaio
        page.get_by_label("CNPJ").fill("11222333000181")
        for faixa, qtd in {"0 - 18": 1, "34 - 38": 2, "59+": 1}.items():
            for _ in range(qtd):
                page.get_by_role("button", name=f"Somar uma vida na faixa {faixa}").first.click()
        # a tela pede a idade nas faixas em que QUALQUER operadora da tela pede (a SulAmérica); a Amil ignora essas idades
        page.get_by_label("Idades na faixa 0 - 18").fill("0")
        page.get_by_label("Idades na faixa 59+").fill("60")
        amil.locator(".planos > div").filter(has=page.get_by_role("heading", name="Platinum")) \
            .get_by_text("PLATINUM R1 COPART", exact=True).click()
        expect(page.get_by_text("1 cotação na Amil")).to_be_visible()
        page.get_by_role("button", name="Ensaiar sem emitir").click()
        faixa = page.locator("#faixa-login")
        expect(faixa.get_by_text("Digite o código que chegou no seu celular/e-mail")).to_be_visible(timeout=LONGO)
        faixa.get_by_label("Digite o código que chegou no seu celular/e-mail").fill(sim.codigo)
        faixa.get_by_role("button", name="Enviar código").click()
        expect(page.get_by_role("heading", name="Ensaio concluído")).to_be_visible(timeout=LONGO)
        expect(page.get_by_text("R$ 4.769,00").first).to_be_visible()
        assert sim.codigos_digitados[-1] == sim.codigo
        assert len(sim.oportunidades) >= 1 and sim.cotacoes_concluidas == [] and sim.downloads == 0
        assert (sim.criar_proposta_cliques, sim.incluir_plano_medico_cliques, sim.enviar_email_cliques) == (0, 0, 0)
        assert _pedir(amb, "POST", "/api/codigo/amil", {"codigo": "12345678"}, tela=True)[0] == 409   # ninguém espera
    finally:
        sim.exigir_codigo = False


def test_codigo_da_amil_nao_some_quando_o_robo_de_outra_operadora_muda_de_estado(page, amb):
    """15/11 (3 robôs no mesmo pedido): a faixa do código da Amil sumia no instante em que a SulAmérica ou a Bradesco mudava
    de estado (conexao/login_ok); a Amil esperava 5 min por um código sem campo para digitar."""
    page.goto(amb["base"] + "/#/nova")
    expect(page.get_by_role("heading", name="Nova cotação")).to_be_visible()

    def evento(**ev):
        page.evaluate("(ev) => NP._tratarGlobal(ev)", ev)

    campo = page.locator("#codigo-verificacao")
    evento(tipo="conexao", operadora="amil", status="aguardando_codigo")
    evento(tipo="codigo_necessario", operadora="amil", trabalho=1)
    expect(campo).to_be_visible()
    campo.fill("4829")
    # o robô de outra operadora entra, loga e trabalha: o campo (e o que o corretor já digitou) continua lá
    evento(tipo="conexao", operadora="sulamerica", status="entrando")
    evento(tipo="login_ok", operadora="sulamerica", trabalho=1, sessao_ativa=False)
    evento(tipo="conexao", operadora="sulamerica", status="ocupado")
    evento(tipo="etapa", operadora="sulamerica", trabalho=1, etapa="vidas")
    evento(tipo="conexao", operadora="sulamerica", status="conectado")
    expect(campo).to_be_visible()
    expect(campo).to_have_value("4829")
    # a Amil recebeu o código e entrou: agora a faixa some
    evento(tipo="conexao", operadora="amil", status="entrando")
    expect(page.locator("#faixa-login")).to_be_hidden()
    # duas operadoras esperando o código: o campo da segunda aparece quando a primeira termina
    evento(tipo="conexao", operadora="amil", status="aguardando_codigo")
    evento(tipo="conexao", operadora="sulamerica", status="aguardando_codigo")
    evento(tipo="codigo_necessario", operadora="amil", trabalho=1)
    evento(tipo="codigo_necessario", operadora="sulamerica", trabalho=1)
    expect(page.locator("#faixa-login")).to_contain_text("Amil")
    evento(tipo="conexao", operadora="amil", status="entrando")
    expect(page.locator("#faixa-login")).to_contain_text("SulAmérica")
    evento(tipo="conexao", operadora="sulamerica", status="entrando")
    expect(page.locator("#faixa-login")).to_be_hidden()
