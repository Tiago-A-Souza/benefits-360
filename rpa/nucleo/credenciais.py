"""Login do portal de cada operadora, guardado no cofre do Windows (Gerenciador de Credenciais).

Cada operadora declara os campos do login dela (Operadora.campos_login: ex.: CPF, e-mail e senha), que o
registro das operadoras anota aqui (`registrar_campos`). O corretor guarda uma vez, na engrenagem do robô
(tela 1, Login); só o robô lê de volta, na hora de entrar no portal. Um serviço por operadora
("NewportCotacoes/<operadora>"), no usuário do Windows: em máquina compartilhada, cada corretor entra com o
próprio usuário do Windows.

Nada disso vai para config_tela.json, config.yaml, tela.db, estado.json, resultados.xlsx, logs, eventos,
mapa, mensagens de erro, URL ou git. A tela só recebe {guardadas, quando, recusadas} e, dos campos que a
operadora marca com "mascara", a versão mascarada (ex.: email_mascarado).
Rede de segurança: os valores lidos ficam em memória para `ocultar()`, que o log, os erros e o mapa usam.
"""
from __future__ import annotations

import getpass
import json
import logging
import re
import traceback
from datetime import datetime

import keyring
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

PREFIXO_SERVICO = "NewportCotacoes"

# Campos do login de uma operadora. "tipo": cpf | cpf_cnpj | email | texto | senha (a senha vazia mantém a guardada);
# "mascara": "email" mostra o campo mascarado na tela (<chave>_mascarado). Sem declaração: usuário e senha.
CAMPOS_PADRAO = [{"chave": "usuario", "rotulo": "Usuário", "tipo": "texto"},
                 {"chave": "senha", "rotulo": "Senha", "tipo": "senha"}]
_CAMPOS: dict[str, list[dict]] = {}


def registrar_campos(op_id: str, campos: list[dict]) -> None:
    """Os campos do login da operadora (o registro das operadoras chama ao carregar cada uma)."""
    _CAMPOS[op_id] = [dict(c) for c in campos]


def campos_login(op_id: str) -> list[dict]:
    return _CAMPOS.get(op_id, CAMPOS_PADRAO)


class ErroCredencial(ValueError):
    def __init__(self, problemas: list[str]):
        super().__init__("; ".join(problemas))
        self.problemas = problemas


class CofreMemoria(KeyringBackend):
    """Cofre que só existe enquanto o processo roda: testes e simulador (config `teste: cofre: memoria`)."""
    priority = -1         # nunca é escolhido sozinho no lugar do cofre do Windows
    _dados: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self._dados.get((service, username))

    def set_password(self, service, username, password):
        self._dados[(service, username)] = password

    def delete_password(self, service, username):
        if self._dados.pop((service, username), None) is None:
            raise PasswordDeleteError("nada guardado")

    @classmethod
    def esvaziar(cls) -> None:
        cls._dados.clear()


# ------------------------------------------------------------------ valores que nunca podem aparecer
_SEGREDOS: set[str] = set()
_VISIVEIS: set[str] = set()     # os que a página pode mostrar (CPF, e-mail): cobertos no print do mapa


def lembrar_segredos(*valores: str, visiveis: bool = False) -> None:
    for v in valores:
        if v and len(v) >= 4:
            _SEGREDOS.add(v)
            if visiveis:
                _VISIVEIS.add(v)


def ocultar(texto: str) -> str:
    """Troca por ••• qualquer valor de login que o robô leu do cofre (ou código digitado) neste processo."""
    if not texto or not _SEGREDOS:
        return texto
    for s in sorted(_SEGREDOS, key=len, reverse=True):
        texto = texto.replace(s, "•••")
    return texto


def segredos_visiveis() -> list[str]:
    return sorted(_VISIVEIS)


class FiltroSegredos(logging.Filter):
    """No logger do robô: nenhuma linha (nem traceback) sai com um valor de login."""

    def filter(self, record: logging.LogRecord) -> bool:
        if _SEGREDOS:
            texto = record.getMessage()
            if record.exc_info:
                texto += "\n" + "".join(traceback.format_exception(*record.exc_info)).rstrip()
                record.exc_info, record.exc_text = None, None
            record.msg, record.args = ocultar(texto), None
        return True


