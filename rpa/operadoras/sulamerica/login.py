"""Login automático: o robô entra no portal com o login que o corretor guardou na engrenagem do robô
(cofre do Windows, nucleo/credenciais.py). O corretor nunca mexe na janela do portal.

Regras:
- só entra quando o portal pede (a sessão fica no perfil_navegador), inclusive no meio de um pedido;
- nada do que é digitado vai para log, mapa, evento ou erro: qualquer falha com o login na tela vira
  ErroLogin com frase fixa (`from None`: a exceção do Playwright, que poderia citar o campo, é descartada);
  o log diz só em que passo parou;
- recusado pelo portal: para na PRIMEIRA vez e marca o login como recusado; o robô não tenta de novo até
  o corretor guardar a senha outra vez (evita bloquear a conta);
- código de verificação: pedido na tela do Newport (sessao.pedir_codigo) e digitado aqui;
- captcha, troca de senha obrigatória ou escolha de corretora depois do login: para e avisa. Captcha
  nunca é resolvido pelo robô.

O portal (OutSystems) responde por AJAX: sair do CPF, marcar "Ok, entendi!" e Entrar mandam cada um um POST
para a própria LoginGeral.aspx, sem recarregar a página. O robô faz como uma pessoa: sai do CPF e espera a
resposta, marca a caixa e espera, e só então clica em Entrar.
"""
from __future__ import annotations

import time

from playwright.sync_api import Page, TimeoutError as PWTimeout

from nucleo.credenciais import cofre as cofre_da_config, lembrar_segredos, mensagem_login, ocultar
from nucleo.navegador import ErroLogin, Parado, esperar_visivel, visiveis

from . import seletores as sel
from .telas import aceitar_cookies

OPERADORA = ("sulamerica", "SulAmérica")
_MARCA = "window.__npEntrar"   # some quando a página recarrega: o clique em ENTRAR levou a outra página


def tela_modulos_visivel(page: Page) -> bool:
    try:
        return bool(visiveis(page.get_by_text(sel.TEXTO_TELA_MODULOS)))
    except Exception:  # noqa: BLE001
        return False


def _erro(motivo: str) -> ErroLogin:
    from . import SulAmerica
    return ErroLogin(mensagem_login(motivo, OPERADORA[1], SulAmerica.mensagens_login), motivo)


def _visivel(loc) -> bool:
    try:
        return bool(visiveis(loc))
    except Exception:  # noqa: BLE001  (página navegando)
        return False


def _esperar_resposta_do_portal(page: Page, acao) -> None:
    """Faz a ação e espera o POST AJAX do portal para a própria página voltar (até 10 s; nem toda ação
    conversa com o servidor)."""
    try:
        with page.expect_response(lambda r: r.request.method == "POST" and sel.ROTA_LOGIN in r.url.lower(),
                                  timeout=10000):
            acao()
    except PWTimeout:
        pass


def painel_visivel(page: Page) -> bool:
    """Painel "Estou em cotações" (PainelCotacao.aspx): para onde "Voltar para a Home" leva (05/11)."""
    try:
        if page.is_closed():
            return False
        return sel.ROTA_PAINEL in sel.caminho(page) or bool(visiveis(page.get_by_text(sel.TEXTO_PAINEL)))
    except Exception:  # noqa: BLE001
        return False


def _sessao_na_tela(page: Page) -> bool:
    """A página já é do portal logado: tela de módulos, painel de cotações, cotador novo ou página da emissão.
    Nessas telas o robô nunca recarrega o login (o portal recusaria o 2º acesso)."""
    if tela_modulos_visivel(page) or painel_visivel(page):
        return True
    caminho = sel.caminho(page)
    return sel.ROTA_EMITIDA in caminho or any(pedaco in caminho for _, pedaco in sel.ROTAS)


def _abrir_login(s) -> None:
    s.page.goto(s.cfg["urls"]["login"])
    s.page.wait_for_load_state("domcontentloaded")
    aceitar_cookies(s.page)


