"""Saídas: resultados.xlsx (histórico, uma linha por plano) e nomes/cópias de PDF. Comum a todas as operadoras."""
from __future__ import annotations

import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook, load_workbook

from .modelo import ROTULOS, CHAVE_POR_ROTULO, PlanoVisto, ResultadoPlano
from .texto import formatar_cnpj, nome_arquivo_seguro

COLUNAS_RESULTADO = (
    ["data_hora", "pedido_id", "linha", "cnpj", "razao_social", "plano", "acomodacao", "status",
     "protocolo", "preco_mensal", "total_sem_iof", "iof", "total_com_iof"]
    + [f"valor_vida_{CHAVE_POR_ROTULO[r]}" for r in ROTULOS]
    + ["pdf_arquivo", "pdf_destino", "etapa_erro", "erro", "versao"]
)
COLUNAS_PRECOS = ["data_hora", "pedido_id", "cnpj", "plano", "acomodacao", "descricao",
                  "versao", "preco_mensal", "pagina"]


def _com_nome_da_versao(colunas: list[str], nome_versao: str) -> list[str]:
    """A coluna "versao" com o nome que a operadora declara (ex.: "coparticipacao")."""
    return [nome_versao if c == "versao" else c for c in colunas]


def _num(valor):
    return float(valor) if isinstance(valor, Decimal) else valor


class Resultados:
    """Acrescenta linhas em saida/resultados.xlsx sem apagar o histórico."""

    def __init__(self, caminho: str | Path, log, ouvinte=None, nome_versao: str = "versao"):
        self.caminho = Path(caminho)
        self.log = log
        self.colunas = _com_nome_da_versao(COLUNAS_RESULTADO, nome_versao)
        self.colunas_precos = _com_nome_da_versao(COLUNAS_PRECOS, nome_versao)
        self.ouvinte = ouvinte               # callable(tipo, dados) — a tela recebe cada resultado
        self.contagem: dict[str, int] = {}   # status -> quantidade, nesta execução

    def _avisar(self, tipo: str, dados) -> None:
        if self.ouvinte:
            try:
                self.ouvinte(tipo, dados)
            except Exception as e:  # noqa: BLE001  (a tela nunca pode derrubar o robô)
                self.log.warning(f"tela: falha ao registrar {tipo} ({e})")

    def _abrir(self):
        if self.caminho.exists():
            wb = load_workbook(self.caminho)
        else:
            wb = Workbook()
            ws = wb.active
            ws.title = "cotacoes"
            ws.append(self.colunas)
            wb.create_sheet("precos_planos").append(self.colunas_precos)
            wb.create_sheet("erros_planilha").append(["data_hora", "linha", "pedido_id", "erro"])
        return wb

    def _gravar(self, wb) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        try:
            wb.save(self.caminho)
        except PermissionError:
            # No Windows, o arquivo aberto no Excel fica travado.
            alternativo = self.caminho.with_name(
                f"{self.caminho.stem}_{datetime.now():%Y%m%d_%H%M%S}{self.caminho.suffix}")
            wb.save(alternativo)
            self.log.warning(f"{self.caminho.name} está aberto (Excel?). Gravei em {alternativo.name}.")

    def plano(self, r: ResultadoPlano) -> None:
        self.contagem[r.status] = self.contagem.get(r.status, 0) + 1
        wb = self._abrir()
        ws = wb["cotacoes"]
        if ws.cell(1, len(self.colunas)).value != self.colunas[-1]:
            ws.cell(1, len(self.colunas)).value = self.colunas[-1]   # planilha de antes da coluna nova
        linha = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), r.pedido_id, r.linha,
                 formatar_cnpj(r.cnpj), r.razao_social, r.plano, r.acomodacao, r.status, r.protocolo,
                 _num(r.preco_mensal), _num(r.total_sem_iof), _num(r.iof), _num(r.total_com_iof)]
        linha += [_num(r.valores_por_vida.get(rot)) for rot in ROTULOS]
        linha += [r.pdf_arquivo, r.pdf_destino, r.etapa_erro, r.erro[:500], getattr(r, "versao", "")]
        ws.append(linha)
        self._gravar(wb)
        self._avisar("plano", r)

    def precos(self, pedido_id: str, cnpj: str, planos: list[PlanoVisto]) -> None:
        if not planos:
            return
        wb = self._abrir()
        ws = wb["precos_planos"]
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for p in planos:
            ws.append([agora, pedido_id, formatar_cnpj(cnpj), p.nome, p.acomodacao, p.descricao,
                       p.versao, _num(p.preco), p.pagina])
        self._gravar(wb)
        self._avisar("precos", {"pedido_id": pedido_id, "cnpj": cnpj, "planos": planos})

    def erros_planilha(self, erros) -> None:
        if not erros:
            return
        wb = self._abrir()
        ws = wb["erros_planilha"]
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for e in erros:
            ws.append([agora, e.linha, e.id, e.mensagem])
        self._gravar(wb)


