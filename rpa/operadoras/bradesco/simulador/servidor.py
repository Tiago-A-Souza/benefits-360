"""Servidor do simulador: Portal de Negócios (portal + cotador SPG + páginas antigas EEEM) e o login (nidp)
em portas diferentes, como os dois domínios do portal real.

Telas e textos do vídeo do corretor (codegen/bradesco_mapa_video.md). O cotador novo é uma página só
(estatico/cotador.html); o cálculo e o "Alterar Cotação" são páginas antigas dentro de um iframe.
"""
from __future__ import annotations

import html
import json
import secrets
import threading
import time
from decimal import ROUND_HALF_UP, Decimal
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

ESTATICO = Path(__file__).parent / "estatico"

ROTA_LOGIN = "/pnegocios2/wps/portal/portaldenegociosnovo/"
BASE = "/pnegocios/wps/myportal/portalnegocios/arealogada"
ROTA_HOME = f"{BASE}/home"
ROTA_PAINEL = f"{BASE}/saude/painel-saude"
ROTA_COTADOR = f"{BASE}/saude/cotacoes/cotacao-spg"

# As 10 faixas: chave, rótulo no cotador novo, rótulo nas páginas antigas
FAIXAS = [("0-18", "00 a 18", "Até 18 anos"), ("19-23", "19 a 23", "19 a 23"), ("24-28", "24 a 28", "24 a 28"),
          ("29-33", "29 a 33", "29 a 33"), ("34-38", "34 a 38", "34 a 38"), ("39-43", "39 a 43", "39 a 43"),
          ("44-48", "44 a 48", "44 a 48"), ("49-53", "49 a 53", "49 a 53"), ("54-58", "54 a 58", "54 a 58"),
          ("59+", "59 ou mais", "59 adiante")]
CHAVES = [f[0] for f in FAIXAS]

# Valores do vídeo: Nacional Plus (reembolso 4x), quarto, coparticipação 30% (cálculo 1) e Nacional III (cálculo 2).
_PLUS4 = ["1155.96", "1364.03", "1650.47", "1980.58", "2257.84", "2325.58", "2831.53", "3330.44", "3963.22", "6935.24"]
_N3 = ["499.13", "588.97", "712.65", "855.19", "974.90", "1004.15", "1222.61", "1438.04", "1711.26", "2994.54"]

# Planos do simulador: código, nome no card, reembolso (Nx tabela; 0 = sem multiplicador), acomodação nas páginas
# antigas, acomodação do grupo no cotador novo, base de preço e fator.
PLANOS = [
    ("TPN8", "Nacional Plus", 8, "Múltiplo 8", "Quarto", _PLUS4, "1.42162"),
    ("TPN6", "Nacional Plus", 6, "Múltiplo 6", "Quarto", _PLUS4, "1.23309"),
    ("TPN4", "Nacional Plus", 4, "Múltiplo 4", "Quarto", _PLUS4, "1"),
    ("TN3P", "Nacional III", 0, "Quarto Privativo", "Quarto", _N3, "1"),
    ("TN3M2", "Nacional III", 2, "Múltiplo 2", "Quarto", _N3, "1.12"),
    ("TN3M3", "Nacional III", 3, "Múltiplo 3", "Quarto", _N3, "1.2"),
    ("TN2P", "Nacional II", 0, "Quarto Privativo", "Quarto", _N3, "0.81"),
    ("TN2E", "Nacional II", 0, "Enfermaria", "Enfermaria", _N3, "0.7"),
    ("TEFE", "Efetivo", 0, "Enfermaria", "Enfermaria", _N3, "0.55"),
]
FATOR_SEM_COPART = Decimal("1.18")
DENTAIS = [("Sem plano dental", None), ("Premium Top 1", "90.29"), ("Padrão Doc White", "27.90"),
           ("Padrão Doc 1", "22.13")]
EMPRESAS = {   # CNPJs fictícios
    "11222333000181": {"razao": "PADARIA MODELO DE TREINO LTDA", "uf": "SP", "cidade": "SAO PAULO",
                       "natureza": "Sociedade Empresarial Limitada", "atividade": "Padaria e confeitaria"},
    "11444777000161": {"razao": "OFICINA EXEMPLO DE TREINO LTDA", "uf": "SP", "cidade": "SAO PAULO",
                       "natureza": "Sociedade Empresarial Limitada", "atividade": "Manutenção de veículos"},
}
SUCURSAIS = [("969", "LAPA MERCADO"), ("978", "SANTANA MERCADO")]
CORRETOR = ("438451", "NEWPORT CONSULTORIA E CORRETORA DE")
ANGARIACOES = ["Não Há", "1ª Parcela 100%, 2ª Parcela 50%", "2 Primeiras Parcelas 100%, 3ª Parcela 50%",
               "1ª Parcela 100%, 2ª Parcela 80%", "1ª Parcela 100%", "1ª Parcela 20%", "3 Primeiras Parcelas 100%"]
CORRETAGENS = ["2% vitalício a partir da 4ª parcela", "1% vitalício a partir da 4ª parcela"]
RAMOS = ["OUTROS", "OUTRAS ATIVIDADES DE SERVIÇOS", "COMÉRCIO VAREJISTA", "INDÚSTRIA"]
IOF = Decimal("0.0238")


