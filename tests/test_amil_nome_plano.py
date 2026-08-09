"""Amil: nome do plano na vizinhança da tabela + acomodação QC/QP."""

from __future__ import annotations

from pathlib import Path

import pytest

from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.parsers import amil

_LUNVOX = Path(r"C:\Users\tiago\Downloads\LUNVOX-20260809T012504Z-1-001\LUNVOX")
_IVTEC = Path(r"C:\Users\tiago\Downloads\IVTEC-20260808T230709Z-1-001\IVTEC")
_CORPUS_AMIL = Path(".private/corpus")

_FRAGMENTOS_PROIBIDOS = ("mais", "marca", "empresas", "queridas", "valiosa", "benefícios")


def _pasta_cotacoes(raiz: Path) -> Path | None:
    if not raiz.is_dir():
        return None
    for p in raiz.rglob("*"):
        if p.is_dir() and "COTA" in p.name.upper():
            return p
    return None


def _pdf_lunvox(nome_parte: str) -> Path | None:
    pasta = _pasta_cotacoes(_LUNVOX)
    if pasta is None:
        return None
    return next((p for p in pasta.glob("AMIL*.pdf") if nome_parte.upper() in p.name.upper()), None)


def _parse(path: Path):
    with PdfDocumento.abrir(path.read_bytes()) as doc:
        return amil.parse(doc, documento_hash="h")


def test_eh_nome_plano_amil_aceita_produto_e_rejeita_institucional():
    assert amil._eh_nome_plano_amil("PRATA QC COPART")
    assert amil._eh_nome_plano_amil("PRATA QC COPART 5 4 10 4 6 2 0 0 0 0 31")
    assert amil._eh_nome_plano_amil("BRONZE SP MAIS COPART TP")
    assert amil._eh_nome_plano_amil("OURO QP R COPART")
    assert amil._eh_nome_plano_amil("AMIL S750 R1 QP NAC")
    assert not amil._eh_nome_plano_amil("mais")
    assert not amil._eh_nome_plano_amil("mais vidas")
    assert not amil._eh_nome_plano_amil("Amil é a 11ª marca mais valiosa do Brasil")
    assert not amil._eh_nome_plano_amil("E mais, cada linha de produto")


def test_inferir_acomodacao_qc_qp():
    assert amil._inferir_acomodacao_amil("PRATA QC COPART") == "Enfermaria"
    assert amil._inferir_acomodacao_amil("PRATA QP COPART") == "Apartamento"
    assert amil._inferir_acomodacao_amil("PLATINUM R1 COPART") is None


def test_lunvox_prata_qc_qp():
    path = _pdf_lunvox("PRATA")
    if path is None:
        pytest.skip("Lunvox Amil Prata indisponível")
    ops, _, _ = _parse(path)
    nomes = [(op.plano_nome.texto or "") for op in ops]
    assert nomes == ["PRATA QC COPART", "PRATA QP COPART"]
    assert (ops[0].acomodacao.texto if ops[0].acomodacao else None) == "Enfermaria"
    assert (ops[1].acomodacao.texto if ops[1].acomodacao else None) == "Apartamento"
    for nome in nomes:
        baixo = nome.lower()
        assert baixo not in _FRAGMENTOS_PROIBIDOS
        assert not any(frag == baixo for frag in _FRAGMENTOS_PROIBIDOS)


@pytest.mark.parametrize(
    "parte,esperados",
    [
        (
            "OURO",
            [
                ("PRATA QC COPART", "Enfermaria"),
                ("OURO QP R COPART", "Apartamento"),
            ],
        ),
        (
            "PLATINUM",
            [
                ("PRATA QC COPART", "Enfermaria"),
                ("PLATINUM R1 COPART", None),
            ],
        ),
        (
            "S750",
            [
                ("PRATA QC COPART", "Enfermaria"),
                ("AMIL S750 R1 QP NAC COPART PJ", "Apartamento"),
            ],
        ),
    ],
)
def test_lunvox_demais_produtos(parte: str, esperados: list[tuple[str, str | None]]):
    path = _pdf_lunvox(parte)
    if path is None:
        pytest.skip(f"Lunvox Amil {parte} indisponível")
    ops, _, _ = _parse(path)
    assert len(ops) == len(esperados)
    for op, (nome, acomod) in zip(ops, esperados, strict=True):
        assert (op.plano_nome.texto or "") == nome
        assert (op.acomodacao.texto if op.acomodacao else None) == acomod
        baixo = (op.plano_nome.texto or "").lower().strip()
        assert baixo not in {"mais", "mais vidas", "marca", "empresas"}


def test_ivtec_bronze_mantem_mais_no_nome():
    path = next(_IVTEC.rglob("*BRONZE*.pdf"), None) if _IVTEC.is_dir() else None
    if path is None:
        pytest.skip("IVTEC Bronze indisponível")
    ops, _, _ = _parse(path)
    assert len(ops) == 1
    nome = ops[0].plano_nome.texto or ""
    assert "BRONZE" in nome.upper()
    assert "MAIS" in nome.upper()
    assert nome.upper() == "BRONZE SP MAIS COPART TP"


def test_ivtec_prata_nome_correto():
    path = next(_IVTEC.rglob("*PRATA*TP.pdf"), None) if _IVTEC.is_dir() else None
    if path is None:
        pytest.skip("IVTEC Prata indisponível")
    ops, _, _ = _parse(path)
    assert len(ops) == 1
    assert (ops[0].plano_nome.texto or "").upper() == "PRATA QC COPART TP"
    assert (ops[0].acomodacao.texto if ops[0].acomodacao else None) == "Enfermaria"


@pytest.mark.private_corpus
def test_corpus_amil_sem_fragmento_institucional():
    pasta = next(_CORPUS_AMIL.rglob("Amil"), None) if _CORPUS_AMIL.is_dir() else None
    if pasta is None or not pasta.is_dir():
        pytest.skip("Corpus Amil indisponível")
    arquivos = sorted(pasta.glob("AMIL*.pdf"))
    assert arquivos
    for path in arquivos:
        ops, _, _ = _parse(path)
        assert ops, path.name
        for op in ops:
            nome = (op.plano_nome.texto or "").strip()
            baixo = nome.lower()
            assert baixo not in {"mais", "mais vidas"}
            assert "marca" not in baixo
            assert "empresas" not in baixo
            if not nome.startswith("Plano "):
                assert amil._eh_nome_plano_amil(nome), (path.name, nome)
