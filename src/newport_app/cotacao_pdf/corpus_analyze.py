"""Caracterização sanitizada do corpus privado de cotações PDF."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from newport_app.cotacao_pdf.coords_extract import (
    localizar_paginas_tabela_geral,
    localizar_paginas_tabela_sulamerica,
)
from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.maturidade import avaliar_maturidade
from newport_app.cotacao_pdf.ocr import tentar_ocr_pagina
from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
from newport_app.cotacao_pdf.template_families import (
    FAMILIAS,
    FAMILIAS_POR_ID,
    identificar_familia,
    operadora_candidata,
)
from newport_app.models.cotacao_pdf import ExtracaoCotacaoCandidata, OpcaoCotacaoCandidata


@dataclass
class OpcaoResumo:
    plano: str | None
    regime: str | None
    copart_percentual: int | None
    acomodacao: str | None
    faixas: int
    premio_centavos: int | None
    iof_centavos: int | None
    total_centavos: int | None
    reconciliacao_ok: bool | None


@dataclass
class DocumentoCaracterizacao:
    hash_sha256: str
    operadora: str | None
    familia_id: str | None
    familia_rotulo: str | None
    reconhecido: bool
    num_paginas: int
    assinatura: dict[str, Any]
    paginas_relevantes: list[int]
    texto_selecionavel: bool
    ocr_necessario_paginas: list[int]
    metodo_extracao_provavel: str
    opcoes: list[OpcaoResumo]
    premio_documento_centavos: int | None = None
    iof_documento_centavos: int | None = None
    total_documento_centavos: int | None = None
    primeira_parcela_centavos: int | None = None
    validade: str | None = None
    campos_seguros: list[str] = field(default_factory=list)
    campos_revisao: list[str] = field(default_factory=list)
    campos_ausentes: list[str] = field(default_factory=list)
    campos_divergentes: list[str] = field(default_factory=list)
    campos_ambiguos: list[str] = field(default_factory=list)
    alertas: list[dict[str, str]] = field(default_factory=list)
    estado_extracao: str | None = None
    maturidade: dict[str, bool] = field(default_factory=dict)


def _hash_bytes(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _assinatura_estrutural(doc: PdfDocumento) -> dict[str, Any]:
    texto = doc.texto_todo()
    tn = texto.upper()
    ancora_hits = {}
    for rotulo, pattern in [
        ("tabela_geral_premios", r"TABELA GERAL DE PR"),
        ("tabela_precos", r"TABELA DE PRE"),
        ("demonstrativo_total", r"DEMONSTRATIVO TOTAL"),
        ("sem_copart", r"SEM COPART"),
        ("copart_percentual", r"\d{1,2}%\s*DE\s*COPART"),
        ("com_copart", r"COM COPARTICIP"),
        ("faixa_etaria", r"0\s*A\s*18"),
        ("codigo_porto", r"P\d{3}\s*[EQ]"),
        ("bx865j", r"BX865J"),
    ]:
        ancora_hits[rotulo] = bool(re.search(pattern, tn, re.IGNORECASE))
    return {
        "ancoras": ancora_hits,
        "paginas_tabela_porto": [p + 1 for p in localizar_paginas_tabela_geral(doc)],
        "paginas_tabela_sul": [p + 1 for p in localizar_paginas_tabela_sulamerica(doc)],
    }


def _paginas_relevantes(doc: PdfDocumento, assinatura: dict) -> list[int]:
    paginas = set(assinatura.get("paginas_tabela_porto", []))
    paginas.update(assinatura.get("paginas_tabela_sul", []))
    for i in range(doc.numero_paginas):
        t = doc.texto(i).upper()
        if any(
            k in t
            for k in (
                "DEMONSTRATIVO TOTAL",
                "SUBTOTAL",
                "PREMIO SAUDE",
                "PRÊMIO SAÚDE",
                "VALOR TOTAL",
                "PRIMEIRA PARCELA",
            )
        ):
            paginas.add(i + 1)
    return sorted(paginas)


def _diagnostico_texto(doc: PdfDocumento) -> tuple[bool, list[int], str]:
    ocr_paginas: list[int] = []
    for i in range(doc.numero_paginas):
        nativo = doc.texto(i).strip()
        words = doc.palavras_pymupdf(i)
        if len(nativo) < 40 and len(words) < 15:
            ocr_paginas.append(i + 1)
    if not ocr_paginas:
        return True, [], "texto_nativo"
    if all(i in ocr_paginas for i in range(1, doc.numero_paginas + 1)):
        return False, ocr_paginas, "ocr_paginas"
    return True, ocr_paginas, "texto_nativo+coordenadas"


def _inferir_acomodacao(nome: str | None) -> str | None:
    if not nome:
        return None
    u = nome.upper()
    if "APARTAMENTO" in u or " Q " in u or u.endswith(" Q"):
        return "Apartamento"
    if "ENFERMARIA" in u or " E " in u or u.endswith(" E"):
        return "Enfermaria"
    return None


def _resumir_opcao(op: OpcaoCotacaoCandidata) -> OpcaoResumo:
    return OpcaoResumo(
        plano=op.plano_nome.texto if op.plano_nome else None,
        regime=op.regime_copart.texto if op.regime_copart else None,
        copart_percentual=op.copart_percentual.inteiro if op.copart_percentual else None,
        acomodacao=_inferir_acomodacao(op.plano_nome.texto if op.plano_nome else None),
        faixas=len(op.tabela),
        premio_centavos=op.premio_saude.centavos if op.premio_saude else None,
        iof_centavos=op.iof.centavos if op.iof else None,
        total_centavos=op.total_recorrente.centavos if op.total_recorrente else None,
        reconciliacao_ok=op.reconciliacao.ok if op.reconciliacao else None,
    )


def _classificar_campos(ext: ExtracaoCotacaoCandidata) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    seguros: list[str] = []
    revisao: list[str] = []
    ausentes: list[str] = []
    divergentes: list[str] = []
    ambiguos: list[str] = []

    for op in ext.opcoes:
        for fx in op.tabela:
            if fx.valor.centavos is not None and fx.valor.estado == "confirmar":
                seguros.append(f"faixa_{fx.faixa}_valor")
            elif fx.valor.estado == "revisar":
                revisao.append(f"faixa_{fx.faixa}_valor")
            elif fx.valor.estado == "ausente":
                ausentes.append(f"faixa_{fx.faixa}_valor")
        for campo in (
            op.plano_nome,
            op.regime_copart,
            op.premio_saude,
            op.iof,
            op.total_recorrente,
            op.validade_oficial,
        ):
            if campo is None:
                continue
            rotulo = campo.rotulo.lower().replace(" ", "_")
            if campo.estado == "ausente" or campo.centavos is None and campo.texto is None and campo.data is None:
                if campo.estado == "ausente":
                    ausentes.append(rotulo)
            elif campo.estado == "revisar":
                revisao.append(rotulo)
            elif campo.confirmado:
                seguros.append(rotulo)
            elif campo.estado == "confirmar" and campo.centavos is not None:
                seguros.append(rotulo)
        if op.reconciliacao and not op.reconciliacao.ok:
            divergentes.append(f"reconciliacao:{op.plano_nome.texto or op.id}")
        if op.regime_copart and op.regime_copart.estado == "revisar":
            ambiguos.append(f"regime_copart:{op.plano_nome.texto or op.id}")

    for alerta in ext.alertas:
        if alerta.codigo in {"PDF-SUL-003", "PDF-PORTO-003", "PDF-PORTO-005"}:
            ambiguos.append(alerta.codigo)

    return seguros, revisao, ausentes, divergentes, ambiguos


def caracterizar_pdf(conteudo: bytes) -> DocumentoCaracterizacao:
    doc_hash = _hash_bytes(conteudo)
    with PdfDocumento.abrir(conteudo) as doc:
        assinatura = _assinatura_estrutural(doc)
        paginas_rel = _paginas_relevantes(doc, assinatura)
        selecionavel, ocr_pags, metodo = _diagnostico_texto(doc)
        operadora = operadora_candidata(doc)
        familia = identificar_familia(doc)

        resultado = DocumentoCaracterizacao(
            hash_sha256=doc_hash,
            operadora=operadora,
            familia_id=familia.id if familia else None,
            familia_rotulo=familia.rotulo if familia else None,
            reconhecido=familia is not None,
            num_paginas=doc.numero_paginas,
            assinatura=assinatura,
            paginas_relevantes=paginas_rel,
            texto_selecionavel=selecionavel,
            ocr_necessario_paginas=ocr_pags,
            metodo_extracao_provavel=metodo,
            opcoes=[],
        )

        if familia is None or familia.extrator is None:
            resultado.estado_extracao = "template_nao_reconhecido"
            if operadora:
                resultado.alertas.append(
                    {
                        "codigo": "PDF-TPL-001",
                        "mensagem": (
                            f"Operadora «{operadora}» detectada, mas família de template "
                            "não reconhecida — aguarda revisão."
                        ),
                    }
                )
            else:
                resultado.alertas.append(
                    {
                        "codigo": "PDF-F02",
                        "mensagem": "Documento não reconhecido — use entrada manual.",
                    }
                )
            return resultado

        opcoes, alertas, meta = familia.extrator(doc, documento_hash=doc_hash)

        for op in opcoes:
            reconciliar_opcao(op)

        ext = ExtracaoCotacaoCandidata(
            id="caracterizacao",
            estudo_id="corpus",
            versao=0,
            documento=__import__(
                "newport_app.models.cotacao_pdf", fromlist=["DocumentoCotacaoPDF"]
            ).DocumentoCotacaoPDF(
                id="doc",
                nome_arquivo="sanitizado.pdf",
                hash_sha256=doc_hash,
                numero_paginas=doc.numero_paginas,
                operadora_detectada=familia.operadora,
                template_id=familia.id,
                parser_versao=familia.parser_versao,
            ),
            estado="extraido" if opcoes else "ocr_parcial",
            opcoes=opcoes,
            alertas=alertas,
            criado_em=datetime.now(timezone.utc),
        )

        resultado.opcoes = [_resumir_opcao(op) for op in opcoes]
        resultado.estado_extracao = ext.estado
        resultado.premio_documento_centavos = meta.get("premio") or (
            opcoes[0].premio_saude.centavos if opcoes and opcoes[0].premio_saude else None
        )
        resultado.iof_documento_centavos = meta.get("iof") or (
            opcoes[0].iof.centavos if opcoes and opcoes[0].iof else None
        )
        resultado.total_documento_centavos = meta.get("total") or (
            opcoes[0].total_recorrente.centavos if opcoes and opcoes[0].total_recorrente else None
        )
        resultado.primeira_parcela_centavos = meta.get("primeira_parcela")
        if meta.get("validade_oficial"):
            resultado.validade = str(meta["validade_oficial"])
        elif opcoes and opcoes[0].validade_oficial and opcoes[0].validade_oficial.data:
            resultado.validade = opcoes[0].validade_oficial.data.isoformat()

        seg, rev, aus, div, amb = _classificar_campos(ext)
        resultado.campos_seguros = sorted(set(seg))
        resultado.campos_revisao = sorted(set(rev))
        resultado.campos_ausentes = sorted(set(aus))
        resultado.campos_divergentes = sorted(set(div))
        resultado.campos_ambiguos = sorted(set(amb))
        resultado.alertas = [{"codigo": a.codigo, "mensagem": a.mensagem} for a in alertas]
        resultado.maturidade = avaliar_maturidade(ext)

        if meta.get("ocr_utilizado"):
            resultado.metodo_extracao_provavel = "ocr_regional"

        return resultado


def analisar_diretorio(raiz: Path) -> dict[str, Any]:
    documentos: list[dict] = []
    por_familia: dict[str, list[str]] = {}
    nao_reconhecidos: list[str] = []

    for pdf in sorted(raiz.rglob("*.pdf")):
        try:
            car = caracterizar_pdf(pdf.read_bytes())
            rel = pdf.relative_to(raiz)
            operadora_dir = rel.parts[0] if rel.parts else "?"
            registro = {
                "operadora_pasta": operadora_dir,
                **{k: v for k, v in asdict(car).items()},
            }
            documentos.append(registro)
            if car.familia_id:
                por_familia.setdefault(car.familia_id, []).append(car.hash_sha256[:12])
            else:
                nao_reconhecidos.append(car.hash_sha256[:12])
        except Exception as exc:
            documentos.append(
                {
                    "operadora_pasta": pdf.parent.name,
                    "hash_sha256": _hash_bytes(pdf.read_bytes())[:12] if pdf.is_file() else None,
                    "reconhecido": False,
                    "estado_extracao": "erro_leitura",
                    "alertas": [{"codigo": "PDF-F03", "mensagem": str(exc)[:120]}],
                }
            )

    familias_resumo = {}
    for fid, hashes in por_familia.items():
        fam = FAMILIAS_POR_ID.get(fid)
        familias_resumo[fid] = {
            "rotulo": fam.rotulo if fam else fid,
            "operadora": fam.operadora if fam else None,
            "documentos": len(hashes),
            "hashes": hashes,
        }

    cobertura_operadora: dict[str, dict] = {}
    for doc in documentos:
        op = doc.get("operadora") or doc.get("operadora_pasta") or "Desconhecida"
        bucket = cobertura_operadora.setdefault(
            op,
            {"total": 0, "reconhecidos": 0, "familias": {}},
        )
        bucket["total"] += 1
        if doc.get("reconhecido"):
            bucket["reconhecidos"] += 1
            fid = doc.get("familia_id")
            if fid:
                bucket["familias"][fid] = bucket["familias"].get(fid, 0) + 1

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "total_documentos": len(documentos),
        "familias_definidas": len(FAMILIAS),
        "familias_no_corpus": len(por_familia),
        "familias_sem_documento": sorted(set(FAMILIAS_POR_ID) - set(por_familia)),
        "documentos": documentos,
        "familias": familias_resumo,
        "cobertura_por_operadora": cobertura_operadora,
        "nao_reconhecidos_hashes": nao_reconhecidos,
    }


def matriz_cobertura(resumo: dict[str, Any]) -> dict[str, Any]:
    campos = [
        "faixas",
        "plano_nome",
        "regime_copart",
        "premio",
        "iof",
        "total",
        "validade",
        "reconciliacao",
    ]
    matriz: dict[str, Any] = {"por_familia": {}, "prioridade_frequencia": []}

    freq: dict[str, int] = {}
    for fid, info in resumo.get("familias", {}).items():
        freq[fid] = info["documentos"]
        docs_fam = [
            d
            for d in resumo["documentos"]
            if d.get("familia_id") == fid
        ]
        seguro_count = sum(len(d.get("campos_seguros", [])) for d in docs_fam)
        revisao_count = sum(len(d.get("campos_revisao", [])) for d in docs_fam)
        matriz["por_familia"][fid] = {
            "documentos": info["documentos"],
            "campos_extraidos_com_seguranca": sorted(
                {c for d in docs_fam for c in d.get("campos_seguros", [])}
            ),
            "campos_exigem_confirmacao": sorted(
                {c for d in docs_fam for c in d.get("campos_revisao", [])}
            ),
            "campos_ambiguos_frequentes": sorted(
                {c for d in docs_fam for c in d.get("campos_ambiguos", [])}
            ),
            "indice_seguro": seguro_count,
            "indice_revisao": revisao_count,
        }

    matriz["prioridade_frequencia"] = [
        {"familia_id": k, "documentos": v}
        for k, v in sorted(freq.items(), key=lambda x: -x[1])
    ]
    matriz["campos_canonicos"] = campos
    return matriz
