"""Os robôs: um por operadora, cada um na sua thread, com a sua fila, a sua janela do portal, a sua trava e o seu
log. Um robô travado (portal lento, código de verificação esperando...) não segura o de outra operadora.

O `Trabalhador` é o coordenador que a tela usa: recebe os pedidos, divide um pedido com várias operadoras entre
os robôs delas e só dá o pedido por terminado quando todas terminam. Cada robô roda um trabalho por vez (a API
síncrona do Playwright exige uma thread por navegador).

O navegador de cada operadora (escondido, por padrão) fica aberto entre um trabalho e outro: o robô entra no
portal sozinho, com o login do cofre do Windows, só quando o portal pede; as cotações seguintes reaproveitam a
sessão. O corretor nunca mexe na janela do portal: se o portal pedir um código de verificação, a tela pede para
ele (receber_codigo).
"""
from __future__ import annotations

import logging
import queue
import threading
import time
import traceback
from pathlib import Path

import operadoras
from nucleo import credenciais
from nucleo.estado import Estado
from nucleo.navegador import ErroLogin, Mapeador, Parado, abrir
from nucleo.registro import configurar_log
from nucleo.trava import OcupadoErro, Trava

# Quando um pedido tem várias operadoras, o resultado final é o "pior" das partes.
_PESO = {"erro": 3, "cancelado": 2, "concluido": 1}


class _ManipuladorTela(logging.Handler):
    """Manda as linhas do log do robô para a tela."""

    def __init__(self, robo: "_RoboOperadora", tid: int):
        super().__init__(level=logging.INFO)
        self.t = robo
        self.tid = tid

    def emit(self, record: logging.LogRecord) -> None:
        try:
            texto = record.getMessage()
            if texto.startswith("mapa salvo:") or set(texto) <= {"="}:
                return
            nivel = record.levelname.lower()
            self.t.banco.evento(self.tid, "log", texto, {"nivel": nivel})
            self.t.bus.publicar({"tipo": "log", "trabalho": self.tid, "nivel": nivel, "texto": texto})
        except Exception:  # noqa: BLE001
            pass


