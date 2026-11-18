import { useEffect, useState } from "react";
import { chamarRpa } from "../rpaClient";
import TabelaCotacoes from "./TabelaCotacoes";
import { saudacao } from "./regrasRestante";
import { digitos, formatarCnpj } from "./regrasNova";

export default function Inicio({
  operadoras,
  trabalhoAtual,
  aviso,
  onAcompanhar,
  onCotacoes,
  onNova,
  onImportar,
  onLogin,
  onCotarEmpresa,
  recarregarSinal = 0,
}) {
  const [cotacoes, setCotacoes] = useState(null);
  const [pendencias, setPendencias] = useState([]);
  const [empresas, setEmpresas] = useState([]);

  useEffect(() => {
    let vivo = true;
    Promise.all([
      chamarRpa("GET", "/api/cotacoes?limite=8&status=OK,ERRO,VERIFICAR,PARADO").catch(() => []),
      chamarRpa("GET", "/api/pendencias").catch(() => []),
      chamarRpa("GET", "/api/empresas").catch(() => []),
    ]).then(([c, p, e]) => {
      if (!vivo) return;
      setCotacoes(Array.isArray(c) ? c : []);
      setPendencias(Array.isArray(p) ? p : []);
      setEmpresas(Array.isArray(e) ? e : []);
    });
    return () => {
      vivo = false;
    };
  }, [recarregarSinal]);

  const tarefasLogin = (operadoras || []).filter((op) => {
    const login = op.login || {};
    return !(login.guardadas && !login.recusadas);
  });

  return (
    <div>
      <h1>{saudacao()}</h1>
      <p className="muted">
        O robô preenche o portal, emite uma cotação por plano e guarda os PDFs. Você escolhe a empresa e os planos.
      </p>

      <div className="nativa-colunas">
        <section className="cartao">
          <h2>O que fazer agora</h2>
          <div className="nativa-tarefas">
            {trabalhoAtual ? (
              <Tarefa
                destaque
                titulo={`Robô trabalhando: ${trabalhoAtual.titulo || "pedido"}`}
                texto={trabalhoAtual.modo === "ensaio" ? "Ensaio, sem emitir." : "Emitindo as cotações no portal."}
                acao={
                  <button type="button" className="secundario" onClick={() => onAcompanhar?.(trabalhoAtual.id)}>
                    Acompanhar
                  </button>
                }
              />
            ) : null}
            {pendencias.length ? (
              <Tarefa
                titulo={
                  pendencias.length === 1
                    ? "Uma cotação pede conferência no portal"
                    : `${pendencias.length} cotações pedem conferência no portal`
                }
                texto="O robô não emite essas de novo até você conferir."
                acao={
                  <button type="button" className="secundario" onClick={onCotacoes}>
                    Conferir
                  </button>
                }
              />
            ) : null}
            <Tarefa
              destaque={!trabalhoAtual}
              titulo="Cotar uma empresa"
              texto="CNPJ, vidas por faixa e planos. O robô faz o resto no portal."
              acao={
                <button type="button" onClick={onNova}>
                  Nova cotação
                </button>
              }
            />
            <Tarefa
              titulo="Cotar várias empresas de uma vez"
              texto="Uma linha por empresa, na planilha modelo."
              acao={
                <button type="button" className="secundario" onClick={onImportar}>
                  Importar planilha
                </button>
              }
            />
            {tarefasLogin.map((op) => {
              const login = op.login || {};
              return (
                <Tarefa
                  key={op.id}
                  destaque
                  titulo={
                    login.guardadas
                      ? `O portal da ${op.nome} recusou o login guardado`
                      : `Cadastre o login da ${op.nome}`
                  }
                  texto={
                    login.guardadas
                      ? "O robô não tenta de novo até você guardar a senha outra vez, para não bloquear a sua conta."
                      : "Uma vez só, em Conexões. O robô entra no portal sozinho com ele; fica no cofre do Windows deste computador."
                  }
                  acao={
                    <button type="button" className="secundario" onClick={() => onLogin?.(op.id)}>
                      {login.guardadas ? "Atualizar a senha" : "Cadastrar o login"}
                    </button>
                  }
                />
              );
            })}
          </div>
        </section>

        <section className="cartao">
          <h2>Empresas recentes</h2>
          {empresas.slice(0, 6).length ? (
            <ul className="nativa-empresas">
              {empresas.slice(0, 6).map((e) => (
                <li key={e.cnpj}>
                  <div>
                    <div className="nativa-empresa-nome">{e.apelido || e.razao_social || formatarCnpj(e.cnpj)}</div>
                    <div className="muted num">
                      {e.apelido && e.razao_social ? `${e.razao_social}, ` : ""}
                      {formatarCnpj(e.cnpj)}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="secundario btn-compacto"
                    onClick={() => onCotarEmpresa?.(digitos(e.cnpj))}
                  >
                    Cotar de novo
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">
              As empresas que você cotar aparecem aqui, para repetir a cotação com os mesmos dados.
            </p>
          )}
        </section>
      </div>

      <section className="cartao">
        <div className="nativa-painel-cabeca">
          <h2>Últimas cotações</h2>
          {cotacoes && cotacoes.length ? (
            <button type="button" className="link" onClick={onCotacoes}>
              Ver todas
            </button>
          ) : null}
        </div>
        {cotacoes === null ? <p className="lista-carregando">Carregando cotações…</p> : null}
        {cotacoes && cotacoes.length === 0 ? (
          <p className="muted">Ainda não há cotações. Quando o robô terminar a primeira, o PDF fica aqui para baixar.</p>
        ) : null}
        {cotacoes && cotacoes.length > 0 ? (
          <TabelaCotacoes
            cotacoes={cotacoes}
            empresa
            data
            operadoras={operadoras}
            aviso={aviso}
            cotarDeNovo
            onCotarDeNovo={onCotarEmpresa}
          />
        ) : null}
      </section>
    </div>
  );
}

function Tarefa({ titulo, texto, acao, destaque = false }) {
  return (
    <div className={`nativa-tarefa${destaque ? " nativa-tarefa--destaque" : ""}`}>
      <div>
        <strong>{titulo}</strong>
        <span className="muted"> {texto}</span>
      </div>
      {acao}
    </div>
  );
}