def _aprender_limite_da_senha(s, limite: int) -> None:
    """O maxlength real do campo de senha, lido a cada login, vai para a configuração aprendida do portal
    (saida/<op>/portal.json): é o limite que a engrenagem usa ao guardar a senha (16 até o portal dizer outro)."""
    from nucleo.configuracao import aprendido, aprender
    pasta = s.cfg["saida"]["pasta"]
    antes = aprendido(pasta).get("senha_max")
    if antes != limite:
        aprender(pasta, "senha_max", limite)
        s.log.info(f"O campo de senha do portal aceita até {limite} caracteres"
                   + (f" (antes: {antes})." if antes else ".") + " A engrenagem passa a usar esse limite.")


def entrar(s, pode_parar: bool = True, insistir: bool = True) -> None:
    """Garante a sessão no portal: tela de módulos (ou a página para onde o portal voltou depois do login).

    Portal real 05/11: com a sessão viva, recarregar a LoginGeral.aspx mostra o formulário de novo e o segundo
    login é recusado ("Já existe um acesso ativo para esse CPF"). Por isso, se a tela já é do portal logado
    (módulos, cotador ou emissão), o robô confia nela; se a sessão tiver caído, a próxima tela leva ao login e
    o robô entra ali. O "acesso ativo" de outro lugar (navegador comum, janela fechada) não é senha errada: no
    começo do trabalho o robô espera e tenta de novo, até `login_liberacao_ms`. No meio de um pedido
    (insistir=False) ele para na hora e avisa: alguém está usando o portal com este CPF."""
    page, log = s.page, s.log
    parar = s.pediu_parar if pode_parar else (lambda: False)
    if _sessao_na_tela(page):
        log.info("Sessão do portal aberta: não precisa entrar de novo.")
        s.aviso("login_ok", sessao_ativa=True)
        return
    if not _visivel(sel.login_campo_cpf(page)):   # página em branco ou outra: abre o login
        _abrir_login(s)
    if tela_modulos_visivel(page):
        log.info("Sessão ainda ativa: tela de módulos já aberta.")
        s.aviso("login_ok", sessao_ativa=True)
        return

    cofre = cofre_da_config(s.cfg, OPERADORA[0])
    if cofre.situacao()["recusadas"]:
        raise _erro("recusadas")
    login = cofre.ler()
    if login is None:
        raise _erro("sem_credenciais")
    espera = s.cfg["execucao"].get("login_reentrada_ms", 60000) / 1000
    limite = s.cfg["execucao"].get("login_liberacao_ms", 600000) / 1000
    inicio = time.monotonic()
    primeira = True
    try:
        while True:
            try:
                _tentar_login(s, cofre, login, parar, mapear=primeira)
                return
            except ErroLogin as e:
                if e.motivo == "acesso_ativo" and not insistir:
                    log.error("No meio do pedido o portal pediu o login de novo e respondeu que já existe um "
                              "acesso ativo para este CPF. O robô parou e não tenta de novo: confira se alguém "
                              "está usando o portal com este CPF.")
                    raise
                if e.motivo != "acesso_ativo" or time.monotonic() - inicio + espera > limite:
                    raise
            primeira = False
            log.warning(f"O portal ainda tem um acesso ativo para este CPF. O robô tenta entrar de novo em "
                        f"{espera:g} s (espera até {limite / 60:g} min no total).")
            s.aviso("login_aguardando", segundos=int(espera))
            fim = time.monotonic() + espera
            while time.monotonic() < fim:
                if parar():
                    raise Parado("login")
                time.sleep(0.5)
            _abrir_login(s)
            if tela_modulos_visivel(page):
                log.info("O portal liberou: tela de módulos aberta.")
                s.aviso("login_ok", sessao_ativa=True)
                return
    finally:
        login = None


