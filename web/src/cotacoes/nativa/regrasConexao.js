import { cnpjValido, cpfValido } from "./regrasNova";

export function campoCredenciais(telas) {
  for (const t of telas || []) {
    const c = (t.campos || []).find((x) => x.tipo === "credenciais");
    if (c) return c;
  }
  return null;
}

export function camposLoginPadrao() {
  return [
    { chave: "usuario", rotulo: "Usuário", tipo: "texto", artigo: "o" },
    { chave: "senha", rotulo: "Senha", tipo: "senha", artigo: "a" },
  ];
}

export function valoresLoginVazios(campos) {
  const v = {};
  for (const c of campos || []) v[c.chave] = "";
  return v;
}

export function limparSenhas(valores, campos) {
  const next = { ...valores };
  for (const c of campos || []) {
    if (c.tipo === "senha") next[c.chave] = "";
  }
  return next;
}

export function corpoLoginParaRobo(campos, valores) {
  const corpo = {};
  for (const c of campos || []) corpo[c.chave] = String((valores && valores[c.chave]) || "");
  return corpo;
}

export function validarLoginLocal(campos, valores, senhaMax) {
  const problemas = [];
  for (const c of campos || []) {
    const v = String((valores && valores[c.chave]) || "");
    if (c.tipo === "cpf" && v && !cpfValido(v)) problemas.push(`CPF inválido: confira os 11 dígitos (${c.rotulo}).`);
    if (c.tipo === "cpf_cnpj" && v && !cpfValido(v) && !cnpjValido(v)) {
      problemas.push(`CPF/CNPJ inválido: confira os dígitos (${c.rotulo}).`);
    }
    if (c.tipo === "senha" && senhaMax && v.length > senhaMax) {
      problemas.push(`A senha do portal tem no máximo ${senhaMax} caracteres (é o limite do campo no portal).`);
    }
  }
  return problemas;
}

export function camposComEspaco(campos, valores) {
  return (campos || []).filter((c) => {
    if (c.tipo === "cpf" || c.tipo === "cpf_cnpj") return false;
    const v = String((valores && valores[c.chave]) || "");
    return v && v !== v.trim();
  });
}

export function acaoLoginDoCartao(op, status, { atual, naFila } = {}) {
  const login = (op && op.login) || {};
  if (!login.guardadas) return { tipo: "cadastrar", rotulo: "Cadastrar o login" };
  if (login.recusadas) return { tipo: "atualizar", rotulo: "Atualizar a senha" };
  if (status === "desconectado") return { tipo: "testar", rotulo: "Testar login" };
  if (status === "conectado" || status === "ocupado") {
    const livre = status === "conectado" && !atual && !(naFila || []).length;
    return {
      tipo: "sair",
      rotulo: "Sair do portal agora",
      livre,
      title: livre
        ? "O robô sai do portal e fecha a janela; na próxima cotação ele entra sozinho de novo."
        : "Dá para sair do portal quando o robô parar.",
    };
  }
  return null;
}
