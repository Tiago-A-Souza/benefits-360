"""Bradesco — Portal de Negócios, Cotação SPG (Saúde PME, 3 a 29 vidas).

Levantado do vídeo de um corretor da Newport (codegen/bradesco_mapa_video.md). Um pedido (empresa) = um processo
("Gerar processo"); cada plano e versão = um cálculo no processo ("Alterar Cotação" -> Calcular) e um PDF (janela
"Imprimir"). Os seletores (seletores.py) ainda precisam ser calibrados no portal real com o ensaio.

Enquanto a calibragem não termina, `emissao_liberada: false` (padrão): o robô só faz ensaio. Com o ensaio
conferido e o pedido do Tiago, liga-se `emissao_liberada: true` no config.yaml.
"""
from __future__ import annotations

from ..base import Operadora
from .pedido import CATEGORIAS, DENTAIS

PLANOS_VIDEO = [   # vistos no vídeo (Resultado e Alterar Cotação), com quarto
    ("Nacional Plus 8x", "Quarto"), ("Nacional Plus 6x", "Quarto"), ("Nacional Plus 4x", "Quarto"),
    ("Nacional III", "Quarto"),
]
ANGARIACOES = ["Não Há", "1ª Parcela 100%, 2ª Parcela 50%", "2 Primeiras Parcelas 100%, 3ª Parcela 50%",
               "1ª Parcela 100%, 2ª Parcela 80%", "1ª Parcela 100%", "1ª Parcela 20%", "3 Primeiras Parcelas 100%"]