def _d(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def reais(v: Decimal) -> str:
    q = _d(v)
    inteiro, cent = f"{q:.2f}".split(".")
    grupos = []
    while inteiro:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    return f"R$ {'.'.join(grupos)},{cent}"


def _plano(codigo: str):
    return next(p for p in PLANOS if p[0] == codigo)


def valores(codigo: str, copart: bool) -> dict[str, Decimal]:
    """Valor por vida em cada faixa."""
    _, _, _, _, _, base, fator = _plano(codigo)
    f = Decimal(fator) * (Decimal(1) if copart else FATOR_SEM_COPART)
    return {k: _d(Decimal(b) * f) for k, b in zip(CHAVES, base)}


def _cnpj_valido(d: str) -> bool:
    if len(d) != 14 or len(set(d)) == 1:
        return False

    def dig(base, pesos):
        r = sum(int(n) * p for n, p in zip(base, pesos)) % 11
        return "0" if r < 2 else str(11 - r)
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    return d[12:] == dig(d[:12], p1) + dig(d[:12] + dig(d[:12], p1), [6] + p1)


def _so_digitos(t) -> str:
    return "".join(ch for ch in str(t or "") if ch.isdigit())


def _fmt_cnpj(d: str) -> str:
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else d


class Simulador:
    # Login FALSO do simulador (nunca um login de verdade): CNPJ fictício da "corretora", senha e CPF de teste.
    DOCUMENTO = "11444777000161"
    SENHA = "Treino#Bradesco1"
    CPF_ACESSO = "11144477735"         # o CPF que a página da senha pede (portal real 07/11)
    CPF_INTERMEDIARIO = "52998224725"
    NOME_INTERMEDIARIO = "CORRETOR DE TREINO DA SILVA"
    CODIGO = "731904"

    def __init__(self, porta_portal: int = 0, porta_login: int = 0):
        self.documento, self.senha, self.codigo = self.DOCUMENTO, self.SENHA, self.CODIGO
        self.cpf_acesso = self.CPF_ACESSO
        self.sessoes: set[str] = set()
        self._pendentes: dict[str, dict] = {}     # sid do login (nidp) -> {"volta"}
        self._tickets: dict[str, str] = {}        # ticket de volta ao portal -> volta
        self.processos: dict[str, dict] = {}      # número do processo -> {"cnpj", "dados", "calculos": [...]}
        self.proximo_processo = 15977143
        self.tentativas_login = 0                 # envios da senha
        self.requisicoes = 0
        self.simulacoes = 0                       # "Calcular" do cotador novo (preços indicativos, nada oficial)
        self.finalizacoes = 0                     # "Finalizar Cálculo": o robô NUNCA pode clicar
        self.contratacoes = 0                     # qualquer coisa que inicie contratação: NUNCA
        self.saidas = 0                           # logouts
        self.senha_lembrada = False               # a etapa da senha passa sozinha (como no vídeo)
        self.exigir_codigo = False
        self.exigir_captcha = False
        self.exigir_troca_senha = False
        self.cair_depois_de_gerar = False         # cria o processo e derruba a sessão antes de mostrar (teste)
        self.cair_depois_de_alterar = False       # cria o cálculo do Alterar Cotação e derruba a sessão (teste)
        self.erro_imprimir = False                # o "Imprimir" não abre a janela (teste)
        self.calculo_em_branco = False            # a página do cálculo nunca carrega depois do Gerar processo (teste)
        self.calculo_demora_s = 0.0               # a página do cálculo só aparece depois de N s (portal lento, 10/11: >100 s)
        self._calculo_pedido_em: dict[str, float] = {}
        self.layout_com_dental_sempre = False     # mesmo com "Sem plano dental", o cálculo sai no layout do dental (teste)
        self.razao_atrasada_ms = 900              # no Alterar Cotação a razão social carrega depois (quadro 24)
        self.lock = threading.Lock()
        self._portal = ThreadingHTTPServer(("127.0.0.1", porta_portal), self._handler_portal())
        self._login = ThreadingHTTPServer(("127.0.0.1", porta_login), self._handler_login())
        self.url_portal = f"http://127.0.0.1:{self._portal.server_address[1]}"
        self.url_nidp = f"http://localhost:{self._login.server_address[1]}"   # outro "domínio", como o real

    # ------------------------------------------------------------------ uso nos testes
    @property
    def url_login(self) -> str:
        return self.url_portal + ROTA_LOGIN

    @property
    def url_cotador(self) -> str:
        return self.url_portal + ROTA_COTADOR

    @property
    def calculos(self) -> list[dict]:
        return [c for p in self.processos.values() for c in p["calculos"]]

    def iniciar(self) -> "Simulador":
        for srv in (self._portal, self._login):
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        return self

    def parar(self) -> None:
        for srv in (self._portal, self._login):
            srv.shutdown()
            srv.server_close()

    def expirar(self) -> None:
        with self.lock:
            self.sessoes.clear()

    # ------------------------------------------------------------------ regras do "portal"
    def _calcular(self, vidas: dict, codigo: str, copart: bool, dental: str) -> dict:
        v = valores(codigo, copart)
        premio = sum((v[k] * int(vidas.get(k, 0)) for k in CHAVES), Decimal(0))
        total_vidas = sum(int(vidas.get(k, 0)) for k in CHAVES)
        por_vida = Decimal(dict(DENTAIS).get(dental) or 0)
        dental_total = _d(por_vida * total_vidas)
        iof = _d(premio * IOF)
        return {"valores": v, "premio": _d(premio), "iof": iof, "total1": _d(premio + iof), "vidas": total_vidas,
                "dental_vida": por_vida, "dental": dental_total, "total_geral": _d(premio + dental_total),
                "total1_conj": _d(premio + dental_total + iof)}

    def _cards(self, vidas: dict, acomodacao: str, copart: bool) -> list[dict]:
        cards = []
        for codigo, nome, reemb, _antiga, grupo, _b, _f in PLANOS:
            if grupo != acomodacao:
                continue
            c = self._calcular(vidas, codigo, copart, "Sem plano dental")
            cards.append({"id": codigo, "nome": nome, "reembolso": reemb, "preco": reais(c["premio"]),
                          # como o portal real (07/11): FAIXA | Qtd | Tabela | Subtotal
                          "faixas": [[k, int(vidas.get(k, 0)), reais(c["valores"][k]),
                                      reais(c["valores"][k] * int(vidas.get(k, 0))) if int(vidas.get(k, 0)) else "-"]
                                     for k, _r, _ in FAIXAS]})
        cards.sort(key=lambda x: -Decimal(_so_digitos(x["preco"])))
        return cards

    def _novo_calculo(self, processo: str, dados: dict) -> dict:
        p = self.processos[processo]
        codigo = dados["plano"]
        copart = dados["copart"]
        c = self._calcular(p["vidas"], codigo, copart, dados["dental"])
        _, nome, reemb, antiga, _g, _b, _f = _plano(codigo)
        calc = {"processo": processo, "n": len(p["calculos"]) + 1, "plano": codigo, "nome": nome, "reembolso": reemb,
                "acomodacao_antiga": antiga, "copart": copart, "dental_nome": dados["dental"],
                "codigo": codigo + (" COPART" if copart else ""), **c}
        p["calculos"].append(calc)
        return calc

    # ------------------------------------------------------------------ páginas
    def _topo(self) -> str:
        return f"""
<header class="topo"><span class="logo">bradesco seguros</span>
 <nav class="menu" aria-label="Menu principal"><a href="{ROTA_HOME}">HOME</a><a href="#">AUTO</a><a href="#">RE</a>
  <a onclick="location.href='{ROTA_PAINEL}'">SAÚDE</a><a href="#">DENTAL</a><a href="#">VIDA</a><a href="#">PREVIDÊNCIA</a></nav>
 <bspn-user-menu class="usuario"><div class="bspn-user-menu" onclick="document.getElementById('menu-usuario').hidden=false">
   <div class="bspn-user-menu_initials">NC</div><div class="bspn-user-menu_title">NEWPORT CONSULTORIA E CORRETORA DE</div>
   <div class="bspn-user-menu_subtitle">Corretora: Newport Consultoria e Corretora De</div></div>
  <div id="menu-usuario" hidden><p>Extratos e relatórios</p><p>Remunerações</p>
   <p onclick="location.href='/pnegocios/sair'">Sair</p></div></bspn-user-menu>
</header>"""

    def _subtopo(self) -> str:
        return f"""
<nav class="subtopo" aria-label="Painel Saúde"><span>Painel Saúde</span><a href="#">MEUS LEADS</a><a href="#">APOIO À VENDA</a>
 <span class="submenu"><button type="button" onclick="this.nextElementSibling.hidden=!this.nextElementSibling.hidden">COTAÇÕES</button>
  <span class="lista" hidden><a href="{ROTA_COTADOR}">Cotação SPG</a><a href="#">Cotação Dental</a></span></span>
 <a href="#">APÓLICES</a><a href="#">MOVIMENTAÇÃO</a><a href="#">COMISSÕES</a><a href="#">SERVIÇOS</a></nav>"""

    def _pagina(self, titulo: str, corpo: str, extra_head: str = "") -> str:
        return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{titulo}</title>
<style>{(ESTATICO / "estilo.css").read_text(encoding="utf-8")}</style>{extra_head}</head><body>{corpo}
<button type="button" class="bia" aria-label="Fale com a BIA">Fale com a BIA</button>
<button type="button" class="cookies" aria-label="Preferências de cookies">🍪</button></body></html>"""

    def pagina_login(self, erro: str = "") -> str:
        return self._pagina("Portal de Negócios", f"""
<header class="topo"><span class="logo">bradesco seguros</span><nav><a href="#">LOGIN</a><a href="#">ATENDIMENTO</a></nav></header>
<main class="login-faixa"><h1>Portal de Negócios <small>para Corretores</small></h1>
 <div class="login-caixa"><p>Entre com seus dados para ter acesso às funcionalidades exclusivas do corretor.</p>
  <div class="rotulo">CPF/CNPJ</div>
  <input id="CpfCnpjTelaInicial" name="CpfCnpjTelaInicial" type="text" placeholder="Digite aqui seu CPF ou CNPJ" maxlength="18">
  <div class="erro" id="erro" role="alert">{html.escape(erro)}</div>
  <div class="form-box show-hide-pnegnovo" style="display: none;"><p>Senha</p>
   <input class="input" type="password" id="senha" maxlength="8"></div>
  <button type="submit" id="tag_Home_Login-Continuar">Continuar</button></div></main>
<section><h2>Seja um Corretor Bradesco Seguros</h2></section>
<!-- como o portal real (07/11): reCAPTCHA invisível (só o selo) e o banner de cookies por cima da tela -->
<iframe title="reCAPTCHA" class="grecaptcha-badge" src="/recaptcha/api2/anchor?size=invisible" width="256" height="60"></iframe>
<iframe title="desafio reCAPTCHA" src="/recaptcha/api2/bframe" style="visibility:hidden"></iframe>
<div id="banner-cookies" class="fundo"><div class="modal"><p>Usamos cookies para melhorar a sua experiência.</p>
 <button type="submit" id="adopt-preferences-button">Configurar cookies</button>
 <button type="submit" id="adopt-reject-all-button" onclick="document.getElementById('banner-cookies').remove()">Rejeitar cookies não necessários</button>
 <button type="submit" id="adopt-accept-all-button" onclick="document.getElementById('banner-cookies').remove()">Aceitar cookies</button></div></div>
<script>
document.getElementById('tag_Home_Login-Continuar').onclick = async () => {{
  const r = await fetch('/pnegocios2/api/documento', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{documento: document.getElementById('CpfCnpjTelaInicial').value,
                           volta: new URLSearchParams(location.search).get('volta') || ''}})}});
  const j = await r.json();
  if (j.erro) {{ document.getElementById('erro').textContent = j.erro; return; }}
  location.href = j.destino;
}};
</script>""")

    def pagina_home(self) -> str:
        return self._pagina("Área logada", self._topo() + """