def _tentar_login(s, cofre, login: dict, parar, mapear: bool) -> None:
    """Uma tentativa: preenche CPF, e-mail e senha, marca "Ok, entendi!", clica em Entrar e espera a resposta."""
    page, log = s.page, s.log
    if _visivel(sel.captcha(page)):
        raise _erro("captcha")
    s.aviso("login_entrando")
    log.info("Entrando no portal com o login guardado na engrenagem do robô.")
    esperar_visivel(sel.login_campo_cpf(page), s.t("timeout_tela_ms"), "campo CPF do login", "login")
    if mapear:
        s.mapa.registrar(page, "login", login_vazio=True)   # só com os campos vazios (calibrar o login)
    antes = _mensagens(page)                                 # texto fixo da página não é resposta ao login
    passo = "caixa Ok, entendi!"
    try:
        ok = sel.login_ok_entendi(page)
        if not ok.count():
            raise RuntimeError("sem a caixa")           # sem ela o portal recusaria: nem tenta
        s.mapa.login_digitado = True
        # O navegador não guarda o que vai ser digitado (preenchimento automático, estado da sessão).
        page.evaluate("() => document.querySelectorAll('form, input').forEach(e => e.setAttribute('autocomplete', 'off'))")
        passo = "achar os campos CPF, e-mail e senha"
        campos = (("o CPF guardado", sel.login_campo_cpf(page), "cpf"),
                  ("o e-mail guardado", sel.login_campo_email(page), "email"),
                  ("a senha guardada", sel.login_campo_senha(page), "senha"))
        for nome, campo, chave in campos:   # maior que o campo seria cortado e recusado: nem tenta
            limite = campo.get_attribute("maxlength")
            if chave == "senha" and limite and limite.isdigit():
                _aprender_limite_da_senha(s, int(limite))
            if limite and limite.isdigit() and len(login[chave]) > int(limite):
                log.error(f"Login: {nome} tem mais caracteres do que o campo do portal aceita ({limite}). "
                          "Confira e guarde de novo na engrenagem do robô.")
                raise _erro("senha_comprida" if chave == "senha" else "falha")
        passo = "CPF"
        cpf = campos[0][1]
        cpf.fill(login["cpf"])
        _esperar_resposta_do_portal(page, cpf.blur)     # o portal confere o CPF ao sair do campo
        passo = "e-mail"
        campos[1][1].fill(login["email"])
        passo = "senha"
        campos[2][1].fill(login["senha"])
        passo = "marcar Ok, entendi!"
        if not ok.first.is_checked():
            _esperar_resposta_do_portal(page, ok.first.check)
        passo = "Entrar"
        page.evaluate(f"{_MARCA} = true")
        sel.login_botao_entrar(page).click()
    except ErroLogin:
        raise
    except Exception as e:  # noqa: BLE001
        log.error(f"Login: não consegui fazer o passo '{passo}' na tela de login ({type(e).__name__}).")
        raise _erro("falha") from None
    _esperar_resultado(s, cofre, parar, antes)


def _mensagens(page: Page) -> dict[str, bool]:
    """Quais respostas possíveis do portal já estão visíveis (antes do clique, são texto fixo da página)."""
    return {"acesso_ativo": _visivel(page.get_by_text(sel.TEXTO_ACESSO_ATIVO)),
            "recusa": _visivel(page.get_by_text(sel.TEXTO_LOGIN_RECUSADO)) or _visivel(sel.login_mensagem_erro(page)),
            "troca": _visivel(page.get_by_text(sel.TEXTO_TROCA_SENHA)),
            "validacao": _visivel(sel.login_validacao(page))}


