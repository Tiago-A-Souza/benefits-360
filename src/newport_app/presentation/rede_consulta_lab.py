"""Simular Rede — consulta de laboratórios fora de qualquer estudo.

Reaproveita ingestão da Matriz_Laboratorio, CSV de marcas e cobertura binária
da etapa 5. Recorte geográfico vem dos filtros do corretor (UF/município).
Nada aqui grava coisa alguma.
"""

from __future__ import annotations

from collections import defaultdict
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
from newport_app.presentation.laboratorios_principais import (
    BaseLaboratoriosPrincipais,
    casar_unidades_marca,
    carregar_laboratorios_principais,
)
from newport_app.presentation.planos_rede import ColunaRede
from newport_app.presentation.rede_consulta import (
    ConsultaRedeInvalida,
    LIMITE_SEM_FILTRO_GEOGRAFICO,
    _agrupar,
    _chave_coluna,
    _data_base_rede,
    _nome_operadora,
    _normalizar_busca,
    _ordem_municipio,
    _rotulo_municipio,
    exigir_termos_busca,
)
from newport_app.presentation.rede_labs import MARCA_COBERTURA
from newport_app.presentation.rede_matriz_laboratorio import (
    BaseRedeLaboratorio,
    PrestadorRedeLaboratorio,
    carregar_base_rede_laboratorio,
)
from newport_app.siscor_importer.normalize import normalizar_cabecalho

MODO_LABORATORIO = "laboratorio"
MODO_PLANO = "plano"

UFS_PORTO_PROPRIA = frozenset({"SP", "RJ", "DF"})

AVISO_PORTO_MEDSERVICE = (
    "Fora de São Paulo, Rio de Janeiro e Distrito Federal, planos Porto Seguro "
    "utilizam a rede Medservice, que não consta nesta extração — a cobertura "
    "pode aparecer vazia por limitação da base, não por falha do sistema."
)


def _carregar() -> tuple[BaseRedeLaboratorio, BaseLaboratoriosPrincipais]:
    base = carregar_base_rede_laboratorio()
    marcas = carregar_laboratorios_principais()
    return base, marcas


def _celula_preenchida(valor: str | None) -> bool:
    return bool(valor and str(valor).strip())


def _normalizar_filtros(uf: str | None, municipio: str | None) -> tuple[str, str]:
    return (
        (uf or "").strip().upper(),
        normalizar_cabecalho((municipio or "").strip()),
    )


def _passa_geografia(
    p: PrestadorRedeLaboratorio, *, uf: str, municipio: str
) -> bool:
    if uf and p.uf != uf:
        return False
    if municipio and p.chave_municipio != municipio:
        return False
    return True


def _operadora_porto_ou_medservice(nome: str) -> bool:
    n = normalizar_cabecalho(nome)
    if "MEDSERVICE" in n:
        return True
    return "PORTO" in n and "ALEGRE" not in n and "VELHO" not in n


def _aviso_porto(
    colunas: Iterable[ColunaRede] | Iterable[ColunaConsultaRede],
    *,
    uf: str,
    municipio: str,
    operadoras: Sequence[str] | None = None,
) -> str | None:
    """Só depois de uma consulta, e só se o resultado ou o filtro envolver Porto."""
    nomes: list[str] = []
    for c in colunas:
        nomes.append(getattr(c, "operadora", None) or _nome_operadora(c))
        raw = getattr(c, "operadora_raw", "") or ""
        if raw:
            nomes.append(raw)
    if operadoras:
        nomes.extend(operadoras)
    tem_porto = any(_operadora_porto_ou_medservice(n) for n in nomes if n)
    if not tem_porto:
        return None
    uf_alvo = uf or (municipio.split(".", 1)[0] if municipio else "")
    if uf_alvo in UFS_PORTO_PROPRIA:
        return None
    return AVISO_PORTO_MEDSERVICE


def _celulas_unidades(
    unidades: Sequence[PrestadorRedeLaboratorio],
    colunas: Iterable[ColunaRede],
) -> dict[str, str]:
    celulas: dict[str, str] = {}
    for col in colunas:
        if any(_celula_preenchida(u.celulas.get(col.col_idx)) for u in unidades):
            celulas[_chave_coluna(col)] = MARCA_COBERTURA
    return celulas


