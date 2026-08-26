"""Tradução de pendências de compilação para a interface."""

from __future__ import annotations

from collections import defaultdict

from newport_app.draft_compiler import compile
from newport_app.models.compilation import ErroCompilacao
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import BloqueioComparativo, PendenciaItem
from newport_app.policy.registry import default_registry
from newport_app.rascunho.cenarios_sync import (
    cenarios_sincronizados,
    propostas_fora_dos_cenarios,
    subgrupos_com_vidas,
)

_TRADUCOES: dict[str, tuple[str, str, str]] = {
    "APP-IMP-001": (
        "bloqueio",
        "Tipo fiscal do plano atual",
        "Informe se o plano atual é contrato da seguradora ou da operadora.",
    ),
    "APP-IMP-002": (
        "bloqueio",
        "Regime de coparticipação do plano atual",
        "Selecione o regime de coparticipação de cada plano importado.",
    ),
    "APP-ESC-001": (
        "bloqueio",
        "Data de referência para idades",
        "Informe a data usada para calcular as idades dos beneficiários.",
    ),
    "APP-ESC-002": (
        "bloqueio",
        "Comparação do plano atual",
        "Confirme se a comparação usa o contrato vigente ou o reajustado.",
    ),
    "APP-ESC-003": (
        "bloqueio",
        "Fonte do valor atual",
        "Tabela e fatura coexistem na mesma faixa; confirme qual fonte prevalece.",
    ),
    "APP-FIN-001": (
        "bloqueio",
        "Base de IOF pendente",
        "Informe se cada valor inclui IOF, exclui IOF ou não se aplica.",
    ),
    "APP-FIN-002": (
        "bloqueio",
        "Confirmação de valor pendente",
        "Confirme explicitamente os valores informados manualmente.",
    ),
    "APP-FIN-003": (
        "bloqueio",
        "Valor financeiro incompleto",
        "Há campos monetários sem valor informado.",
    ),
    "APP-QTD-001": (
        "bloqueio",
        "Quantidade cotada na proposta",
        "Informe a quantidade cotada de cada faixa ou confirme zero.",
    ),
    "APP-DOC-001": (
        "bloqueio",
        "Documento de cotação pendente",
        "Conclua a extração ou confirme o PDF antes de calcular.",
    ),
    "APP-BAS-001": (
        "bloqueio",
        "Base IOF inválida",
        "A opção «não se aplica» só é permitida para operadoras sem IOF.",
    ),
    "APP-ET3-001": (
        "bloqueio",
        "Nenhuma cotação cadastrada",
        "Cadastre ao menos uma opção de plano na etapa Cotações.",
    ),
    "APP-ET4-001": (
        "bloqueio",
        "Atribuição de propostas pendente",
        "Confirme qual proposta substitui cada plano atual em todos os cenários.",
    ),
    "APP-ET4-002": (
        "alerta",
        "Propostas fora dos cenários",
        "Há propostas selecionadas na etapa Cotações que não entram em nenhum cenário.",
    ),
}


_ROTULOS_CAMINHO_FIXOS: dict[str, str] = {
    "/escolhas/data_referencia_idade": "Data de referência para idades",
    "/escolhas/baseline_escolhido/confirmado": "Comparação do plano atual",
    "/escolhas/precedencia_atual_vida/confirmado": "Fonte do valor atual",
    "/policy_set_versao": "Versão das políticas do estudo",
}

_ROTULOS_SEGMENTO_CAMINHO: dict[str, str] = {
    "price_basis": "base IOF",
    "valor_centavos": "valor",
    "quantidade_cotada": "quantidade cotada",
    "regime_copart_id": "regime de coparticipação",
    "tipo_fiscal": "tipo fiscal",
    "documento_cotacao_id": "documento de cotação",
    "premio_saude": "prêmio saúde",
    "iof": "IOF",
    "total_recorrente": "total recorrente",
    "total_primeira_parcela": "total da primeira parcela",
    "subtotal_impresso": "subtotal impresso",
    "tabela": "tabela de preços",
    "confirmado": "confirmação",
}


def _opcao_por_referencia(rascunho: RascunhoEstudo, referencia: str):
    try:
        indice = int(referencia)
        if 0 <= indice < len(rascunho.opcoes_proposta):
            return rascunho.opcoes_proposta[indice]
    except ValueError:
        pass
    for opcao in rascunho.opcoes_proposta:
        if opcao.id == referencia:
            return opcao
    return None


