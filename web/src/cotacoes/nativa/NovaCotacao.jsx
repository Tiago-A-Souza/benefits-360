import { useEffect, useMemo, useState } from "react";
import { chamarRpa, RpaClienteErro } from "../rpaClient";
import { useConfirmacao } from "./Confirmacao";
import {
  CONEXAO,
  FAIXAS,
  aplicarDados,
  clonarForm,
  cnpjValido,
  digitos,
  estadoInicial,
  faixasExatas,
  fluxoConfirmacao,
  formatarCnpj,
  fraseResumoBarra,
  montarItens,
  opsAtivas,
  problemasLocais,
  resumoDoRobo,
  totalCotacoes,
  totalVidas,
  visivel,
} from "./regrasNova";

function Segmentos({ opcoes, valor, onChange, rotulo }) {
  return (
    <div className="nativa-segmentos" role="group" aria-label={rotulo}>
      {opcoes.map(([v, texto]) => (
        <button
          key={String(v)}
          type="button"
          className="secundario"
          aria-pressed={String(valor) === String(v)}
          onClick={() => onChange(v)}
        >
          {texto}
        </button>
      ))}
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

function CampoOperadora({ campo, valor, opId, onChange }) {
  const id = `${opId}-${campo.chave}`;
  let controle;
  if (campo.tipo === "sim_nao") {
    controle = <Chave rotulo={campo.rotulo} marcado={valor === "sim"} onChange={(v) => onChange(v ? "sim" : "nao")} />;
  } else if (campo.tipo === "escolha") {
    controle = (
      <Segmentos
        opcoes={campo.opcoes}
        valor={valor}
        onChange={onChange}
        rotulo={campo.rotulo}
      />
    );
  } else {
    const lista = campo.tipo === "sugestoes" ? `sug-${opId}-${campo.chave}` : null;
    controle = (
      <>
        <input
          className="campo"
          id={id}
          value={valor || ""}
          list={lista || undefined}
          onChange={(e) => onChange(e.target.value)}
        />
        {lista ? (
          <datalist id={lista}>
            {(campo.opcoes || []).map((x) => (
              <option key={x} value={x} />
            ))}
          </datalist>
        ) : null}
      </>
    );
  }
  const titulo = campo.tipo === "sim_nao" ? campo.titulo || "" : campo.rotulo;
  return (
    <div className="nativa-form-linha">
      {campo.tipo === "sim_nao" ? (
        <div className="nativa-rotulo">{titulo}</div>
      ) : (
        <label className="nativa-rotulo" htmlFor={id}>
          {titulo}
        </label>
      )}
      <div>
        {controle}
        {campo.ajuda ? <div className="nativa-ajuda">{campo.ajuda}</div> : null}
      </div>
    </div>
  );
}

function PainelOperadora({ op, o, conexao, soUma, onPatch, onConfigurar }) {
  const padraoDe = (chaveCampo) => {
    const c = op.campos.find((x) => x.chave === chaveCampo);
    return c && c.padrao !== undefined && c.padrao !== null ? String(c.padrao) : "";
  };
  const mudadoNestaCotacao = op.campos.some((c) => c.robo && o.campos[c.chave] !== padraoDe(c.chave));
  const frase = resumoDoRobo(op, (k) => o.campos[k], { produto: op.produto_portal });
  const grupos = {};
  for (const p of op.planos || []) {
    (grupos[p.acomodacao || "Outros"] = grupos[p.acomodacao || "Outros"] || []).push(p);
  }

  function setCampo(chave, valor) {
    onPatch({ campos: { ...o.campos, [chave]: valor } });
  }

  return (
    <section className="cartao nativa-operadora" style={{ "--cor-op": op.cor }} aria-labelledby={`t-${op.id}`}>
      <div className="nativa-operadora-cabeca">
        <div>
          <div className="nativa-operadora-nome" id={`t-${op.id}`}>
            {op.nome}
          </div>
          <div className="muted">{op.produto}</div>
        </div>
        <div className="nativa-operadora-lado">
          <div className="nativa-conexao">
            <span className={`nativa-ponto nativa-ponto--${conexao}`} />
            {CONEXAO[conexao] || conexao}
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
          {!soUma ? (
            <Chave
              rotulo="Cotar nesta operadora"
              marcado={o.ativa}
              onChange={(v) => onPatch({ ativa: v })}
            />
          ) : null}
        </div>
      </div>

      {o.ativa ? (
        <div>
          {(op.campos || [])
            .filter((c) => !c.robo && visivel(c, o.campos))
            .map((c) => (
              <CampoOperadora
                key={c.chave}
                campo={c}
                valor={o.campos[c.chave]}
                opId={op.id}
                onChange={(v) => setCampo(c.chave, v)}
              />
            ))}

          <div className="nativa-form-linha">
            <div className="nativa-rotulo">O robô vai cotar</div>
            <div>
              <div className="nativa-frase-robo">
                {frase}.
                {mudadoNestaCotacao ? <span className="nativa-selo-mudado">mudado só nesta cotação</span> : null}
              </div>
              <div className="nativa-acoes-frase">
                <button type="button" className="link" onClick={() => onPatch({ ajustar: !o.ajustar })}>
                  {o.ajustar ? "Fechar" : "Mudar só nesta cotação"}
                </button>
                {mudadoNestaCotacao ? (
                  <button
                    type="button"
                    className="link"
                    onClick={() => {
                      const campos = { ...o.campos };
                      for (const c of op.campos) if (c.robo) campos[c.chave] = padraoDe(c.chave);
                      onPatch({ campos, ajustar: o.ajustar });
                    }}
                  >
                    Voltar à configuração do robô
                  </button>
                ) : null}
                <button type="button" className="link" onClick={() => onConfigurar?.(op.id)}>
                  Configurar o robô
                </button>
              </div>
            </div>
          </div>

          {o.ajustar
            ? (op.campos || [])
                .filter((c) => c.robo && visivel(c, o.campos))
                .map((c) => (
                  <CampoOperadora
                    key={`aj-${c.chave}`}
                    campo={c}
                    valor={o.campos[c.chave]}
                    opId={op.id}
                    onChange={(v) => setCampo(c.chave, v)}
                  />
                ))
            : null}

          <div className="nativa-form-linha">
            <div className="nativa-rotulo">Planos</div>
            <div>
              <div style={{ marginBottom: 10 }}>
                <Segmentos
                  opcoes={[
                    ["lista", "Escolher na lista"],
                    ["menor", "Os mais baratos"],
                  ]}
                  valor={o.menor ? "menor" : "lista"}
                  onChange={(v) => onPatch({ menor: v === "menor" })}
                  rotulo="Como escolher os planos"
                />
              </div>
              {o.menor ? (
                <div className="nativa-menor-preco">
                  <span>Cotar os</span>
                  <div className="nativa-passo">
                    <button
                      type="button"
                      className="secundario"
                      aria-label="Menos um plano"
                      onClick={() => onPatch({ qtdMenor: Math.max(1, o.qtdMenor - 1) })}
                    >
                      −
                    </button>
                    <button
                      type="button"
                      className="secundario"
                      aria-label="Mais um plano"
                      onClick={() => onPatch({ qtdMenor: Math.min(10, o.qtdMenor + 1) })}
                    >
                      +
                    </button>
                  </div>
                  <span className="num nativa-faixa-qtd">{o.qtdMenor}</span>
                  <span>
                    {o.qtdMenor === 1
                      ? "plano mais barato da lista do portal"
                      : "planos mais baratos da lista do portal"}
                  </span>
                </div>
              ) : (
                <div className="nativa-planos">
                  {Object.keys(grupos)
                    .sort()
                    .map((acom) => (
                      <div key={acom}>
                        <h3>{acom}</h3>
                        {grupos[acom].map((p) => {
                          const rotulo = `${p.nome} | ${p.acomodacao}`;
                          const marcado = o.planos.includes(rotulo);
                          return (
                            <label key={rotulo} className={`nativa-plano-item${marcado ? " marcado" : ""}`}>
                              <input
                                type="checkbox"
                                checked={marcado}
                                onChange={(e) => {
                                  const planos = e.target.checked
                                    ? [...o.planos, rotulo]
                                    : o.planos.filter((x) => x !== rotulo);
                                  onPatch({ planos });
                                }}
                              />
                              <span>{p.nome}</span>
                            </label>
                          );
                        })}
                      </div>
                    ))}
                </div>
              )}
              <div className="nativa-ajuda">
                {(op.textos || {}).planos ||
                  "Cada plano vira uma cotação e um PDF. A lista cresce sozinha com os planos que o robô encontrar no portal."}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export default function NovaCotacao({
  operadoras,
  conexao = {},
  urlRobo,
  cnpjInicial,
  onEnfileirado,
  onIrIframeCotacoes,
  onCotarEmpresa,
  onConfigurar,
  empresasRecentes: empresasProp,
  aviso,
}) {
  const [form, setForm] = useState(() => estadoInicial(operadoras));
  const [cnpjAjuda, setCnpjAjuda] = useState(null);
  const [carregado, setCarregado] = useState(null);
  const [problemas, setProblemas] = useState([]);
  const [enviando, setEnviando] = useState(false);
  const [empresas, setEmpresas] = useState(empresasProp || []);
  const [confirmar, modal] = useConfirmacao();

  useEffect(() => {
    setForm(estadoInicial(operadoras));
  }, [operadoras]);

  useEffect(() => {
    if (empresasProp) {
      setEmpresas(empresasProp);
      return;
    }
    let vivo = true;
    chamarRpa("GET", "/api/empresas")
      .then((d) => vivo && setEmpresas(Array.isArray(d) ? d : []))
      .catch(() => vivo && setEmpresas([]));
    return () => {
      vivo = false;
    };
  }, [empresasProp]);

  useEffect(() => {
    if (!cnpjInicial) return;
    let vivo = true;
    (async () => {
      try {
        const emp = await chamarRpa("GET", `/api/empresas/${digitos(cnpjInicial)}`, undefined, { aceitarErro: true });
        if (!vivo) return;
        if (emp && emp.ultimo_pedido) {
          setForm((f) => aplicarDados(estadoInicial(operadoras), emp.ultimo_pedido, operadoras));
          setCarregado(emp);
        } else {
          setForm((f) => ({ ...f, cnpj: digitos(cnpjInicial) }));
        }
      } catch {
        if (vivo) setForm((f) => ({ ...f, cnpj: digitos(cnpjInicial) }));
      }
    })();
    return () => {
      vivo = false;
    };
  }, [cnpjInicial, operadoras]);

  function patch(p) {
    setForm((f) => ({ ...clonarForm(f), ...p }));
  }
  function patchOp(id, p) {
    setForm((f) => {
      const next = clonarForm(f);
      next.ops[id] = { ...next.ops[id], ...p };
      return next;
    });
  }

  async function aoMudarCnpj(texto) {
    const d = digitos(texto).slice(0, 14);
    patch({ cnpj: d });
    setCnpjAjuda(null);
    if (d.length === 14 && !cnpjValido(d)) {
      setCnpjAjuda({ tipo: "erro", texto: "Este CNPJ não é válido. Confira os números." });
      return;
    }
    if (d.length === 14) {
      try {
        const emp = await chamarRpa("GET", `/api/empresas/${d}`, undefined, { aceitarErro: true });
        if (emp && emp.cnpj) {
          setCnpjAjuda({
            tipo: "info",
            nome: emp.razao_social || emp.apelido || "esta empresa",
            temPedido: !!emp.ultimo_pedido,
            cnpj: d,
          });
        }
      } catch {
        /* sem histórico */
      }
    }
  }

  async function escolherPasta() {
    try {
      const r = await chamarRpa("POST", "/api/escolher-pasta");
      if (r.pasta) patch({ pasta: r.pasta });
    } catch (e) {
      aviso?.(e.message, "erro");
    }
  }

  async function enviar(modo) {
    setProblemas([]);
    const locais = problemasLocais(form, operadoras);
    if (locais.length) {
      setProblemas(locais);
      return;
    }
    const itens = montarItens(form, operadoras);
    let validacao;
    try {
      validacao = await chamarRpa("POST", "/api/validar", { itens });
    } catch (e) {
      aviso?.(e.message, "erro");
      return;
    }
    if (!validacao.ok) {
      setProblemas(Object.values(validacao.problemas || {}).flat());
      return;
    }
    const decisao = await fluxoConfirmacao(
      modo,
      validacao,
      opsAtivas(form, operadoras).map((o) => o.nome),
      confirmar,
    );
    if (decisao.abortar) {
      if (decisao.irCotacoes) onIrIframeCotacoes?.();
      return;
    }
    setEnviando(true);
    try {
      const corpo = {
        modo,
        confirmado: modo === "emitir",
        itens,
        ...(decisao.reemitir?.length ? { reemitir: decisao.reemitir } : {}),
      };
      const r = await chamarRpa("POST", "/api/trabalhos", corpo);
      aviso?.(
        modo === "ensaio"
          ? "Ensaio na fila. O robô percorre as telas com o primeiro plano e para antes de emitir."
          : decisao.reemitir?.length
            ? "Pedido na fila. O robô vai emitir de novo, com protocolo novo."
            : "Pedido na fila. Acompanhe o robô por aqui.",
      );
      onEnfileirado?.(r.id);
    } catch (e) {
      if (e instanceof RpaClienteErro && e.dados && e.dados.problemas) {
        setProblemas(Object.values(e.dados.problemas).flat());
      } else {
        aviso?.(e.message, "erro");
      }
    } finally {
      setEnviando(false);
    }
  }

  const total = totalVidas(form.vidas);
  const escala = Math.max(5, ...Object.values(form.vidas));
  const exatas = useMemo(() => faixasExatas(operadoras), [operadoras]);
  const opAtiva = opsAtivas(form, operadoras)[0];
  const n = totalCotacoes(form, operadoras);
  const nomesPdf = (operadoras || []).map((op) => (op.textos || {}).nome_pdf).filter(Boolean);
  const soUma = (operadoras || []).length <= 1;

  return (
    <div className="nativa-nova">
      {modal}
      <header className="lista-head">
        <div>
          <h1>Nova cotação</h1>
          <p>Preencha a empresa e as vidas, escolha os planos e o robô faz o resto no portal.</p>
        </div>
      </header>
      {carregado && carregado.ultimo_pedido ? (
        <p className="muted">
          Dados da última cotação de {carregado.razao_social || carregado.apelido || formatarCnpj(carregado.cnpj)}{" "}
          carregados. Confira antes de gerar.
        </p>
      ) : null}

      <section className="cartao" aria-labelledby="t-empresas-recentes">
        <h2 id="t-empresas-recentes">Empresas recentes</h2>
        {empresas.length ? (
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
                  onClick={() => (onCotarEmpresa ? onCotarEmpresa(digitos(e.cnpj)) : aoMudarCnpj(e.cnpj))}
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

      <section className="cartao" aria-labelledby="t-empresa">
        <h2 id="t-empresa">Empresa</h2>
        <p className="muted">O robô busca a razão social no portal pelo CNPJ.</p>
        <div className="nativa-form-linha">
          <label htmlFor="nativa-cnpj">CNPJ</label>
          <div>
            <input
              id="nativa-cnpj"
              className={`campo${form.cnpj.length === 14 && !cnpjValido(form.cnpj) ? " invalido" : ""}`}
              inputMode="numeric"
              autoComplete="off"
              list="nativa-empresas-cnpj"
              placeholder="00.000.000/0000-00"
              value={formatarCnpj(form.cnpj)}
              onChange={(e) => aoMudarCnpj(e.target.value)}
            />
            <datalist id="nativa-empresas-cnpj">
              {empresas.map((e) => (
                <option key={e.cnpj} value={formatarCnpj(e.cnpj)}>
                  {e.apelido || e.razao_social || formatarCnpj(e.cnpj)}
                </option>
              ))}
            </datalist>
            <div className={`nativa-ajuda${cnpjAjuda?.tipo === "erro" ? " erro" : ""}`}>
              {cnpjAjuda?.tipo === "erro" ? cnpjAjuda.texto : null}
              {cnpjAjuda?.tipo === "info" ? (
                <>
                  {cnpjAjuda.nome} já foi cotada aqui.{" "}
                  {cnpjAjuda.temPedido ? (
                    <button
                      type="button"
                      className="link"
                      onClick={async () => {
                        try {
                          const emp = await chamarRpa("GET", `/api/empresas/${cnpjAjuda.cnpj}`, undefined, {
                            aceitarErro: true,
                          });
                          if (emp?.ultimo_pedido) {
                            setForm(aplicarDados(estadoInicial(operadoras), emp.ultimo_pedido, operadoras));
                            setCarregado(emp);
                          }
                        } catch {
                          /* ignore */
                        }
                      }}
                    >
                      Usar os mesmos dados da última cotação
                    </button>
                  ) : null}
                </>
              ) : null}
            </div>
          </div>
        </div>
        <div className="nativa-form-linha">
          <label htmlFor="nativa-apelido">Nome para achar depois</label>
          <div>
            <input
              id="nativa-apelido"
              className="campo"
              value={form.apelido}
              placeholder="Ex.: Padaria do Centro"
              onChange={(e) => patch({ apelido: e.target.value })}
            />
            <div className="nativa-ajuda">Opcional. Aparece na lista de cotações.</div>
          </div>
        </div>
        <div className="nativa-form-linha">
          <label htmlFor="nativa-pasta">Pasta do cliente</label>
          <div>
            <div className="nativa-campo-grupo">
              <input
                id="nativa-pasta"
                className="campo"
                value={form.pasta}
                placeholder="C:\...\SAÚDE\IMPLANTAÇÃO\ESTUDO\COTAÇÕES"
                onChange={(e) => patch({ pasta: e.target.value })}
              />
              <button type="button" className="secundario" onClick={escolherPasta}>
                Escolher pasta
              </button>
            </div>
            <div className="nativa-ajuda">
              Opcional. Os PDFs são copiados para cá com o nome de sempre
              {nomesPdf.length ? ` (${nomesPdf.join(" / ")})` : ""}.
            </div>
          </div>
        </div>
      </section>

      <section className="cartao" aria-labelledby="t-vidas">
        <h2 id="t-vidas">Vidas por faixa etária</h2>
        <p className="muted">
          Clique na coluna ou use + e − para distribuir as vidas da empresa (titulares e dependentes).{" "}
          {exatas.size ? "Nas faixas com * o portal pede a idade de cada vida." : ""}
        </p>
        <div className="nativa-censo">
          {FAIXAS.map(([k, rotulo]) => {
            const q = form.vidas[k];
            const mudar = (delta) =>
              patch({ vidas: { ...form.vidas, [k]: Math.max(0, Math.min(99, form.vidas[k] + delta)) } });
            return (
              <div key={k} className="nativa-faixa-col">
                <div className={`nativa-faixa-qtd num${q === 0 ? " zero" : ""}`}>{q}</div>
                <div
                  className="nativa-faixa-barra-area"
                  title={`Somar uma vida na faixa ${rotulo}`}
                  onClick={() => mudar(1)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") mudar(1);
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <div className="nativa-faixa-barra" style={{ height: `${(q / escala) * 100}%` }} />
                </div>
                <div className="nativa-faixa-rotulo">
                  {rotulo}
                  {exatas.has(rotulo) ? (
                    <span className="nativa-exata" title="Pede idade exata">
                      {" "}
                      *
                    </span>
                  ) : null}
                </div>
                <div className="nativa-passo">
                  <button
                    type="button"
                    className="secundario"
                    aria-label={`Tirar uma vida da faixa ${rotulo}`}
                    onClick={() => mudar(-1)}
                  >
                    −
                  </button>
                  <button
                    type="button"
                    className="secundario"
                    aria-label={`Somar uma vida na faixa ${rotulo}`}
                    onClick={() => mudar(1)}
                  >
                    +
                  </button>
                </div>
              </div>
            );
          })}
        </div>
        <div className="nativa-censo-total">
          <strong className={opAtiva && (total < opAtiva.min_vidas || total > opAtiva.max_vidas) && total > 0 ? "fora" : ""}>
            {total}
          </strong>
          <span className="muted">
            {total === 1 ? "vida" : "vidas"}
            {opAtiva ? ` (a ${opAtiva.nome} cota de ${opAtiva.min_vidas} a ${opAtiva.max_vidas})` : ""}
          </span>
        </div>
        <div className="nativa-idades">
          {FAIXAS.map(([k, rotulo]) => {
            if (!exatas.has(rotulo) || form.vidas[k] === 0) return null;
            return (
              <div key={k} className="nativa-idade-linha">
                <label htmlFor={`idades_${k}`}>Idades na faixa {rotulo}</label>
                <div>
                  <input
                    className="campo"
                    id={`idades_${k}`}
                    value={form.idades[k]}
                    inputMode="numeric"
                    placeholder={form.vidas[k] === 1 ? "Ex.: 7" : "Ex.: 3, 7, 12"}
                    onChange={(e) => patch({ idades: { ...form.idades, [k]: e.target.value } })}
                  />
                  <div className="nativa-ajuda">
                    {form.vidas[k] === 1
                      ? "A idade da vida nesta faixa."
                      : `As ${form.vidas[k]} idades, separadas por vírgula.`}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {(operadoras || []).map((op) =>
        form.ops[op.id] ? (
          <PainelOperadora
            key={op.id}
            op={op}
            o={form.ops[op.id]}
            conexao={conexao[op.id] || "desconectado"}
            soUma={soUma}
            onPatch={(p) => patchOp(op.id, p)}
            onConfigurar={onConfigurar}
          />
        ) : null,
      )}

      {problemas.length ? (
        <div className="nativa-problemas" role="alert">
          <strong>Antes de continuar, ajuste:</strong>
          <ul>
            {problemas.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="nativa-barra-acao">
        <div className="nativa-resumo">{fraseResumoBarra(form, operadoras)}</div>
        <div className="nativa-acoes">
          <button type="button" className="secundario" disabled={enviando} onClick={() => enviar("ensaio")}>
            Ensaiar sem emitir
          </button>
          <button type="button" disabled={enviando} onClick={() => enviar("emitir")}>
            {n ? `Gerar ${n === 1 ? "1 cotação" : `${n} cotações`}` : "Gerar cotações"}
          </button>
        </div>
      </div>
    </div>
  );
}
