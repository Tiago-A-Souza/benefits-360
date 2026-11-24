"""Núcleo: as partes que não dependem do navegador nem de operadora nenhuma."""
from decimal import Decimal

import pytest

from nucleo.texto import cnpj_valido, dinheiro


def test_dinheiro():
    assert dinheiro("R$ 1.144,03 / mês") == Decimal("1144.03")
    assert dinheiro("R$ 0") == Decimal("0.00")
    assert dinheiro("R$ 1144,03") == Decimal("1144.03")
    assert dinheiro("R$\n2.443,46") == Decimal("2443.46")
    assert dinheiro("sem preço") is None


def test_cnpj():
    assert cnpj_valido("11.222.333/0001-81")
    assert not cnpj_valido("11.222.333/0001-82")
    assert not cnpj_valido("11111111111111")


def test_login_com_espaco_no_comeco_ou_no_fim_nao_e_cortado():
    """A tela pergunta antes; o cofre guarda como veio (não tira espaço sozinho)."""
    from nucleo.credenciais import Cofre, CofreMemoria
    CofreMemoria.esvaziar()
    cofre = Cofre("teste_espaco", memoria=True)
    cofre.guardar("52998224725", " corretor@exemplo.com ", "senha com espaço ")
    assert cofre.situacao()["guardadas"]
    CofreMemoria.esvaziar()


def test_trava_impede_dois_robos(tmp_path):
    from nucleo.trava import OcupadoErro, Trava
    with Trava(tmp_path):
        with pytest.raises(OcupadoErro):
            with Trava(tmp_path):
                pass
    with Trava(tmp_path):      # liberou ao sair
        pass


def test_concluir_a_mao_mantem_bloqueio_de_reemissao(tmp_path):
    from nucleo.estado import Estado

    class P:
        id, cnpj = "X", "11222333000181"

    e = Estado(tmp_path / "estado.json")
    e.registrar("k", P, "Executivo R1", "Apartamento", "emitindo")
    assert e.concluir_manual("k", "conferido no portal")
    assert e.item("k")["status"] == "pdf_ok" and not e.pendencias()
    assert not e.concluir_manual("k", "de novo")   # só pendências podem ser resolvidas à mão


def test_dois_processos_no_mesmo_registro_nao_apagam_um_ao_outro(tmp_path):
    from nucleo.estado import Estado

    class P:
        id, cnpj = "X", "11222333000181"

        def assinatura(self):
            return "mesma"

    a = Estado(tmp_path / "estado.json")   # a linha de comando abriu o registro...
    b = Estado(tmp_path / "estado.json")   # ...e a tela também
    a.registrar("k1", P(), "Especial Mais", "Apartamento", "emitindo")
    assert not b.pode_emitir("k1")          # b enxerga a gravação de a sem reabrir o arquivo
    b.registrar("k2", P(), "Executivo R1", "Apartamento", "emitindo")
    assert set(Estado(tmp_path / "estado.json").dados["itens"]) == {"k1", "k2"}   # nada se perdeu
    assert b.concluir_manual("k1", "conferido")
    a.registrar("k2", P(), "Executivo R1", "Apartamento", "emitida", protocolo="9")
    final = Estado(tmp_path / "estado.json").dados["itens"]
    assert final["k1"]["status"] == "pdf_ok" and final["k2"]["status"] == "emitida"
    assert not list(tmp_path.glob("*.tmp"))


def test_cofre_confere_cpf_e_tamanho_da_senha_sem_repetir_o_valor():
    from nucleo.credenciais import Cofre, CofreMemoria, ErroCredencial, registrar_campos
    CofreMemoria.esvaziar()
    registrar_campos("teste", [{"chave": "cpf", "tipo": "cpf"}, {"chave": "email", "tipo": "email", "mascara": "email"},
                               {"chave": "senha", "tipo": "senha"}])   # os campos que a operadora declara
    cofre = Cofre("teste", memoria=True)
    with pytest.raises(ErroCredencial) as e:
        cofre.guardar("111.111.111-11", "a@b.com.br", "segredo-123456789", senha_max=16)
    texto = str(e.value)
    assert "CPF inválido" in texto and "no máximo 16 caracteres" in texto
    assert "segredo" not in texto and "111" not in texto
    assert cofre.situacao()["guardadas"] is False
    cofre.guardar("529.982.247-25", "tiago@empresa.com.br", "s" * 16, senha_max=16)
    assert cofre.situacao() == {"guardadas": True, "email_mascarado": "ti***@***.com.br",
                                "quando": cofre.situacao()["quando"], "recusadas": False}
    CofreMemoria.esvaziar()


