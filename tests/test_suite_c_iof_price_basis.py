"""Suíte C — IOF e price_basis por componente."""

from datetime import date

from newport_motor.engine import calcular
from newport_motor.models import AtribuicaoPlano, Cenario, EstudoInput
from newport_motor.provenance import ComponenteFinanceiro, ProvenienciaCampo
from newport_motor.types import (
    FormatoEstudo,
    OrigemValor,
    PriceBasis,
    RegimeCopartTipo,
    SeveridadeValidacao,
    TipoFiscal,
)
from tests.conftest import opcao_plano, policy_completa, regime, subgrupo_atual, vida_ficticia


def _estudo_iof(tipo_fiscal: TipoFiscal, premio_basis: PriceBasis = PriceBasis.EXCLUI_IOF):
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 1, 1), "sg-1")
    op = opcao_plano("op-1", tipo_fiscal=tipo_fiscal, premio_basis=premio_basis)
    sg = subgrupo_atual(tipo_fiscal=tipo_fiscal)
    cenario = Cenario(
        id="c1",
        atribuicoes=[
            AtribuicaoPlano(id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1")
        ],
    )
    return EstudoInput(
        id="estudo-c",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )


def test_seguradora_aplica_iof():
    estudo = _estudo_iof(TipoFiscal.SEGURADORA)
    result = calcular(estudo, policy_completa())
    vida = result.cenarios[0].secoes[0].subgrupos[0].vidas[0]
    assert vida.proposta_centavos.centavos > 10_000_00


def test_operadora_sem_iof():
    estudo = _estudo_iof(TipoFiscal.OPERADORA)
    result = calcular(estudo, policy_completa())
    vida = result.cenarios[0].secoes[0].subgrupos[0].vidas[0]
    # Faixa 4 para idade ~36
    assert vida.proposta_centavos.centavos == 12_000_00


def test_price_basis_desconhecido_bloqueia():
    estudo = _estudo_iof(TipoFiscal.SEGURADORA)
    estudo.opcoes_plano[0].total_recorrente = ComponenteFinanceiro(
        centavos=12_000_00,
        price_basis=PriceBasis.DESCONHECIDO,
        proveniencia=ProvenienciaCampo(origem=OrigemValor.MANUAL),
    )
    result = calcular(estudo, policy_completa())
    bloqueios = [v for v in result.validacoes if v.severidade == SeveridadeValidacao.BLOQUEANTE]
    assert any(v.codigo == "B-02" for v in bloqueios)
