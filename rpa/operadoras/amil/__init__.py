"""Amil — vendasmil, Cotação PME.

Levantado do vídeo de um corretor da Newport (codegen/amil_mapa_video.md). Um pedido (empresa) = uma OPORTUNIDADE (OPP-...);
cada plano = uma COTAÇÃO (COT-...) dentro dela, com o seu PDF. O ponto sem volta é "Concluir Cotação". O login pede um código
de verificação de 8 dígitos enviado por e-mail: o robô pede o código na tela do Newport. Os seletores (seletores.py) ainda
precisam ser calibrados no portal real com o ensaio.

Enquanto a calibragem não termina, `emissao_liberada: false` (padrão): o robô só faz ensaio (que já cria a oportunidade e uma
cotação "Em Digitação" por plano). Com o ensaio conferido e o pedido do Tiago, liga-se `emissao_liberada: true`.
"""
from __future__ import annotations

from ..base import Operadora
from .pedido import PLANOS_CONHECIDOS, familia

NOMES_DE_PDF = {"PLATINUM R1 COPART": "PLATINUM", "AMIL BLACK I R1 COPART": "BLACK", "AMIL S2500 R1 QP COPART": "S2500"}


class Amil(Operadora):
    id = "amil"
    nome = "Amil"
    produto = "Cotação PME (vendasmil)"
    cor = "#0057B8"
    min_vidas = 2
    max_vidas = 29
    faixas_idade_exata = ()
    etapas = (
        ("login", "Login"), ("oportunidade", "Oportunidade"), ("vinculo", "Vínculo de vendas"),
        ("planos", "Planos e vidas"), ("revisar", "Revisar cotação"), ("concluir", "Concluir e PDF"),
    )

    PADRAO_CONFIG = {
        "urls": {"login": "https://vendas.amil.com.br/login", "home": "https://vendas.amil.com.br/"},
        "execucao": {"timeout_padrao_ms": 30000, "timeout_login_ms": 60000, "timeout_codigo_ms": 300000,
                     "sair_do_portal_min": 3, "timeout_emissao_ms": 180000, "timeout_tela_ms": 60000,
                     "timeout_download_ms": 120000},
        # Só ensaio até a calibragem no portal real terminar (decisão do Tiago: "Concluir Cotação" só quando ele pedir).
        "emissao_liberada": False,
        # Padrões = o que o corretor fez no vídeo (Seção 7 do mapa).
        "padroes": {"coligacao": "nao", "corretor": "EDLAINE ABREU SOARES", "supervisor": "", "dental_aderir": "sim",
                    "planos": []},
        "faixas_idade_exata": [],
        "criterio_plano": {"tipo": "menor_preco", "quantidade": 1},
        "conferencias": {"aliquota_iof": "0.0238", "tolerancia_reais": "0.05"},
        "saida": {"nome_pdf_arquivo": "AMIL_{cnpj}_{protocolo}.pdf", "nome_pdf_destino": "AMIL {plano_arquivo} {versao}.pdf",
                  "substituir_no_destino": True, "nomes_arquivo": dict(NOMES_DE_PDF)},
    }

    OPCOES_COLIGACAO = [["nao", "Não"], ["sim", "Sim"]]

    # ------------------------------------------------------------------ tela
    # O corretor, o supervisor e a coligação são do robô (engrenagem), nunca de um pedido avulso.
    def campos(self, cfg: dict) -> list[dict]:
        padroes = cfg.get("padroes", {})
        return [
            {"chave": "dental", "titulo": "Dental", "rotulo": "Aderir ao dental da cotação", "tipo": "sim_nao", "robo": True,
             "padrao": str(padroes.get("dental_aderir", "sim")),
             "ajuda": "No vídeo, o portal oferece o DENTAL BRONZE PJ PROMO (R$ 0,00 nos 12 primeiros meses) e o corretor "
                      "deixa marcado em Aderir."},
        ]

    def configuracao(self, cfg: dict) -> list[dict]:
        return [
            {"etapa": "login", "faz": "Entra no vendasmil sozinho, só quando o portal pede, com o login que você guarda aqui. "
                                      "O portal manda um código de 8 dígitos para o seu e-mail (vale 15 min): a tela do "
                                      "Newport pede o código e o robô digita. A sessão fica no navegador do robô para pedir "
                                      "código o menos possível.",
             "campos": [{"tipo": "credenciais", "rotulo": "Login no portal", "senha_max": 64, "campos": self.campos_login(),
                         "ajuda": "Fica no cofre do Windows, só neste computador e no seu usuário do Windows. A senha nunca "
                                  "volta para a tela. O código de verificação não é guardado: você digita na tela quando "
                                  "o robô pedir."},
                        {"chave": "tempos.sair_do_portal_min", "rotulo": "Sair do portal depois de (minutos sem pedidos)",
                         "tipo": "numero", "minimo": 0, "maximo": 120,
                         "ajuda": "Com a fila vazia por esse tempo, o robô sai do portal e fecha a janela. Atenção: depois de "
                                  "sair, o próximo login pede um novo código por e-mail. 0 = não sai sozinho."}]},
            {"etapa": "oportunidade", "faz": "Menu Criar Oportunidade PME, digita o CNPJ (o portal preenche o resto pela Receita "
                                             "Federal) e conclui a oportunidade (OPP). Uma empresa = uma oportunidade: se o "
                                             "robô já criou a OPP dela, reabre, não cria outra. ATENÇÃO: o ensaio já cria a "
                                             "oportunidade no portal.",
             "campos": [{"chave": "padroes.coligacao", "rotulo": "Haverá coligação?", "tipo": "escolha",
                         "opcoes": self.OPCOES_COLIGACAO, "ajuda": "No vídeo: Não."}]},
            {"etapa": "vinculo", "faz": "Criar Cotação: escolhe o corretor do Vínculo de Vendas e continua. Cada plano é uma "
                                         "cotação (COT) da oportunidade.",
             "campos": [{"chave": "padroes.corretor", "rotulo": "Nome do corretor", "tipo": "texto",
                         "sugestoes": ["EDLAINE ABREU SOARES"],
                         "ajuda": "O texto como aparece na lista do portal (o código e o nome; basta o nome). No vídeo: "
                                  "EDLAINE ABREU SOARES."},
                        {"chave": "padroes.supervisor", "rotulo": "Nome do supervisor", "tipo": "texto",
                         "ajuda": "Vazio = nenhum (no vídeo: \"Nenhum supervisor disponível\")."}]},
            {"etapa": "planos", "faz": "Escolhe o plano pelo texto exato da lista, preenche as 10 faixas e só depois lê o valor "
                                       "por vida (ele muda com o total de vidas). Confere o aditivo e o dental.",
             "campos": [{"chave": "padroes.dental_aderir", "rotulo": "Aderir ao dental", "tipo": "sim_nao", "por_cotacao": True,
                         "ajuda": "No vídeo: aderir ao DENTAL BRONZE PJ PROMO (o robô confere o estado final: dental marcado e "
                                  "o aditivo AMIL RESGATE SAÚDE I presente)."}]},
            {"etapa": "revisar", "faz": "Lê o Resumo Geral e confere: soma das faixas = Valor Total; 50% na 1ª e 2ª parcelas "
                                        "quando há o selo; total após 12 meses = total + dental. Se algo não bater, para antes "
                                        "de concluir. O ensaio para aqui.", "campos": []},
            {"etapa": "concluir", "faz": "Concluir Cotação (a cotação vira Concluída e o portal gera o PDF) e Baixar PDF. Nunca "
                                         "clica em Criar Proposta. Se cair depois de Concluir, reabre a cotação pela "
                                         "oportunidade e baixa o PDF, sem criar outra.",
             "campos": [
                 {"chave": "arquivos.nome_pdf_destino", "rotulo": "Nome do PDF na pasta do cliente", "tipo": "texto",
                  "validar": "nome_pdf",
                  "ajuda": "{plano_arquivo} é o apelido do plano (abaixo) e {versao} é o nome curto da empresa, o campo \"nome "
                           "para achar depois\" da Nova cotação (vazio = sem nome).",
                  "exemplo_pdf": {"plano": "PLATINUM R1 COPART", "versoes": ["CALANDRINI"],
                                  "frase_versoes": "Com o nome curto da empresa"}},
                 {"chave": "arquivos.nomes_arquivo", "rotulo": "Apelido de cada plano no nome do PDF", "tipo": "pares",
                  "colunas": ["Plano no portal", "Apelido no arquivo"], "exemplos": ["PLATINUM R1 COPART", "PLATINUM"],
                  "ajuda": "Como a Newport chama o plano no PDF: AMIL PLATINUM CALANDRINI.pdf. Plano sem apelido sai com o nome "
                           "inteiro."},
                 {"chave": "arquivos.substituir_no_destino", "rotulo": "Substituir o PDF antigo com o mesmo nome",
                  "tipo": "sim_nao", "booleano": True,
                  "ajuda": "Desligado, o robô guarda o novo com a data no nome e não apaga o antigo."},
             ]},
        ]

    def marcada_na_nova_cotacao(self, cfg: dict) -> bool:
        """Em calibragem (só ensaio) a Nova cotação começa com a Amil desmarcada."""
        return bool(cfg.get("emissao_liberada"))

    def planos_conhecidos(self) -> list[dict]:
        return [{"nome": n, "acomodacao": familia(n)} for n in PLANOS_CONHECIDOS]

    # ------------------------------------------------------------------ pedidos
    def montar_pedido(self, dados: dict, cfg: dict, linha: int = 0):
        from .planilha import montar_pedido
        return montar_pedido(dados, linha, cfg)

    def qtd_cotacoes(self, pedido) -> int:
        return len(pedido.planos)

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
        from .telas import ajustar_mapa
        ajustar_mapa(mapa, page)
        return Sessao(cfg=cfg, log=log, contexto=contexto, page=page, estado=estado, resultados=resultados, mapa=mapa,
                      ensaio=ensaio, avisar=avisar, parar=parar, pedir_codigo=pedir_codigo,
                      reemitir={str(x) for x in (reemitir or ())})

    def login(self, sessao) -> None:
        from .login import entrar
        entrar(sessao)

    mensagens_login = {
        "codigo": "O código de verificação da {op} não chegou a tempo ou não foi aceito (ele vale 15 minutos e chega por "
                  "e-mail, de mail@noreply.amil.com.br). Tente de novo.",
    }

    def textos_tela(self) -> dict:
        """Os textos da Amil na tela: oportunidade e cotação, código por e-mail, o ensaio que já cria a oportunidade."""
        return {
            "passo_login": "Na engrenagem do robô (tela Login), guarde o usuário e a senha do vendasmil. Eles ficam no cofre do Windows. A Amil manda um código de 8 dígitos para o seu e-mail a cada login: a tela pede o código e você digita (o robô não lê o seu e-mail).",
            "passo_nova": "CNPJ, vidas por faixa etária e os planos (o nome exato da lista da Amil). Cada empresa vira uma oportunidade e cada plano uma cotação com PDF. ATENÇÃO: o ensaio da Amil já cria a oportunidade e uma cotação “Em Digitação” por plano no portal (vencem em 1 dia); só não conclui.",
            "perguntas": {
                "sair_do_portal": [
                    "Por que o robô pede um código de verificação?",
                    "A Amil manda um código de 8 dígitos para o e-mail do usuário em cada login (vale 15 minutos). A tela mostra “Digite o código que chegou no seu e-mail”; copie do e-mail e digite. O robô guarda a sessão no navegador dele para pedir o código o menos possível, e sair do portal (fila vazia, Parar, Sair do portal agora) faz o próximo login pedir um código novo."
                ],
                "pdfs": [
                    "Onde ficam os PDFs?",
                    "Se você informou a pasta do cliente, uma cópia vai para lá com o nome AMIL <PLANO> <EMPRESA>.pdf (o nome curto da empresa é o campo “nome para achar depois”). O robô também guarda uma cópia na pasta dele, que é a que você baixa por aqui."
                ],
                "configurar": [
                    "Como mudo o corretor ou o apelido dos planos no nome do PDF?",
                    "Clique na engrenagem do cartão da Amil (no pé do menu ou em Robôs). O corretor do Vínculo de Vendas fica na tela “Vínculo de vendas”; o apelido de cada plano no nome do PDF fica na tela “Concluir e PDF”."
                ],
                "versoes": [
                    "O ensaio da Amil cria alguma coisa no portal?",
                    "Sim. O portal só mostra os valores depois de criar a oportunidade (OPP) e uma cotação (COT) “Em Digitação” por plano, que vencem em 1 dia. O ensaio para em Revisar Cotação, sem concluir. Quando você pedir a cotação de verdade, o robô reabre a mesma oportunidade e continua a mesma cotação, sem duplicar."
                ],
            },
            "nome_pdf": "AMIL <PLANO> <EMPRESA>.pdf",
            "planos": "Cada plano vira uma cotação e um PDF. O nome precisa ser igual ao da lista da Amil; a lista cresce sozinha com os planos que o robô encontrar no portal. ATENÇÃO: o ensaio da Amil já cria a oportunidade e uma cotação “Em Digitação” por plano no portal (vencem em 1 dia); só não conclui.",
            "login_livre": "o seu usuário",
        }

    def sair(self, sessao, prazo_s: float = 30) -> bool:
        from .etapas import sair_do_portal
        return sair_do_portal(sessao, prazo_s)

    def treino(self) -> dict:
        from .simulador.servidor import Simulador
        return {"iniciar": lambda: Simulador(8785).iniciar(), "portas": "porta 8785",
                "login_falso": {"usuario": Simulador.USUARIO, "senha": Simulador.SENHA}}

    def conectado(self, page) -> bool:
        from .telas import logado
        return logado(page)

    def recuperar_pdfs(self, sessao) -> None:
        pass     # a recuperação é feita pedido a pedido (fluxo.preparar/_percorrer): reabre a COT e baixa o PDF

    def processar(self, sessao, pedido) -> None:
        if not sessao.ensaio and not sessao.cfg.get("emissao_liberada"):
            from nucleo.modelo import ResultadoPlano
            sessao.log.error(f"[{pedido.id}] A Amil está em calibragem: só o ensaio está liberado. Nada foi feito no portal.")
            for alvo in list(pedido.planos) or [None]:
                sessao.resultados.plano(ResultadoPlano(
                    pedido_id=pedido.id, linha=pedido.linha, cnpj=pedido.cnpj, plano=alvo.nome if alvo else "",
                    status="ERRO", etapa_erro="calibragem",
                    erro="a Amil ainda está em calibragem: só o ensaio está liberado (nada foi feito no portal)"))
            return
        from .fluxo import processar_pedido
        processar_pedido(sessao, pedido)
