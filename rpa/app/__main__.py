"""python -m app  ->  abre a tela do Newport Cotações no navegador (http://127.0.0.1:8600)."""
from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import urllib.request
import webbrowser


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
    args = ap.parse_args(argv)

    from nucleo.registro import carregar_config

    total = carregar_config(args.config)
    porta = args.porta or int((total.get("tela") or {}).get("porta", 8600))
    url = f"http://127.0.0.1:{porta}"

    if _porta_ocupada(porta):
        if _tela_ja_aberta(porta):
            print(f"O Newport Cotações já está aberto. Abrindo a tela de novo: {url}")
            if not args.sem_navegador:
                webbrowser.open(url)
            return 0
        print(f"A porta {porta} está em uso por outro programa. Mude 'tela: porta:' no {args.config}.")
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

    tela = Tela(args.config, porta)
    _sair_ao_fechar_a_janela(tela)
    print(f"Newport Cotações aberto em {url}")
    print("Deixe esta janela aberta enquanto usa a tela. Para encerrar, feche esta janela.")
    if not args.sem_navegador:
        threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(url)), daemon=True).start()
    uvicorn.run(tela.criar_app(), host="127.0.0.1", port=porta, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
