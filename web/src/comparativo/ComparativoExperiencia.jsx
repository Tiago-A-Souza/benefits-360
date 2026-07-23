import { useCallback, useEffect, useMemo, useState } from "react";
import { salvarSelecaoApresentacao } from "../api";
import { DESTAQUE_LABELS, FAIXAS_ROTULOS, formatBps, formatCentavos } from "./format";
import {
  filtrarPropostas,
  opcoesUnicas,
  ordenarPropostas,
  ordenarSelecao,
} from "./logica";

function Pendencias({ items }) {
  if (!items?.length) return <p className="ok">Nenhuma pendência bloqueante nesta verificação.</p>;
  return (
    <ul className="pendencias">
      {items.map((p, i) => (
        <li key={i} className={`pendencia pendencia--${p.tipo}`}>
          <strong>{p.titulo}</strong>
          <p>{p.descricao}</p>
          {p.acao_sugerida && <p className="acao">{p.acao_sugerida}</p>}
        </li>
      ))}
    </ul>
  );
}

function CardProposta({ proposta, selecionada, onToggle, compacto }) {
  const n = proposta.numerico;
  return (
    <article
      className={`cmp-card${selecionada ? " cmp-card--selecionada" : ""}${compacto ? " cmp-card--compacto" : ""}`}
    >
      <header className="cmp-card-cabecalho">
        <div>
          <strong className="cmp-card-nome">{proposta.plano_nome}</strong>
          <p className="muted cmp-card-meta">
            {proposta.operadora}
            {proposta.acomodacao ? ` · ${proposta.acomodacao}` : ""}
          </p>
        </div>
        <div className="cmp-card-badges">
          {proposta.destaques?.map((d) => (
            <span key={d} className="badge badge--destaque">
              {DESTAQUE_LABELS[d] || d}
            </span>
          ))}
        </div>
      </header>
      <dl className="cmp-card-metricas">
        <div>
          <dt>Coparticipação</dt>
          <dd>{proposta.regime_coparticipacao}</dd>
        </div>
        <div>
          <dt>Mensalidade</dt>
          <dd>{formatCentavos(n?.proposta_mensal_centavos)}</dd>
        </div>
        <div>
          <dt>Diferença</dt>
          <dd>{formatCentavos(n?.diff_mes_centavos)}</dd>
        </div>
        <div>
          <dt>Diferença %</dt>
          <dd>{formatBps(n?.diff_bps)}</dd>
        </div>
      </dl>
      <button type="button" className={selecionada ? "secundario" : ""} onClick={() => onToggle(proposta.opcao_id)}>
        {selecionada ? "Remover da comparação" : "Adicionar à comparação"}
      </button>
    </article>
  );
}

