"""Navegador, esperas genéricas e registro das telas (modo --mapear). Vale para qualquer operadora."""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Locator, Page, TimeoutError as PWTimeout

from .credenciais import ocultar, segredos_visiveis


class ErroFluxo(Exception):
    """A tela não se comportou como esperado (seletor, tempo, validação)."""

    def __init__(self, mensagem: str, etapa: str = ""):
        super().__init__(mensagem)
        self.etapa = etapa


class ErroDados(ErroFluxo):
    """O dado do pedido não serve para o portal (plano inexistente, idade faltando...)."""


class ErroLogin(ErroFluxo):
    """O robô não conseguiu entrar no portal. Para o trabalho inteiro (os outros pedidos também precisariam
    do login). `motivo`: sem_credenciais | recusadas | captcha | troca_senha | codigo | sem_resposta | falha.
    A mensagem é sempre uma frase fixa: nunca leva o que foi digitado no login."""

    def __init__(self, mensagem: str, motivo: str):
        super().__init__(mensagem, "login")
        self.motivo = motivo


class Parado(Exception):
    """O corretor pediu para parar. Só é levantada em ponto seguro (nunca no meio de uma emissão)."""

    def __init__(self, etapa: str = ""):
        super().__init__("parado a pedido do corretor")
        self.etapa = etapa


# 15/11, 3 robôs juntos: a SulAmérica ficou com a tela trocada (URL e título novos) mas o corpo da anterior e a captura em
# branco: o navegador do robô parou de pintar. No Windows o Chromium marca como "coberta" a janela que não está à
# vista e reduz o desenho dela (CalculateNativeWinOcclusion); o resto desliga a economia de segundo plano. Com vários
# navegadores escondidos ao mesmo tempo, nenhum pode ser tratado como "em segundo plano". Não muda o que o portal vê.
# O Chromium só vale um --disable-features (o último): a lista abaixo é a do Playwright mais a CalculateNativeWinOcclusion.
_DESLIGADOS = ("CalculateNativeWinOcclusion,ImprovedCookieControls,LazyFrameLoading,GlobalMediaControls,"
               "DestroyProfileOnBrowserClose,MediaRouter,DialMediaRouteProvider,AcceptCHFrame,AutoExpandDetailsElement,"
               "CertificateTransparencyComponentUpdater,AvoidUnnecessaryBeforeUnloadCheckSync,Translate")
ARGS_SEM_PAUSA = [
    f"--disable-features={_DESLIGADOS}",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-background-timer-throttling",
    "--disable-ipc-flooding-protection",
]


class VigiaDeRede:
    """Quais requisições do navegador estão pendentes e quais falharam (ou deram 4xx/5xx) há pouco. Só host e caminho (sem
    query: nunca guarda tokens nem o que foi digitado). O mapa de erro mostra isto: 15/11 o portal da SulAmérica ficou
    ~60 s com a tela nova pela metade e nada no log dizia por quê."""

    def __init__(self):
        self.pendentes: dict = {}
        self.falhas: list[str] = []
        self.erros_js: list[str] = []          # exceções do JavaScript do portal e console.error

    def erro_js(self, texto: str) -> None:
        self.erros_js = (self.erros_js + [f"{datetime.now():%H:%M:%S} {texto[:300]}"])[-15:]

    @staticmethod
    def _curto(url: str) -> str:
        u = urlparse(url)
        return f"{u.netloc}{u.path}"[:140]

    def comecou(self, req) -> None:
        self.pendentes[req] = (time.monotonic(), req.method, self._curto(req.url))

    def acabou(self, req) -> None:
        self.pendentes.pop(req, None)

    def falhou(self, req) -> None:
        self.pendentes.pop(req, None)
        self._anotar(f"{req.method} {self._curto(req.url)} falhou: {getattr(req, 'failure', None)}")

    def respondeu(self, resp) -> None:
        if resp.status >= 400:
            self._anotar(f"{resp.request.method} {self._curto(resp.url)} -> HTTP {resp.status}")

    def _anotar(self, texto: str) -> None:
        self.falhas = (self.falhas + [f"{datetime.now():%H:%M:%S} {texto}"])[-15:]

    def linhas(self) -> list[str]:
        agora = time.monotonic()
        antigas = sorted(((agora - t, m, u) for t, m, u in self.pendentes.values()), reverse=True)
        saida = [f"requisições pendentes: {len(antigas)}"]
        saida += [f"  {m} {u} há {idade:.0f} s" for idade, m, u in antigas[:12]]
        if self.falhas:
            saida.append("falhas e erros HTTP recentes:")
            saida += [f"  {f}" for f in self.falhas]
        if self.erros_js:
            saida.append("erros de JavaScript do portal:")
            saida += [f"  {e}" for e in self.erros_js]
        return saida