def _subgrupo_por_referencia(rascunho: RascunhoEstudo, referencia: str):
    try:
        indice = int(referencia)
        if 0 <= indice < len(rascunho.subgrupos_atuais):
            return rascunho.subgrupos_atuais[indice]
    except ValueError:
        pass
    for subgrupo in rascunho.subgrupos_atuais:
        if subgrupo.id == referencia:
            return subgrupo
    return None


def _rotulo_segmentos_caminho(segmentos: list[str]) -> str | None:
    if not segmentos:
        return None
    partes: list[str] = []
    i = 0
    while i < len(segmentos):
        seg = segmentos[i]
        if seg == "tabela" and i + 1 < len(segmentos) and segmentos[i + 1].isdigit():
            partes.append(f"faixa {segmentos[i + 1]}")
            i += 2
            if i < len(segmentos):
                partes.append(_ROTULOS_SEGMENTO_CAMINHO.get(segmentos[i], segmentos[i]))
                i += 1
            continue
        if seg == "custos_unicos" and i + 1 < len(segmentos) and segmentos[i + 1].isdigit():
            partes.append(f"custo único {segmentos[i + 1]}")
            i += 2
            if i < len(segmentos):
                partes.append(_ROTULOS_SEGMENTO_CAMINHO.get(segmentos[i], segmentos[i]))
                i += 1
            continue
        partes.append(_ROTULOS_SEGMENTO_CAMINHO.get(seg, seg.replace("_", " ")))
        i += 1
    return " · ".join(partes)


def resolver_caminho_compilacao(rascunho: RascunhoEstudo, caminho: str) -> str:
    if caminho in _ROTULOS_CAMINHO_FIXOS:
        return _ROTULOS_CAMINHO_FIXOS[caminho]

    if caminho.startswith("/opcoes_proposta/"):
        resto = caminho.removeprefix("/opcoes_proposta/").split("/")
        opcao = _opcao_por_referencia(rascunho, resto[0])
        nome_opcao = opcao.plano_nome if opcao else resto[0]
        detalhe = _rotulo_segmentos_caminho(resto[1:])
        return f"{nome_opcao} · {detalhe}" if detalhe else nome_opcao

    if caminho.startswith("/subgrupos_atuais/"):
        resto = caminho.removeprefix("/subgrupos_atuais/").split("/")
        subgrupo = _subgrupo_por_referencia(rascunho, resto[0])
        nome_sg = subgrupo.plano_nome if subgrupo else resto[0]
        detalhe = _rotulo_segmentos_caminho(resto[1:])
        return f"{nome_sg} · {detalhe}" if detalhe else nome_sg

    if caminho.startswith("/vidas/"):
        resto = caminho.removeprefix("/vidas/").split("/")
        vida = next((v for v in rascunho.vidas if v.id == resto[0]), None)
        nome_vida = vida.nome if vida else resto[0]
        detalhe = _rotulo_segmentos_caminho(resto[1:])
        return f"{nome_vida} · {detalhe}" if detalhe else nome_vida

    if caminho.startswith("/cenarios/"):
        resto = caminho.removeprefix("/cenarios/").split("/")
        try:
            cenario = rascunho.cenarios[int(resto[0])]
            nome = cenario.rotulo or cenario.id
        except (ValueError, IndexError):
            nome = resto[0]
        detalhe = _rotulo_segmentos_caminho(resto[1:])
        return f"{nome} · {detalhe}" if detalhe else nome

    return caminho


def etapa_erro_compilacao(codigo: str, caminho: str) -> int:
    return _etapa_erro(codigo, caminho)


def acao_sugerida_compilacao(codigo: str) -> str | None:
    if codigo in _TRADUCOES:
        if codigo == "APP-QTD-001":
            return (
                "Na etapa Cotações, abra o PDF, confirme a tabela de cada plano "
                "e clique em «Adicionar ao comparativo» novamente."
            )
        return "Complete a etapa correspondente no fluxo guiado."
    return "Revise os dados nas etapas anteriores."


