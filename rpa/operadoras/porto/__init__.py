"""Porto Seguro — Corretor Online, Saúde PME.

Levantado do vídeo de um corretor da Newport (codegen/porto_mapa_video.md, Seções 2 a 6).
1 plano = 1 cotação = 1 PDF, sempre por "Criar nova cotação" (nunca Duplicar). O ponto sem volta é
"Gerar orçamento". O ensaio para no passo 3 (plano selecionado), sem gerar. O robô NUNCA clica em
Elaborar proposta, Adicionar à Proposta, Remissão nem Editar.

Enquanto a calibragem não termina, `emissao_liberada: false` (padrão): o robô só faz ensaio.
"Gerar orçamento" só roda quando o Tiago liga a emissão e clica em Gerar.
"""
from __future__ import annotations

from ..base import Operadora
from .pedido import COMISSAO_K001, PLANOS_CONHECIDOS


class Porto(Operadora):
    id = "porto"
    nome = "Porto Seguro"
    produto = "Cotação Saúde PME"
    cor = "#00A651"
    min_vidas = 3
    max_vidas = 29
    faixas_idade_exata = ("0 - 18",)
    etapas = (
        ("login", "Login"), ("susep", "SUSEP"), ("inicio", "Criar cotação"),
        ("dados", "Dados iniciais"), ("vidas", "Produto e vidas"), ("comissao", "Comissão"),
        ("planos", "Selecionar o plano"), ("orcamento", "Gerar orçamento"), ("pdf", "PDF"),
    )

    PADRAO_CONFIG = {
        "urls": {"login": "https://corretor.portoseguro.com.br/",
                 "cotador": "https://www.saude.portoseguro.com.br/corretor/cotar"},
        "execucao": {"timeout_padrao_ms": 30000, "timeout_login_ms": 60000, "timeout_codigo_ms": 300000,
                     "sair_do_portal_min": 3, "timeout_emissao_ms": 180000, "timeout_tela_ms": 60000,
                     "timeout_download_ms": 120000},
        "emissao_liberada": False,
        "padroes": {"susep": "BX865J", "produto": "Saude", "comissao": COMISSAO_K001,
                    "aceitar_agenciamento": "sim", "acomodacao": "Apartamento",
                    "coparticipacao": "com", "planos": []},
        "faixas_idade_exata": ["0 - 18"],
        "congeneres_de_para": {"NOTREDAME": "NotreDame Intermédica",
                               "NotreDame Intermédica": "NotreDame Intermédica"},
        "conferencias": {"aliquota_iof": "0.0238", "taxa_inscricao_por_vida": "5.00",
                         "tolerancia_reais": "0.05"},
        "saida": {"nome_pdf_arquivo": "PORTO_{cnpj}_{protocolo}.pdf",
                  "nome_pdf_destino": "PORTO {plano_arquivo} {versao}.pdf",
                  "substituir_no_destino": True, "nomes_arquivo": {}},
    }

    OPCOES_COPART = [["sem", "Sem (0%)"], ["com", "Com (30%)"],
                     ["as_duas", "Com e sem", "com e sem coparticipação (2 cotações por plano)"]]
    OPCOES_ACOMOD = [["Apartamento", "Apartamento"], ["Enfermaria", "Enfermaria"]]

    def campos(self, cfg: dict) -> list[dict]:
        padroes = cfg.get("padroes", {})
        sugestoes = sorted({*(cfg.get("congeneres_de_para") or {}).keys(),
                            *(cfg.get("congeneres_de_para") or {}).values()})
        return [
            {"chave": "seguro_novo", "titulo": "Plano atual", "rotulo": "A empresa não tem plano de saúde hoje",
             "tipo": "sim_nao", "padrao": "nao", "empresa": True},
            {"chave": "congenere_atual", "rotulo": "Operadora atual", "tipo": "sugestoes", "opcoes": sugestoes,
             "visivel_se": {"seguro_novo": "nao"}, "empresa": True,
             "ajuda": "Como a Newport escreve; o robô troca pelo nome da lista da Porto (de-para na engrenagem)."},
            {"chave": "coparticipacao", "rotulo": "Coparticipação", "tipo": "escolha", "robo": True,
             "opcoes": self.OPCOES_COPART, "padrao": padroes.get("coparticipacao", "com"),
             "multiplica": {"as_duas": 2}},
            {"chave": "acomodacao", "rotulo": "Acomodação", "tipo": "escolha", "robo": True,
             "opcoes": self.OPCOES_ACOMOD, "padrao": padroes.get("acomodacao", "Apartamento")},
        ]

    def configuracao(self, cfg: dict) -> list[dict]:
        return [
            {"etapa": "login", "faz": "Entra no Corretor Online sozinho, só quando o portal pede, com o CPF, a senha "
                                      "e o código SUSEP que você guarda em Conexões. Depois do CPF e da senha o portal "
                                      "abre o dropdown da SUSEP; o robô escolhe o código guardado. Se aparecer "
                                      "desafio de reCAPTCHA, o robô para e avisa: não tenta burlar. A sessão fica no "
                                      "navegador do robô.",
             "campos": [{"tipo": "credenciais", "rotulo": "Login no portal", "senha_max": 64,
                         "campos": self.campos_login(),
                         "ajuda": "CPF, senha e SUSEP ficam no cofre do Windows (NewportCotacoes/porto). A senha nunca volta para a tela."},
                        {"chave": "tempos.sair_do_portal_min", "rotulo": "Sair do portal depois de (minutos sem pedidos)",
                         "tipo": "numero", "minimo": 0, "maximo": 120}]},
            {"etapa": "susep", "faz": "Depois do CPF e da senha, escolhe no dropdown o código SUSEP guardado no login "
                                      "(o mesmo da lista: BX865J (P), etc.). Sem esse código o robô não entra.",
             "campos": []},
            {"etapa": "inicio", "faz": "Abre o cotador (iframe) e clica em Criar nova cotação. Nunca Duplicar orçamento.",
             "campos": []},
            {"etapa": "dados", "faz": "Digita o CNPJ, espera o preenchimento da Receita e confere a razão social.",
             "campos": []},
            {"etapa": "vidas", "faz": "Produto Saúde, total de vidas, plano anterior e faixas (idade exata de 0 a 18).",
             "campos": [{"chave": "congeneres_de_para", "rotulo": "Nomes das operadoras", "tipo": "pares",
                         "colunas": ["Como a Newport escreve", "Como o portal mostra"],
                         "exemplos": ["NOTREDAME", "NotreDame Intermédica"]}]},
            {"etapa": "comissao", "faz": "Escolhe a comissão pelo texto exato e marca o aceite de agenciamento.",
             "campos": [{"chave": "padroes.comissao", "rotulo": "Opção de comissão (texto exato da lista)",
                         "tipo": "texto", "sugestoes": [COMISSAO_K001],
                         "ajuda": "O robô confere o texto depois de selecionar. Padrão do vídeo: K001."}]},
            {"etapa": "planos", "faz": "Acomodação e coparticipação, clica no plano pelo nome exato. O ensaio para aqui, "
                                       "sem Gerar orçamento. Nunca marca Medicamentos nem Remissão.",
             "campos": [
                 {"chave": "padroes.acomodacao", "rotulo": "Acomodação", "tipo": "escolha", "por_cotacao": True,
                  "opcoes": self.OPCOES_ACOMOD},
                 {"chave": "padroes.coparticipacao", "rotulo": "Coparticipação", "tipo": "escolha", "por_cotacao": True,
                  "opcoes": self.OPCOES_COPART},
             ]},
            {"etapa": "orcamento", "faz": "Ponto sem volta: grava o registro antes do clique em Gerar orçamento e, no "
                                          "modal, Emitir Sem Medicamentos. Só com a emissão liberada e o corretor em Gerar. "
                                          "Nunca Elaborar proposta nem Adicionar à Proposta.",
             "campos": []},
            {"etapa": "pdf", "faz": "Imprimir cotação: baixa o PDF do link da aba nova. Em Erro ao gerar PDF, fecha e "
                                    "tenta de novo até 3 vezes. Se cair depois de Gerar, procura na lista pelo CNPJ e "
                                    "abre Visualizar, sem gerar outra.",
             "campos": [
                 {"chave": "arquivos.nome_pdf_destino", "rotulo": "Nome do PDF na pasta do cliente", "tipo": "texto",
                  "validar": "nome_pdf",
                  "ajuda": "{plano_arquivo} é o apelido do plano e {versao} é o nome curto da empresa.",
                  "exemplo_pdf": {"plano": "Ouro Mais I", "versoes": ["PADARIA"],
                                  "frase_versoes": "Com o nome curto da empresa"}},
                 {"chave": "arquivos.substituir_no_destino", "rotulo": "Substituir o PDF antigo com o mesmo nome",
                  "tipo": "sim_nao", "booleano": True},
             ]},
        ]

    def marcada_na_nova_cotacao(self, cfg: dict) -> bool:
        return bool(cfg.get("emissao_liberada"))

    def planos_conhecidos(self) -> list[dict]:
        return [{"nome": n, "acomodacao": a} for n, a in PLANOS_CONHECIDOS]

    def montar_pedido(self, dados: dict, cfg: dict, linha: int = 0):
        from .planilha import montar_pedido
        return montar_pedido(dados, linha, cfg)

    def qtd_cotacoes(self, pedido) -> int:
        return len(pedido.planos) * len(pedido.versoes_copart)

    def versoes(self, pedido) -> list:
        if len(pedido.versoes_copart) == 1:
            return [(pedido, "")]
        return [(pedido.na_versao(c), f"{c} coparticipação") for c in pedido.versoes_copart]

    def ler_registros(self, caminho):
        from .planilha import ler_registros
        return ler_registros(caminho)

    def ler_planilha(self, caminho, cfg: dict):
        from .planilha import ler_planilha
        return ler_planilha(caminho, cfg)

    def criar_modelo(self, caminho) -> None:
        from .planilha import criar_modelo
        criar_modelo(caminho)

    nome_versao_planilha = "coparticipacao"

    def rotulos_versao(self) -> dict[str, str]:
        return {"com": "com coparticipação 30%", "sem": "sem coparticipação"}

    def nova_sessao(self, cfg, log, contexto, page, estado, resultados, mapa, ensaio: bool, avisar=None,
                    parar=None, pedir_codigo=None, reemitir=()):
        from .etapas import Sessao
        return Sessao(cfg=cfg, log=log, contexto=contexto, page=page, estado=estado, resultados=resultados, mapa=mapa,
                      ensaio=ensaio, avisar=avisar, parar=parar, pedir_codigo=pedir_codigo,
                      reemitir={str(x) for x in (reemitir or ())})

    def login(self, sessao) -> None:
        from .login import entrar
        entrar(sessao)

    CAMPOS_LOGIN = [{"chave": "cpf", "rotulo": "CPF", "tipo": "cpf", "artigo": "o"},
                    {"chave": "senha", "rotulo": "Senha", "tipo": "senha", "artigo": "a"},
                    {"chave": "susep", "rotulo": "SUSEP", "tipo": "texto", "artigo": "o"}]
    mensagens_login = {
        "captcha": "O portal da {op} mostrou um desafio de reCAPTCHA. O robô não tenta resolver: resolva no "
                   "seu navegador (ou ligue “Mostrar a janela do portal”) e peça de novo.",
        "sem_susep": "O código SUSEP guardado no robô não está na lista do portal. O campo SUSEP do robô "
                     "precisa ser um dos códigos do dropdown (o sufixo (P) não precisa ser digitado).",
        "sem_botao_entrada": "O robô parou na primeira página da {op}: não achei o botão «Acessar o Corretor "
                             "Online». Ligue “Mostrar a janela do portal” e confira se o site mudou.",
        "sem_janela_login": "O robô clicou em «Acessar o Corretor Online», mas a janela de login não abriu. "
                            "Ligue “Mostrar a janela do portal” e tente de novo.",
        "sem_resposta": "O robô parou na primeira página da {op} sem chegar ao login (o portal não mostrou "
                        "CPF, senha nem SUSEP). Ele já recusa o aviso de localização sozinho. Ligue "
                        "“Mostrar a janela do portal” e tente de novo.",
    }

    def campos_login(self) -> list[dict]:
        return [dict(c) for c in self.CAMPOS_LOGIN]

    def textos_tela(self) -> dict:
        return {
            "passo_login": "Em Conexões da Porto, guarde CPF, senha e o código SUSEP do dropdown (depois do login). Ficam no cofre do Windows (NewportCotacoes/porto). Se o portal mostrar reCAPTCHA, o robô para e avisa.",
            "passo_nova": "CNPJ, vidas por faixa (idade exata de 0 a 18), operadora atual e os planos pelo nome da grade. Cada plano vira uma cotação e um PDF, sempre por Criar nova cotação.",
            "perguntas": {
                "versoes": [
                    "O ensaio da Porto cria alguma coisa no portal?",
                    "Não. O ensaio preenche até o passo 3 (plano selecionado, preço indicativo) e para sem Gerar orçamento. Nada é criado. Gerar orçamento só quando a emissão estiver liberada e você clicar em Gerar."
                ],
                "pdfs": [
                    "Onde ficam os PDFs da Porto?",
                    "Se você informou a pasta do cliente, uma cópia vai para lá com o nome PORTO <PLANO> <EMPRESA>.pdf. O robô também guarda uma cópia na pasta dele."
                ],
            },
            "nome_pdf": "PORTO <PLANO> <EMPRESA>.pdf",
            "planos": "Cada plano vira uma cotação e um PDF (Criar nova cotação, nunca Duplicar). O nome precisa ser igual ao da grade da Porto.",
            "login_livre": "o seu CPF",
        }

    def treino(self) -> dict:
        from .simulador.servidor import Simulador
        return {"iniciar": lambda: Simulador(8795).iniciar(), "portas": "porta 8795",
                "login_falso": {"cpf": Simulador.CPF, "senha": Simulador.SENHA, "susep": Simulador.SUSEP}}

    def sair(self, sessao, prazo_s: float = 30) -> bool:
        from .etapas import sair_do_portal
        return sair_do_portal(sessao, prazo_s)

    def conectado(self, page) -> bool:
        from .telas import logado
        return logado(page)

    def recuperar_pdfs(self, sessao) -> None:
        pass

    def processar(self, sessao, pedido) -> None:
        if not sessao.ensaio and not sessao.cfg.get("emissao_liberada"):
            from nucleo.modelo import ResultadoPlano
            from .etapas import com_versoes
            sessao.log.error(f"[{pedido.id}] A Porto está em calibragem: só o ensaio está liberado. Nada foi feito no portal.")
            for alvo in com_versoes(pedido, list(pedido.planos)) or [None]:
                sessao.resultados.plano(ResultadoPlano(
                    pedido_id=pedido.id, linha=pedido.linha, cnpj=pedido.cnpj,
                    plano=alvo.nome if alvo else "", acomodacao=(alvo.acomodacao or "") if alvo else "",
                    versao=(alvo.versao if alvo and alvo.versao else pedido.coparticipacao),
                    status="ERRO", etapa_erro="calibragem",
                    erro="a Porto ainda está em calibragem: só o ensaio está liberado (nada foi gerado no portal)"))
            return
        from .fluxo import processar_pedido
        processar_pedido(sessao, pedido)
