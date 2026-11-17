"""Linha de comando do robô de cotações (usada na calibragem e por quem prefere terminal).

Para o dia a dia, use a tela:  python -m app   (ou o atalho "Abrir Newport Cotacoes.bat").
O robô entra no portal sozinho com o login guardado na engrenagem da tela (cofre do Windows).

Uso (PowerShell, com o .venv ativo, na pasta do projeto):

  python main.py --validar              confere a planilha, sem abrir o navegador
  python main.py --ensaio --mapear      percorre as telas e PARA antes de emitir (calibragem)
  python main.py                        emite de verdade (pede confirmação digitando EMITIR)
  python main.py --pendencias           lista cotações que precisam de conferência
  python main.py --registro             lista todas as cotações registradas, com a chave
  python main.py --liberar "<chave>"    libera um item depois de conferir no portal

Opções: --operadora sulamerica (padrão) | --linha N | --id X | --planilha arquivo.xlsx | --config arquivo.yaml
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def _args(argv=None):
    ap = argparse.ArgumentParser(description="Robô de cotações (Newport)")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--operadora", default="sulamerica")
    ap.add_argument("--planilha", default="cotacoes.xlsx")
    ap.add_argument("--ensaio", action="store_true", help="percorre as telas e para antes de emitir")
    ap.add_argument("--mapear", action="store_true", help="salva print/HTML/árvore de cada tela em saida/.../mapa")
    ap.add_argument("--validar", action="store_true", help="só valida a planilha")
    ap.add_argument("--linha", type=int, help="processa só a linha N da planilha")
    ap.add_argument("--id", help="processa só o pedido com esse id")
    ap.add_argument("--confirmar", action="store_true",
                    help="não pergunta antes de emitir (use só quando já estiver calibrado)")
    ap.add_argument("--pendencias", action="store_true", help="lista itens que precisam de conferência")
    ap.add_argument("--registro", action="store_true", help="lista todas as cotações registradas (com a chave)")
    ap.add_argument("--liberar", metavar="CHAVE", help="remove um item travado do registro, após conferir")
    ap.add_argument("--criar-modelo", action="store_true", help="gera cotacoes_modelo.xlsx")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # console do Windows
    except Exception:  # noqa: BLE001
        pass
    args = _args(argv)

    import operadoras
    from nucleo.estado import Estado
    from nucleo.registro import carregar_config_com_ajustes, configurar_log, migrar_legado, pasta_saida, retencao_dias
    from nucleo.retencao import limpar as limpar_vencidos
    from nucleo.trava import OcupadoErro, Trava

    op = operadoras.obter(args.operadora)
    if args.criar_modelo:
        op.criar_modelo("cotacoes_modelo.xlsx")
        print("cotacoes_modelo.xlsx criado.")
        return 0

    total = carregar_config_com_ajustes(args.config)   # os mesmos ajustes que a tela usa
    migrar_legado(total)
    cfg = op.config(total)
    if args.mapear:
        cfg["execucao"]["mapear"] = True
    pasta = Path(cfg["saida"]["pasta"])
    log = configurar_log(pasta / "logs")
    limpar_vencidos(pasta_saida(total), retencao_dias(total), log)
    estado = Estado(pasta / "estado.json")   # para as consultas; a execução relê dentro da trava

    if args.pendencias:
        itens = estado.pendencias()
        if not itens:
            print("Nenhuma pendência.")
        for chave, item in itens:
            print(f"{item['status']:<11} protocolo={item.get('protocolo', '-'):<10} chave=\"{chave}\"")
        return 0
    if args.registro:
        itens = estado.dados["itens"]
        if not itens:
            print("Registro vazio.")
        for chave, item in itens.items():
            print(f"{item['status']:<11} protocolo={item.get('protocolo', '-'):<10} {item.get('plano')} | "
                  f"{item.get('acomodacao')} | CNPJ {item.get('cnpj')}\n            chave=\"{chave}\"")
        return 0
    if args.liberar:
        try:
            with Trava(pasta):   # nunca com um robô rodando (tela com o portal aberto ou outro terminal)
                ok = estado.liberar(args.liberar)
        except OcupadoErro as e:
            log.error(str(e))
            return 4
        print("Liberado." if ok else "Chave não encontrada (use --registro para ver as chaves).")
        return 0 if ok else 1

    resultados = op.resultados(pasta / "resultados.xlsx", log)
    try:
        pedidos, erros = op.ler_planilha(args.planilha, cfg)
    except (FileNotFoundError, ValueError) as e:
        log.error(f"Planilha: {e}")
        return 2
    for e in erros:
        log.error(f"Planilha linha {e.linha} ({e.id}): {e.mensagem}")
    resultados.erros_planilha(erros)
    if args.linha:
        pedidos = [p for p in pedidos if p.linha == args.linha]
    if args.id:
        pedidos = [p for p in pedidos if p.id == args.id]
    n_planos = sum(op.qtd_cotacoes(p) for p in pedidos)
    log.info(f"Planilha: {len(pedidos)} pedido(s) válido(s), {len(erros)} com erro, "
             f"até {n_planos} cotação(ões) a emitir.")
    if args.validar:
        return 1 if erros else 0
    if not pedidos:
        log.info("Nada a processar.")
        return 1 if erros else 0

    if args.ensaio:
        log.info("MODO ENSAIO: o robô percorre as telas e para no resumo, sem emitir nada.")
    elif not args.confirmar:
        print(f"\nO robô vai EMITIR até {n_planos} cotação(ões) REAIS no portal da {op.nome} "
              f"({len(pedidos)} empresa(s)). Cada uma gera um protocolo na operadora.")
        if input("Digite EMITIR para continuar: ").strip().upper() != "EMITIR":
            print("Cancelado.")
            return 1

    from playwright.sync_api import sync_playwright

    from nucleo import credenciais
    from nucleo.navegador import ErroLogin, Mapeador, abrir

    def pedir_codigo():
        try:
            return input("O portal pediu um código de verificação. Digite o código que chegou: ").strip()
        except EOFError:
            return None

    inicio = time.monotonic()
    try:
        with Trava(pasta), sync_playwright() as pw:
            estado = Estado(pasta / "estado.json")   # lido só depois da trava (e relido a cada consulta)
            situacao = credenciais.cofre(cfg, op.id).situacao()
            if not situacao["guardadas"] or situacao["recusadas"]:   # sem login: nem abre o portal
                log.error(credenciais.mensagem_login("recusadas" if situacao["guardadas"] else "sem_credenciais",
                                                     op.nome) + " (tela: Robôs > engrenagem > Login)")
                return 5
            contexto, page = abrir(pw, cfg)
            mapa = Mapeador(pasta, bool(cfg["execucao"].get("mapear")), log,
                            url_login=cfg.get("urls", {}).get("login", ""))
            s = op.nova_sessao(cfg, log, contexto, page, estado, resultados, mapa, args.ensaio,
                               pedir_codigo=pedir_codigo)
            try:
                op.login(s)
                if not args.ensaio:
                    op.recuperar_pdfs(s)
                for i, pedido in enumerate(pedidos):
                    try:
                        op.processar(s, pedido)
                    except ErroLogin:
                        raise
                    except Exception as e:  # noqa: BLE001  (última barreira: um pedido não derruba o lote)
                        log.exception(f"[{pedido.id}] erro inesperado: {e}")
                    if i < len(pedidos) - 1:
                        time.sleep(cfg["execucao"].get("pausa_entre_pedidos_s", 3))
                # Fim da fila: sai do portal antes de fechar a janela. Sem isso a sessão fica aberta e a próxima
                # execução (ou o corretor no navegador dele) recebe "já existe um acesso ativo para esse CPF".
                try:
                    if op.sair(s, prazo_s=20):
                        log.info("Saí do portal (fim da fila).")
                    else:
                        log.warning("Não consegui sair do portal (fim da fila); a sessão do portal expira sozinha.")
                except Exception as e:  # noqa: BLE001
                    log.warning("Não consegui sair do portal (fim da fila): "
                                f"{credenciais.ocultar((str(e).splitlines() or [''])[0][:200])}. "
                                "A sessão do portal expira sozinha.")
            except ErroLogin as e:
                log.error(f"Login no portal: {e}")
                return 5
            except KeyboardInterrupt:
                log.warning("Interrompido pelo usuário.")
            finally:
                contexto.close()
    except OcupadoErro as e:
        log.error(str(e))
        return 4

    minutos = (time.monotonic() - inicio) / 60
    log.info(f"Fim em {minutos:.1f} min. Nesta execução: {resultados.contagem or 'nada registrado'}. "
             f"Detalhes em {pasta / 'resultados.xlsx'}.")
    pend = estado.pendencias()
    if pend:
        log.warning(f"{len(pend)} item(ns) pedem conferência: rode  python main.py --pendencias")
    return 0 if not resultados.contagem.get("ERRO") and not resultados.contagem.get("VERIFICAR") else 3


if __name__ == "__main__":
    sys.exit(main())
