"""Simulador local do Corretor Online (Porto Saúde PME). Login FALSO e valores fictícios da Seção 3.

Não fala com a Porto. O cotador fica num iframe, como o portal. Conta cliques nos botões que o robô
NUNCA pode acionar (Elaborar proposta, Adicionar à Proposta, Remissão, Editar, Duplicar).
"""
from __future__ import annotations

import html
import json
import secrets
import threading
from decimal import ROUND_HALF_UP, Decimal
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from ..pedido import COMISSAO_K001

D = Decimal


def _d(v) -> Decimal:
    return D(str(v)).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def reais(v) -> str:
    inteiro, dec = f"{_d(v):.2f}".split(".")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    return "R$ " + ".".join([inteiro] + grupos) + "," + dec


# Valores fictícios (Seção 3 do mapa), empresa de treino — nenhum cliente real.
# 4 vidas: 1×0 anos, 2×34-38, 1×59-60. 3 vidas: 1×0, 2×34-38.
PRECO_4 = {
    "P220": D("2184.68"), "P320": D("2496.57"), "P420": D("3386.12"), "P470": D("4142.29"),
    "Bronze Brasil I": D("2671.06"), "Prata Mais I": D("3368.73"),
    "Ouro Mais I": D("4591.96"), "Ouro Max I": D("5556.53"),
    "Ouro Pro": D("2865.57"), "Diamante Pro": D("4328.20"),
}
PRECO_3 = {
    "P220": D("1114.79"), "P320": D("1273.94"), "P420": D("1727.86"), "P470": D("2113.71"),
    "Bronze Brasil I": D("1362.98"), "Prata Mais I": D("1718.98"),
    "Ouro Mais I": D("2343.16"), "Ouro Max I": D("2835.36"),
    "Ouro Pro": D("1462.23"), "Diamante Pro": D("2208.58"),
}
FAIXAS_4 = {  # valor por beneficiário sem IOF
    "Ouro Mais I": {"0 - 18": D("864.89"), "34 - 38": D("670.75"), "59+": D("2385.57")},
    "P470": {"0 - 18": D("429.93"), "34 - 38": D("780.19"), "59+": D("2151.97")},
}
FAIXAS_3 = {
    "Ouro Max I": {"0 - 18": D("612.67"), "34 - 38": D("1111.35")},
    "P470": {"0 - 18": D("456.59"), "34 - 38": D("828.56")},
}
PLANOS = list(PRECO_4)
EMPRESAS = {"11222333000181": "PADARIA MODELO DE TREINO LTDA"}
OPERADORAS_ANTERIORES = ["Não Possui Plano Anterior", "NotreDame Intermédica", "SulAmérica", "Amil"]
COMISSOES = [
    "H175 | ag1(100%) | ag2(0%) | ag3(0%) | Corretagem(5%)",
    COMISSAO_K001,
    "K070 | ag1(100%) | ag2(100%) | ag3(0%) | Corretagem(7,5%)",
    "K130 | ag1(100%) | ag2(100%) | ag3(0%) | Corretagem(5%)",
]


def calcular(plano: str, vidas: dict[str, int]) -> dict:
    total = sum(vidas.values())
    tabela = PRECO_3 if total <= 3 else PRECO_4
    subtotal = _d(tabela.get(plano, D("1000.00") * total))
    faixas = (FAIXAS_3 if total <= 3 else FAIXAS_4).get(plano, {})
    taxa = _d(D("5.00") * total)
    iof = _d((subtotal + taxa) * D("0.0238"))
    return {"subtotal": subtotal, "taxa": taxa, "iof": iof, "total": _d(subtotal + taxa + iof),
            "faixas": faixas, "vidas": total}


def _pdf(numero: str, plano: str, cnpj: str) -> bytes:
    texto = f"Indicativo de Precos Saude - PME cotacao {numero} CNPJ {cnpj} plano {plano}"
    conteudo = (f"BT /F1 12 Tf 50 780 Td ({texto}) Tj ET").encode("latin-1", "replace")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(conteudo)).encode() + b" >>\nstream\n" + conteudo + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length 6000 >>\nstream\n" + (b"0" * 6000) + b"\nendstream",
    ]
    saida, posicoes = b"%PDF-1.4\n", []
    for i, obj in enumerate(objetos, 1):
        posicoes.append(len(saida))
        saida += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for pos in posicoes:
        saida += f"{pos:010d} 00000 n \n".encode()
    saida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return saida