# ------------------------------------------------------------------ formatos
def so_digitos(texto: str) -> str:
    return "".join(ch for ch in str(texto or "") if ch.isdigit())


def cpf_valido(d: str) -> bool:
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if str((soma * 10 % 11) % 10) != d[n]:
            return False
    return True


def formatar_cpf(d: str) -> str:
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}" if len(d) == 11 else d


def _formatos(valor: str, tipo: str | None) -> list[str]:
    """Como a página do portal pode mostrar o documento (para esconder também esses jeitos no log e no mapa)."""
    if tipo in ("cpf", "cpf_cnpj") and len(valor) == 11:
        return [formatar_cpf(valor)]
    if tipo == "cpf_cnpj" and len(valor) == 14:
        return [f"{valor[:2]}.{valor[2:5]}.{valor[5:8]}/{valor[8:12]}-{valor[12:]}"]
    return []


def mascarar_email(email: str) -> str:
    """"corretor@exemplo.com.br" -> "co***@***.com.br"."""
    usuario, _, dominio = email.partition("@")
    fim = dominio[dominio.find("."):] if "." in dominio else ""
    return f"{usuario[:2]}***@***{fim}"


# ------------------------------------------------------------------ cofre
class Cofre:
    """O login de uma operadora no cofre: serviço "NewportCotacoes/<operadora>", usuário do Windows.
    Os campos (e a validação de cada um) são os que a operadora declarou."""

    def __init__(self, op_id: str, memoria: bool = False):
        self.servico = f"{PREFIXO_SERVICO}/{op_id}"
        self.usuario = getpass.getuser()
        self.campos = campos_login(op_id)
        self._chaveiro = CofreMemoria() if memoria else keyring.get_keyring()

    def _ler(self) -> dict:
        try:
            bruto = self._chaveiro.get_password(self.servico, self.usuario)
            dados = json.loads(bruto) if bruto else {}
        except Exception:  # noqa: BLE001  (cofre indisponível ou conteúdo estranho: como se não houvesse)
            return {}
        completo = isinstance(dados, dict) and all(dados.get(c["chave"]) for c in self.campos)
        return dados if completo else {}

    def _mascarados(self, d: dict) -> dict:
        return {f"{c['chave']}_mascarado": (mascarar_email(d[c["chave"]]) if d else "")
                for c in self.campos if c.get("mascara") == "email"}

    def _gravar(self, dados: dict) -> None:
        self._chaveiro.set_password(self.servico, self.usuario, json.dumps(dados, ensure_ascii=False))

    def situacao(self) -> dict:
        """O que a tela pode saber: nunca um valor de login inteiro (só os mascarados que a operadora pede)."""
        d = self._ler()
        if not d:
            return {"guardadas": False, **self._mascarados({}), "quando": "", "recusadas": False}
        return {"guardadas": True, **self._mascarados(d), "quando": d.get("quando", ""),
                "recusadas": bool(d.get("recusadas_em"))}

    def guardar(self, *valores: str, senha_max: int | None = None, **por_nome: str) -> None:
        """Os valores na ordem dos campos da operadora (ou por nome). Senha vazia mantém a guardada (o campo da
        tela vem vazio). As mensagens nunca repetem o valor. `senha_max`: o limite do campo de senha no portal
        (maior seria cortado lá e recusado)."""
        dados = {c["chave"]: "" for c in self.campos}
        for campo, valor in zip(self.campos, valores):
            dados[campo["chave"]] = valor
        dados.update({k: v for k, v in por_nome.items() if k in dados})
        atual = self._ler()
        problemas = []
        for c in self.campos:
            # Espaço no começo ou no fim fica como veio: a tela avisa e pede confirmação antes (não remove sozinha).
            v = str(dados[c["chave"]] or "")
            tipo = c.get("tipo", "texto")
            if tipo == "cpf":
                v = so_digitos(v)
                if not cpf_valido(v):
                    problemas.append("CPF inválido: confira os 11 dígitos")
            elif tipo == "cpf_cnpj":
                v = so_digitos(v)
                from .texto import cnpj_valido
                if not (cpf_valido(v) or (len(v) == 14 and cnpj_valido(v))):
                    problemas.append("CPF/CNPJ inválido: confira os dígitos")
            elif tipo == "email":
                if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v.strip()):
                    problemas.append("E-mail inválido")
            elif tipo == "senha":
                if not v and not atual:
                    problemas.append("Digite a senha")
                if v and senha_max and len(v) > senha_max:
                    problemas.append(f"A senha do portal tem no máximo {senha_max} caracteres (é o limite do campo "
                                     "no portal). Confira se não entrou um espaço a mais")
            elif not v.strip():
                problemas.append(f"Digite {c.get('rotulo', c['chave']).lower()}")
            dados[c["chave"]] = v
        if problemas:
            raise ErroCredencial(problemas)
        senhas = [c["chave"] for c in self.campos if c.get("tipo") == "senha"]
        novo = {c["chave"]: dados[c["chave"]] or (atual.get(c["chave"], "") if c["chave"] in senhas else "")
                for c in self.campos}
        novo["quando"] = datetime.now().isoformat(timespec="seconds")
        # Recusado pelo portal: só volta a tentar quando o corretor digitar a senha de novo (ou mudar o
        # usuário). Guardar sem mexer em nada não libera: evita bloquear a conta.
        identificacao = [c["chave"] for c in self.campos if c["chave"] not in senhas]
        if (not any(dados[k] for k in senhas) and atual.get("recusadas_em")
                and all(dados[k] == atual.get(k) for k in identificacao)):
            novo["recusadas_em"] = atual["recusadas_em"]
        self._gravar(novo)

    def apagar(self) -> None:
        try:
            self._chaveiro.delete_password(self.servico, self.usuario)
        except PasswordDeleteError:
            pass

    def ler(self) -> dict | None:
        """Só para o robô, na hora de entrar no portal. Nunca imprima nem registre o retorno."""
        d = self._ler()
        if not d:
            return None
        for c in self.campos:            # a página pode mostrar o usuário (ex.: CPF, e-mail): coberto no print
            v = d[c["chave"]]
            if c.get("tipo") == "senha":
                lembrar_segredos(v)
            else:
                lembrar_segredos(v, *_formatos(v, c.get("tipo")), visiveis=True)
        return d

    def marcar_recusadas(self) -> None:
        d = self._ler()
        if d:
            d["recusadas_em"] = datetime.now().isoformat(timespec="seconds")
            self._gravar(d)


