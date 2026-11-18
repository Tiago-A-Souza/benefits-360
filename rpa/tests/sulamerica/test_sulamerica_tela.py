"""A tela de ponta a ponta, como o corretor usa: navegador -> tela (python -m app) -> robô -> simulador.

A tela e o simulador sobem uma vez para o arquivo todo; cada teste usa um CNPJ diferente.
Para guardar prints de cada passo: NEWPORT_PRINTS=<pasta> python -m pytest tests/test_tela_e2e.py
"""
from __future__ import annotations

import io
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pytest
from openpyxl import load_workbook
from playwright.sync_api import expect, sync_playwright

from operadoras.sulamerica.simulador.servidor import Simulador

RAIZ = Path(__file__).resolve().parents[2]
PRINTS = os.environ.get("NEWPORT_PRINTS")
LONGO = 120_000   # ms: o robô percorre o portal de verdade (simulado)


def _porta_livre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


@pytest.fixture(scope="module")
def amb(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("tela")
    sim = Simulador().iniciar()
    porta = _porta_livre()
    porta_benefits = _porta_livre()
    (pasta / "config.yaml").write_text(f"""
geral:
  pasta_saida: "saida"
  modo_visual: false
  lentidao_ms: 0
  pausa_entre_pedidos_s: 0
tela:
  porta: {porta}
  frame_ancestors:
    - http://localhost:5173
    - http://127.0.0.1:5173
    - http://127.0.0.1:{porta_benefits}
  origens_permitidas:
    - http://localhost:5173
    - http://127.0.0.1:5173
    - http://127.0.0.1:{porta_benefits}
teste:
  simulador: true
  cofre: memoria
operadoras:
  sulamerica:
    urls:
      login: "{sim.url_login}"
    tempos:
      sair_do_portal_min: 0      # os testes da tela não saem do portal sozinhos (tem teste próprio)
      timeout_login_ms: 20000
      login_reentrada_ms: 500
      login_liberacao_ms: 3000
      timeout_tela_ms: 15000
      timeout_emissao_ms: 30000
      timeout_download_ms: 8000
    arquivos:
      nomes_arquivo:
        "Executivo R1": "EXECUTIVO"
    padroes:
      coparticipacao: "com"     # os testes antigos contam 1 cotação por plano; "Com e sem" tem teste próprio
""", encoding="utf-8")
    cliente = pasta / "cliente"
    cliente.mkdir()
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
    _guardar_login(f"http://127.0.0.1:{porta}")   # o login FALSO do simulador, no cofre de memória da tela
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        yield {
            "base": f"http://127.0.0.1:{porta}",
            "pasta": pasta,
            "cliente": cliente,
            "sim": sim,
            "navegador": navegador,
            "origem": f"http://127.0.0.1:{porta}",
            "benefits_shim": f"http://127.0.0.1:{porta_benefits}",
            "proc": proc,
        }
        navegador.close()
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()
    sim.parar()


@pytest.fixture()
def page(amb, request):
    ctx = amb["navegador"].new_context(viewport={"width": 1366, "height": 900}, accept_downloads=True, locale="pt-BR")
    p = ctx.new_page()
    erros: list[str] = []
    p.on("pageerror", lambda e: erros.append(f"erro de script: {e}"))
    p.on("console", lambda m: erros.append(f"console: {m.text}") if m.type == "error" else None)
    p.prints = []
    p.nome_teste = request.node.name
    p.erros_esperados = []   # trechos de mensagens de console que o teste provoca de propósito
    yield p
    ctx.close()
    erros = [e for e in erros if not any(x in e for x in p.erros_esperados)]
    assert not erros, erros


def _print(page, nome: str) -> None:
    if PRINTS:
        Path(PRINTS).mkdir(parents=True, exist_ok=True)
        page.wait_for_timeout(200)
        page.screenshot(path=str(Path(PRINTS) / f"{page.nome_teste}_{len(page.prints):02d}_{nome}.png"), full_page=True)
        page.prints.append(nome)


def _guardar_login(base: str) -> None:
    corpo = json.dumps({"cpf": Simulador.CPF, "email": Simulador.EMAIL, "senha": Simulador.SENHA}).encode()
    req = urllib.request.Request(base + "/api/credenciais/sulamerica", data=corpo, method="POST", headers={
        "Content-Type": "application/json", "X-Newport-Tela": "1", "Origin": base})
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.status == 200


def _arquivos_com_login(pasta: Path) -> list[str]:
    """Arquivos em que aparece o CPF (com e sem máscara), o e-mail ou a senha falsos, em UTF-8 ou UTF-16."""
    valores = [Simulador.CPF, "529.982.247-25", Simulador.EMAIL, Simulador.SENHA]
    padroes = [v.encode(cod) for v in valores for cod in ("utf-8", "utf-16-le")]
    arquivos = [pasta] if pasta.is_file() else [a for a in pasta.rglob("*") if a.is_file()]
    return [str(a) for a in arquivos if any(x in _ler(a) for x in padroes)]


def _ler(arquivo: Path) -> bytes:
    """Lê mesmo arquivo que o Chromium acabou de soltar (o Windows trava alguns enquanto ele roda)."""
    fim = time.monotonic() + 20
    while True:
        try:
            return arquivo.read_bytes()
        except FileNotFoundError:   # apagado pelo Chromium ao fechar (lockfile): nada a procurar
            return b""
        except PermissionError:
            if time.monotonic() > fim:
                raise
            time.sleep(0.5)


def _esperar_trabalho(amb, tid: int, timeout_s: int = 120) -> dict:
    fim = time.monotonic() + timeout_s
    while True:
        t = _pedir(amb, "GET", f"/api/trabalhos/{tid}")[1]
        if t["status"] not in ("na_fila", "rodando"):
            return t
        assert time.monotonic() < fim, f"o trabalho {tid} não terminou"
        time.sleep(0.5)


def _menu(page, nome: str):
    return page.locator("nav.menu").get_by_role("link", name=nome, exact=True)


def _grupo_planos(page, acomodacao: str):
    return page.locator(".planos > div").filter(has=page.get_by_role("heading", name=acomodacao))


def _nova_cotacao(page, amb, cnpj: str, vidas: dict[str, int], planos: list[tuple[str, str]], apelido: str = "",
                  congenere: str | None = "NOTREDAME", idades: dict[str, str] | None = None, pasta: str = "") -> None:
    if hasattr(page, "goto"):
        page.goto(amb["base"] + "/#/nova")
        expect(page.get_by_role("heading", name="Nova cotação")).to_be_visible()
    page.get_by_label("CNPJ").fill(cnpj)
    if apelido:
        page.get_by_label("Nome para achar depois").fill(apelido)
    if pasta:
        page.get_by_label("Pasta do cliente").fill(pasta)
    for faixa, qtd in vidas.items():
        for _ in range(qtd):
            page.get_by_role("button", name=f"Somar uma vida na faixa {faixa}").first.click()
    for faixa, texto in (idades or {}).items():
        page.get_by_label(f"Idades na faixa {faixa}").fill(texto)
    if congenere is None:
        page.get_by_text("A empresa não tem plano de saúde hoje").click()
    else:
        page.get_by_label("Operadora atual").fill(congenere)
    for nome, acomodacao in planos:
        _grupo_planos(page, acomodacao).get_by_text(nome, exact=True).click()


def _confirmar(page, botao: str) -> None:
    page.locator(".modal").get_by_role("button", name=botao).click()


def _emitidas(amb, cnpj_digitos: str) -> list[tuple[str, str]]:
    return sorted((c["plano"], c["acomodacao"]) for c in amb["sim"].cotacoes.values() if c["cnpj"] == cnpj_digitos)


def _baixar(page, acao) -> tuple[str, bytes]:
    with page.expect_download() as d:
        acao()
    return d.value.suggested_filename, Path(d.value.path()).read_bytes()


# ---------------------------------------------------------------------------------------------- testes
def test_corretor_ensaia_gera_e_baixa_os_pdfs_sem_reemitir(page, amb):
    _nova_cotacao(page, amb, "11222333000181", {"0 - 18": 1, "34 - 38": 2},
                  [("Especial Mais", "Apartamento"), ("Executivo R1", "Apartamento")],
                  apelido="Padaria do Centro", idades={"0 - 18": "0"}, pasta=str(amb["cliente"]))
    expect(page.get_by_text("3 vidas, 2 cotações na SulAmérica")).to_be_visible()
    _print(page, "nova")

    # ensaio: percorre as telas e não emite
    page.get_by_role("button", name="Ensaiar sem emitir").click()
    expect(page.get_by_role("heading", name="Ensaio concluído")).to_be_visible(timeout=LONGO)
    expect(page.get_by_text("Ensaio ok", exact=True)).to_be_visible()
    expect(page.get_by_text("R$ 2.501,62")).to_be_visible()   # mesmos números do vídeo
    assert _emitidas(amb, "11222333000181") == []
    _print(page, "ensaio")

    # gerar de verdade a partir do ensaio
    page.get_by_role("button", name="Gerar as cotações").click()
    _confirmar(page, "Gerar as cotações")
    expect(page.get_by_role("heading", name="Pronto: 2 cotações emitidas")).to_be_visible(timeout=LONGO)
    assert _emitidas(amb, "11222333000181") == [("Especial Mais", "Apartamento"), ("Executivo R1", "Apartamento")]
    _print(page, "pronto")

    nome, dados = _baixar(page, lambda: page.get_by_role("button", name="Baixar PDF").first.click())
    assert nome in {"SULAMERICA ESPECIAL MAIS.pdf", "SULAMERICA EXECUTIVO.pdf"} and dados.startswith(b"%PDF")
    nome, dados = _baixar(page, lambda: page.get_by_role("button", name="Baixar os 2 PDFs (.zip)").click())
    assert nome.endswith(".zip")
    assert sorted(zipfile.ZipFile(io.BytesIO(dados)).namelist()) == ["SULAMERICA ESPECIAL MAIS.pdf", "SULAMERICA EXECUTIVO.pdf"]
    assert sorted(os.listdir(amb["cliente"])) == ["SULAMERICA ESPECIAL MAIS.pdf", "SULAMERICA EXECUTIVO.pdf"]

    # valores por faixa sem abrir o PDF
    page.get_by_role("button", name="ver por faixa").first.click()
    expect(page.get_by_text("Valor mensal por vida em cada faixa.").first).to_be_visible()

    # a lista de cotações mostra as duas, com PDF
    _menu(page, "Cotações").click()
    expect(page.get_by_role("heading", name="Cotações", exact=True)).to_be_visible()
    expect(page.get_by_text("Emitida", exact=True)).to_have_count(2)
    _print(page, "cotacoes")

    # cotar de novo com os mesmos dados: a tela avisa que já saiu (com o protocolo) e nem manda o robô
    page.goto(amb["base"] + "/#/nova?cnpj=11222333000181")
    expect(page.get_by_label("Nome para achar depois")).to_have_value("Padaria do Centro")
    page.get_by_role("button", name="Gerar 2 cotações").click()
    modal = page.locator(".modal")
    expect(modal.get_by_role("heading", name="Estas cotações já foram emitidas")).to_be_visible()
    expect(modal.get_by_text(re.compile(r"Especial Mais \| Apartamento: protocolo \d+"))).to_be_visible()
    _print(page, "repetido")
    _confirmar(page, "Ver em Cotações")
    expect(page.get_by_role("heading", name="Cotações", exact=True)).to_be_visible()
    assert len(_emitidas(amb, "11222333000181")) == 2
    nome, _ = _baixar(page, lambda: page.get_by_role("button", name="Baixar PDF").first.click())
    assert nome.startswith("SULAMERICA ")   # o PDF da emissão anterior continua a um clique

    # para testar ou mostrar o robô: "Emitir de novo mesmo assim" (duas confirmações) sai com protocolo novo
    page.goto(amb["base"] + "/#/nova?cnpj=11222333000181")
    expect(page.get_by_label("Nome para achar depois")).to_have_value("Padaria do Centro")
    page.get_by_role("button", name="Gerar 2 cotações").click()
    _confirmar(page, "Emitir de novo mesmo assim")
    expect(modal.get_by_role("heading", name="Emitir de novo estas 2 cotações?")).to_be_visible()
    _print(page, "emitir_de_novo")
    _confirmar(page, "Emitir de novo as 2")
    expect(page.get_by_role("heading", name="Pronto: 2 cotações emitidas")).to_be_visible(timeout=LONGO)
    assert len(_emitidas(amb, "11222333000181")) == 4
    tid = int(page.url.rsplit("/", 1)[-1])
    # "Tentar de novo" desse trabalho nunca leva o "emitir de novo": nada sai outra vez
    tela = {"X-Newport-Tela": "1", "Origin": amb["origem"]}
    status, t = _pedir(amb, "POST", f"/api/trabalhos/{tid}/repetir", {"modo": "emitir", "confirmado": True}, tela)
    assert status == 200
    assert _esperar_trabalho(amb, t["id"])["status"] == "concluido"
    assert len(_emitidas(amb, "11222333000181")) == 4
    # e "emitir de novo" só vale para emissão, com protocolos de verdade
    corpo = {"modo": "ensaio", "reemitir": ["1"], "itens": []}
    assert _pedir(amb, "POST", "/api/trabalhos", corpo, tela)[0] == 400


@pytest.fixture()
def page_iframe(amb, request):
    """Tela do RPA dentro de um iframe (como o Benefits 360 embute na aba Cotações)."""
    origem_benefits = amb["benefits_shim"]
    html = (
        f'<!DOCTYPE html><html><body style="margin:0">'
        f'<iframe id="rpa" src="{amb["origem"]}/" '
        f'style="width:1366px;height:900px;border:0"></iframe></body></html>'
    )

    class _PaginaBenefits(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                corpo = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)
            else:
                self.send_error(404)

        def log_message(self, *_args):
            return

    shim = urlparse(origem_benefits)
    servidor = HTTPServer((shim.hostname or "127.0.0.1", shim.port or 80), _PaginaBenefits)
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    ctx = amb["navegador"].new_context(viewport={"width": 1366, "height": 900}, accept_downloads=True, locale="pt-BR")
    parent = ctx.new_page()
    erros: list[str] = []
    parent.on("pageerror", lambda e: erros.append(f"erro de script: {e}"))
    parent.goto(f"{origem_benefits}/", wait_until="domcontentloaded")
    frame = parent.frame_locator("#rpa")
    parent.nome_teste = request.node.name
    try:
        yield parent, frame
    finally:
        servidor.shutdown()
        ctx.close()
    erros = [e for e in erros if e]
    assert not erros, erros


def test_iframe_ensaio_baixa_pdf_como_aba_direta(page, page_iframe, amb):
    """Com frame-ancestors do Benefits, o PDF continua baixando de dentro do iframe."""
    pasta = amb["cliente"] / "iframe_pdf"
    pasta.mkdir(exist_ok=True)
    _nova_cotacao(
        page,
        amb,
        "55667788000186",
        {"0 - 18": 1, "34 - 38": 2},
        [("Especial Mais", "Apartamento")],
        congenere=None,
        idades={"0 - 18": "0"},
        pasta=str(pasta),
    )
    page.get_by_role("button", name="Ensaiar sem emitir").click()
    expect(page.get_by_role("heading", name="Ensaio concluído")).to_be_visible(timeout=LONGO)
    page.get_by_role("button", name="Gerar as cotações").click()
    _confirmar(page, "Gerar as cotações")
    expect(page.get_by_role("heading", name="Pronto: 1 cotação emitida")).to_be_visible(timeout=LONGO)
    nome_direto, _ = _baixar(page, lambda: page.get_by_role("button", name="Baixar PDF").first.click())
    rota_emitida = page.url

    parent, frame = page_iframe
    parent.locator("#rpa").evaluate(f"(el) => {{ el.src = {json.dumps(rota_emitida)}; }}")
    expect(frame.get_by_role("button", name="Baixar PDF").first).to_be_visible(timeout=15_000)
    nome_iframe, dados = _baixar(parent, lambda: frame.get_by_role("button", name="Baixar PDF").first.click())
    assert nome_iframe == nome_direto
    assert nome_iframe.startswith("SULAMERICA ") and dados.startswith(b"%PDF")


def test_com_e_sem_coparticipacao_gera_duas_e_mostra_juntas(page, amb):
    """Padrão da Newport: "Com e sem" = 2 cotações por plano, cada uma com protocolo e PDF próprios."""
    pasta = amb["pasta"] / "cliente_com_e_sem"
    pasta.mkdir()
    _nova_cotacao(page, amb, "33000167000101", {"0 - 18": 1, "34 - 38": 2}, [("Especial Mais", "Apartamento")],
                  idades={"0 - 18": "0"}, pasta=str(pasta))
    expect(page.get_by_role("button", name="Gerar 1 cotação")).to_be_visible()
    page.get_by_role("button", name="Mudar só nesta cotação").click()
    page.get_by_role("group", name="Coparticipação").get_by_role("button", name="Com e sem", exact=True).click()
    expect(page.locator(".frase-robo")).to_contain_text("com e sem coparticipação (2 cotações por plano)")
    expect(page.get_by_text("3 vidas, 2 cotações na SulAmérica")).to_be_visible()
    _print(page, "com_e_sem")
    page.get_by_role("button", name="Gerar 2 cotações").click()
    _confirmar(page, "Gerar 2 cotações")
    expect(page.get_by_role("heading", name="Pronto: 2 cotações emitidas")).to_be_visible(timeout=LONGO)
    linhas = page.locator("table.tabela tbody tr").filter(has_text="Especial Mais")
    expect(linhas).to_have_count(2)
    expect(linhas.nth(0)).to_contain_text("com coparticipação")
    expect(linhas.nth(1)).to_contain_text("sem coparticipação")
    _print(page, "com_e_sem_pronto")
    nome, dados = _baixar(page, lambda: page.get_by_role("button", name="Baixar os 2 PDFs (.zip)").click())
    assert sorted(zipfile.ZipFile(io.BytesIO(dados)).namelist()) == [
        "SULAMERICA ESPECIAL MAIS COM COPARTICIPACAO.pdf", "SULAMERICA ESPECIAL MAIS SEM COPARTICIPACAO.pdf"]
    assert sorted(os.listdir(pasta)) == [
        "SULAMERICA ESPECIAL MAIS COM COPARTICIPACAO.pdf", "SULAMERICA ESPECIAL MAIS SEM COPARTICIPACAO.pdf"]
    coparts = [c["estado"]["filtros"]["copart"] for c in amb["sim"].cotacoes.values() if c["cnpj"] == "33000167000101"]
    assert [x["com"] for x in coparts] == [True, False]

    # "Cotar de novo" com mais um plano: 2 já saíram, 2 são novas. O aviso deixa emitir só as novas (padrão)
    # ou todas de novo (testes e demonstrações), com uma segunda confirmação.
    page.goto(amb["base"] + "/#/nova?cnpj=33000167000101")
    expect(page.get_by_text("3 vidas, 1 cotação na SulAmérica")).to_be_visible()   # o robô deste teste: "com"
    page.get_by_role("button", name="Mudar só nesta cotação").click()
    page.get_by_role("group", name="Coparticipação").get_by_role("button", name="Com e sem", exact=True).click()
    expect(page.get_by_text("3 vidas, 2 cotações na SulAmérica")).to_be_visible()
    _grupo_planos(page, "Apartamento").get_by_text("Executivo R1", exact=True).click()
    page.get_by_role("button", name="Gerar 4 cotações").click()
    modal = page.locator(".modal")
    expect(modal.get_by_role("heading", name="Gerar 2 cotações na SulAmérica?")).to_be_visible()
    expect(modal.get_by_text(re.compile("Já emitidas antes"))).to_be_visible()
    _confirmar(page, "Emitir todas (4)")
    expect(modal.get_by_role("heading", name="Emitir de novo também as 2 que já saíram?")).to_be_visible()
    _confirmar(page, "Emitir as 4")
    # 4 cotações seguidas (cópia entre elas): mais tempo
    expect(page.get_by_role("heading", name="Pronto: 4 cotações emitidas")).to_be_visible(timeout=LONGO * 3)
    assert len([c for c in amb["sim"].cotacoes.values() if c["cnpj"] == "33000167000101"]) == 6


def test_parar_no_meio_e_continuar_sem_duplicar(page, amb):
    planos = [("Direto Nacional", "Enfermaria"), ("Direto Nacional", "Apartamento"), ("Clássico 100", "Enfermaria")]
    _nova_cotacao(page, amb, "45723174000110", {"24 - 28": 3}, planos, congenere=None)
    page.get_by_role("button", name="Gerar 3 cotações").click()
    _confirmar(page, "Gerar 3 cotações")
    expect(page.get_by_text("Emitida", exact=True).first).to_be_visible(timeout=LONGO)
    page.get_by_role("button", name="Parar o robô").click()
    _confirmar(page, "Parar o robô")
    expect(page.get_by_role("heading", name="Parado", exact=True)).to_be_visible(timeout=LONGO)
    expect(page.get_by_text("Parada", exact=True).first).to_be_visible()
    antes = _emitidas(amb, "45723174000110")
    assert 1 <= len(antes) < 3
    _print(page, "parado")

    page.get_by_role("button", name="Continuar de onde parou").click()
    _confirmar(page, "Continuar")
    expect(page.get_by_role("heading", name=f"Pronto: {3 - len(antes)} cotaç", exact=False)).to_be_visible(timeout=LONGO)
    assert _emitidas(amb, "45723174000110") == sorted(planos)   # cada plano uma vez só
    _print(page, "continuado")

    # mesmo plano em duas acomodações: a acomodação entra no nome do PDF
    nome, dados = _baixar(page, lambda: page.get_by_role("button", name="Baixar os 3 PDFs (.zip)").click())
    assert sorted(zipfile.ZipFile(io.BytesIO(dados)).namelist()) == [
        "SULAMERICA CLÁSSICO 100.pdf", "SULAMERICA DIRETO NACIONAL APARTAMENTO.pdf",
        "SULAMERICA DIRETO NACIONAL ENFERMARIA.pdf"]


def test_corretor_configura_o_robo_pela_engrenagem_e_o_robo_obedece(page, amb):
    page.goto(amb["base"] + "/#/inicio")
    page.get_by_role("link", name="Configurar o robô da SulAmérica").first.click()
    expect(page.get_by_role("heading", name="Robô da SulAmérica")).to_be_visible()
    expect(page.get_by_text("Hoje o robô cota assim:")).to_be_visible()
    tela_planos = page.locator("#tela-planos")
    tela_planos.get_by_role("button", name="12 meses", exact=True).click()
    tela_planos.get_by_role("button", name="Sem coparticipação", exact=True).click()
    expect(page.get_by_text("2 mudanças ainda não salvas")).to_be_visible()
    expect(tela_planos.get_by_text("Padrão da Newport: 24 meses.")).to_be_visible()
    _print(page, "configurando")

    # sair sem salvar pede confirmação
    _menu(page, "Início").click()
    expect(page.get_by_role("heading", name="Sair sem salvar?")).to_be_visible()
    page.locator(".modal").get_by_role("button", name="Continuar aqui").click()
    expect(page.get_by_role("heading", name="Robô da SulAmérica")).to_be_visible()

    page.get_by_role("button", name="Salvar configuração").click()
    expect(page.get_by_text("Tudo salvo.")).to_be_visible()
    cfg = json.loads((amb["pasta"] / "saida" / "config_tela.json").read_text(encoding="utf-8"))
    assert cfg["operadoras"]["sulamerica"]["padroes"] == {"vigencia_meses": "12", "coparticipacao": "sem"}

    # a Nova cotação já vem com a configuração do robô, e o robô usa no portal
    _nova_cotacao(page, amb, "12345678000195", {"24 - 28": 2, "29 - 33": 1}, [("Especial Mais", "Apartamento")])
    expect(page.locator(".frase-robo")).to_contain_text("12 meses, sem coparticipação")
    page.get_by_role("button", name="Gerar 1 cotação").click()
    _confirmar(page, "Gerar 1 cotação")
    expect(page.get_by_role("heading", name="Pronto: 1 cotação emitida")).to_be_visible(timeout=LONGO)
    [cot] = [c for c in amb["sim"].cotacoes.values() if c["cnpj"] == "12345678000195"]
    assert cot["estado"]["filtros"]["vig"] == {"12": True, "24": False}
    assert cot["estado"]["filtros"]["copart"] == {"sem": True, "com": False}

    # mudar só nesta cotação não muda a configuração do robô
    _nova_cotacao(page, amb, "98765432000198", {"24 - 28": 3}, [("Especial Mais", "Apartamento")])
    page.get_by_role("button", name="Mudar só nesta cotação").click()
    page.locator(".ajuste-cotacao").get_by_role("button", name="24 meses", exact=True).click()
    expect(page.locator(".frase-robo")).to_contain_text("24 meses")
    expect(page.get_by_text("mudado só nesta cotação")).to_be_visible()
    _print(page, "mudando_so_nesta")
    _menu(page, "Início").click()
    _menu(page, "Nova cotação").click()
    expect(page.locator(".frase-robo")).to_contain_text("12 meses")

    # "Cotar de novo" traz a empresa, as vidas e os planos; o que o robô preenche vem da configuração de hoje
    # (05/11: a coparticipação da cotação antiga vinha junto e o "Com e sem" não valia)
    page.goto(amb["base"] + "/#/nova?cnpj=11222333000181")
    expect(page.get_by_label("Nome para achar depois")).to_have_value("Padaria do Centro")
    expect(page.locator(".frase-robo")).to_contain_text("12 meses, sem coparticipação")
    expect(page.get_by_text("mudado só nesta cotação")).to_have_count(0)

    # voltar aos padrões da Newport
    page.goto(amb["base"] + "/#/robo/sulamerica")
    page.get_by_role("button", name="Voltar aos padrões da Newport").click()
    _confirmar(page, "Voltar aos padrões")
    expect(page.locator(".robo-resumo")).to_contain_text("24 meses, com coparticipação")
    assert "sulamerica" not in json.loads((amb["pasta"] / "saida" / "config_tela.json").read_text(encoding="utf-8")).get("operadoras", {})


def test_importar_planilha_confere_e_ensaia(page, amb, tmp_path):
    from operadoras.sulamerica.planilha import criar_modelo
    planilha = tmp_path / "empresas.xlsx"
    criar_modelo(planilha)
    wb = load_workbook(planilha)
    ws = wb["cotacoes"]
    ruim = [c.value for c in ws[2]]
    ruim[0], ruim[1] = "ERRADA", "11.111.111/1111-11"
    ws.append(ruim)
    wb.save(planilha)

    page.goto(amb["base"] + "/#/importar")
    page.locator("input[type=file]").set_input_files(str(planilha))
    expect(page.get_by_text("1 empresa pronta, 1 linha com problema")).to_be_visible()
    expect(page.get_by_text("Linha 3 (ERRADA)", exact=False)).to_be_visible()
    _print(page, "importada")
    page.get_by_role("button", name="Ensaiar sem emitir").click()
    expect(page.get_by_role("heading", name="Ensaio concluído")).to_be_visible(timeout=LONGO)


def test_pendencia_conferida_no_portal_sai_da_lista_sem_liberar_reemissao(page, amb):
    from nucleo.estado import Estado

    class Pedido:
        id, cnpj = "P9", "24681357000140"

        def assinatura(self):
            return {"teste": True}

    estado = Estado(amb["pasta"] / "saida" / "sulamerica" / "estado.json")
    chave = "24681357000140|executivo r1|apartamento|abc12345"
    estado.registrar(chave, Pedido(), "Executivo R1", "Apartamento", "emitindo", obs="teste")
    page.goto(amb["base"] + "/#/cotacoes")
    expect(page.get_by_role("heading", name="Uma cotação pede conferência no portal")).to_be_visible()
    _print(page, "pendencia")
    page.get_by_role("button", name="Saiu: já tenho o PDF").click()
    _confirmar(page, "Marcar como resolvida")
    expect(page.get_by_role("heading", name="Uma cotação pede conferência no portal")).to_be_hidden()
    item = json.loads((amb["pasta"] / "saida" / "sulamerica" / "estado.json").read_text(encoding="utf-8"))["itens"][chave]
    assert item["status"] == "pdf_ok" and item["resolvido_a_mao"]   # continua bloqueando reemissão


def _pedir(amb, metodo: str, caminho: str, corpo=None, cabecalhos=None) -> tuple[int, dict]:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(amb["base"] + caminho, data=dados, method=metodo,
                                 headers={"Content-Type": "application/json", **(cabecalhos or {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def test_login_pela_engrenagem(page, amb):
    """Sem login guardado o robô nem abre o portal e a tela leva à engrenagem. O CPF é conferido, a senha
    nunca volta para a tela e "Testar login" para na tela de módulos (com a sessão do portal aberta, não entra
    de novo: o portal recusaria um segundo acesso)."""
    sim, tela = amb["sim"], {"X-Newport-Tela": "1", "Origin": amb["origem"]}
    page.goto(amb["base"] + "/#/robo/sulamerica?login=1")
    expect(page.locator(".login-estado")).to_contain_text("Login guardado")
    page.get_by_role("button", name="Apagar credenciais").click()
    _confirmar(page, "Apagar credenciais")
    expect(page.locator(".login-estado")).to_contain_text("Nenhum login guardado")

    requisicoes = sim.requisicoes
    page.erros_esperados.append("status of 409 (Conflict)")   # a tela recusa o pedido sem login
    _nova_cotacao(page, amb, "11444777000161", {"34 - 38": 3}, [("Especial Mais", "Apartamento")])
    page.get_by_role("button", name="Ensaiar sem emitir").click()
    faixa = page.locator("#faixa-login")
    expect(faixa.get_by_text("Cadastre o login da SulAmérica na engrenagem do robô")).to_be_visible()
    assert sim.requisicoes == requisicoes                       # nem abriu o portal
    _print(page, "sem_login")
    faixa.get_by_role("link", name="Abrir a engrenagem").click()

    # a engrenagem desenha exatamente o login que a SulAmérica declara: CPF, e-mail e senha
    rotulos = page.locator(".login-campos label")
    expect(rotulos).to_have_count(3)
    assert [x.strip() for x in rotulos.all_inner_texts()] == ["CPF", "E-mail", "Senha"]
    page.get_by_label("CPF", exact=True).fill("111.111.111-11")
    page.get_by_label("E-mail", exact=True).fill(Simulador.EMAIL)
    page.get_by_label("Senha", exact=True).fill(Simulador.SENHA)
    page.get_by_role("button", name="Guardar", exact=True).click()
    expect(page.get_by_text("CPF inválido: confira os 11 dígitos.")).to_be_visible()
    page.get_by_label("CPF", exact=True).fill(Simulador.CPF)
    page.get_by_role("button", name="Guardar", exact=True).click()
    expect(page.locator(".login-estado")).to_contain_text("Login guardado")
    senha = page.get_by_label("Senha", exact=True)
    expect(senha).to_have_value("")
    expect(senha).to_have_attribute("placeholder", "senha guardada")
    _print(page, "login_guardado")

    status, r = _pedir(amb, "GET", "/api/credenciais/sulamerica")
    assert status == 200 and set(r) == {"guardadas", "email_mascarado", "quando", "recusadas"}
    assert r["email_mascarado"] == "co***@***.local"
    assert Simulador.SENHA not in json.dumps(r) and Simulador.CPF not in json.dumps(r)
    # só a própria tela grava ou apaga o login; erro de validação nunca repete o que foi digitado
    assert _pedir(amb, "POST", "/api/credenciais/sulamerica",
                  {"cpf": Simulador.CPF, "email": "a@b.c", "senha": "x"})[0] == 403
    assert _pedir(amb, "DELETE", "/api/credenciais/sulamerica", None,
                  {"X-Newport-Tela": "1", "Origin": "https://site-qualquer.com"})[0] == 403
    status, r = _pedir(amb, "POST", "/api/credenciais/sulamerica",
                       {"cpf": "98765", "email": "nao-e-email", "senha": "segredo-xyz"}, tela)
    assert status == 400 and "segredo-xyz" not in json.dumps(r) and "98765" not in json.dumps(r)
    comprida = "s" * 17                                         # o campo de senha do portal aceita 16
    status, r = _pedir(amb, "POST", "/api/credenciais/sulamerica",
                       {"cpf": Simulador.CPF, "email": Simulador.EMAIL, "senha": comprida}, tela)
    assert status == 400 and "no máximo 16 caracteres" in r["erro"] and comprida not in json.dumps(r)
    assert _pedir(amb, "GET", "/api/credenciais/sulamerica")[1]["guardadas"] is True   # o anterior ficou

    def testar_login():
        page.goto(amb["base"] + "/#/robo/sulamerica?login=1")
        page.locator("#tela-login").get_by_role("button", name="Testar login").click()
        page.get_by_role("button", name="Acompanhar").click()     # abre o andamento deste teste de login
        expect(page.get_by_role("heading", name="Login ok na SulAmérica")).to_be_visible(timeout=LONGO)

    # o teste prepara a própria sessão: o 1º "Testar login" entra no portal se ainda não houver sessão aberta
    # (rodando sozinho) e não entra se outro teste já abriu (rodando a suíte)
    antes = sim.tentativas_login
    testar_login()
    assert sim.tentativas_login - antes <= 1
    tentativas = sim.tentativas_login
    testar_login()
    assert sim.tentativas_login == tentativas                   # sessão aberta: não entrou de novo


def test_codigo_de_verificacao_pedido_pela_tela(page, amb):
    sim, tela = amb["sim"], {"X-Newport-Tela": "1", "Origin": amb["origem"]}
    sim.exigir_codigo = True
    sim.expirar()                    # a sessão cai: o portal pede o login quando o robô abre o cotador
    try:
        _nova_cotacao(page, amb, "11444777000161", {"34 - 38": 3}, [("Especial Mais", "Apartamento")])
        page.get_by_role("button", name="Ensaiar sem emitir").click()
        faixa = page.locator("#faixa-login")
        expect(faixa.get_by_text("Digite o código que chegou no seu celular/e-mail")).to_be_visible(timeout=LONGO)
        _print(page, "codigo")
        faixa.get_by_label("Digite o código que chegou no seu celular/e-mail").fill(sim.codigo)
        faixa.get_by_role("button", name="Enviar código").click()
        expect(page.get_by_role("heading", name="Ensaio concluído")).to_be_visible(timeout=LONGO)
        assert _pedir(amb, "POST", "/api/codigo/sulamerica", {"codigo": "123456"}, tela)[0] == 409   # ninguém espera
    finally:
        sim.exigir_codigo = False


def test_a_tela_nunca_roda_javascript_velho(amb):
    """A UI velha não é mais servida: `/` e `/static/...` apontam para o Benefits (5173)."""
    aviso = "Use o Benefits (http://localhost:5173), aba Cotações."
    with urllib.request.urlopen(amb["base"] + "/", timeout=10) as r:
        html = r.read().decode("utf-8")
        assert r.headers.get("Cache-Control") == "no-cache"
        assert aviso in html
        assert "js/telas/nova.js" not in html
    with urllib.request.urlopen(amb["base"] + "/static/js/telas/nova.js", timeout=10) as r:
        assert r.status == 200 and r.headers.get("Cache-Control") == "no-cache"
        assert aviso in r.read().decode("utf-8")
    status, estado = _pedir(amb, "GET", "/api/estado")
    assert status == 200 and "versao" in estado


def test_api_recusa_pedidos_que_nao_vem_da_tela(amb):
    tela = {"X-Newport-Tela": "1", "Origin": amb["origem"]}
    corpo = {"modo": "ensaio", "itens": []}
    assert _pedir(amb, "POST", "/api/trabalhos", corpo)[0] == 403                     # sem o cabeçalho da tela
    assert _pedir(amb, "POST", "/api/trabalhos", corpo,
                  {"X-Newport-Tela": "1", "Origin": "https://site-qualquer.com"})[0] == 403   # outro site
    # Benefits na allowlist pode mutar (com o cabeçalho); sem itens → 400, não 403
    assert _pedir(amb, "POST", "/api/trabalhos", corpo,
                  {"X-Newport-Tela": "1", "Origin": "http://127.0.0.1:5173"})[0] == 400
    assert _pedir(amb, "POST", "/api/trabalhos", {"modo": "emitir", "itens": []}, tela)[0] == 400   # sem confirmar
    assert _pedir(amb, "GET", "/api/cotacoes/999999/pdf")[0] == 404
    status, r = _pedir(amb, "PUT", "/api/robos/sulamerica",
                       {"valores": {"arquivos.nome_pdf_destino": "SULAMERICA.pdf"}}, tela)
    assert status == 400 and "plano_arquivo" in r["erro"]
    assert _pedir(amb, "PUT", "/api/robos/sulamerica", {"valores": {"padroes.vigencia_meses": "36"}}, tela)[0] == 400
    # a tela só grava os campos que a operadora declara (nunca a pasta do registro anti-reemissão ou a URL)
    for chave in ("arquivos.pasta", "urls.login", "conferencias.aliquota_iof"):
        status, r = _pedir(amb, "PUT", "/api/robos/sulamerica", {"valores": {chave: "x"}}, tela)
        assert status == 400 and "desconhecido" in r["erro"], chave
    ajustes = amb["pasta"] / "saida" / "config_tela.json"
    assert not ajustes.exists() or "urls" not in ajustes.read_text(encoding="utf-8")
    # outro nome apontando para 127.0.0.1 (DNS rebinding) não lê nada
    assert _pedir(amb, "GET", "/api/cotacoes", cabecalhos={"Host": "site-qualquer.com"})[0] == 421
    # só o Benefits (frame_ancestors no config) pode embutir; site arbitrário não entra na allowlist
    with urllib.request.urlopen(amb["base"] + "/", timeout=10) as resp:
        csp = resp.headers["Content-Security-Policy"]
        assert "frame-ancestors" in csp
        assert "http://localhost:5173" in csp
        assert "http://127.0.0.1:5173" in csp
        assert "https://site-malicioso.exemplo" not in csp
        assert resp.headers.get("X-Frame-Options") != "DENY"


def test_linha_de_comando_nao_roda_enquanto_a_tela_esta_com_o_portal_aberto(amb, tmp_path):
    from operadoras.sulamerica.planilha import criar_modelo
    tela = {"X-Newport-Tela": "1", "Origin": amb["origem"]}
    assert _pedir(amb, "POST", "/api/conectar/sulamerica", {}, tela)[0] == 200
    fim = time.monotonic() + 60
    while _pedir(amb, "GET", "/api/estado")[1]["robo"]["conexao"].get("sulamerica") != "conectado":
        assert time.monotonic() < fim, "a tela não conectou ao simulador"
        time.sleep(0.5)
    planilha = tmp_path / "p.xlsx"
    criar_modelo(planilha)
    r = subprocess.run([sys.executable, "main.py", "--config", str(amb["pasta"] / "config.yaml"),
                        "--planilha", str(planilha), "--ensaio"], cwd=RAIZ, capture_output=True,
                       encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=120)
    assert r.returncode == 4, r.stdout + r.stderr
    assert "já existe um robô rodando" in r.stdout


def test_sair_do_portal_agora_pelo_cartao(page, amb):
    """O corretor libera o CPF na hora: o robô sai do portal (logout) e fecha a janela; o cartão volta a
    "Desconectado" e a próxima cotação entra sozinha de novo."""
    page.goto(amb["base"] + "/#/")
    cartao = page.locator("#conexoes .conexao").first
    testar = cartao.get_by_role("button", name="Testar login")
    if testar.is_visible():
        testar.click()
    botao = cartao.get_by_role("button", name="Sair do portal agora")
    expect(botao).to_be_enabled(timeout=LONGO)
    antes = amb["sim"].saidas
    _print(page, "sair_do_portal")
    botao.click()
    expect(cartao).to_contain_text("Desconectado", timeout=30000)
    expect(cartao.get_by_role("button", name="Testar login")).to_be_visible()
    assert amb["sim"].saidas == antes + 1


def test_nenhum_arquivo_nem_a_saida_do_servidor_tem_o_login(page, amb):
    """Rodada completa com prints de cada tela e o portal pedindo login de novo no meio do pedido: o CPF,
    o e-mail e a senha falsos não aparecem em nenhum arquivo de saida/ (tela.db, logs, mapa, registro,
    resultados, perfil do navegador) nem na saída do servidor."""
    sim, tela = amb["sim"], {"X-Newport-Tela": "1", "Origin": amb["origem"]}
    assert _pedir(amb, "PUT", "/api/geral", {"geral": {"mapear": True}}, tela)[0] == 200
    sim.expirar()                            # o robô digita o login no começo...
    sim.expirar_apos_download = True         # ...e de novo depois do 1º PDF
    tentativas = sim.tentativas_login
    try:
        _nova_cotacao(page, amb, "55667788000186", {"0 - 18": 1, "34 - 38": 2},
                      [("Especial Mais", "Apartamento"), ("Executivo R1", "Apartamento")], idades={"0 - 18": "0"})
        page.get_by_role("button", name="Gerar 2 cotações").click()
        _confirmar(page, "Gerar 2 cotações")
        expect(page.get_by_role("heading", name="Pronto: 2 cotações emitidas")).to_be_visible(timeout=LONGO)
    finally:
        _pedir(amb, "PUT", "/api/geral", {"geral": {"mapear": False}}, tela)
    assert sim.tentativas_login == tentativas + 2
    assert list((amb["pasta"] / "saida" / "sulamerica" / "mapa").rglob("*.aria.txt"))   # os prints existem
    page.goto("about:blank")                 # sai da tela antes de fechá-la (sem erro de conexão no console)
    amb["proc"].terminate()                  # último teste: fecha a tela (e o navegador do robô solta o perfil)
    amb["proc"].wait(timeout=15)
    trava = amb["pasta"] / "saida" / "sulamerica" / "perfil_navegador" / "lockfile"
    fim = time.monotonic() + 20
    while trava.exists() and time.monotonic() < fim:
        time.sleep(0.5)
    assert _arquivos_com_login(amb["pasta"] / "saida") == []
    assert _arquivos_com_login(amb["pasta"] / "tela.log") == []
