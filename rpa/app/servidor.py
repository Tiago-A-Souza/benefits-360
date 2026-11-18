"""Servidor local da tela (Starlette). Só aceita conexões da própria máquina (127.0.0.1)."""
from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

import operadoras
from nucleo import configuracao as cfgrobo
from nucleo import credenciais
from nucleo.estado import Estado
from nucleo.registro import carregar_config, mesclar, migrar_legado, pasta_saida, retencao_dias
from nucleo.retencao import limpar as limpar_vencidos
from nucleo.saidas import nome_pdf_destino
from nucleo.texto import formatar_cnpj, nome_arquivo_seguro, so_digitos

from .banco import Banco
from .codigo import VersaoDoCodigo
from .eventos import Barramento
from .trabalhador import Trabalhador

WEB = Path(__file__).parent / "web"


class _ArquivosSemCache(StaticFiles):
    """Os arquivos da tela (JS, CSS) sempre conferidos com o servidor. 05/11: sem isso o Chrome guardava o
    JavaScript antigo (até depois do F5) e a Nova cotação mandava a coparticipação da cotação anterior."""

    async def get_response(self, path, scope):
        resposta = await super().get_response(path, scope)
        resposta.headers["Cache-Control"] = "no-cache"
        return resposta

# Ajustes gerais que a tela pode gravar. Os de cada operadora são os campos de Operadora.configuracao().
AJUSTAVEIS_GERAL = {"mapear", "modo_visual"}


def _serial(valor):
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