function MatrizComparativa({ planoAtual, propostas, vista, mostrarNomes }) {
  if (!propostas.length) {
    return <p className="muted">Selecione ao menos uma proposta para montar a matriz comparativa.</p>;
  }

  const colunas = [{ id: "atual", rotulo: planoAtual?.plano_nome || "Plano atual", proposta: null }, ...propostas.map((p) => ({
    id: p.opcao_id,
    rotulo: p.plano_nome,
    proposta: p,
  }))];

  if (vista === "faixas") {
    const faixas = new Set();
    for (const p of propostas) {
      for (const f of p.faixas || []) faixas.add(f.faixa);
    }
    const listaFaixas = [...faixas].sort((a, b) => a - b);
    return (
      <div className="cmp-matriz-scroll">
        <table className="conferencia cmp-matriz">
          <thead>
            <tr>
              <th>Faixa</th>
              {colunas.map((c) => (
                <th key={c.id}>{c.rotulo}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {listaFaixas.map((fx) => (
              <tr key={fx}>
                <td>{FAIXAS_ROTULOS[fx] || fx}</td>
                <td>—</td>
                {propostas.map((p) => {
                  const f = (p.faixas || []).find((x) => x.faixa === fx);
                  return (
                    <td key={p.opcao_id}>
                      {f ? formatCentavos(f.proposta_centavos) : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (vista === "beneficiarios") {
    const vidas = propostas[0]?.secoes?.[0]?.vidas || [];
    return (
      <>
        {!mostrarNomes && (
          <p className="alerta">Modo agregado — nomes ocultos. Ative a exibição para revisão interna.</p>
        )}
        <div className="cmp-matriz-scroll">
          <table className="conferencia cmp-matriz">
            <thead>
              <tr>
                <th>Beneficiário</th>
                <th>Plano atual</th>
                {propostas.map((p) => (
                  <th key={p.opcao_id}>{p.plano_nome}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {vidas.map((v) => (
                <tr key={v.vida_id}>
                  <td>{mostrarNomes ? v.nome : `Beneficiário ${v.faixa ?? ""}`}</td>
                  <td>{v.atual_reais ?? formatCentavos(v.atual_centavos)}</td>
                  {propostas.map((p) => {
                    const pv = p.secoes?.[0]?.vidas?.find((x) => x.vida_id === v.vida_id);
                    return (
                      <td key={p.opcao_id}>
                        {pv?.proposta_reais ?? formatCentavos(pv?.proposta_centavos)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </>
    );
  }

  const linhas = [
    { rotulo: "Mensalidade", fn: (p) => formatCentavos(p?.numerico?.proposta_mensal_centavos) },
    {
      rotulo: "Diferença mensal",
      fn: (p) => formatCentavos(p?.numerico?.diff_mes_centavos),
    },
    { rotulo: "Diferença %", fn: (p) => formatBps(p?.numerico?.diff_bps) },
    {
      rotulo: "Diferença anual",
      fn: (p) => formatCentavos(p?.numerico?.diff_ano_centavos),
    },
    { rotulo: "Acomodação", fn: (p) => p?.acomodacao || "—" },
    { rotulo: "Coparticipação", fn: (p) => p?.regime_coparticipacao || "—" },
    { rotulo: "Validade", fn: (p) => p?.validade_oficial || "—" },
  ];

  return (
    <div className="cmp-matriz-scroll">
      <table className="conferencia cmp-matriz cmp-matriz--resumo">
        <thead>
          <tr>
            <th />
            <th>{planoAtual?.plano_nome || "Plano atual"}</th>
            {propostas.map((p) => (
              <th key={p.opcao_id}>{p.plano_nome}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Mensalidade (referência)</td>
            <td>{formatCentavos(planoAtual?.mensal_centavos)}</td>
            {propostas.map((p) => (
              <td key={p.opcao_id}>{formatCentavos(p.numerico?.proposta_mensal_centavos)}</td>
            ))}
          </tr>
          {linhas.slice(1).map((linha) => (
            <tr key={linha.rotulo}>
              <td>{linha.rotulo}</td>
              <td>—</td>
              {propostas.map((p) => (
                <td key={p.opcao_id}>{linha.fn(p)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ComparativoExperiencia({ estudoId, resultado }) {
  const todas = useMemo(
    () => (resultado?.propostas || []).filter((p) => p.calculo_realizado),
    [resultado]
  );

  const [modo, setModo] = useState("analise");
  const [vista, setVista] = useState("resumo");
  const [mostrarNomes, setMostrarNomes] = useState(false);
  const [ordenacao, setOrdenacao] = useState("menor_mensalidade");
  const [filtros, setFiltros] = useState({
    grupoRegime: "",
    acomodacao: "",
    operadora: "",
    precoMin: "",
    precoMax: "",
    semantica: "",
  });
  const [selecao, setSelecao] = useState(resultado?.propostas_apresentacao || []);
  const [salvandoSelecao, setSalvandoSelecao] = useState(false);
  const [auditoriaAberta, setAuditoriaAberta] = useState(false);

  useEffect(() => {
    if (resultado?.propostas_apresentacao) {
      setSelecao(resultado.propostas_apresentacao);
    }
  }, [resultado]);

  const filtrosNum = useMemo(
    () => ({
      ...filtros,
      precoMin: filtros.precoMin !== "" ? Math.round(Number(filtros.precoMin) * 100) : null,
      precoMax: filtros.precoMax !== "" ? Math.round(Number(filtros.precoMax) * 100) : null,
    }),
    [filtros]
  );

  const catalogo = useMemo(
    () => ordenarPropostas(filtrarPropostas(todas, filtrosNum), ordenacao),
    [todas, filtrosNum, ordenacao]
  );

  const selecionadas = useMemo(
    () => ordenarSelecao(todas, selecao),
    [todas, selecao]
  );

  const exibirCards = modo === "analise" ? catalogo : selecionadas;

  const persistirSelecao = useCallback(
    async (novaSelecao) => {
      if (!estudoId) return;
      setSalvandoSelecao(true);
      try {
        await salvarSelecaoApresentacao(estudoId, novaSelecao);
      } finally {
        setSalvandoSelecao(false);
      }
    },
    [estudoId]
  );

  function toggleSelecao(opcaoId) {
    setSelecao((prev) => {
      const nova = prev.includes(opcaoId)
        ? prev.filter((id) => id !== opcaoId)
        : [...prev, opcaoId];
      persistirSelecao(nova);
      return nova;
    });
  }

  const operadoras = opcoesUnicas(todas, "operadora");
  const acomodacoes = opcoesUnicas(todas, "acomodacao");

  return (
    <div className="cmp-experiencia">
      <div className="cmp-modos" role="tablist">
        <button
          type="button"
          role="tab"
          className={modo === "analise" ? "cmp-modo cmp-modo--ativo" : "cmp-modo"}
          onClick={() => setModo("analise")}
        >
          Análise Newport
        </button>
        <button
          type="button"
          role="tab"
          className={modo === "previa" ? "cmp-modo cmp-modo--ativo" : "cmp-modo"}
          onClick={() => setModo("previa")}
        >
          Prévia do cliente
        </button>
      </div>

      <div className="cmp-contadores">
        <span>
          <strong>{todas.length}</strong> calculada(s)
        </span>
        <span>
          <strong>{selecionadas.length}</strong> na apresentação
        </span>
        {salvandoSelecao && <span className="muted">Salvando seleção…</span>}
      </div>

      {modo === "analise" && (
        <>
          {resultado.consistencia && (
            <div
              className={
                resultado.consistencia.consistente
                  ? "comparativo-consistencia comparativo-consistencia--ok"
                  : "comparativo-consistencia comparativo-consistencia--erro"
              }
            >
              <strong>Consistência</strong>
              <p>
                {resultado.consistencia.propostas_selecionadas} proposta(s) ·{" "}
                {resultado.consistencia.cenarios_configurados} cenário(s) ·{" "}
                {resultado.consistencia.resultados_apresentados} resultado(s)
              </p>
              {resultado.consistencia.mensagem && (
                <p className="erro">{resultado.consistencia.mensagem}</p>
              )}
            </div>
          )}

          <section className="cmp-filtros cartao cartao--interno">
            <h3>Filtros e ordenação</h3>
            <div className="cmp-filtros-grid">
              <label>
                Coparticipação
                <select
                  value={filtros.grupoRegime}
                  onChange={(e) => setFiltros((f) => ({ ...f, grupoRegime: e.target.value }))}
                >
                  <option value="">Todas</option>
                  <option value="sem_copart">Sem coparticipação</option>
                  <option value="com_copart">Com coparticipação</option>
                </select>
              </label>
              <label>
                Acomodação
                <select
                  value={filtros.acomodacao}
                  onChange={(e) => setFiltros((f) => ({ ...f, acomodacao: e.target.value }))}
                >
                  <option value="">Todas</option>
                  {acomodacoes.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Operadora
                <select
                  value={filtros.operadora}
                  onChange={(e) => setFiltros((f) => ({ ...f, operadora: e.target.value }))}
                >
                  <option value="">Todas</option>
                  {operadoras.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Preço mín. (R$)
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={filtros.precoMin}
                  onChange={(e) => setFiltros((f) => ({ ...f, precoMin: e.target.value }))}
                />
              </label>
              <label>
                Preço máx. (R$)
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={filtros.precoMax}
                  onChange={(e) => setFiltros((f) => ({ ...f, precoMax: e.target.value }))}
                />
              </label>
              <label>
                Diferença
                <select
                  value={filtros.semantica}
                  onChange={(e) => setFiltros((f) => ({ ...f, semantica: e.target.value }))}
                >
                  <option value="">Todas</option>
                  <option value="economia">Economia</option>
                  <option value="aumento">Aumento</option>
                </select>
              </label>
              <label>
                Ordenar por
                <select value={ordenacao} onChange={(e) => setOrdenacao(e.target.value)}>
                  <option value="menor_mensalidade">Menor mensalidade</option>
                  <option value="menor_aumento">Menor aumento / maior economia</option>
                  <option value="mais_proximo">Mais próximo do contrato atual</option>
                </select>
              </label>
            </div>
          </section>
        </>
      )}

      {modo === "previa" && (
        <p className="cmp-previa-lead muted">
          Visualização limpa para o cliente — somente planos escolhidos para apresentação, sem
          detalhes técnicos.
        </p>
      )}

      <section className="cmp-cards-secao">
        <h3>{modo === "analise" ? "Propostas calculadas" : "Planos na apresentação"}</h3>
        <div className="cmp-cards-grid">
          {exibirCards.map((p) => (
            <CardProposta
              key={p.opcao_id}
              proposta={p}
              selecionada={selecao.includes(p.opcao_id)}
              onToggle={toggleSelecao}
              compacto={modo === "previa"}
            />
          ))}
        </div>
        {modo === "previa" && !exibirCards.length && (
          <p className="muted">
            Nenhum plano selecionado — volte à Análise Newport e adicione propostas à comparação.
          </p>
        )}
      </section>

      <section className="cmp-matriz-secao cartao cartao--interno">
        <header className="cmp-matriz-cabecalho">
          <h3>Matriz comparativa</h3>
          <div className="cmp-vistas">
            <button
              type="button"
              className={vista === "resumo" ? "cmp-vista cmp-vista--ativa" : "cmp-vista"}
              onClick={() => setVista("resumo")}
            >
              Resumo executivo
            </button>
            <button
              type="button"
              className={vista === "faixas" ? "cmp-vista cmp-vista--ativa" : "cmp-vista"}
              onClick={() => setVista("faixas")}
            >
              Faixas etárias
            </button>
            <button
              type="button"
              className={vista === "beneficiarios" ? "cmp-vista cmp-vista--ativa" : "cmp-vista"}
              onClick={() => setVista("beneficiarios")}
            >
              Por beneficiário
            </button>
          </div>
        </header>
        {vista === "beneficiarios" && modo === "analise" && (
          <label className="cmp-aviso-pii">
            <input
              type="checkbox"
              checked={mostrarNomes}
              onChange={(e) => setMostrarNomes(e.target.checked)}
            />
            Exibir nomes de beneficiários (dados pessoais — uso interno)
          </label>
        )}
        <MatrizComparativa
          planoAtual={resultado.plano_atual}
          propostas={selecionadas}
          vista={vista}
          mostrarNomes={modo === "analise" && mostrarNomes}
        />
      </section>

      {modo === "analise" && (
        <>
          <section className="cmp-detalhes-tecnicos">
            <h3>Detalhamento técnico por proposta</h3>
            {catalogo.map((p) => (
              <details key={p.opcao_id} className="comparativo-detalhe-proposta cartao cartao--interno">
                <summary>
                  <span className="comparativo-detalhe-nome">{p.plano_nome}</span>
                  <span className="muted">
                    {formatCentavos(p.numerico?.proposta_mensal_centavos)}/mês
                  </span>
                </summary>
                {p.pendencias?.length > 0 && <Pendencias items={p.pendencias} />}
                {p.secoes?.[0]?.vidas?.length > 0 && (
                  <table className="conferencia">
                    <thead>
                      <tr>
                        <th>Beneficiário</th>
                        <th>Idade</th>
                        <th>Faixa</th>
                        <th>Atual</th>
                        <th>Proposta</th>
                        <th>Diff</th>
                      </tr>
                    </thead>
                    <tbody>
                      {p.secoes[0].vidas.map((v) => (
                        <tr key={v.vida_id}>
                          <td>{v.nome}</td>
                          <td>{v.idade ?? "—"}</td>
                          <td>{v.faixa ?? "—"}</td>
                          <td>{formatCentavos(v.atual_centavos)}</td>
                          <td>{formatCentavos(v.proposta_centavos)}</td>
                          <td>{formatCentavos(v.diff_mes_centavos)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </details>
            ))}
          </section>

          <h3>Pendências e alertas</h3>
          <Pendencias items={resultado.pendencias} />

          <section className="cartao cartao--auditoria">
            <button type="button" className="link" onClick={() => setAuditoriaAberta((v) => !v)}>
              {auditoriaAberta ? "Ocultar" : "Mostrar"} auditoria técnica
            </button>
            {auditoriaAberta && (
              <table className="auditoria">
                <thead>
                  <tr>
                    <th>Código</th>
                    <th>Nível</th>
                    <th>Detalhe</th>
                  </tr>
                </thead>
                <tbody>
                  {resultado.auditoria.map((a, i) => (
                    <tr key={i}>
                      <td>{a.codigo}</td>
                      <td>{a.severidade}</td>
                      <td>{a.mensagem}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </div>
  );
}