CSS = """
body{font-family:Arial,sans-serif;margin:0;color:#1a1a1a}
header{background:#00A651;color:#fff;padding:10px 16px}
main{padding:16px}
.card{border:1px solid #ccc;border-radius:8px;padding:16px;margin:12px 0}
button,.btn{background:#00A651;color:#fff;border:0;border-radius:6px;padding:8px 14px;cursor:pointer;margin:4px}
button.sec{background:#eee;color:#333}
input,select{padding:6px;margin:4px 0}
.erro{color:#b00;border:1px solid #b00;padding:8px;margin:8px 0}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center}
.modal .box{background:#fff;padding:20px;border-radius:8px;min-width:320px}
[data-plano]{display:inline-block;margin:4px;padding:10px;border:1px solid #aaa;background:#f7f7f7;color:#111}
[data-plano].sel{border:2px solid #00A651;background:#e8f8ef}
iframe#cotador{width:100%;height:720px;border:0}
.proibido{background:#c00}
#susep-caixa{width:100%;text-align:left;background:#fff;color:#111;border:1px solid #888}
#susep-lista{list-style:none;margin:4px 0 0;padding:0;border:1px solid #888;background:#fff}
#susep-lista li{padding:8px;cursor:pointer}
#susep-lista li:hover{background:#e8f8ef}
"""


def _pagina(titulo: str, corpo: str, script: str = "") -> str:
    return (f"<!doctype html><html lang=pt-BR><head><meta charset=utf-8><title>{html.escape(titulo)}</title>"
            f"<style>{CSS}</style></head><body>{corpo}<script>{script}</script></body></html>")


