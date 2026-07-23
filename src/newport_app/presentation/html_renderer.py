"""Renderer HTML autocontido — ETAPA 2.8."""

from __future__ import annotations

import html

from newport_app.models.presentation import PresentationViewModel
from newport_app.snapshot.hashing import hash_sha256_objeto

RENDERER_VERSAO = "html@2.8.0"


def render_html(model: PresentationViewModel) -> str:
    meta_hash = hash_sha256_objeto(model.model_dump(mode="json"))
    css = """
    * { box-sizing: border-box; }
    body { font-family: 'Segoe UI', system-ui, sans-serif; margin: 0; color: #1a1a1a; background: #f4f6f8; }
    .page { max-width: 1200px; margin: 0 auto; padding: 24px; background: #fff; min-height: 100vh; }
    @media print {
      body { background: #fff; }
      .page { page-break-after: always; max-width: none; padding: 16px; }
      .no-print { display: none; }
    }
    header { border-bottom: 3px solid #0b5cab; padding-bottom: 12px; margin-bottom: 20px; }
    h1 { color: #0b5cab; margin: 0 0 4px; font-size: 1.6rem; }
    .sub { color: #555; margin: 0; }
    .rascunho { background: #fff3e0; border: 1px solid #ffb74d; padding: 8px 12px; margin: 12px 0; font-weight: 600; color: #e65100; }
    .aviso-pii { background: #fdecea; border: 1px solid #f5c2c0; padding: 8px 12px; margin: 12px 0; }
    table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin: 12px 0 24px; }
    th, td { border: 1px solid #dde2e8; padding: 6px 8px; text-align: left; }
    th { background: #e8f0fa; color: #0b5cab; }
    .secao-regime { margin-top: 28px; page-break-inside: avoid; }
    .secao-regime h2 { font-size: 1.1rem; color: #0b5cab; border-left: 4px solid #0b5cab; padding-left: 8px; }
    .totais { display: flex; flex-wrap: wrap; gap: 16px; margin: 16px 0; }
    .totais div { background: #f4f6f8; padding: 10px 14px; border-radius: 6px; min-width: 180px; }
    .totais strong { display: block; font-size: 0.75rem; color: #555; }
    .ressalvas { font-size: 0.9rem; color: #444; }
    footer.meta { margin-top: 32px; font-size: 0.7rem; color: #888; border-top: 1px solid #eee; padding-top: 8px; }
    """

    partes = [
        "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>",
        f"<title>{html.escape(model.titulo)}</title>",
        f"<style>{css}</style></head><body><div class='page'>",
        "<header>",
        f"<h1>{html.escape(model.titulo)}</h1>",
        f"<p class='sub'>{html.escape(model.subtitulo or '')} · {html.escape(model.data_apresentacao)}</p>",
        "</header>",
        f"<div class='rascunho'>{html.escape(model.aviso_rascunho_interno)}</div>",
    ]

    if model.modo == "beneficiario":
        partes.append(
            "<div class='aviso-pii'>Este material contém nomes de beneficiários. "
            "Mantenha em armazenamento privado.</div>"
        )

    if model.totais_gerais:
        partes.append("<div class='totais'>")
        for chave, valor in model.totais_gerais.items():
            if valor and isinstance(valor, str):
                rotulo = chave.replace("_", " ").title()
                partes.append(f"<div><strong>{html.escape(rotulo)}</strong>{html.escape(valor)}</div>")
        partes.append("</div>")

    for secao in model.secoes_regime:
        partes.append(f"<section class='secao-regime'><h2>{html.escape(secao.regime_rotulo)}</h2>")
        for prop in secao.propostas:
            partes.append(
                f"<p><strong>{html.escape(prop.operadora)} — {html.escape(prop.plano_nome)}</strong>"
                f" · Total: {html.escape(prop.total_mensal_reais or '—')}</p>"
            )
        if model.modo == "faixas":
            for plano in secao.planos_atuais:
                if not plano.faixas:
                    continue
                partes.append(
                    f"<h3>{html.escape(plano.operadora)} — {html.escape(plano.plano_nome)}</h3>"
                )
                partes.append("<table><thead><tr><th>Faixa</th><th>Tit.</th><th>Dep.</th>"
                              "<th>Total vidas</th><th>Atual</th><th>Obs.</th></tr></thead><tbody>")
                for fx in plano.faixas:
                    if fx.qtd_total == 0:
                        continue
                    partes.append(
                        f"<tr><td>{html.escape(fx.rotulo)}</td>"
                        f"<td>{fx.qtd_titulares}</td><td>{fx.qtd_dependentes}</td>"
                        f"<td>{fx.qtd_total}</td>"
                        f"<td>{html.escape(fx.atual_vigente_reais or '—')}</td>"
                        f"<td>{html.escape(fx.observacao_valor or '')}</td></tr>"
                    )
                partes.append("</tbody></table>")
        partes.append("</section>")

    if model.modo == "beneficiario" and model.beneficiarios:
        partes.append("<section class='secao-regime'><h2>Detalhamento por beneficiário</h2>")
        partes.append(
            "<table><thead><tr><th>Nome</th><th>Idade</th><th>Faixa</th>"
            "<th>Parentesco</th><th>Plano atual</th><th>Atual</th>"
        )
        for op_id in model.propostas_selecionadas:
            partes.append(f"<th>Proposta {html.escape(op_id[:8])}</th>")
        partes.append("</tr></thead><tbody>")
        for b in model.beneficiarios:
            partes.append(
                f"<tr><td>{html.escape(b.nome)}</td>"
                f"<td>{b.idade if b.idade is not None else '—'}</td>"
                f"<td>{html.escape(b.faixa_rotulo or '—')}</td>"
                f"<td>{html.escape(b.parentesco or '—')}</td>"
                f"<td>{html.escape(b.plano_atual or '—')}</td>"
                f"<td>{html.escape(b.atual_vigente_reais or '—')}</td>"
            )
            for op_id in model.propostas_selecionadas:
                partes.append(f"<td>{html.escape(b.propostas.get(op_id, '—'))}</td>")
            partes.append("</tr>")
        partes.append("</tbody></table></section>")

    if model.ressalvas:
        partes.append("<section class='ressalvas'><h3>Ressalvas</h3><ul>")
        for r in model.ressalvas:
            partes.append(f"<li>{html.escape(r)}</li>")
        partes.append("</ul></section>")

    partes.extend([
        "<footer class='meta'>",
        f"Modo: {html.escape(model.modo)} · Snapshot: {html.escape(model.snapshot_id[:12])}… · ",
        f"Hash snapshot: {html.escape(model.snapshot_hash[:16])}… · ",
        f"Hash conteúdo: {html.escape(meta_hash[:16])}… · ",
        f"Renderer: {html.escape(model.renderer_versao)} · ",
        f"Gerado: {html.escape(model.gerado_em)}",
        "</footer></div></body></html>",
    ])
    return "".join(partes)
