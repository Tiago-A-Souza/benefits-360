/** Ponto único da sessão visual (Fase 2). Na Fase 3, trocar só este arquivo para o Supabase. */

export const CHAVE_SESSAO = "benefits_demo_logado";

export function sessaoAtiva() {
  try {
    return sessionStorage.getItem(CHAVE_SESSAO) === "1";
  } catch {
    return false;
  }
}

export function entrarDemo() {
  sessionStorage.setItem(CHAVE_SESSAO, "1");
}

export function sairSessao() {
  try {
    sessionStorage.removeItem(CHAVE_SESSAO);
  } catch {
    /* ignore */
  }
}

/** Valida só preenchimento. Não envia, não grava e não registra a senha. */
export function mensagemCamposLogin(email, senha) {
  if (!(email || "").trim() || !senha) {
    return "Informe o e-mail e a senha.";
  }
  return "";
}
