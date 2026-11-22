"""CORS + origens_permitidas: Benefits chama a API; site estranho não."""
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

from app.servidor import (
    _cabecalhos_cors,
    _origens_permitidas,
    SoDaPropriaTela,
)

RAIZ = Path(__file__).resolve().parents[2]


def test_origens_permitidas_vem_do_config(monkeypatch):
    monkeypatch.delenv("NEWPORT_RPA_ORIGENS", raising=False)
    monkeypatch.delenv("BENEFITS_ORIGENS", raising=False)
    cfg = {"tela": {"origens_permitidas": ["http://localhost:5173", "http://app.exemplo"]}}
    assert _origens_permitidas(cfg) == ["http://localhost:5173", "http://app.exemplo"]
    assert _origens_permitidas({}) == []


def test_origens_permitidas_aceitam_env(monkeypatch):
    monkeypatch.setenv("NEWPORT_RPA_ORIGENS", "https://piloto.up.railway.app, https://outro.exemplo/")
    cfg = {"tela": {"origens_permitidas": ["http://localhost:5173"]}}
    assert _origens_permitidas(cfg) == [
        "http://localhost:5173",
        "https://piloto.up.railway.app",
        "https://outro.exemplo",
    ]


def test_cabecalhos_cors_preflight_com_pna():
    h = dict(_cabecalhos_cors("http://127.0.0.1:5173", preflight=True, private_network=True))
    assert h[b"access-control-allow-origin"] == b"http://127.0.0.1:5173"
    assert b"x-newport-tela" in h[b"access-control-allow-headers"]
    assert h[b"access-control-allow-private-network"] == b"true"


def test_mutacao_ok_inclui_propria_e_cors():
    mw = SoDaPropriaTela(lambda *a: None, porta=8600, origens_permitidas=["http://127.0.0.1:5173"])
    assert "http://127.0.0.1:8600" in mw.mutacao_ok
    assert "http://127.0.0.1:5173" in mw.mutacao_ok
    assert "https://site-malicioso.exemplo" not in mw.mutacao_ok


def _porta() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _pedir(base: str, metodo: str, caminho: str, corpo=None, cabecalhos=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    hdrs = dict(cabecalhos or {})
    if corpo is not None and "Content-Type" not in hdrs:
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(base + caminho, data=dados, method=metodo, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            # chaves em minúsculas: dict(HTTPMessage) perde o get case-insensitive
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


@pytest.fixture(scope="module")
def tela_cors(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("cors")
    porta = _porta()
    (pasta / "config.yaml").write_text(
        f"""
geral:
  pasta_saida: "saida"
  modo_visual: false
  lentidao_ms: 0
  pausa_entre_pedidos_s: 0
tela:
  porta: {porta}
  frame_ancestors:
    - http://127.0.0.1:5173
  origens_permitidas:
    - http://127.0.0.1:5173
    - http://localhost:5173
teste:
  simulador: true
  cofre: memoria
operadoras: {{}}
""",
        encoding="utf-8",
    )
    log = open(pasta / "tela.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "app", "--config", str(pasta / "config.yaml"), "--sem-navegador"],
        cwd=RAIZ,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", porta), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.15)
    else:
        proc.kill()
        pytest.fail("tela CORS não subiu: " + (pasta / "tela.log").read_text(encoding="utf-8"))
    base = f"http://127.0.0.1:{porta}"
    yield {"base": base, "origem": base, "proc": proc, "pasta": pasta}
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()


def test_origem_permitida_passa_get_com_cors(tela_cors):
    status, heads, corpo = _pedir(
        tela_cors["base"], "GET", "/api/estado", cabecalhos={"Origin": "http://127.0.0.1:5173"}
    )
    assert status == 200
    assert heads.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert json.loads(corpo).get("versao")


def test_origem_estranha_sem_cors_em_get(tela_cors):
    status, heads, _ = _pedir(
        tela_cors["base"], "GET", "/api/estado", cabecalhos={"Origin": "https://site-malicioso.exemplo"}
    )
    assert status == 200
    assert heads.get("access-control-allow-origin") is None


def test_mutacao_origem_estranha_barrada(tela_cors):
    status, _, _ = _pedir(
        tela_cors["base"],
        "POST",
        "/api/validar",
        {"itens": []},
        {"X-Newport-Tela": "1", "Origin": "https://site-malicioso.exemplo"},
    )
    assert status == 403


def test_mutacao_sem_x_newport_tela_barrada(tela_cors):
    status, _, _ = _pedir(
        tela_cors["base"],
        "POST",
        "/api/validar",
        {"itens": []},
        {"Origin": "http://127.0.0.1:5173"},
    )
    assert status == 403


def test_host_estranho_barrado(tela_cors):
    status, _, _ = _pedir(
        tela_cors["base"], "GET", "/api/estado", cabecalhos={"Host": "site-qualquer.com"}
    )
    assert status == 421


def test_preflight_origem_permitida(tela_cors):
    status, heads, _ = _pedir(
        tela_cors["base"],
        "OPTIONS",
        "/api/validar",
        cabecalhos={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-newport-tela",
            "Access-Control-Request-Private-Network": "true",
        },
    )
    assert status == 204
    assert heads.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert "x-newport-tela" in (heads.get("access-control-allow-headers") or "").lower()
    assert heads.get("access-control-allow-private-network") == "true"


def test_preflight_origem_estranha_barrada(tela_cors):
    status, heads, _ = _pedir(
        tela_cors["base"],
        "OPTIONS",
        "/api/estado",
        cabecalhos={"Origin": "https://site-malicioso.exemplo", "Access-Control-Request-Method": "GET"},
    )
    assert status == 403
    assert heads.get("access-control-allow-origin") is None


def test_sse_aceita_origem_permitida(tela_cors):
    import http.client
    from urllib.parse import urlparse

    u = urlparse(tela_cors["base"])
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=5)
    try:
        conn.request("GET", "/api/eventos", headers={"Origin": "http://127.0.0.1:5173"})
        r = conn.getresponse()
        assert r.status == 200
        assert r.getheader("Access-Control-Allow-Origin") == "http://127.0.0.1:5173"
        assert "text/event-stream" in (r.getheader("Content-Type") or "")
    finally:
        conn.close()
