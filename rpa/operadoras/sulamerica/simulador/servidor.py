"""Servidor do simulador: portal antigo (os11) e cotador novo (SPA) em portas diferentes."""
from __future__ import annotations

import json
import secrets
import threading
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from .pdf import pdf_simples

ESTATICO = Path(__file__).parent / "estatico"


def _cnpj_valido(d: str) -> bool:
    if len(d) != 14 or len(set(d)) == 1:
        return False

    def dig(base, pesos):
        r = sum(int(n) * p for n, p in zip(base, pesos)) % 11
        return "0" if r < 2 else str(11 - r)
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    return d[12:] == dig(d[:12], p1) + dig(d[:12] + dig(d[:12], p1), [6] + p1)


class Simulador:
    # Login FALSO do simulador: o portal de treino só aceita estes valores (nunca um login de verdade).
    CPF = "52998224725"
    EMAIL = "corretor.treino@simulador.local"
    SENHA = "Treino#Falsa-26"   # o campo do portal aceita até 16 caracteres
    CODIGO = "482913"

    def __init__(self, porta_portal: int = 0, porta_spa: int = 0):
        self.cotacoes: dict[str, dict] = {}
        self.proximo = 8601800
        self.sessoes: set[str] = set()
        self.cpf, self.email, self.senha, self.codigo = self.CPF, self.EMAIL, self.SENHA, self.CODIGO
        self.tentativas_login = 0                # envios do formulário de login (CPF, e-mail e senha)
        self.requisicoes = 0                     # qualquer pedido ao portal antigo
        self.exigir_codigo = False               # depois da senha, pede o código de verificação
        self.exigir_captcha = False              # tela de login com captcha
        self.exigir_troca_senha = False          # depois da senha, pede para trocar a senha
        self.exigir_selecao_corretora = False    # depois da senha, pede para escolher a corretora (EV/EA/AA)
        self.acesso_ativo = False                # o CPF já está logado em outro lugar (mensagem do portal real)
        self.acesso_ativo_por = 0                # as próximas N entradas recebem "acesso ativo"; depois libera
        # Como o portal real (05/11): com a sessão viva, abrir a LoginGeral.aspx direto (sem vir de um link do
        # portal) mostra o formulário de novo, e entrar de novo é recusado com "acesso ativo".
        self.um_acesso_por_cpf = False
        self.validacao_forcada = ""              # o formulário recusa o preenchimento com esta mensagem
        self._formularios: dict[str, dict] = {}  # estado de cada tela de login (como o __OSVSTATE do portal)
        self.expirar_apos_download = False       # derruba a sessão logo depois do próximo PDF (teste)
        self.cotador_em_aba_nova = False         # o card "Cotação PME" abre o cotador em outra aba
        self.cotador_lento_ms = 0                # passa por uma página intermediária antes do cotador
        self.modal_sair_sem_confirmar = False    # o modal "Deseja realmente sair?" só tem Cancelar (teste)
        self.pdf_abre_aba = False                # BAIXAR também abre o visualizador do PDF em outra aba (teste)
        self.sem_voltar_home = False             # a tela da emissão não tem "Voltar para a home" (teste)
        self.copia_trava_copart = False          # na cotação copiada, o filtro de coparticipação fica travado (teste)
        self.travar_troca_cuidado = False        # a 1ª troca para o Cuidado 360° trava (URL nova, corpo velho; F5 volta ao começo)
        self.sair_da_cotacao_vai_ao_painel = False   # "Sair da cotação" leva ao painel "Estou em cotações" (teste)
        self.saidas = 0                          # cliques em "Sair do Cotador" (logout)
        self.senha_maxlength = 16                # maxlength do campo de senha (portal real em 03/11: 16)
        self.acesso_ativo_depois_de_expirar = False   # quando a sessão cai, outro lugar entra com o CPF (teste)
        self.sessao_expirada = False
        self._codigos_pendentes: dict[str, str] = {}   # token da tela do código -> para onde voltar
        self.falhar_download: set[str] = set()   # protocolos cujo 1º download falha (teste)
        self.falhar_proximo_download = False
        self.visitas_contratacao = 0
        self.lock = threading.Lock()
        self._portal = ThreadingHTTPServer(("127.0.0.1", porta_portal), self._handler_portal())
        self._spa = ThreadingHTTPServer(("127.0.0.1", porta_spa), self._handler_spa())
        self.url_portal = f"http://127.0.0.1:{self._portal.server_address[1]}"
        # host diferente para simular o outro domínio do cotador novo
        self.url_spa = f"http://localhost:{self._spa.server_address[1]}"

    @property
    def url_login(self) -> str:
        return f"{self.url_portal}/SaudeCotador/LoginGeral.aspx"

    @property
    def emissoes(self) -> int:
        return len(self.cotacoes)

    def iniciar(self) -> "Simulador":
        for srv in (self._portal, self._spa):
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        return self

    def parar(self) -> None:
        for srv in (self._portal, self._spa):
            srv.shutdown()
            srv.server_close()

    def expirar(self) -> None:
        """A sessão do portal acaba: o próximo pedido ao portal ou ao cotador vai para o login, que
        depois do login volta para onde o robô estava (como o portal faz com ?volta=)."""
        with self.lock:
            self.sessoes.clear()
            self.sessao_expirada = True
            if self.acesso_ativo_depois_de_expirar:
                self.acesso_ativo = True

    # ------------------------------------------------------------------ portal antigo
    def _handler_portal(self):
        sim = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _sessao(self) -> bool:
                c = SimpleCookie(self.headers.get("Cookie", ""))
                return "sess" in c and c["sess"].value in sim.sessoes

            def _html(self, corpo: str, cookie: str | None = None, status: int = 200):
                dados = corpo.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(dados)))
                if cookie:
                    self.send_header("Set-Cookie", cookie)
                self.end_headers()
                self.wfile.write(dados)

            def _redirecionar(self, destino: str, cookie: str | None = None):
                self.send_response(303)
                self.send_header("Location", destino)
                self.send_header("Content-Length", "0")
                if cookie:
                    self.send_header("Set-Cookie", cookie)
                self.end_headers()

            def _json(self, obj, cookie: str | None = None):
                dados = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(dados)))
                if cookie:
                    self.send_header("Set-Cookie", cookie)
                self.end_headers()
                self.wfile.write(dados)

            def _nova_sessao(self) -> str:
                token = secrets.token_hex(8)
                with sim.lock:
                    sim.sessoes.add(token)
                    sim.sessao_expirada = False
                return f"sess={token}; Path=/"

            @staticmethod
            def _destino(volta: str) -> str:
                ok = volta.startswith("/") or volta.startswith(sim.url_spa + "/")
                return volta if ok else "/SaudeCotador/LoginGeral.aspx"

            def _entrar(self, volta: str):
                return self._redirecionar(self._destino(volta), self._nova_sessao())

            def _ajax_login(self, form: dict):
                """Como o portal (OutSystems): sair do CPF, marcar a caixa e Entrar são POSTs AJAX que
                respondem JSON; a página não recarrega. Entrar só vale com o CPF conferido e a caixa marcada."""
                acao, volta = form.get("acao"), form.get("volta", "")
                with sim.lock:
                    estado = sim._formularios.setdefault(form.get("__OSVSTATE", ""), {"cpf": "", "aceite": False})
                if acao == "cpf":
                    estado["cpf"] = "".join(ch for ch in form.get("cpf", "") if ch.isdigit())
                    return self._json({"ok": True})
                if acao == "aceite":
                    estado["aceite"] = form.get("ok") == "on"
                    return self._json({"ok": True})
                cpf = "".join(ch for ch in form.get("cpf", "") if ch.isdigit())
                if sim.validacao_forcada:
                    return self._json({"validacao": sim.validacao_forcada})
                if not cpf or cpf != estado["cpf"] or not form.get("email") or not form.get("senha"):
                    return self._json({"validacao": "Preencha CPF, e-mail e senha."})
                if not estado["aceite"]:
                    return self._json({"validacao": "Marque 'Ok, entendi!'."})
                sim.tentativas_login += 1
                if (cpf, form["email"].strip().lower(), form["senha"]) != (sim.cpf, sim.email.lower(), sim.senha):
                    return self._json({"erro": "Usuário ou senha inválidos."})
                if sim.acesso_ativo_por > 0:
                    sim.acesso_ativo_por -= 1
                    return self._json({"erro": "Já existe um acesso ativo para esse CPF. Tente novamente mais tarde."})
                if sim.acesso_ativo or (sim.um_acesso_por_cpf and sim.sessoes):   # texto visto no portal real em 03/11
                    return self._json({"erro": "Já existe um acesso ativo para esse CPF. Tente novamente mais tarde."})
                if sim.exigir_troca_senha:
                    return self._json({"troca": True})
                if sim.exigir_selecao_corretora:
                    return self._json({"selecao": True}, cookie=self._nova_sessao())
                if sim.exigir_codigo:
                    return self._json({"destino": f"/SaudeCotador/LoginGeral.aspx?codigo={sim._novo_pendente(volta)}"})
                return self._json({"destino": self._destino(volta)}, cookie=self._nova_sessao())

            def do_GET(self):
                sim.requisicoes += 1
                u = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                rota = u.path.lower()
                if rota == "/saudecotador/sair.aspx":     # "Sair do Cotador": acaba a sessão e volta ao login
                    c = SimpleCookie(self.headers.get("Cookie", ""))
                    with sim.lock:
                        if "sess" in c:
                            sim.sessoes.discard(c["sess"].value)
                        sim.saidas += 1
                    return self._redirecionar("/SaudeCotador/LoginGeral.aspx")
                if rota == "/saudecotador/logingeral.aspx":
                    if self._sessao() and not (sim.um_acesso_por_cpf and not self.headers.get("Referer")):
                        return self._html(sim.pagina_modulos())
                    if q.get("codigo") in sim._codigos_pendentes:
                        return self._html(sim.pagina_codigo(q["codigo"]))
                    volta = q.get("volta", "")
                    return self._html(sim.pagina_login("Sessão expirada. Faça login novamente." if volta else "", volta))
                if not self._sessao():
                    return self._redirecionar(f"/SaudeCotador/LoginGeral.aspx?volta={quote(self.path, safe='')}")
                if rota == "/saudecotador/abrircotador.aspx":   # passagem lenta para o cotador novo
                    return self._html(f"""<!doctype html><html><body><p>Abrindo o cotador...</p><script>
setTimeout(() => {{ location.href = "{sim.url_spa}/dados-empresa?novo=1"; }}, {int(sim.cotador_lento_ms)});
</script></body></html>""")
                if rota == "/saudecotador/painelcotacao.aspx":
                    return self._html(sim.pagina_painel())
                if rota == "/saudecotador/popupcotduplicar.aspx":   # o conteúdo do modal Copiar Cotação (iframe)
                    p = q.get("InIdCotacao", "")
                    return self._html(f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"></head><body>
<p>Deseja copiar a cotação?</p>
<input type="button" value="NÃO" onclick="window.parent.document.getElementById('modal').style.display='none'">
<input type="button" value="SIM" onclick="window.top.location.href='{sim.url_spa}/dados-empresa?copia={p}'">
</body></html>""")
                if rota == "/saudecotador/simulador.aspx":
                    return self._html(sim.pagina_emitida(q.get("p", "")))
                if rota == "/saudecotador/verpdf.aspx":   # visualizador que alguns portais abrem junto
                    return self._html(f"<!doctype html><html><body><p>Visualizar PDF {q.get('p', '')}</p></body></html>")
                if rota == "/saudecotador/download.aspx":
                    p = q.get("p", "")
                    with sim.lock:
                        falhar = p in sim.falhar_download
                        sim.falhar_download.discard(p)
                    if falhar or p not in sim.cotacoes:
                        return self._html("<h1>Erro ao gerar o arquivo</h1>", status=500)
                    self._pdf(p)
                    if sim.expirar_apos_download:
                        sim.expirar_apos_download = False
                        sim.expirar()
                    return None
                if rota == "/saudecotador/contratacao.aspx":
                    sim.visitas_contratacao += 1
                    return self._html("<h1>Contratação iniciada (o robô nunca deveria chegar aqui)</h1>")
                return self._html("<h1>404</h1>", status=404)

            def do_POST(self):
                sim.requisicoes += 1
                tamanho = int(self.headers.get("Content-Length", 0))
                form = {k: v[0] for k, v in parse_qs(self.rfile.read(tamanho).decode()).items()}
                volta = form.get("volta", "")
                if "codigo" in form:
                    with sim.lock:
                        destino = sim._codigos_pendentes.pop(form.get("pendente", ""), None)
                    if destino is None:
                        return self._html(sim.pagina_login("Sessão expirada. Faça login novamente."))
                    if form["codigo"].strip() != sim.codigo:
                        return self._html(sim.pagina_codigo(sim._novo_pendente(destino), "Código inválido."))
                    return self._entrar(destino)
                if "acao" in form:
                    return self._ajax_login(form)
                return self._html("<h1>Pedido inválido</h1>", status=400)

            def _pdf(self, p: str):
                c = sim.cotacoes[p]
                dados = pdf_simples([
                    "SulAmerica Saude - DADOS DA PROPOSTA COMERCIAL (SIMULADOR)",
                    f"Numero da proposta: {p}-1",
                    f"CNPJ: {c['cnpj']}  Razao social: {c['razao']}",
                    f"Plano: {c['plano']} - {c['acomodacao']}",
                    f"Total sem IOF: {c['total']}  IOF: {c['iof']}",
                ])
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="PropostaComercialCuidado360_{p}-1.pdf"')
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)
        return H

    # ------------------------------------------------------------------ cotador novo (SPA)
    def _handler_spa(self):
        sim = self
        app = (ESTATICO / "app.html").read_text(encoding="utf-8")

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, obj, status=200):
                dados = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

            def do_GET(self):
                u = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                if sim.sessao_expirada and not u.path.startswith("/api/"):
                    self.send_response(302)
                    self.send_header("Location", f"{sim.url_login}?volta={quote(sim.url_spa + self.path, safe='')}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if u.path == "/api/empresa":
                    d = "".join(ch for ch in q.get("cnpj", "") if ch.isdigit())
                    if not _cnpj_valido(d):
                        return self._json({"ok": False})
                    return self._json({"ok": True, "razao": f"EMPRESA TESTE {d[8:12]} LTDA",
                                       "endereco": "RUA DO TESTE, 100 - CENTRO - SAO PAULO/SP - 01000000",
                                       "municipio": "SAO PAULO - SP", "cep": "01000000"})
                if u.path.startswith("/api/cotacao/"):
                    p = u.path.rsplit("/", 1)[-1]
                    if p not in sim.cotacoes:
                        return self._json({"erro": "não encontrada"}, 404)
                    return self._json(sim.cotacoes[p])
                html = (app.replace("__PORTAL__", sim.url_portal)
                        .replace("__SO_CANCELAR__", "true" if sim.modal_sair_sem_confirmar else "false")
                        .replace("__TRAVA_COPART__", "true" if sim.copia_trava_copart else "false")
                        .replace("__TRAVAR_TROCA__", "true" if sim.travar_troca_cuidado else "false")
                        .replace("__DESTINO_SAIR__", "/SaudeCotador/PainelCotacao.aspx" if sim.sair_da_cotacao_vai_ao_painel
                                 else "/SaudeCotador/LoginGeral.aspx")).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)

            def do_POST(self):
                if urlparse(self.path).path != "/api/emitir":
                    return self._json({"erro": "rota"}, 404)
                tamanho = int(self.headers.get("Content-Length", 0))
                corpo = json.loads(self.rfile.read(tamanho).decode("utf-8"))
                with sim.lock:
                    protocolo = str(sim.proximo)
                    sim.proximo += 1
                    sim.cotacoes[protocolo] = {**corpo["resumo"], "estado": corpo["estado"]}
                return self._json({"protocolo": protocolo, "token": secrets.token_urlsafe(24)})
        return H

    # ------------------------------------------------------------------ páginas do portal antigo
    _ESTILO = """<style>body{font-family:Arial,sans-serif;margin:0;background:#f4f4f4}
    .topo{background:#e8651d;color:#fff;padding:14px 24px;font-weight:bold}
    .caixa{background:#fff;max-width:520px;margin:30px auto;padding:24px;border-radius:6px}
    input[type=text],input[type=password]{display:block;width:100%;margin:8px 0;padding:10px;box-sizing:border-box}
    .btn{display:inline-block;padding:10px 18px;margin:6px;border-radius:20px;background:#e8651d;color:#fff;
    text-decoration:none;font-weight:bold;border:0;cursor:pointer}.azul{background:#0b2e59}
    .cards{display:flex;gap:12px}.card{display:block;background:#fff;border:1px solid #ddd;padding:16px;
    width:150px;color:#333;text-decoration:none}#cookies{position:fixed;bottom:0;left:0;right:0;background:#fff;
    padding:10px;border-top:1px solid #ccc}#modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.4)}
    #modal>div{background:#fff;max-width:360px;margin:120px auto;padding:20px;text-align:center}</style>"""

    _COOKIES = """<div id="cookies">A SulAmérica somente utiliza cookies essenciais...
    <button class="btn" onclick="document.getElementById('cookies').remove()">ACEITO</button></div>"""

    def _novo_pendente(self, volta: str) -> str:
        token = secrets.token_hex(8)
        with self.lock:
            self._codigos_pendentes[token] = volta
        return token

    def pagina_login(self, erro: str = "", volta: str = "") -> str:
        """Imita a tela real (mapa de 03/11, OutSystems): campos sem <label> (nome pelo placeholder), caixa
        "Ok, entendi!" sem nome com um div de texto ao lado, botão escondido que o CPF clica ao perder o
        foco, AJAX em vez de recarregar, blocos escondidos de senha expirada e de escolha da corretora."""
        aviso = f'<p style="color:#b00">{erro}</p>' if erro else ""
        captcha = ('<iframe title="reCAPTCHA" src="about:blank" width="300" height="78"></iframe>'
                   '<p>Não sou um robô</p>') if self.exigir_captcha else ""
        estado = secrets.token_hex(8)
        return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Login</title>{self._ESTILO}</head>
<body><form class="caixa" method="post" action="/SaudeCotador/LoginGeral.aspx" onsubmit="return false">
<div><span>LOGIN</span><br><span>COTADOR SULAMERICA</span></div>{aviso}
<input type="hidden" id="osv" name="__OSVSTATE" value="{estado}">
<input type="hidden" id="volta" name="volta" value="{volta.replace('"', '&quot;')}">
<input type="text" id="cpf" maxlength="20" class="Mandatory" placeholder="CPF" autocomplete="off"
 onblur="document.getElementById('blurcpf').click();">
<input type="submit" id="blurcpf" tabindex="-1" value="." style="display:none" onclick="ajax({{acao: 'cpf', cpf: f('cpf').value}}); return false;">
<span class="ValidationMessage" role="alert" style="display:none" id="validacao"></span>
<input type="text" id="email" maxlength="250" class="Mandatory" placeholder="E-mail">
<input type="password" id="senha" maxlength="{self.senha_maxlength}" class="Mandatory" placeholder="Senha">
<a href="#">ESQUECEU SUA SENHA?</a>
<div id="expira" style="display:none"><b>Sua senha expirou.</b> REDEFINIR A SENHA</div>
<p>O uso dos dados... A SENHA utilizada para acessar o cotador é de seu conhecimento e uso exclusivo...</p>
{captcha}<div><input type="checkbox" id="aceite" class="check-custom aceite" onclick="ajax({{acao: 'aceite', ok: f('aceite').checked ? 'on' : ''}});"><div class="aceite_texto">Ok, entendi!</div></div>
<input type="submit" class="btn" value="Entrar" onclick="entrar(); return false;">
<div id="feedback"></div>
<div id="selecao" style="display:none"><p>Selecione sua Corretora ou EV</p><select><option>Selecione</option></select></div>
</form>{self._COOKIES}
<script>
const f = (id) => document.getElementById(id);
async function ajax(dados) {{
  const corpo = new URLSearchParams({{...dados, __OSVSTATE: f('osv').value, volta: f('volta').value}});
  const r = await fetch('/SaudeCotador/LoginGeral.aspx', {{method: 'POST', body: corpo}});
  return r.json();
}}
async function entrar() {{
  const j = await ajax({{acao: 'entrar', cpf: f('cpf').value, email: f('email').value, senha: f('senha').value}});
  if (j.destino) {{ location.href = j.destino; return; }}
  if (j.validacao) {{ f('validacao').textContent = j.validacao; f('validacao').style.display = 'inline'; return; }}
  if (j.troca) {{ f('expira').style.display = 'block'; return; }}
  if (j.selecao) {{ f('selecao').style.display = 'block'; return; }}
  f('feedback').innerHTML = '<div class="Feedback_Message_Error">' + j.erro + '</div>';
}}
</script></body></html>"""

    def pagina_codigo(self, pendente: str, erro: str = "") -> str:
        aviso = f'<p style="color:#b00">{erro}</p>' if erro else ""
        return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Verificação</title>{self._ESTILO}</head>
<body><form class="caixa" method="post" action="/SaudeCotador/LoginGeral.aspx">
<p>Digite o código de verificação enviado para o seu celular.</p>{aviso}
<input type="hidden" name="pendente" value="{pendente}">
<input type="text" name="codigo" placeholder="Código de verificação" autocomplete="one-time-code">
<button class="btn" type="submit">CONFIRMAR</button></form></body></html>"""

    # Como o cabeçalho do portal (mapa 01_login.html de 05/11): ícone de 3 barras (a.menuLeft) abre o menu
    # lateral com "Sair do Cotador" (div.logout ...wtLogout).
    _CABECALHO = """<div class="cabecalho"><a class="menuLeft" id="VanillaTheme_wtMenuLateral2" href="#" aria-label="Menu"
 onclick="document.getElementById('menuSlide').style.display='block';return false;">&#9776;</a>
<div id="menuSlide" class="menuSlide" style="display:none"><div><span>Consultor</span></div>
<div id="VanillaTheme_wtLogout" class="logout" tabindex="-1" onclick="location.href='/SaudeCotador/Sair.aspx'"><span tabindex="-1">Sair do Cotador</span></div></div></div>"""

    def pagina_painel(self) -> str:
        """Como o portal real (05/11): "Voltar para a Home" leva ao painel "ESTOU EM COTAÇÕES"
        (PainelCotacao.aspx), com o cartão NOVA COTAÇÃO e um campo de senha escondido no cabeçalho."""
        return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Página Inicial</title>{self._ESTILO}</head>
<body>{self._CABECALHO}<div class="caixa"><h2>ESTOU EM COTAÇÕES</h2>
<div style="display:none"><input type="password" id="wtInpNovaSenha" autocomplete="off"></div>
<div class="cards"><a class="card" href="{self.url_spa}/dados-empresa?novo=1"><div>NOVA</div><div><b>COTAÇÃO</b></div></a>
<div class="card"><b>500</b><br>EM PREENCHIMENTO</div><div class="card"><b>2555</b><br>CONCLUÍDAS</div></div>
<p><a href="#">IR PARA O MÓDULO IMPLANTAÇÃO</a> <a href="#">VER TODAS AS COTAÇÕES</a>
<a href="/SaudeCotador/LoginGeral.aspx">SELECIONAR OUTRO MÓDULO</a></p></div></body></html>"""

    def pagina_modulos(self) -> str:
        return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Módulos</title>{self._ESTILO}</head>
<body>{self._CABECALHO}
<div class="caixa"><div><span>COTADOR SULAMERICA</span><br><span>SELECIONE UM MÓDULO</span></div>
<p>Com qual módulo deseja trabalhar?</p><div class="cards">
<a class="card" href="{"/SaudeCotador/AbrirCotador.aspx" if self.cotador_lento_ms else self.url_spa + "/dados-empresa?novo=1"}"
 {'target="_blank"' if self.cotador_em_aba_nova else ""}><h3>Cotação PME</h3><p>3 a 29 Vidas</p>
<small>Permite a realização e acompanhamento de solicitações de estudos</small></a>
<a class="card" href="#"><h3>Módulo Cotação</h3><p>30 Vidas ou Mais</p></a>
<a class="card" href="#"><h3>Módulo Implantação</h3></a></div>
<p><a href="#">Cotações emitidas</a> Acompanhe as propostas criadas</p></div></body></html>"""

    def pagina_emitida(self, p: str) -> str:
        if p not in self.cotacoes:
            return "<h1>Cotação não encontrada</h1>"
        # pdf_abre_aba: BAIXAR baixa nesta aba e abre o visualizador em outra (o robô fecha a aba extra).
        abrir_pdf = (" onclick=\"window.open('/SaudeCotador/VerPdf.aspx?p=" + p + "', '_blank')\""
                     if self.pdf_abre_aba else "")
        voltar_home = "" if self.sem_voltar_home else '<p><a href="/SaudeCotador/PainelCotacao.aspx">Voltar para a Home</a></p>'
        return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Simulador</title>{self._ESTILO}</head>
<body><div class="caixa" style="text-align:center"><p>COTAÇÃO EMITIDA COM SUCESSO!</p>
<p><small>Protocolo Saúde: nº {p}</small></p>
<input type="text" id="wtInpTokenCotacao" style="display:none" value="">
<a class="btn" href="/SaudeCotador/Download.aspx?p={p}"{abrir_pdf}>BAIXAR COTAÇÃO SAÚDE</a>
<a class="btn azul" href="/SaudeCotador/Contratacao.aspx?p={p}">INICIAR CONTRATAÇÃO</a><br>
<a class="btn" href="{self.url_spa}/dados-empresa?novo=1">NOVA COTAÇÃO</a>
<a class="btn" href="#">ENVIAR POR E-MAIL</a>
<a class="btn" href="#" onclick="document.getElementById('modal').style.display='block';document.getElementById('frameCopiar').src='PopUpCotDuplicar.aspx?InIdCotacao={p}';return false;">COPIAR COTAÇÃO</a>
{voltar_home}
<p>Você será notificado dentro do Sistema Cotador a cada mudança de status.</p></div>
<div id="modal" role="dialog" aria-label="Copiar Cotação"><div><span>Copiar Cotação</span>
<button type="button" onclick="document.getElementById('modal').style.display='none'">&times;</button>
<iframe id="frameCopiar" width="100%" height="160" frameborder="0" src="about:blank"></iframe></div></div>{self._COOKIES}</body></html>"""
