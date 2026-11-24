"""python -m app  ->  sobe o motor do robô (API em 127.0.0.1:8600). A interface é o Benefits (5173)."""
from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


def _tela_ja_aberta(porta: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/estado", timeout=2) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def _porta_ocupada(porta: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", porta)) == 0


def _sair_ao_fechar_a_janela(tela) -> None:
    """Fechar a janela preta: o Windows avisa e dá uns 5 s antes de encerrar o programa. O robô usa esse
    tempo para sair do portal (com o robô parado); se não der, a sessão expira sozinha no portal."""
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes
    fechar, sair_do_windows, desligar = 2, 5, 6   # CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
    def ao_evento(evento):
        if evento in (fechar, sair_do_windows, desligar):
            try:
                tela.robo.sair_ao_fechar(4.0)
            except Exception:  # noqa: BLE001
                pass
        return False   # segue o encerramento normal (Ctrl+C continua com o uvicorn)

    tela._ao_fechar = ao_evento    # a referência tem de viver enquanto a tela estiver aberta
    try:
        ctypes.windll.kernel32.SetConsoleCtrlHandler(ao_evento, True)
    except Exception:  # noqa: BLE001
        pass


class _Tee:
    def __init__(self, *streams):
        self._s = streams

    def write(self, data):
        for s in self._s:
            try:
                s.write(data)
                s.flush()
            except Exception:  # noqa: BLE001
                pass

    def flush(self):
        for s in self._s:
            try:
                s.flush()
            except Exception:  # noqa: BLE001
                pass

    def reconfigure(self, **kwargs):
        for s in self._s:
            fn = getattr(s, "reconfigure", None)
            if fn:
                try:
                    fn(**kwargs)
                except Exception:  # noqa: BLE001
                    pass


def _ligar_log(caminho: str) -> None:
    p = Path(caminho)
    p.parent.mkdir(parents=True, exist_ok=True)
    arq = p.open("a", encoding="utf-8")
    sys.stdout = _Tee(sys.__stdout__, arq)
    sys.stderr = _Tee(sys.__stderr__, arq)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="Tela do Newport Cotações")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--porta", type=int, default=None)
    ap.add_argument("--sem-navegador", action="store_true", help="não abre o navegador sozinho")
    ap.add_argument("--com-simulador", action="store_true",
                    help="sobe junto o simulador de treino de cada operadora (use com config_simulador.yaml)")
    ap.add_argument("--log", default=None, help="também grava a saída neste arquivo")
    args = ap.parse_args(argv)
    if args.log:
        _ligar_log(args.log)

    from nucleo.instancia import OcupadoErro, TravaPorta, mensagem_porta_config
    from nucleo.registro import carregar_config

    total = carregar_config(args.config)
    porta = args.porta or int((total.get("tela") or {}).get("porta", 8600))
    recusa = mensagem_porta_config(args.config, porta)
    if recusa:
        print(recusa)
        return 2
    url = f"http://127.0.0.1:{porta}"

    if _porta_ocupada(porta):
        if _tela_ja_aberta(porta):
            print("Já existe um robô nesta porta. O que está ligado continua; este atalho não abre outro.")
            print("Motor do robô de cotações em execução. Use o Benefits (http://localhost:5173), aba Cotações.")
            if not args.sem_navegador:
                webbrowser.open("http://localhost:5173")
            return 0
        print(f"A porta {porta} está em uso por outro programa. Mude 'tela: porta:' no {args.config}.")
        return 1

    try:
        trava = TravaPorta(porta)
        trava.__enter__()
    except OcupadoErro as e:
        print(e)
        if _tela_ja_aberta(porta):
            print("O robô que já está no ar continua. Este atalho não abre outro.")
            return 0
        return 1

    if args.com_simulador:
        import operadoras
        from nucleo.credenciais import Cofre
        for op in operadoras.ativas(total) or operadoras.todas():
            treino = op.treino()     # cada operadora entrega o seu simulador (ou nenhum)
            if not treino:
                continue
            try:
                treino["iniciar"]()
                print(f"Simulador da {op.nome} rodando ({treino['portas']}). Nada é emitido de verdade.")
            except OSError:
                print(f"O simulador da {op.nome} já está rodando em outra janela; usando aquele.")
            if (total.get("teste") or {}).get("cofre") == "memoria":
                cofre = Cofre(op.id, memoria=True)   # login de treino, só na memória (nunca o real)
                if not cofre.situacao()["guardadas"]:
                    cofre.guardar(**treino["login_falso"])

    import uvicorn

    from .servidor import Tela

    try:
        tela = Tela(args.config, porta)
        _sair_ao_fechar_a_janela(tela)
        print(f"Motor do robô em {url} (API). Interface: http://localhost:5173 aba Cotações.")
        print(f"Pasta de saída: {tela.pasta}")
        if (total.get("teste") or {}).get("simulador"):
            print("MODO TREINO: esta pasta NÃO é a das cotações reais (saida).")
        print("Deixe esta janela aberta enquanto o Benefits usa o robô. Para encerrar, feche esta janela.")
        if not args.sem_navegador:
            threading.Thread(
                target=lambda: (time.sleep(1.2), webbrowser.open("http://localhost:5173")),
                daemon=True,
            ).start()
        uvicorn.run(tela.criar_app(), host="127.0.0.1", port=porta, log_level="warning")
        return 0
    finally:
        trava.__exit__(None, None, None)


if __name__ == "__main__":
    sys.exit(main())
