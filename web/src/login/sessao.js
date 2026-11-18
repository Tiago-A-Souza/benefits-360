/** Ponto único da sessão. Com VITE_SUPABASE_URL: Auth real. Sem URL: modo demonstração (testes/offline). */

import { obterCliente, supabaseConfigurado } from "./supabase";

export const CHAVE_SESSAO = "benefits_demo_logado";

const AVISO_CONFIRMACAO =
  "Enviamos um e-mail de confirmação. Confirme e depois faça login.";
const AVISO_RECUPERAR = "Enviamos um e-mail para redefinir a senha.";

export function mensagemCamposLogin(email, senha) {
  if (!(email || "").trim() || !senha) {
    return "Informe o e-mail e a senha.";
  }
  return "";
}

export function mensagemCamposCriarConta(email, senha, confirmar) {
  if (!(email || "").trim() || !senha) {
    return "Informe o e-mail e a senha.";
  }
  if (String(senha).length < 8) {
    return "A senha deve ter pelo menos 8 caracteres.";
  }
  if (senha !== confirmar) {
    return "As senhas não coincidem.";
  }
  return "";
}

export function mensagemErroAuth(erro) {
  const codigo = String(erro?.code || "").toLowerCase();
  const texto = String(erro?.message || "").toLowerCase();
  if (
    codigo === "email_not_confirmed" ||
    texto.includes("email not confirmed")
  ) {
    return "Confirme o e-mail antes de entrar.";
  }
  if (
    codigo === "invalid_credentials" ||
    texto.includes("invalid login credentials")
  ) {
    return "E-mail ou senha incorretos.";
  }
  if (
    codigo === "user_already_exists" ||
    texto.includes("already registered") ||
    texto.includes("user already registered")
  ) {
    return "Este e-mail já está cadastrado.";
  }
  if (codigo === "weak_password" || texto.includes("at least 8")) {
    return "A senha deve ter pelo menos 8 caracteres.";
  }
  if (
    codigo === "over_email_send_rate_limit" ||
    texto.includes("rate limit") ||
    texto.includes("too many")
  ) {
    return "Tente novamente em alguns minutos.";
  }
  if (
    codigo === "validation_failed" ||
    texto.includes("invalid email") ||
    texto.includes("unable to validate email")
  ) {
    return "Informe um e-mail válido.";
  }
  return "Não foi possível concluir. Tente de novo.";
}

export function sessaoAtiva() {
  if (supabaseConfigurado()) return false;
  try {
    return sessionStorage.getItem(CHAVE_SESSAO) === "1";
  } catch {
    return false;
  }
}

export function entrarDemo() {
  sessionStorage.setItem(CHAVE_SESSAO, "1");
}

export async function sairSessao() {
  try {
    sessionStorage.removeItem(CHAVE_SESSAO);
  } catch {
    /* ignore */
  }
  const cliente = obterCliente();
  if (cliente) {
    await cliente.auth.signOut();
  }
}

function emailConfirmado(user) {
  return Boolean(user?.email_confirmed_at || user?.confirmed_at);
}

function sessaoUsavel(session) {
  if (!session?.user) return null;
  if (!emailConfirmado(session.user)) return null;
  return session;
}

export const EVENTO_NAO_AUTORIZADO = "benefits:nao-autorizado";

export function avisarNaoAutorizado() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(EVENTO_NAO_AUTORIZADO));
}

export async function obterAccessToken() {
  if (!supabaseConfigurado()) return null;
  const cliente = obterCliente();
  if (!cliente) return null;
  const { data } = await cliente.auth.getSession();
  return data?.session?.access_token || null;
}

export async function obterSessao() {
  if (!supabaseConfigurado()) {
    return sessaoAtiva() ? { demo: true } : null;
  }
  const cliente = obterCliente();
  if (!cliente) return null;
  const { data } = await cliente.auth.getSession();
  return sessaoUsavel(data?.session);
}

export function ouvirSessao(aoMudar) {
  const cliente = obterCliente();
  if (!cliente) return () => {};
  const { data } = cliente.auth.onAuthStateChange((_evento, session) => {
    aoMudar(sessaoUsavel(session));
  });
  return () => data.subscription.unsubscribe();
}

export async function entrar(email, senha) {
  const campo = mensagemCamposLogin(email, senha);
  if (campo) return { ok: false, erro: campo };
  if (!supabaseConfigurado()) {
    entrarDemo();
    return { ok: true };
  }
  const cliente = obterCliente();
  if (!cliente) {
    return { ok: false, erro: "Login não está configurado neste computador." };
  }
  const { data, error } = await cliente.auth.signInWithPassword({
    email: String(email).trim(),
    password: senha,
  });
  if (error) return { ok: false, erro: mensagemErroAuth(error) };
  const session = data?.session;
  if (!sessaoUsavel(session)) {
    await cliente.auth.signOut();
    return { ok: false, erro: "Confirme o e-mail antes de entrar." };
  }
  return { ok: true };
}

export async function criarConta(email, senha, confirmar) {
  const campo = mensagemCamposCriarConta(email, senha, confirmar ?? senha);
  if (campo) return { ok: false, erro: campo };
  if (!supabaseConfigurado()) {
    return { ok: false, erro: "Para criar conta, configure o login (Supabase)." };
  }
  const cliente = obterCliente();
  if (!cliente) {
    return { ok: false, erro: "Login não está configurado neste computador." };
  }
  const origem = typeof window !== "undefined" ? window.location.origin : undefined;
  const { data, error } = await cliente.auth.signUp({
    email: String(email).trim(),
    password: senha,
    options: origem ? { emailRedirectTo: origem } : undefined,
  });
  if (error) return { ok: false, erro: mensagemErroAuth(error) };
  if (data?.user && Array.isArray(data.user.identities) && data.user.identities.length === 0) {
    return { ok: false, erro: "Este e-mail já está cadastrado." };
  }
  if (data?.session) {
    await cliente.auth.signOut();
  }
  return { ok: true, aviso: AVISO_CONFIRMACAO };
}

export async function recuperarSenha(email) {
  if (!(email || "").trim()) {
    return { ok: false, erro: "Informe o e-mail." };
  }
  if (!supabaseConfigurado()) {
    return { ok: false, erro: "Para recuperar a senha, configure o login (Supabase)." };
  }
  const cliente = obterCliente();
  if (!cliente) {
    return { ok: false, erro: "Login não está configurado neste computador." };
  }
  const origem = typeof window !== "undefined" ? window.location.origin : undefined;
  const { error } = await cliente.auth.resetPasswordForEmail(String(email).trim(), {
    redirectTo: origem,
  });
  if (error) return { ok: false, erro: mensagemErroAuth(error) };
  return { ok: true, aviso: AVISO_RECUPERAR };
}
