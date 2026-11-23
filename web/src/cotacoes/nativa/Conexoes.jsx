import { useState } from "react";
import { chamarRpa } from "../rpaClient";
import CartaoLogin from "./CartaoLogin";
import LogoOperadora from "./LogoOperadora";
import { attrsCartaoOperadora } from "./operadoras";
import { acaoLoginDoCartao } from "./regrasConexao";
import { CONEXAO, resumoDoRobo } from "./regrasNova";
import { asArray, camposDaOperadora } from "../../util/colecao";

export default function Conexoes({
  operadoras,
  indisponiveis = [],
  conexao,
  urlRobo,
  aviso,
  onReloadOps,
  trabalhoAtual,
  naFila = [],
  opLoginInicial = null,
  onConfigurar,
}) {
  const [aberto, setAberto] = useState(opLoginInicial);

  async function testar(opId) {
    try {
      const r = await chamarRpa("POST", `/api/conectar/${opId}`);
      aviso?.("Testando o login: o robô entra no portal sozinho e para na tela de módulos.");
      onReloadOps?.();
      return r;
    } catch (e) {
      aviso?.(e.message, "erro");
      return null;
    }
  }

  async function sair(opId) {
    try {
      const r = await chamarRpa("POST", `/api/sair/${opId}`);
      const op = (operadoras || []).find((o) => o.id === opId);
      const quem = ((op && op.textos) || {}).login_livre || "o seu login";
      aviso?.(
        r && r.ja_fora
          ? "O robô já estava fora do portal."
          : `Saindo do portal: ${quem} fica livre para usar o portal no navegador. Na próxima cotação o robô entra sozinho de novo.`,
      );
      onReloadOps?.();
    } catch (e) {
      aviso?.(e.message, "erro");
    }
  }

  return (
    <div>
      <h1>Conexões</h1>
      <p className="muted">
        Status de cada operadora e o login do portal, guardado no cofre deste computador. A configuração
        completa do robô (o que ele preenche em cada tela) fica em Ajustes dos robôs.
      </p>
      <div className="nativa-robos">
        {asArray(operadoras).map((op) => {
          const st = (conexao && conexao[op.id]) || op.conexao || "desconectado";
          const acao = acaoLoginDoCartao(op, st, { atual: trabalhoAtual, naFila });
          const padrao = (c) => (camposDaOperadora(op).find((x) => x.chave === c) || {}).padrao;
          const marca = attrsCartaoOperadora(op.id, aberto === op.id);
          return (
            <article
              key={op.id}
              className={`nativa-robo-cartao cartao ${marca.className}`}
              style={marca.style}
              data-cor-op={marca["data-cor-op"]}
            >
              <div className="nativa-robo-topo nativa-op-cabeca">
                <div>
                  <h2>
                    <LogoOperadora operadora={op.id} tamanho="md" />
                  </h2>
                  <div className="muted">{op.produto}</div>
                </div>
                <button
                  type="button"
                  className="nativa-engrenagem"
                  title="Configurar o robô"
                  aria-label={`Configurar o robô da ${op.nome}`}
                  onClick={() => onConfigurar?.(op.id)}
                >
                  ⚙
                </button>
              </div>
              <p className="muted">{resumoDoRobo(op, padrao, { produto: op.produto_portal })}.</p>
              <div className="nativa-robo-pe">
                <span className={`nativa-conexao-status nativa-conexao-status--${st}`}>
                  <span className={`nativa-ponto nativa-ponto--${st}`} />
                  {CONEXAO[st] || st}
                </span>
                <div className="nativa-acoes-linha">
                  {acao?.tipo === "cadastrar" || acao?.tipo === "atualizar" ? (
                    <button type="button" className="secundario btn-compacto" onClick={() => setAberto(op.id)}>
                      {acao.rotulo}
                    </button>
                  ) : null}
                  {acao?.tipo === "testar" ? (
                    <button type="button" className="secundario btn-compacto" onClick={() => testar(op.id)}>
                      {acao.rotulo}
                    </button>
                  ) : null}
                  {acao?.tipo === "sair" ? (
                    <button
                      type="button"
                      className="secundario btn-compacto"
                      disabled={!acao.livre}
                      title={acao.title}
                      onClick={() => sair(op.id)}
                    >
                      {acao.rotulo}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="secundario btn-compacto"
                    onClick={() => onConfigurar?.(op.id)}
                  >
                    Configurar
                  </button>
                </div>
              </div>
              {aberto === op.id ? (
                <CartaoLogin
                  opId={op.id}
                  nomeOp={op.nome}
                  aviso={aviso}
                  focar
                  onGuardado={() => onReloadOps?.()}
                  onTestar={() => testar(op.id)}
                />
              ) : null}
            </article>
          );
        })}
        {(indisponiveis || []).map((op) => (
          <article key={op.id || op.nome} className="nativa-robo-cartao cartao nativa-robo-indisponivel">
            <h2>{op.nome}</h2>
            <p className="muted">
              O robô desta operadora não carregou. As outras operadoras funcionam normalmente.{" "}
              <span className="muted">Motivo: {op.motivo}</span>
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}