class Trabalhador(threading.Thread):
    """Coordena um robô por operadora. A tela só conversa com este objeto."""

    def __init__(self, obter_config, banco, bus):
        super().__init__(daemon=True, name="robos")
        self.obter_config = obter_config      # função: devolve o config total já com os ajustes da tela
        self.banco = banco
        self.bus = bus
        # desconectado | abrindo | entrando | aguardando_portal | aguardando_codigo | conectado | ocupado | saindo
        self.conexao: dict[str, str] = {}
        self.ultima_etapa: dict | None = None
        self._robos: dict[str, _RoboOperadora] = {}
        self._partes: dict[int, dict] = {}    # pedido -> {"trabalho", "faltam", "fins", "comecou"}
        self._mutex = threading.Lock()
        self._encerrar = threading.Event()

    # ------------------------------------------------------------------ robôs
    def _robo(self, op_id: str) -> "_RoboOperadora":
        with self._mutex:
            robo = self._robos.get(op_id)
            if robo is None:
                robo = _RoboOperadora(self, op_id)
                self._robos[op_id] = robo
                robo.start()
            return robo

    def _todos(self) -> list["_RoboOperadora"]:
        with self._mutex:
            return list(self._robos.values())

    @property
    def navegadores(self) -> dict[str, tuple]:
        """As janelas do portal abertas agora, por operadora."""
        return {r.op_id: r.navegador for r in self._todos() if r.navegador is not None}

    # ------------------------------------------------------------------ chamado pelo servidor
    def enfileirar(self, trabalho: dict) -> None:
        """Um pedido com várias operadoras vira uma parte por operadora, cada uma na fila do robô dela."""
        tid = trabalho["id"]
        if trabalho.get("tipo") == "conectar":
            partes = {trabalho["operadora"]: trabalho}
        else:
            por_op: dict[str, list] = {}
            for item in trabalho.get("itens") or []:
                por_op.setdefault(item["operadora"], []).append(item)
            partes = {op_id: {**trabalho, "itens": itens} for op_id, itens in por_op.items()}
        with self._mutex:
            self._partes[tid] = {"trabalho": trabalho, "faltam": set(partes), "fins": {}, "comecou": False}
        self.bus.publicar({"tipo": "trabalho", "trabalho": tid, "status": "na_fila"})
        if not partes:
            self._terminou(tid, "", "concluido")
        for op_id, parte in partes.items():
            self._robo(op_id).enfileirar(parte)

    def cancelar(self, tid: int) -> bool:
        achou = [r.cancelar(tid) for r in self._todos()]     # todas as operadoras do pedido
        return any(achou)

    def receber_codigo(self, op_id: str, codigo: str) -> bool:
        """Código de verificação digitado na tela. False se o robô não está esperando um."""
        robo = self._robos.get(op_id)
        return bool(robo and robo.receber_codigo(codigo))

    def ocupado(self) -> bool:
        return any(r.ocupado() for r in self._todos())

    def registro_livre(self, op_id: str, pasta) -> bool:
        """True se dá para liberar/resolver pendências desta operadora agora: o robô dela está parado e nenhum
        outro processo (linha de comando) está com o robô rodando nesta pasta."""
        robo = self._robos.get(op_id)
        if robo is not None and robo.ocupado():
            return False
        if robo is not None and robo.trava is not None:     # a trava é desta tela (janela aberta, robô parado)
            return True
        try:
            with Trava(pasta):
                return True
        except OcupadoErro:
            return False

    def pedir_saida(self, op_id: str) -> str:
        """"Sair do portal agora" (cartão da operadora): só com o robô dela parado e a fila dela vazia.
        "ok" (o robô sai já), "fora" (não há janela do portal aberta) ou "ocupado"."""
        robo = self._robos.get(op_id)
        return robo.pedir_saida() if robo is not None else "fora"

    def sair_ao_fechar(self, prazo_s: float = 4.0) -> None:
        """A janela preta está fechando: o Windows dá uns 5 s. Cada robô parado sai do portal nesse tempo; no
        meio de uma cotação não sai (a sessão do portal expira sozinha)."""
        feitos = [f for f in (r.sair_ao_fechar(prazo_s) for r in self._todos()) if f is not None]
        fim = time.monotonic() + prazo_s
        for feito in feitos:
            feito.wait(max(0.0, fim - time.monotonic()))

    def encerrar(self) -> None:
        self._encerrar.set()
        for robo in self._todos():
            robo.encerrar()

    def situacao(self) -> dict:
        robos = self._todos()
        rodando = [r.atual for r in robos if r.atual]
        atual = ({k: rodando[0].get(k) for k in ("id", "tipo", "modo", "titulo")} if rodando else None)
        ids_rodando = {t.get("id") for t in rodando}
        na_fila = [tid for tid in dict.fromkeys(t for r in robos for t in r.lista_da_fila()) if tid not in ids_rodando]
        return {"conexao": dict(self.conexao), "atual": atual, "ultima_etapa": self.ultima_etapa, "na_fila": na_fila}

    def run(self) -> None:
        self._encerrar.wait()
        fim = time.monotonic() + 6
        for robo in self._todos():
            robo.join(max(0.1, fim - time.monotonic()))

    # ------------------------------------------------------------------ chamado pelos robôs
    def _conexao(self, op_id: str, status: str) -> None:
        self.conexao[op_id] = status
        self.bus.publicar({"tipo": "conexao", "operadora": op_id, "status": status})

    def _publicar_status(self, tid: int, status: str, mensagem: str = "") -> None:
        self.banco.atualizar_trabalho(tid, status, mensagem)
        trabalho = (self._partes.get(tid) or {}).get("trabalho") or {}
        self.bus.publicar({"tipo": "trabalho", "trabalho": tid, "status": status, "mensagem": mensagem,
                           "titulo": trabalho.get("titulo"), "modo": trabalho.get("modo"),
                           "tipo_trabalho": trabalho.get("tipo")})

    def _comecou(self, tid: int) -> None:
        with self._mutex:
            info = self._partes.get(tid)
            if info is None or info["comecou"]:
                return
            info["comecou"] = True
        self._publicar_status(tid, "rodando")

    def _terminou(self, tid: int, op_id: str, status: str, mensagem: str = "") -> None:
        """Uma operadora terminou a parte dela. O pedido só termina quando todas terminam."""
        with self._mutex:
            info = self._partes.get(tid)
            if info is None:
                return
            info["faltam"].discard(op_id)
            if op_id:
                info["fins"][op_id] = (status, mensagem)
            if info["faltam"]:
                return
            fins = list(info["fins"].values()) or [("concluido", "")]
        final, msg = max(fins, key=lambda f: (_PESO.get(f[0], 0), f[0] == "cancelado" and "parado" in f[1]))
        self._publicar_status(tid, final, msg)
        with self._mutex:
            self._partes.pop(tid, None)


