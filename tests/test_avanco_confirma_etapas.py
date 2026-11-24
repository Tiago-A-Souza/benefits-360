"""O «Próxima etapa» confirma as etapas 1, 2 e 4; a etapa 5 não muda."""

from __future__ import annotations

from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "web" / "src"


def test_12_etapa1_sem_botao_antigo():
    src = (_WEB / "SiscorPanel.jsx").read_text(encoding="utf-8")
    assert "Confirmar beneficiários sem exceção" not in src
    assert "onRegistrarAvanco" in src
    assert "confirmarLoteSiscor" in src


def test_13_etapa2_sem_botao_nem_checkbox():
    src = (_WEB / "ConfigEstudo.jsx").read_text(encoding="utf-8")
    assert "Salvar plano atual" not in src
    assert "Revisei e confirmo as informações do plano atual" not in src
    assert "confirmacaoFinal" not in src
    assert "baseline_escolhido.confirmado = true" in src
    assert "onRegistrarAvanco" in src


def test_14_etapa4_sem_botao_antigo():
    src = (_WEB / "PlanosSelecionadosPanel.jsx").read_text(encoding="utf-8")
    assert "Confirmar atribuições" not in src
    assert "onRegistrarAvanco" in src
    assert "mensagemLacunasAtribuicao" in src


def test_18_etapa5_intacta():
    cmp_src = (_WEB / "comparativo" / "ComparativoExperiencia.jsx").read_text(
        encoding="utf-8"
    )
    gov_src = (_WEB / "apresentacao" / "GovernancaComparativo.jsx").read_text(
        encoding="utf-8"
    )
    painel = (_WEB / "ComparativoPanel.jsx").read_text(encoding="utf-8")
    assert "Confirmar comparativo" in cmp_src
    assert "Exportar HTML" in gov_src
    assert "onRegistrarAvanco" not in painel
    assert "Confirmar beneficiários sem exceção" not in painel
    assert "Salvar plano atual" not in painel
    assert "Confirmar atribuições" not in painel


def test_app_proxima_etapa_chama_confirmacao():
    src = (_WEB / "App.jsx").read_text(encoding="utf-8")
    assert "registrarAvancoEtapa" in src
    assert "avancarEtapaRef" in src
    assert "proximaEtapaClicavel" in src
    # Voltar etapa: a barra lateral navega por hash, não por setPasso do cabeçalho antigo.
    assert "function irAnterior()" in src
    assert "hashEstudo(estudoId, passo - 1)" in src