def test_rodape_diz_o_commit_e_avisa_quando_o_disco_fica_mais_novo(tmp_path):
    """A tela mostra o commit que está rodando e avisa "reinicie" quando o código no disco muda depois que ela abriu."""
    import os
    import subprocess

    from app.codigo import VersaoDoCodigo

    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Teste", "-c", "user.email=teste@exemplo.local",
                        *args], check=True, capture_output=True)

    (tmp_path / "app").mkdir()
    codigo = tmp_path / "app" / "tela.py"
    codigo.write_text("x = 1", encoding="utf-8")
    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "primeiro")
    versao = VersaoDoCodigo(raiz=tmp_path, pastas=("app",), arquivos=())
    versao.INTERVALO_S = 0
    s = versao.situacao()
    assert len(s["commit"]) >= 7 and s["quando"] and s["mais_novo_no_disco"] is False

    git("commit", "-q", "--allow-empty", "-m", "segundo")             # commit novo no disco
    assert versao.situacao()["mais_novo_no_disco"] is True
    assert versao.situacao()["commit"] == s["commit"]                 # continua dizendo o que está rodando

    sem_git = tmp_path / "copia"                                      # a pasta veio sem git: vale a data do .py
    (sem_git / "app").mkdir(parents=True)
    arq = sem_git / "app" / "tela.py"
    arq.write_text("x = 1", encoding="utf-8")
    versao = VersaoDoCodigo(raiz=sem_git, pastas=("app",), arquivos=())
    versao.INTERVALO_S = 0
    versao.commit = None                                              # mesmo se o Temp estiver dentro de um repositório
    assert versao.situacao()["mais_novo_no_disco"] is False
    os.utime(arq, (arq.stat().st_atime, arq.stat().st_mtime + 60))   # alguém mudou o código com a tela aberta
    assert versao.situacao() == {"commit": None, "quando": None, "mais_novo_no_disco": True}


def test_tela_sensivel_nao_avalia_iframe_de_recaptcha(tmp_path):
    import logging

    from nucleo.navegador import Mapeador, quadros_do_portal

    class Quadro:
        def __init__(self, url):
            self.url = url
            self.evals = 0

        def evaluate(self, js, arg=None):
            assert arg is None
            self.evals += 1
            if "recaptcha" in self.url:
                raise AssertionError("evaluate no iframe de reCAPTCHA")
            if "one-time-code" in js or "otp" in js:
                return ""
            if "password" in js:
                return False
            return True

    recaptcha = Quadro("https://www.google.com/recaptcha/api2/anchor?k=x")
    pagina = type("P", (), {
        "url": "https://corretor.portoseguro.com.br/corretoronline",
        "frames": [Quadro("https://corretor.portoseguro.com.br/corretoronline"), recaptcha],
    })()
    assert recaptcha not in quadros_do_portal(pagina)
    mapa = Mapeador(tmp_path, True, logging.getLogger("teste"), url_login="")
    assert mapa.tela_sensivel(pagina) is None
    assert recaptcha.evals == 0


def test_avaliar_quadro_chama_evaluate_sem_timeout():
    """Playwright Frame.evaluate(expression, arg=None): timeout= vira TypeError e o mapa some."""
    from nucleo.navegador import _avaliar_quadro

    class Quadro:
        def evaluate(self, expression, arg=None):
            if arg is not None:
                raise TypeError("evaluate() got an unexpected keyword argument")
            return True

    assert _avaliar_quadro(Quadro(), "() => true") is True