def _contagem(linhas: Sequence[LinhaConsultaRede], chaves: Sequence[str]) -> dict[str, int]:
    contagem = {ch: 0 for ch in chaves}
    for ln in linhas:
        for ch in chaves:
            val = ln.celulas.get(ch, "")
            if val and val != "—":
                contagem[ch] += 1
    return contagem


def _colunas_consulta(
    colunas_alvo: Sequence[ColunaRede], chaves_com_cobertura: set[str]
) -> list[ColunaConsultaRede]:
    return [
        ColunaConsultaRede(
            chave=_chave_coluna(c),
            operadora=_nome_operadora(c),
            plano=c.rotulo_completo,
        )
        for c in colunas_alvo
        if _chave_coluna(c) in chaves_com_cobertura
    ]


def _casa_texto(palheiro: str, termos: list[list[str]]) -> bool:
    if not termos:
        return True
    return any(all(tok in palheiro for tok in termo) for termo in termos)


def _unidades_no_filtro(
    base: BaseRedeLaboratorio, uf: str, municipio: str
) -> tuple[PrestadorRedeLaboratorio, ...]:
    return tuple(
        p for p in base.prestadores if _passa_geografia(p, uf=uf, municipio=municipio)
    )


def opcoes_simulacao_laboratorio() -> OpcoesSimulacaoRede:
    base, marcas = _carregar()
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
    por_uf: dict[str, list[MunicipioOpcaoSimulacao]] = {}
    for chave in base.municipios:
        uf, _ = chave.split(".", 1)
        por_uf.setdefault(uf, []).append(
            MunicipioOpcaoSimulacao(chave=chave, rotulo=_rotulo_municipio(chave), zonas=[])
        )
    ufs = [
        UfOpcaoSimulacao(
            uf=uf,
            municipios=sorted(muns, key=lambda m: normalizar_cabecalho(m.rotulo)),
        )
        for uf, muns in sorted(por_uf.items())
    ]
    ativas = [m for m in marcas.marcas if m.ativo]
    return OpcoesSimulacaoRede(
        data_base_rede=_data_base_rede(),
        total_prestadores=len(base.prestadores),
        total_principais=len(ativas),
        operadoras=operadoras,
        ufs=ufs,
    )


def _filtrar_colunas(
    base: BaseRedeLaboratorio, operadoras: Sequence[str] | None
) -> list[ColunaRede]:
    ops_f = {normalizar_cabecalho(o) for o in (operadoras or []) if (o or "").strip()}
    return [
        c
        for c in base.colunas
        if not ops_f or normalizar_cabecalho(_nome_operadora(c)) in ops_f
    ]


def _municipios_rotulo(unidades: Sequence[PrestadorRedeLaboratorio]) -> list[str]:
    chaves = sorted({u.chave_municipio for u in unidades}, key=_ordem_municipio)
    return [_rotulo_municipio(c) for c in chaves]


def _linha_marca(
    marca: str, unidades: Sequence[PrestadorRedeLaboratorio], celulas: dict[str, str]
) -> LinhaConsultaRede:
    return LinhaConsultaRede(
        linha_id=f"marca:{normalizar_cabecalho(marca)}",
        prestador=marca,
        prestador_nome=marca,
        municipio=unidades[0].chave_municipio if unidades else "",
        principal=True,
        celulas=celulas,
        municipios=_municipios_rotulo(unidades),
    )


