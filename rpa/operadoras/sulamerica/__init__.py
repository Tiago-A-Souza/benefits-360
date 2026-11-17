"""SulAmérica — Cotador Saúde, módulo Cotação PME (3 a 29 vidas).

O fluxo foi levantado de um vídeo gravado por um corretor da Newport. Os seletores
(seletores.py) ainda precisam ser calibrados no portal real (ver CLAUDE.md).
"""
from __future__ import annotations

from nucleo.configuracao import aprendido
from nucleo.saidas import Resultados  # noqa: F401  (reexportado para quem monta sessões)

from ..base import Operadora

PLANOS_VIDEO = [
    # Os 12 planos da 1ª página vistos no vídeo (filtros 557-AHO, Compulsória, 24 meses, com coparticipação).
    # A 2ª página tinha mais 2, que aparecem na tela depois da primeira execução.
    ("Direto Nacional", "Enfermaria"), ("Direto Nacional", "Apartamento"),
    ("Clássico Vital", "Enfermaria"), ("Especial Vital", "Apartamento"),
    ("Clássico 100", "Enfermaria"), ("Especial Vital R1", "Apartamento"),
    ("Especial RC", "Apartamento"), ("Especial 100 R1", "Apartamento"),
    ("Especial Mais Vital", "Apartamento"), ("Especial Mais", "Apartamento"),
    ("Executivo R1", "Apartamento"), ("Executivo R2", "Apartamento"),
]


