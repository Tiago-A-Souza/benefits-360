"""API da tela com a Porto: login no cofre (sem devolver senha) e operadora desmarcada (só ensaio)."""
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

from operadoras.porto.simulador.servidor import Simulador

RAIZ = Path(__file__).resolve().parents[2]


def _porta_livre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


@pytest.fixture(scope="module")
def amb(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("tela_porto")
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
  porto:
    urls:
      login: "{sim.url_login}"
      cotador: "{sim.url_home}"
    emissao_liberada: false
    tempos:
      sair_do_portal_min: 0
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
    yield {"base": f"http://127.0.0.1:{porta}", "origem": f"http://127.0.0.1:{porta}", "sim": sim}
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()
    sim.parar()


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


def test_api_lista_a_porto_desmarcada_com_cpf_e_senha(amb):
    status, ops = _pedir(amb, "GET", "/api/operadoras")
    assert status == 200
    porto = next(o for o in ops if o["id"] == "porto")
    assert porto["nome"] == "Porto Seguro"
    texto = json.dumps(porto)
    assert "cpf" in texto.lower() and "senha" in texto.lower()
    assert "Gerar orçamento" in texto or "gerar" in texto.lower()
    assert Simulador.SENHA not in texto


def test_cofre_guarda_o_login_e_nao_devolve_a_senha(amb):
    status, _ = _pedir(amb, "POST", "/api/credenciais/porto",
                       {"cpf": Simulador.CPF, "senha": Simulador.SENHA}, tela=True)
    assert status == 200
    status, r = _pedir(amb, "GET", "/api/credenciais/porto")
    assert status == 200 and r["guardadas"] is True
    bruto = json.dumps(r)
    assert Simulador.SENHA not in bruto
    assert "Treino#" not in bruto
