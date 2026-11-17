"""Histórico da tela em SQLite (saida/tela.db): trabalhos, cotações, eventos, planos vistos e empresas.

O registro que impede reemissão continua sendo o estado.json de cada operadora; aqui fica só o
que a tela precisa mostrar.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS trabalhos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, criado_em TEXT, tipo TEXT, modo TEXT, status TEXT,
  titulo TEXT, total_pedidos INTEGER DEFAULT 0, total_cotacoes INTEGER DEFAULT 0,
  mensagem TEXT DEFAULT '', terminado_em TEXT, itens_json TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS cotacoes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, trabalho_id INTEGER, criado_em TEXT, operadora TEXT, modo TEXT,
  pedido_id TEXT, cnpj TEXT, razao_social TEXT, plano TEXT, acomodacao TEXT, status TEXT, protocolo TEXT,
  preco_mensal REAL, total_sem_iof REAL, iof REAL, total_com_iof REAL, valores_json TEXT,
  pdf_arquivo TEXT, pdf_destino TEXT, erro TEXT, etapa_erro TEXT, pdf_nome TEXT DEFAULT '',
  versao TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS ix_cotacoes_cnpj ON cotacoes (cnpj);
CREATE TABLE IF NOT EXISTS eventos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, trabalho_id INTEGER, em TEXT, tipo TEXT, texto TEXT, dados_json TEXT);
CREATE INDEX IF NOT EXISTS ix_eventos_trabalho ON eventos (trabalho_id);
CREATE TABLE IF NOT EXISTS catalogo (
  operadora TEXT, nome TEXT, acomodacao TEXT, visto_em TEXT, PRIMARY KEY (operadora, nome, acomodacao));
CREATE TABLE IF NOT EXISTS empresas (
  cnpj TEXT PRIMARY KEY, razao_social TEXT, apelido TEXT, atualizado_em TEXT, ultimo_pedido_json TEXT);
"""


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _num(v):
    if isinstance(v, Decimal):
        return float(v)
    return v


