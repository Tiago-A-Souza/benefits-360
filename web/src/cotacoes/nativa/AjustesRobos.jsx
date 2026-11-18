import { useEffect, useState } from "react";
import { chamarRpa } from "../rpaClient";
import { CONEXAO, resumoDoRobo } from "./regrasNova";

export default function AjustesRobos({
  operadoras,
  indisponiveis = [],
  conexao,
  aviso,
  onConfigurar,
  onLogin,
}) {
  const [geral, setGeral] = useState(null);

  useEffect(() => {
    let vivo = true;
    chamarRpa("GET", "/api/geral")
      .then((d) => {
        if (vivo) setGeral(d);
      })
      .catch((e) => aviso?.(e.message, "erro"));
    return () => {
      vivo = false;
    };
  }, [aviso]);

  async function setAjuste(chave, valor, msg) {
    try {
      await chamarRpa("PUT", "/api/geral", { geral: { [chave]: valor } });
      setGeral((g) => ({
        ...(g || {}),
        geral: { ...((g && g.geral) || {}), [chave]: valor },
      }));
      aviso?.(msg);
    } catch (e) {
      aviso?.(e.message, "erro");
    }
  }

  const g = (geral && geral.geral) || {};

  return (
    <div>
      <h1>Robôs</h1>
      <p className="muted">
        Cada operadora tem o seu robô. A engrenagem mostra tudo o que ele preenche no portal, tela por tela, e deixa
        você mudar. A configuração fica neste computador: é a do seu robô. O login do portal fica em Conexões.
      </p>

      <div className="nativa-robos">
        {(operadoras || []).map((op) => {
          const st = conexao[op.id] || op.conexao || "desconectado";
          const padrao = (c) => (op.campos.find((x) => x.chave === c) || {}).padrao;
          const login = op.login || {};
          return (
            <article key={op.id} className="nativa-robo-cartao cartao" style={{ "--cor-op": op.cor }}>
              <div className="nativa-robo-topo">
                <div>
                  <h2>{op.nome}</h2>
                  <div className="muted">{op.produto}</div>
                </div>
                <button
                  type="button"
                  className="nativa-engrenagem"
                  onClick={() => onConfigurar?.(op.id)}
                  title="Configurar o robô"
                  aria-label={`Configurar o robô da ${op.nome}`}
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
                  {!login.guardadas || login.recusadas ? (
                    <button type="button" className="secundario btn-compacto" onClick={() => onLogin?.(op.id)}>
                      {login.guardadas ? "Atualizar a senha" : "Cadastrar o login"}
                    </button>
                  ) : null}
                  <button type="button" className="secundario btn-compacto" onClick={() => onConfigurar?.(op.id)}>
                    Configurar
                  </button>
                </div>
              </div>
            </article>
          );
        })}
        {(indisponiveis || []).map((op) => (
          <article key={op.id || op.nome} className="nativa-robo-cartao cartao nativa-robo-indisponivel">
            <h2>{op.nome}</h2>
            <div className="muted">Indisponível</div>
            <p className="muted">
              O robô desta operadora não carregou. As outras operadoras funcionam normalmente.{" "}
              <span className="muted">Motivo: {op.motivo}</span>
            </p>
          </article>
        ))}
      </div>

      <section className="cartao">
        <h2>Para todos os robôs</h2>
        <div className="nativa-form-linha">
          <div className="nativa-rotulo">Prints das telas</div>
          <div>
            <Chave
              rotulo="Guardar print de cada tela do portal"
              marcado={!!g.mapear}
              onChange={(v) => setAjuste("mapear", v, v ? "Prints ligados." : "Prints desligados.")}
            />
            <div className="nativa-ajuda">Só para ajustar o robô quando o portal muda. Deixe desligado no dia a dia.</div>
          </div>
        </div>
        <div className="nativa-form-linha">
          <div className="nativa-rotulo">Janela do portal</div>
          <div>
            <Chave
              rotulo="Mostrar a janela do portal (para calibrar)"
              marcado={!!g.modo_visual}
              onChange={(v) =>
                setAjuste(
                  "modo_visual",
                  v,
                  v
                    ? "A janela do portal aparece a partir da próxima vez que o robô abrir o portal."
                    : "A janela do portal fica escondida a partir da próxima vez que o robô abrir o portal.",
                )
              }
            />
            <div className="nativa-ajuda">
              Opção técnica. No dia a dia fica desligada: o robô entra e trabalha no portal sem aparecer. Se o portal
              já estiver aberto, feche a tela (janela preta) e abra de novo para valer.
            </div>
          </div>
        </div>
        <div className="nativa-form-linha">
          <div className="nativa-rotulo">Pasta do robô</div>
          <div>
            <div className="num">{geral ? geral.pasta_saida : "…"}</div>
            <div className="nativa-ajuda">
              Guarda a sessão do portal, os PDFs, o histórico e o registro que impede cotação repetida. Arquivos do
              robô com mais de {geral && geral.retencao_dias ? geral.retencao_dias : 90} dias são apagados sozinhos.
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function Chave({ rotulo, marcado, onChange }) {
  return (
    <label className="nativa-chave">
      <input type="checkbox" checked={!!marcado} onChange={(e) => onChange(e.target.checked)} />
      <span className="nativa-chave-trilho" />
      <span>{rotulo}</span>
    </label>
  );
}
