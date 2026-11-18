"""Erros de autenticação — mensagem ao cliente, sem detalhe interno."""


class AutenticacaoError(Exception):
    def __init__(self, mensagem: str = "Faça login para continuar.") -> None:
        self.mensagem = mensagem
        super().__init__(mensagem)