def bloqueios_comparativo_de_erros(
    rascunho: RascunhoEstudo,
    erros: list[ErroCompilacao],
) -> list[BloqueioComparativo]:
    bloqueios: list[BloqueioComparativo] = []
    for erro in erros:
        bloqueios.append(
            BloqueioComparativo(
                codigo=erro.codigo,
                mensagem=erro.mensagem,
                mensagem_motor=erro.mensagem,
                severidade=erro.severidade,
                alvo_ref=erro.caminho,
                alvo_rotulo=resolver_caminho_compilacao(rascunho, erro.caminho),
                etapa_sugerida=etapa_erro_compilacao(erro.codigo, erro.caminho),
                acao_sugerida=acao_sugerida_compilacao(erro.codigo),
                origem="compilacao",
            )
        )
    return bloqueios


def _etapa_erro(codigo: str, caminho: str) -> int:
    if codigo in ("APP-ET3-001",):
        return 3
    if codigo in ("APP-ET4-001",):
        return 4
    if codigo.startswith("APP-ESC") or codigo.startswith("APP-IMP"):
        return 2
    if "/vidas/" in caminho or "/subgrupos_atuais/" in caminho:
        return 2
    if "/opcoes_proposta/" in caminho or codigo in ("APP-QTD-001", "APP-DOC-001"):
        return 3
    if "/cenarios/" in caminho:
        return 4
    if codigo.startswith("APP-FIN") or codigo == "APP-BAS-001":
        return 2 if "/opcoes_proposta/" not in caminho else 3
    return 2


def _titulo_descricao_agrupados(
    codigo: str,
    titulo: str,
    descricao: str,
    quantidade: int,
) -> tuple[str, str]:
    if quantidade <= 1:
        return titulo, descricao
    rotulos = {
        "APP-FIN-001": f"Base de IOF pendente em {quantidade} valores",
        "APP-FIN-002": f"Confirmação de valor pendente em {quantidade} campos",
        "APP-FIN-003": f"Valor financeiro incompleto em {quantidade} campos",
        "APP-IMP-001": f"Tipo fiscal pendente em {quantidade} planos",
        "APP-IMP-002": f"Regime de coparticipação pendente em {quantidade} planos",
    }
    if codigo in rotulos:
        return rotulos[codigo], descricao
    return titulo, f"{descricao} ({quantidade} ocorrências)."


def _item_de_erro(codigo: str, erros: list[ErroCompilacao]) -> PendenciaItem:
    caminho = erros[0].caminho
    etapa = _etapa_erro(codigo, caminho)
    quantidade = len(erros)
    if codigo in _TRADUCOES:
        tipo, titulo, descricao = _TRADUCOES[codigo]
        titulo, descricao = _titulo_descricao_agrupados(codigo, titulo, descricao, quantidade)
        acao = "Complete a etapa correspondente no fluxo guiado."
        if codigo == "APP-QTD-001":
            acao = (
                "Na etapa Cotações, abra o PDF, confirme a tabela de cada plano "
                "e clique em «Adicionar ao comparativo» novamente."
            )
        return PendenciaItem(
            tipo=tipo,
            titulo=titulo,
            descricao=descricao,
            acao_sugerida=acao,
            codigo=codigo,
            etapa=etapa,
            quantidade=quantidade,
        )
    return PendenciaItem(
        tipo="bloqueio",
        titulo="Informação pendente no estudo",
        descricao=erros[0].mensagem,
        acao_sugerida="Revise os dados nas etapas anteriores.",
        codigo=codigo,
        etapa=etapa,
        quantidade=quantidade,
    )


