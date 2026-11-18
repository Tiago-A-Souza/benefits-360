"""Autenticação do Benefits (Supabase JWT). Sem service_role."""

from newport_app.auth.contexto import UsuarioAtual, id_dono, usuario_atual
from newport_app.auth.erros import AutenticacaoError

__all__ = ["AutenticacaoError", "UsuarioAtual", "id_dono", "usuario_atual"]
