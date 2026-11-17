"""python -m operadoras.bradesco.simulador  ->  sobe o simulador nas portas 8775 (portal) e 8776 (login)."""
import time

from .servidor import Simulador


def main() -> None:
    sim = Simulador(8775, 8776).iniciar()
    print("Simulador do Portal de Negócios Bradesco rodando (Ctrl+C para parar)")
    print(f"  login:  {sim.url_login}")
    print(f"  login de treino (falso): CPF/CNPJ {sim.DOCUMENTO}, senha {sim.SENHA}, "
          f"CPF do intermediário {sim.CPF_INTERMEDIARIO}")
    print("    guarde na engrenagem do robô Bradesco (tela com config_simulador.yaml); o simulador só aceita este")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sim.parar()


if __name__ == "__main__":
    main()