def nome_plano_arquivo(plano: str, cfg: dict) -> str:
    mapa = (cfg.get("saida") or {}).get("nomes_arquivo") or {}
    for original, curto in mapa.items():
        if original.strip().lower() == plano.strip().lower():
            return curto.upper()
    return plano.upper()


def nome_pdf_arquivo(cfg: dict, cnpj: str, protocolo: str, plano: str) -> str:
    modelo = (cfg.get("saida") or {}).get("nome_pdf_arquivo", "COTACAO_{cnpj}_{protocolo}.pdf")   # a operadora define
    return nome_arquivo_seguro(modelo.format(cnpj=cnpj, protocolo=protocolo,
                                             plano=plano, plano_arquivo=nome_plano_arquivo(plano, cfg)))


def nome_pdf_destino(cfg: dict, cnpj: str, protocolo: str, plano: str, acomodacao: str = "",
                     versao: str = "") -> str:
    """Nome do PDF na pasta do cliente. Com acomodacao, ela entra no nome do plano
    (usado quando o mesmo plano existe em Enfermaria e Apartamento: um PDF não substitui o outro).
    Com versao (o texto que a operadora dá à versão da cotação), ela também entra: no lugar de {versao}, se o
    modelo tiver, ou logo depois do plano. Assim duas versões do mesmo plano nunca têm o mesmo nome."""
    modelo = (cfg.get("saida") or {}).get("nome_pdf_destino", "COTACAO {plano_arquivo}.pdf")   # a operadora define
    plano_arquivo = nome_plano_arquivo(plano, cfg)
    if acomodacao:
        plano_arquivo = f"{plano_arquivo} {acomodacao.upper()}"
    if versao and "{versao}" not in modelo:
        if "{plano_arquivo}" in modelo:
            plano_arquivo = f"{plano_arquivo} {versao}"
        else:
            modelo = modelo[:-4] + " {versao}.pdf" if modelo.lower().endswith(".pdf") else modelo + " {versao}"
    nome = modelo.format(cnpj=cnpj, protocolo=protocolo, plano=plano, plano_arquivo=plano_arquivo,
                         acomodacao=acomodacao, versao=versao)
    return nome_arquivo_seguro(" ".join(nome.split()).replace(" .pdf", ".pdf"))


def copiar_para_destino(origem: Path, pasta: str, nome: str, substituir: bool, log) -> str:
    destino_dir = Path(pasta)
    if not destino_dir.exists():
        raise FileNotFoundError(f"pasta_destino não existe: {destino_dir}")
    destino = destino_dir / nome
    if destino.exists() and not substituir:
        base, ext = destino.stem, destino.suffix
        destino = destino_dir / f"{base} ({datetime.now():%Y%m%d_%H%M%S}){ext}"
    shutil.copy2(origem, destino)
    log.info(f"PDF copiado para a pasta do cliente: {destino}")
    return str(destino)