class SulAmerica(Operadora):
    id = "sulamerica"
    nome = "SulAmérica"
    produto = "Cotação PME (3 a 29 vidas)"
    cor = "#E8651D"
    min_vidas = 3
    max_vidas = 29
    faixas_idade_exata = ("0 - 18", "59+")   # vídeo: 0–18; 59+ a confirmar no portal
    etapas = (
        ("login", "Login"), ("modulos", "Módulo PME"), ("dados_empresa", "Empresa"),
        ("cuidado_360", "Cuidado 360°"), ("congenere", "Operadora atual"), ("vidas", "Vidas"),
        ("idades", "Idades"), ("planos", "Planos"), ("comparacao", "Comparação"),
        ("resumo", "Resumo"), ("emitida", "PDF"),
    )

    # O vendedor é quem cota: vem só da engrenagem do robô (04/11: um vendedor antigo copiado do pedido
    # anterior travava "Comece por aqui"). A planilha ainda pode trazer um, na coluna vendedor.
    campos_so_configuracao = ("vendedor",)

    PADRAO_CONFIG = {
        "urls": {"login": "https://os11.sulamerica.com.br/SaudeCotador/LoginGeral.aspx"},
        "execucao": {"timeout_padrao_ms": 30000, "timeout_login_ms": 60000, "timeout_codigo_ms": 300000,
                     "login_reentrada_ms": 60000, "login_liberacao_ms": 600000,
                     "sair_do_portal_min": 3,   # fila vazia há 3 min: o robô sai do portal e fecha a janela
                     "timeout_emissao_ms": 180000, "timeout_tela_ms": 60000, "timeout_download_ms": 120000},
        # O que o robô preenche no portal quando a cotação não diz outra coisa (o corretor muda em Robôs).
        "padroes": {"cuidado_360": "sim", "tipo_contratacao": "compulsoria", "produto": "557 - AHO",
                    "vigencia_meses": "24", "coparticipacao": "as_duas", "vendedor": "",
                    "planos_modo": "lista", "planos": []},
        "faixas_idade_exata": ["0 - 18", "59+"],
        "criterio_plano": {"tipo": "menor_preco", "quantidade": 1},
        "navegacao": {"proxima_empresa": "voltar_home"},
        # Reabrir a página da emissão para baixar o PDF de novo: desligado até confirmar no portal que isso
        # não gera protocolo novo (codegen/mapa_seletores.md). Desligado, fica em "Conferir no portal".
        "recuperar_pdf_automatico": False,
        "conferencias": {"aliquota_iof": "0.0238", "tolerancia_reais": "0.05"},
        "saida": {"nome_pdf_arquivo": "SULAMERICA_{cnpj}_{protocolo}.pdf",
                  "nome_pdf_destino": "SULAMERICA {plano_arquivo}.pdf", "substituir_no_destino": True,
                  "nomes_arquivo": {}},
        "congeneres_de_para": {},
    }

    # ------------------------------------------------------------------ tela
    OPCOES_CONTRATACAO = [["cbo", "CBO"], ["compulsoria", "Compulsória"], ["flex", "Flex"]]
    OPCOES_VIGENCIA = [["12", "12 meses"], ["24", "24 meses"]]
    # O 3º item é a frase do resumo ("O robô vai cotar ..."); o 2º é o rótulo do botão.
    OPCOES_COPART = [["sem", "Sem coparticipação"], ["com", "Com coparticipação"],
                     ["as_duas", "Com e sem", "com e sem coparticipação (2 cotações por plano)"]]

    def campos(self, cfg: dict) -> list[dict]:
        """Campos de cada cotação na Nova cotação. Os marcados "robo" vêm da configuração do robô
        (o corretor muda lá para todas as cotações, ou só numa cotação em "Mudar só nesta cotação")."""
        padroes = cfg.get("padroes", {})
        sugestoes = sorted({"NOTREDAME", *(cfg.get("congeneres_de_para") or {}).values()})
        return [
            {"chave": "seguro_novo", "titulo": "Plano atual", "rotulo": "A empresa não tem plano de saúde hoje",
             "tipo": "sim_nao", "padrao": "nao", "empresa": True},
            {"chave": "congenere_atual", "rotulo": "Operadora atual", "tipo": "sugestoes", "opcoes": sugestoes,
             "visivel_se": {"seguro_novo": "nao"}, "empresa": True,
             "ajuda": "Como aparece na lista do portal (ex.: NOTREDAME)."},
            {"chave": "cuidado_360", "titulo": "Cuidado 360°", "rotulo": "Incluir na cotação", "tipo": "sim_nao",
             "padrao": padroes.get("cuidado_360", "sim"), "robo": True,
             "ajuda": "Odonto e vida sem custo adicional. Incluído, o robô aceita os termos do Cuidado 360° no portal."},
            {"chave": "tipo_contratacao", "rotulo": "Tipo de contratação", "tipo": "escolha", "robo": True,
             "opcoes": self.OPCOES_CONTRATACAO, "padrao": padroes.get("tipo_contratacao", "compulsoria")},
            {"chave": "vigencia_meses", "rotulo": "Vigência contratual", "tipo": "escolha", "robo": True,
             "opcoes": self.OPCOES_VIGENCIA, "padrao": str(padroes.get("vigencia_meses", "24"))},
            {"chave": "coparticipacao", "rotulo": "Coparticipação", "tipo": "escolha", "robo": True,
             "opcoes": self.OPCOES_COPART, "padrao": padroes.get("coparticipacao", "as_duas"),
             "multiplica": {"as_duas": 2},   # a Nova cotação conta 2 cotações por plano
             "ajuda": "Com e sem: duas cotações por plano, cada uma com o seu protocolo e o seu PDF."},
        ]

    def configuracao(self, cfg: dict) -> list[dict]:
        """O robô da SulAmérica tela por tela, com tudo o que o corretor pode configurar (Robôs > SulAmérica)."""
        return [
            {"etapa": "login", "faz": "Entra no portal sozinho, só quando o portal pede, com o login que você "
                                      "guarda aqui. Se o portal pedir um código, a tela pede para você.",
             "campos": [{"tipo": "credenciais", "rotulo": "Login no portal",
                         # maxlength do campo de senha no portal: 16 no mapa de 03/11; o robô relê a cada login
                         "senha_max": int(aprendido(cfg.get("saida", {}).get("pasta", "")).get("senha_max") or 16),
                         "campos": self.campos_login(),
                         "ajuda": "Fica no cofre do Windows, só neste computador e no seu usuário do Windows. "
                                  "A senha nunca volta para a tela. Ao sair da Newport, apague."},
                        {"chave": "tempos.sair_do_portal_min", "rotulo": "Sair do portal depois de (minutos sem pedidos)",
                         "tipo": "numero", "minimo": 0, "maximo": 120,
                         "ajuda": "Com a fila vazia por esse tempo, o robô sai do portal e fecha a janela: o seu CPF "
                                  "fica livre para usar o portal no seu navegador. Na próxima cotação ele entra "
                                  "sozinho de novo. 0 = não sai sozinho (sai ao clicar em Parar com a fila vazia, "
                                  "em “Sair do portal agora” ou ao fechar a tela)."}]},
            {"etapa": "modulos", "faz": "Escolhe o módulo Cotação PME (3 a 29 vidas).", "campos": []},
            {"etapa": "dados_empresa", "faz": "Digita o CNPJ de cada cotação e confere a razão social.",
             "campos": [{"chave": "padroes.vendedor", "rotulo": "Vendedor", "tipo": "texto",
                         "exemplo": "Vazio: quem fez o login",
                         "ajuda": "Vale para todas as cotações (a Nova cotação não muda). Como aparece na lista de "
                                  "vendedores do portal; espaços e hífens não importam. Vazio: o robô mantém quem "
                                  "fez o login."}]},
            {"etapa": "cuidado_360", "faz": "Responde se a cotação inclui o Cuidado 360° e, se incluir, aceita os termos.",
             "campos": [{"chave": "padroes.cuidado_360", "rotulo": "Incluir o Cuidado 360°", "tipo": "sim_nao",
                         "por_cotacao": True, "ajuda": "Odonto e vida sem custo adicional na proposta."}]},
            {"etapa": "congenere", "faz": "Informa a operadora atual da empresa (você diz qual em cada cotação) "
                                          "ou marca que é um seguro novo.",
             "campos": [{"chave": "congeneres_de_para", "rotulo": "Nomes das operadoras", "tipo": "pares",
                         "colunas": ["Como a Newport escreve", "Como o portal mostra"],
                         "exemplos": ["NotreDame Intermédica", "NOTREDAME"],
                         "ajuda": "O robô troca o nome da esquerda pelo da direita antes de procurar na lista do portal."}]},
            {"etapa": "vidas", "faz": "Preenche as vidas de cada faixa etária, que você informa em cada cotação.",
             "campos": []},
            {"etapa": "idades", "faz": "Quando o portal pede, informa a idade exata de cada vida.",
             "campos": [{"chave": "faixas_idade_exata", "rotulo": "Faixas em que o portal pede a idade", "tipo": "faixas",
                         "ajuda": "Nessas faixas a Nova cotação pede a idade de cada vida. No vídeo, o portal pediu a 0 - 18."}]},
            {"etapa": "planos", "faz": "Acerta os filtros da tela Planos disponíveis, lê os planos das duas páginas "
                                       "e marca um plano por cotação.",
             "campos": [
                 {"chave": "padroes.produto", "rotulo": "Produto Saúde PME", "tipo": "texto", "sugestoes": ["557 - AHO"],
                  "ajuda": "Escrito como aparece no filtro do portal. Se o portal não mostrar esse produto, "
                           "o robô para sem cotar."},
                 {"chave": "padroes.tipo_contratacao", "rotulo": "Tipo de contratação", "tipo": "escolha",
                  "por_cotacao": True, "opcoes": self.OPCOES_CONTRATACAO},
                 {"chave": "padroes.vigencia_meses", "rotulo": "Vigência contratual", "tipo": "escolha",
                  "por_cotacao": True, "opcoes": self.OPCOES_VIGENCIA},
                 {"chave": "padroes.coparticipacao", "rotulo": "Coparticipação", "tipo": "escolha",
                  "por_cotacao": True, "opcoes": self.OPCOES_COPART,
                  "ajuda": "Com e sem: o robô faz duas cotações por plano (primeiro com, depois sem "
                           "coparticipação), cada uma com o seu protocolo e o seu PDF. Para a segunda, usa "
                           "Copiar cotação e troca só a coparticipação."},
                 {"tipo": "info", "rotulo": "Ordenar por",
                  "texto": "Não precisa configurar: o robô lê os planos das duas páginas, em qualquer ordem."},
                 {"chave": "padroes.planos_modo", "rotulo": "Planos que já vêm marcados", "tipo": "escolha",
                  "por_cotacao": True, "opcoes": [["lista", "Escolher na lista"], ["menor_preco", "Os mais baratos"]]},
                 {"chave": "padroes.planos", "rotulo": "Marcados na Nova cotação", "tipo": "planos",
                  "visivel_se": {"padroes.planos_modo": "lista"},
                  "ajuda": "Cada plano vira uma cotação e um PDF. Na Nova cotação dá para desmarcar ou marcar outros."},
                 {"chave": "criterio_plano.quantidade", "rotulo": "Quantos planos", "tipo": "numero",
                  "minimo": 1, "maximo": 10, "visivel_se": {"padroes.planos_modo": "menor_preco"},
                  "ajuda": "Os mais baratos da lista do portal, com os filtros acima."},
             ]},
            {"etapa": "comparacao", "faz": "Lê o valor por vida de cada faixa e confere se a soma bate com o preço "
                                           "do plano. Se não bater, para sem emitir.", "campos": []},
            {"etapa": "resumo", "faz": "Antes de emitir, confere CNPJ, plano, produto, vidas, contratação, vigência, "
                                       "coparticipação e o IOF de 2,38% por vida.", "campos": []},
            {"etapa": "emitida", "faz": "Lê o protocolo, baixa o PDF e copia para a pasta do cliente. Para a próxima "
                                        "cotação (outro plano ou a versão sem coparticipação), usa Copiar cotação, "
                                        "sem sair do portal.",
             "campos": [
                 {"chave": "arquivos.nome_pdf_destino", "rotulo": "Nome do PDF na pasta do cliente", "tipo": "texto",
                  "validar": "nome_pdf", "ajuda": "{plano_arquivo} vira o nome do plano em letras maiúsculas.",
                  # o exemplo que a engrenagem mostra (um plano e as versões "Com e sem" coparticipação)
                  "exemplo_pdf": {"plano": "Especial Mais", "versoes": ["COM COPARTICIPACAO", "SEM COPARTICIPACAO"],
                                  "frase_versoes": "Com “Com e sem” coparticipação"}},
                 {"chave": "arquivos.substituir_no_destino", "rotulo": "Substituir o PDF antigo com o mesmo nome",
                  "tipo": "sim_nao", "booleano": True,
                  "ajuda": "Desligado, o robô guarda o novo com a data no nome e não apaga o antigo."},
                 {"chave": "arquivos.nomes_arquivo", "rotulo": "Nomes curtos", "tipo": "pares",
                  "colunas": ["Plano no portal", "Nome no arquivo"], "exemplos": ["Executivo R1", "EXECUTIVO"],
                  "ajuda": "Para quando a Newport salva o plano com outro nome no PDF."},
                 {"chave": "navegacao.proxima_empresa", "rotulo": "Depois da última cotação da empresa",
                  "tipo": "escolha", "opcoes": [["voltar_home", "Voltar para a home"], ["nova_cotacao", "Nova cotação"]]},
             ]},
        ]

    def planos_conhecidos(self) -> list[dict]:
        return [{"nome": n, "acomodacao": a} for n, a in PLANOS_VIDEO]

    # ------------------------------------------------------------------ pedidos
    def montar_pedido(self, dados: dict, cfg: dict, linha: int = 0):
        from .planilha import montar_pedido
        return montar_pedido(dados, linha, cfg)

    def qtd_cotacoes(self, pedido) -> int:
        return (len(pedido.planos) or (pedido.criterio_quantidade or 0)) * len(pedido.versoes_copart)

    def versoes(self, pedido) -> list:
        """Cada cotação real do pedido por plano: [(pedido de uma coparticipação, texto da versão)]."""
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

    # ------------------------------------------------------------------ robô
    def nova_sessao(self, cfg, log, contexto, page, estado, resultados, mapa, ensaio: bool, avisar=None,
                    parar=None, pedir_codigo=None, reemitir=()):
        from .etapas import Sessao
        return Sessao(cfg=cfg, log=log, contexto=contexto, page=page, estado=estado,
                      resultados=resultados, mapa=mapa, ensaio=ensaio, avisar=avisar, parar=parar,
                      pedir_codigo=pedir_codigo, reemitir={str(x) for x in (reemitir or ())})

    def login(self, sessao) -> None:
        from .login import entrar
        entrar(sessao)

    # Login do portal: CPF, e-mail e senha (mapa de 03/11). O e-mail aparece mascarado na tela.
    CAMPOS_LOGIN = [{"chave": "cpf", "rotulo": "CPF", "tipo": "cpf", "artigo": "o"},
                    {"chave": "email", "rotulo": "E-mail", "tipo": "email", "mascara": "email", "artigo": "o"},
                    {"chave": "senha", "rotulo": "Senha", "tipo": "senha", "artigo": "a"}]
    mensagens_login = {
        "acesso_ativo": "O portal da {op} continuou dizendo que já existe um acesso ativo para este CPF, mesmo depois "
                        "de o robô esperar e tentar de novo: o login está aberto em outro navegador ou computador. Saia "
                        "do portal no outro lugar e peça de novo. O login guardado continua valendo.",
        "selecao_corretora": "Depois do login o portal da {op} pediu para escolher a corretora (EV/EA/AA). O robô "
                             "ainda não faz essa escolha: avise quem cuida do robô.",
    }

    # resultados.xlsx: a coluna da versão da cotação continua com o nome de antes
    nome_versao_planilha = "coparticipacao"

    def rotulos_versao(self) -> dict[str, str]:
        """"Com e sem" coparticipação: duas cotações por plano, nesta ordem."""
        return {"com": "com coparticipação", "sem": "sem coparticipação"}

    def textos_tela(self) -> dict:
        """Os textos da SulAmérica na tela (Ajuda, Nova cotação, Andamento, avisos): CPF, Cuidado 360°, Com e sem
        coparticipação, SULAMERICA <PLANO>.pdf..."""
        return {
            "passo_login": "Na engrenagem do robô (tela Login), guarde o CPF, o e-mail e a senha do portal. Eles ficam no cofre do Windows, só neste computador e no seu usuário do Windows. O robô entra no portal sozinho quando o portal pede; você não mexe na janela do portal.",
            "passo_nova": "CNPJ, vidas por faixa etária e os planos. As opções do portal (Cuidado 360°, contratação, vigência, coparticipação) vêm da configuração do seu robô.",
            "perguntas": {
                "sair_do_portal": [
                    "Quero usar o portal no meu navegador. O robô está ocupando o meu CPF?",
                    "Com a fila vazia, o robô sai do portal sozinho depois de 3 minutos (dá para mudar na engrenagem, tela Login) e também ao clicar em Parar com a fila vazia ou ao fechar a janela preta. Para liberar na hora, clique em “Sair do portal agora” no cartão da SulAmérica. Na próxima cotação o robô entra sozinho de novo."
                ],
                "acesso_ativo": [
                    "O portal diz que “já existe um acesso ativo para esse CPF”.",
                    "O portal só aceita o mesmo CPF logado em um lugar. O robô espera e tenta entrar de novo sozinho, a cada minuto, por até 10 minutos (a tela mostra “Esperando o portal liberar”); não precisa fazer nada. Para não acontecer: não entre no portal com o mesmo CPF no seu navegador enquanto o robô trabalha e não feche a janela do portal do robô. O login guardado não é marcado como recusado."
                ],
                "pdfs": [
                    "Onde ficam os PDFs?",
                    "Se você informou a pasta do cliente, uma cópia vai para lá com o nome SULAMERICA <PLANO>.pdf. O robô também guarda uma cópia na pasta dele, que é a que você baixa por aqui."
                ],
                "configurar": [
                    "Como mudo o que o robô preenche no portal (ex.: vigência de 24 para 12 meses)?",
                    "Clique na engrenagem do cartão da SulAmérica (no pé do menu ou em Robôs). Lá estão as telas do portal na ordem em que o robô passa, com o que dá para mudar em cada uma. Mude e clique em Salvar configuração: vale para as próximas cotações. Para uma cotação só, use “Mudar só nesta cotação” na Nova cotação."
                ],
                "versoes": [
                    "Como cotar com e sem coparticipação?",
                    "É automático. Com “Com e sem” (o padrão da Newport), o robô faz duas cotações para cada plano, primeiro com e depois sem coparticipação, cada uma com o seu protocolo e o seu PDF (ex.: SULAMERICA ESPECIAL MAIS COM COPARTICIPACAO.pdf e SULAMERICA ESPECIAL MAIS SEM COPARTICIPACAO.pdf). Em Cotações, as duas aparecem juntas. Para só uma, escolha “Com” ou “Sem” na engrenagem do robô (tela Planos) ou em “Mudar só nesta cotação”. Na planilha, a coluna coparticipacao aceita com, sem ou as_duas."
                ]
            },
            "nome_pdf": "SULAMERICA <PLANO>.pdf",
            "planos": "Cada plano vira uma cotação e um PDF (com “Com e sem” coparticipação, duas). A lista cresce sozinha com os planos que o robô encontrar no portal.",
            "aguardando_portal": "O portal ainda tem uma sessão aberta para este CPF (outro navegador ou uma janela fechada). ",
            "login_livre": "o seu CPF"
        }

    def campos_login(self) -> list[dict]:
        return [dict(c) for c in self.CAMPOS_LOGIN]

    def sair(self, sessao, prazo_s: float = 30) -> bool:
        from .etapas import sair_do_portal
        return sair_do_portal(sessao, prazo_s)

    def treino(self) -> dict:
        from .simulador.servidor import Simulador
        return {"iniciar": lambda: Simulador(8765, 8766).iniciar(), "portas": "portas 8765 e 8766",
                "login_falso": {"cpf": Simulador.CPF, "email": Simulador.EMAIL, "senha": Simulador.SENHA}}

    def conectado(self, page) -> bool:
        from .login import painel_visivel, tela_modulos_visivel
        return tela_modulos_visivel(page) or painel_visivel(page)

    def recuperar_pdfs(self, sessao) -> None:
        from .fluxo import recuperar_pdfs
        recuperar_pdfs(sessao)

    def processar(self, sessao, pedido) -> None:
        from .fluxo import processar_pedido
        processar_pedido(sessao, pedido)
