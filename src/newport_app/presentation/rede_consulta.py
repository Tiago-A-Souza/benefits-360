"""Simular Rede — consulta da rede credenciada fora de qualquer estudo.

Reaproveita o pipeline da etapa 5: `carregar_base_rede_hospital` (matriz
SiscorNet, em cache), `carregar_hospitais_principais` (marcação), o filtro de
especialidade e a regra de rede verticalizada (`_coberto_na_coluna`). Não há
estudo, vidas nem recorte por beneficiário: o recorte vem dos filtros do corretor.

Nada aqui grava coisa alguma.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from newport_app.models.simular_rede import (
    BlocoConsultaRede,
    ColunaConsultaRede,
    ConsultaRedeResponse,
    LinhaConsultaRede,
    MunicipioOpcaoSimulacao,
    OperadoraOpcaoSimulacao,
    OpcoesSimulacaoRede,
    PlanoOpcaoSimulacao,
    UfOpcaoSimulacao,
)
from newport_app.presentation.hospitais_principais import (
    BaseHospitaisPrincipais,
    carregar_hospitais_principais,
)
from newport_app.presentation.planos_rede import ColunaRede
from newport_app.presentation.rede_codigos import (
    formatar_cobertura_abreviada,
    sigla_zona_capital,
)
from newport_app.presentation.rede_matriz_hospital import (
    BaseRedeHospital,
    PrestadorRedeHospital,
    carregar_base_rede_hospital,
    data_base_rede_formatada,
)
from newport_app.presentation.rede_prestador_rotulo import nome_prestador_para_rotulo
from newport_app.presentation.rede_recorte import parse_municipio_base
from newport_app.presentation.rede_visao import _coberto_na_coluna
from newport_app.siscor_importer.normalize import normalizar_cabecalho

MODO_HOSPITAL = "hospital"
MODO_PLANO = "plano"

# Acima disto, sem nenhum filtro geográfico, a consulta por plano pede confirmação.
LIMITE_SEM_FILTRO_GEOGRAFICO = 100

_CAPITAIS_COM_ZONA = frozenset({"SP.SAO PAULO", "RJ.RIO DE JANEIRO"})

# Palavras que a base abrevia ou omite («HOSP SAMARITANO», «H ISRAELITA…»):
# não podem impedir o casamento de «Hospital Samaritano».
_PALAVRAS_GENERICAS = frozenset(
    {
        "HOSPITAL",
        "HOSP",
        "H",
        "CLINICA",
        "CLIN",
        "CENTRO",
        "CTO",
        "DE",
        "DA",
        "DO",
        "DAS",
        "DOS",
        "E",
    }
)

_RE_NAO_ALFANUM = re.compile(r"[^A-Z0-9]+")
_RE_SEPARA_TERMOS = re.compile(r"[;,\n|]+")


class ConsultaRedeInvalida(ValueError):
    """Parâmetro inválido (plano inexistente, termo ausente…)."""


# --------------------------------------------------------------------------
# Texto
# --------------------------------------------------------------------------


def _normalizar_busca(texto: object) -> str:
    return _RE_NAO_ALFANUM.sub(" ", normalizar_cabecalho(texto)).strip()


def _tokens_termo(termo: str) -> list[str]:
    tokens = _normalizar_busca(termo).split()
    uteis = [t for t in tokens if t not in _PALAVRAS_GENERICAS]
    return uteis or tokens


def termos_de_busca(consulta: str | Sequence[str] | None) -> list[list[str]]:
    """«Einstein; Sírio-Libanês» → [['EINSTEIN'], ['SIRIO', 'LIBANES']]."""
    if consulta is None:
        return []
    if isinstance(consulta, str):
        pedacos: Iterable[str] = _RE_SEPARA_TERMOS.split(consulta)
    else:
        pedacos = [p for item in consulta for p in _RE_SEPARA_TERMOS.split(item or "")]
    saida: list[list[str]] = []
    for pedaco in pedacos:
        tokens = _tokens_termo(pedaco)
        if tokens:
            saida.append(tokens)
    return saida


def exigir_termos_busca(
    consulta: str | Sequence[str] | None, *, o_que: str
) -> list[list[str]]:
    """Exige ao menos um termo; busca vazia nunca lista a base inteira."""
    termos = termos_de_busca(consulta)
    if not termos:
        raise ConsultaRedeInvalida(f"Digite o nome de ao menos um {o_que}.")
    return termos


def _prestador_casa(p: PrestadorRedeHospital, termos: list[list[str]]) -> bool:
    palheiro = _normalizar_busca(f"{p.prestador} {p.bairro}")
    return any(all(tok in palheiro for tok in termo) for termo in termos)


# --------------------------------------------------------------------------
# Atributos do prestador
# --------------------------------------------------------------------------


def _titulo_municipio(chave: str) -> str:
    uf, cidade = parse_municipio_base(chave)
    return f"{cidade.title()} · {uf}"


def _rotulo_municipio(chave: str) -> str:
    uf, cidade = parse_municipio_base(chave)
    return cidade.title()


def _zona_prestador(p: PrestadorRedeHospital, ent) -> str:
    zona_csv = ((ent.zona if ent else "") or "").strip()
    return zona_csv or (p.regiao or "").strip()


def _linha_id(p: PrestadorRedeHospital) -> str:
    return f"l{p.linha_idx}"


def _chave_coluna(col: ColunaRede) -> str:
    return str(col.col_idx)


def _nome_operadora(col: ColunaRede) -> str:
    return col.operadora_canon or col.operadora_raw or "—"


def _ordem_municipio(chave: str) -> tuple:
    uf, _ = parse_municipio_base(chave)
    cap = 0 if chave in _CAPITAIS_COM_ZONA else 1
    return (cap, uf, chave)


def _ordem_linha(ln: LinhaConsultaRede) -> tuple:
    sigla = ln.zona_sigla if ln.municipio in _CAPITAIS_COM_ZONA else ""
    return (sigla, ln.prestador_nome, ln.bairro)


# --------------------------------------------------------------------------
# Contexto carregado (cache em memória)
# --------------------------------------------------------------------------


def _carregar() -> tuple[BaseRedeHospital, BaseHospitaisPrincipais]:
    base = carregar_base_rede_hospital()
    principais = carregar_hospitais_principais(prestadores_matriz=base.prestadores)
    return base, principais


def _data_base_rede() -> str:
    return data_base_rede_formatada()


# --------------------------------------------------------------------------
# Opções (selects da tela)
# --------------------------------------------------------------------------


def opcoes_simulacao() -> OpcoesSimulacaoRede:
    base, principais = _carregar()

    por_operadora: dict[str, list[PlanoOpcaoSimulacao]] = {}
    for col in base.colunas:
        por_operadora.setdefault(_nome_operadora(col), []).append(
            PlanoOpcaoSimulacao(chave=_chave_coluna(col), rotulo=col.rotulo_completo)
        )
    operadoras = [
        OperadoraOpcaoSimulacao(
            nome=nome,
            planos=sorted(planos, key=lambda x: x.rotulo.casefold()),
        )
        for nome, planos in sorted(por_operadora.items(), key=lambda kv: kv[0].casefold())
    ]

    zonas_por_mun: dict[str, set[str]] = {}
    for p in base.prestadores:
        ent = principais.por_prestador_matriz.get(p.chave)
        zonas = zonas_por_mun.setdefault(p.chave_municipio, set())
        zona = _zona_prestador(p, ent)
        if zona:
            zonas.add(zona)

    por_uf: dict[str, list[MunicipioOpcaoSimulacao]] = {}
    for chave, zonas in zonas_por_mun.items():
        uf, _ = parse_municipio_base(chave)
        por_uf.setdefault(uf, []).append(
            MunicipioOpcaoSimulacao(
                chave=chave,
                rotulo=_rotulo_municipio(chave),
                zonas=sorted(zonas),
            )
        )
    ufs = [
        UfOpcaoSimulacao(
            uf=uf,
            municipios=sorted(muns, key=lambda m: normalizar_cabecalho(m.rotulo)),
        )
        for uf, muns in sorted(por_uf.items())
    ]

    return OpcoesSimulacaoRede(
        data_base_rede=_data_base_rede(),
        total_prestadores=len(base.prestadores),
        total_principais=sum(
            1
            for p in base.prestadores
            if (ent := principais.por_prestador_matriz.get(p.chave)) and ent.principal
        ),
        operadoras=operadoras,
        ufs=ufs,
    )


# --------------------------------------------------------------------------
# Consulta
# --------------------------------------------------------------------------


def _passa_geografia(
    p: PrestadorRedeHospital,
    zona: str,
    *,
    uf: str,
    municipio: str,
    zona_filtro: str,
) -> bool:
    if uf and p.uf != uf:
        return False
    if municipio and p.chave_municipio != municipio:
        return False
    if zona_filtro and normalizar_cabecalho(zona) != zona_filtro:
        return False
    return True


def _normalizar_filtros(
    uf: str | None, municipio: str | None, zona: str | None
) -> tuple[str, str, str]:
    return (
        (uf or "").strip().upper(),
        normalizar_cabecalho((municipio or "").strip()),
        normalizar_cabecalho((zona or "").strip()),
    )


def _celulas_prestador(
    p: PrestadorRedeHospital,
    ent,
    colunas: Iterable[ColunaRede],
) -> dict[str, str]:
    celulas: dict[str, str] = {}
    for col in colunas:
        cob, val = _coberto_na_coluna(
            p, col.col_idx, col.operadora_canon or "", entrada_principal=ent
        )
        codigo = formatar_cobertura_abreviada(val, coberto=cob)
        if codigo:
            celulas[_chave_coluna(col)] = codigo
    return celulas


def _montar_linha(
    p: PrestadorRedeHospital, ent, celulas: dict[str, str]
) -> LinhaConsultaRede:
    zona = _zona_prestador(p, ent)
    sigla = sigla_zona_capital(zona) if p.chave_municipio in _CAPITAIS_COM_ZONA else ""
    nome = nome_prestador_para_rotulo(p.prestador, p.bairro or "")
    return LinhaConsultaRede(
        linha_id=_linha_id(p),
        prestador=p.prestador,
        prestador_nome=nome,
        municipio=p.chave_municipio,
        bairro=p.bairro or "",
        zona=zona,
        zona_sigla=sigla,
        principal=bool(ent and ent.principal),
        rede_verticalizada=(ent.rede_verticalizada if ent else "") or "",
        celulas=celulas,
    )


def _agrupar(linhas: list[LinhaConsultaRede]) -> list[BlocoConsultaRede]:
    por_mun: dict[str, list[LinhaConsultaRede]] = {}
    for ln in linhas:
        por_mun.setdefault(ln.municipio, []).append(ln)
    blocos: list[BlocoConsultaRede] = []
    for mun in sorted(por_mun, key=_ordem_municipio):
        blocos.append(
            BlocoConsultaRede(
                titulo=_titulo_municipio(mun),
                municipio=mun,
                linhas=sorted(por_mun[mun], key=_ordem_linha),
            )
        )
    return blocos


def consultar_por_hospital(
    consulta: str | Sequence[str] | None,
    *,
    uf: str | None = None,
    municipio: str | None = None,
    zona: str | None = None,
    operadoras: Sequence[str] | None = None,
    todos: bool = False,
) -> ConsultaRedeResponse:
    """Quais planos cobrem o(s) hospital(is) digitado(s) — uma linha por unidade."""
    termos = exigir_termos_busca(consulta, o_que="hospital")
    base, principais = _carregar()
    uf_f, mun_f, zona_f = _normalizar_filtros(uf, municipio, zona)

    ops_f = {normalizar_cabecalho(o) for o in (operadoras or []) if (o or "").strip()}
    colunas_alvo = [
        c
        for c in base.colunas
        if not ops_f or normalizar_cabecalho(_nome_operadora(c)) in ops_f
    ]

    candidatos: list[tuple[PrestadorRedeHospital, object]] = []
    for p in base.prestadores:
        if not _prestador_casa(p, termos):
            continue
        ent = principais.por_prestador_matriz.get(p.chave)
        if not _passa_geografia(
            p, _zona_prestador(p, ent), uf=uf_f, municipio=mun_f, zona_filtro=zona_f
        ):
            continue
        candidatos.append((p, ent))

    total_encontrado = len(candidatos)
    visiveis = [
        (p, ent) for p, ent in candidatos if todos or (ent is not None and ent.principal)
    ]
    ocultos = total_encontrado - len(visiveis)

    linhas: list[LinhaConsultaRede] = []
    chaves_com_cobertura: set[str] = set()
    for p, ent in visiveis:
        # Sem cobertura em nenhum plano → linha vazia, mas ela fica na tabela.
        celulas = _celulas_prestador(p, ent, colunas_alvo)
        chaves_com_cobertura.update(celulas)
        linhas.append(_montar_linha(p, ent, celulas))

    colunas = [
        ColunaConsultaRede(
            chave=_chave_coluna(c), operadora=_nome_operadora(c), plano=c.rotulo_completo
        )
        for c in colunas_alvo
        if _chave_coluna(c) in chaves_com_cobertura
    ]

    aviso = None
    if not total_encontrado:
        aviso = "Nenhum prestador da base corresponde à busca e aos filtros."
    elif not visiveis:
        aviso = (
            f"{ocultos} resultado(s) não são hospitais principais — "
            "use «Ver todos» para listá-los."
        )
    return ConsultaRedeResponse(
        modo=MODO_HOSPITAL,
        colunas=colunas,
        blocos=_agrupar(linhas),
        total_linhas=len(linhas),
        total_encontrado=total_encontrado,
        ocultos_nao_principais=ocultos,
        mostrando_todos=todos,
        aviso=aviso,
        sem_cobertura=bool(linhas) and not colunas,
        data_base_rede=_data_base_rede(),
    )


def consultar_por_plano(
    plano: str,
    *,
    uf: str | None = None,
    municipio: str | None = None,
    zona: str | None = None,
    todos: bool = False,
    confirmar: bool = False,
) -> ConsultaRedeResponse:
    """Onde o plano atende — prestadores agrupados por município."""
    base, principais = _carregar()
    col = next((c for c in base.colunas if _chave_coluna(c) == str(plano)), None)
    if col is None:
        raise ConsultaRedeInvalida("Plano não encontrado na base de rede.")
    uf_f, mun_f, zona_f = _normalizar_filtros(uf, municipio, zona)
    sem_filtro_geo = not (uf_f or mun_f or zona_f)

    cobertos: list[tuple[PrestadorRedeHospital, object, dict[str, str]]] = []
    for p in base.prestadores:
        ent = principais.por_prestador_matriz.get(p.chave)
        if not _passa_geografia(
            p, _zona_prestador(p, ent), uf=uf_f, municipio=mun_f, zona_filtro=zona_f
        ):
            continue
        celulas = _celulas_prestador(p, ent, [col])
        if not celulas:
            continue
        cobertos.append((p, ent, celulas))

    total_encontrado = len(cobertos)
    visiveis = [
        t for t in cobertos if todos or (t[1] is not None and t[1].principal)
    ]
    ocultos = total_encontrado - len(visiveis)
    coluna = ColunaConsultaRede(
        chave=_chave_coluna(col), operadora=_nome_operadora(col), plano=col.rotulo_completo
    )

    if sem_filtro_geo and not confirmar and len(visiveis) > LIMITE_SEM_FILTRO_GEOGRAFICO:
        return ConsultaRedeResponse(
            modo=MODO_PLANO,
            colunas=[coluna],
            total_linhas=0,
            total_encontrado=total_encontrado,
            ocultos_nao_principais=ocultos,
            mostrando_todos=todos,
            requer_confirmacao=True,
            aviso=(
                f"Sem filtro de estado, município ou zona, esta consulta devolve "
                f"{len(visiveis)} prestadores. Filtre para reduzir ou confirme para listar tudo."
            ),
            data_base_rede=_data_base_rede(),
        )

    linhas = [_montar_linha(p, ent, celulas) for p, ent, celulas in visiveis]
    aviso = None
    if not total_encontrado:
        aviso = "Nenhum prestador coberto por este plano nos filtros escolhidos."
    elif not visiveis:
        aviso = (
            f"{ocultos} prestador(es) coberto(s) não são principais — "
            "use «Ver todos» para listá-los."
        )
    return ConsultaRedeResponse(
        modo=MODO_PLANO,
        colunas=[coluna],
        blocos=_agrupar(linhas),
        total_linhas=len(linhas),
        total_encontrado=total_encontrado,
        ocultos_nao_principais=ocultos,
        mostrando_todos=todos,
        aviso=aviso,
        data_base_rede=_data_base_rede(),
    )