class Bradesco(Operadora):
    id = "bradesco"
    nome = "Bradesco"
    produto = "Cotação SPG (Saúde PME, 3 a 29 vidas)"
    cor = "#CC092F"
    min_vidas = 3
    max_vidas = 29
    faixas_idade_exata = ("0 - 18", "59+")
    etapas = (
        ("login", "Login"), ("portal", "Cotação SPG"), ("empresa", "Empresa"), ("grupos", "Vidas e idades"),
        ("regiao", "Região"), ("personalizar", "Personalizar"), ("configuracao", "Contrato e grupo"),
        ("resultado", "Planos"), ("complementares", "Dados complementares"), ("calculo", "Cálculo e PDF"),
        ("alterar", "Alterar cotação"),
    )

    PADRAO_CONFIG = {
        "urls": {"login": "https://wwwn.bradescoseguros.com.br/pnegocios2/wps/portal/portaldenegociosnovo/",
                 "home": "https://wwwn.bradescoseguros.com.br/pnegocios/wps/myportal/portalnegocios/arealogada/home",
                 "cotador": "https://wwwn.bradescoseguros.com.br/pnegocios/wps/myportal/portalnegocios/arealogada/"
                            "saude/cotacoes/cotacao-spg"},
        "execucao": {"timeout_padrao_ms": 30000, "timeout_login_ms": 60000, "timeout_codigo_ms": 300000,
                     "sair_do_portal_min": 3, "timeout_emissao_ms": 180000, "timeout_tela_ms": 60000,
                     "timeout_download_ms": 120000},
        # Só ensaio até a calibragem no portal real terminar (decisão do Tiago: "Gerar processo" só quando ele pedir).
        "emissao_liberada": False,
        # Modo de testes (só na calibragem): ignora o registro anti-reemissão da empresa a cada pedido (ver etapas).
        "teste_repetir": False,
        # Padrões = o que o corretor fez no vídeo (Seção 5 e 6 do mapa).
        "padroes": {"categoria": "Sócios e Diretores", "adesao": "compulsoria", "cobertura": "top",
                    "mais_de_um_titular": "nao", "desconto_folha": "nao", "desconto_comissao": "nenhum",
                    "sucursal": "978", "codigo_corretor": "438451", "acomodacao": "Quarto",
                    "coparticipacao": "com", "copart_percentual": "30%", "dental": "Sem plano dental",
                    "identificador_com": "COM COPAY", "identificador_sem": "SEM COPAY",
                    "email_corretora": "", "celular_corretora": "",
                    "angariacao": "3 Primeiras Parcelas 100%", "corretagem": "2% vitalício a partir da 4ª parcela",
                    "intermediario_papel": "corretor", "intermediario_email": "", "intermediario_celular": "",
                    "transferencia": "nao", "ramo": "OUTROS", "planos_modo": "lista", "planos": []},
        "faixas_idade_exata": ["0 - 18", "59+"],
        "criterio_plano": {"tipo": "menor_preco", "quantidade": 1},
        "conferencias": {"aliquota_iof": "0.0238", "tolerancia_reais": "0.05"},
        "saida": {"nome_pdf_arquivo": "BRADESCO_{cnpj}_{protocolo}_{plano_arquivo}.pdf",
                  "nome_pdf_destino": "BRADESCO {plano_arquivo}.pdf", "substituir_no_destino": True,
                  "nomes_arquivo": {}},
    }

    OPCOES_COPART = [["sem", "Sem coparticipação"], ["com", "Com coparticipação"],
                     ["as_duas", "Com e sem", "com e sem coparticipação (2 cálculos por plano)"]]
    OPCOES_ADESAO = [["compulsoria", "Compulsória"], ["opcional", "Opcional"]]
    OPCOES_COBERTURA = [["top", "Top"], ["hospitalar", "Hospitalar"]]
    OPCOES_DENTAL = [[d, d] for d in DENTAIS]

    # ------------------------------------------------------------------ tela
    def campos(self, cfg: dict) -> list[dict]:
        padroes = cfg.get("padroes", {})
        return [
            {"chave": "coparticipacao", "rotulo": "Coparticipação", "tipo": "escolha", "robo": True,
             "opcoes": self.OPCOES_COPART, "padrao": padroes.get("coparticipacao", "com"), "multiplica": {"as_duas": 2},
             "ajuda": "Com e sem: dois cálculos por plano no mesmo processo, cada um com o seu PDF."},
            {"chave": "dental", "rotulo": "Dental conjugado", "tipo": "escolha", "robo": True,
             "opcoes": self.OPCOES_DENTAL, "padrao": padroes.get("dental", "Sem plano dental")},
            {"chave": "adesao", "rotulo": "Modalidade de adesão", "tipo": "escolha", "robo": True,
             "opcoes": self.OPCOES_ADESAO, "padrao": padroes.get("adesao", "compulsoria")},
            {"chave": "cobertura", "rotulo": "Cobertura", "tipo": "escolha", "robo": True,
             "opcoes": self.OPCOES_COBERTURA, "padrao": padroes.get("cobertura", "top")},
        ]

    def configuracao(self, cfg: dict) -> list[dict]:
        pasta = cfg.get("saida", {}).get("pasta", "")
        return [
            {"etapa": "login", "faz": "Entra no Portal de Negócios sozinho, só quando o portal pede: CPF/CNPJ, "
                                      "Continuar e a senha. Se o portal pedir um código, a tela pede para você.",
             "campos": [{"tipo": "credenciais", "rotulo": "Login no portal",
                         # o maxlength=8 do campo Senha do portal não é o limite real (07/11): a tela não corta a senha
                         "senha_max": 64, "campos": self.campos_login(),
                         "ajuda": "Fica no cofre do Windows, só neste computador e no seu usuário do Windows. A senha "
                                  "nunca volta para a tela. CPF/CNPJ: o da 1ª tela do portal (a corretora). CPF de "
                                  "acesso: o que a página da senha pede. CPF do intermediário: o da aba Intermediário "
                                  "dos Dados complementares (o portal completa o nome)."},
                        {"chave": "padroes.email_corretora", "rotulo": "E-mail da corretora (assinatura da proposta)",
                         "tipo": "texto", "exemplo": "contato@suacorretora.com.br",
                         "ajuda": "O portal pede este e-mail nos Dados complementares (aba Corretora) antes de gerar o "
                                  "processo. Fica na configuração do robô (não é senha). Sem ele o robô para antes de "
                                  "gerar o processo."},
                        {"chave": "tempos.sair_do_portal_min", "rotulo": "Sair do portal depois de (minutos sem pedidos)",
                         "tipo": "numero", "minimo": 0, "maximo": 120,
                         "ajuda": "Com a fila vazia por esse tempo, o robô sai do portal e fecha a janela. 0 = não sai "
                                  "sozinho."}]},
            {"etapa": "portal", "faz": "Menu SAÚDE, COTAÇÕES, Cotação SPG e o produto Saúde e conjugado, como no vídeo.",
             "campos": [{"chave": "teste_repetir", "rotulo": "Modo de testes: repetir a mesma cotação", "tipo": "sim_nao",
                         "booleano": True,
                         "ajuda": "Só para a calibragem. Com \"sim\", cada pedido gera um processo NOVO no portal, mesmo que "
                                  "a empresa já tenha um processo no registro (o robô tira o antigo do registro sem "
                                  "conferir no portal; ele fica no histórico). Desligue para o uso de verdade: é o "
                                  "registro que impede processos duplicados."}]},
            {"etapa": "empresa", "faz": "Digita o CNPJ, clica em Consultar e confere a razão social.", "campos": []},
            {"etapa": "grupos", "faz": "Grupo 1 com a categoria funcional, as vidas de cada faixa e a idade de cada "
                                       "pessoa em 00 a 18 e 59 ou mais (você informa na Nova cotação).",
             "campos": [{"chave": "padroes.categoria", "rotulo": "Categoria funcional do grupo", "tipo": "escolha",
                         "opcoes": [[c, c] for c in CATEGORIAS]}]},
            {"etapa": "regiao", "faz": "Confere a região que o portal indica pelo CNPJ e avança.", "campos": []},
            {"etapa": "personalizar", "faz": "Pula (operadora atual, hospital e valor desejado), como no vídeo.",
             "campos": []},
            {"etapa": "configuracao", "faz": "Aba Contrato e aba Grupo 1, depois Calcular (preços indicativos: ainda "
                                             "nada oficial).",
             "campos": [
                 {"chave": "padroes.adesao", "rotulo": "Modalidade de adesão", "tipo": "escolha", "por_cotacao": True,
                  "opcoes": self.OPCOES_ADESAO},
                 {"chave": "padroes.cobertura", "rotulo": "Cobertura", "tipo": "escolha", "por_cotacao": True,
                  "opcoes": self.OPCOES_COBERTURA},
                 {"tipo": "info", "rotulo": "Modalidade de pagamento", "texto": "Faixa Etária, como no vídeo."},
                 {"chave": "padroes.mais_de_um_titular", "rotulo": "Possui mais de 1 titular", "tipo": "sim_nao"},
                 {"chave": "padroes.desconto_folha", "rotulo": "Desconto Folha de Pagamento Bradesco", "tipo": "sim_nao"},
                 {"chave": "padroes.desconto_comissao", "rotulo": "Desconto de comissionamento", "tipo": "escolha",
                  "opcoes": [["nenhum", "Nenhum"], ["2,5", "2,5%"], ["5", "5%"], ["7,5", "7,5%"], ["10", "10%"]]},
                 {"chave": "padroes.sucursal", "rotulo": "Número da sucursal", "tipo": "texto",
                  "sugestoes": ["978", "969"], "ajuda": "Vídeo: 978 - SANTANA MERCADO."},
                 {"chave": "padroes.codigo_corretor", "rotulo": "Código do corretor", "tipo": "texto",
                  "sugestoes": ["438451"], "ajuda": "Vídeo: 438451 - NEWPORT CONSULTORIA E CORRETORA DE."},
                 {"chave": "padroes.coparticipacao", "rotulo": "Coparticipação", "tipo": "escolha", "por_cotacao": True,
                  "opcoes": self.OPCOES_COPART,
                  "ajuda": "Com e sem: o 1º cálculo sai com coparticipação e o 2º pelo Alterar Cotação, sem (esse "
                           "caminho não aparece no vídeo: confira no primeiro ensaio de emissão)."},
                 {"chave": "padroes.copart_percentual", "rotulo": "Percentual de coparticipação (Alterar Cotação)",
                  "tipo": "texto", "sugestoes": ["30%"]},
             ]},
            {"etapa": "resultado", "faz": "Lê os planos do carrossel, escolhe o pedido e o dental. O ensaio para aqui, "
                                          "antes de Iniciar cotação: nada oficial é gerado.",
             "campos": [{"chave": "padroes.dental", "rotulo": "Dental conjugado", "tipo": "escolha", "por_cotacao": True,
                         "opcoes": self.OPCOES_DENTAL,
                         "ajuda": "O portal já vem com o Padrão Doc 1 marcado; como o corretor no vídeo, o robô troca "
                                  "para o que você escolher (padrão: Sem plano dental) e confere que ficou marcado."}]},
            {"etapa": "complementares", "faz": "Abas Corretora, Intermediário, Transferência Bradesco e Processo; "
                                               "depois Gerar processo (cria o Número do Processo, válido por 40 dias).",
             "campos": [
                 {"chave": "padroes.celular_corretora", "rotulo": "Celular da corretora (opcional)", "tipo": "texto"},
                 {"chave": "padroes.angariacao", "rotulo": "Angariação", "tipo": "escolha",
                  "opcoes": [[x, x] for x in ANGARIACOES]},
                 {"chave": "padroes.corretagem", "rotulo": "Corretagem", "tipo": "texto",
                  "sugestoes": ["2% vitalício a partir da 4ª parcela"]},
                 {"chave": "padroes.intermediario_papel", "rotulo": "Intermediário: perfil", "tipo": "escolha",
                  "opcoes": [["corretor", "Corretor"], ["produtor", "Produtor"], ["angariador", "Angariador"]]},
                 {"chave": "padroes.intermediario_email", "rotulo": "Intermediário: e-mail (opcional)", "tipo": "texto"},
                 {"chave": "padroes.transferencia", "rotulo": "Transferência Bradesco", "tipo": "sim_nao",
                  "ajuda": "Não, como no vídeo (Sim pediria os CPFs ou cartões Bradesco dos proponentes)."},
                 {"chave": "padroes.ramo", "rotulo": "Ramo de atividade", "tipo": "texto", "sugestoes": ["OUTROS"]},
             ]},
            {"etapa": "calculo", "faz": "Lê o Número do Processo e o cálculo, confere vidas, prêmio e IOF de 2,38%, e "
                                        "salva o PDF pela janela Imprimir. Nunca clica em Finalizar Cálculo.",
             "campos": [
                 {"chave": "padroes.identificador_com", "rotulo": "Identificação do cálculo com coparticipação",
                  "tipo": "texto", "sugestoes": ["COM COPAY"],
                  "ajuda": "O robô digita em \"Identifique o cálculo a ser armazenado\" antes do Imprimir; esse texto "
                           "sai no cabeçalho do PDF (vídeo: COM COPAY)."},
                 {"chave": "padroes.identificador_sem", "rotulo": "Identificação do cálculo sem coparticipação",
                  "tipo": "texto", "sugestoes": ["SEM COPAY"]},
                 {"chave": "arquivos.nome_pdf_destino", "rotulo": "Nome do PDF na pasta do cliente", "tipo": "texto",
                  "validar": "nome_pdf", "ajuda": "{plano_arquivo} vira o nome do plano em letras maiúsculas.",
                  "exemplo_pdf": {"plano": "Nacional Plus 4x", "versoes": ["COM COPARTICIPACAO", "SEM COPARTICIPACAO"],
                                  "frase_versoes": "Com “Com e sem” coparticipação"}},
                 {"chave": "arquivos.substituir_no_destino", "rotulo": "Substituir o PDF antigo com o mesmo nome",
                  "tipo": "sim_nao", "booleano": True},
                 {"chave": "arquivos.nomes_arquivo", "rotulo": "Nomes curtos", "tipo": "pares",
                  "colunas": ["Plano no robô", "Nome no arquivo"], "exemplos": ["Nacional Plus 4x", "NACIONAL PLUS"]},
             ]},
            {"etapa": "alterar", "faz": "Os planos seguintes da mesma empresa saem no mesmo processo: Alterar Cotação, "
                                        "troca plano, acomodação e coparticipação, Calcular.", "campos": []},
        ]

    def planos_conhecidos(self) -> list[dict]:
        return [{"nome": n, "acomodacao": a} for n, a in PLANOS_VIDEO]

    def marcada_na_nova_cotacao(self, cfg: dict) -> bool:
        """Em calibragem (só ensaio), a Nova cotação começa com a Bradesco desmarcada."""
        return bool(cfg.get("emissao_liberada"))

    # ------------------------------------------------------------------ pedidos
    def montar_pedido(self, dados: dict, cfg: dict, linha: int = 0):
        from .planilha import montar_pedido
        return montar_pedido(dados, linha, cfg)

    def qtd_cotacoes(self, pedido) -> int:
        return (len(pedido.planos) or (pedido.criterio_quantidade or 0)) * len(pedido.versoes_copart)

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
        return {"com": "com coparticipação", "sem": "sem coparticipação"}

    # ------------------------------------------------------------------ robô
    def nova_sessao(self, cfg, log, contexto, page, estado, resultados, mapa, ensaio: bool, avisar=None,
                    parar=None, pedir_codigo=None, reemitir=()):
        from .etapas import Sessao
        _preparar_navegador(contexto, page, log)
        _campos_de_cadastro_no_mapa(mapa)
        return Sessao(cfg=cfg, log=log, contexto=contexto, page=page, estado=estado, resultados=resultados, mapa=mapa,
                      ensaio=ensaio, avisar=avisar, parar=parar, pedir_codigo=pedir_codigo,
                      reemitir={str(x) for x in (reemitir or ())})

    def login(self, sessao) -> None:
        from .login import entrar
        entrar(sessao)

    # O login do portal (CPF/CNPJ e senha, em duas etapas) e o CPF do intermediário (aba Intermediário): os três no
    # cofre do Windows, nunca na configuração.
    # Portal real 07/11: a 1ª tela pede o CPF/CNPJ (a corretora) e a página da senha (nidp) pede o CPF de quem entra
    # ("Por favor digite um CPF válido para prosseguir") junto com a senha.
    CAMPOS_LOGIN = [{"chave": "documento", "rotulo": "CPF/CNPJ", "tipo": "cpf_cnpj", "artigo": "o"},
                    {"chave": "cpf", "rotulo": "CPF de acesso", "tipo": "cpf", "artigo": "o"},
                    {"chave": "senha", "rotulo": "Senha", "tipo": "senha", "artigo": "a"},
                    {"chave": "intermediario_cpf", "rotulo": "CPF do intermediário", "tipo": "cpf", "artigo": "o"}]
    mensagens_login = {}

    def campos_login(self) -> list[dict]:
        return [dict(c) for c in self.CAMPOS_LOGIN]

    def textos_tela(self) -> dict:
        return {
            "passo_login": "Na engrenagem do robô Bradesco (tela Login), guarde o CPF/CNPJ e a senha do Portal de "
                           "Negócios e o CPF do intermediário. Ficam no cofre do Windows, só neste computador. O robô "
                           "entra no portal sozinho quando o portal pede.",
            "passo_nova": "CNPJ, vidas por faixa (com a idade de cada pessoa em 0 - 18 e 59+) e os planos. Coparticipação, "
                          "dental, adesão e cobertura vêm da configuração do robô.",
            "perguntas": {
                "pdfs": ["Onde ficam os PDFs da Bradesco?",
                         "Cada plano vira um cálculo no processo da empresa e um PDF (a janela Imprimir do portal). Se você "
                         "informou a pasta do cliente, uma cópia vai para lá com o nome BRADESCO <PLANO>.pdf."],
                "versoes": ["Como funciona o processo da Bradesco?",
                            "Cada empresa gera um processo (Número do Processo, válido por 40 dias). O primeiro plano "
                            "sai do cotador novo; os outros saem do Alterar Cotação, no mesmo processo. Pedir de novo a "
                            "mesma empresa com os mesmos dados não gera outro processo."],
            },
            "nome_pdf": "BRADESCO <PLANO>.pdf",
            "planos": "Cada plano vira um cálculo no processo da empresa e um PDF. O “4x” é o reembolso do card "
                      "(os Nacional Plus só se diferenciam por ele).",
            "login_livre": "o seu login do Portal de Negócios",
        }

    def sair(self, sessao, prazo_s: float = 30) -> bool:
        from .etapas import sair_do_portal
        return sair_do_portal(sessao, prazo_s)

    def treino(self) -> dict:
        from .simulador.servidor import Simulador
        return {"iniciar": lambda: Simulador(8775, 8776).iniciar(), "portas": "portas 8775 e 8776",
                "login_falso": {"documento": Simulador.DOCUMENTO, "cpf": Simulador.CPF_ACESSO, "senha": Simulador.SENHA,
                                "intermediario_cpf": Simulador.CPF_INTERMEDIARIO}}

    def conectado(self, page) -> bool:
        from .login import logado
        return logado(page)

    def recuperar_pdfs(self, sessao) -> None:
        for chave, item in sessao.estado.pendencias():
            sessao.log.warning(f"PENDENTE ({item['status']}): {item.get('plano')} | processo {item.get('protocolo', '-')}"
                               " — o robô não tenta de novo sozinho; confira no portal ('Acompanhar processos').")

    def processar(self, sessao, pedido) -> None:
        if not sessao.ensaio and not sessao.cfg.get("emissao_liberada"):
            from .etapas import com_versoes
            from nucleo.modelo import ResultadoPlano
            sessao.log.error(f"[{pedido.id}] A Bradesco está em calibragem: só o ensaio está liberado. Nada foi feito "
                             "no portal.")
            for alvo in com_versoes(pedido, list(pedido.planos)) or [None]:
                sessao.resultados.plano(ResultadoPlano(
                    pedido_id=pedido.id, linha=pedido.linha, cnpj=pedido.cnpj, plano=alvo.nome if alvo else "",
                    acomodacao=(alvo.acomodacao or "") if alvo else "", status="ERRO", etapa_erro="calibragem",
                    versao=(alvo.versao if alvo and alvo.versao else pedido.coparticipacao),
                    erro="a Bradesco ainda está em calibragem: só o ensaio está liberado (nada foi gerado no portal)"))
            return
        from .fluxo import processar_pedido
        processar_pedido(sessao, pedido)