<main class="conteudo"><h1>Olá, corretor</h1><p>Bem-vindo ao Portal de Negócios.</p></main>""")

    def pagina_painel(self) -> str:
        return self._pagina("Painel Saúde", self._topo() + self._subtopo() + f"""
<main class="conteudo"><h1>Painel Saúde</h1>
 <section class="acesso"><h2>Acesso rápido</h2>
  <app-menu-item><div class="menu-item"><p>Cartões de novos segurados</p><a href="#">Conferir</a></div></app-menu-item>
  <app-menu-item><div class="menu-item"><p>Cotação SPG</p><a href="{ROTA_COTADOR}">Conferir</a></div></app-menu-item>
 </section></main>
<div class="modal fade pn-modal" role="dialog" style="display:none"></div>
<div class="modal fade pn-modal" role="dialog" style="display:none"></div>
<div class="modal fade pn-modal modal-aviso in fundo" role="dialog" id="aviso-campanha">
 <div class="modal"><button type="button" class="close" aria-label="Close"
   onclick="document.getElementById('aviso-campanha').remove()">×</button>
 <p>Seguros Friday: campanha da semana.</p><p>Não quero mais visualizar esta mensagem.</p></div></div>""")

    def pagina_cotador(self) -> str:
        """Portal real 07/11: a página da Cotação SPG mostra a área de trabalho antiga (EEEM) num iframe."""
        return self._pagina("Cotação SPG", self._topo() + self._subtopo() + """
