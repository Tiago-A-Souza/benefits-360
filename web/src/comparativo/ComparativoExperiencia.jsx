import { useCallback, useEffect, useMemo, useState } from "react";
import { salvarSelecaoApresentacao } from "../api";
import BloqueiosComparativo from "./BloqueiosComparativo";
import { FAIXAS_ROTULOS, classeVariacao, formatBps, formatCentavos } from "./format";
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

function rotuloCopartCurto(regime) {
  if (!regime) return "—";
  const r = regime.toLowerCase();
  if (r.includes("sem")) return "Sem copart";
  if (r.includes("parcial")) return "Copart parcial";
  if (r.includes("total")) return "Copart total";
  return regime;
}

function CardProposta({ proposta, selecionada, onToggle, compacto, seguroNovo }) {
  const n = proposta.numerico;
  const diffCls = classeVariacao(n?.diff_mes_centavos ?? n?.diff_bps);

  return (
    <article
      className={`cmp-card${selecionada ? " cmp-card--selecionada" : ""}${compacto ? " cmp-card--compacto" : ""}`}
    >
      <div className="cmp-card-bloco cmp-card-bloco--topo">
        <h4 className="cmp-card-nome">{proposta.plano_nome}</h4>
        <p className="cmp-card-meta">
          {proposta.operadora}
          {proposta.acomodacao ? ` · ${proposta.acomodacao}` : ""}
        </p>
      </div>

      <div className="cmp-card-bloco cmp-card-bloco--valor">
        <div className="cmp-card-mensal">
          <span className="cmp-card-mensal-valor">
            {formatCentavos(n?.proposta_mensal_centavos)}
          </span>
          <span className="cmp-card-mensal-rotulo">/ mês</span>
        </div>
        {seguroNovo ? (
          <div className={`cmp-card-diff ${diffCls}`}>
            <span>{formatCentavos(n?.diff_mes_centavos)}</span>
            <span className="cmp-card-diff-vs">vs menor proposta</span>
          </div>
        ) : (
          <div className={`cmp-card-diff ${diffCls}`}>
            <span>{formatCentavos(n?.diff_mes_centavos)}</span>
            <span className="cmp-card-diff-sep" aria-hidden>
              ·
            </span>
            <span>{formatBps(n?.diff_bps)}</span>
            <span className="cmp-card-diff-vs">vs atual</span>
          </div>
        )}
      </div>

      <div className="cmp-card-bloco cmp-card-bloco--rodape">
        <span className="cmp-card-chip">{rotuloCopartCurto(proposta.regime_coparticipacao)}</span>
        <button
          type="button"
          className={selecionada ? "cmp-card-btn cmp-card-btn--ativo" : "cmp-card-btn"}
          onClick={() => onToggle(proposta.opcao_id)}
        >
          {selecionada ? "Remover" : "Adicionar"}
        </button>
      </div>
    </article>
  );
}

function CelulaVariacao({ centavos, bps }) {
  const cls = classeVariacao(centavos ?? bps);
  return (
    <span className={cls}>
      {centavos != null && formatCentavos(centavos)}
      {bps != null && (
        <small className={centavos != null ? "cmp-var-pct" : undefined}>
          {centavos != null ? ` (${formatBps(bps)})` : formatBps(bps)}
        </small>
      )}
    </span>
  );
}

function CabecalhoMatriz({ planoAtual, propostas, seguroNovo }) {
  return (
    <thead className="cmp-matriz-thead">
      <tr>
        <th className="cmp-matriz-rotulo-col" scope="col">
          Indicador
        </th>
        {!seguroNovo && (
          <th className="cmp-col-atual" scope="col">
            <span className="cmp-col-badge">Contrato atual</span>
            <strong>{planoAtual?.plano_nome || "Plano atual"}</strong>
            {planoAtual?.operadora && (
              <span className="cmp-col-sub">{planoAtual.operadora}</span>
            )}
          </th>
        )}
        {propostas.map((p) => (
          <th key={p.opcao_id} scope="col">
            <strong>{p.plano_nome}</strong>
            {p.operadora && <span className="cmp-col-sub">{p.operadora}</span>}
          </th>
        ))}
      </tr>
    </thead>
  );
}

