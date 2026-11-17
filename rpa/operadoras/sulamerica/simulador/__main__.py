"""python -m operadoras.sulamerica.simulador  ->  sobe o simulador nas portas 8765 (portal) e 8766 (cotador novo)."""
import time

from .servidor import Simulador


def main() -> None:
    sim = Simulador(8765, 8766).iniciar()
    print("Simulador do Cotador SulAmérica rodando (Ctrl+C para parar)")
    print(f"  login:  {sim.url_login}")
    print(f"  login de treino (falso): CPF {sim.CPF}, e-mail {sim.EMAIL}, senha {sim.SENHA}")
    print("    guarde na engrenagem do robô (tela com config_simulador.yaml); o simulador só aceita este")
    print("  em outro terminal:  python -m app --config config_simulador.yaml   (a tela)")
    print("                  ou:  python main.py --config config_simulador.yaml --planilha cotacoes_modelo.xlsx")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sim.parar()


if __name__ == "__main__":
    main()