<nav class="migalhas">Painel Saúde &gt; Cotações &gt; <b>Cotação SPG</b></nav>
<iframe id="eeem" src="/EEEM-EmissaoExpressa/init.do?NroControle=1&Site=Corretor" style="width:100%;height:1400px;border:0"></iframe>""")

    def _menu_eeem(self) -> str:
        return """<ul class="menu-eeem"><li><a href="/EEEM-EmissaoExpressa/areaTrabalho/show.do">Processos</a></li>
 <li class="menu-acoes"><a href="#">Ações</a><ul class="sub" style="display:none">
  <li><a href="/EEEM-EmissaoExpressa/novaCotacao/iniciarNovaCotacao.do">Iniciar Nova Cotação SPG</a></li>
  <li><a href="#">Regerar Boleto</a></li><li><a href="#">Histórico de Processos</a></li></ul></li>
 <li><a href="#">Relatórios</a></li></ul>
<script>document.querySelector('.menu-acoes').onmouseenter = (e) => { e.currentTarget.querySelector('.sub').style.display = 'block'; };
document.querySelector('.menu-acoes').onmouseleave = (e) => { e.currentTarget.querySelector('.sub').style.display = 'none'; };</script>"""

    def pagina_area_trabalho(self) -> str:
        linhas = "".join(f"<tr><td>{n}</td><td>{_fmt_cnpj(p['cnpj'])}</td></tr>" for n, p in self.processos.items())
        return self._antiga("Acompanhamento de Processos", self._menu_eeem() + f"""
<h2>Acompanhamento de Processos</h2><table class="processos"><tr><th>Processo</th><th>Estipulante</th></tr>{linhas}</table>""")

    def pagina_nova_cotacao(self) -> str:
        return self._antiga("Nova Cotação", self._menu_eeem() + """