function DetalhesFixosMatriz({ planoAtual, propostas, seguroNovo }) {
  const linhas = [
    {
      rotulo: "Acomodação",
      atual: planoAtual?.acomodacao || "—",
      proposta: (p) => p.acomodacao || "—",
    },
    {
      rotulo: "Coparticipação",
      atual: planoAtual?.regime_coparticipacao || "—",
      proposta: (p) => p.regime_coparticipacao || "—",
    },
    {
      rotulo: "Custo total mensal",
      atual: formatCentavos(planoAtual?.mensal_centavos),
      proposta: (p) => formatCentavos(p.numerico?.proposta_mensal_centavos),
      destaque: true,
    },
    {
      rotulo: seguroNovo ? "Diferença vs menor proposta" : "Variação do custo",
      atual: "Referência",
      proposta: (p) => (
        <CelulaVariacao
          centavos={p.numerico?.diff_mes_centavos}
          bps={seguroNovo ? null : p.numerico?.diff_bps}
        />
      ),
    },
  ];

  return (
    <tbody className="cmp-matriz-fixos">
      {linhas.map((linha) => (
        <tr key={linha.rotulo} className={linha.destaque ? "cmp-linha-destaque" : undefined}>
          <th scope="row">{linha.rotulo}</th>
          {!seguroNovo && <td className="cmp-col-atual">{linha.atual}</td>}
          {propostas.map((p) => (
            <td key={p.opcao_id}>
              {typeof linha.proposta === "function" ? linha.proposta(p) : linha.proposta}
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  );
}

function SeparadorMatriz({ rotulo }) {
  return (
    <tbody className="cmp-matriz-separador">
      <tr>
        <td colSpan={100}>{rotulo}</td>
      </tr>
    </tbody>
  );
}

function MatrizComparativa({ planoAtual, propostas, vista, mostrarNomes, seguroNovo }) {
  if (!propostas.length) {
    return <p className="muted">Selecione ao menos uma proposta para montar a matriz comparativa.</p>;
  }

  const faixasAtual = propostas[0]?.faixas || [];

  return (
    <div className="cmp-matriz-scroll">
      <table className="conferencia cmp-matriz">
        <CabecalhoMatriz
          planoAtual={planoAtual}
          propostas={propostas}
          seguroNovo={seguroNovo}
        />
        <DetalhesFixosMatriz
          planoAtual={planoAtual}
          propostas={propostas}
          seguroNovo={seguroNovo}
        />

        {vista === "resumo" && (
          <>
            <SeparadorMatriz rotulo="Resumo executivo" />
            <tbody className="cmp-matriz-dados">
              <tr>
                <th scope="row">
                  {seguroNovo ? "Diferença vs menor (mês)" : "Diferença mensal"}
                </th>
                {!seguroNovo && <td className="cmp-col-atual">—</td>}
                {propostas.map((p) => (
                  <td key={p.opcao_id}>
                    <CelulaVariacao centavos={p.numerico?.diff_mes_centavos} bps={null} />
                  </td>
                ))}
              </tr>
              <tr>
                <th scope="row">
                  {seguroNovo ? "Diferença vs menor (ano)" : "Diferença anual"}
                </th>
                {!seguroNovo && <td className="cmp-col-atual">—</td>}
                {propostas.map((p) => (
                  <td key={p.opcao_id} className={classeVariacao(p.numerico?.diff_ano_centavos)}>
                    {formatCentavos(p.numerico?.diff_ano_centavos)}
                  </td>
                ))}
              </tr>
              <tr>
                <th scope="row">Validade da cotação</th>
                {!seguroNovo && <td className="cmp-col-atual">—</td>}
                {propostas.map((p) => (
                  <td key={p.opcao_id}>{p.validade_oficial || "—"}</td>
                ))}
              </tr>
            </tbody>
          </>
        )}

        {vista === "faixas" && (
          <>
            <SeparadorMatriz rotulo="Valores por faixa etária (soma do grupo)" />
            <tbody className="cmp-matriz-dados">
              {[...new Set(propostas.flatMap((p) => (p.faixas || []).map((f) => f.faixa)))]
                .sort((a, b) => a - b)
                .map((fx) => {
                  const faixaAtual = faixasAtual.find((f) => f.faixa === fx);
                  return (
                    <tr key={fx}>
                      <th scope="row">{FAIXAS_ROTULOS[fx] || `Faixa ${fx + 1}`}</th>
                      {!seguroNovo && (
                        <td className="cmp-col-atual">
                          {formatCentavos(faixaAtual?.atual_centavos)}
                          {faixaAtual?.quantidade > 1 && (
                            <small className="cmp-faixa-qtd"> ({faixaAtual.quantidade} vidas)</small>
                          )}
                        </td>
                      )}
                      {propostas.map((p) => {
                        const f = (p.faixas || []).find((x) => x.faixa === fx);
                        return (
                          <td key={p.opcao_id}>
                            {formatCentavos(f?.proposta_centavos)}
                            {f?.quantidade > 1 && (
                              <small className="cmp-faixa-qtd"> ({f.quantidade} vidas)</small>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
            </tbody>
          </>
        )}

        {vista === "beneficiarios" && (
          <>
            {!mostrarNomes && (
              <tbody className="cmp-matriz-aviso">
                <tr>
                  <td colSpan={100}>
                    <p className="alerta cmp-aviso-inline">
                      Modo agregado — nomes ocultos. Ative a exibição para revisão interna.
                    </p>
                  </td>
                </tr>
              </tbody>
            )}
            <SeparadorMatriz rotulo="Detalhamento por beneficiário" />
            <tbody className="cmp-matriz-dados">
              {(propostas[0]?.secoes?.[0]?.vidas || []).map((v) => (
                <tr key={v.vida_id}>
                  <th scope="row">
                    {mostrarNomes ? v.nome : `Beneficiário · faixa ${(v.faixa ?? 0) + 1}`}
                  </th>
                  {!seguroNovo && (
                    <td className="cmp-col-atual">
                      {formatCentavos(v.atual_centavos)}
                    </td>
                  )}
                  {propostas.map((p) => {
                    const pv = p.secoes?.[0]?.vidas?.find((x) => x.vida_id === v.vida_id);
                    return (
                      <td key={p.opcao_id}>{formatCentavos(pv?.proposta_centavos)}</td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </>
        )}
      </table>
    </div>
  );
}

export default function ComparativoExperiencia({
  estudoId,
  resultado,
  rascunho = null,
  rotuloEtapa = "Comparativo",
  confirmado = false,
  confirmando = false,
  onConfirmar,
  onRecalcular,
  recalculando,
}) {
  const seguroNovo =
    resultado?.formato === "novo" || rascunho?.formato === "novo";

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
    if (Array.isArray(resultado?.propostas_apresentacao)) {
      setSelecao(resultado.propostas_apresentacao);
    }
  }, [resultado?.propostas_apresentacao]);

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
  const planoAtual = resultado.plano_atual;
  const filtrosAtivos = Object.entries(filtros).filter(
    ([, v]) => v !== "" && v != null
  ).length;

  function limparFiltros() {
    setFiltros({
      grupoRegime: "",
      acomodacao: "",
      operadora: "",
      precoMin: "",
      precoMax: "",
      semantica: "",
    });
  }

  const podeConfirmar =
    !confirmado &&
    !confirmando &&
    selecao.length > 0 &&
    Boolean(resultado?.calculo_realizado) &&
    resultado?.consistencia?.consistente !== false;

  return (
    <div className="cmp-experiencia">
      <header className="cmp-hero cmp-hero--compact">
        <div className="cmp-hero-linha cmp-hero-linha--titulo">
          <div className="cmp-hero-identidade">
            <span className="cmp-etapa">{rotuloEtapa}</span>
            <h2 className="cmp-hero-titulo">{resultado.titulo || "Análise comparativa"}</h2>
          </div>
          <div className="cmp-hero-acoes-topo">
            {onRecalcular && (
              <button
                type="button"
                className="secundario cmp-btn-recalc"
                onClick={onRecalcular}
                disabled={recalculando}
              >
                {recalculando ? "Calculando…" : "Recalcular"}
              </button>
            )}
            {resultado.consistencia && modo === "analise" && (
              <div
                className={
                  resultado.consistencia.consistente
                    ? "cmp-status cmp-status--ok"
                    : "cmp-status cmp-status--erro"
                }
                title={resultado.consistencia.mensagem || undefined}
              >
                {resultado.consistencia.consistente ? "Consistente" : "Inconsistente"}
                <span className="cmp-status-det">
                  {resultado.consistencia.resultados_apresentados}/
                  {resultado.consistencia.propostas_selecionadas}
                </span>
              </div>
            )}
            {salvandoSelecao && <span className="cmp-salvando">Salvando…</span>}
          </div>
        </div>

        <div className="cmp-hero-linha cmp-hero-linha--dados">
          <div className="cmp-kpis">
            <div className="cmp-kpi">
              <span className="cmp-kpi-valor">{todas.length}</span>
              <span className="cmp-kpi-rotulo">Calculadas</span>
            </div>
            <div className="cmp-kpi cmp-kpi--ativo">
              <span className="cmp-kpi-valor">{selecionadas.length}</span>
              <span className="cmp-kpi-rotulo">Apresentação</span>
            </div>
            <div className="cmp-kpi">
              <span className="cmp-kpi-valor">{resultado.beneficiarios_calculados}</span>
              <span className="cmp-kpi-rotulo">Beneficiários</span>
            </div>
            {resultado.validade_proposta && (
              <div className="cmp-kpi">
                <span className="cmp-kpi-valor cmp-kpi-valor--sm">{resultado.validade_proposta}</span>
                <span className="cmp-kpi-rotulo">Validade</span>
              </div>
            )}
          </div>

          {planoAtual && (
            <div className="cmp-ref-bar" title={`${planoAtual.plano_nome} · ${planoAtual.operadora}`}>
              <span className="cmp-ref-etiq">Referência</span>
              <p className="cmp-ref-texto">
                <strong>{planoAtual.plano_nome}</strong>
                <span className="cmp-ref-sep">·</span>
                <span>{planoAtual.operadora}</span>
                {planoAtual.acomodacao && (
                  <>
                    <span className="cmp-ref-sep">·</span>
                    <span>{planoAtual.acomodacao}</span>
                  </>
                )}
              </p>
              <span className="cmp-ref-valor">{formatCentavos(planoAtual.mensal_centavos)}</span>
            </div>
          )}
        </div>

        <div className="cmp-hero-linha cmp-hero-linha--modos">
          <div className="cmp-segmento" role="tablist" aria-label="Modo de visualização">
            <button
              type="button"
              role="tab"
              aria-selected={modo === "analise"}
              title="Catálogo completo, filtros e auditoria"
              className={modo === "analise" ? "cmp-seg cmp-seg--ativo" : "cmp-seg"}
              onClick={() => setModo("analise")}
            >
              Análise Newport
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={modo === "previa"}
              title="Somente planos selecionados para o cliente"
              className={modo === "previa" ? "cmp-seg cmp-seg--ativo" : "cmp-seg"}
              onClick={() => setModo("previa")}
            >
              Prévia do cliente
            </button>
          </div>
          <p className="cmp-modo-hint muted">
            {modo === "analise"
              ? "Catálogo completo · selecione propostas para apresentação"
              : "Espelho do material ao cliente · somente selecionados"}
          </p>
        </div>
      </header>

      {modo === "analise" && (
        <section className="cmp-filtros">
          <div className="cmp-filtros-bar">
            <h3 className="cmp-secao-titulo">Refinar catálogo</h3>
            <span className="cmp-filtros-pill">
              {catalogo.length}/{todas.length} visíveis
            </span>
            {filtrosAtivos > 0 && (
              <>
                <span className="cmp-filtros-pill cmp-filtros-pill--ativo">
                  {filtrosAtivos} filtro(s)
                </span>
                <button type="button" className="cmp-btn-limpar" onClick={limparFiltros}>
                  Limpar
                </button>
              </>
            )}
          </div>
          <div className="cmp-filtros-grid">
            <div className="cmp-filtro">
              <span className="cmp-filtro-label">Coparticipação</span>
              <select
                value={filtros.grupoRegime}
                onChange={(e) => setFiltros((f) => ({ ...f, grupoRegime: e.target.value }))}
              >
                <option value="">Todas</option>
                <option value="sem_copart">Sem coparticipação</option>
                <option value="com_copart">Com coparticipação</option>
              </select>
            </div>
            <div className="cmp-filtro">
              <span className="cmp-filtro-label">Acomodação</span>
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
            </div>
            <div className="cmp-filtro">
              <span className="cmp-filtro-label">Operadora</span>
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
            </div>
            <div className="cmp-filtro">
              <span className="cmp-filtro-label">Diferença</span>
              <select
                value={filtros.semantica}
                onChange={(e) => setFiltros((f) => ({ ...f, semantica: e.target.value }))}
              >
                <option value="">Todas</option>
                <option value="economia">Economia</option>
                <option value="aumento">Aumento</option>
              </select>
            </div>
            <div className="cmp-filtro cmp-filtro--preco">
              <span className="cmp-filtro-label">Faixa de preço (R$)</span>
              <div className="cmp-filtro-faixa">
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="Mín"
                  value={filtros.precoMin}
                  onChange={(e) => setFiltros((f) => ({ ...f, precoMin: e.target.value }))}
                />
                <span aria-hidden>—</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="Máx"
                  value={filtros.precoMax}
                  onChange={(e) => setFiltros((f) => ({ ...f, precoMax: e.target.value }))}
                />
              </div>
            </div>
            <div className="cmp-filtro cmp-filtro--ordem">
              <span className="cmp-filtro-label">Ordenar por</span>
              <select value={ordenacao} onChange={(e) => setOrdenacao(e.target.value)}>
                <option value="menor_mensalidade">Menor mensalidade</option>
                {!seguroNovo && (
                  <>
                    <option value="menor_aumento">Menor aumento / maior economia</option>
                    <option value="mais_proximo">Mais próximo do contrato atual</option>
                  </>
                )}
              </select>
            </div>
          </div>
        </section>
      )}

      <section className="cmp-cards-secao">
        <header className="cmp-secao-cabecalho cmp-secao-cabecalho--cards">
          <div>
            <h3 className="cmp-secao-titulo">
              {modo === "analise" ? "Propostas calculadas" : "Planos na apresentação"}
              <span className="cmp-contagem">{exibirCards.length}</span>
            </h3>
            <p className="cmp-secao-sub muted">
              {modo === "analise"
                ? "Clique em Adicionar para incluir na matriz — a seleção é salva automaticamente."
                : "Material que será entregue ao cliente."}
            </p>
          </div>
          {modo === "analise" && selecionadas.length > 0 && (
            <span className="cmp-cards-resumo">
              {selecionadas.length} na apresentação
            </span>
          )}
        </header>
        <div className="cmp-cards-grid">
          {exibirCards.map((p) => (
            <CardProposta
              key={p.opcao_id}
              proposta={p}
              selecionada={selecao.includes(p.opcao_id)}
              onToggle={toggleSelecao}
              compacto={modo === "previa"}
              seguroNovo={seguroNovo}
            />
          ))}
        </div>
        {modo === "previa" && !exibirCards.length && (
          <p className="muted">
            Nenhum plano selecionado — volte à Análise Newport e adicione propostas à comparação.
          </p>
        )}
      </section>

      <section className="cmp-matriz-secao">
        <header className="cmp-matriz-cabecalho">
          <div>
            <h3 className="cmp-secao-titulo">Matriz comparativa</h3>
            <p className="cmp-secao-sub muted">
              {seguroNovo
                ? `Comparativo entre propostas · ${selecionadas.length} proposta(s) selecionada(s)`
                : `Contrato atual na primeira coluna · ${selecionadas.length} proposta(s) selecionada(s)`}
            </p>
          </div>
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
          seguroNovo={seguroNovo}
        />
      </section>

      {resultado?.calculo_realizado && onConfirmar && (
        <section className="cmp-confirmacao-secao">
          <h3 className="cmp-secao-titulo">Confirmar revisão</h3>
          {!resultado.consistencia?.consistente && (
            <>
              <BloqueiosComparativo
                consistencia={resultado.consistencia}
                rascunho={rascunho}
              />
              {!resultado.consistencia?.bloqueios?.length && (
                <p className="erro">
                  {resultado.consistencia?.mensagem ||
                    "O comparativo está inconsistente — corrija pendências antes de confirmar."}
                </p>
              )}
            </>
          )}
          {!resultado.hash_comparativo && (
            <p className="muted">
              A versão do comparativo será validada no servidor ao confirmar.
            </p>
          )}
          <p className="cmp-secao-sub muted">
            {selecao.length === 0
              ? "Adicione ao menos uma proposta na matriz (botão «Adicionar» nos cards)."
              : confirmado
                ? "Comparativo confirmado. Use «Próxima etapa» para ir à Apresentação."
                : `${selecao.length} proposta(s) selecionada(s) para o material ao cliente.`}
          </p>
          <button
            type="button"
            className="cmp-btn-principal"
            disabled={!podeConfirmar}
            onClick={() => onConfirmar(selecao)}
          >
            {confirmando
              ? "Confirmando…"
              : "Confirmar comparativo e continuar para apresentação"}
          </button>
        </section>
      )}

      {modo === "analise" && (
        <>
          <section className="cmp-detalhes-tecnicos">
            <header className="cmp-secao-cabecalho cmp-secao-cabecalho--cards">
              <div>
                <h3 className="cmp-secao-titulo">
                  Detalhamento técnico
                  <span className="cmp-contagem">{catalogo.length}</span>
                </h3>
                <p className="cmp-secao-sub muted">
                  Expanda cada proposta para revisar valores por beneficiário (uso interno).
                </p>
              </div>
            </header>
            <div className="cmp-detalhes-lista">
              {catalogo.map((p) => {
                const n = p.numerico;
                const diffCls = classeVariacao(n?.diff_mes_centavos ?? n?.diff_bps);
                return (
                  <details key={p.opcao_id} className="cmp-detalhe">
                    <summary className="cmp-detalhe-sum">
                      <span className="cmp-detalhe-chevron" aria-hidden />
                      <div className="cmp-detalhe-info">
                        <span className="cmp-detalhe-nome">{p.plano_nome}</span>
                        <span className="cmp-detalhe-meta">
                          {p.operadora}
                          {p.acomodacao ? ` · ${p.acomodacao}` : ""}
                          {" · "}
                          {rotuloCopartCurto(p.regime_coparticipacao)}
                        </span>
                      </div>
                      <div className="cmp-detalhe-valores">
                        <span className="cmp-detalhe-preco">
                          {formatCentavos(n?.proposta_mensal_centavos)}
                          <small>/mês</small>
                        </span>
                        <span className={`cmp-detalhe-diff ${diffCls}`}>
                          {formatCentavos(n?.diff_mes_centavos)} · {formatBps(n?.diff_bps)}
                        </span>
                      </div>
                      {p.pendencias?.length > 0 && (
                        <span className="cmp-detalhe-alerta" title="Pendências nesta proposta">
                          {p.pendencias.length}
                        </span>
                      )}
                    </summary>
                    <div className="cmp-detalhe-corpo">
                      {p.pendencias?.length > 0 && <Pendencias items={p.pendencias} />}
                      {p.secoes?.[0]?.vidas?.length > 0 ? (
                        <div className="cmp-detalhe-tabela-scroll">
                          <table className="conferencia cmp-detalhe-tabela">
                            <thead>
                              <tr>
                                <th>Beneficiário</th>
                                <th>Idade</th>
                                <th>Faixa</th>
                                {!seguroNovo && <th>Atual</th>}
                                <th>Proposta</th>
                                {!seguroNovo && <th>Diff</th>}
                              </tr>
                            </thead>
                            <tbody>
                              {p.secoes[0].vidas.map((v) => (
                                <tr key={v.vida_id}>
                                  <td>{v.nome}</td>
                                  <td>{v.idade ?? "—"}</td>
                                  <td>{v.faixa ?? "—"}</td>
                                  {!seguroNovo && (
                                    <td>{formatCentavos(v.atual_centavos)}</td>
                                  )}
                                  <td>{formatCentavos(v.proposta_centavos)}</td>
                                  {!seguroNovo && (
                                    <td className={classeVariacao(v.diff_mes_centavos)}>
                                      {formatCentavos(v.diff_mes_centavos)}
                                    </td>
                                  )}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <p className="muted cmp-detalhe-vazio">Sem detalhamento por beneficiário.</p>
                      )}
                    </div>
                  </details>
                );
              })}
            </div>
          </section>

          <section className="cmp-auditoria-secao">
            <h3 className="cmp-secao-titulo">Pendências e alertas</h3>
            <Pendencias items={resultado.pendencias} />
            <button type="button" className="link cmp-link-auditoria" onClick={() => setAuditoriaAberta((v) => !v)}>
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