class Banco:
    def __init__(self, caminho: str | Path):
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(caminho), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._con.executescript(ESQUEMA)
            # bancos criados por versão anterior da tela
            for tabela, coluna, tipo in (("cotacoes", "pdf_nome", "TEXT DEFAULT ''"),
                                         ("cotacoes", "versao", "TEXT DEFAULT ''"),
                                         ("trabalhos", "itens_json", "TEXT DEFAULT '[]'")):
                colunas = {r["name"] for r in self._con.execute(f"PRAGMA table_info({tabela})")}
                if coluna not in colunas:
                    self._con.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
            # 06/11: a versão da cotação era gravada na coluna "coparticipacao" (só a SulAmérica tinha versões)
            colunas = {r["name"] for r in self._con.execute("PRAGMA table_info(cotacoes)")}
            if "coparticipacao" in colunas:
                self._con.execute("UPDATE cotacoes SET versao=coparticipacao "
                                  "WHERE (versao IS NULL OR versao='') AND coparticipacao<>''")
            # trabalhos que ficaram "rodando" quando a tela foi fechada
            self._con.execute("UPDATE trabalhos SET status='interrompido', terminado_em=? "
                              "WHERE status IN ('na_fila','rodando')", (_agora(),))
            self._con.commit()

    def _exec(self, sql: str, args=()):
        with self._lock:
            cur = self._con.execute(sql, args)
            self._con.commit()
            return cur

    def _todos(self, sql: str, args=()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._con.execute(sql, args).fetchall()]

    # ------------------------------------------------------------------ trabalhos
    def novo_trabalho(self, tipo: str, modo: str, titulo: str, total_pedidos: int, total_cotacoes: int,
                      itens: list | None = None) -> int:
        cur = self._exec("INSERT INTO trabalhos (criado_em, tipo, modo, status, titulo, total_pedidos, total_cotacoes, "
                         "itens_json) VALUES (?,?,?,?,?,?,?,?)",
                         (_agora(), tipo, modo, "na_fila", titulo, total_pedidos, total_cotacoes,
                          json.dumps(itens or [], ensure_ascii=False, default=str)))
        return int(cur.lastrowid)

    def atualizar_trabalho(self, tid: int, status: str, mensagem: str = "") -> None:
        fim = _agora() if status in ("concluido", "erro", "cancelado", "interrompido") else None
        self._exec("UPDATE trabalhos SET status=?, mensagem=?, terminado_em=COALESCE(?, terminado_em) WHERE id=?",
                   (status, mensagem, fim, tid))

    def trabalho(self, tid: int) -> dict | None:
        r = self._todos("SELECT * FROM trabalhos WHERE id=?", (tid,))
        if not r:
            return None
        t = r[0]
        t["itens"] = json.loads(t.pop("itens_json") or "[]")
        return t

    def trabalhos(self, limite: int = 20) -> list[dict]:
        linhas = self._todos("SELECT * FROM trabalhos ORDER BY id DESC LIMIT ?", (limite,))
        for t in linhas:
            itens = json.loads(t.pop("itens_json") or "[]")
            t["operadoras"] = sorted({it.get("operadora") for it in itens if it.get("operadora")})
        return linhas

    # ------------------------------------------------------------------ cotações
    def registrar_cotacao(self, tid: int | None, operadora: str, modo: str, r) -> dict:
        valores = {k: _num(v) for k, v in (r.valores_por_vida or {}).items()}
        cur = self._exec(
            "INSERT INTO cotacoes (trabalho_id, criado_em, operadora, modo, pedido_id, cnpj, razao_social, plano, "
            "acomodacao, status, protocolo, preco_mensal, total_sem_iof, iof, total_com_iof, valores_json, "
            "pdf_arquivo, pdf_destino, erro, etapa_erro, pdf_nome, versao) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tid, _agora(), operadora, modo, r.pedido_id, r.cnpj, r.razao_social, r.plano, r.acomodacao,
             r.status, r.protocolo, _num(r.preco_mensal), _num(r.total_sem_iof), _num(r.iof),
             _num(r.total_com_iof), json.dumps(valores, ensure_ascii=False), r.pdf_arquivo, r.pdf_destino,
             r.erro, r.etapa_erro, getattr(r, "pdf_nome", "") or "", getattr(r, "versao", "") or ""))
        if r.razao_social:
            self._exec("INSERT INTO empresas (cnpj, razao_social, atualizado_em) VALUES (?,?,?) "
                       "ON CONFLICT(cnpj) DO UPDATE SET razao_social=excluded.razao_social, "
                       "atualizado_em=excluded.atualizado_em", (r.cnpj, r.razao_social, _agora()))
        return self.cotacao(int(cur.lastrowid))

    def cotacao(self, cid: int) -> dict | None:
        r = self._todos("SELECT * FROM cotacoes WHERE id=?", (cid,))
        return _com_valores(r[0]) if r else None

    def cotacoes(self, busca: str = "", status: str = "", trabalho: int | None = None, limite: int = 300) -> list[dict]:
        sql = "SELECT * FROM cotacoes WHERE 1=1"
        args: list = []
        if busca:
            digitos = "".join(ch for ch in busca if ch.isdigit())
            sql += " AND (razao_social LIKE ? OR plano LIKE ? OR protocolo LIKE ? OR pedido_id LIKE ?"
            args += [f"%{busca}%"] * 4
            if digitos:
                sql += " OR cnpj LIKE ?"
                args.append(f"%{digitos}%")
            sql += ")"
        if status:
            sql += " AND status IN (" + ",".join("?" * len(status.split(","))) + ")"
            args += status.split(",")
        if trabalho:
            sql += " AND trabalho_id=?"
            args.append(trabalho)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limite)
        return [_com_valores(r) for r in self._todos(sql, args)]

    # ------------------------------------------------------------------ eventos
    def evento(self, tid: int | None, tipo: str, texto: str = "", dados: dict | None = None) -> None:
        self._exec("INSERT INTO eventos (trabalho_id, em, tipo, texto, dados_json) VALUES (?,?,?,?,?)",
                   (tid, _agora(), tipo, texto, json.dumps(dados or {}, ensure_ascii=False, default=str)))

    def eventos(self, tid: int, limite: int = 400) -> list[dict]:
        linhas = self._todos("SELECT * FROM eventos WHERE trabalho_id=? ORDER BY id DESC LIMIT ?", (tid, limite))
        for l in linhas:
            l["dados"] = json.loads(l.pop("dados_json") or "{}")
        return list(reversed(linhas))

    def limpar_eventos(self, dias: int | None) -> None:
        """Prazo de retenção: o registro detalhado (linhas do log) some depois de N dias."""
        if not dias or int(dias) <= 0:
            return
        corte = datetime.fromtimestamp(datetime.now().timestamp() - int(dias) * 86400).isoformat(timespec="seconds")
        self._exec("DELETE FROM eventos WHERE em < ?", (corte,))

    # ------------------------------------------------------------------ catálogo e empresas
    def salvar_catalogo(self, operadora: str, planos) -> None:
        agora = _agora()
        for p in planos:
            self._exec("INSERT INTO catalogo (operadora, nome, acomodacao, visto_em) VALUES (?,?,?,?) "
                       "ON CONFLICT(operadora, nome, acomodacao) DO UPDATE SET visto_em=excluded.visto_em",
                       (operadora, p.nome, p.acomodacao, agora))

    def catalogo(self, operadora: str) -> list[dict]:
        return self._todos("SELECT nome, acomodacao, visto_em FROM catalogo WHERE operadora=? ORDER BY nome",
                           (operadora,))

    def salvar_empresa(self, cnpj: str, apelido: str, dados: dict) -> None:
        self._exec("INSERT INTO empresas (cnpj, apelido, atualizado_em, ultimo_pedido_json) VALUES (?,?,?,?) "
                   "ON CONFLICT(cnpj) DO UPDATE SET apelido=COALESCE(NULLIF(excluded.apelido,''), apelido), "
                   "atualizado_em=excluded.atualizado_em, ultimo_pedido_json=excluded.ultimo_pedido_json",
                   (cnpj, apelido, _agora(), json.dumps(dados, ensure_ascii=False)))

    def empresas(self, busca: str = "", limite: int = 20) -> list[dict]:
        args: list = []
        sql = "SELECT cnpj, razao_social, apelido, atualizado_em FROM empresas"
        if busca:
            digitos = "".join(ch for ch in busca if ch.isdigit()) or "\x00"
            sql += " WHERE razao_social LIKE ? OR apelido LIKE ? OR cnpj LIKE ?"
            args = [f"%{busca}%", f"%{busca}%", f"%{digitos}%"]
        sql += " ORDER BY atualizado_em DESC LIMIT ?"
        args.append(limite)
        return self._todos(sql, args)

    def empresa(self, cnpj: str) -> dict | None:
        r = self._todos("SELECT * FROM empresas WHERE cnpj=?", (cnpj,))
        if not r:
            return None
        e = r[0]
        e["ultimo_pedido"] = json.loads(e.pop("ultimo_pedido_json") or "null")
        return e


def _com_valores(linha: dict) -> dict:
    linha["valores_por_vida"] = json.loads(linha.pop("valores_json") or "{}")
    return linha