def abrir(pw, cfg: dict):
    """Abre o navegador do robô. Por padrão o corretor não vê a janela do portal: headless "new" (o
    Chromium completo, sem janela) ou, com `janela_escondida: fora_da_tela`, uma janela minimizada fora
    da tela, para portais que se comportam diferente sem janela. `modo_visual` mostra a janela (calibrar).
    Nunca ligar trace do Playwright: ele gravaria o que é digitado no login."""
    ex = cfg["execucao"]
    perfil = Path(cfg["saida"]["pasta"]) / "perfil_navegador"
    perfil.mkdir(parents=True, exist_ok=True)
    _sem_guardar_formularios(perfil)
    janela: dict = {"headless": False}
    if not ex.get("modo_visual"):
        if ex.get("janela_escondida") == "fora_da_tela":
            janela["args"] = ["--window-position=-32000,-32000", "--start-minimized"]
        else:
            janela = {"headless": True, "channel": "chromium"}
    janela["args"] = list(janela.get("args") or []) + ARGS_SEM_PAUSA
    contexto = pw.chromium.launch_persistent_context(
        user_data_dir=str(perfil),
        slow_mo=ex.get("lentidao_ms", 0),
        accept_downloads=True,
        viewport={"width": 1400, "height": 900},
        locale="pt-BR",
        **janela,
    )
    contexto.set_default_timeout(ex.get("timeout_padrao_ms", 30000))
    vigia = VigiaDeRede()
    contexto.np_rede = vigia
    contexto.on("request", vigia.comecou)
    contexto.on("requestfinished", vigia.acabou)
    contexto.on("requestfailed", vigia.falhou)
    contexto.on("response", vigia.respondeu)
    contexto.on("weberror", lambda we: vigia.erro_js(f"exceção: {we.error}"))
    contexto.on("console", lambda m: vigia.erro_js(f"console.error: {m.text}") if m.type == "error" else None)
    page = contexto.pages[0] if contexto.pages else contexto.new_page()
    return contexto, page


def _sem_guardar_formularios(perfil: Path) -> None:
    """O navegador do robô não guarda senha (gerenciador de senhas) nem o que é digitado em formulários
    (preenchimento automático): o perfil fica em saida/ e não pode ter o login do portal. Junto com o
    autocomplete=off que o login põe nos campos antes de digitar (form state da sessão)."""
    arquivo = perfil / "Default" / "Preferences"
    try:
        prefs = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}
    except ValueError:
        prefs = {}
    prefs["credentials_enable_service"] = False
    prefs["credentials_enable_autosignin"] = False
    prefs.setdefault("profile", {})["password_manager_enabled"] = False
    prefs.setdefault("autofill", {}).update(enabled=False, profile_enabled=False, credit_card_enabled=False)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(prefs), encoding="utf-8")


_TIPOS_SEM_TEXTO ="['hidden','checkbox','radio','submit','button','image','reset']"
_JS_CAMPOS_VAZIOS = ("() => [...document.querySelectorAll('input, textarea')].every(e => "
                     f"{_TIPOS_SEM_TEXTO}.includes((e.type || '').toLowerCase()) || e.value === '')")
# Campo de código de verificação VISÍVEL (quem digita o código precisa ver o campo). Devolve o nome do campo
# (id, name ou placeholder; nunca o valor) para o log. 05/11: a página da cotação emitida (Simulador.aspx)
# era tomada por tela de código e ficava sem mapa (campo escondido com "token" no nome, a confirmar).
_JS_CAMPO_CODIGO = ("() => { const e = [...document.querySelectorAll('input')].find(e => (e.type || '').toLowerCase() !== 'hidden' && "
                    "e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden' && "
                    "((e.autocomplete || '').toLowerCase() === 'one-time-code' || /c[oó]digo|token|otp|verifica/i.test("
                    "[e.name, e.id, e.placeholder, e.getAttribute('aria-label')].join(' ')))); "
                    "return e ? String(e.id || e.name || e.placeholder || 'sem nome').slice(0, 60) : ''; }")


