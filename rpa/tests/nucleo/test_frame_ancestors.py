"""CSP frame-ancestors: allowlist do Benefits, sem DENY absoluto."""
from __future__ import annotations

import urllib.request

from app.servidor import _cabecalhos_seguranca, _origens_frame_ancestors, _origens_permitidas


def test_origens_vem_do_config():
    cfg = {"tela": {"frame_ancestors": ["http://localhost:5173", "http://app.newport.exemplo"]}}
    assert _origens_frame_ancestors(cfg) == ["http://localhost:5173", "http://app.newport.exemplo"]
    assert _origens_frame_ancestors({}) == []
    assert _origens_permitidas({"tela": {"origens_permitidas": ["http://localhost:5173"]}}) == [
        "http://localhost:5173"
    ]


def test_cabecalhos_sem_allowlist_usa_none():
    csp = next(v.decode() for k, v in _cabecalhos_seguranca([]) if k == b"content-security-policy")
    assert "frame-ancestors 'none'" in csp


def test_cabecalhos_com_allowlist_nao_usa_deny():
    headers = _cabecalhos_seguranca(["http://localhost:5173"])
    assert not any(k == b"x-frame-options" and v == b"DENY" for k, v in headers)
    csp = next(v.decode() for k, v in headers if k == b"content-security-policy")
    assert "http://localhost:5173" in csp
    assert "'self'" in csp
    assert "site-malicioso" not in csp