def consultar_por_laboratorio(
    consulta: str | Sequence[str] | None = None,
    *,
    uf: str | None = None,
    municipio: str | None = None,
    operadoras: Sequence[str] | None = None,
    todos: bool = False,
    confirmar: bool = False,
) -> ConsultaRedeResponse:
    """Marcas (ou cada prestador, se `todos`) × planos da matriz, com ✓."""
    termos = exigir_termos_busca(consulta, o_que="laboratório")
    base, marcas = _carregar()
    uf_f, mun_f = _normalizar_filtros(uf, municipio)
    sem_filtro_geo = not (uf_f or mun_f)
    ops_filtro = [o for o in (operadoras or []) if (o or "").strip()]
    colunas_alvo = _filtrar_colunas(base, operadoras)
    no_geo = _unidades_no_filtro(base, uf_f, mun_f)

    if todos:
        candidatos = [
            p
            for p in no_geo
            if _casa_texto(_normalizar_busca(p.prestador), termos)
        ]
        pares = casar_unidades_marca(candidatos, marcas.marcas)
        curados = {u.prestador.linha_idx for u in pares}
        visiveis = candidatos
        ocultos = 0
        total_encontrado = len(candidatos)
        if (
            sem_filtro_geo
            and not confirmar
            and len(visiveis) > LIMITE_SEM_FILTRO_GEOGRAFICO
        ):
            return ConsultaRedeResponse(
                modo=MODO_LABORATORIO,
                total_linhas=0,
                total_encontrado=total_encontrado,
                ocultos_nao_principais=0,
                mostrando_todos=True,
                requer_confirmacao=True,
                aviso=(
                    f"Sem filtro de estado ou município, esta consulta devolve "
                    f"{len(visiveis)} laboratórios. Filtre para reduzir ou confirme "
                    "para listar tudo."
                ),
                data_base_rede=_data_base_rede(),
            )
        linhas: list[LinhaConsultaRede] = []
        chaves_cob: set[str] = set()
        for p in visiveis:
            celulas = _celulas_unidades([p], colunas_alvo)
            chaves_cob.update(celulas)
            linhas.append(
                LinhaConsultaRede(
                    linha_id=f"l{p.linha_idx}",
                    prestador=p.prestador,
                    prestador_nome=p.prestador,
                    municipio=p.chave_municipio,
                    principal=p.linha_idx in curados,
                    celulas=celulas,
                )
            )
        colunas = _colunas_consulta(colunas_alvo, chaves_cob)
        aviso = None
        if not total_encontrado:
            aviso = "Nenhum laboratório da base corresponde à busca e aos filtros."
        return ConsultaRedeResponse(
            modo=MODO_LABORATORIO,
            colunas=colunas,
            blocos=_agrupar(linhas),
            total_linhas=len(linhas),
            total_encontrado=total_encontrado,
            ocultos_nao_principais=ocultos,
            mostrando_todos=True,
            aviso=aviso,
            sem_cobertura=bool(linhas) and not colunas,
            data_base_rede=_data_base_rede(),
            aviso_porto=_aviso_porto(
                colunas, uf=uf_f, municipio=mun_f, operadoras=ops_filtro
            ),
            contagem_por_coluna=_contagem(linhas, [c.chave for c in colunas]),
        )

    pares = casar_unidades_marca(no_geo, marcas.marcas)
    por_marca: dict[str, list[PrestadorRedeLaboratorio]] = defaultdict(list)
    for u in pares:
        por_marca[u.marca].append(u.prestador)
    n_curados = len(pares)
    ocultos = len(no_geo) - n_curados

    linhas_marca: list[LinhaConsultaRede] = []
    chaves_cob = set()
    for marca in marcas.marcas:
        if not marca.ativo:
            continue
        unidades = por_marca.get(marca.marca, [])
        if not unidades:
            continue
        palheiro = _normalizar_busca(
            marca.marca + " " + " ".join(u.prestador for u in unidades)
        )
        if not _casa_texto(palheiro, termos):
            continue
        celulas = _celulas_unidades(unidades, colunas_alvo)
        chaves_cob.update(celulas)
        linhas_marca.append(_linha_marca(marca.marca, unidades, celulas))

    colunas = _colunas_consulta(colunas_alvo, chaves_cob)
    aviso = None
    if not linhas_marca:
        aviso = "Nenhuma marca da lista corresponde à busca e aos filtros."
    elif ocultos > 0:
        aviso = None
    return ConsultaRedeResponse(
        modo=MODO_LABORATORIO,
        colunas=colunas,
        blocos=[
            BlocoConsultaRede(
                titulo="Laboratórios",
                municipio="",
                linhas=linhas_marca,
            )
        ]
        if linhas_marca
        else [],
        total_linhas=len(linhas_marca),
        total_encontrado=len(linhas_marca),
        ocultos_nao_principais=max(ocultos, 0),
        mostrando_todos=False,
        aviso=aviso,
        sem_cobertura=bool(linhas_marca) and not colunas,
        data_base_rede=_data_base_rede(),
        aviso_porto=_aviso_porto(
            colunas, uf=uf_f, municipio=mun_f, operadoras=ops_filtro
        ),
        contagem_por_coluna=_contagem(linhas_marca, [c.chave for c in colunas]),
    )


