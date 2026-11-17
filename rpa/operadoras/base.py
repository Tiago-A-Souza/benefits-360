"""O "encaixe" que toda operadora implementa.

A tela e a linha de comando só conversam com esta interface. Para criar uma operadora
nova (Amil, Bradesco, Porto...), crie a pasta operadoras/<id>/ com uma classe que herda
de Operadora, preencha os atributos e os métodos, e registre em operadoras/__init__.py.
O passo a passo está em CLAUDE.md ("Como adicionar uma operadora").
"""
from __future__ import annotations

from nucleo.registro import config_operadora


class Operadora:
    # ---- identidade (aparece na tela) ----
    id: str = ""                 # curto, sem espaço: "sulamerica"
    nome: str = ""               # "SulAmérica"
    produto: str = ""            # "Cotação PME (3 a 29 vidas)"
    cor: str = "#2B2F36"         # cor de destaque da operadora na tela
    min_vidas: int = 1
    max_vidas: int = 999
    faixas_idade_exata: tuple[str, ...] = ()   # faixas em que o portal pede a idade de cada vida
    etapas: tuple[tuple[str, str], ...] = ()   # (id da etapa, nome amigável) na ordem do portal

    PADRAO_CONFIG: dict = {}     # padrões da seção operadoras.<id> do config.yaml
    # Campos que só valem da configuração do robô (engrenagem): a tela nunca manda num pedido, e o
    # servidor descarta se vier (aba antiga, "Tentar de novo"). Ex.: o vendedor, que é quem cota.
    campos_so_configuracao: tuple[str, ...] = ()

    # ---- configuração ----
    def config(self, total: dict) -> dict:
        return config_operadora(total, self.id, self.PADRAO_CONFIG)

    # ---- formulário da tela ----
    def campos(self, cfg: dict) -> list[dict]:
        """Opções próprias da operadora que a tela mostra no formulário (ver SulAmerica.campos)."""
        return []

    def configuracao(self, cfg: dict) -> list[dict]:
        """O robô tela por tela do portal, com o que o corretor pode configurar (Robôs > <operadora>).

        Uma entrada por tela, na ordem de `etapas`: {"etapa": id, "faz": o que o robô faz ali,
        "campos": [...]}. Cada campo: {"chave": caminho na seção operadoras.<id> do config.yaml
        (ex.: "padroes.vigencia_meses", "tempos.timeout_tela_ms", "arquivos.nome_pdf_destino"),
        "rotulo", "tipo", "opcoes", "ajuda", "por_cotacao", "visivel_se"}. Tipos e validação em
        nucleo/configuracao.py. A tela lê o valor atual e o padrão da Newport e só grava estes campos.
        Na tela "login", um campo {"tipo": "credenciais"} (sem chave) desenha CPF, e-mail e senha, que vão
        para o cofre do Windows (nucleo/credenciais.py), nunca para a configuração."""
        return []

    def marcada_na_nova_cotacao(self, cfg: dict) -> bool:
        """A Nova cotação começa com esta operadora marcada ("Cotar nesta operadora")? Padrão: sim. Uma operadora em
        calibragem (só ensaio) pode começar desmarcada."""
        return True

    def planos_conhecidos(self) -> list[dict]:
        """Planos que a tela oferece antes de o robô ler a lista do portal: [{"nome", "acomodacao"}]."""
        return []

    # ---- pedidos ----
    def montar_pedido(self, dados: dict, cfg: dict, linha: int = 0):
        """Valida um pedido vindo da tela ou da planilha. Levanta ValueError com .problemas."""
        raise NotImplementedError

    def qtd_cotacoes(self, pedido) -> int:
        raise NotImplementedError

    def ler_registros(self, caminho) -> list[tuple[int, dict]]:
        raise NotImplementedError

    def ler_planilha(self, caminho, cfg: dict):
        raise NotImplementedError

    def criar_modelo(self, caminho) -> None:
        raise NotImplementedError

    # ---- robô ----
    def versoes(self, pedido) -> list:
        """Cotações reais do pedido para cada plano: [(pedido, texto da versão)]. Uma só, por padrão; a
        SulAmérica com "Com e sem" coparticipação devolve duas. A tela usa para avisar o que já foi emitido."""
        return [(pedido, "")]

    def nova_sessao(self, cfg, log, contexto, page, estado, resultados, mapa, ensaio: bool, avisar=None,
                    parar=None, pedir_codigo=None, reemitir=()):
        """avisar(tipo, **dados) informa a tela (login_entrando, login_ok, etapa).
        reemitir: protocolos que o corretor pediu na tela para emitir de novo ("Emitir de novo mesmo
        assim"); só esses, só se concluídos (pdf_ok), uma vez cada. Sem ele, o registro bloqueia tudo.
        parar() devolve True quando o corretor clicou em Parar: a operadora deve levantar
        nucleo.navegador.Parado só em ponto seguro, nunca entre o clique de emitir e o protocolo.
        pedir_codigo() pede na tela o código de verificação que o portal mandou (None: não veio)."""
        raise NotImplementedError

    # Nome da coluna da versão da cotação em resultados.xlsx (a SulAmérica usa "coparticipacao").
    nome_versao_planilha: str = "versao"

    def rotulos_versao(self) -> dict[str, str]:
        """Versões da cotação de um mesmo plano, na ordem, com o texto que a tela mostra ({código: texto}).
        Padrão: nenhuma (uma cotação por plano)."""
        return {}

    def resultados(self, caminho, log, ouvinte=None):
        """A planilha de resultados desta operadora (mesmo formato para todas; só o nome da coluna da versão)."""
        from nucleo.saidas import Resultados
        return Resultados(caminho, log, ouvinte=ouvinte, nome_versao=self.nome_versao_planilha)

    # Mensagens de login que só esta operadora tem (motivo -> frase com {op}); as gerais ficam no núcleo.
    mensagens_login: dict[str, str] = {}

    def campos_login(self) -> list[dict]:
        """Campos do login no portal, guardados no cofre do Windows (nunca na configuração). Cada campo:
        {"chave", "rotulo", "tipo": cpf | email | texto | senha, "mascara": "email" (opcional)}."""
        from nucleo.credenciais import CAMPOS_PADRAO
        return [dict(c) for c in CAMPOS_PADRAO]

    def textos_tela(self) -> dict:
        """Textos que a tela mostra sobre esta operadora (no lugar dos genéricos). Chaves: passo_login,
        passo_nova, perguntas {sair_do_portal, acesso_ativo, pdfs, configurar, versoes: [pergunta, resposta]},
        nome_pdf, planos, aguardando_portal, login_livre. Padrão: nenhum (a tela usa os genéricos)."""
        return {}

    def treino(self) -> dict | None:
        """Simulador de treino (python -m app --com-simulador), se a operadora tiver um:
        {"iniciar": callable, "portas": "texto", "login_falso": {campo: valor}}. O login falso vai só para o
        cofre de memória (nunca o real). Padrão: sem simulador."""
        return None

    def sair(self, sessao, prazo_s: float = 30) -> bool:
        """Sai do portal (logout) com o robô parado, para liberar o login (ex.: o CPF) do corretor. True se saiu.
        Padrão: a operadora não sabe sair; a tela só fecha a janela."""
        return False

    def login(self, sessao) -> None:
        """Entra no portal sozinho com o login do cofre (nucleo.credenciais.cofre), só se o portal pedir.
        Falhas: nucleo.navegador.ErroLogin com frase fixa, nunca com o que foi digitado."""
        raise NotImplementedError

    def conectado(self, page) -> bool:
        """True se a página mostra o portal já logado."""
        return False

    def recuperar_pdfs(self, sessao) -> None:
        pass

    def processar(self, sessao, pedido) -> None:
        raise NotImplementedError