<iframe id="cotador" src="/eeem-fed-simulacao-cotacao/" style="width:100%;height:1300px;border:0"></iframe>""")

    def pagina_spa(self) -> str:
        """O cotador novo ("Cotador de planos SPG"), dentro do iframe da Nova Cotação (saudeexterno no real)."""
        app = (ESTATICO / "cotador.html").read_text(encoding="utf-8")
        dados = {"empresas_api": "/api/spg", "faixas": FAIXAS, "dentais": [d for d, _ in DENTAIS],
                 "sucursais": SUCURSAIS, "corretor": CORRETOR, "angariacoes": ANGARIACOES,
                 "corretagens": CORRETAGENS, "ramos": RAMOS}
        app = app.replace("/*DADOS*/", "window.SIM = " + json.dumps(dados, ensure_ascii=False) + ";")
        return self._pagina("Cotação", app)

    # ---- páginas antigas (EEEM-EmissaoExpressa), dentro do iframe do cotador
    def _antiga(self, titulo: str, corpo: str) -> str:
        return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{titulo}</title>
<style>{(ESTATICO / "antigo.css").read_text(encoding="utf-8")}</style></head><body>
<nav class="menu-antigo"><a href="#">Processos</a><a href="#">Ações</a><a href="#">Relatórios</a></nav>{corpo}</body></html>"""

    def _tabela_calculo(self, calc: dict, vidas: dict) -> str:
        if calc["dental_nome"] == "Sem plano dental" and not self.layout_com_dental_sempre:
            return self._tabela_conjugado(calc, vidas)
        linhas = []
        for k, _r, antigo in FAIXAS:
            q = int(vidas.get(k, 0))
            v = calc["valores"][k]
            dv = calc["dental_vida"]
            # como o portal real (07/11): Saúde, Dental, Qtd, Saúde, Dental, Saúde + Dental
            linhas.append(f"<tr><td>{antigo}</td><td>{reais(v)}</td><td>{reais(dv)}</td><td>{q}</td>"
                          f"<td>{reais(v * q)}</td><td>{reais(dv * q)}</td><td>{reais(v * q + dv * q)}</td></tr>")
        copart = "30%" if calc["copart"] else "Sem coparticipação"
        return f"""
<table class="perfil" aria-label="Perfil 1"><caption>Perfil 1: Sócios</caption>
 <tr><th>Plano Saúde</th><td class="nome-plano">{calc['nome']}</td><td>Código do Plano: {calc['codigo']}</td>
  <td>Região: São Paulo Capital</td><td>Coparticipação: {copart}</td><td>Reembolso Completo</td></tr>
 <tr><th>Plano Dental</th><td>{calc['dental_nome']}</td></tr></table>
<table class="valores" aria-label="Valores por faixa etária">
 <tr><th>Faixa Etária</th><th>Saúde(R$)</th><th>Dental(R$)</th><th>Qtd</th><th>Saúde</th><th>Dental</th><th>Saúde + Dental</th></tr>
 {''.join(linhas)}
 <tr><td>Total</td><td></td><td></td><td>{calc['vidas']}</td><td>{reais(calc['premio'])}</td>
  <td>{reais(calc['dental'])}</td><td>{reais(calc['total_geral'])}</td></tr></table>
<table class="totais" aria-label="Totais"><caption>Totais</caption>
 <tr><td>Total de Vidas</td><td>{calc['vidas']}</td></tr><tr><td>Prêmio Saúde</td><td>{reais(calc['premio'])}</td></tr>
 <tr><td>Prêmio Dental</td><td>{reais(calc['dental'])}</td></tr><tr><td>Total Geral</td><td>{reais(calc['total_geral'])}</td></tr>
 <tr><td>Taxa Kit Digital</td><td>R$ 0,00</td></tr><tr><td>I.O.F. Saúde</td><td>{reais(calc['iof'])}</td></tr>
 <tr><td>Total 1ª Parcela</td><td>{reais(calc['total1_conj'])}</td></tr><tr><td>Demais Parcelas</td><td>{reais(calc['total1_conj'])}</td></tr></table>
<p class="aviso">Os valores informados nesta cotação são meramente indicativos e poderão ser revistos, sendo reduzidos ou
 agravados, após a análise da Seguradora. Este estudo é valido por 40 dias a partir da cotação deste processo.</p>"""

    def _tabela_conjugado(self, calc: dict, vidas: dict) -> str:
        """O cálculo com "Sem plano dental" (vídeo): Saúde, Saúde Conjugado e Dental Conjugado (o dental só como
        comparação, no valor do Padrão Doc 1), "Totais Saúde" e "Totais Conjugado" (o conjugado não é contratado)."""
        comparacao = Decimal(dict(DENTAIS)["Padrão Doc 1"])
        linhas = []
        for k, _r, antigo in FAIXAS:
            q = int(vidas.get(k, 0))
            v = calc["valores"][k]
            linhas.append(f"<tr><td>{antigo}</td><td>{reais(v)}</td><td>{reais(v)}</td><td>{reais(comparacao)}</td><td>{q}</td>"
                          f"<td>{reais(v * q)}</td><td>{reais(v * q)}</td><td>{reais(comparacao * q)}</td>"
                          f"<td>{reais(v * q + comparacao * q)}</td></tr>")
        dental = _d(comparacao * calc["vidas"])
        total_geral = _d(calc["premio"] + dental)
        total1_conj = _d(total_geral + calc["iof"])
        copart = "30%" if calc["copart"] else "Sem coparticipação"
        return f"""
<table class="perfil" aria-label="Perfil 1"><caption>Perfil 1: Sócios</caption>
 <tr><th>Plano Saúde</th><td class="nome-plano">{calc['nome']}</td><td>Código do Plano: {calc['codigo']}</td>
  <td>Região: São Paulo Capital</td><td>Coparticipação: {copart}</td><td>Reembolso Completo</td></tr></table>
<table class="valores" aria-label="Valores por faixa etária">
 <tr><th>Faixa Etária</th><th>Saúde(R$)</th><th>Saúde Conjugado(R$)</th><th>Dental Conjugado(R$)</th><th>Qtd</th><th>Saúde</th>
  <th>Saúde Conjugado</th><th>Dental Conjugado</th><th>Saúde + Dental</th></tr>
 {''.join(linhas)}</table>
<table class="totais" aria-label="Totais Saúde"><caption>Totais Saúde</caption>
 <tr><td>Total de Vidas</td><td>{calc['vidas']}</td></tr><tr><td>Prêmio Saúde</td><td>{reais(calc['premio'])}</td></tr>
 <tr><td>Taxa Kit Digital</td><td>R$ 0,00</td></tr><tr><td>I.O.F. Saúde</td><td>{reais(calc['iof'])}</td></tr>
 <tr><td>Total 1ª Parcela</td><td>{reais(calc['total1'])}</td></tr><tr><td>Demais Parcelas</td><td>{reais(calc['total1'])}</td></tr></table>
<table class="totais" aria-label="Totais Conjugado"><caption>Totais Conjugado</caption>
 <tr><td>Prêmio Dental</td><td>{reais(dental)}</td></tr><tr><td>Total Geral</td><td>{reais(total_geral)}</td></tr>
 <tr><td>Total 1ª Parcela</td><td>{reais(total1_conj)}</td></tr><tr><td>Demais Parcelas</td><td>{reais(total1_conj)}</td></tr></table>
<p class="aviso">Os valores informados nesta cotação são meramente indicativos e poderão ser revistos, sendo reduzidos ou
 agravados, após a análise da Seguradora. Este estudo é valido por 40 dias a partir da cotação deste processo.</p>"""

    def pagina_calculo(self, processo: str, n: int, novo: str) -> str:
        p = self.processos[processo]
        calc = p["calculos"][n - 1]
        tabela = self._tabela_calculo(calc, p["vidas"])
        modais = []
        if novo == "alterar":
            modais.append(f"<b>Processo #{processo}</b><p>Cotação com Reembolso Específico.</p>")
        if novo:
            modais.append("<p>Os valores desta simulação são meramente indicativos. Este processo é válido por 40 dias.</p>")
        impressao = json.dumps(f"""<html><head><title>Impressão</title></head><body><div class="logo">bradesco saúde</div>
<div>@@IDENTIFICADOR@@ 16/10/2026</div><div>Processo {processo}</div>{tabela}</body></html>""", ensure_ascii=False)
        return self._antiga("Cálculo de Seguro SPG", f"""
<h2>Cálculo de Seguro SPG</h2>
<table class="processo"><tr><th>Número do Processo</th><td id="numero-processo">{processo}</td>
 <td>Reembolso Específico (exceto Nacional Plus e Premium)</td></tr></table>
<table class="identificar"><tr><th>Identifique o cálculo a ser armazenado *</th></tr>
 <tr><td><input type="text" name="cotacao.calculo.identificador" maxlength="60" id="form_calculo_cotacao_calculo_identificador"></td></tr></table>
{tabela}
<div class="botoes"><button type="button" id="alterar" onclick="location.href='/EEEM-EmissaoExpressa/CotacaoSPG.aspx?processo={processo}&calculo={n}'">Alterar Cotação</button>
<button type="button" id="imprimir">Imprimir</button>
<button type="button" id="finalizar" onclick="fetch('/EEEM-EmissaoExpressa/Finalizar.aspx',{{method:'POST'}})">Finalizar Cálculo</button></div>
<script>
const fila = {json.dumps(modais, ensure_ascii=False)};
function proximoModal() {{
  const m = fila.shift(); if (!m) return;
  // como o portal real (07/11): fundo #box-overlayer + caixa #box-alertbox com button#box-button-ok
  const d = document.createElement('div');
  d.innerHTML = '<div id="box-overlayer" class="fundo"></div><div id="box-alertbox" class="fundo"><div class="modal">' + m
    + '<div id="box-button"><button type="button" id="box-button-ok">OK</button></div></div></div>';
  d.querySelector('#box-button-ok').onclick = () => {{ d.remove(); setTimeout(proximoModal, 150); }};
  document.body.appendChild(d);
}}
setTimeout(proximoModal, 200);
document.getElementById('imprimir').onclick = () => {{
  if ({'true' if self.erro_imprimir else 'false'}) return;
  if (!document.getElementById('form_calculo_cotacao_calculo_identificador').value.trim()) {{
    fila.push('<p>O identificador do cálculo deve ser preenchido.</p>'); proximoModal(); return;
  }}
  const w = window.open('about:blank');
  const nome = document.getElementById('form_calculo_cotacao_calculo_identificador').value.replace(/[<>&]/g, '');
  w.document.write({impressao}.replace('@@IDENTIFICADOR@@', nome)); w.document.close(); w.print();
}};
</script>""")

    def pagina_alterar(self, processo: str, n: int) -> str:
        p = self.processos[processo]
        calc = p["calculos"][n - 1]
        emp = EMPRESAS.get(p["cnpj"], {})
        nomes = []
        for _c, nome, *_ in PLANOS:
            if nome not in nomes:
                nomes.append(nome)
        acomod = {nome: sorted([x[3] for x in PLANOS if x[1] == nome],
                               key=lambda a: (not a.startswith("Quarto"), a)) for nome in nomes}
        opcoes_plano = "".join(f"<option{' selected' if nome == calc['nome'] else ''}>{nome}</option>" for nome in nomes)
        vidas = "".join(
            f'<td><label for="v{i}">{antigo}</label><input id="v{i}" name="v_{k}" value="{p["vidas"].get(k) or ""}"></td>'
            for i, (k, _r, antigo) in enumerate(FAIXAS))
        d = p["dados"]
        return self._antiga("Cotação SPG", f"""
<h2>Cotação SPG</h2>
<div class="banner"><b>Nova modalidade de reembolso disponível</b><p>O modelo de reembolso da sua cotação agora pode ser
 completo ou específico. IMPORTANTE: os planos Nacional Plus e Premium só contam com reembolso completo.</p></div>
<form method="post" action="/EEEM-EmissaoExpressa/CotacaoSPG.aspx?processo={processo}">
<table class="dados"><caption>Dados da Cotação</caption>
 <tr><th>Tipo de Cotação*</th><td><select name="tipo"><option>Saúde</option></select></td>
  <th>Código Sucursal*</th><td><input name="sucursal" value="{d.get('sucursal', '')}"></td>
  <th>CPD Corretor *</th><td><input name="cpd" value="{d.get('corretor', '')}"></td></tr>
 <tr><th>Angariação*</th><td><select name="angariacao"><option>{html.escape(d.get('angariacao', ''))}</option></select></td>
  <th>Corretagem*</th><td><select name="corretagem"><option>{html.escape(d.get('corretagem', ''))}</option></select></td></tr>
 <tr><th>Produto*</th><td><select name="produto"><option>{d.get('cobertura', 'Top')}</option></select></td></tr>
 <tr><th>CNPJ ou CAEPF*</th><td><select><option>CNPJ</option></select><span id="cnpj">{_fmt_cnpj(p['cnpj'])}</span></td>
  <th>Razão Social*</th><td><input id="razao" name="razao" value=""></td><th>UF*</th><td><input id="uf" value=""></td></tr>
 <tr><th>Ramo de Atividade*</th><td><select name="ramo"><option>{d.get('ramo', '')}</option></select></td></tr>
 <tr><th>Natureza Jurídica*</th><td><select name="natureza"><option>Selecione...</option></select></td></tr>
 <tr><th>Tipo de SPG*</th><td><label><input type="radio" name="spg" checked>3 a 29</label>
  <label><input type="radio" name="spg">30 a 99</label><label><input type="radio" name="spg">100 a 199</label></td></tr>
</table>
<table class="perfil"><caption>Perfil 1</caption>
 <tr><th><label for="categoria">Categoria Funcional*</label></th><td><select id="categoria" name="categoria"><option>Sócios</option><option>Funcionários</option></select></td>
  <th><label for="acomodacao">Acomodação*</label></th><td rowspan="2"><select id="acomodacao" name="acomodacao" size="3"></select></td>
  <th><label for="copart">Coparticipação</label></th><td><select id="copart" name="copart"><option>30%</option><option>Sem coparticipação</option></select></td></tr>
 <tr><th><label for="plano">Plano Saúde*</label></th><td><select id="plano" name="plano">{opcoes_plano}</select></td>
  <th>Região*</th><td><select disabled><option>São Paulo Capital</option></select></td></tr>
 <tr><th>Vidas*</th>{vidas}</tr>
</table>
<div class="botoes"><button type="submit" id="calcular">Calcular</button></div>
</form>
<script>
const ACOMOD = {json.dumps(acomod, ensure_ascii=False)};
const atual = {json.dumps(calc['acomodacao_antiga'], ensure_ascii=False)};
function opcoes() {{
  const s = document.getElementById('acomodacao'); s.innerHTML = '';
  for (const a of ACOMOD[document.getElementById('plano').value]) {{
    const o = document.createElement('option'); o.textContent = a; o.selected = a === atual; s.appendChild(o);
  }}
}}
document.getElementById('plano').onchange = () => opcoes();
opcoes();
document.getElementById('copart').value = {json.dumps("30%" if calc['copart'] else "Sem coparticipação")};
setTimeout(() => {{ document.getElementById('razao').value = {json.dumps(emp.get('razao', ''))};
                    document.getElementById('uf').value = {json.dumps(emp.get('uf', ''))}; }}, {self.razao_atrasada_ms});
</script>""")

    # ------------------------------------------------------------------ portal (HTTP)
    def _handler_portal(self):
        sim = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _sessao(self) -> bool:
                c = SimpleCookie(self.headers.get("Cookie", ""))
                return "PNSESS" in c and c["PNSESS"].value in sim.sessoes

            def _enviar(self, corpo: bytes, tipo: str, status: int = 200, cookie: str | None = None):
                self.send_response(status)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(corpo)))
                self.send_header("Cache-Control", "no-store")
                if cookie:
                    self.send_header("Set-Cookie", cookie)
                self.end_headers()
                self.wfile.write(corpo)

            def _html(self, corpo: str, cookie: str | None = None):
                self._enviar(corpo.encode("utf-8"), "text/html; charset=utf-8", cookie=cookie)

            def _json(self, obj, status: int = 200):
                self._enviar(json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8",
                             status)

            def _ir(self, destino: str, cookie: str | None = None):
                self.send_response(303)
                self.send_header("Location", destino)
                self.send_header("Content-Length", "0")
                if cookie:
                    self.send_header("Set-Cookie", cookie)
                self.end_headers()

            def _corpo(self) -> bytes:
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def do_GET(self):
                sim.requisicoes += 1
                u = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                rota = u.path
                if rota.startswith("/recaptcha/"):          # o selo do reCAPTCHA invisível (sem desafio)
                    return self._html("<html><body><small>protegido por reCAPTCHA</small></body></html>")
                if rota == ROTA_LOGIN:
                    if self._sessao():
                        return self._ir(ROTA_HOME)
                    return self._html(sim.pagina_login())
                if rota == "/pnegocios/login/retorno":
                    volta = sim._tickets.pop(q.get("ticket", ""), None)
                    if volta is None:
                        return self._ir(ROTA_LOGIN)
                    token = secrets.token_hex(8)
                    with sim.lock:
                        sim.sessoes.add(token)
                    return self._ir(volta or ROTA_HOME, cookie=f"PNSESS={token}; Path=/")
                if rota == "/pnegocios/sair":
                    c = SimpleCookie(self.headers.get("Cookie", ""))
                    with sim.lock:
                        if "PNSESS" in c:
                            sim.sessoes.discard(c["PNSESS"].value)
                        sim.saidas += 1
                    return self._ir(ROTA_LOGIN, cookie="PNSESS=; Path=/; Max-Age=0")
                if rota.startswith("/pnegocios/wps/") or rota.startswith("/EEEM-") or rota.startswith("/eeem-fed-"):
                    if not self._sessao():
                        if not rota.startswith("/pnegocios/"):
                            return self._html("<html><body><script>top.location.href='" + ROTA_LOGIN
                                              + "?volta=" + quote(ROTA_HOME) + "'</script></body></html>")
                        return self._ir(ROTA_LOGIN + "?volta=" + quote(rota))
                if rota == ROTA_HOME:
                    return self._html(sim.pagina_home())
                if rota == ROTA_PAINEL:
                    return self._html(sim.pagina_painel())
                if rota == ROTA_COTADOR:
                    return self._html(sim.pagina_cotador())
                if rota in ("/EEEM-EmissaoExpressa/init.do", "/EEEM-EmissaoExpressa/areaTrabalho/show.do"):
                    return self._html(sim.pagina_area_trabalho())
                if rota == "/EEEM-EmissaoExpressa/novaCotacao/iniciarNovaCotacao.do":
                    return self._html(sim.pagina_nova_cotacao())
                if rota.startswith("/eeem-fed-simulacao-cotacao"):
                    return self._html(sim.pagina_spa())
                if rota == "/EEEM-EmissaoExpressa/CalculoSPG.aspx" and sim.calculo_em_branco:
                    return self._html("<html><body><p>Carregando...</p></body></html>")
                if rota == "/EEEM-EmissaoExpressa/CalculoSPG.aspx" and sim.calculo_demora_s:
                    desde = sim._calculo_pedido_em.setdefault(q.get("processo", ""), time.monotonic())
                    if time.monotonic() - desde < sim.calculo_demora_s:
                        # enquanto carrega: o portal já fala em "Número do Processo", mas sem o título da página
                        return self._html(f"<html><body><p>Carregando... Número do Processo {q.get('processo', '')}</p>"
                                          "<script>setTimeout(() => location.reload(), 1000)</script></body></html>")
                if rota == "/EEEM-EmissaoExpressa/CalculoSPG.aspx":
                    return self._html(sim.pagina_calculo(q.get("processo", ""), int(q.get("calculo", 1)),
                                                         q.get("novo", "")))
                if rota == "/EEEM-EmissaoExpressa/CotacaoSPG.aspx":
                    return self._html(sim.pagina_alterar(q.get("processo", ""), int(q.get("calculo", 1))))
                if rota.startswith("/api/spg/intermediario"):
                    if not self._sessao():
                        return self._json({"sessao": False}, 401)
                    cpf = _so_digitos(q.get("cpf"))
                    return self._json({"nome": sim.NOME_INTERMEDIARIO if cpf == sim.CPF_INTERMEDIARIO else ""})
                if rota.startswith("/api/spg/empresa"):
                    if not self._sessao():
                        return self._json({"sessao": False}, 401)
                    cnpj = _so_digitos(q.get("cnpj"))
                    if not _cnpj_valido(cnpj):
                        return self._json({"erro": "CNPJ inválido."})
                    emp = EMPRESAS.get(cnpj) or {"razao": "EMPRESA DE TREINO " + cnpj[:4] + " LTDA", "uf": "SP",
                                                 "cidade": "SAO PAULO", "natureza": "Sociedade Empresarial Limitada"}
                    return self._json(emp)
                self._enviar(b"nao encontrado", "text/plain", 404)

            def do_POST(self):
                sim.requisicoes += 1
                u = urlparse(self.path)
                rota = u.path
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                if rota == "/pnegocios2/api/documento":
                    dados = json.loads(self._corpo() or b"{}")
                    doc = _so_digitos(dados.get("documento"))
                    if len(doc) not in (11, 14):
                        return self._json({"erro": "Informe um CPF ou CNPJ válido."})
                    if doc != sim.documento:
                        sim.tentativas_login += 1
                        return self._json({"erro": "CPF/CNPJ não cadastrado no Portal de Negócios."})
                    volta = dados.get("volta") or ""
                    if sim.senha_lembrada:
                        ticket = secrets.token_hex(8)
                        sim._tickets[ticket] = volta
                        return self._json({"destino": f"/pnegocios/login/retorno?ticket={ticket}"})
                    sid = secrets.token_hex(8)
                    sim._pendentes[sid] = {"volta": volta}
                    return self._json({"destino": f"{sim.url_nidp}/nidp/app/login?id=secure_name_pasword_form_pneg&sid={sid}"})
                if rota == "/EEEM-EmissaoExpressa/Finalizar.aspx":
                    sim.finalizacoes += 1
                    return self._json({"ok": True})
                if not self._sessao():
                    if rota.startswith("/EEEM-"):
                        return self._html("<html><body><script>top.location.href='" + ROTA_LOGIN + "'</script></body></html>")
                    return self._json({"sessao": False}, 401)
                if rota == "/api/spg/calcular":
                    dados = json.loads(self._corpo() or b"{}")
                    sim.simulacoes += 1
                    cards = sim._cards(dados["vidas"], dados["acomodacao"], dados["copart"])
                    total = sum(int(dados["vidas"].get(k, 0)) for k in CHAVES)
                    dentais = [{"nome": n, "preco": reais(Decimal(v) * total) if v else ""} for n, v in DENTAIS]
                    return self._json({"cards": cards, "dentais": dentais})
                if rota == "/api/spg/processo":
                    dados = json.loads(self._corpo() or b"{}")
                    with sim.lock:
                        numero = str(sim.proximo_processo)
                        sim.proximo_processo += 1
                        sim.processos[numero] = {"cnpj": _so_digitos(dados["cnpj"]), "vidas": dados["vidas"],
                                                 "idades": dados.get("idades", {}), "dados": dados, "calculos": []}
                        sim._novo_calculo(numero, {"plano": dados["plano"], "copart": dados["copart"],
                                                   "dental": dados["dental"]})
                        if sim.cair_depois_de_gerar:
                            sim.sessoes.clear()
                            return self._json({"sessao": False}, 401)
                    return self._json({"processo": numero, "calculo": 1})
                if rota == "/EEEM-EmissaoExpressa/CotacaoSPG.aspx":
                    form = {k: v[0] for k, v in parse_qs(self._corpo().decode("utf-8")).items()}
                    numero = q.get("processo", "")
                    p = sim.processos[numero]
                    plano = next((x[0] for x in PLANOS if x[1] == form.get("plano") and x[3] == form.get("acomodacao")), None)
                    if plano is None:
                        return self._html(sim._antiga("Cotação SPG", "<p class='erro'>Selecione a acomodação.</p>"))
                    vidas = {k: int(form.get(f"v_{k}") or 0) for k in CHAVES}
                    if vidas != {k: int(p["vidas"].get(k, 0)) for k in CHAVES}:
                        p["vidas"] = vidas
                    calc = sim._novo_calculo(numero, {"plano": plano, "copart": form.get("copart") == "30%",
                                                      "dental": p["calculos"][0]["dental_nome"]})
                    if sim.cair_depois_de_alterar:
                        sim.sessoes.clear()
                        return self._html("<html><body><script>top.location.href='" + ROTA_LOGIN + "'</script></body></html>")
                    return self._ir(f"/EEEM-EmissaoExpressa/CalculoSPG.aspx?processo={numero}&calculo={calc['n']}&novo=alterar")
                self._enviar(b"nao encontrado", "text/plain", 404)

        return H

    # ------------------------------------------------------------------ login (nidp)
    def pagina_senha(self, sid: str, erro: str = "") -> str:
        captcha = '<div class="g-recaptcha" title="reCAPTCHA">Não sou um robô</div>' if self.exigir_captcha else ""
        return self._pagina("Login", f"""
<main class="login-faixa"><div class="login-caixa"><h1>Digite sua senha</h1>
<form method="post" action="/nidp/app/login?sid={sid}" id="form-senha">
 <label for="input_cpf_cnpj">CPF</label><input id="input_cpf_cnpj" name="Ecom_User_ID" type="text">
 <label for="input_senha">Senha</label><input id="input_senha" name="Ecom_Password" type="password">
 {captcha}<div class="erro" role="alert" id="erro-senha">{html.escape(erro)}</div>
 <button type="submit">Entrar</button></form></div></main>
<script>
document.getElementById('form-senha').onsubmit = (e) => {{
  const cpf = document.getElementById('input_cpf_cnpj').value.replace(/[^0-9]/g, '');
  if (cpf.length !== 11) {{
    e.preventDefault();
    document.getElementById('erro-senha').textContent = 'Por favor digite um CPF válido para prosseguir.';
  }}
}};
</script>""")

    def pagina_codigo(self, sid: str, erro: str = "") -> str:
        return self._pagina("Verificação", f"""
<main class="login-faixa"><div class="login-caixa"><h1>Código de verificação</h1>
<p>Enviamos um código para o seu celular.</p>
<form method="post" action="/nidp/app/codigo?sid={sid}">
 <label for="codigo">Código de verificação</label><input id="codigo" name="codigo" autocomplete="one-time-code">
 <div class="erro" role="alert">{html.escape(erro)}</div><button type="submit">Confirmar</button></form></div></main>""")

    def _handler_login(self):
        sim = self

        class L(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _html(self, corpo: str):
                dados = corpo.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

            def _ir(self, destino: str):
                self.send_response(303)
                self.send_header("Location", destino)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def _voltar_ao_portal(self, sid: str):
                pend = sim._pendentes.pop(sid, {})
                ticket = secrets.token_hex(8)
                sim._tickets[ticket] = pend.get("volta", "")
                return self._ir(f"{sim.url_portal}/pnegocios/login/retorno?ticket={ticket}")

            def do_GET(self):
                u = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                if u.path == "/nidp/app/login" and q.get("sid") in sim._pendentes:
                    return self._html(sim.pagina_senha(q["sid"]))
                self._ir(sim.url_login)

            def do_POST(self):
                u = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                sid = q.get("sid", "")
                form = {k: v[0] for k, v in parse_qs(self.rfile.read(int(self.headers.get("Content-Length") or 0))
                                                     .decode("utf-8")).items()}
                if sid not in sim._pendentes:
                    return self._ir(sim.url_login)
                if u.path == "/nidp/app/login":
                    sim.tentativas_login += 1
                    if _so_digitos(form.get("Ecom_User_ID")) != sim.cpf_acesso or form.get("Ecom_Password") != sim.senha:
                        return self._html(sim.pagina_senha(sid, "Usuário ou senha inválidos."))
                    if sim.exigir_troca_senha:
                        return self._html(sim._pagina("Senha", """<main><h1>Sua senha expirou</h1>
<p>Cadastre uma nova senha.</p><input type="password" aria-label="Nova senha"><input type="password" aria-label="Confirme a nova senha"></main>"""))
                    if sim.exigir_codigo:
                        return self._html(sim.pagina_codigo(sid))
                    return self._voltar_ao_portal(sid)
                if u.path == "/nidp/app/codigo":
                    if form.get("codigo") != sim.codigo:
                        return self._html(sim.pagina_codigo(sid, "Código inválido."))
                    return self._voltar_ao_portal(sid)
                self._ir(sim.url_login)

        return L