def cofre(cfg: dict, op_id: str) -> Cofre:
    """O cofre que a configuração manda usar: o do Windows, ou o de memória nos testes e no simulador."""
    return Cofre(op_id, memoria=(cfg.get("teste") or {}).get("cofre") == "memoria")


MENSAGENS_LOGIN = {
    "sem_credenciais": "Cadastre o login da {op} na engrenagem do robô.",
    "recusadas": "A {op} recusou o login guardado. Por segurança o robô não tenta de novo: confira e "
                 "guarde a senha outra vez na engrenagem do robô.",
    "captcha": "O portal da {op} pediu um captcha. O robô não resolve captcha: entre uma vez no portal "
               "pelo seu navegador e tente de novo.",
    "troca_senha": "O portal da {op} pede para trocar a senha. Troque no portal pelo seu navegador e "
                   "guarde a nova na engrenagem do robô.",
    "codigo": "O código de verificação não chegou a tempo ou não foi aceito. Tente de novo.",
    "senha_comprida": "A senha guardada tem mais caracteres do que o portal da {op} aceita, então o robô nem tentou "
                      "entrar. Confira se não entrou um espaço a mais e guarde de novo na engrenagem do robô.",
    "sem_resposta": "O portal da {op} não respondeu ao login. Tente de novo em alguns minutos.",
    "falha": "Não consegui preencher o login no portal da {op} (a tela mudou?). Ligue \"Mostrar a janela "
             "do portal\" e os prints em Robôs para calibrar.",
}


def mensagem_login(motivo: str, nome_operadora: str, proprias: dict | None = None) -> str:
    """Frase fixa para o corretor. `proprias`: as mensagens que só a operadora tem (Operadora.mensagens_login)."""
    texto = (proprias or {}).get(motivo) or MENSAGENS_LOGIN.get(motivo, MENSAGENS_LOGIN["falha"])
    return texto.format(op=nome_operadora)
