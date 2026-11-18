import { useEffect, useState } from "react";
import { chamarRpa } from "../rpaClient";
import { useConfirmacao } from "./Confirmacao";
import {
  campoCredenciais,
  camposComEspaco,
  camposLoginPadrao,
  corpoLoginParaRobo,
  validarLoginLocal,
  valoresLoginVazios,
} from "./regrasConexao";
import { formatarCpf, formatarCpfOuCnpj, quando } from "./regrasNova";

/**
 * Login do portal → cofre do robô local (POST /api/credenciais/{op}).
 * A senha só existe no estado do formulário e no body dessa requisição.
 */
export default function CartaoLogin({ opId, nomeOp, aviso, onGuardado, onTestar, focar }) {
  const [campos, setCampos] = useState(camposLoginPadrao());
  const [senhaMax, setSenhaMax] = useState(null);
  const [valores, setValores] = useState(() => valoresLoginVazios(camposLoginPadrao()));
  const [sit, setSit] = useState({ guardadas: false, recusadas: false, quando: "" });
  const [confirmar, modal] = useConfirmacao();

  useEffect(() => {
    let vivo = true;
    Promise.all([
      chamarRpa("GET", `/api/robos/${opId}`).catch(() => null),
      chamarRpa("GET", `/api/credenciais/${opId}`),
    ])
      .then(([robo, s]) => {
        if (!vivo) return;
        const decl = campoCredenciais(robo && robo.telas);
        const lista = (decl && decl.campos) || camposLoginPadrao();
        setCampos(lista);
        setSenhaMax(decl && decl.senha_max ? Number(decl.senha_max) : null);
        setValores(valoresLoginVazios(lista));
        setSit(s || { guardadas: false, recusadas: false, quando: "" });
      })
      .catch((e) => vivo && aviso?.(e.message, "erro"));
    return () => {
      vivo = false;
    };
  }, [opId, aviso]);

  useEffect(() => {
    if (!focar) return;
    const el = document.querySelector(`#login-${opId}-` + (campos[0] ? campos[0].chave : ""));
    el?.focus();
  }, [focar, campos, opId]);

  function mostrar(s) {
    setSit(s);
    setValores(valoresLoginVazios(campos));
  }

  async function guardar(ev) {
    ev.preventDefault();
    const problemas = validarLoginLocal(campos, valores, senhaMax);
    if (problemas.length) {
      aviso?.(problemas[0], "erro");
      return;
    }
    const comEspaco = camposComEspaco(campos, valores);
    let envio = valores;
    if (comEspaco.length) {
      const nomes = comEspaco.map((c) => `${c.artigo || "o"} ${(c.rotulo || c.chave).toLowerCase()}`).join(" e ");
      const maiuscula = (t) => t[0].toUpperCase() + t.slice(1);
      const escolha = await confirmar({
        titulo: `${maiuscula(nomes)} ${comEspaco.length > 1 ? "começam ou terminam" : "começa ou termina"} com espaço`,
        texto: [
          "Espaço no começo ou no fim costuma entrar sem querer (ao copiar e colar). O robô digita no portal exatamente o que estiver guardado, e o portal pode recusar o login.",
          `Confira ${nomes}. O robô não tira os espaços sozinho.`,
        ],
        ok: "Guardar assim mesmo",
        principal: false,
        alternativa: "Tirar os espaços",
        cancelar: "Voltar",
      });
      if (!escolha) return;
      if (escolha === "alternativa") {
        envio = { ...valores };
        for (const c of comEspaco) envio[c.chave] = String(envio[c.chave] || "").trim();
      }
    }
    const corpo = corpoLoginParaRobo(campos, envio);
    try {
      const r = await chamarRpa("POST", `/api/credenciais/${opId}`, corpo);
      mostrar(r);
      aviso?.("Login guardado no cofre do Windows. Use “Testar login” para conferir.");
      onGuardado?.(r);
    } catch (e) {
      aviso?.(e.message, "erro");
    } finally {
      setValores(valoresLoginVazios(campos));
    }
  }

  async function apagar() {
    const ok = await confirmar({
      titulo: `Apagar o login da ${nomeOp} deste computador?`,
      texto: ["O robô deixa de entrar no portal até alguém guardar um login de novo.", "Faça isso ao sair da Newport."],
      ok: "Apagar credenciais",
      principal: false,
    });
    if (!ok) return;
    try {
      const r = await chamarRpa("DELETE", `/api/credenciais/${opId}`);
      mostrar(r);
      aviso?.("Login apagado do cofre do Windows.");
      onGuardado?.(r);
    } catch (e) {
      aviso?.(e.message, "erro");
    }
  }

  const mascarados = campos
    .filter((c) => c.mascara && sit[`${c.chave}_mascarado`])
    .map((c) => `${(c.rotulo || c.chave).toLowerCase()} ${sit[`${c.chave}_mascarado`]}`);
  const textoSit = !sit.guardadas
    ? `Nenhum login guardado. Sem ele o robô não entra no portal da ${nomeOp}.`
    : sit.recusadas
      ? "O portal recusou este login. O robô não tenta de novo até você guardar a senha outra vez."
      : `Login guardado${sit.quando ? ` ${quando(sit.quando)}` : ""}${mascarados.length ? ` (${mascarados.join(", ")})` : ""}.`;

  return (
    <form className="nativa-login-portal" autoComplete="off" onSubmit={guardar}>
      {modal}
      <p className={`nativa-login-estado${sit.recusadas ? " nativa-login-estado--erro" : ""}`} role="status">
        {textoSit}
      </p>
      <div className="nativa-login-campos">
        {campos.map((c) => {
          const id = `login-${opId}-${c.chave}`;
          const tipo = c.tipo === "senha" ? "password" : c.tipo === "email" ? "email" : "text";
          let placeholder = `${c.artigo || "o"} ${(c.rotulo || c.chave).toLowerCase()} do portal`;
          if (c.tipo === "senha") placeholder = sit.guardadas ? `${(c.rotulo || "senha").toLowerCase()} guardada` : "";
          else if (c.mascara && sit.guardadas) placeholder = sit[`${c.chave}_mascarado`] || placeholder;
          else if (sit.guardadas) placeholder = `${c.rotulo} guardado (digite para trocar)`;
          else if (c.tipo === "cpf") placeholder = "000.000.000-00";
          else if (c.tipo === "cpf_cnpj") placeholder = "CPF ou CNPJ";
          return (
            <label key={c.chave} htmlFor={id}>
              {c.rotulo || c.chave}
              <input
                className="campo"
                id={id}
                name={`np-login-${opId}-${c.chave}`}
                type={tipo}
                autoComplete={c.tipo === "senha" ? "new-password" : "off"}
                spellCheck={false}
                inputMode={c.tipo === "cpf" || c.tipo === "cpf_cnpj" ? "numeric" : undefined}
                value={valores[c.chave] || ""}
                placeholder={placeholder}
                onChange={(e) => {
                  let v = e.target.value;
                  if (c.tipo === "cpf") v = formatarCpf(v);
                  if (c.tipo === "cpf_cnpj") v = formatarCpfOuCnpj(v);
                  setValores((prev) => ({ ...prev, [c.chave]: v }));
                }}
              />
            </label>
          );
        })}
      </div>
      {senhaMax ? <p className="muted">A senha do portal tem até {senhaMax} caracteres.</p> : null}
      <div className="nativa-acoes-linha">
        <button type="submit">Guardar</button>
        <button
          type="button"
          className="secundario"
          disabled={!sit.guardadas || sit.recusadas}
          onClick={() => onTestar?.()}
        >
          Testar login
        </button>
        <button type="button" className="secundario" disabled={!sit.guardadas} onClick={apagar}>
          Apagar credenciais
        </button>
      </div>
    </form>
  );
}