# Campos do formulário Alterar Cotação cujo nome tem "código" mas são de cadastro (a sucursal, o corretor), não de
# verificação: sem isso o mapa tomava a tela por "tela de código" e não gravava nada (10/11, "codigoSucursal").
_CAMPOS_DE_CADASTRO = {"codigosucursal", "codigocorretor", "cpdcorretor"}


def _campos_de_cadastro_no_mapa(mapa) -> None:
    """O Mapeador não grava telas de código de verificação. Se o único campo que bateu com "código" é um desses campos
    de cadastro, a tela vale como qualquer outra; os demais testes (tela de login e campo de senha) continuam valendo."""
    original = getattr(mapa, "tela_sensivel", None)
    if original is None or getattr(mapa, "_np_bradesco_campos", False):
        return

    def tela_sensivel(page):
        resultado = original(page)
        if resultado != "codigo":
            return resultado
        campo = "".join(str(getattr(mapa, "_campo_codigo", "")).lower().split())
        if campo not in _CAMPOS_DE_CADASTRO:
            return resultado
        try:
            from urllib.parse import urlparse

            from nucleo.navegador import _JS_CAMPO_SENHA
            if mapa.path_login and urlparse(page.url).path.rstrip("/").lower() == mapa.path_login:
                return "login"
            return "login" if any(f.evaluate(_JS_CAMPO_SENHA) for f in page.frames) else None
        except Exception:  # noqa: BLE001
            return "login"

    try:
        mapa.tela_sensivel = tela_sensivel
        mapa._np_bradesco_campos = True
    except Exception:  # noqa: BLE001
        pass


def _preparar_navegador(contexto, page, log) -> None:
    """A janela "Imprimir" do portal chama window.print(): o robô salva a janela como PDF, sem a caixa de impressão.
    Avisos do navegador (alert/confirm) ficam no log; o robô só confirma os de saída da página."""
    if getattr(contexto, "_np_bradesco", False):
        return
    try:
        contexto._np_bradesco = True
    except Exception:  # noqa: BLE001
        pass
    try:
        contexto.add_init_script("window.print = function () {};")
    except Exception:  # noqa: BLE001
        pass

    def dialogo(d) -> None:
        try:
            log.info(f"Aviso do navegador ({d.type}): {' '.join((d.message or '').split())[:200]}")
            if d.type in ("alert", "beforeunload"):
                d.accept()
            else:
                d.dismiss()
        except Exception:  # noqa: BLE001
            pass

    try:
        contexto.on("page", lambda p: p.on("dialog", dialogo))
        for p in contexto.pages:
            p.on("dialog", dialogo)
    except Exception:  # noqa: BLE001
        pass
