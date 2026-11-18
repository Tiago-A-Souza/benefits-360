import { useState } from "react";
import {
  criarConta,
  entrar,
  mensagemCamposCriarConta,
  mensagemCamposLogin,
  recuperarSenha,
} from "./sessao";
import "./TelaLogin.css";

function MarcaFundo() {
  return (
    <svg
      className="tela-login-marca-fundo"
      viewBox="0 0 348 481"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="turyaFundo" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f8a352" stopOpacity="0.17" />
          <stop offset="0.55" stopColor="#ee6a26" stopOpacity="0.11" />
          <stop offset="1" stopColor="#e24a1b" stopOpacity="0.05" />
        </linearGradient>
      </defs>
      <path
        d="M167.2,96.7 L163.0,98.6 L88.8,147.5 L66.0,165.9 L50.8,181.0 L42.8,190.2 L33.7,202.5 L25.5,216.0 L18.8,229.0 L14.1,241.0 L10.7,252.5 L8.2,264.8 L7.0,274.2 L6.5,292.0 L8.3,312.5 L10.9,326.0 L14.7,339.2 L19.8,352.2 L26.5,365.2 L32.2,373.8 L41.4,385.0 L56.5,399.3 L77.0,415.1 L163.8,470.6 L170.0,473.3 L172.6,472.1 L173.7,468.7 L173.3,449.5 L174.7,419.0 L173.6,412.0 L169.0,407.8 L139.8,389.5 L118.8,374.4 L109.5,366.0 L98.2,354.0 L88.3,339.8 L79.3,320.8 L75.0,306.8 L70.8,284.0 L74.0,262.8 L78.5,248.5 L86.3,232.8 L93.2,223.2 L105.8,209.0 L121.5,195.1 L140.2,181.5 L167.5,164.3 L170.1,161.5 L170.7,156.8 L170.2,101.0 L169.4,97.9Z"
        fill="url(#turyaFundo)"
      />
      <path
        d="M176.3,6.8 L173.5,8.4 L172.5,12.3 L172.5,67.8 L173.2,72.0 L176.3,75.1 L201.8,90.8 L221.8,105.9 L234.7,117.8 L250.2,135.8 L260.9,151.8 L269.8,171.0 L275.1,190.0 L277.0,201.2 L276.2,207.8 L263.7,234.5 L251.4,256.0 L237.3,275.5 L227.5,286.4 L212.0,300.1 L198.8,310.1 L181.3,320.0 L178.0,323.5 L177.0,328.0 L177.0,381.2 L178.0,384.6 L180.3,385.6 L184.2,384.2 L214.5,365.0 L254.2,338.5 L278.5,319.4 L302.7,295.7 L315.3,279.2 L321.1,270.0 L327.9,256.2 L331.7,246.5 L335.3,234.0 L338.9,215.5 L340.7,191.8 L338.0,163.5 L332.3,141.8 L321.7,118.5 L314.3,107.0 L305.4,95.5 L288.8,78.9 L269.0,63.8 L237.0,43.1 L180.0,8.1Z"
        fill="url(#turyaFundo)"
      />
      <circle cx="174.2" cy="238.9" r="33.5" fill="#ffffff" fillOpacity="0.09" />
    </svg>
  );
}