def pendencias_compilacao(rascunho: RascunhoEstudo) -> list[PendenciaItem]:
    resultado = compile(rascunho, policy_registry=default_registry)
    por_codigo: dict[str, list[ErroCompilacao]] = defaultdict(list)
    for erro in resultado.erros:
        por_codigo[erro.codigo].append(erro)

    itens: list[PendenciaItem] = [
        _item_de_erro(codigo, erros) for codigo, erros in sorted(por_codigo.items())
    ]

    if not rascunho.opcoes_proposta:
        itens.append(
            PendenciaItem(
                tipo="bloqueio",
                titulo="Nenhuma cotação cadastrada",
                descricao="Cadastre ao menos uma opção de plano na etapa Cotações.",
                acao_sugerida="Use a etapa Cotações para incluir a proposta.",
                codigo="APP-ET3-001",
                etapa=3,
                quantidade=1,
            )
        )
    if rascunho.opcoes_proposta and not cenarios_sincronizados(rascunho):
        etapa = 4 if len(rascunho.subgrupos_atuais) > 1 else 3
        descricao = _descricao_cenarios_incompletos(rascunho)
        acao = (
            "Use a etapa «Correspondência com os planos atuais»."
            if etapa == 4
            else "Aguarde a sincronização automática ou revise as cotações."
        )
        itens.append(
            PendenciaItem(
                tipo="bloqueio",
                titulo="Atribuição de propostas pendente",
                descricao=descricao,
                acao_sugerida=acao,
                codigo="APP-ET4-001",
                etapa=etapa,
                quantidade=1,
            )
        )
    elif rascunho.opcoes_proposta and cenarios_sincronizados(rascunho):
        itens.extend(pendencias_propostas_fora_dos_cenarios(rascunho))
    from newport_app.rascunho.acomodacao import pendencias_divergencia_acomodacao

    itens.extend(pendencias_divergencia_acomodacao(rascunho))
    return itens


def _descricao_cenarios_incompletos(rascunho: RascunhoEstudo) -> str:
    if not rascunho.cenarios:
        return (
            "Nenhum cenário montado. Na etapa «Correspondência com os planos atuais», "
            "escolha uma cotação para cada plano vigente."
        )
    if rascunho.formato == "novo" or len(rascunho.subgrupos_atuais) <= 1:
        return "Confirme qual proposta substitui cada plano atual em todos os cenários."

    obrigatorios = set(subgrupos_com_vidas(rascunho))
    op_ids = {op.id for op in rascunho.opcoes_proposta}
    nomes_sg = {
        sg.id: (sg.plano_nome or sg.id) for sg in rascunho.subgrupos_atuais
    }
    lacunas: list[str] = []
    for i, cenario in enumerate(rascunho.cenarios, start=1):
        atrib_por_sg = {
            a.alvo_id: a.opcao_plano_id
            for a in cenario.atribuicoes
            if a.alvo_tipo == "subgrupo"
        }
        faltando = [
            nomes_sg.get(sg_id, sg_id)
            for sg_id in obrigatorios
            if not atrib_por_sg.get(sg_id) or atrib_por_sg.get(sg_id) not in op_ids
        ]
        if faltando:
            lacunas.append(
                f"Cenário {i}: falta escolher cotação para {', '.join(faltando)}"
            )
    if lacunas:
        return " · ".join(lacunas)
    return "Confirme qual proposta substitui cada plano atual em todos os cenários."


def pendencias_propostas_fora_dos_cenarios(rascunho: RascunhoEstudo) -> list[PendenciaItem]:
    """Alerta informativo: propostas da etapa 3 não usadas em nenhum cenário.

    Só em renovação multi — no 1 plano / seguro novo o sync usa todas.
    Não bloqueia o cálculo (Leonardo: não precisa migrar N para N).
    """
    if rascunho.formato == "novo" or len(rascunho.subgrupos_atuais) <= 1:
        return []
    if not cenarios_sincronizados(rascunho):
        return []
    fora_ids = propostas_fora_dos_cenarios(rascunho)
    if not fora_ids:
        return []
    por_id = {op.id: op for op in rascunho.opcoes_proposta}
    nomes = [por_id[i].plano_nome or i for i in fora_ids]
    n = len(nomes)
    lista = ", ".join(nomes[:4])
    if n > 4:
        lista += f" e mais {n - 4}"
    return [
        PendenciaItem(
            tipo="alerta",
            titulo=(
                f"{n} proposta(s) selecionada(s) ficaram fora dos cenários"
                if n > 1
                else "1 proposta selecionada ficou fora dos cenários"
            ),
            descricao=(
                f"{lista}. Continuam disponíveis na etapa Cotações; "
                "só entram no comparativo se forem usadas em algum cenário."
            ),
            acao_sugerida=(
                "Opcional: volte à «Correspondência com os planos atuais» "
                "e inclua-as em um cenário, ou ignore se não quiser compará-las."
            ),
            codigo="APP-ET4-002",
            etapa=4,
            quantidade=n,
        )
    ]