"""Aplicação de IOF — reexporta finance para compatibilidade."""

from newport_motor.finance import (
    aplicar_iof_se_necessario,
    componente_para_recorrente,
    normalizar_vidas_para_recorrente,
    para_base_exclui_iof,
    tipo_fiscal_aplica_iof,
)

__all__ = [
    "tipo_fiscal_aplica_iof",
    "para_base_exclui_iof",
    "aplicar_iof_se_necessario",
    "componente_para_recorrente",
    "normalizar_vidas_para_recorrente",
]
