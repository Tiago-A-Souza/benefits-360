"""Simulador local do vendasmil (Amil, Cotação PME), montado a partir dos quadros do vídeo do corretor.

Só para testes e treino: login FALSO, empresas e valores de exemplo (os do vídeo, Seção 3 do mapa). Nada aqui fala com a
Amil. As telas imitam os quadros: login com código de 8 dígitos, menu lateral, Oportunidade PME (CNPJ consultado na
"Receita"), Resumo Geral da oportunidade com "Cotações da Oportunidade", Criar Cotação (Vínculo de Vendas, Selecionar Planos,
Revisar Cotação), Concluir Cotação com "Gerando PDF…" -> "PDF Gerado" e Baixar PDF.
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
from urllib.parse import parse_qs, urlparse

FAIXAS = ["Até 18", "19-23", "24-28", "29-33", "34-38", "39-43", "44-48", "49-53", "54-58", "59 ou mais"]
D = Decimal


def _d(v) -> Decimal:
    return D(v).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def reais(v) -> str:
    inteiro, dec = f"{_d(v):.2f}".split(".")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    return "R$ " + ".".join([inteiro] + grupos) + "," + dec


def _lista(*v) -> list[Decimal]:
    return [D(x) for x in v]


# Valores por vida com 4 vidas (Seção 3 do mapa). Com 2 ou 3 vidas os valores sobem ~19,5% (vídeo: Platinum até 18 =
# 540,32 com 0 vidas e 452,13 com 4; S2500 = 1.002,35 com 3 e 838,76 com 4).
PLATINUM = _lista("452.13", "528.99", "645.38", "774.45", "813.18", "894.50", "1118.13", "1229.94", "1537.43", "2690.51")
BLACK = _lista("801.42", "937.66", "1143.95", "1372.74", "1441.37", "1585.51", "1981.90", "2180.08", "2725.11", "4768.94")
S2500 = _lista("838.76", "981.35", "1197.25", "1436.71", "1508.54", "1659.40", "2074.25", "2281.68", "2852.10", "4991.18")
FATOR_POUCAS_VIDAS = D("1.19505")
DENTAL_UNITARIO = D("14.50")
DENTAL = "DENTAL BRONZE PJ PROMO"
ADITIVO = "AMIL RESGATE SAUDE I"
CORRETORES = ["30227287860 - EDLAINE ABREU SOARES", "11111111111 - CORRETOR DE TREINO UM", "22222222222 - CORRETORA DE TREINO DOIS"]


def planos_do_portal() -> dict[str, dict]:
    """A lista do <select> Plano:. Os três do vídeo têm os valores do mapa; os outros, valores derivados."""
    planos: dict[str, dict] = {}
    nomes = ["BRONZE SP COPART", "BRONZE SP COPART TP", "BRONZE SP MAIS QC COPART", "BRONZE SP MAIS QP COPART",
             "PRATA QC COPART", "PRATA QP COPART", "PRATA II QC COPART", "PRATA II QP COPART", "OURO QC R COPART",
             "OURO QP R COPART", "OURO II QP R COPART", "PLATINUM R1 COPART", "PLATINUM R1 COPART TP",
             "PLATINUM R2 COPART", "AMIL BLACK I R1 COPART", "AMIL BLACK I R2 COPART", "AMIL BLACK I R3 COPART",
             "AMIL BLACK II R1 COPART", "AMIL S2500 R1 QP COPART", "AMIL S2500 R2 QP COPART",
             "AMIL S6500 BLACK R1 QP COPART"]
    for i, nome in enumerate(nomes):
        base = {"PLATINUM R1 COPART": PLATINUM, "AMIL BLACK I R1 COPART": BLACK, "AMIL S2500 R1 QP COPART": S2500}.get(nome)
        if base is None:
            base = [_d(v * (D(1) + D(i) / D(40))) for v in PLATINUM]
        planos[nome] = {"base4": base, "selo": ("PLATINUM" in nome or "BLACK I" in nome) and "TP" not in nome,
                        "aditivo": "S2500" not in nome and "S6500" not in nome and "PRATA" not in nome}
    return planos


PLANOS = planos_do_portal()
# Receita Federal de mentira: CNPJ (só dígitos) -> (razão social, fantasia)
EMPRESAS = {
    "11222333000181": ("PADARIA MODELO DE TREINO LTDA", "PADARIA MODELO"),
    "61978595000149": ("CALANDRINI HEALTHSPAN LTDA", "CALANDRINI HEALTHSPAN"),
    "49418533000187": ("L C GASTRONOMIA LTDA", "L C GASTRONOMIA"),
}


def valores_por_vida(plano: str, total_vidas: int) -> list[Decimal]:
    base = PLANOS[plano]["base4"]
    fator = FATOR_POUCAS_VIDAS if total_vidas <= 3 else (D("0.95") if total_vidas >= 10 else D(1))
    return [_d(v * fator) for v in base]


def calcular(plano: str, vidas: list[int], dental: bool) -> dict:
    """Os totais da cotação (mesmas regras do mapa: soma = Valor Total; 50% na 1ª e 2ª; após 12 meses = total + dental)."""
    total_vidas = sum(vidas)
    valores = valores_por_vida(plano, total_vidas)
    subtotais = [_d(v * q) for v, q in zip(valores, vidas)]
    mensal = _d(sum(subtotais, D(0)))
    selo = PLANOS[plano]["selo"]
    dental_12 = _d(DENTAL_UNITARIO * total_vidas) if dental else D("0.00")
    return {"valores": valores, "subtotais": subtotais, "mensal": mensal, "selo": selo, "vidas": total_vidas,
            "total_geral": _d(mensal / 2) if selo else mensal, "dental_12": dental_12,
            "apos_12": _d(mensal + dental_12)}


def _pdf(cot: str, plano: str, texto: str) -> bytes:
    """Um PDF mínimo e válido (com o número da COT e o plano no texto), com enchimento para parecer um PDF de verdade."""
    conteudo = (f"BT /F1 14 Tf 50 780 Td ({cot} - {plano}) Tj 0 -22 Td ({texto}) Tj ET").encode("latin-1", "replace")
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


# ---------------------------------------------------------------------------------------------------------- páginas
CSS = """
body{font-family:Arial,sans-serif;margin:0;color:#1c1c3c}
.menu{position:fixed;left:0;top:0;bottom:0;width:230px;background:#1a0a5e;color:#fff;padding:12px;box-sizing:border-box}
.menu a,.menu button{display:block;color:#fff;background:none;border:0;padding:10px 4px;text-align:left;font-size:14px;cursor:pointer;text-decoration:none;width:100%}
.centro{margin-left:240px;margin-right:300px;padding:20px}
.painel{position:fixed;right:0;top:0;bottom:0;width:290px;background:#f4f4fa;padding:16px;box-sizing:border-box;font-size:13px}
.painel h4{margin:0 0 10px;background:#1a0a5e;color:#fff;padding:10px}
.card{border:1px solid #ddd;border-radius:8px;padding:16px;margin:12px 0}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:6px;text-align:center}
.roxo{background:#4a14ff;color:#fff;border:0;border-radius:6px;padding:10px 18px;font-weight:bold;cursor:pointer}
.roxo[disabled]{background:#ccc;cursor:not-allowed}
.toasts{position:fixed;top:20px;right:300px;z-index:9}
.toast{background:#e8fbee;border:1px solid #6c6;padding:10px 14px;margin-bottom:8px;width:300px}
[role=listbox]{border:1px solid #888;background:#fff;position:absolute;width:300px;z-index:5}
[role=option]{padding:8px;cursor:pointer}
.chip{background:#4a14ff;color:#fff;border-radius:4px;padding:6px 10px;margin-left:8px;font-weight:bold}
.oculto{display:none}
#grade{table-layout:fixed;font-size:11px}#grade td,#grade th{padding:2px}#grade input{width:30px}#grade button{padding:0 4px}
"""

MENU = """<nav class="menu"><div><b>amil</b> vendasmil</div>
<a href="/">Página Inicial</a><a href="/oportunidades-pme/cadastro">Criar Oportunidade PME</a>
<a href="/oportunidades-pme/cadastro?pj=1">Criar Oportunidade PJ Amil</a><a href="#">Andamentos</a><a href="#">Equipe de Vendas</a>
<button type="button" id="sair">Sair</button></nav>
<script>document.getElementById('sair').onclick=async()=>{await fetch('/api/sair',{method:'POST'});location='/login'}</script>"""


def _pagina(titulo: str, centro: str, painel: str = "", script: str = "") -> str:
    return (f"<!doctype html><html lang=pt-BR><head><meta charset=utf-8><title>{html.escape(titulo)}</title><style>{CSS}</style></head>"
            f"<body>{MENU}<main class=centro>{centro}</main><aside class=painel>{painel}</aside>"
            f"<div class=toasts id=toasts></div><script>{script}</script></body></html>")


LOGIN = """<!doctype html><html lang=pt-BR><head><meta charset=utf-8><title>vendasmil</title><style>__CSS__</style></head><body>
<main style="width:380px;margin:60px auto"><h2>Bem-vindo ao <b>vendasmil</b></h2><p>A plataforma de vendas do Grupo Amil</p>
<form id="f1"><label for="email">E-mail</label><br><input id="email" name="email" type="email" autocomplete="off" style="width:100%"><br><br>
<label for="senha">Senha</label><br><input id="senha" name="senha" type="password" autocomplete="off" style="width:100%"><br><br>
<button class="roxo" id="entrar" type="submit">Iniciar Sessão</button><p id="erro" style="color:#c00"></p></form>
<div id="f2" class="oculto"><div class="card"><b>Código de verificação enviado</b><br>Enviado para: te***@simulador.local<br>
O código expira em 15 minutos.</div><label for="codigo">Código de verificação</label><br>
<input id="codigo" placeholder="00000000" maxlength="8" autocomplete="off" style="width:100%"><br><br>
<button class="roxo" id="verificar" type="button" disabled>Verificar código</button><br><br>
<button id="reenviar" type="button">Reenviar código</button> <button id="voltar" type="button">Voltar</button>
<p id="erro2" style="color:#c00"></p></div></main>
<script>
const $=id=>document.getElementById(id);
$('f1').onsubmit=async e=>{e.preventDefault();
 const r=await (await fetch('/api/login',{method:'POST',body:JSON.stringify({email:$('email').value,senha:$('senha').value})})).json();
 if(r.etapa==='codigo'){$('f1').classList.add('oculto');$('f2').classList.remove('oculto')}
 else if(r.etapa==='ok'){location='/'} else {$('erro').textContent='Usuário ou senha inválidos.'}};
$('codigo').oninput=()=>{$('verificar').disabled=!/^\\d{8}$/.test($('codigo').value)};
$('verificar').onclick=async()=>{const r=await (await fetch('/api/codigo',{method:'POST',body:JSON.stringify({codigo:$('codigo').value})})).json();
 if(r.etapa==='ok'){location='/'} else {$('erro2').textContent='Código inválido ou expirado.'}};
$('voltar').onclick=()=>{$('f2').classList.add('oculto');$('f1').classList.remove('oculto')};
</script></body></html>""".replace("__CSS__", CSS)


class Simulador:
    # Login FALSO do simulador (nunca um login de verdade).
    USUARIO = "corretor.treino@simulador.local"
    SENHA = "Treino#Amil1"
    CODIGO = "48291637"

    def __init__(self, porta: int = 0):
        self.usuario, self.senha, self.codigo = self.USUARIO, self.SENHA, self.CODIGO
        self.sessoes: dict[str, dict] = {}            # sid -> {"logado": bool}
        self.exigir_codigo = False                    # o portal real pede o código em todo login
        self.tentativas_login = 0
        self.codigos_digitados: list[str] = []
        self.oportunidades: dict[str, dict] = {}      # id -> {"opp", "cnpj", "razao", "cotacoes": [ids]}
        self.cotacoes: dict[str, dict] = {}           # id -> {...}
        self.rascunhos: set[str] = set()
        self.proxima_opp, self.proxima_cot = 5147302, 5185118
        self.downloads = 0
        self.criar_proposta_cliques = 0               # "Criar Proposta": o robô NUNCA pode clicar
        self.incluir_plano_medico_cliques = 0         # "+ Incluir Plano Médico": o robô NUNCA pode clicar
        self.enviar_email_cliques = 0                 # "Enviar por E-mail": NUNCA
        self.saidas = 0
        self.dental_vem_marcado = True                # o portal já traz o dental em Aderir (o vídeo não mostra o clique)
        self.pdf_demora_s = 0.6                       # "Gerando PDF…"
        self.cair_depois_de_concluir = False          # conclui a cotação e derruba a sessão (teste)
        self.total_geral_errado = False               # o Total Geral da revisão não bate com o valor mensal (teste)
        self.lock = threading.Lock()
        self._srv = ThreadingHTTPServer(("127.0.0.1", porta), self._handler())
        self.url_base = f"http://127.0.0.1:{self._srv.server_address[1]}"

    # ------------------------------------------------------------------ uso nos testes
    @property
    def url_login(self) -> str:
        return self.url_base + "/login"

    @property
    def url_home(self) -> str:
        return self.url_base + "/"

    def iniciar(self) -> "Simulador":
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        return self

    def parar(self) -> None:
        self._srv.shutdown()
        self._srv.server_close()

    def expirar(self) -> None:
        with self.lock:
            self.sessoes.clear()

    @property
    def cotacoes_concluidas(self) -> list[dict]:
        return [c for c in self.cotacoes.values() if c["status"] == "Concluída"]

    # ------------------------------------------------------------------ páginas
    def _painel_cot(self, c: dict) -> str:
        o = self.oportunidades[c["opp_id"]]
        return (f"<h4>Status da Cotação<br>{c['status']}</h4>"
                + ('<button class="roxo" id="proposta" ' + ('' if c["status"] == "Concluída" else 'disabled') + '>Criar Proposta</button>')
                + f"<p><b>Nome:</b> {html.escape(o['fantasia'])}</p>"
                  f"<p>Número da Oportunidade: <a href='/oportunidades/{c['opp_id']}'>{o['opp']}</a></p>"
                  f"<p>Número da Cotação: <b>{c['cot']}</b></p><p>Data de Criação: {c['criada']}</p>"
                  f"<p>Data de Expiração: {c['expira']}</p>")

    def _painel_opp(self, o: dict) -> str:
        return ("<h4>Status da Oportunidade<br>Aberto-Ativo</h4><button class='roxo' id='criar-painel' "
                f"onclick=\"criar('{o['id']}')\">Criar Cotação</button>"
                f"<p>Nome: {html.escape(o['fantasia'])}</p><p>Número da Oportunidade: <b>{o['opp']}</b></p>"
                f"<p>Etapa: Oportunidade</p><p>Cidade/Estado: SAO PAULO/SP</p><p>Data de Criação: {o['criada']}</p>")

    def _pagina_oportunidade(self, o: dict) -> str:
        linhas = ""
        for cid in o["cotacoes"]:
            c = self.cotacoes[cid]
            linhas += (f"<tr><td>{c['cot']}</td><td>{reais(c['mensal']) if c.get('mensal') is not None else 'R$ 0,00'}</td>"
                       f"<td>{c.get('vidas_total', 0)}</td><td>{c['status']}</td>"
                       f"<td><button type='button' aria-label='Ver cotação' onclick=\"location='/cotacoes/{cid}'\">👁</button></td></tr>")
        centro = (f"<a href='/'>← Voltar</a><h2>Oportunidade PME</h2><div class=card><h3>Resumo Geral</h3>"
                  f"<p>CNPJ: {o['cnpj_fmt']}</p><p>Razão Social: {html.escape(o['razao'])}</p>"
                  f"<p>Nome Fantasia: {html.escape(o['fantasia'])}</p><p>Empresa MEI: Não</p><p>UF: SP</p></div>"
                  f"<div class=card><h3>Cotações da Oportunidade ({len(o['cotacoes'])})</h3>"
                  f"<button class='roxo' id='criar-lista' onclick=\"criar('{o['id']}')\">Criar Cotação</button>"
                  f"<table><tr><th>ID</th><th>Valor</th><th>Total de Vidas</th><th>Status</th><th>Ações</th></tr>{linhas}</table></div>")
        script = ("async function criar(id){const r=await (await fetch('/api/cotacoes/criar',{method:'POST',"
                  "body:JSON.stringify({opp:id})})).json();location='/cotacoes/'+r.id}")
        return _pagina("Oportunidade PME", centro, self._painel_opp(o), script)

    def _pagina_rascunho(self, rid: str) -> str:
        centro = """<h2>Oportunidade PME</h2><div class=card><b>Haverá Coligação?</b>
<label><input type=radio name=colig id=colig-sim> Sim</label> <label><input type=radio name=colig id=colig-nao checked> Não</label></div>
<div class=card><h3>Detalhes da Empresa</h3>
<label for=cnpj>CNPJ *</label><br><input id=cnpj placeholder="00.000.000/0000-00"><span id=consulta class=oculto> Consultando CNPJ na Receita Federal...</span><br>
<label for=fantasia>Nome Fantasia *</label><br><input id=fantasia readonly><br>
<label for=razao>Razão Social *</label><br><input id=razao readonly><br>
<label for=abertura>Data de Abertura *</label><br><input id=abertura type=date readonly><br>
<label for=natureza>Natureza Jurídica *</label><br><select id=natureza disabled><option>Selecione a natureza jurídica</option><option>206-2 - Sociedade Empresária Limitada</option></select><br>
<label for=atividade>Atividade Econômica *</label><br><select id=atividade disabled><option>Selecione a atividade econômica</option><option>8630501 - Atividade médica ambulatorial</option></select></div>
<div class=card><b>Empresa MEI? *</b> Não<h3>Endereço</h3>
<label for=cep>CEP *</label> <input id=cep readonly> <label for=numero>Número *</label> <input id=numero></div>
<button class=roxo id=concluir disabled>Concluir Oportunidade</button>"""
        script = ("const $=i=>document.getElementById(i);let ok=false;"
                  "$('cnpj').oninput=async()=>{const d=$('cnpj').value.replace(/\\D/g,'');if(d.length!==14)return;"
                  "$('consulta').classList.remove('oculto');await new Promise(r=>setTimeout(r,500));"
                  "const r=await (await fetch('/api/receita?cnpj='+d)).json();$('consulta').classList.add('oculto');"
                  "if(r.razao){$('razao').value=r.razao;$('fantasia').value=r.fantasia;$('cep').value='01227-200';"
                  "$('natureza').selectedIndex=1;$('atividade').selectedIndex=1;$('concluir').disabled=false}};"
                  f"$('concluir').onclick=async()=>{{const r=await (await fetch('/api/oportunidades/concluir',{{method:'POST',"
                  f"body:JSON.stringify({{rascunho:'{rid}',cnpj:$('cnpj').value}})}})).json();"
                  "location='/oportunidades/'+r.id+'?origem=cadastro-pme'}")
        painel = "<h4>Editando Rascunho<br>PME</h4><p>Status: Em andamento</p><p>Tipo: PME</p>"
        return _pagina("Oportunidade PME", centro, painel, script)

    def _pagina_cotacao(self, c: dict) -> str:
        etapa = c["etapa"]
        if etapa == "vinculo":
            opcoes = "".join(f"<div role=option>{html.escape(n)}</div>" for n in CORRETORES)
            centro = f"""<a href='#'>← Voltar</a><h2>Criar Cotação</h2><h3>Vínculo de Vendas</h3><p>Expira em: {c['expira']}</p>
<div class=card><label>Nome da Corretora *</label><br><input value="NEWPORT CONSULTORIA E CORRETORA DE" readonly style="width:300px"><br>
<span id=lcor>Nome do Corretor *</span><br>
<div role=combobox aria-labelledby=lcor tabindex=0 id=combo style="border:1px solid #888;padding:8px;width:300px">Selecione um corretor...</div>
<div role=listbox class=oculto id=lista><input placeholder="Digite nome ou código do corretor..." id=busca>{opcoes}</div><br>
<span id=lsup>Nome do Supervisor</span><br><div role=combobox aria-labelledby=lsup id=sup style="border:1px solid #888;padding:8px;width:300px">Selecione...</div></div>
<button class=roxo id=continuar disabled>Preencha os Campos Obrigatórios</button>"""
            script = ("const $=i=>document.getElementById(i);let escolhido=null;"
                      "$('combo').onclick=()=>{$('lista').classList.toggle('oculto');$('busca').focus()};"
                      "$('busca').oninput=()=>{const q=$('busca').value.toLowerCase();"
                      "document.querySelectorAll('#lista [role=option]').forEach(o=>o.classList.toggle('oculto',!o.textContent.toLowerCase().includes(q)))};"
                      "document.querySelectorAll('#lista [role=option]').forEach(o=>o.onclick=()=>{escolhido=o.textContent;"
                      "$('combo').textContent=o.textContent.split(' - ')[1];$('lista').classList.add('oculto');"
                      "$('continuar').disabled=false;$('continuar').textContent='Continuar'});"
                      f"$('continuar').onclick=async()=>{{await fetch('/api/cotacoes/{c['id']}/vinculo',{{method:'POST',"
                      "body:JSON.stringify({corretor:escolhido})});location.reload()}")
            return _pagina("Criar Cotação", centro, self._painel_cot(c), script)
        if etapa == "planos":
            return self._pagina_planos(c)
        return self._pagina_revisar(c)

    def _pagina_planos(self, c: dict) -> str:
        opcoes = "<option>Selecione...</option>" + "".join(f"<option>{html.escape(n)}</option>" for n in PLANOS)
        cab = "".join(f"<th>{f}</th>" for f in FAIXAS)
        qtd = "".join(f"<td><button type=button>+</button><input aria-label='Vidas {f}' value=0 data-i={i}><button type=button>−</button></td>"
                      for i, f in enumerate(FAIXAS))
        zeros = "".join("<td>R$ 0,00</td>" for _ in FAIXAS)
        centro = f"""<a href='#'>← Anterior</a><h2>Criar Cotação</h2><h3>Selecionar Planos</h3><p>Preencha a distribuição etária da empresa.</p>
<h3>Planos Médicos <span class=chip id=ctv>Total de Vidas: 0</span><span class=chip id=cvt>Valor Total: R$ 0,00</span></h3>
<div class=card><label for=plano>Plano:</label> <select id=plano>{opcoes}</select>
<button type=button id=inc-aditivo>+ Incluir Aditivo</button> <span class="chip oculto" id=selo>50% OFF 1ª e 2ª parcela</span>
<table id=grade><tr><th>Plano</th>{cab}</tr><tr><th>Qtd. Vidas</th>{qtd}</tr><tr><th>Valor por Vida</th>{zeros}</tr>
<tr><th>Subtotal</th>{zeros}</tr></table><p id=totais>Total de Vidas: 0 · Valor Total: R$ 0,00</p>
<div id=aditivo class=oculto><b>Aditivo:</b> <select><option>{ADITIVO}</option></select> Vidas: <input readonly value=0 id=advidas>
<span>Aditivo Resgate: Promocional por 12 meses</span></div></div>
<button type=button id=inc-medico>+ Incluir Plano Médico</button>
<div id=dental class=oculto><h3>Planos Dentais</h3><table><tr><th>Aderir</th><th>Plano Dental</th><th>Plano Médico</th><th>Total de Vidas</th>
<th>Período de Desconto</th></tr><tr><td><input type=checkbox aria-label="Aderir" id=aderir {'checked' if self.dental_vem_marcado else ''}></td>
<td>{DENTAL}</td><td id=dmed></td><td id=dvid>0</td><td>12 Meses</td></tr></table></div>
<br><button class=roxo id=continuar>Continuar</button>"""
        dados = json.dumps({"planos": {n: {"base4": [str(v) for v in p["base4"]], "selo": p["selo"], "aditivo": p["aditivo"]}
                                       for n, p in PLANOS.items()},
                            "fator": str(FATOR_POUCAS_VIDAS)})
        script = ("const $=i=>document.getElementById(i);const P=" + dados + ";"
                  "const fmt=v=>'R$ '+v.toFixed(2).replace('.',',').replace(/\\B(?=(\\d{3})+(?!\\d))/g,'.');"
                  "const r2=v=>Math.round(v*100+1e-9)/100;"
                  "function recalcular(){const q=[...document.querySelectorAll('#grade input')].map(i=>parseInt(i.value||'0',10)||0);"
                  "const tot=q.reduce((a,b)=>a+b,0);const pl=$('plano').value;const cels=[...document.querySelectorAll('#grade tr')];"
                  "let soma=0;if(P.planos[pl]){const f=tot<=3?parseFloat(P.fator):(tot>=10?0.95:1);"
                  "const base=P.planos[pl].base4.map(v=>r2(parseFloat(v)*f));"
                  "base.forEach((v,i)=>{cels[2].children[i+1].textContent=fmt(v);const s=r2(v*q[i]);cels[3].children[i+1].textContent=fmt(s);soma+=s});"
                  "$('selo').classList.toggle('oculto',!P.planos[pl].selo);$('aditivo').classList.toggle('oculto',!P.planos[pl].aditivo);"
                  "$('dental').classList.remove('oculto');$('dmed').textContent=pl}"
                  "else{for(let i=0;i<10;i++){cels[2].children[i+1].textContent=fmt(0);cels[3].children[i+1].textContent=fmt(0)}}"
                  "$('ctv').textContent='Total de Vidas: '+tot;$('cvt').textContent='Valor Total: '+fmt(r2(soma));"
                  "$('totais').textContent='Total de Vidas: '+tot+' · Valor Total: '+fmt(r2(soma));$('advidas').value=tot;$('dvid').textContent=tot}"
                  "document.querySelectorAll('#grade input').forEach(i=>i.oninput=recalcular);$('plano').onchange=recalcular;"
                  "document.querySelectorAll('#grade button').forEach((b,k)=>b.onclick=()=>{const i=b.parentElement.querySelector('input');"
                  "i.value=Math.max(0,(parseInt(i.value||'0',10)||0)+(b.textContent==='+'?1:-1));recalcular()});"
                  "$('inc-medico').onclick=()=>fetch('/api/proibido/incluir-plano-medico',{method:'POST'});"
                  f"$('continuar').onclick=async()=>{{await fetch('/api/cotacoes/{c['id']}/planos',{{method:'POST',body:JSON.stringify({{"
                  "plano:$('plano').value,vidas:[...document.querySelectorAll('#grade input')].map(i=>parseInt(i.value||'0',10)||0),"
                  "dental:$('aderir').checked&&!$('dental').classList.contains('oculto')})});location.reload()}")
        return _pagina("Criar Cotação", centro, self._painel_cot(c), script)

    def _pagina_revisar(self, c: dict) -> str:
        o = self.oportunidades[c["opp_id"]]
        t = dict(c["totais"])
        if self.total_geral_errado:
            t["total_geral"] = _d(t["total_geral"] + 10)
        concluida = c["status"] == "Concluída"
        selo = t["selo"]
        cab_desc = "<th>Desconto 50%<br>1ª e 2ª parcela</th>" if selo else ""
        cel_desc = (f"<td><span class=chip>Plano elegível</span> <s>{reais(t['mensal'])}</s> <b>{reais(t['total_geral'])}</b></td>"
                    if selo else "")
        tot_desc = f"<td><s>{reais(t['mensal'])}</s> <b>{reais(t['total_geral'])}</b></td>" if selo else ""
        dental = (f"<table><tr><th>Nome do Plano Dental</th><th>Quantidade de Vidas</th><th>Valor</th></tr>"
                  f"<tr><td>{DENTAL}</td><td>{t['vidas']}</td><td>R$ 0,00</td></tr><tr><td>Total</td><td>{t['vidas']}</td><td>R$ 0,00</td></tr></table>"
                  if c["dental"] else "")
        dental12 = (f"<table><tr><th>Nome do Plano Dental</th><th>Quantidade de Vidas</th><th>Valor</th></tr>"
                    f"<tr><td>{DENTAL}</td><td>{t['vidas']}</td><td>{reais(t['dental_12'])}</td></tr>"
                    f"<tr><td>Total</td><td>{t['vidas']}</td><td>{reais(t['dental_12'])}</td></tr></table>" if c["dental"] else "")
        aditivo = (f"<table><tr><th>Aditivos</th><th>Quantidade de Vidas</th><th>Valor</th></tr><tr><td>AMIL RESGATE SAÚDE I</td>"
                   f"<td>{t['vidas']}</td><td>R$ 0,00</td></tr><tr><td>Total</td><td>{t['vidas']}</td><td>R$ 0,00</td></tr></table>"
                   if PLANOS[c["plano"]]["aditivo"] else "")
        pdf = ""
        if concluida:
            pdf = (f"<div class=card id=pdfbox><b>PDF da Cotação PME</b><p>cotacao-{c['cot']}.pdf</p>"
                   "<button type=button id=email>Enviar por E-mail</button> <button type=button class=roxo id=baixar disabled>"
                   "Gerando PDF...</button></div><br><button class=roxo id=proposta2>Criar Proposta</button>")
        else:
            pdf = "<br><button class=roxo id=concluir>Concluir Cotação</button>"
        centro = f"""<a href='#'>← Anterior</a><h2>Revisar Cotação</h2><h3>Cotação</h3><h4>Resumo Geral</h4>
<p>{c['cot']}</p><p>Expira em: {c['expira']}</p>
<div class=card><table style="text-align:left"><tr><td>OPORTUNIDADE</td><td>DATA DE VALIDADE</td></tr>
<tr><td>{o['opp']} - {html.escape(o['razao'])}</td><td>{c['expira']}</td></tr>
<tr><td>DATA DE CRIAÇÃO</td><td>CORRETOR</td></tr><tr><td>{c['criada']}</td><td>{html.escape(c['corretor_nome'])}</td></tr>
<tr><td>PORTE</td><td>SUPERVISOR</td></tr><tr><td>PME I</td><td>-</td></tr>
<tr><td>TABELA</td><td>NÚMERO DE EMPRESAS COLIGADAS</td></tr><tr><td>Compulsória</td><td>0</td></tr>
<tr><td>CORRETORA</td><td>GESTOR COMERCIAL</td></tr><tr><td>NEWPORT CONSULTORIA E CORRETORA DE SEGUROS LTDA</td><td>BRUNA RAFAELA DA SILVA</td></tr>
<tr><td>COLIGADA</td><td></td></tr><tr><td>Não</td><td></td></tr></table></div>
<table><tr><th>Nome do Plano Médico</th><th>Quantidade de Vidas</th>{cab_desc}<th>Valor/mês<br>A partir 3ª parcela</th></tr>
<tr><td>{html.escape(c['plano'])}</td><td>{t['vidas']}</td>{cel_desc}<td>{reais(t['mensal'])}</td></tr>
<tr><td>Total</td><td>{t['vidas']}</td>{tot_desc}<td>{reais(t['mensal'])}</td></tr></table>
{dental}{aditivo}
<div class=card><b>Total Geral</b> <span style="float:right"><b>{reais(t['total_geral'])}</b></span>
<p>O desconto de 50% é aplicado somente nas 2 (duas) primeiras mensalidades dos planos elegíveis.</p></div>
<div class=card><b>Total Geral após 12 Meses</b> <span style="float:right"><b>{reais(t['apos_12'])}*</b></span>
<p>*Nesse valor não está calculado o reajuste a ser aplicado após os 12 meses de contrato.</p>{dental12}</div>{pdf}"""
        script = ("const $=i=>document.getElementById(i);"
                  "function toast(t,s){const d=document.createElement('div');d.className='toast';d.setAttribute('role','alert');"
                  "d.innerHTML='<b>'+t+'</b><br>'+s+' <button type=button aria-label=Fechar>×</button>';"
                  "d.querySelector('button').onclick=()=>d.remove();$('toasts').appendChild(d)}"
                  "function ligarPdf(espera){setTimeout(()=>{const b=$('baixar');if(!b)return;b.disabled=false;b.textContent='Baixar PDF';"
                  f"toast('PDF Gerado','PDF da cotação está disponível para download.');b.onclick=()=>{{location='/api/cotacoes/{c['id']}/pdf'}}}},espera)}}"
                  "if($('proposta2'))$('proposta2').onclick=()=>fetch('/api/proibido/criar-proposta',{method:'POST'});"
                  "if($('email'))$('email').onclick=()=>fetch('/api/proibido/enviar-email',{method:'POST'});"
                  f"if($('concluir'))$('concluir').onclick=async()=>{{await fetch('/api/cotacoes/{c['id']}/concluir',{{method:'POST'}});"
                  "location.reload()};"
                  + (f"ligarPdf({int(max(0.0, c.get('pdf_pronto_em', 0) - time.time()) * 1000)});"
                     "toast('Cotação concluída com sucesso!','Agora você pode criar uma proposta.');" if concluida else ""))
        return _pagina("Revisar Cotação", centro, self._painel_cot(c), script)

    # ------------------------------------------------------------------ servidor
    def _logado(self, h) -> bool:
        sid = h.sid()
        return bool(sid and self.sessoes.get(sid, {}).get("logado"))

    def _handler(self):
        sim = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silêncio
                pass

            def sid(self):
                c = SimpleCookie(self.headers.get("Cookie", ""))
                return c["amil_sid"].value if "amil_sid" in c else None

            def _enviar(self, corpo, tipo="text/html; charset=utf-8", status=200, extra=None):
                dados = corpo if isinstance(corpo, bytes) else corpo.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(dados)))
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(dados)

            def _json(self, obj, status=200):
                self._enviar(json.dumps(obj), "application/json", status)

            def _redir(self, destino):
                self.send_response(302)
                self.send_header("Location", destino)
                self.end_headers()

            def _corpo(self) -> dict:
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    return json.loads(self.rfile.read(n) or b"{}")
                except ValueError:
                    return {}

            def do_GET(self):
                u = urlparse(self.path)
                rota, q = u.path, parse_qs(u.query)
                with sim.lock:
                    if rota == "/login":
                        if sim._logado(self):
                            return self._redir("/")
                        sid = self.sid() or secrets.token_hex(8)
                        sim.sessoes.setdefault(sid, {"logado": False})
                        return self._enviar(LOGIN, extra={"Set-Cookie": f"amil_sid={sid}; Path=/; Max-Age=86400"})
                    if not sim._logado(self):
                        return self._redir("/login")
                    if rota == "/":
                        return self._enviar(_pagina("Página Inicial", "<h2>Minhas Pendências PME</h2><p>Nenhuma pendência</p>"))
                    if rota == "/oportunidades-pme/cadastro":
                        rid = (q.get("id") or [""])[0]
                        if not rid:
                            rid = secrets.token_hex(12)
                            sim.rascunhos.add(rid)
                            return self._redir(f"/oportunidades-pme/cadastro?id={rid}")
                        return self._enviar(sim._pagina_rascunho(rid))
                    if rota.startswith("/oportunidades/"):
                        o = sim.oportunidades.get(rota.split("/")[2])
                        return self._enviar(sim._pagina_oportunidade(o)) if o else self._enviar("não encontrada", status=404)
                    if rota.startswith("/cotacoes/"):
                        c = sim.cotacoes.get(rota.split("/")[2])
                        return self._enviar(sim._pagina_cotacao(c)) if c else self._enviar("não encontrada", status=404)
                    if rota == "/api/receita":
                        d = (q.get("cnpj") or [""])[0]
                        r = EMPRESAS.get(d)
                        return self._json({"razao": r[0], "fantasia": r[1]} if r else {})
                    if rota.startswith("/api/cotacoes/") and rota.endswith("/pdf"):
                        c = sim.cotacoes.get(rota.split("/")[3])
                        if not c or c["status"] != "Concluída" or time.time() < c.get("pdf_pronto_em", 0):
                            return self._enviar("PDF ainda não gerado", status=409)
                        sim.downloads += 1
                        corpo = _pdf(c["cot"], c["plano"], f"valor mensal {reais(c['totais']['mensal'])}")
                        return self._enviar(corpo, "application/pdf",
                                            extra={"Content-Disposition": f'attachment; filename="cotacao-{c["cot"]}.pdf"'})
                self._enviar("não encontrado", status=404)

            def do_POST(self):
                rota, corpo = urlparse(self.path).path, self._corpo()
                with sim.lock:
                    if rota == "/api/login":
                        sim.tentativas_login += 1
                        sid = self.sid() or secrets.token_hex(8)
                        ok = corpo.get("email") == sim.usuario and corpo.get("senha") == sim.senha
                        if not ok:
                            return self._enviar(json.dumps({"etapa": "erro"}), "application/json",
                                                extra={"Set-Cookie": f"amil_sid={sid}; Path=/; Max-Age=86400"})
                        sim.sessoes[sid] = {"logado": not sim.exigir_codigo, "pendente": sim.exigir_codigo}
                        return self._enviar(json.dumps({"etapa": "codigo" if sim.exigir_codigo else "ok"}), "application/json",
                                            extra={"Set-Cookie": f"amil_sid={sid}; Path=/; Max-Age=86400"})
                    if rota == "/api/codigo":
                        sid = self.sid()
                        sim.codigos_digitados.append(str(corpo.get("codigo")))
                        if sid in sim.sessoes and sim.sessoes[sid].get("pendente") and corpo.get("codigo") == sim.codigo:
                            sim.sessoes[sid] = {"logado": True}
                            return self._json({"etapa": "ok"})
                        return self._json({"etapa": "erro"})
                    if rota == "/api/sair":
                        sim.saidas += 1
                        sim.sessoes.pop(self.sid(), None)
                        return self._json({"ok": True})
                    if not sim._logado(self):
                        return self._json({"erro": "sessão"}, 401)
                    if rota.startswith("/api/proibido/"):
                        chave = rota.rsplit("/", 1)[1]
                        if chave == "criar-proposta":
                            sim.criar_proposta_cliques += 1
                        elif chave == "incluir-plano-medico":
                            sim.incluir_plano_medico_cliques += 1
                        elif chave == "enviar-email":
                            sim.enviar_email_cliques += 1
                        return self._json({"ok": True})
                    if rota == "/api/oportunidades/concluir":
                        cnpj = "".join(ch for ch in str(corpo.get("cnpj")) if ch.isdigit())
                        emp = EMPRESAS.get(cnpj)
                        if not emp:
                            return self._json({"erro": "CNPJ"}, 400)
                        oid = secrets.token_hex(12)
                        sim.oportunidades[oid] = {"id": oid, "opp": f"OPP-{sim.proxima_opp}", "cnpj": cnpj,
                                                  "cnpj_fmt": f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}",
                                                  "razao": emp[0], "fantasia": emp[1], "cotacoes": [],
                                                  "criada": time.strftime("%d/%m/%Y, %H:%M")}
                        sim.proxima_opp += 1
                        return self._json({"id": oid})
                    if rota == "/api/cotacoes/criar":
                        o = sim.oportunidades.get(corpo.get("opp"))
                        if not o:
                            return self._json({"erro": "oportunidade"}, 404)
                        cid = secrets.token_hex(12)
                        agora = time.strftime("%d/%m/%Y, %H:%M")
                        sim.cotacoes[cid] = {"id": cid, "cot": f"COT-{sim.proxima_cot}", "opp_id": o["id"], "status": "Em Digitação",
                                             "etapa": "vinculo", "criada": agora, "expira": agora, "plano": None, "dental": False,
                                             "corretor_nome": "", "vidas_total": 0, "mensal": None}
                        sim.proxima_cot += 7
                        o["cotacoes"].append(cid)
                        return self._json({"id": cid})
                    if rota.startswith("/api/cotacoes/"):
                        _, _, _, cid, acao = rota.split("/")
                        c = sim.cotacoes.get(cid)
                        if not c:
                            return self._json({"erro": "cotação"}, 404)
                        if acao == "vinculo":
                            c["corretor_nome"] = str(corpo.get("corretor") or "").split(" - ")[-1]
                            c["etapa"] = "planos"
                        elif acao == "planos":
                            vidas = [int(v) for v in corpo.get("vidas") or []]
                            c.update(plano=corpo.get("plano"), vidas=vidas, dental=bool(corpo.get("dental")), etapa="revisar")
                            c["totais"] = calcular(c["plano"], vidas, c["dental"])
                            c["vidas_total"], c["mensal"] = sum(vidas), c["totais"]["mensal"]
                        elif acao == "concluir":
                            c["status"] = "Concluída"
                            c["pdf_pronto_em"] = time.time() + sim.pdf_demora_s
                            if sim.cair_depois_de_concluir:
                                sim.sessoes.clear()
                        return self._json({"ok": True})
                self._json({"erro": "rota"}, 404)

        return H
