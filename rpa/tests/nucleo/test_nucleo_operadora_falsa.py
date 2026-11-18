"""Núcleo e tela com uma operadora falsa mínima: nenhuma operadora de verdade entra aqui."""
import asyncio
import json
from pathlib import Path
import logging
from decimal import Decimal

import pytest
from starlette.requests import Request

import operadoras

FALSA = ("falsa", "Operadora Falsa", "tests.nucleo.operadora_falsa", "OperadoraFalsa")
QUEBRADA = ("quebrada", "Quebrada", "operadoras.nao_existe", "Classe")
FALSA2 = ("falsa2", "Outra Operadora Falsa", "tests.nucleo.operadora_falsa", "OutraOperadoraFalsa")
CNPJ = "11.222.333/0001-81"


@pytest.fixture()
def registro():
    """Troca o registro das operadoras pelo do teste e devolve o de verdade no fim."""
    def carregar(*itens):
        operadoras._carregar(list(itens))
    yield carregar
    operadoras._carregar()


def _config(tmp_path, *ids):
    linhas = ["geral:", "  pasta_saida: saida", "teste:", "  cofre: memoria", "operadoras:"] + [f"  {i}: {{}}" for i in ids]
    (tmp_path / "config.yaml").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return tmp_path / "config.yaml"


def _get(rota):
    pedido = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""})
    return json.loads(asyncio.run(rota(pedido)).body)


def test_operadora_que_falha_ao_carregar_fica_indisponivel_e_a_tela_abre(tmp_path, registro):
    from app.servidor import Tela

    registro(QUEBRADA, FALSA)
    assert [o.id for o in operadoras.todas()] == ["falsa"]
    [ind] = operadoras.indisponiveis()
    assert (ind["id"], ind["nome"]) == ("quebrada", "Quebrada") and "ModuleNotFoundError" in ind["motivo"]
    with pytest.raises(KeyError, match="indisponível"):
        operadoras.obter("quebrada")
    tela = Tela(_config(tmp_path, "falsa", "quebrada"), 0)
    assert [d["id"] for d in _get(tela.estado)["operadoras_indisponiveis"]] == ["quebrada"]
    [op] = _get(tela.lista_operadoras)                       # a outra operadora segue normal
    assert op["id"] == "falsa" and op["versoes"] == {"a": "versão A", "b": "versão B"} and op["textos"] == {}


def test_operadora_que_quebra_ao_montar_o_formulario_nao_derruba_a_tela(tmp_path, registro, monkeypatch):
    from app.servidor import Tela

    registro(FALSA)
    monkeypatch.setattr(type(operadoras.obter("falsa")), "campos", lambda self, cfg: 1 / 0)
    tela = Tela(_config(tmp_path, "falsa"), 0)
    assert _get(tela.lista_operadoras) == []
    [ind] = _get(tela.estado)["operadoras_indisponiveis"]
    assert ind["id"] == "falsa" and "ZeroDivisionError" in ind["motivo"]


def test_raiz_nao_serve_a_ui_velha(tmp_path, registro):
    """`/` e `/static` respondem o aviso do motor; a API /api/estado segue igual."""
    from app.servidor import Tela

    registro(FALSA)
    tela = Tela(_config(tmp_path, "falsa"), 0)
    pedido = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""})
    html = asyncio.run(tela.inicio(pedido)).body.decode()
    assert "Motor do robô de cotações em execução" in html
    assert "Use o Benefits (http://localhost:5173), aba Cotações." in html
    html_static = asyncio.run(tela.pagina_motor(pedido)).body.decode()
    assert "Use o Benefits (http://localhost:5173), aba Cotações." in html_static
    estado = _get(tela.estado)
    assert "versao" in estado and "robo" in estado