def consultar_por_plano_laboratorio(
    plano: str,
    *,
    uf: str | None = None,
    municipio: str | None = None,
    todos: bool = False,
    confirmar: bool = False,
) -> ConsultaRedeResponse:
    """Onde o plano cobre laboratório — marcas ou cada prestador."""
    base, marcas = _carregar()
    col = next((c for c in base.colunas if _chave_coluna(c) == str(plano)), None)
    if col is None:
        raise ConsultaRedeInvalida("Plano não encontrado na base de rede.")
    uf_f, mun_f = _normalizar_filtros(uf, municipio)
    sem_filtro_geo = not (uf_f or mun_f)
    no_geo = _unidades_no_filtro(base, uf_f, mun_f)
    cobertos = [p for p in no_geo if _celula_preenchida(p.celulas.get(col.col_idx))]
    coluna = ColunaConsultaRede(
        chave=_chave_coluna(col), operadora=_nome_operadora(col), plano=col.rotulo_completo
    )
    chave = coluna.chave

    if todos:
        if (
            sem_filtro_geo
            and not confirmar
            and len(cobertos) > LIMITE_SEM_FILTRO_GEOGRAFICO
        ):
            return ConsultaRedeResponse(
                modo=MODO_PLANO,
                colunas=[coluna],
                total_linhas=0,
                total_encontrado=len(cobertos),
                ocultos_nao_principais=0,
                mostrando_todos=True,
                requer_confirmacao=True,
                aviso=(
                    f"Sem filtro de estado ou município, esta consulta devolve "
                    f"{len(cobertos)} laboratórios. Filtre para reduzir ou confirme "
                    "para listar tudo."
                ),
                data_base_rede=_data_base_rede(),
                aviso_porto=_aviso_porto([col], uf=uf_f, municipio=mun_f),
            )
        pares = casar_unidades_marca(cobertos, marcas.marcas)
        curados = {u.prestador.linha_idx for u in pares}
        linhas = [
            LinhaConsultaRede(
                linha_id=f"l{p.linha_idx}",
                prestador=p.prestador,
                prestador_nome=p.prestador,
                municipio=p.chave_municipio,
                principal=p.linha_idx in curados,
                celulas={chave: MARCA_COBERTURA},
            )
            for p in cobertos
        ]
        aviso = None
        if not cobertos:
            aviso = "Nenhum laboratório coberto por este plano nos filtros escolhidos."
        return ConsultaRedeResponse(
            modo=MODO_PLANO,
            colunas=[coluna],
            blocos=_agrupar(linhas),
            total_linhas=len(linhas),
            total_encontrado=len(cobertos),
            ocultos_nao_principais=0,
            mostrando_todos=True,
            aviso=aviso,
            data_base_rede=_data_base_rede(),
            aviso_porto=_aviso_porto([col], uf=uf_f, municipio=mun_f),
            contagem_por_coluna=_contagem(linhas, [chave]),
        )

    pares = casar_unidades_marca(cobertos, marcas.marcas)
    por_marca: dict[str, list[PrestadorRedeLaboratorio]] = defaultdict(list)
    for u in pares:
        por_marca[u.marca].append(u.prestador)
    ocultos = len(cobertos) - len(pares)
    linhas_marca: list[LinhaConsultaRede] = []
    for marca in marcas.marcas:
        if not marca.ativo:
            continue
        unidades = por_marca.get(marca.marca, [])
        if not unidades:
            continue
        linhas_marca.append(
            _linha_marca(marca.marca, unidades, {chave: MARCA_COBERTURA})
        )
    aviso = None
    if not linhas_marca:
        aviso = "Nenhuma marca da lista é coberta por este plano nos filtros escolhidos."
    return ConsultaRedeResponse(
        modo=MODO_PLANO,
        colunas=[coluna],
        blocos=[
            BlocoConsultaRede(titulo="Laboratórios", municipio="", linhas=linhas_marca)
        ]
        if linhas_marca
        else [],
        total_linhas=len(linhas_marca),
        total_encontrado=len(linhas_marca),
        ocultos_nao_principais=max(ocultos, 0),
        mostrando_todos=False,
        aviso=aviso,
        data_base_rede=_data_base_rede(),
        aviso_porto=_aviso_porto([col], uf=uf_f, municipio=mun_f),
        contagem_por_coluna=_contagem(linhas_marca, [chave]),
    )
