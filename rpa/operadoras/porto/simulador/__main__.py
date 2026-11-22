"""python -m operadoras.porto.simulador  ->  sobe o simulador da Porto na porta 8795."""
import time

from .servidor import Simulador


def main() -> None:
    sim = Simulador(8795)
    sim.iniciar()
    print("Simulador da Porto Seguro Saúde PME rodando (Ctrl+C para parar)")
    print(f"  login:  {sim.url_login}")
    print(f"  login de treino (falso): CPF {sim.CPF}, senha {sim.SENHA}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sim.parar()


if __name__ == "__main__":
    main()
