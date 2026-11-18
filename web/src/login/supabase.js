import { createClient } from "@supabase/supabase-js";

/** Cliente do browser. Só URL + chave anon. Nunca service_role. */

export function urlSupabase() {
  return String(import.meta.env.VITE_SUPABASE_URL || "").trim();
}

/** Ligado quando a URL existe. Sem URL, o login cai no modo demonstração. */
export function supabaseConfigurado() {
  return Boolean(urlSupabase());
}

let cliente = null;

export function obterCliente() {
  if (!supabaseConfigurado()) return null;
  const chave = String(import.meta.env.VITE_SUPABASE_ANON_KEY || "").trim();
  if (!chave) return null;
  if (!cliente) {
    cliente = createClient(urlSupabase(), chave, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
  }
  return cliente;
}