class _RoboOperadora(threading.Thread):
    """O robô de uma operadora: a sua thread, a sua fila, a sua janela do portal, a sua trava e o seu log."""

    def __init__(self, coordenador: Trabalhador, op_id: str):
        super().__init__(daemon=True, name=f"robo-{op_id}")
        self.c = coordenador
        self.op_id = op_id
        self.banco = coordenador.banco
        self.bus = coordenador.bus
        self.obter_config = coordenador.obter_config
        self.fila: queue.Queue = queue.Queue()
        self.navegador: tuple | None = None      # (contexto, página) enquanto a janela estiver aberta
        self.trava: Trava | None = None          # a trava da pasta desta operadora, com a janela aberta
        self.sessao = None                       # a sessão do último trabalho (para sair do portal)
        self.atual: dict | None = None
        self.na_fila: list[int] = []
        self._cancelados: set[int] = set()
        self._cancelar = threading.Event()
        self._encerrar = threading.Event()
        self._codigo: queue.Queue | None = None  # fila do código de verificação, enquanto o portal espera
        # Protege atual / na_fila / _cancelados / _cancelar entre a thread do servidor e a do robô:
        # "Tirar da fila" e "Parar" nunca se perdem nem caem no pedido errado.
        self._mutex = threading.Lock()
        self._pw = None
        self._ocioso_desde: float | None = None  # fila vazia e robô parado desde quando
        self._proxima_folga = 0.0

    # ------------------------------------------------------------------ chamado pelo coordenador
    def enfileirar(self, parte: dict) -> None:
        with self._mutex:
            self.na_fila.append(parte["id"])
            self.fila.put(parte)

    def lista_da_fila(self) -> list[int]:
        with self._mutex:
            return list(self.na_fila)

    def cancelar(self, tid: int) -> bool:
        with self._mutex:
            if self.atual and self.atual.get("id") == tid:
                self._cancelar.set()
                return True
            if tid in self.na_fila:
                self._cancelados.add(tid)
                return True
            return False

    def receber_codigo(self, codigo: str) -> bool:
        with self._mutex:
            if self._codigo is None:
                return False
            self._codigo.put(codigo)
            return True

    def ocupado(self) -> bool:
        with self._mutex:
            return self.atual is not None

    def pedir_saida(self) -> str:
        with self._mutex:
            if self.atual is not None or self.na_fila:
                return "ocupado"
            if self.navegador is None:
                return "fora"
            self.fila.put({"tipo": "sair", "motivo": "o corretor pediu"})
        return "ok"

    def sair_ao_fechar(self, prazo_s: float) -> threading.Event | None:
        with self._mutex:
            if self.atual is not None or self.navegador is None:
                return None
            feito = threading.Event()
            self.fila.put({"tipo": "sair", "motivo": "a tela foi fechada", "prazo_s": max(1.0, prazo_s - 0.5),
                           "feito": feito})
            return feito

    def encerrar(self) -> None:
        self._encerrar.set()
        self.fila.put(None)

    # ------------------------------------------------------------------ laço
    def run(self) -> None:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            self._pw = pw
            while not self._encerrar.is_set():
                try:
                    trabalho = self.fila.get(timeout=1.0)
                except queue.Empty:
                    self._pulso()
                    self._sair_se_ocioso()
                    continue
                if trabalho is None:
                    break
                if trabalho.get("tipo") == "sair":       # "Sair do portal agora" ou a tela fechando
                    try:
                        self._sair_do_portal(trabalho["motivo"], trabalho.get("prazo_s", 30))
                    finally:
                        if trabalho.get("feito"):
                            trabalho["feito"].set()
                    continue
                with self._mutex:
                    if trabalho["id"] in self.na_fila:
                        self.na_fila.remove(trabalho["id"])
                    cancelado = trabalho["id"] in self._cancelados
                    self._cancelados.discard(trabalho["id"])
                    if not cancelado:
                        self.atual = trabalho
                        self._cancelar.clear()
                if cancelado:
                    self.c._terminou(trabalho["id"], self.op_id, "cancelado", "tirado da fila antes de começar")
                    continue
                self._ocioso_desde = None
                self._executar(trabalho)
                with self._mutex:
                    fila_vazia = not self.na_fila
                if fila_vazia:
                    self._ocioso_desde = time.monotonic()
                    if self._cancelar.is_set():   # Parar sem nada na fila: sai do portal na hora
                        self._sair_do_portal("o corretor parou o robô e a fila ficou vazia")
            self._sair_do_portal("a tela foi fechada", prazo_s=4)   # a tela fechou: tenta sair em poucos segundos
            if self.navegador is not None:
                try:
                    self.navegador[0].close()
                except Exception:  # noqa: BLE001
                    pass
            self._soltar_trava()

    def _conexao(self, status: str) -> None:
        self.c._conexao(self.op_id, status)

    def _executar(self, trabalho: dict) -> None:
        tid = trabalho["id"]          # self.atual já aponta para ele (definido no laço, sob o mutex)
        self.c.ultima_etapa = None
        self.c._comecou(tid)
        status, mensagem = "concluido", ""
        try:
            if trabalho["tipo"] == "conectar":
                self._conectar(trabalho)
            else:
                self._cotar(trabalho)
            if self._cancelar.is_set():
                status, mensagem = "cancelado", "parado a pedido do corretor"
        except Parado:
            status, mensagem = "cancelado", "parado a pedido do corretor"
            st = self.c.conexao.get(self.op_id)
            if st in ("abrindo", "entrando", "aguardando_portal", "aguardando_codigo"):
                self._conexao("desconectado")
            elif st == "ocupado":
                self._conexao("conectado")
        except ErroLogin as e:
            # Frase fixa, sem nada do que foi digitado. A tela mostra a faixa com o link para a engrenagem.
            op_id = getattr(e, "operadora", "") or self.op_id
            self.banco.evento(tid, "login_problema", str(e), {"motivo": e.motivo, "operadora": op_id})
            self.bus.publicar({"tipo": "login_problema", "trabalho": tid, "operadora": op_id,
                               "motivo": e.motivo, "mensagem": str(e)})
            status, mensagem = "erro", str(e)
            self._conexao("desconectado")
        except Exception as e:  # noqa: BLE001
            texto = credenciais.ocultar(str(e).splitlines()[0] if str(e) else type(e).__name__)
            if "Executable doesn't exist" in str(e):
                texto = "o navegador do robô não está instalado: rode instalar.bat (ou playwright install chromium)"
            self.banco.evento(tid, "erro", texto, {"detalhe": credenciais.ocultar(traceback.format_exc()[-2000:])})
            status, mensagem = "erro", texto
            if self.c.conexao.get(self.op_id) in ("ocupado", "abrindo", "entrando", "aguardando_portal",
                                                  "aguardando_codigo"):
                self._conexao("desconectado")
        finally:
            with self._mutex:
                self.atual = None
            self.c._terminou(tid, self.op_id, status, mensagem)

    # ------------------------------------------------------------------ sair do portal
    def _folga_min(self) -> float:
        try:
            op = operadoras.obter(self.op_id)
            return float(op.config(self.obter_config())["execucao"].get("sair_do_portal_min", 3) or 0)
        except Exception:  # noqa: BLE001
            return 3.0

    def _sair_se_ocioso(self) -> None:
        """Fila vazia e robô parado há mais que a folga da operadora: sai do portal e fecha a janela."""
        if self._ocioso_desde is None or self.navegador is None:
            return
        agora = time.monotonic()
        if agora < self._proxima_folga:
            return
        self._proxima_folga = agora + 5          # a configuração é relida a cada 5 s, não a cada segundo
        with self._mutex:
            if self.atual is not None or self.na_fila:
                return
        minutos = self._folga_min()
        if minutos > 0 and agora - self._ocioso_desde >= minutos * 60:
            self._sair_do_portal(f"fila vazia há {minutos:g} min")

    def _sair_do_portal(self, motivo: str, prazo_s: float = 30) -> None:
        """Logout com o robô parado (nunca no meio de uma cotação) e fecha a janela do portal. Na próxima
        cotação o robô entra sozinho de novo."""
        if self.navegador is None:
            return
        par = self._conferir_navegador()
        if par is None:
            return                                 # a janela já tinha sido fechada
        contexto, page = par
        s = self.sessao
        log = s.log if s is not None else logging.getLogger(f"cotacao.{self.op_id}")
        self._conexao("saindo")
        saiu, erro = False, ""
        try:
            if s is not None:
                s.page = page
                s.parar = None                     # sair do portal não é interrompido pelo Parar
                saiu = bool(operadoras.obter(self.op_id).sair(s, prazo_s=prazo_s))
        except Exception as e:  # noqa: BLE001
            erro = credenciais.ocultar((str(e).splitlines() or [type(e).__name__])[0][:200])
        if saiu:
            log.info(f"Saí do portal ({motivo}).")
        else:
            log.warning(f"Não consegui sair do portal ({motivo}){': ' + erro if erro else ''}. Fechei a janela; "
                        "a sessão do portal expira sozinha.")
        self.navegador = None
        self.sessao = None
        try:
            contexto.close()
        except Exception:  # noqa: BLE001
            pass
        self._soltar_trava()
        self._conexao("desconectado")
        self.bus.publicar({"tipo": "saiu_do_portal", "operadora": self.op_id, "motivo": motivo, "ok": saiu})
        self._ocioso_desde = None

    # ------------------------------------------------------------------ peças
    def _pulso(self) -> None:
        """Com o robô parado, o Playwright só entrega eventos (ex.: o corretor fechou a janela do
        portal) quando alguma chamada vai ao navegador. Uma ida e volta por segundo mantém a
        situação da tela certa e solta a trava quando a janela é fechada."""
        if self.navegador is not None:
            self._conferir_navegador()

    def _conferir_navegador(self):
        """Devolve (contexto, página viva) ou None, descartando a janela que foi fechada."""
        contexto, page = self.navegador
        try:
            contexto.cookies()   # ida e volta ao navegador (não depende do estado da página)
            if page.is_closed():
                vivas = [p for p in contexto.pages if not p.is_closed()]
                if not vivas:
                    raise RuntimeError("todas as janelas foram fechadas")
                page = vivas[-1]
                self.navegador = (contexto, page)
            return contexto, page
        except Exception:  # noqa: BLE001
            self.navegador = None
            try:
                contexto.close()
            except Exception:  # noqa: BLE001
                pass
            self._soltar_trava()
            if self.c.conexao.get(self.op_id, "desconectado") != "desconectado":
                self._conexao("desconectado")
            return None

    def _abrir_navegador(self, cfg):
        if self.navegador is not None:
            vivo = self._conferir_navegador()
            if vivo:
                return vivo
        # A trava fica com a tela enquanto a janela da operadora estiver aberta: a linha de comando
        # (ou outra tela) não abre o mesmo perfil do navegador nem mexe no registro ao mesmo tempo.
        self._soltar_trava()
        trava = Trava(cfg["saida"]["pasta"]).__enter__()   # OcupadoErro se outro robô estiver rodando
        self.trava = trava
        self._conexao("abrindo")
        try:
            contexto, page = abrir(self._pw, cfg)
        except Exception:
            self._soltar_trava()
            raise

        def fechou(*_):
            self._conexao("desconectado")
            if self.trava is trava:
                self._soltar_trava()
        contexto.on("close", fechou)
        self.navegador = (contexto, page)
        return contexto, page

    def _soltar_trava(self) -> None:
        trava, self.trava = self.trava, None
        if trava is not None:
            try:
                trava.__exit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass

    def _sessao(self, op, cfg, tid: int, modo: str, reemitir=()):
        pasta = Path(cfg["saida"]["pasta"])
        # Sem login guardado (ou recusado pelo portal): nem abre o portal.
        situacao = credenciais.cofre(cfg, op.id).situacao()
        if not situacao["guardadas"] or situacao["recusadas"]:
            motivo = "recusadas" if situacao["guardadas"] else "sem_credenciais"
            raise ErroLogin(credenciais.mensagem_login(motivo, op.nome), motivo)
        # um log por operadora (cotacao.<operadora>, em saida/<operadora>/logs/): dois robôs não se misturam
        log = configurar_log(pasta / "logs", extra_handler=_ManipuladorTela(self, tid), nome=f"cotacao.{op.id}")
        contexto, page = self._abrir_navegador(cfg)

        def ouvir(tipo, dados):
            if tipo == "plano":
                linha = self.banco.registrar_cotacao(tid, op.id, modo, dados)
                self.bus.publicar({"tipo": "cotacao", "trabalho": tid, "cotacao": linha})
            elif tipo == "precos":
                self.banco.salvar_catalogo(op.id, dados["planos"])
                self.bus.publicar({"tipo": "catalogo", "operadora": op.id})

        def avisar(tipo, **dados):
            evento = {"tipo": tipo, "trabalho": tid, "operadora": op.id, **dados}
            if tipo == "login_entrando":
                self._conexao("entrando")
            elif tipo == "login_aguardando":
                self._conexao("aguardando_portal")
            elif tipo == "login_ok":
                self._conexao("ocupado" if (self.atual or {}).get("tipo") == "cotar" else "conectado")
            elif tipo == "etapa":
                self.c.ultima_etapa = evento
            self.bus.publicar(evento)

        def pedir_codigo():
            """O portal pediu um código de verificação: a tela pede ao corretor e o robô espera."""
            fila: queue.Queue = queue.Queue()
            with self._mutex:
                self._codigo = fila
            self._conexao("aguardando_codigo")
            self.banco.evento(tid, "codigo_necessario", "O portal pediu um código de verificação")
            self.bus.publicar({"tipo": "codigo_necessario", "trabalho": tid, "operadora": op.id})
            fim = time.monotonic() + int(cfg["execucao"].get("timeout_codigo_ms", 300000)) / 1000
            try:
                while time.monotonic() < fim:
                    if self._cancelar.is_set():
                        raise Parado("login")
                    try:
                        return fila.get(timeout=0.5)
                    except queue.Empty:
                        pass
                return None
            finally:
                with self._mutex:
                    self._codigo = None
                self._conexao("entrando")

        return op.nova_sessao(cfg, log, contexto, page, Estado(pasta / "estado.json"),
                              op.resultados(pasta / "resultados.xlsx", log, ouvinte=ouvir),
                              Mapeador(pasta, bool(cfg["execucao"].get("mapear")), log,
                                       url_login=cfg.get("urls", {}).get("login", "")),
                              modo == "ensaio", avisar=avisar, parar=self._cancelar.is_set,
                              pedir_codigo=pedir_codigo, reemitir=reemitir if modo == "emitir" else ())

    def _conectar(self, trabalho: dict) -> None:
        """Testar login: entra no portal (se o portal pedir) e para na tela de módulos, sem cotar."""
        op = operadoras.obter(self.op_id)
        cfg = op.config(self.obter_config())
        try:
            s = self._sessao(op, cfg, trabalho["id"], "ensaio")
            self.sessao = s
            op.login(s)
        except ErroLogin as e:
            e.operadora = op.id
            raise
        self.navegador = (s.contexto, s.page)
        self._conexao("conectado")

    def _cotar(self, trabalho: dict) -> None:
        tid, modo = trabalho["id"], trabalho["modo"]
        total = self.obter_config()
        op = operadoras.obter(self.op_id)
        cfg = op.config(total)
        pedidos = [op.montar_pedido(dados, cfg, linha=i + 1)
                   for item in trabalho["itens"] for i, dados in enumerate(item["pedidos"])]
        if not pedidos or self._cancelar.is_set():
            return
        try:
            # abre (ou reaproveita) a janela e pega a trava; "reemitir" só vem do "Emitir de novo mesmo assim"
            s = self._sessao(op, cfg, tid, modo, trabalho.get("reemitir") or ())
            self.sessao = s
            op.login(s)
        except ErroLogin as e:
            e.operadora = op.id
            raise
        self._conexao("ocupado")
        if modo != "ensaio":
            op.recuperar_pdfs(s)
        for pedido in pedidos:
            if self._cancelar.is_set():
                s.log.warning("Parado a pedido do corretor (o pedido em andamento terminou antes).")
                break
            self.bus.publicar({"tipo": "pedido", "trabalho": tid, "operadora": op.id,
                               "pedido": pedido.id, "cnpj": pedido.cnpj})
            try:
                op.processar(s, pedido)
            except Parado:
                break
            except ErroLogin as e:   # o portal pediu login no meio e não deu: para o trabalho
                e.operadora = op.id
                self.navegador = (s.contexto, s.page)
                raise
            except Exception as e:  # noqa: BLE001  (um pedido não derruba os outros)
                s.log.exception(f"[{pedido.id}] erro inesperado: {e}")
        self.navegador = (s.contexto, s.page)
        try:
            self._conexao("conectado" if op.conectado(s.page) else "desconectado")
        except Exception:  # noqa: BLE001
            self._conexao("desconectado")
