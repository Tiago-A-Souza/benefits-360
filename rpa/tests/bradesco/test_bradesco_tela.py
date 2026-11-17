"""A tela com a Bradesco, de ponta a ponta: navegador -> tela (python -m app) -> robô -> simulador da Bradesco.

A tela sobe com as duas operadoras (a SulAmérica só para a tela mostrar as duas; nada é cotado nela) e o simulador
da Bradesco. Cada teste prepara o que precisa (login falso guardado pela API da própria tela).
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

from operadoras.bradesco.simulador.servidor import Simulador

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
    pasta = tmp_path_factory.mktemp("tela_bradesco")
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
  bradesco:
    urls:
      login: "{sim.url_login}"
      cotador: "{sim.url_cotador}"
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
    p.erros_esperados = []
    yield p
    ctx.close()
    assert not [e for e in erros if not any(x in e for x in p.erros_esperados)], erros


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
    status, _ = _pedir(amb, "POST", "/api/credenciais/bradesco",
                       {"documento": Simulador.DOCUMENTO, "cpf": Simulador.CPF_ACESSO, "senha": Simulador.SENHA,
                        "intermediario_cpf": Simulador.CPF_INTERMEDIARIO}, tela=True)
    assert status == 200


def test_engrenagem_da_bradesco_pede_cpf_cnpj_senha_e_cpf_do_intermediario(page, amb):
    _pedir(amb, "DELETE", "/api/credenciais/bradesco", tela=True)
    page.goto(amb["base"] + "/#/robo/bradesco?login=1")
    expect(page.locator(".login-estado")).to_contain_text("Nenhum login guardado")
    rotulos = page.locator(".login-campos label")
    expect(rotulos).to_have_count(4)
    assert [x.strip() for x in rotulos.all_inner_texts()] == ["CPF/CNPJ", "CPF de acesso", "Senha", "CPF do intermediário"]
    page.get_by_label("CPF/CNPJ", exact=True).fill("11.444.777/0001-00")
    page.get_by_label("CPF de acesso", exact=True).fill(Simulador.CPF_ACESSO)
    page.get_by_label("Senha", exact=True).fill(Simulador.SENHA)
    page.get_by_label("CPF do intermediário", exact=True).fill(Simulador.CPF_INTERMEDIARIO)
    page.get_by_role("button", name="Guardar", exact=True).click()
    expect(page.get_by_text("CPF/CNPJ inválido: confira os dígitos.")).to_be_visible()
    page.get_by_label("CPF/CNPJ", exact=True).fill(Simulador.DOCUMENTO)
    expect(page.get_by_label("CPF/CNPJ", exact=True)).to_have_value("11.444.777/0001-61")     # máscara de CNPJ
    page.get_by_role("button", name="Guardar", exact=True).click()
    expect(page.locator(".login-estado")).to_contain_text("Login guardado")
    status, r = _pedir(amb, "GET", "/api/credenciais/bradesco")
    assert status == 200 and set(r) == {"guardadas", "quando", "recusadas"} and r["guardadas"] is True
    texto = json.dumps(r)
    assert Simulador.SENHA not in texto and Simulador.DOCUMENTO not in texto and Simulador.CPF_INTERMEDIARIO not in texto
    assert Simulador.CPF_ACESSO not in texto
    # o login da SulAmérica é outro (nada guardado lá)
    assert _pedir(amb, "GET", "/api/credenciais/sulamerica")[1]["guardadas"] is False


def test_nova_cotacao_comeca_sem_a_bradesco_e_o_ensaio_para_no_resultado(page, amb):
    _guardar_login_falso(amb)
    sim = amb["sim"]
    page.goto(amb["base"] + "/#/nova")
    expect(page.get_by_role("heading", name="Nova cotação")).to_be_visible()
    bradesco = page.locator("section.operadora").filter(has=page.get_by_text("Bradesco", exact=True))
    sulamerica = page.locator("section.operadora").filter(has=page.get_by_text("SulAmérica", exact=True))
    chave_b = bradesco.get_by_label("Cotar nesta operadora")
    expect(chave_b).not_to_be_checked()                       # em calibragem: começa desmarcada
    sulamerica.locator("label.chave").filter(has_text="Cotar nesta operadora").click()   # só a Bradesco nesta cotação
    bradesco.locator("label.chave").filter(has_text="Cotar nesta operadora").click()
    expect(chave_b).to_be_checked()
    page.get_by_label("CNPJ").fill("11222333000181")
    for faixa, qtd in {"0 - 18": 1, "34 - 38": 2}.items():
        for _ in range(qtd):
            page.get_by_role("button", name=f"Somar uma vida na faixa {faixa}").first.click()
    page.get_by_label("Idades na faixa 0 - 18").fill("0")
    bradesco.locator(".planos > div").filter(has=page.get_by_role("heading", name="Quarto")) \
        .get_by_text("Nacional Plus 4x", exact=True).click()
    expect(page.get_by_text("1 cotação na Bradesco")).to_be_visible()
    page.get_by_role("button", name="Ensaiar sem emitir").click()
    expect(page.get_by_role("heading", name="Ensaio concluído")).to_be_visible(timeout=LONGO)
    expect(page.get_by_text("R$ 5.806,63").first).to_be_visible()      # 5.671,64 + IOF 134,99 (vídeo)
    assert sim.processos == {} and sim.finalizacoes == 0