def test_estado_da_tela_diz_o_commit_que_esta_rodando(tmp_path, registro):
    """O rodapé da tela mostra o commit (e o aviso de reiniciar) que vem de /api/estado."""
    import subprocess

    from app.servidor import WEB, Tela

    registro(FALSA)
    tela = Tela(_config(tmp_path, "falsa"), 0)
    raiz = Path(__file__).resolve().parents[2]
    git = subprocess.run(["git", "-C", str(raiz), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    codigo = _get(tela.estado)["codigo"]
    assert set(codigo) == {"commit", "quando", "mais_novo_no_disco"}
    if git.returncode == 0:
        assert codigo["commit"] == git.stdout.strip()
    assert 'id="versao-codigo"' in (WEB / "index.html").read_text(encoding="utf-8")


def test_emitir_de_novo_aceita_protocolo_com_prefixo_e_recusa_lixo(tmp_path, registro):
    """12/11: o servidor só aceitava protocolo de dígitos e recusava o "COT-5291608" da Amil ("protocolos inválidos")."""
    from app.servidor import Tela

    registro(FALSA)
    tela = Tela(_config(tmp_path, "falsa"), 0)

    def pedir(reemitir, modo="emitir"):
        corpo = json.dumps({"modo": modo, "confirmado": True, "reemitir": reemitir, "itens": []}).encode()
        sobra = [False]

        async def receber():
            if sobra[0]:
                return {"type": "http.disconnect"}
            sobra[0] = True
            return {"type": "http.request", "body": corpo, "more_body": False}
        pedido = Request({"type": "http", "method": "POST", "path": "/api/trabalhos", "headers": [], "query_string": b""}, receber)
        resp = asyncio.run(tela.criar_trabalho(pedido))
        return resp.status_code, json.loads(resp.body)

    for bom in (["5291608"], ["COT-5291608"], ["OPP-5228962", "COT-5291608"]):
        status, corpo = pedir(bom)
        assert corpo.get("erro") != "protocolos inválidos", bom          # passa da validação (falha depois: sem pedidos)
    for ruim in (["COT-5291608; x"], ["../x"], [""], [5291608], "COT-5291608", ["COT 5291608"]):
        assert pedir(ruim) == (400, {"erro": "protocolos inválidos"}), ruim
    assert pedir(["COT-5291608"], modo="ensaio") == (400, {"erro": "emitir de novo só vale para emissão"})


def test_cofre_usa_os_campos_que_a_operadora_declara(registro):
    from nucleo.credenciais import Cofre, CofreMemoria, ErroCredencial

    registro(FALSA)
    CofreMemoria.esvaziar()
    cofre = Cofre("falsa", memoria=True)
    assert cofre.servico == "NewportCotacoes/falsa"                  # um serviço por operadora
    assert [c["chave"] for c in cofre.campos] == ["usuario", "senha"]
    with pytest.raises(ErroCredencial) as e:
        cofre.guardar(usuario="", senha="")
    assert e.value.problemas == ["Digite usuário", "Digite a senha"]
    cofre.guardar(usuario="corretor.falso", senha="senha-falsa-1")
    assert cofre.situacao() == {"guardadas": True, "quando": cofre.situacao()["quando"], "recusadas": False}
    cofre.marcar_recusadas()
    cofre.guardar(usuario="corretor.falso", senha="")                # sem digitar a senha: continua recusado
    assert cofre.situacao()["recusadas"] is True
    CofreMemoria.esvaziar()


def test_resultados_com_o_nome_que_a_operadora_da_a_versao(tmp_path, registro):
    from openpyxl import load_workbook

    from nucleo.modelo import PlanoVisto, ResultadoPlano

    registro(FALSA)
    r = operadoras.obter("falsa").resultados(tmp_path / "resultados.xlsx", logging.getLogger("teste"))
    r.plano(ResultadoPlano(pedido_id="P1", linha=1, cnpj="11222333000181", plano="Plano A", status="OK", versao="a"))
    r.precos("P1", "11222333000181", [PlanoVisto("Plano A", "Enfermaria", Decimal("10.00"), versao="A")])
    wb = load_workbook(tmp_path / "resultados.xlsx")
    assert wb.sheetnames == ["cotacoes", "precos_planos", "erros_planilha"]
    cabecalho = [c.value for c in wb["cotacoes"][1]]
    assert cabecalho[-1] == "variante" and wb["cotacoes"].cell(2, len(cabecalho)).value == "a"
    assert [c.value for c in wb["precos_planos"][1]][6] == "variante"


def test_nome_do_pdf_e_versao_sem_texto_de_operadora():
    from nucleo.modelo import PlanoAlvo
    from nucleo.saidas import nome_pdf_arquivo, nome_pdf_destino

    assert nome_pdf_arquivo({}, "1", "2", "Plano A") == "COTACAO_1_2.pdf"
    assert nome_pdf_destino({}, "1", "2", "Plano A") == "COTACAO PLANO A.pdf"
    assert nome_pdf_destino({}, "1", "2", "Plano A", versao="VERSAO B") == "COTACAO PLANO A VERSAO B.pdf"
    alvo = PlanoAlvo("Plano A", "Enfermaria", versao="b", versao_texto="versão B")
    assert alvo.rotulo() == "Plano A | Enfermaria" and alvo.rotulo_completo() == "Plano A | Enfermaria | versão B"


def test_registro_anti_reemissao_com_o_pedido_da_operadora_falsa(tmp_path, registro):
    from nucleo.estado import Estado

    registro(FALSA)
    p = operadoras.obter("falsa").montar_pedido({"cnpj": "11.222.333/0001-81", "planos": "Plano A"}, {}, 1)
    est = Estado(tmp_path / "estado.json")
    k = est.chave(p, "Plano A", "Enfermaria")
    assert est.procurar(p, p.planos[0]) is None and est.pode_emitir(k)
    est.registrar(k, p, "Plano A", "Enfermaria", "emitindo")
    assert not Estado(tmp_path / "estado.json").pode_emitir(k)       # persiste em disco
    assert est.procurar(p, p.planos[0])[0] == k


# ---------- um robô por operadora: thread, fila, janela, trava e log de cada uma ----------

class _Bus:
    def __init__(self):
        self.eventos = []

    def publicar(self, evento):
        self.eventos.append(evento)


def _trabalhador(tmp_path, *ids):
    from app.banco import Banco
    from app.trabalhador import Trabalhador
    from nucleo.credenciais import Cofre, CofreMemoria
    from nucleo.registro import carregar_config

    caminho = _config(tmp_path, *ids)
    banco, bus = Banco(tmp_path / "saida" / "tela.db"), _Bus()
    CofreMemoria.esvaziar()
    for op_id in ids:                       # o login falso de cada operadora, só no cofre de memória
        login = {"documento": "11.222.333/0001-81"} if op_id == "falsa2" else {"usuario": "corretor.falso"}
        Cofre(op_id, memoria=True).guardar(senha="senha-falsa-1", **login)
    robo = Trabalhador(lambda: carregar_config(caminho), banco, bus)
    robo.start()
    return robo, banco, bus


def _pedido(banco, robo, partes):
    itens = [{"operadora": op_id, "pedidos": pedidos} for op_id, pedidos in partes.items()]
    n = sum(len(p) for p in partes.values())
    tid = banco.novo_trabalho("cotar", "emitir", "teste", n, n, itens)
    robo.enfileirar({"id": tid, "tipo": "cotar", "modo": "emitir", "titulo": "teste", "itens": itens})
    return tid


def _esperar(condicao, segundos):
    import time
    fim = time.monotonic() + segundos
    while not condicao():
        assert time.monotonic() < fim, "não aconteceu a tempo"
        time.sleep(0.2)


def _log(tmp_path, op_id):
    return "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "saida" / op_id / "logs").glob("*.log"))


def test_um_robo_travado_nao_segura_o_de_outra_operadora(tmp_path, registro):
    registro(FALSA, FALSA2)
    robo, banco, _ = _trabalhador(tmp_path, "falsa", "falsa2")
    try:
        travado = _pedido(banco, robo, {"falsa": [{"cnpj": CNPJ, "espera_s": 300}]})
        rapido = _pedido(banco, robo, {"falsa2": [{"cnpj": CNPJ}]})
        _esperar(lambda: banco.trabalho(rapido)["status"] == "concluido", 60)
        assert banco.trabalho(travado)["status"] == "rodando"          # o outro robô continua no "portal"
        assert [c["operadora"] for c in banco.cotacoes(trabalho=rapido)] == ["falsa2"]
        assert set(robo.navegadores) == {"falsa", "falsa2"}            # uma janela (e uma trava) por operadora
        assert robo.registro_livre("falsa2", tmp_path / "saida" / "falsa2")   # o parado está livre
        assert not robo.registro_livre("falsa", tmp_path / "saida" / "falsa")
        assert robo.cancelar(travado)                                  # Parar
        _esperar(lambda: banco.trabalho(travado)["status"] == "cancelado", 30)
        log_falsa, log_falsa2 = _log(tmp_path, "falsa"), _log(tmp_path, "falsa2")   # um log por operadora
        assert "cotando na Operadora Falsa" in log_falsa and "Outra Operadora Falsa" not in log_falsa
        assert "cotando na Outra Operadora Falsa" in log_falsa2 and "cotando na Operadora Falsa" not in log_falsa2
    finally:
        robo.encerrar()
        robo.join(30)


def test_pedido_com_duas_operadoras_so_conclui_quando_as_duas_terminam(tmp_path, registro):
    registro(FALSA, FALSA2)
    robo, banco, bus = _trabalhador(tmp_path, "falsa", "falsa2")
    try:
        tid = _pedido(banco, robo, {"falsa": [{"cnpj": CNPJ, "espera_s": 6}], "falsa2": [{"cnpj": CNPJ}]})
        _esperar(lambda: [c["operadora"] for c in banco.cotacoes(trabalho=tid)] == ["falsa2"], 60)
        assert banco.trabalho(tid)["status"] == "rodando"              # a outra operadora ainda não terminou
        _esperar(lambda: banco.trabalho(tid)["status"] == "concluido", 60)
        assert sorted(c["operadora"] for c in banco.cotacoes(trabalho=tid)) == ["falsa", "falsa2"]
        assert [e["status"] for e in bus.eventos if e["tipo"] == "trabalho" and e["trabalho"] == tid] == [
            "na_fila", "rodando", "concluido"]
    finally:
        robo.encerrar()
        robo.join(30)


def test_cada_operadora_guarda_o_seu_login_sem_mexer_no_da_outra(registro):
    """Cada operadora declara os seus campos e tem o seu serviço no cofre (NewportCotacoes/<operadora>)."""
    from nucleo.credenciais import Cofre, CofreMemoria, ErroCredencial

    registro(FALSA, FALSA2)
    CofreMemoria.esvaziar()
    um, outro = Cofre("falsa", memoria=True), Cofre("falsa2", memoria=True)
    assert [c["chave"] for c in outro.campos] == ["documento", "senha"]
    with pytest.raises(ErroCredencial, match="CPF/CNPJ inválido"):
        outro.guardar(documento="11.111.111/1111-11", senha="senha-falsa-2")
    um.guardar(usuario="corretor.falso", senha="senha-falsa-1")
    outro.guardar(documento="11.222.333/0001-81", senha="senha-falsa-2")     # CNPJ
    assert um.ler() == {"usuario": "corretor.falso", "senha": "senha-falsa-1", "quando": um.ler()["quando"]}
    assert outro.ler()["documento"] == "11222333000181" and outro.ler()["senha"] == "senha-falsa-2"
    outro.guardar(documento="529.982.247-25", senha="")                      # CPF; senha vazia mantém a guardada
    assert outro.ler()["documento"] == "52998224725" and outro.ler()["senha"] == "senha-falsa-2"
    outro.apagar()
    assert not outro.situacao()["guardadas"] and um.situacao()["guardadas"]   # apagar uma não mexe na outra
    assert um.ler()["senha"] == "senha-falsa-1"
    CofreMemoria.esvaziar()
