import { useEffect, useMemo, useState } from "react";
import LogoOperadora from "./LogoOperadora";
import { attrsCartaoOperadora } from "./operadoras";
import { chamarRpa } from "../rpaClient";
import { useConfirmacao } from "./Confirmacao";
import {
  FAIXAS_ANS,
  carregarRascunho,
  diferencasDoPadrao,
  fraseExemploPdf,
  mudancasConfig,
  textoDoValor,
  valorDeConfig,
  valoresParaSalvar,
  visivelConfig,
} from "./regrasRestante";
import { CONEXAO, plural, resumoDoRobo } from "./regrasNova";

export default function ConfigRobo({
  opId,
  operadoras,
  conexao,
  aviso,
  onVoltar,
  onLogin,
  onSujo,
}) {
  const [dados, setDados] = useState(null);
  const [falhou, setFalhou] = useState(false);
  const [rascunho, setRascunho] = useState({});
  const [pares, setPares] = useState({});
  const [salvando, setSalvando] = useState(false);
  const [confirmar, modal] = useConfirmacao();

  const campos = useMemo(() => {
    const m = {};
    for (const t of (dados && dados.telas) || []) {
      for (const c of t.campos || []) if (c.chave) m[c.chave] = c;
    }
    return m;
  }, [dados]);

  function aplicarTelas(telas) {
    const { rascunho: r, pares: p } = carregarRascunho(telas);
    setRascunho(r);
    setPares(p);
  }

  useEffect(() => {
    let vivo = true;
    setFalhou(false);
    setDados(null);
    chamarRpa("GET", `/api/robos/${opId}`)
      .then((d) => {
        if (!vivo) return;
        setDados(d);
        aplicarTelas(d.telas);
      })
      .catch(() => vivo && setFalhou(true));
    return () => {
      vivo = false;
    };
  }, [opId]);

  const mudancas = dados ? mudancasConfig(campos, rascunho, pares) : [];
  const diffsPadrao = dados ? diferencasDoPadrao(campos, rascunho, pares) : [];
  const avisoSair = mudancas.length ? "Há mudanças na configuração do robô que ainda não foram salvas." : "";

  useEffect(() => {
    onSujo?.(() => avisoSair);
    return () => onSujo?.(() => "");
  }, [avisoSair, onSujo]);

  useEffect(() => {
    if (!avisoSair) return undefined;
    const fn = (ev) => {
      ev.preventDefault();
      ev.returnValue = "";
    };
    window.addEventListener("beforeunload", fn);
    return () => window.removeEventListener("beforeunload", fn);
  }, [avisoSair]);

  function setValor(chave, valor, redesenharPares) {
    if (redesenharPares) setPares((p) => ({ ...p, [chave]: valor }));
    else setRascunho((r) => ({ ...r, [chave]: valor }));
  }

  async function salvar() {
    const valores = valoresParaSalvar(campos, rascunho, pares);
    setSalvando(true);
    try {
      const r = await chamarRpa("PUT", `/api/robos/${opId}`, { valores });
      setDados((d) => ({ ...d, telas: r.telas }));
      aplicarTelas(r.telas);
      aviso?.("Configuração salva. O robô usa estas escolhas a partir da próxima cotação.");
    } catch (e) {
      aviso?.(e.message, "erro");
      if (e.dados && e.dados.campo) {
        const alvo = document.getElementById(`cfg-${e.dados.campo}`);
        if (alvo) alvo.focus();
      }
    } finally {
      setSalvando(false);
    }
  }

  async function voltarPadroes() {
    const ok = await confirmar({
      titulo: "Voltar aos padrões da Newport?",
      texto: ["Todas as escolhas deste robô voltam a ser as do padrão da Newport.", "Cotações já emitidas não mudam."],
      ok: "Voltar aos padrões",
      principal: false,
    });
    if (!ok) return;
    try {
      const r = await chamarRpa("DELETE", `/api/robos/${opId}`);
      setDados((d) => ({ ...d, telas: r.telas }));
      aplicarTelas(r.telas);
      aviso?.("O robô voltou aos padrões da Newport.");
    } catch (e) {
      aviso?.(e.message, "erro");
    }
  }

  if (falhou) {
    return (
      <div>
        <h1>Robô não encontrado</h1>
        <button type="button" className="secundario" onClick={onVoltar}>
          Ver os robôs
        </button>
      </div>
    );
  }

  if (!dados) return <p className="lista-carregando">Carregando configuração do robô…</p>;

  const op = (operadoras || []).find((o) => o.id === opId) || dados;
  const st = conexao[opId] || dados.conexao || "desconectado";
  const n = mudancas.length;
  const dPadrao = diffsPadrao.length;
  const valorDe = (k) => valorDeConfig(k, campos, rascunho, pares);
  const marca = attrsCartaoOperadora(opId, false);

  return (
    <div>
      {modal}
      <div
        className={`nativa-robo-cabeca ${marca.className}`}
        style={marca.style}
        data-cor-op={marca["data-cor-op"]}
      >
        <div>
          <h1>
            <LogoOperadora operadora={opId} tamanho="md" /> Robô da {dados.nome}
          </h1>
          <p className="muted">
            {dados.produto}. O robô usa estas escolhas em todas as suas cotações, até você mudar de novo. Para uma
            cotação só, use “Mudar só nesta cotação” na Nova cotação.
          </p>
        </div>
        <span className={`nativa-conexao-status nativa-conexao-status--${st}`}>
          <span className={`nativa-ponto nativa-ponto--${st}`} />
          {CONEXAO[st] || st}
        </span>
      </div>

      <section
        className={`cartao nativa-operadora ${marca.className}`}
        style={marca.style}
        data-cor-op={marca["data-cor-op"]}
      >
        <p className="nativa-robo-resumo">
          <strong>Hoje o robô cota assim: </strong>
          {resumoDoRobo(op, (k) => valorDe(`padroes.${k}`), { produto: valorDe("padroes.produto") })}.
          {dPadrao ? (
            <span className="muted">
              {" "}
              {plural(dPadrao, "escolha diferente", "escolhas diferentes")} dos padrões da Newport.
            </span>
          ) : null}
        </p>
      </section>

      <section className="cartao">
        <h2>O caminho do robô no portal</h2>
        <p className="muted">As telas na ordem em que o robô passa por elas, com o que ele preenche em cada uma.</p>
        <ol className="nativa-trilha">
          {(dados.telas || []).map((t) => {
            const linhas = (t.campos || []).filter((c) => visivelConfig(c, campos, rascunho, pares));
            return (
              <li key={t.etapa} className={`nativa-passo-robo${linhas.length ? "" : " nativa-passo-robo--vazio"}`}>
                <div className="nativa-passo-cabeca">
                  <h2>{t.titulo}</h2>
                  <p className="muted">{t.faz}</p>
                </div>
                {linhas.length ? (
                  <div>
                    {linhas.map((c) => (
                      <CampoConfig
                        key={c.chave || `${t.etapa}-${c.rotulo}-${c.tipo}`}
                        c={c}
                        valor={c.chave ? rascunho[c.chave] : undefined}
                        paresLinha={c.chave ? pares[c.chave] : undefined}
                        planos={dados.planos || []}
                        diferente={c.chave ? !iguaisPadrao(c, valorDe(c.chave)) : false}
                        onChange={setValor}
                        onLogin={onLogin}
                        opId={opId}
                      />
                    ))}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ol>
      </section>

      <div className="nativa-barra-acao">
        <div className="nativa-resumo">{n ? plural(n, "mudança ainda não salva", "mudanças ainda não salvas") : "Tudo salvo."}</div>
        <div className="nativa-acoes">
          {dPadrao || n ? (
            <button type="button" className="secundario" onClick={voltarPadroes}>
              Voltar aos padrões da Newport
            </button>
          ) : null}
          <button type="button" className="secundario" disabled={!n} onClick={() => aplicarTelas(dados.telas)}>
            Desfazer
          </button>
          <button type="button" disabled={!n || salvando} onClick={salvar}>
            Salvar configuração
          </button>
        </div>
      </div>
    </div>
  );
}

function iguaisPadrao(c, valor) {
  return JSON.stringify(valor) === JSON.stringify(c.padrao);
}

function CampoConfig({ c, valor, paresLinha, planos, diferente, onChange, onLogin, opId }) {
  if (c.tipo === "credenciais") {
    return (
      <div className="nativa-form-linha">
        <div className="nativa-rotulo">{c.rotulo || "Login no portal"}</div>
        <div className="nativa-login-nesta-tela">
          <p>
            O login do portal fica em <strong>Conexões</strong>. A senha nunca aparece nesta tela e não entra na
            configuração salva.
          </p>
          <button type="button" className="secundario btn-compacto" onClick={() => onLogin?.(opId)}>
            Abrir Conexões
          </button>
          {c.ajuda ? <div className="nativa-ajuda">{c.ajuda}</div> : null}
        </div>
      </div>
    );
  }

  const rotuloEsquerda = c.tipo === "sim_nao" ? "" : c.rotulo;
  return (
    <div className="nativa-form-linha">
      {c.tipo === "texto" && c.chave ? (
        <label className="nativa-rotulo" htmlFor={`cfg-${c.chave}`}>
          {rotuloEsquerda}
        </label>
      ) : (
        <div className="nativa-rotulo">{rotuloEsquerda}</div>
      )}
      <div>
        <Controle
          c={c}
          valor={valor}
          paresLinha={paresLinha}
          planos={planos}
          onChange={onChange}
        />
        {c.ajuda ? <div className="nativa-ajuda">{c.ajuda}</div> : null}
        {c.chave && diferente ? (
          <div className="nativa-nota-padrao">
            <span className="nativa-ponto nativa-ponto--aguardando_codigo" aria-hidden="true" />
            Padrão da Newport: {textoDoValor(c, c.padrao)}.{" "}
            <button
              type="button"
              className="link"
              onClick={() => {
                if (c.tipo === "pares") onChange(c.chave, Object.entries(c.padrao || {}), true);
                else onChange(c.chave, JSON.parse(JSON.stringify(c.padrao)));
              }}
            >
              Voltar ao padrão
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function Controle({ c, valor, paresLinha, planos, onChange }) {
  const k = c.chave;
  if (c.tipo === "info") return <div className="muted">{c.texto}</div>;
  if (c.tipo === "sim_nao") {
    return (
      <label className="nativa-chave">
        <input
          type="checkbox"
          checked={valor === "sim"}
          onChange={(e) => onChange(k, e.target.checked ? "sim" : "nao")}
        />
        <span className="nativa-chave-trilho" />
        <span>{c.rotulo}</span>
      </label>
    );
  }
  if (c.tipo === "escolha") {
    return (
      <div className="nativa-segmentos" role="group" aria-label={c.rotulo}>
        {(c.opcoes || []).map(([v, texto]) => (
          <button
            key={String(v)}
            type="button"
            className="secundario"
            aria-pressed={String(v) === String(valor)}
            onClick={() => onChange(k, String(v))}
          >
            {texto}
          </button>
        ))}
      </div>
    );
  }
  if (c.tipo === "numero") {
    const mudar = (d) => {
      const min = c.minimo == null ? 1 : c.minimo;
      const max = c.maximo == null ? 99 : c.maximo;
      const next = Math.max(min, Math.min(max, Number(valor) + d));
      onChange(k, next);
    };
    return (
      <div className="nativa-menor-preco">
        <div className="nativa-passo">
          <button type="button" aria-label={`Menos em ${c.rotulo}`} onClick={() => mudar(-1)}>
            −
          </button>
          <button type="button" aria-label={`Mais em ${c.rotulo}`} onClick={() => mudar(1)}>
            +
          </button>
        </div>
        <span className="num nativa-faixa-qtd">{String(valor)}</span>
      </div>
    );
  }
  if (c.tipo === "texto") {
    const lista = c.sugestoes ? `sug-${String(k).replace(/\W/g, "-")}` : null;
    const exemplo = c.validar === "nome_pdf" ? fraseExemploPdf(valor, c.exemplo_pdf || {}) : null;
    return (
      <div>
        <input
          className="campo"
          id={`cfg-${k}`}
          value={valor || ""}
          list={lista || undefined}
          placeholder={c.exemplo || ""}
          onChange={(e) => onChange(k, e.target.value)}
        />
        {lista ? (
          <datalist id={lista}>
            {c.sugestoes.map((x) => (
              <option key={x} value={x} />
            ))}
          </datalist>
        ) : null}
        {exemplo ? <div className="nativa-ajuda">{exemplo}</div> : null}
      </div>
    );
  }
  if (c.tipo === "faixas") {
    const atual = new Set(valor || []);
    return (
      <div className="nativa-faixas-escolha" role="group" aria-label={c.rotulo}>
        {FAIXAS_ANS.map((f) => (
          <label key={f} className="nativa-faixa-chip">
            <input
              type="checkbox"
              checked={atual.has(f)}
              onChange={(e) => {
                const next = new Set(valor || []);
                if (e.target.checked) next.add(f);
                else next.delete(f);
                onChange(
                  k,
                  FAIXAS_ANS.filter((x) => next.has(x)),
                );
              }}
            />
            <span>{f}</span>
          </label>
        ))}
      </div>
    );
  }
  if (c.tipo === "planos") {
    const grupos = {};
    for (const p of planos) (grupos[p.acomodacao] = grupos[p.acomodacao] || []).push(p);
    return (
      <div className="nativa-planos">
        {Object.keys(grupos)
          .sort()
          .map((acom) => (
            <div key={acom}>
              <h3>{acom}</h3>
              {grupos[acom].map((p) => {
                const rotulo = `${p.nome} | ${p.acomodacao}`;
                const marcado = (valor || []).includes(rotulo);
                return (
                  <label key={rotulo} className={`nativa-plano-item${marcado ? " marcado" : ""}`}>
                    <input
                      type="checkbox"
                      checked={marcado}
                      onChange={(e) => {
                        const atual = (valor || []).filter((x) => x !== rotulo);
                        if (e.target.checked) atual.push(rotulo);
                        onChange(k, atual);
                      }}
                    />
                    <span>{p.nome}</span>
                  </label>
                );
              })}
            </div>
          ))}
      </div>
    );
  }
  if (c.tipo === "pares") {
    const linhas = paresLinha || [];
    const [rotuloA, rotuloB] = c.colunas || ["De", "Para"];
    const [exemploA, exemploB] = c.exemplos || ["", ""];
    function mudarLinha(i, j, v) {
      const next = linhas.map((par, idx) => (idx === i ? (j === 0 ? [v, par[1]] : [par[0], v]) : par));
      onChange(k, next, true);
    }
    return (
      <div>
        <table className="nativa-tabela nativa-tabela-edicao">
          <thead>
            <tr>
              <th>{rotuloA}</th>
              <th>{rotuloB}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {linhas.length ? (
              linhas.map((par, i) => (
                <tr key={i}>
                  <td>
                    <input
                      className="campo"
                      value={par[0]}
                      aria-label={rotuloA}
                      placeholder={exemploA}
                      onChange={(e) => mudarLinha(i, 0, e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      className="campo"
                      value={par[1]}
                      aria-label={rotuloB}
                      placeholder={exemploB}
                      onChange={(e) => mudarLinha(i, 1, e.target.value)}
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className="secundario btn-compacto"
                      aria-label={`Tirar a linha ${par[0] || i + 1}`}
                      onClick={() => onChange(k, linhas.filter((_, idx) => idx !== i), true)}
                    >
                      Tirar
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={3} className="muted">
                  Nenhuma linha.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <button
          type="button"
          className="secundario btn-compacto"
          onClick={() => onChange(k, [...linhas, ["", ""]], true)}
        >
          Adicionar linha
        </button>
      </div>
    );
  }
  return <span>{String(valor)}</span>;
}