def _esperar_resultado(s, cofre, parar, antes: dict[str, bool]) -> None:
    page, log = s.page, s.log
    limite = s.cfg["execucao"].get("timeout_login_ms", 60000) / 1000
    fim = time.monotonic() + limite
    codigos = fora = 0
    while time.monotonic() < fim:
        if parar():
            raise Parado("login")
        if tela_modulos_visivel(page):
            break
        if _visivel(page.get_by_text(sel.TEXTO_SELECAO_CORRETORA)):
            raise _erro("selecao_corretora")
        if _visivel(sel.campo_codigo(page)):
            if codigos >= 3:
                raise _erro("codigo")
            codigos += 1
            _digitar_codigo(s)
            fim = time.monotonic() + limite    # o tempo recomeça depois do código
            antes = _mensagens(page)
            continue
        if _visivel(sel.captcha(page)):
            raise _erro("captcha")
        no_login = _visivel(sel.login_campo_cpf(page))
        if not no_login and len(_visiveis_senha(page)) >= 2:
            raise _erro("troca_senha")
        agora = _mensagens(page)
        _resposta_que_nao_e_recusa(log, agora, antes)
        if no_login and (not _marcado(page) or (agora["recusa"] and not antes["recusa"])):
            # Confirma com a página assentada antes de marcar a recusa: a mensagem, ou a navegação depois de um
            # login que deu certo, pode ter chegado entre uma conferência e outra.
            time.sleep(0.8)
            if tela_modulos_visivel(page) or not _visivel(sel.login_campo_cpf(page)):
                continue
            agora = _mensagens(page)
            _resposta_que_nao_e_recusa(log, agora, antes)
            if not _marcado(page) or (agora["recusa"] and not antes["recusa"]):
                _recusado(s, cofre)             # o login voltou (página recarregada) ou o portal disse não
        # Fora do login e sem nada pedindo atenção por ~1 s: o portal voltou para onde o robô estava.
        fora = fora + 1 if not no_login and sel.ROTA_LOGIN not in page.url.lower() else 0
        if fora >= 3:
            break
        time.sleep(0.3)
    else:
        if _visivel(sel.login_campo_cpf(page)):
            _recusado(s, cofre)                 # continua no login sem resposta: tratar como recusa
        raise _erro("sem_resposta")
    log.info("Login feito.")
    s.aviso("login_ok", sessao_ativa=False)


def _resposta_que_nao_e_recusa(log, agora: dict[str, bool], antes: dict[str, bool]) -> None:
    """Respostas do portal que param o robô sem marcar o login como recusado (a senha não estava errada)."""
    novo = {k: agora[k] and not antes[k] for k in agora}
    if novo["troca"]:
        raise _erro("troca_senha")
    if novo["acesso_ativo"]:
        log.error("Login: o portal diz que já existe um acesso ativo para este CPF (logado em outro navegador "
                  "ou computador). O login não foi marcado como recusado.")
        raise _erro("acesso_ativo")
    if novo["validacao"]:
        log.error("Login: o próprio formulário do portal recusou o preenchimento (campo faltando ou "
                  "fora do formato). O login não foi marcado como recusado.")
        raise _erro("falha")


def _visiveis_senha(page: Page) -> list:
    try:
        return visiveis(page.locator("input[type=password i]"))
    except Exception:  # noqa: BLE001
        return []


def _marcado(page: Page) -> bool:
    """True enquanto a página do clique em ENTRAR é a mesma (ainda não recarregou)."""
    try:
        return bool(page.evaluate(f"{_MARCA} === true"))
    except Exception:  # noqa: BLE001  (navegando: trata como a mesma página por enquanto)
        return True


def _recusado(s, cofre) -> None:
    cofre.marcar_recusadas()
    try:
        textos = visiveis(sel.login_mensagem_erro(s.page)) or visiveis(s.page.get_by_text(sel.TEXTO_LOGIN_RECUSADO))
        resposta = ocultar(" ".join(textos[0].inner_text().split()))[:200] if textos else ""
    except Exception:  # noqa: BLE001
        resposta = ""
    s.log.error("O portal recusou o login guardado"
                + (f" (mensagem do portal: \"{resposta}\")" if resposta else "")
                + ". O robô não tenta de novo até a senha ser guardada outra vez.")
    raise _erro("recusadas")


def _digitar_codigo(s) -> None:
    page, log = s.page, s.log
    log.info("O portal pediu um código de verificação; pedindo na tela do Newport.")
    codigo = s.pedir_codigo() if s.pedir_codigo else None
    if not codigo:
        raise _erro("codigo")
    lembrar_segredos(codigo)
    try:
        sel.campo_codigo(page).first.fill(codigo)
        page.evaluate(f"{_MARCA} = true")
        sel.botao_confirmar_codigo(page).first.click()
    except Exception as e:  # noqa: BLE001
        log.error(f"Login: não consegui digitar o código de verificação ({type(e).__name__}).")
        raise _erro("falha") from None
    finally:
        codigo = None
    fim = time.monotonic() + 10
    while time.monotonic() < fim and _marcado(page):   # espera a resposta do portal ao código
        time.sleep(0.3)
