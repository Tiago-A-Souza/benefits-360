"""Normalização para casamento plano × base de rede."""

from __future__ import annotations

from newport_app.presentation.casamento_rede import (
    chave_casamento_rede,
    normalizar_nome_plano_casamento,
)

FLAGS_WESLEY = dict(
    strip_op_prefix=True,
    strip_copart=True,
    strip_reembolso_sul=True,
    strip_paren=True,
    ignore_acom_advance=True,
    acom_full=True,
)


def test_nucleo_em_caixa_alta_executivo():
    chave = chave_casamento_rede(
        "SulAmérica",
        "Executivo R1 Apartamento (Nacional)",
        **FLAGS_WESLEY,
    )
    assert chave == ("SulAmérica", "APTO", "", "EXECUTIVO")


def test_nucleo_rede_executivo_apto():
    chave = chave_casamento_rede(
        "SulAmérica",
        "EXECUTIVO-APTO",
        **FLAGS_WESLEY,
    )
    assert chave == ("SulAmérica", "APTO", "", "EXECUTIVO")


def test_remove_percentual_copart_30():
    chave = chave_casamento_rede(
        "Porto Seguro",
        "BRONZE RIO PRO COPAR Q 30",
        **FLAGS_WESLEY,
    )
    assert chave == ("Porto Seguro", "APTO", "PRO", "BRONZE RIO PRO")


def test_remove_percentuais_copart_20_40_50():
    for pct in ("20", "40", "50"):
        chave = chave_casamento_rede(
            "Porto Seguro",
            f"PRATA RIO PRO COPAR Q {pct}",
            **FLAGS_WESLEY,
        )
        assert chave == ("Porto Seguro", "APTO", "PRO", "PRATA RIO PRO")


def test_copart_adjacente_remove_junto():
    nome = normalizar_nome_plano_casamento(
        "BRONZE BRASIL I E COPAR 30",
        "Porto Seguro",
        strip_op_prefix=True,
        strip_copart=True,
        strip_reembolso_sul=False,
        strip_paren=False,
    )
    assert "30" not in nome.split()
    assert "COPAR" not in nome.upper()


def test_codigo_porto_p420_nao_perde_digitos():
    chave = chave_casamento_rede(
        "Porto Seguro",
        "P420 Q COPAR 30",
        **FLAGS_WESLEY,
    )
    assert "P420" in chave[3]