# Campo de senha visível, ou com algo digitado (mesmo escondido): a tela conta como tela de login e não vira
# mapa. 05/11: o painel "Estou em cotações" ficava sem mapa por um campo de senha escondido e vazio.
_JS_CAMPO_SENHA = ("() => [...document.querySelectorAll('input[type=password i]')].some(e => "
                   "(e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden') || !!e.value)")


class Mapeador:
    """Salva print, HTML e árvore de acessibilidade de cada tela.

    É o material que o Claude Code (ou quem for calibrar) lê para corrigir seletores.

    LGPD:
    - tela de login (URL de login da operadora, com path igual, ou campo de senha na página): só é
      gravada pelo robô ANTES de digitar (`login_vazio=True`, todos os campos vazios), para calibrar
      os seletores do login. Depois de digitar, nada da tela de login é gravado, nem em erro (forcar=True).
      No portal a tela de módulos tem a mesma URL do login e também fica de fora;
    - tela de código de verificação: nunca;
    - nas outras telas, os valores de login que o robô leu (ex.: e-mail no topo do portal) saem do HTML
      e da árvore como ••• e ficam cobertos no print.
    """

    def __init__(self, pasta_saida: str | Path, ativo: bool, log, url_login: str = ""):
        self.ativo = ativo
        self.log = log
        self.pasta = Path(pasta_saida) / "mapa" / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.n = 0
        self.path_login = urlparse(url_login).path.rstrip("/").lower()
        self.login_digitado = False   # o robô começou a digitar o login: daqui em diante, nunca mais
        self._campo_codigo = ""

    def tela_sensivel(self, page: Page) -> str | None:
        """"login", "codigo" ou None. Na dúvida (página navegando ou fechada), "login": melhor perder um mapa."""
        try:
            achado = next((c for c in (f.evaluate(_JS_CAMPO_CODIGO) for f in page.frames) if c), "")
            if achado:
                self._campo_codigo = achado
                return "codigo"
            if self.path_login and urlparse(page.url).path.rstrip("/").lower() == self.path_login:
                return "login"
            return "login" if any(f.evaluate(_JS_CAMPO_SENHA) for f in page.frames) else None
        except Exception:  # noqa: BLE001
            return "login"

    def tela_de_login(self, page: Page) -> bool:
        return self.tela_sensivel(page) is not None

    def _campos_vazios(self, page: Page) -> bool:
        try:
            return all(f.evaluate(_JS_CAMPOS_VAZIOS) for f in page.frames)
        except Exception:  # noqa: BLE001
            return False

    def registrar(self, page: Page, etapa: str, forcar: bool = False, login_vazio: bool = False) -> Path | None:
        if not (self.ativo or forcar):
            return None
        sensivel = self.tela_sensivel(page)
        if sensivel == "codigo":
            self.log.info(f"mapa não gravado: tela de código de verificação (campo {self._campo_codigo})")
            return None
        if sensivel == "login" and not (login_vazio and not self.login_digitado and self._campos_vazios(page)):
            self.log.info("mapa não gravado: tela de login")
            return None
        self.n += 1
        self.pasta.mkdir(parents=True, exist_ok=True)
        base = self.pasta / f"{self.n:02d}_{etapa}"
        try:
            mascaras = [page.get_by_text(s) for s in segredos_visiveis()]
            page.screenshot(path=str(base.with_suffix(".png")), full_page=True, mask=mascaras)
        except Exception:  # noqa: BLE001
            self.log.warning("mapear: print falhou")
        try:
            base.with_suffix(".html").write_text(ocultar(page.content()), encoding="utf-8")
        except Exception:  # noqa: BLE001
            self.log.warning("mapear: HTML falhou")
        try:
            arvore = page.locator("body").aria_snapshot()
            base.with_suffix(".aria.txt").write_text(ocultar(f"URL: {page.url}\n\n{arvore}"), encoding="utf-8")
        except Exception:  # noqa: BLE001
            self.log.warning("mapear: árvore falhou")
        if forcar and etapa.startswith("ERRO_"):
            self._diagnostico(page, base)
        self.log.info(f"mapa salvo: {base}.*")
        return base

    def _diagnostico(self, page: Page, base: Path) -> None:
        """Mapa de ERRO: grava também o erro inteiro (o log só guarda a 1ª linha; o resto traz o que o Playwright viu, ex.:
        "<div> intercepts pointer events") e o estado de carga da página (15/11: com 3 robôs, páginas ficaram em branco ou
        em "Carregando..." por mais de 30 s e o log não dizia o porquê). Nada digitado entra aqui; passa por `ocultar`."""
        linhas = []
        erro = sys.exc_info()[1]
        if erro is not None:
            linhas += [f"Erro: {type(erro).__name__}", str(erro), ""]
        try:
            info = page.evaluate(
                "() => { const n = performance.getEntriesByType('navigation')[0] || {}; "
                "return {readyState: document.readyState, visibilidade: document.visibilityState, foco: document.hasFocus(), "
                "online: navigator.onLine, titulo: document.title, "
                "texto_chars: (document.body && document.body.innerText || '').length, "
                "dom_pronto_ms: Math.round(n.domContentLoadedEventEnd || 0), carga_ms: Math.round(n.loadEventEnd || 0), "
                "desde_a_navegacao_ms: Math.round(performance.now()), "
                "recursos: performance.getEntriesByType('resource').length}; }")
            linhas += [f"{k}: {v}" for k, v in info.items()]
        except Exception as e:  # noqa: BLE001
            linhas.append(f"estado da página: não consegui ler ({type(e).__name__})")
        try:
            quadros = page.evaluate("() => new Promise(r => { const t = setTimeout(() => r('NÃO disparou em 1,5 s (a página "
                                    "não está desenhando quadros)'), 1500); requestAnimationFrame(() => { clearTimeout(t); "
                                    "r('ok'); }); })")
            linhas.append(f"quadros de animação (requestAnimationFrame): {quadros}")
        except Exception as e:  # noqa: BLE001
            linhas.append(f"quadros de animação: sem resposta da página ({type(e).__name__})")
        try:
            vigia = getattr(page.context, "np_rede", None)
            if vigia is not None:
                linhas += ["", *vigia.linhas()]
        except Exception:  # noqa: BLE001
            pass
        try:
            base.with_suffix(".erro.txt").write_text(ocultar("\n".join(linhas)), encoding="utf-8")
        except Exception:  # noqa: BLE001
            self.log.warning("mapear: diagnóstico do erro falhou")