class Tela:
    def __init__(self, caminho_config: str | Path, porta: int):
        self.caminho_config = Path(caminho_config).resolve()
        self.porta = porta
        base = carregar_config(self.caminho_config)
        migrar_legado(base)
        self.pasta = pasta_saida(base)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.arquivo_ajustes = self.pasta / "config_tela.json"
        self.versao = str(time.time_ns())   # muda a cada vez que a tela é aberta: a página recarrega sozinha
        self.codigo = VersaoDoCodigo()      # o commit que está rodando, e se o disco ficou mais novo (reiniciar)
        self._falhas_operadora: dict[str, dict] = {}   # operadora que deu erro ao montar o formulário
        self.banco = Banco(self.pasta / "tela.db")
        self.bus = Barramento()
        self.robo = Trabalhador(self.config_total, self.banco, self.bus)
        self.dias_retencao = retencao_dias(base)
        limpar_vencidos(self.pasta, self.dias_retencao)
        self.banco.limpar_eventos(self.dias_retencao)

    # ------------------------------------------------------------------ configuração
    def ajustes(self) -> dict:
        try:
            return json.loads(self.arquivo_ajustes.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return {}

    def config_total(self) -> dict:
        return carregar_config(self.caminho_config, self.ajustes())

    def _op_cfg(self, op_id: str):
        op = operadoras.obter(op_id)
        return op, op.config(self.config_total())

    # ------------------------------------------------------------------ rotas
    async def inicio(self, request: Request):
        """A página com a versão do servidor no endereço de cada arquivo: tela atualizada = arquivos novos."""
        html = (WEB / "index.html").read_text(encoding="utf-8")
        html = re.sub(r'((?:src|href)="/static/[^"?]+)"', rf'\1?v={self.versao}"', html)
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    async def estado(self, request: Request):
        total = self.config_total()
        return JSONResponse({
            "robo": self.robo.situacao(),
            "versao": self.versao,
            "codigo": await asyncio.to_thread(self.codigo.situacao),
            # Operadoras que não carregaram (ou que quebraram ao montar o formulário): a tela mostra "indisponível".
            "operadoras_indisponiveis": operadoras.indisponiveis(total) + list(self._falhas_operadora.values()),
            "simulador": bool((total.get("teste") or {}).get("simulador")),
            "pasta_saida": str(self.pasta),
            "retencao_dias": self.dias_retencao,
        })

    async def lista_operadoras(self, request: Request):
        total = self.config_total()
        saida = []
        for op in operadoras.ativas(total):
            try:
                saida.append(self._formulario(op, total))
                self._falhas_operadora.pop(op.id, None)
            except Exception as e:  # noqa: BLE001  (uma operadora com defeito não derruba a tela)
                motivo = credenciais.ocultar((f"{type(e).__name__}: {e}".splitlines() or [""])[0][:300])
                self._falhas_operadora[op.id] = {"id": op.id, "nome": op.nome, "motivo": motivo}
        return JSONResponse(saida)

    def _formulario(self, op, total: dict) -> dict:
        """O que a tela precisa de uma operadora: formulário, planos, etapas e situação do login."""
        if True:
            cfg = op.config(total)
            conhecidos = {(p["nome"], p["acomodacao"]) for p in op.planos_conhecidos()}
            vistos = {(p["nome"], p["acomodacao"]) for p in self.banco.catalogo(op.id)}
            planos = [{"nome": n, "acomodacao": a, "visto_no_portal": (n, a) in vistos}
                      for n, a in sorted(conhecidos | vistos)]
            return {
                "id": op.id, "nome": op.nome, "produto": op.produto, "cor": op.cor,
                "marcada": bool(op.marcada_na_nova_cotacao(cfg)),   # começa marcada na Nova cotação
                "min_vidas": op.min_vidas, "max_vidas": op.max_vidas,
                "faixas_idade_exata": list(cfg.get("faixas_idade_exata") or op.faixas_idade_exata),
                "etapas": [{"id": i, "nome": n} for i, n in op.etapas],
                "campos": op.campos(cfg), "planos": planos,
                "versoes": op.rotulos_versao(),     # versões da cotação de um mesmo plano: {código: texto}
                "textos": op.textos_tela(),         # textos da operadora na tela (Ajuda, Nova cotação...)
                "menor_preco_padrao": int((cfg.get("criterio_plano") or {}).get("quantidade", 1)),
                "planos_modo_padrao": (cfg.get("padroes") or {}).get("planos_modo", "lista"),
                "produto_portal": (cfg.get("padroes") or {}).get("produto", ""),
                "planos_padrao": list((cfg.get("padroes") or {}).get("planos") or []),
                "conexao": self.robo.conexao.get(op.id, "desconectado"),
                "login": {k: v for k, v in credenciais.cofre(cfg, op.id).situacao().items()
                          if k in ("guardadas", "recusadas")},
            }

    def _validar_itens(self, itens: list[dict]) -> tuple[list[dict], dict, int]:
        """Valida cada pedido de cada operadora. Devolve (itens normalizados, problemas, total de cotações)."""
        total = self.config_total()
        problemas: dict[str, list[str]] = {}
        normalizados, n_cot = [], 0
        for item in itens:
            try:
                op = operadoras.obter(item["operadora"])
            except KeyError as e:          # operadora indisponível (o módulo não carregou) ou desconhecida
                problemas[str(item.get("operadora"))] = [str(e)]
                continue
            cfg = op.config(total)
            pedidos_ok = []
            for i, dados in enumerate(item.get("pedidos") or []):
                try:
                    pedido = op.montar_pedido(dados, cfg, linha=i + 1)
                    n_cot += op.qtd_cotacoes(pedido)
                    pedidos_ok.append(dados)
                except ValueError as e:
                    rotulo = f"{op.nome} — {dados.get('id') or formatar_cnpj(str(dados.get('cnpj', '')))}"
                    problemas[rotulo] = list(getattr(e, "problemas", [str(e)]))
            normalizados.append({"operadora": op.id, "pedidos": pedidos_ok})
        return normalizados, problemas, n_cot

    def _ja_emitidas(self, itens: list[dict]) -> list[dict]:
        """Cotações do pedido que o registro anti-reemissão já tem como emitidas: o robô vai pular, então a
        tela avisa antes de gerar (05/11: o mesmo pedido de ontem parecia "travado" na tela de módulos)."""
        total = self.config_total()
        saida = []
        for item in itens:
            op = operadoras.obter(item["operadora"])
            cfg = op.config(total)
            estado = Estado(Path(cfg["saida"]["pasta"]) / "estado.json")
            for i, dados in enumerate(item.get("pedidos") or []):
                try:
                    pedido = op.montar_pedido(dados, cfg, linha=i + 1)
                except ValueError:
                    continue
                # versões da cotação de um mesmo plano (a operadora define; ex.: com e sem coparticipação)
                cotacoes = [(versao, texto, alvo) for versao, texto in op.versoes(pedido)
                            for alvo in getattr(pedido, "planos", None) or []]
                for versao, texto, alvo in cotacoes:
                    achado = estado.procurar(versao, alvo)
                    if achado and achado[1].get("status") == "pdf_ok":
                        reg = achado[1]
                        saida.append({"plano": f"{reg.get('plano')} | {reg.get('acomodacao')}" + (f" | {texto}" if texto else ""),
                                      "protocolo": reg.get("protocolo", ""), "quando": reg.get("atualizado_em", ""),
                                      "cnpj": pedido.cnpj})
        return saida

    async def validar(self, request: Request):
        corpo = await request.json()
        itens = self._so_configuracao(corpo.get("itens") or [])
        _, problemas, n = self._validar_itens(itens)
        return JSONResponse({"ok": not problemas, "problemas": problemas, "cotacoes": n,
                             "ja_emitidas": [] if problemas else self._ja_emitidas(itens)})

    @staticmethod
    def _so_configuracao(itens: list[dict]) -> list[dict]:
        """Tira dos pedidos da tela os campos que só valem da configuração do robô (ex.: vendedor)."""
        saida = []
        for item in itens:
            fora = set(operadoras.obter(item["operadora"]).campos_so_configuracao)
            saida.append({**item, "pedidos": [{k: v for k, v in d.items() if k not in fora}
                                              for d in item.get("pedidos") or []]})
        return saida

    def _enfileirar_cotacao(self, modo: str, itens_brutos: list[dict], reemitir: list[str] | None = None) -> JSONResponse:
        itens, problemas, n_cot = self._validar_itens(self._so_configuracao(itens_brutos))
        if problemas:
            return JSONResponse({"erro": "há pedidos com problema", "problemas": problemas}, status_code=400)
        pedidos = [d for it in itens for d in it["pedidos"]]
        if not pedidos:
            return JSONResponse({"erro": "nenhum pedido para cotar"}, status_code=400)
        sem_login = self._sem_login([it["operadora"] for it in itens if it["pedidos"]])
        if sem_login:
            return sem_login
        for d in pedidos:
            self.banco.salvar_empresa(so_digitos(d.get("cnpj")), str(d.get("apelido") or ""), d)
        primeiro = pedidos[0]
        pid = str(primeiro.get("id") or "")
        nome = (str(primeiro.get("apelido") or "")
                or (pid if pid and not re.fullmatch(r"L\d+", pid) and so_digitos(pid) != so_digitos(primeiro.get("cnpj")) else "")
                or (self.banco.empresa(so_digitos(primeiro.get("cnpj"))) or {}).get("razao_social")
                or formatar_cnpj(so_digitos(primeiro.get("cnpj"))))
        titulo = nome if len(pedidos) == 1 else f"{nome} e mais {len(pedidos) - 1}"
        # "Emitir de novo mesmo assim": só os protocolos que o registro tem como concluídos para ESTES pedidos.
        # Não vai para os itens guardados: "Tentar de novo" (repetir) nunca reemite.
        if reemitir:
            conhecidos = {j["protocolo"] for j in self._ja_emitidas(itens) if j.get("protocolo")}
            reemitir = sorted(set(reemitir) & conhecidos)
        tid = self.banco.novo_trabalho("cotar", modo, titulo, len(pedidos), n_cot, itens)
        if reemitir:
            self.banco.evento(tid, "reemissao", "O corretor pediu para emitir de novo (protocolo novo no portal): "
                              + ", ".join(reemitir), {"protocolos": reemitir})
        self.robo.enfileirar({"id": tid, "tipo": "cotar", "modo": modo, "titulo": titulo, "itens": itens,
                              "reemitir": reemitir or []})
        return JSONResponse({"id": tid, "cotacoes": n_cot, "reemitir": reemitir or []})

    async def criar_trabalho(self, request: Request):
        corpo = await request.json()
        modo = corpo.get("modo")
        if modo not in ("ensaio", "emitir"):
            return JSONResponse({"erro": "modo inválido"}, status_code=400)
        if modo == "emitir" and corpo.get("confirmado") is not True:
            return JSONResponse({"erro": "a emissão precisa ser confirmada"}, status_code=400)
        reemitir = corpo.get("reemitir") or []
        if reemitir:
            if modo != "emitir":
                return JSONResponse({"erro": "emitir de novo só vale para emissão"}, status_code=400)
            # protocolo = só dígitos (SulAmérica, Bradesco) ou com prefixo e hífen (Amil: "COT-5291608")
            if not isinstance(reemitir, list) or not all(isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,39}", x)
                                                         for x in reemitir):
                return JSONResponse({"erro": "protocolos inválidos"}, status_code=400)
        return self._enfileirar_cotacao(modo, corpo.get("itens") or [], reemitir=reemitir)

    async def repetir(self, request: Request):
        """Pede de novo os mesmos pedidos de um trabalho (ex.: depois do ensaio, gerar de verdade).
        O registro de cada operadora continua impedindo que uma cotação já emitida saia de novo."""
        t = self.banco.trabalho(int(request.path_params["tid"]))
        if not t or t["tipo"] != "cotar" or not t.get("itens"):
            return JSONResponse({"erro": "não há pedidos guardados para este trabalho"}, status_code=404)
        corpo = await request.json()
        modo = corpo.get("modo")
        if modo not in ("ensaio", "emitir"):
            return JSONResponse({"erro": "modo inválido"}, status_code=400)
        if modo == "emitir" and corpo.get("confirmado") is not True:
            return JSONResponse({"erro": "a emissão precisa ser confirmada"}, status_code=400)
        return self._enfileirar_cotacao(modo, t["itens"])

    async def sair_do_portal(self, request: Request):
        """"Sair do portal agora": logout e fecha a janela, para o corretor usar o portal no navegador dele.
        Só com o robô parado; na próxima cotação o robô entra sozinho de novo."""
        op = operadoras.obter(request.path_params["op"])
        r = self.robo.pedir_saida(op.id)
        if r == "ocupado":
            return JSONResponse({"erro": "O robô está trabalhando. Dá para sair do portal quando ele parar."},
                                status_code=409)
        return JSONResponse({"ok": True, "ja_fora": r == "fora"})

    async def conectar(self, request: Request):
        op_id = request.path_params["op"]
        op = operadoras.obter(op_id)
        atual = self.robo.situacao()["atual"]
        if atual and atual.get("tipo") == "conectar":
            return JSONResponse({"id": atual["id"]})
        sem_login = self._sem_login([op.id])
        if sem_login:
            return sem_login
        tid = self.banco.novo_trabalho("conectar", "ensaio", f"Testar login na {op.nome}", 0, 0)
        self.robo.enfileirar({"id": tid, "tipo": "conectar", "modo": "ensaio", "operadora": op_id,
                              "titulo": f"Testar login na {op.nome}"})
        return JSONResponse({"id": tid})

    # ------------------------------------------------------------------ login do portal (cofre do Windows)
    def _cofre(self, op_id: str):
        op = operadoras.obter(op_id)
        return op, credenciais.cofre(op.config(self.config_total()), op.id)

    def _sem_login(self, op_ids: list[str]) -> JSONResponse | None:
        """Sem login guardado (ou recusado pelo portal) o robô nem abre o portal: a tela leva à engrenagem."""
        for op_id in dict.fromkeys(op_ids):
            op, cofre = self._cofre(op_id)
            sit = cofre.situacao()
            if not sit["guardadas"] or sit["recusadas"]:
                motivo = "recusadas" if sit["guardadas"] else "sem_credenciais"
                return JSONResponse({"erro": credenciais.mensagem_login(motivo, op.nome), "motivo": motivo,
                                     "operadora": op.id}, status_code=409)
        return None

    async def ler_credenciais(self, request: Request):
        """Só a situação: {guardadas, quando, recusadas} e os campos que a operadora mostra mascarados (ex.:
        email_mascarado). Nunca um valor de login inteiro."""
        _, cofre = self._cofre(request.path_params["op"])
        return JSONResponse(cofre.situacao())

    async def guardar_credenciais(self, request: Request):
        """Só escrita. Senha vazia mantém a guardada. Erros nunca repetem o que foi digitado."""
        op, cofre = self._cofre(request.path_params["op"])
        campo = next((c for t in op.configuracao(op.config(self.config_total())) for c in t.get("campos", [])
                      if c.get("tipo") == "credenciais"), {})
        try:
            corpo = await request.json()
        except ValueError:
            corpo = None
        if not isinstance(corpo, dict):
            return JSONResponse({"erro": "pedido inválido"}, status_code=400)
        try:
            # só os campos que a operadora declarou (o resto do corpo é ignorado)
            cofre.guardar(**{c["chave"]: str(corpo.get(c["chave"]) or "") for c in cofre.campos},
                          senha_max=campo.get("senha_max"))
        except credenciais.ErroCredencial as e:
            return JSONResponse({"erro": str(e), "problemas": e.problemas}, status_code=400)
        except Exception:  # noqa: BLE001  (a exceção do cofre não volta para a tela)
            return JSONResponse({"erro": "não consegui gravar no cofre do Windows"}, status_code=500)
        return JSONResponse({"ok": True, **cofre.situacao()})

    async def apagar_credenciais(self, request: Request):
        _, cofre = self._cofre(request.path_params["op"])
        cofre.apagar()
        return JSONResponse({"ok": True, **cofre.situacao()})

    async def receber_codigo(self, request: Request):
        """Código de verificação que o portal mandou ao corretor: vai direto para o robô, sem ser guardado."""
        op = operadoras.obter(request.path_params["op"])
        try:
            corpo = await request.json()
        except ValueError:
            corpo = {}
        codigo = re.sub(r"\s", "", str((corpo or {}).get("codigo") or ""))
        if not re.fullmatch(r"[A-Za-z0-9]{4,12}", codigo):
            return JSONResponse({"erro": "Digite o código como chegou (só letras e números)."}, status_code=400)
        if not self.robo.receber_codigo(op.id, codigo):
            return JSONResponse({"erro": "O robô não está esperando um código agora."}, status_code=409)
        return JSONResponse({"ok": True})

    async def parar(self, request: Request):
        ok = self.robo.cancelar(int(request.path_params["tid"]))
        return JSONResponse({"ok": ok})

    async def trabalhos(self, request: Request):
        return JSONResponse(self.banco.trabalhos(int(request.query_params.get("limite", 20))))

    def _com_pdf(self, linhas: list[dict]) -> list[dict]:
        """Completa as linhas para a tela: se o PDF ainda existe e a razão social (as linhas de
        "já emitida antes" são registradas antes de o robô ler o nome da empresa no portal)."""
        nomes: dict[str, str] = {}
        for c in linhas:
            c["tem_pdf"] = self._arquivo_da_cotacao(c)[0] is not None
            if not c.get("razao_social"):
                if c["cnpj"] not in nomes:
                    nomes[c["cnpj"]] = (self.banco.empresa(c["cnpj"]) or {}).get("razao_social") or ""
                c["razao_social"] = nomes[c["cnpj"]]
        return linhas

    async def trabalho(self, request: Request):
        tid = int(request.path_params["tid"])
        t = self.banco.trabalho(tid)
        if not t:
            return JSONResponse({"erro": "não encontrado"}, status_code=404)
        t["operadoras"] = sorted({it.get("operadora") for it in t.pop("itens", []) if it.get("operadora")})
        t["eventos"] = self.banco.eventos(tid)
        t["cotacoes"] = self._com_pdf(self.banco.cotacoes(trabalho=tid))
        t["parando"] = tid in set(self.robo.ids_parando())
        return JSONResponse(t)

    async def cotacoes(self, request: Request):
        q = request.query_params
        limite = min(int(q.get("limite") or 300), 1000)
        return JSONResponse(self._com_pdf(self.banco.cotacoes(q.get("busca", ""), q.get("status", ""),
                                                              int(q["trabalho"]) if q.get("trabalho") else None,
                                                              limite)))

    def _arquivo_da_cotacao(self, c: dict | None) -> tuple[Path | None, str]:
        """PDF guardado pelo robô (só dentro da pasta de saída) e o nome com que o corretor o recebe."""
        if not c or not c.get("pdf_arquivo"):
            return None, ""
        arquivo = Path(c["pdf_arquivo"]).resolve()
        try:
            arquivo.relative_to(self.pasta.resolve())
        except ValueError:
            return None, ""
        if c.get("pdf_nome"):
            nome = c["pdf_nome"]
        elif c.get("pdf_destino"):
            nome = Path(c["pdf_destino"]).name
        else:
            op = operadoras.obter(c["operadora"])
            nome = nome_pdf_destino(op.config(self.config_total()), c["cnpj"], c.get("protocolo") or "", c["plano"])
        return (arquivo if arquivo.exists() else None), nome

    async def baixar_pdf(self, request: Request):
        arquivo, nome = self._arquivo_da_cotacao(self.banco.cotacao(int(request.path_params["cid"])))
        if not arquivo:
            return JSONResponse({"erro": "PDF não encontrado"}, status_code=404)
        return FileResponse(arquivo, media_type="application/pdf", filename=nome)

    async def baixar_zip(self, request: Request):
        """Vários PDFs de uma vez (todos de um trabalho, ou os escolhidos na lista) num .zip.
        Com mais de uma empresa, cada uma vai numa pasta com o nome dela."""
        q = request.query_params
        if q.get("trabalho"):
            linhas = self.banco.cotacoes(trabalho=int(q["trabalho"]))
        else:
            ids = [int(x) for x in q.get("ids", "").split(",") if x.strip().isdigit()]
            linhas = [c for c in (self.banco.cotacao(i) for i in ids) if c]
        achados = [(c, *self._arquivo_da_cotacao(c)) for c in linhas]
        achados = [(c, arq, nome) for c, arq, nome in achados if arq]
        if not achados:
            return JSONResponse({"erro": "nenhum PDF para baixar"}, status_code=404)
        empresas = {c["cnpj"] for c, _, _ in achados}
        usados: set[str] = set()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for c, arq, nome in achados:
                pasta = ""
                if len(empresas) > 1:
                    pasta = nome_arquivo_seguro(c.get("razao_social") or formatar_cnpj(c["cnpj"])) + "/"
                base, ext = os.path.splitext(nome)
                caminho, n = pasta + nome, 2
                while caminho.lower() in usados:
                    caminho, n = f"{pasta}{base} ({n}){ext}", n + 1
                usados.add(caminho.lower())
                z.write(arq, caminho)
        primeiro = achados[0][0]
        rotulo = (primeiro.get("razao_social") or formatar_cnpj(primeiro["cnpj"])) if len(empresas) == 1 else "varias empresas"
        nome_zip = nome_arquivo_seguro(f"Cotacoes {rotulo} {datetime.now():%Y-%m-%d}.zip")
        ascii_ = nome_zip.encode("ascii", "ignore").decode() or "cotacoes.zip"
        return Response(buf.getvalue(), media_type="application/zip", headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nome_zip)}"})

    async def abrir_pasta(self, request: Request):
        c = self.banco.cotacao(int(request.path_params["cid"])) or {}
        alvo = c.get("pdf_destino") or c.get("pdf_arquivo")
        if not alvo or not Path(alvo).exists():
            return JSONResponse({"erro": "arquivo não encontrado"}, status_code=404)
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", "/select,", str(Path(alvo))])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(alvo)])
            else:
                subprocess.Popen(["xdg-open", str(Path(alvo).parent)])
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"erro": f"não consegui abrir a pasta ({e})"}, status_code=500)
        return JSONResponse({"ok": True})

    async def empresas(self, request: Request):
        return JSONResponse(self.banco.empresas(request.query_params.get("busca", "")))

    async def empresa(self, request: Request):
        # Empresa nunca cotada responde vazio (não é erro: a tela pergunta a cada CNPJ digitado).
        return JSONResponse(self.banco.empresa(so_digitos(request.path_params["cnpj"])) or {})

    async def pendencias(self, request: Request):
        total = self.config_total()
        saida = []
        for op in operadoras.ativas(total):
            estado = Estado(Path(op.config(total)["saida"]["pasta"]) / "estado.json")
            for chave, item in estado.pendencias():
                empresa = self.banco.empresa(so_digitos(item.get("cnpj"))) or {}
                saida.append({"operadora": op.id, "operadora_nome": op.nome, "chave": chave,
                              "razao_social": empresa.get("razao_social") or empresa.get("apelido") or "", **{
                    k: item.get(k) for k in ("status", "protocolo", "plano", "acomodacao", "cnpj", "pedido_id",
                                             "atualizado_em")}})
        return JSONResponse(saida)

    async def liberar(self, request: Request):
        corpo = await request.json()
        op, cfg = self._op_cfg(corpo["operadora"])
        if not self.robo.registro_livre(op.id, cfg["saida"]["pasta"]):
            return JSONResponse({"erro": "espere o robô terminar o trabalho atual"}, status_code=409)
        ok = Estado(Path(cfg["saida"]["pasta"]) / "estado.json").liberar(corpo["chave"])
        return JSONResponse({"ok": ok}, status_code=200 if ok else 404)

    async def concluir(self, request: Request):
        """Pendência resolvida à mão no portal: marca como concluída (continua bloqueando reemissão)."""
        corpo = await request.json()
        op, cfg = self._op_cfg(corpo["operadora"])
        if not self.robo.registro_livre(op.id, cfg["saida"]["pasta"]):
            return JSONResponse({"erro": "espere o robô terminar o trabalho atual"}, status_code=409)
        ok = Estado(Path(cfg["saida"]["pasta"]) / "estado.json").concluir_manual(
            corpo["chave"], "resolvido à mão pelo corretor no portal (tela)")
        return JSONResponse({"ok": ok}, status_code=200 if ok else 404)

    # ------------------------------------------------------------------ configuração do robô
    def _salvar_ajustes(self, ajustes: dict) -> None:
        tmp = self.arquivo_ajustes.with_name(self.arquivo_ajustes.name + ".tmp")
        tmp.write_text(json.dumps(ajustes, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.arquivo_ajustes)

    def _telas_do_robo(self, op) -> list[dict]:
        """Esquema da operadora com o valor atual (com os ajustes) e o padrão da Newport (config.yaml)."""
        atual = op.config(self.config_total())
        padrao = op.config(carregar_config(self.caminho_config))
        nomes = dict(op.etapas)
        telas = []
        for tela in op.configuracao(atual):
            campos = []
            for c in tela.get("campos", []):
                c = dict(c)
                if c.get("chave"):
                    c["valor"] = cfgrobo.para_tela(c, cfgrobo.ler(atual, c["chave"]))
                    c["padrao"] = cfgrobo.para_tela(c, cfgrobo.ler(padrao, c["chave"]))
                campos.append(c)
            telas.append({**tela, "titulo": nomes.get(tela["etapa"], tela["etapa"]), "campos": campos})
        return telas

    async def configuracao_robo(self, request: Request):
        op = operadoras.obter(request.path_params["op"])
        cfg = op.config(self.config_total())
        planos = [{"nome": n, "acomodacao": a} for n, a in sorted(
            {(p["nome"], p["acomodacao"]) for p in op.planos_conhecidos()}
            | {(p["nome"], p["acomodacao"]) for p in self.banco.catalogo(op.id)})]
        return JSONResponse({"id": op.id, "nome": op.nome, "produto": op.produto, "cor": op.cor,
                             "conexao": self.robo.conexao.get(op.id, "desconectado"),
                             "planos": planos, "exemplo_pdf": cfg["saida"].get("nome_pdf_destino", ""),
                             "telas": self._telas_do_robo(op)})

    async def gravar_robo(self, request: Request):
        """Grava só os campos que a operadora declara em configuracao(), validados um a um."""
        op = operadoras.obter(request.path_params["op"])
        corpo = await request.json()
        campos = cfgrobo.campos_por_chave(op.configuracao(op.config(self.config_total())))
        novos = {}
        for chave, valor in (corpo.get("valores") or {}).items():
            campo = campos.get(chave)
            if campo is None:
                return JSONResponse({"erro": f"campo desconhecido: {chave}"}, status_code=400)
            try:
                novos[chave] = cfgrobo.validar(campo, valor)
            except ValueError as e:
                return JSONResponse({"erro": f"{campo.get('rotulo') or chave}: {e}", "campo": chave}, status_code=400)
        ajustes = self.ajustes()
        secao = ajustes.setdefault("operadoras", {}).setdefault(op.id, {})
        for chave, valor in novos.items():
            cfgrobo.gravar(secao, chave, valor)
        self._salvar_ajustes(ajustes)
        return JSONResponse({"ok": True, "telas": self._telas_do_robo(op)})

    async def restaurar_robo(self, request: Request):
        """Volta o robô aos padrões da Newport (config.yaml), apagando os ajustes da tela desta operadora."""
        op = operadoras.obter(request.path_params["op"])
        ajustes = self.ajustes()
        (ajustes.get("operadoras") or {}).pop(op.id, None)
        self._salvar_ajustes(ajustes)
        return JSONResponse({"ok": True, "telas": self._telas_do_robo(op)})

    async def ler_geral(self, request: Request):
        total = self.config_total()
        return JSONResponse({"geral": {k: total["geral"].get(k) for k in AJUSTAVEIS_GERAL},
                             "pasta_saida": str(self.pasta), "retencao_dias": self.dias_retencao})

    async def gravar_geral(self, request: Request):
        corpo = await request.json()
        geral = {}
        for k, v in (corpo.get("geral") or {}).items():
            if k not in AJUSTAVEIS_GERAL or not isinstance(v, bool):
                return JSONResponse({"erro": f"ajuste desconhecido: {k}"}, status_code=400)
            geral[k] = v
        ajustes = self.ajustes()
        ajustes.setdefault("geral", {}).update(geral)
        self._salvar_ajustes(ajustes)
        return JSONResponse({"ok": True})

    async def escolher_pasta(self, request: Request):
        """Abre a janela "Escolher pasta" do Windows (o servidor roda na própria máquina do corretor)."""
        script = ("import tkinter as tk; from tkinter import filedialog; r = tk.Tk(); r.withdraw(); "
                  "r.attributes('-topmost', True); print(filedialog.askdirectory(title='Pasta COTAÇÕES do cliente'))")
        try:
            proc = await asyncio.to_thread(subprocess.run, [sys.executable, "-c", script],
                                           capture_output=True, text=True, timeout=600)
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"erro": f"não consegui abrir a janela de pastas ({e})"}, status_code=500)
        pasta = (proc.stdout or "").strip()
        if proc.returncode != 0:
            return JSONResponse({"erro": "não consegui abrir a janela de pastas; cole o caminho no campo"},
                                status_code=500)
        return JSONResponse({"pasta": str(Path(pasta)) if pasta else ""})

    async def importar(self, request: Request):
        form = await request.form()
        arquivo = form.get("arquivo")
        # A planilha é de uma operadora (colunas próprias): a tela sempre diz qual. Nada de operadora "padrão".
        if not form.get("operadora"):
            return JSONResponse({"erro": "escolha a operadora da planilha"}, status_code=400)
        try:
            op, cfg = self._op_cfg(str(form.get("operadora")))
        except KeyError as e:
            return JSONResponse({"erro": str(e)}, status_code=400)
        if arquivo is None:
            return JSONResponse({"erro": "envie um arquivo .xlsx"}, status_code=400)
        conteudo = await arquivo.read()
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "importada.xlsx"
            caminho.write_bytes(conteudo)
            try:
                registros = op.ler_registros(caminho)
            except Exception as e:  # noqa: BLE001
                return JSONResponse({"erro": f"planilha: {e}"}, status_code=400)
        validos, erros, ids = [], [], set()
        for n, registro in registros:
            dados = {k: _serial(v) for k, v in registro.items()}
            pid = str(dados.get("id") or f"L{n}")
            dados["id"] = pid
            try:
                pedido = op.montar_pedido(dados, cfg, linha=n)
                if pid in ids:
                    raise ValueError(f"id '{pid}' repetido na planilha")
                validos.append({"linha": n, "dados": dados, "cnpj": pedido.cnpj, "id": pedido.id,
                                "vidas": pedido.total_vidas, "cotacoes": op.qtd_cotacoes(pedido)})
            except ValueError as e:
                erros.append({"linha": n, "id": pid, "problemas": list(getattr(e, "problemas", [str(e)]))})
            ids.add(pid)
        return JSONResponse({"operadora": op.id, "validos": validos, "erros": erros})

    async def modelo(self, request: Request):
        op = operadoras.obter(request.path_params["op"])
        destino = self.pasta / f"modelo_{op.id}.xlsx"
        op.criar_modelo(destino)
        return FileResponse(destino, filename=f"cotacoes_modelo_{op.id}.xlsx")

    async def eventos(self, request: Request):
        fila = self.bus.assinar()

        async def fluxo():
            try:
                yield "retry: 3000\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        ev = await asyncio.wait_for(fila.get(), timeout=15)
                        yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
            finally:
                self.bus.cancelar(fila)
        return StreamingResponse(fluxo(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ------------------------------------------------------------------ aplicação
    def criar_app(self) -> Starlette:
        tela = self

        @contextlib.asynccontextmanager
        async def ciclo(app):
            tela.bus.ligar(asyncio.get_running_loop())
            if not tela.robo.is_alive():
                tela.robo.start()
            yield
            tela.robo.encerrar()
            # o robô tenta sair do portal (logout) antes de a tela fechar; no meio de uma cotação, não espera
            await asyncio.get_running_loop().run_in_executor(None, tela.robo.join, 6)

        rotas = [
            Route("/", self.inicio),
            Route("/api/estado", self.estado),
            Route("/api/operadoras", self.lista_operadoras),
            Route("/api/validar", self.validar, methods=["POST"]),
            Route("/api/trabalhos", self.trabalhos),
            Route("/api/trabalhos", self.criar_trabalho, methods=["POST"]),
            Route("/api/trabalhos/{tid:int}", self.trabalho),
            Route("/api/trabalhos/{tid:int}/parar", self.parar, methods=["POST"]),
            Route("/api/trabalhos/{tid:int}/repetir", self.repetir, methods=["POST"]),
            Route("/api/conectar/{op}", self.conectar, methods=["POST"]),
            Route("/api/sair/{op}", self.sair_do_portal, methods=["POST"]),
            Route("/api/credenciais/{op}", self.ler_credenciais),
            Route("/api/credenciais/{op}", self.guardar_credenciais, methods=["POST"]),
            Route("/api/credenciais/{op}", self.apagar_credenciais, methods=["DELETE"]),
            Route("/api/codigo/{op}", self.receber_codigo, methods=["POST"]),
            Route("/api/cotacoes", self.cotacoes),
            Route("/api/cotacoes/{cid:int}/pdf", self.baixar_pdf),
            Route("/api/pdfs.zip", self.baixar_zip),
            Route("/api/cotacoes/{cid:int}/abrir-pasta", self.abrir_pasta, methods=["POST"]),
            Route("/api/empresas", self.empresas),
            Route("/api/empresas/{cnpj}", self.empresa),
            Route("/api/pendencias", self.pendencias),
            Route("/api/liberar", self.liberar, methods=["POST"]),
            Route("/api/concluir", self.concluir, methods=["POST"]),
            Route("/api/robos/{op}", self.configuracao_robo),
            Route("/api/robos/{op}", self.gravar_robo, methods=["PUT"]),
            Route("/api/robos/{op}", self.restaurar_robo, methods=["DELETE"]),
            Route("/api/geral", self.ler_geral),
            Route("/api/geral", self.gravar_geral, methods=["PUT"]),
            Route("/api/escolher-pasta", self.escolher_pasta, methods=["POST"]),
            Route("/api/importar", self.importar, methods=["POST"]),
            Route("/api/modelo/{op}", self.modelo),
            Route("/api/eventos", self.eventos),
            Mount("/static", _ArquivosSemCache(directory=str(WEB)), name="static"),
        ]
        cfg = self.config_total()
        anc = _origens_frame_ancestors(cfg)
        cors = _origens_permitidas(cfg)
        return Starlette(
            routes=rotas,
            middleware=[Middleware(
                SoDaPropriaTela,
                porta=self.porta,
                frame_ancestors=anc,
                origens_permitidas=cors,
            )],
            lifespan=ciclo,
        )


def _lista_origens_cfg(cfg: dict, chave: str) -> list[str]:
    """Lê lista de origens do bloco tela.* (sem domínio fixo no código)."""
    brutos = (cfg.get("tela") or {}).get(chave) or []
    if not isinstance(brutos, list):
        return []
    saida: list[str] = []
    for item in brutos:
        s = str(item).strip().rstrip("/")
        if s and s not in saida:
            saida.append(s)
    return saida


def _origens_frame_ancestors(cfg: dict) -> list[str]:
    """Origens externas permitidas em frame-ancestors (vêm do config)."""
    return _lista_origens_cfg(cfg, "frame_ancestors")


def _origens_permitidas(cfg: dict) -> list[str]:
    """Origens do Benefits que podem chamar a API (CORS) — tela.origens_permitidas no config."""
    return _lista_origens_cfg(cfg, "origens_permitidas")


def _cabecalhos_seguranca(frame_ancestors: list[str]) -> list[tuple[bytes, bytes]]:
    if frame_ancestors:
        ancestros = " ".join(["'self'", *frame_ancestors])
    else:
        ancestros = "'none'"
    csp = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        f"font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
        f"form-action 'none'; frame-ancestors {ancestros}"
    )
    # Com allowlist, só a CSP controla o iframe (X-Frame-Options: DENY bloquearia o Benefits).
    return [
        (b"content-security-policy", csp.encode("ascii")),
        (b"x-content-type-options", b"nosniff"),
        (b"referrer-policy", b"no-referrer"),
        (b"cross-origin-opener-policy", b"same-origin"),
        (b"cross-origin-resource-policy", b"same-origin"),
    ]


def _cabecalhos_cors(origem: str, *, preflight: bool = False, private_network: bool = False) -> list[tuple[bytes, bytes]]:
    """CORS só para origem da allowlist. Private Network Access no preflight quando o Chrome pede."""
    out: list[tuple[bytes, bytes]] = [
        (b"access-control-allow-origin", origem.encode("ascii")),
        (b"vary", b"Origin"),
        (b"access-control-expose-headers", b"content-disposition, content-type"),
    ]
    if preflight:
        out.extend([
            (b"access-control-allow-methods", b"GET, HEAD, POST, PUT, DELETE, OPTIONS"),
            (b"access-control-allow-headers", b"content-type, x-newport-tela"),
            (b"access-control-max-age", b"600"),
        ])
        if private_network:
            out.append((b"access-control-allow-private-network", b"true"))
    return out


class SoDaPropriaTela:
    """Só a própria tela (e o Benefits na allowlist) conversam com o servidor local.

    - Host: 127.0.0.1 ou localhost nesta porta (bloqueia DNS rebinding).
    - Mutações: exigem X-Newport-Tela: 1 e, se houver Origin, ela tem que ser a própria
      tela OU uma origem em tela.origens_permitidas (Benefits). Site estranho → 403.
    - CORS: só para origens_permitidas (inclui preflight e Private Network Access).
    - frame-ancestors: CSP com allowlist (iframe); CORP same-origin por padrão, e
      cross-origin só quando a Origin da allowlist chama a API (fetch/SSE do Benefits).
    """

    def __init__(
        self,
        app,
        porta: int,
        frame_ancestors: list[str] | None = None,
        origens_permitidas: list[str] | None = None,
    ):
        self.app = app
        self.hosts = {f"127.0.0.1:{porta}", f"localhost:{porta}"}
        self.proprias = {f"http://{h}" for h in self.hosts}
        self.cors = set(origens_permitidas or [])
        self.mutacao_ok = self.proprias | self.cors
        self._cabecalhos = _cabecalhos_seguranca(frame_ancestors or [])

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        cab = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        if cab.get("host") not in self.hosts:
            await JSONResponse({"erro": "endereço não permitido"}, status_code=421)(scope, receive, send)
            return

        origem = cab.get("origin")

        if scope["method"] == "OPTIONS":
            if not origem or origem not in self.cors:
                await JSONResponse({"erro": "pedido recusado"}, status_code=403)(scope, receive, send)
                return
            pna = cab.get("access-control-request-private-network", "").lower() == "true"
            heads = {
                k.decode("ascii"): v.decode("ascii")
                for k, v in _cabecalhos_cors(origem, preflight=True, private_network=pna)
            }
            await Response(status_code=204, headers=heads)(scope, receive, send)
            return

        if scope["method"] not in ("GET", "HEAD"):
            if cab.get("x-newport-tela") != "1" or (origem and origem not in self.mutacao_ok):
                await JSONResponse({"erro": "pedido recusado"}, status_code=403)(scope, receive, send)
                return

        async def enviar(mensagem):
            if mensagem["type"] == "http.response.start":
                headers = list(mensagem.get("headers") or []) + list(self._cabecalhos)
                if origem and origem in self.cors:
                    # fetch/SSE do Benefits: CORP same-origin bloquearia a leitura cross-origin.
                    headers = [(k, v) for k, v in headers if k != b"cross-origin-resource-policy"]
                    headers.append((b"cross-origin-resource-policy", b"cross-origin"))
                    headers.extend(_cabecalhos_cors(origem))
                mensagem["headers"] = headers
            await send(mensagem)

        await self.app(scope, receive, enviar)