class Simulador:
    CPF = "529.982.247-25"
    SENHA = "Treino#Porto1"
    SUSEP = "BX865J"
    SUSEPS = ("381N5F", "BX865J", "1VTUFJ", "1Y5ZLJ")
    SUSEP_COM_P = frozenset({"381N5F", "BX865J"})

    def __init__(self, porta: int = 0):
        self.cpf, self.senha = self.CPF, self.SENHA
        self.susep = self.SUSEP
        self.susep_escolhida = ""
        self.codigos_susep = list(self.SUSEPS)
        self.susep_com_p = set(self.SUSEP_COM_P)
        self.dropdown_susep = "select"  # "select" nativo | "menu" personalizado (só clique)
        self.atraso_susep_ms = 0
        self.sessoes: dict[str, dict] = {}
        self.exigir_captcha = False
        self.tentativas_login = 0
        self.cotacoes: dict[str, dict] = {}
        self.proxima = 9000001
        self.downloads = 0
        self.gerar_orcamento_cliques = 0
        self.emitir_sem_medicamentos_cliques = 0
        self.elaborar_proposta_cliques = 0
        self.adicionar_proposta_cliques = 0
        self.remissao_cliques = 0
        self.editar_cliques = 0
        self.duplicar_cliques = 0
        self.falhas_pdf_restantes = 0
        self.cair_depois_de_gerar = False
        self.httpd: ThreadingHTTPServer | None = None
        self.thread = None
        self.porta = porta

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.porta}/"

    @property
    def url_login(self) -> str:
        return f"http://127.0.0.1:{self.porta}/login"

    @property
    def url_home(self) -> str:
        return f"http://127.0.0.1:{self.porta}/home"

    @property
    def url_cotar(self) -> str:
        return f"http://127.0.0.1:{self.porta}/cotar"

    def iniciar(self):
        sim = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def _sid(self) -> str:
                c = SimpleCookie(self.headers.get("Cookie", ""))
                return c["sid"].value if "sid" in c else ""

            def _sess(self) -> dict | None:
                return sim.sessoes.get(self._sid())

            def _json(self, codigo, dados, sid=None):
                corpo = json.dumps(dados).encode()
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(corpo)))
                if sid:
                    self.send_header("Set-Cookie", f"sid={sid}; Path=/")
                self.end_headers()
                self.wfile.write(corpo)

            def _html(self, codigo, texto, sid=None):
                corpo = texto.encode("utf-8")
                self.send_response(codigo)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo)))
                if sid:
                    self.send_header("Set-Cookie", f"sid={sid}; Path=/")
                self.end_headers()
                self.wfile.write(corpo)

            def _bytes(self, corpo: bytes, tipo: str):
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

            def _body(self) -> dict:
                n = int(self.headers.get("Content-Length") or 0)
                bruto = self.rfile.read(n) if n else b""
                if not bruto:
                    return {}
                try:
                    return json.loads(bruto.decode())
                except json.JSONDecodeError:
                    return {k: v[0] for k, v in parse_qs(bruto.decode()).items()}

            def do_GET(self):
                path = urlparse(self.path).path
                qs = parse_qs(urlparse(self.path).query)
                sess = self._sess()
                if path == "/login":
                    desafio = ("<p id='captcha' class='erro'>Não sou um robô — desafio reCAPTCHA</p>"
                               if sim.exigir_captcha else "")
                    self._html(200, _pagina("Login Porto", f"""
<header>Corretor Online</header><main class=card style="width:360px;margin:40px auto">
<h2>Acesse o Corretor Online</h2>
<label for=cpf>CPF</label><br><input id=cpf name=cpf autocomplete=off><br>
<label for=senha>Senha</label><br><input id=senha name=senha type=password autocomplete=off><br>
<button id=entrar>ENTRAR</button>
<small>O Recaptcha serve para a sua maior segurança ao acessar o Corretor Online.</small>
{desafio}<p id=erro class=erro style="display:none"></p>
</main><script>
document.getElementById('entrar').onclick=async()=>{{
 const r=await (await fetch('/api/login',{{method:'POST',headers:{{'Content-Type':'application/json'}},
  body:JSON.stringify({{cpf:cpf.value,senha:senha.value}})}})).json();
 if(r.ok) location=r.ir; else {{erro.style.display='block';erro.textContent=r.erro;}}
}};
</script>"""))
                    return
                if path == "/susep":
                    if not sess:
                        self.send_response(302); self.send_header("Location", "/login"); self.end_headers(); return
                    self._html(200, _pagina_susep(sim))
                    return
                if path == "/home":
                    if not sess:
                        self.send_response(302); self.send_header("Location", "/login"); self.end_headers(); return
                    self._html(200, _pagina("Home", f"<header>EDLAINE {sess.get('susep','')} · Corretor Online "
                                                    f"<button id=sair>Sair</button></header>"
                                                    f"<iframe id=cotador src='/cotar'></iframe>"
                                                    "<script>sair.onclick=async()=>{await fetch('/api/sair',{method:'POST'});location='/login'}</script>"))
                    return
                if path == "/cotar":
                    if not sess:
                        self._html(401, _pagina("Login", "<p>sessão caiu</p>")); return
                    self._html(200, _cotar_html(sim, sess, qs))
                    return
                if path == "/pdf":
                    numero = (qs.get("n") or [""])[0]
                    cot = sim.cotacoes.get(numero)
                    if not cot:
                        self.send_response(404); self.end_headers(); return
                    sim.downloads += 1
                    self._bytes(_pdf(numero, cot["plano"], cot["cnpj"]), "application/pdf")
                    return
                if path == "/":
                    self._html(200, _pagina_entrada())
                    return
                self.send_response(404); self.end_headers()

            def do_POST(self):
                path = urlparse(self.path).path
                dados = self._body()
                sess = self._sess()
                if path == "/api/login":
                    sim.tentativas_login += 1
                    cpf, senha = (dados.get("cpf") or "").replace(".", "").replace("-", ""), dados.get("senha")
                    if sim.exigir_captcha:
                        self._json(200, {"ok": False, "erro": "Não sou um robô — desafio reCAPTCHA"}); return
                    if so_digitos(cpf) != so_digitos(sim.cpf) or senha != sim.senha:
                        self._json(200, {"ok": False, "erro": "CPF ou senha inválidos"}); return
                    sid = secrets.token_hex(8)
                    sim.sessoes[sid] = {"logado": True, "passo": "lista", "rascunho": {}, "susep": ""}
                    self._json(200, {"ok": True, "ir": "/susep"}, sid=sid); return
                if path == "/api/susep" and sess:
                    sess["susep"] = dados.get("codigo") or ""
                    sim.susep_escolhida = sess["susep"]
                    self._json(200, {"ok": True}); return
                if path == "/api/sair" and sess:
                    sim.sessoes.pop(self._sid(), None)
                    self._json(200, {"ok": True}); return
                if path == "/api/proibido":
                    qual = dados.get("qual")
                    if qual == "elaborar":
                        sim.elaborar_proposta_cliques += 1
                    elif qual == "adicionar":
                        sim.adicionar_proposta_cliques += 1
                    elif qual == "remissao":
                        sim.remissao_cliques += 1
                    elif qual == "editar":
                        sim.editar_cliques += 1
                    elif qual == "duplicar":
                        sim.duplicar_cliques += 1
                    self._json(200, {"ok": True}); return
                if not sess:
                    self._json(401, {"ok": False, "erro": "sessão"}); return
                if path == "/api/cotar":
                    self._json(200, _api_cotar(sim, sess, dados)); return
                self._json(404, {"ok": False})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.porta), H)
        self.porta = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self

    def parar(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()


def _pagina_entrada() -> str:
    """Página pública: aviso de localização, cookies e o botão que abre a janela de login."""
    corpo = """
<header>Porto Seguro · Corretor Online</header>
<main class=card style="width:420px;margin:40px auto">
<div id=aviso-localizacao role=dialog>
 <p>O site quer saber sua localização.</p>
 <button type=button id=loc-bloquear>Bloquear</button>
</div>
<div id=aviso-cookies>
 <p>Usamos cookies.</p>
 <button type=button id=cookies-recusar>Recusar cookies</button>
</div>
<h1>Corretor Online</h1>
<p>Para cotar, entre no Corretor Online.</p>
<button type=button id=acessar class="ps-btn ps-btn-secondary">ACESSAR O CORRETOR ONLINE</button>
<input type=password style="display:none" aria-hidden="true" tabindex="-1">
<input type=password style="display:none" aria-hidden="true" tabindex="-1">
</main>
"""
    script = """
document.getElementById('loc-bloquear').onclick=()=>document.getElementById('aviso-localizacao').remove();
document.getElementById('cookies-recusar').onclick=()=>document.getElementById('aviso-cookies').remove();
document.getElementById('acessar').onclick=()=>{ location.href='/login'; };
"""
    return _pagina("Corretor Online", corpo, script)


def so_digitos(t) -> str:
    return "".join(c for c in str(t or "") if c.isdigit())


def _itens_susep(sim: Simulador) -> list[tuple[str, str]]:
    itens = []
    for c in sim.codigos_susep:
        rotulo = f"{c} (P)" if c in sim.susep_com_p else c
        itens.append((c, rotulo))
    return itens


def _pagina_susep(sim: Simulador) -> str:
    """Dropdown só clicável (não aceita digitar), com atraso opcional, select nativo ou menu."""
    itens = _itens_susep(sim)
    atraso = int(sim.atraso_susep_ms or 0)
    js_itens = json.dumps([{"codigo": c, "rotulo": r} for c, r in itens])
    if sim.dropdown_susep == "menu":
        corpo = """
<header>Acesse o Corretor Online</header>
<main class=card style="width:360px;margin:40px auto">
<h2>Acesse o Corretor Online</h2>
<label id=lb-susep>SUSEP</label><br>
<button type=button id=susep-caixa role=combobox aria-labelledby=lb-susep aria-haspopup=listbox
 aria-expanded=false aria-label=SUSEP>Selecione</button>
<ul id=susep-lista role=listbox hidden></ul>
</main>"""
        script = f"""
const itens={js_itens};
const caixa=document.getElementById('susep-caixa');
const lista=document.getElementById('susep-lista');
function enviar(codigo){{
 fetch('/api/susep',{{method:'POST',headers:{{'Content-Type':'application/json'}},
  body:JSON.stringify({{codigo}})}}).then(()=>location='/home');
}}
function montar(){{
 lista.innerHTML='';
 itens.forEach(it=>{{
  const li=document.createElement('li');
  li.setAttribute('role','option');
  li.dataset.susep=it.codigo;
  li.textContent=it.rotulo;
  li.onclick=e=>{{e.stopPropagation();enviar(it.codigo);}};
  lista.appendChild(li);
 }});
 lista.hidden=false;
 caixa.setAttribute('aria-expanded','true');
}}
caixa.onclick=()=>{{
 if(!lista.hidden) return;
 if({atraso}>0) setTimeout(montar,{atraso}); else montar();
}};
caixa.addEventListener('keydown',e=>e.preventDefault());
"""
        return _pagina("Acesse o Corretor Online", corpo, script)
    corpo = """
<header>Acesse o Corretor Online</header>
<main class=card style="width:360px;margin:40px auto">
<h2>Acesse o Corretor Online</h2>
<label for=susep>SUSEP</label><br>
<select id=susep name=susep aria-label=SUSEP></select>
</main>"""
    script = f"""
const itens={js_itens};
const caixa=document.getElementById('susep');
function montar(){{
 caixa.innerHTML='<option value="">Selecione</option>'+itens.map(it=>
  '<option value="'+it.codigo+'">'+it.rotulo+'</option>').join('');
}}
caixa.onchange=async()=>{{
 if(!caixa.value) return;
 await fetch('/api/susep',{{method:'POST',headers:{{'Content-Type':'application/json'}},
  body:JSON.stringify({{codigo:caixa.value}})}});
 location='/home';
}};
caixa.addEventListener('keydown',e=>{{
 if(e.key.length===1) e.preventDefault();
}});
if({atraso}>0) setTimeout(montar,{atraso}); else montar();
"""
    return _pagina("Acesse o Corretor Online", corpo, script)


def _api_cotar(sim: Simulador, sess: dict, dados: dict) -> dict:
    acao = dados.get("acao")
    r = sess.setdefault("rascunho", {})
    if acao == "nova":
        sess["passo"] = "dados"
        sess["rascunho"] = {}
        return {"ok": True, "passo": "dados"}
    if acao == "cnpj":
        cnpj = so_digitos(dados.get("cnpj"))
        razao = EMPRESAS.get(cnpj)
        if not razao:
            return {"ok": False, "erro": "CNPJ não encontrado na Receita de treino"}
        r.update({"cnpj": cnpj, "razao": razao})
        sess["passo"] = "vidas"
        return {"ok": True, "passo": "vidas", "razao": razao}
    if acao == "vidas":
        r["total"] = int(dados.get("total") or 0)
        r["anterior"] = dados.get("anterior") or ""
        r["faixas"] = dados.get("faixas") or {}
        r["idades"] = dados.get("idades") or {}
        soma = sum(int(v or 0) for v in (r["faixas"] or {}).values())
        if soma != r["total"]:
            extra = soma - r["total"]
            msg = (f"Quantidade de vidas — [Faltam: {-extra} vidas]" if extra < 0
                   else f"Quantidade de vidas — [Ultrapassou a quantidade informada em {extra} vidas]")
            return {"ok": False, "erro": msg}
        sess["passo"] = "comissao"
        return {"ok": True, "passo": "comissao"}
    if acao == "comissao":
        r["comissao"] = dados.get("comissao") or ""
        r["agenciamento"] = bool(dados.get("agenciamento"))
        sess["passo"] = "planos"
        return {"ok": True, "passo": "planos"}
    if acao == "plano":
        r["plano"] = dados.get("plano")
        r["acomodacao"] = dados.get("acomodacao") or "Apartamento"
        r["copart"] = dados.get("copart") or "30%"
        return {"ok": True, "passo": "planos", "selecionado": r["plano"]}
    if acao == "gerar":
        sim.gerar_orcamento_cliques += 1
        if not r.get("plano"):
            return {"ok": False, "erro": "sem plano"}
        sess["passo"] = "modal"
        return {"ok": True, "passo": "modal"}
    if acao == "emitir_sem_med":
        sim.emitir_sem_medicamentos_cliques += 1
        if sim.cair_depois_de_gerar:
            sim.cair_depois_de_gerar = False
            numero = str(sim.proxima)
            sim.proxima += 1
            faixas = {k: int(v or 0) for k, v in (r.get("faixas") or {}).items()}
            calc = calcular(r["plano"], faixas)
            sim.cotacoes[numero] = {"numero": numero, "cnpj": r.get("cnpj"), "plano": r["plano"],
                                    "status": "Calculada", **{k: str(v) for k, v in calc.items() if k != "faixas"},
                                    "acomodacao": r.get("acomodacao"), "razao": r.get("razao")}
            sess["passo"] = "lista"
            sess["rascunho"] = {}
            return {"ok": False, "caiu": True}
        numero = str(sim.proxima)
        sim.proxima += 1
        faixas = {k: int(v or 0) for k, v in (r.get("faixas") or {}).items()}
        calc = calcular(r["plano"], faixas)
        cot = {"numero": numero, "cnpj": r.get("cnpj"), "plano": r["plano"], "status": "Calculada",
               "acomodacao": r.get("acomodacao"), "razao": r.get("razao"),
               "subtotal": calc["subtotal"], "taxa": calc["taxa"], "iof": calc["iof"], "total": calc["total"]}
        sim.cotacoes[numero] = cot
        sess["passo"] = "resultado"
        sess["atual"] = numero
        return {"ok": True, "passo": "resultado", "numero": numero,
                "subtotal": str(calc["subtotal"]), "taxa": str(calc["taxa"]),
                "iof": str(calc["iof"]), "total": str(calc["total"])}
    if acao == "imprimir":
        if sim.falhas_pdf_restantes > 0:
            sim.falhas_pdf_restantes -= 1
            return {"ok": False, "erro_pdf": True}
        numero = sess.get("atual") or dados.get("numero")
        return {"ok": True, "url": f"/pdf?n={numero}"}
    if acao == "lista":
        sess["passo"] = "lista"
        sess["rascunho"] = {}
        return {"ok": True, "passo": "lista"}
    if acao == "visualizar":
        numero = dados.get("numero")
        if numero not in sim.cotacoes:
            return {"ok": False}
        sess["passo"] = "resultado"
        sess["atual"] = numero
        return {"ok": True, "passo": "resultado"}
    return {"ok": False}


def _cotar_html(sim: Simulador, sess: dict, qs) -> str:
    passo = sess.get("passo") or "lista"
    r = sess.get("rascunho") or {}
    busca = (qs.get("cnpj") or [""])[0]
    if passo == "lista":
        linhas = []
        for n, c in sim.cotacoes.items():
            if busca and so_digitos(busca) not in str(c.get("cnpj")):
                continue
            linhas.append(f"<tr><td>{n}</td><td>{c.get('plano')}</td><td>{c.get('status')}</td>"
                          f"<td><button data-vis='{n}'>Visualizar</button>"
                          f"<button class=proibido data-proibido=editar>Editar</button>"
                          f"<button class=proibido data-proibido=duplicar>Duplicar orçamento</button>"
                          f"<button class=proibido data-proibido=elaborar>Elaborar proposta</button></td></tr>")
        corpo = f"""<main>
<h2>Acompanhe o status da cotação / estudo</h2>
<button id=nova>Criar nova cotação</button>
<label>Busca por CNPJ</label> <input id=busca-cotacao value='{html.escape(busca)}'>
<table><thead><tr><th>Nº</th><th>Plano</th><th>Status</th><th></th></tr></thead>
<tbody>{''.join(linhas) or '<tr><td colspan=4>nenhuma</td></tr>'}</tbody></table>
<button class=proibido data-proibido=elaborar>Elaborar proposta</button>
</main>"""
        script = """
const api=(acao,extra={})=>fetch('/api/cotar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({acao,...extra})}).then(r=>r.json());
nova.onclick=async()=>{await api('nova');location='/cotar'};
document.querySelectorAll('[data-vis]').forEach(b=>b.onclick=async()=>{await api('visualizar',{numero:b.dataset.vis});location='/cotar'});
document.querySelectorAll('[data-proibido]').forEach(b=>b.onclick=()=>fetch('/api/proibido',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({qual:b.dataset.proibido})}));
"""
        return _pagina("Cotador", corpo, script)

    if passo == "dados":
        return _pagina("1 de 4 — Dados iniciais", f"""<main class=card>
<h2>1 de 4 — Dados iniciais</h2>
<label for=cnpj>CNPJ</label><input id=cnpj name=cnpj>
<p>Razão social: <span id=rs>{html.escape(r.get('razao') or '')}</span></p>
<p>CNAE: 5611-2/01 · CEP: 01310-100 · São Paulo/SP</p>
<button id=proximo>Próximo</button></main>""", """
const api=(acao,extra={})=>fetch('/api/cotar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({acao,...extra})}).then(r=>r.json());
const EMP={'11222333000181':'PADARIA MODELO DE TREINO LTDA'};
cnpj.oninput=()=>{const d=(cnpj.value||'').replace(/\\D/g,''); rs.textContent=EMP[d]||'';};
proximo.onclick=async()=>{const r=await api('cnpj',{cnpj:cnpj.value}); if(r.ok) location='/cotar'; else alert(r.erro);};
""")

    if passo == "vidas":
        faixas = "".join(
            f"<div><label>{rot}</label> <input data-faixa='{rot}' value='0'>"
            + ("".join(f" <input data-idade='{i}' placeholder='{i} anos' style='width:70px'>" for i in range(0, 19))
               if rot == "0 - 18" else "")
            + "</div>"
            for rot in ["0 - 18", "19 - 23", "24 - 28", "29 - 33", "34 - 38", "39 - 43", "44 - 48", "49 - 53", "54 - 58", "59+"])
        ops = "".join(f"<option>{html.escape(o)}</option>" for o in OPERADORAS_ANTERIORES)
        return _pagina("2 de 4 — Produto e vidas", f"""<main class=card>
<h2>2 de 4 — Produto e vidas</h2>
<p>Produto: Saúde</p>
<label for=total-vidas>Quantidade total</label> <input id=total-vidas>
<label for=plano-anterior>Informe se esta empresa possui plano anterior</label>
<select id=plano-anterior name=anterior><option value=''>Selecione</option>{ops}</select>
<h3>Distribuir vidas por faixa</h3>{faixas}
<p id=erro class=erro style=display:none></p>
<button id=proximo>Próximo</button></main>""", """
const api=(acao,extra={})=>fetch('/api/cotar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({acao,...extra})}).then(r=>r.json());
proximo.onclick=async()=>{
 const faixas={}; document.querySelectorAll('[data-faixa]').forEach(i=>faixas[i.dataset.faixa]=i.value);
 const idades={}; document.querySelectorAll('[data-idade]').forEach(i=>{if(i.value) idades[i.dataset.idade]=i.value});
 const r=await api('vidas',{total:document.getElementById('total-vidas').value, anterior:document.getElementById('plano-anterior').value, faixas, idades});
 if(r.ok) location='/cotar'; else {erro.style.display='block'; erro.textContent=r.erro;}
};
""")

    if passo == "comissao":
        ops = "".join(f"<option>{html.escape(c)}</option>" for c in COMISSOES)
        return _pagina("Comissão", f"""<main class=card>
<h2>Selecione uma das opções de comissão</h2>
<label for=comissao>Comissão</label>
<select id=comissao>{ops}</select>
<label><input type=checkbox id=agenciamento> Li e estou de acordo com as regras de agenciamento</label>
<button id=proximo>Próximo</button></main>""", """
const api=(acao,extra={})=>fetch('/api/cotar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({acao,...extra})}).then(r=>r.json());
proximo.onclick=async()=>{await api('comissao',{comissao:comissao.value, agenciamento:agenciamento.checked}); location='/cotar'};
""")

    if passo == "planos":
        total = int(r.get("total") or 4)
        tabela = PRECO_3 if total <= 3 else PRECO_4
        grade = "".join(
            f"<button type=button data-plano=\"{html.escape(n)}\">{html.escape(n)}</button> "
            f"<span>{reais(tabela[n])}</span> "
            for n in PLANOS)
        sel = html.escape(r.get("plano") or "")
        return _pagina("3 de 4 — Selecionar o plano", f"""<main class=card>
<h2>3 de 4 — Selecionar o plano</h2>
<p>Todas as vidas em um único plano</p>
<label><input type=radio name=acomodacao value=Apartamento checked> Apartamento</label>
<label><input type=radio name=acomodacao value=Enfermaria> Enfermaria</label>
<label><input type=radio name=copart value='0%'> 0%</label>
<label><input type=radio name=copart value='30%' checked> 30%</label>
<div id=grade>{grade}</div>
<div class=card><h3>Resumo da cotação</h3>
<p>Plano: <span id=rp>{sel}</span></p>
<p>Valor: <span id=rv></span></p>
<p id=sel>{'Selecionado' if sel else ''}</p>
<label><input type=checkbox checked disabled> Seguro Odonto + Vida</label>
<label><input type=checkbox id=med> Cobertura Medicamentos</label>
<label><input type=checkbox id=rem data-proibido=remissao> Remissão</label>
</div>
<button id=gerar>Gerar orçamento</button>
<button id=voltar class=sec>Ir para página principal</button>
<button class=proibido data-proibido=adicionar>Adicionar à Proposta</button>
</main>""", """
const api=(acao,extra={})=>fetch('/api/cotar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({acao,...extra})}).then(r=>r.json());
document.querySelectorAll('[data-plano]').forEach(b=>b.onclick=async()=>{
 document.querySelectorAll('[data-plano]').forEach(x=>x.classList.remove('sel')); b.classList.add('sel');
 rp.textContent=b.dataset.plano; document.getElementById('sel').textContent='Selecionado';
 await api('plano',{plano:b.dataset.plano, acomodacao:document.querySelector('[name=acomodacao]:checked').value,
  copart:document.querySelector('[name=copart]:checked').value});
});
gerar.onclick=async()=>{await api('gerar'); location='/cotar'};
voltar.onclick=async()=>{await api('lista'); location='/cotar'};
document.querySelectorAll('[data-proibido]').forEach(b=>b.onclick=()=>fetch('/api/proibido',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({qual:b.dataset.proibido})}));
""")

    if passo == "modal":
        return _pagina("Modal medicamentos", """<div class=modal><div class=box>
<h3>Aumente as chances de fechar essa proposta!</h3>
<button id=sem>Emitir Sem Medicamentos</button>
<button class=proibido data-proibido=adicionar>Adicionar à Proposta</button>
</div></div>""", """
const api=(acao,extra={})=>fetch('/api/cotar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({acao,...extra})}).then(r=>r.json());
sem.onclick=async()=>{const r=await api('emitir_sem_med'); if(r.caiu){parent.location='/login'; return;} location='/cotar'};
document.querySelectorAll('[data-proibido]').forEach(b=>b.onclick=()=>fetch('/api/proibido',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({qual:b.dataset.proibido})}));
""")

    if passo == "resultado":
        n = sess.get("atual")
        c = sim.cotacoes.get(n) or {}
        return _pagina("4 de 4 — Detalhes", f"""<main class=card>
<h2>4 de 4 — Detalhes da cotação</h2>
<p>A cotação nº {html.escape(str(n))} foi calculada com sucesso.</p>
<p>Este orçamento expira em 30 dias.</p>
<p>Razão social: {html.escape(str(c.get('razao') or ''))}</p>
<p>Valor total mensal: {reais(c.get('total') or 0)}</p>
<p>Sub-total: {reais(c.get('subtotal') or 0)}</p>
<p>Taxa de inscrição: {reais(c.get('taxa') or 0)}</p>
<p>IOF Saúde: {reais(c.get('iof') or 0)}</p>
<button id=imprimir>Imprimir cotação</button>
<button id=voltar class=sec>Ir para página principal</button>
<button class=proibido data-proibido=elaborar>Elaborar proposta</button>
<div id=erro class=erro style=display:none>Erro ao gerar PDF — Não foi possível gerar o PDF agora.
<button id=fechar>Fechar</button></div>
</main>""", """
const api=(acao,extra={})=>fetch('/api/cotar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({acao,...extra})}).then(r=>r.json());
imprimir.onclick=async()=>{const r=await api('imprimir'); if(r.erro_pdf){erro.style.display='block'; return;}
 if(r.url) window.open(r.url,'_blank');};
fechar && (fechar.onclick=()=>erro.style.display='none');
voltar.onclick=async()=>{await api('lista'); location='/cotar'};
document.querySelectorAll('[data-proibido]').forEach(b=>b.onclick=()=>fetch('/api/proibido',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({qual:b.dataset.proibido})}));
""")

    return _pagina("Cotador", "<p>passo desconhecido</p>")
