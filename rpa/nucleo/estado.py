"""Registro de andamento (saida/estado.json).

Regra central: o robô NUNCA emite duas vezes a mesma cotação. "Mesma cotação" =
mesmo CNPJ + mesmos parâmetros que mudam o preço (vidas, vigência, coparticipação,
tipo de contratação, Cuidado 360°, congênere) + mesmo plano e acomodação **como
aparecem no portal**. O id da linha e a grafia do plano na planilha não entram na
chave: mover a linha, trocar o id ou escrever "Especial Mais" em vez de
"Especial Mais | Apartamento" não libera nova emissão.

Status de cada cotação:
  emitindo    clicou em emitir e ainda não confirmou o protocolo (estado incerto)
  emitida     protocolo capturado, PDF ainda não salvo
  pdf_ok      PDF salvo; concluída
  pdf_manual  protocolo existe, mas o PDF não pôde ser recuperado; baixar à mão

Todos bloqueiam nova emissão. Para recotar de propósito (ex.: validade vencida) ou
liberar um item conferido no portal:  python main.py --liberar "<chave>"  (ou "Não saiu: liberar" na tela).

Única exceção ao bloqueio: o corretor clica, na tela, em "Emitir de novo mesmo assim" no aviso de cotação
já emitida (testes e demonstrações). O pedido leva os protocolos que ele viu no aviso, e o robô só emite de
novo uma cotação concluída (pdf_ok) com aquele protocolo, uma vez: na hora de gravar "emitindo", o item
antigo vai para "reemitidos" (com o protocolo de antes) e o novo volta a bloquear como qualquer outro.
"Tentar de novo", planilhas e pedidos repetidos nunca levam essa exceção.

Concorrência: o robô, a tela (liberar / resolver à mão) e a linha de comando podem mexer no mesmo
arquivo. Toda consulta relê o disco se ele mudou, e toda gravação acontece sob uma trava curta, relendo
o arquivo antes de mudar e gravando de forma atômica e durável (temporário + fsync + troca com
"write-through"). Assim uma gravação nunca apaga a de outro processo.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

from .texto import norm
from .trava import Trava

BLOQUEIA_EMISSAO = {"emitindo", "emitida", "pdf_ok", "pdf_manual"}


def _hash(assinatura: str) -> str:
    return hashlib.sha1(assinatura.encode("utf-8")).hexdigest()[:8]


def _substituir(tmp: Path, destino: Path) -> None:
    """Troca o arquivo de forma atômica e durável. No Windows, espera se outro programa (leitor,
    antivírus) estiver com o arquivo aberto naquele instante."""
    fim = time.monotonic() + 10
    while True:
        try:
            if os.name == "nt":
                import ctypes
                MOVEFILE_REPLACE_EXISTING, MOVEFILE_WRITE_THROUGH = 0x1, 0x8
                if not ctypes.windll.kernel32.MoveFileExW(str(tmp), str(destino),
                                                          MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH):
                    raise ctypes.WinError()
            else:
                os.replace(tmp, destino)
                fd = os.open(destino.parent, os.O_RDONLY)
                try:
                    os.fsync(fd)   # a troca de nome também precisa estar no disco
                finally:
                    os.close(fd)
            return
        except PermissionError:
            if time.monotonic() >= fim:
                raise
            time.sleep(0.05)


class Estado:
    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)
        self._assinatura_arquivo = None
        self.dados = {"versao": 2, "itens": {}, "criterios": {}}
        self.recarregar()

    # ------------------------------------------------------------------ disco
    def recarregar(self) -> None:
        """Relê o arquivo se ele mudou desde a última leitura (outro processo pode ter gravado)."""
        fim = time.monotonic() + 10
        while True:
            try:
                st = os.stat(self.caminho)
                marca = (st.st_mtime_ns, st.st_size)
                if marca == self._assinatura_arquivo:
                    return
                with open(self.caminho, encoding="utf-8") as f:
                    dados = json.load(f)
                break
            except FileNotFoundError:
                dados, marca = {"versao": 2, "itens": {}, "criterios": {}}, None
                break
            except PermissionError:   # Windows: o arquivo está sendo trocado neste instante
                if time.monotonic() >= fim:
                    raise
                time.sleep(0.05)
        dados.setdefault("itens", {})
        dados.setdefault("criterios", {})
        self.dados, self._assinatura_arquivo = dados, marca

    @contextlib.contextmanager
    def _gravando(self):
        """Trava curta entre processos + releitura: a mudança é aplicada sobre o arquivo mais novo."""
        with Trava(self.caminho.parent, self.caminho.name + ".trava", esperar_s=30,
                   mensagem="o registro de cotações ficou ocupado por mais de 30 s; tente de novo"):
            self._assinatura_arquivo = None
            self.recarregar()
            antes = json.dumps(self.dados, sort_keys=True, ensure_ascii=False)
            yield
            if json.dumps(self.dados, sort_keys=True, ensure_ascii=False) != antes:
                self._salvar()

    # ------------------------------------------------------------------ chaves
    @staticmethod
    def chave(pedido, plano_nome: str, acomodacao: str | None) -> str:
        """Chave da cotação real: plano e acomodação como aparecem no portal."""
        return f"{pedido.cnpj}|{norm(plano_nome)}|{norm(acomodacao or '')}|{_hash(pedido.assinatura())}"

    def item(self, chave: str) -> dict | None:
        self.recarregar()
        return self.dados["itens"].get(chave)

    def status(self, chave: str) -> str | None:
        item = self.item(chave)
        return item["status"] if item else None

    def pode_emitir(self, chave: str) -> bool:
        return self.status(chave) not in BLOQUEIA_EMISSAO

    def procurar(self, pedido, alvo) -> tuple[str, dict] | None:
        """Cotação já registrada para este pedido (mesmo CNPJ e parâmetros) que casa com o alvo da planilha.

        Usado antes de abrir o portal; o alvo pode vir sem acomodação ("Especial Mais").
        """
        self.recarregar()
        h = _hash(pedido.assinatura())
        for chave, item in self.dados["itens"].items():
            if item.get("cnpj") == pedido.cnpj and item.get("hash") == h \
                    and alvo.casa_com(item.get("plano", ""), item.get("acomodacao")):
                return chave, item
        return None

    # ------------------------------------------------------------------ critério (menor preço)
    def _chave_criterio(self, pedido) -> str:
        return f"{pedido.cnpj}|{_hash(pedido.assinatura())}"

    def planos_resolvidos(self, pedido) -> list[str] | None:
        self.recarregar()
        return self.dados["criterios"].get(self._chave_criterio(pedido))

    def salvar_planos_resolvidos(self, pedido, rotulos: list[str]) -> None:
        with self._gravando():
            self.dados["criterios"][self._chave_criterio(pedido)] = rotulos

    # ------------------------------------------------------------------ gravação
    def registrar(self, chave: str, pedido, plano: str, acomodacao: str | None,
                  status: str, obs: str = "", substituir_protocolo: str | None = None, **campos) -> None:
        """substituir_protocolo: emitir de novo, a pedido do corretor, a cotação concluída com esse protocolo.
        O item antigo vai para "reemitidos" na mesma gravação; se ele não estiver mais concluído com esse
        protocolo, não grava nada e levanta erro (o robô não clica em emitir)."""
        with self._gravando():
            agora = datetime.now().isoformat(timespec="seconds")
            if substituir_protocolo:
                antigo = self.dados["itens"].get(chave)
                if antigo is not None:
                    if antigo.get("status") != "pdf_ok" or str(antigo.get("protocolo") or "") != substituir_protocolo:
                        raise RuntimeError(f"item {chave} mudou ({antigo.get('status')}, protocolo "
                                           f"{antigo.get('protocolo') or '-'}); não emito de novo")
                    self.dados.setdefault("reemitidos", []).append(
                        {"em": agora, "chave": chave, "item": self.dados["itens"].pop(chave)})
                campos["reemissao_de"] = substituir_protocolo
            item = self.dados["itens"].setdefault(chave, {
                "pedido_id": pedido.id, "cnpj": pedido.cnpj, "plano": plano,
                "acomodacao": acomodacao or "", "hash": chave.rsplit("|", 1)[-1],
                "criado_em": agora, "historico": [],
            })
            if hasattr(pedido, "assinatura"):
                item.setdefault("parametros", pedido.assinatura())
            if item.get("status") == "pdf_ok" and status != "pdf_ok":
                raise RuntimeError(f"item {chave} já concluído; não pode voltar para {status}")
            item["status"] = status
            item["atualizado_em"] = agora
            item.update({k: v for k, v in campos.items() if v is not None})
            item["historico"].append({"em": agora, "status": status, "obs": obs})

    def liberar(self, chave: str) -> bool:
        with self._gravando():
            if chave not in self.dados["itens"]:
                return False
            removido = self.dados["itens"].pop(chave)
            self.dados.setdefault("liberados", []).append({
                "em": datetime.now().isoformat(timespec="seconds"), "chave": chave, "item": removido})
            return True

    def concluir_manual(self, chave: str, obs: str) -> bool:
        """O corretor resolveu à mão no portal (conferiu a emissão e baixou o PDF).
        O item fica como concluído: continua impedindo reemissão. É o oposto de liberar."""
        with self._gravando():
            item = self.dados["itens"].get(chave)
            if not item or item.get("status") not in ("emitindo", "emitida", "pdf_manual"):
                return False
            agora = datetime.now().isoformat(timespec="seconds")
            item["status"] = "pdf_ok"
            item["atualizado_em"] = agora
            item["resolvido_a_mao"] = True
            item["historico"].append({"em": agora, "status": "pdf_ok", "obs": obs})
            return True

    def pendencias(self) -> list[tuple[str, dict]]:
        """Itens que precisam de atenção humana ou de recuperação de PDF."""
        self.recarregar()
        return [(k, v) for k, v in self.dados["itens"].items()
                if v.get("status") in ("emitindo", "emitida", "pdf_manual")]

    def _salvar(self) -> None:
        """Só dentro de _gravando(). "emitindo" precisa estar no disco antes do clique de emitir."""
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho.with_name(f"{self.caminho.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.dados, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        _substituir(tmp, self.caminho)
        st = os.stat(self.caminho)
        self._assinatura_arquivo = (st.st_mtime_ns, st.st_size)