def test_mapa_de_erro_guarda_o_erro_inteiro_e_o_estado_de_carga(tmp_path):
    """15/11: o log só tem a 1ª linha do erro do Playwright; o mapa ERRO_ guarda o resto e o estado da página."""
    import logging

    from playwright.sync_api import sync_playwright

    from nucleo.navegador import Mapeador

    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        page = navegador.new_page()
        page.set_content("<html><title>Teste</title><body><button id=b>Ok</button>"
                         "<div style='position:fixed;inset:0'>cobre tudo</div></body></html>")
        mapa = Mapeador(tmp_path, False, logging.getLogger("teste"))
        try:
            page.locator("#b").click(timeout=800)
        except Exception:  # noqa: BLE001  (como o fluxo das operadoras: o mapa é gravado dentro do except)
            base = mapa.registrar(page, "ERRO_inicio", forcar=True)
        navegador.close()
    texto = base.with_suffix(".erro.txt").read_text(encoding="utf-8")
    assert "TimeoutError" in texto and "intercepts pointer events" in texto     # o que estava na frente do clique
    assert "readyState: complete" in texto and "online: True" in texto
    # sem erro em andamento e sem ser ERRO_, nada é gravado
    mapa2 = Mapeador(tmp_path / "b", False, logging.getLogger("teste"))
    assert mapa2.registrar(None, "x") is None


def test_mapa_de_erro_lista_as_requisicoes_pendentes_sem_a_query(tmp_path):
    """O diagnóstico mostra o que o navegador esperava (host e caminho, nunca a query com tokens)."""
    import logging
    import socket
    import threading

    from playwright.sync_api import sync_playwright

    from nucleo.navegador import Mapeador, abrir

    servidor = socket.socket()
    servidor.bind(("127.0.0.1", 0))
    servidor.listen(5)
    conexoes = []

    def aceitar():
        try:
            while True:
                conexoes.append(servidor.accept()[0])       # aceita e nunca responde
        except OSError:
            pass                                            # o teste fechou o servidor
    threading.Thread(target=aceitar, daemon=True).start()
    porta = servidor.getsockname()[1]
    cfg = {"execucao": {"lentidao_ms": 0}, "saida": {"pasta": str(tmp_path / "saida")}}
    with sync_playwright() as pw:
        contexto, page = abrir(pw, cfg)
        page.set_content("<html><title>Teste</title><body>oi</body></html>")
        page.evaluate(f"() => {{ fetch('http://127.0.0.1:{porta}/api/preco?token=SEGREDO123').catch(() => {{}}); }}")
        page.wait_for_timeout(600)                    # a requisição fica no ar: o servidor nunca responde
        mapa = Mapeador(tmp_path / "mapa", False, logging.getLogger("teste"))
        base = mapa.registrar(page, "ERRO_x", forcar=True)
        contexto.close()
    servidor.close()
    texto = base.with_suffix(".erro.txt").read_text(encoding="utf-8")
    assert "requisições pendentes: 1" in texto and f"127.0.0.1:{porta}/api/preco" in texto
    assert "SEGREDO123" not in texto and "token=" not in texto
    assert "visibilidade: visible" in texto


def test_esperar_visivel_para_na_hora_quando_a_tela_nao_avanca():
    """Parar não espera a próxima tela: se o título nunca vem, a espera cai no mesmo instante."""
    import time

    from nucleo.navegador import (ErroFluxo, Parado, desligar_parar, esperar_sair_da_rota,
                                  esperar_visivel, ligar_parar, sem_parar)

    class Loc:
        def count(self):
            return 0

        def nth(self, i):
            return self

        def is_visible(self):
            return False

    class Pagina:
        url = "https://exemplo/planos"

        def wait_for_url(self, *a, **k):
            raise TimeoutError("ainda na mesma rota")

    ligar_parar(lambda: True)
    try:
        t0 = time.monotonic()
        with pytest.raises(Parado) as e:
            esperar_visivel(Loc(), 30_000, "título da tela", "planos")
        assert time.monotonic() - t0 < 1.5 and e.value.etapa == "planos"

        t0 = time.monotonic()
        with pytest.raises(Parado):
            esperar_sair_da_rota(Pagina(), "/planos", 30_000, "planos", "Continuar")
        assert time.monotonic() - t0 < 1.5

        with sem_parar():
            t0 = time.monotonic()
            with pytest.raises(ErroFluxo):
                esperar_visivel(Loc(), 400, "título", "emitida")
            assert time.monotonic() - t0 >= 0.3
    finally:
        desligar_parar()
