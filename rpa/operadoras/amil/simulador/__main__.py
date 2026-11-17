"""python -m operadoras.amil.simulador  ->  sobe o simulador do vendasmil na porta 8785."""
import time

from .servidor import Simulador


def main() -> None:
    sim = Simulador(8785)
    sim.exigir_codigo = True        # como o portal real: todo login pede o código de 8 dígitos
    sim.iniciar()
    print("Simulador do vendasmil (Amil) rodando (Ctrl+C para parar)")
    print(f"  login:  {sim.url_login}")
    print(f"  login de treino (falso): usuário {sim.USUARIO}, senha {sim.SENHA}, código de verificação {sim.CODIGO}")
    print("    guarde o usuário e a senha na engrenagem do robô Amil (tela com config_simulador.yaml); "
          "o código você digita na tela quando ela pedir")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sim.parar()


if __name__ == "__main__":
    main()