function Olho({ aberto }) {
  return aberto ? (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#526277" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 3l18 18" />
      <path d="M10.6 6.2A10.6 10.6 0 0 1 12 6c6 0 9.5 6 9.5 6a17 17 0 0 1-3 3.7M6.4 7.6A17 17 0 0 0 2.5 12S6 18 12 18a10 10 0 0 0 4-.8" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    </svg>
  ) : (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#526277" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2.5 12S6 6 12 6s9.5 6 9.5 6-3.5 6-9.5 6S2.5 12 2.5 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

export default function TelaLogin({ onEntrar }) {
  const [modo, setModo] = useState("entrar");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [manter, setManter] = useState(false);
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [enviando, setEnviando] = useState(false);

  const criando = modo === "criar";

  function irModo(proximo) {
    setModo(proximo);
    setErro("");
    setAviso("");
    setSenha("");
    setConfirmar("");
  }

  async function enviar(ev) {
    ev.preventDefault();
    setAviso("");
    const msg = criando
      ? mensagemCamposCriarConta(email, senha, confirmar)
      : mensagemCamposLogin(email, senha);
    if (msg) {
      setErro(msg);
      return;
    }
    setErro("");
    setEnviando(true);
    try {
      if (criando) {
        const r = await criarConta(email, senha, confirmar);
        if (!r.ok) {
          setErro(r.erro);
          return;
        }
        setAviso(r.aviso);
        setModo("entrar");
        setSenha("");
        setConfirmar("");
        return;
      }
      const r = await entrar(email, senha);
      if (!r.ok) {
        setErro(r.erro);
        return;
      }
      onEntrar?.();
    } finally {
      setEnviando(false);
    }
  }

  async function esqueciSenha() {
    setErro("");
    setAviso("");
    setEnviando(true);
    try {
      const r = await recuperarSenha(email);
      if (!r.ok) {
        setErro(r.erro);
        return;
      }
      setAviso(r.aviso);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="tela-login">
      <header className="tela-login-topo">
        <div className="tela-login-topo-inner">
          <div className="tela-login-marca">
            <img src="/login-assets/turya-logo-recortado.png" alt="Turya" />
          </div>
          <nav className="tela-login-nav" aria-label="Principal">
            <button
              type="button"
              className={`tela-login-nav-item${criando ? " is-off" : ""}`}
              aria-pressed={!criando}
              onClick={() => irModo("entrar")}
            >
              ENTRAR
            </button>
            <button
              type="button"
              className={`tela-login-nav-item${criando ? "" : " is-off"}`}
              aria-pressed={criando}
              onClick={() => irModo("criar")}
            >
              CRIAR CONTA
            </button>
          </nav>
        </div>
      </header>

      <section className="tela-login-hero">
        <MarcaFundo />

        <div className="tela-login-grid">
          <div className="tela-login-copy">
            <div className="tela-login-copy-topo">
              <span className="tela-login-kicker">BENEFITS 360</span>
              <h1 className="tela-login-titulo">Estudos de saúde e cotações, em um só lugar.</h1>
              <p className="tela-login-lead">
                Compare planos, simule a rede credenciada e cote nas operadoras com a mesma
                ferramenta que você já usa no dia a dia.
              </p>
            </div>
            <ul className="tela-login-lista">
              <li>
                <span className="tela-login-bolinha" aria-hidden="true" />
                Compare planos e reajustes em estudos de renovação ou seguro novo
              </li>
              <li>
                <span className="tela-login-bolinha" aria-hidden="true" />
                Simule a rede credenciada por região e prestador
              </li>
              <li>
                <span className="tela-login-bolinha" aria-hidden="true" />
                Cote nas operadoras e baixe os PDFs sem digitar tudo de novo
              </li>
            </ul>
          </div>

          <form className="tela-login-cartao" onSubmit={enviar} noValidate>
            <div className="tela-login-cartao-topo">
              <h2>{criando ? "Crie sua conta" : "Acesse sua conta"}</h2>
              <p>
                {criando
                  ? "Use o e-mail da corretora. Depois confirme o e-mail para entrar."
                  : "Use o e-mail e a senha da sua corretora."}
              </p>
            </div>

            <div className="tela-login-campo">
              <label htmlFor="login-email">E-mail</label>
              <input
                id="login-email"
                name="email"
                type="email"
                autoComplete="username"
                placeholder="nome@corretora.com.br"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div className="tela-login-campo">
              <label htmlFor="login-senha">Senha</label>
              <div className="tela-login-senha-linha">
                <input
                  id="login-senha"
                  name="senha"
                  type={mostrarSenha ? "text" : "password"}
                  autoComplete={criando ? "new-password" : "current-password"}
                  placeholder={criando ? "Mínimo de 8 caracteres" : "Digite sua senha"}
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                />
                <button
                  type="button"
                  className="tela-login-olho"
                  aria-label={mostrarSenha ? "Ocultar senha" : "Mostrar senha"}
                  onClick={() => setMostrarSenha((v) => !v)}
                >
                  <Olho aberto={mostrarSenha} />
                </button>
              </div>
            </div>

            {criando ? (
              <div className="tela-login-campo">
                <label htmlFor="login-confirmar">Confirmar senha</label>
                <input
                  id="login-confirmar"
                  name="confirmar"
                  type={mostrarSenha ? "text" : "password"}
                  autoComplete="new-password"
                  placeholder="Repita a senha"
                  value={confirmar}
                  onChange={(e) => setConfirmar(e.target.value)}
                />
              </div>
            ) : (
              <div className="tela-login-acoes">
                <div className="tela-login-manter">
                  <input
                    id="login-manter"
                    type="checkbox"
                    checked={manter}
                    onChange={(e) => setManter(e.target.checked)}
                  />
                  <label htmlFor="login-manter">Manter conectado</label>
                </div>
                <button type="button" className="tela-login-link" onClick={esqueciSenha} disabled={enviando}>
                  Esqueci minha senha
                </button>
              </div>
            )}

            {erro ? (
              <p className="tela-login-erro" role="alert">
                {erro}
              </p>
            ) : null}
            {aviso ? (
              <p className="tela-login-aviso" role="status">
                {aviso}
              </p>
            ) : null}

            <button type="submit" className="tela-login-entrar" disabled={enviando}>
              {criando ? "Criar conta" : "Entrar"}
            </button>

            <div className="tela-login-rodape-cartao">
              {criando ? (
                <>
                  Já tem conta?{" "}
                  <button type="button" className="tela-login-link" onClick={() => irModo("entrar")}>
                    Entrar
                  </button>
                  . Depois de confirmar o e-mail, você entra direto no sistema.
                </>
              ) : (
                <>
                  Ainda não tem conta?{" "}
                  <button type="button" className="tela-login-link" onClick={() => irModo("criar")}>
                    Criar conta
                  </button>
                  . Confirme o e-mail que enviamos e acesse na hora — não precisa de aprovação.
                </>
              )}
            </div>
          </form>
        </div>
      </section>
    </div>
  );
}