def visiveis(loc: Locator) -> list[Locator]:
    return [loc.nth(i) for i in range(loc.count()) if loc.nth(i).is_visible()]


def esperar_visivel(loc: Locator, timeout_ms: int, descricao: str, etapa: str = "") -> Locator:
    """Espera o PRIMEIRO elemento visível do localizador (tolera duplicados escondidos)."""
    fim = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fim:
        try:
            achados = visiveis(loc)
        except Exception:  # noqa: BLE001  (página navegando)
            achados = []
        if achados:
            return achados[0]
        time.sleep(0.2)
    raise ErroFluxo(f"não encontrei '{descricao}' na tela em {timeout_ms // 1000}s", etapa)


def clicar_texto(page: Page, padrao: re.Pattern, descricao: str, timeout_ms: int = 15000,
                 etapa: str = "") -> None:
    """Clica no primeiro elemento visível com o texto (botão, link ou input com value)."""
    esperar_visivel(page.get_by_text(padrao), timeout_ms, descricao, etapa).click()


def esperar_sumir(page: Page, localizador, timeout_ms: int = 30000) -> None:
    """Espera até nenhum elemento do localizador estar visível (ex.: "esqueletos" de carregamento)."""
    fim = time.monotonic() + timeout_ms / 1000
    estavel = 0
    while time.monotonic() < fim:
        try:
            n = len(visiveis(localizador(page)))
        except Exception:  # noqa: BLE001
            n = 1
        estavel = estavel + 1 if n == 0 else 0
        if estavel >= 2:
            return
        time.sleep(0.25)


def esperar_sair_da_rota(page: Page, pedaco_url: str, timeout_ms: int, etapa: str, motivo: str) -> None:
    pedaco = pedaco_url.lower()
    try:
        page.wait_for_url(lambda u: pedaco not in u.lower(), timeout=timeout_ms, wait_until="commit")
    except PWTimeout:
        raise ErroFluxo(
            f"{motivo}: a tela {etapa} não avançou em {timeout_ms // 1000}s "
            "(campo obrigatório faltando ou mensagem de erro na tela?)", etapa)
