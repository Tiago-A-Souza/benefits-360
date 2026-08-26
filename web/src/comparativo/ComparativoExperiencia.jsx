import { useCallback, useEffect, useMemo, useState } from "react";
import { salvarSelecaoApresentacao } from "../api";
import BloqueiosComparativo from "./BloqueiosComparativo";
import { classeVariacao, formatBps, formatCentavos } from "./format";
import {
  filtrarPropostas,
  opcoesUnicas,
  ordenarPropostas,
  ordenarSelecao,
  paginarPropostas,
} from "./logica";

function Pendencias({ items }) {
  if (!items?.length) return <p className="ok">Nenhuma pendência bloqueante nesta verificação.</p>;
  return (
    <ul className="pendencias cmp-pendencias-lista">
      {items.map((p, i) => (
        <li key={p.codigo || i} className={`pendencia pendencia--${p.tipo} cmp-pendencia-item`}>
          <div className="cmp-pendencia-cabecalho">
            {p.codigo && <span className="cmp-bloqueio-codigo">{p.codigo}</span>}
            <strong>{p.titulo}</strong>
          </div>
          {p.descricao && <p>{p.descricao}</p>}
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

function CardProposta({ proposta, selecionada, onToggle, compacto, seguroNovo, somenteLeitura }) {
  const n = proposta.numerico;
  const diffCls = classeVariacao(n?.diff_mes_centavos ?? n?.diff_bps);

  return (
    <article
      className={`proposal cmp-card${selecionada ? " selected cmp-card--selecionada" : ""}${compacto ? " cmp-card--compacto" : ""}`}
    >
      <div className="cmp-card-bloco cmp-card-bloco--topo">
        <b className="cmp-card-nome">{proposta.plano_nome}</b>
        <div className="op cmp-card-meta">
          {proposta.operadora}
          {proposta.acomodacao ? ` · ${proposta.acomodacao}` : ""}
        </div>
      </div>

      <div className="cmp-card-bloco cmp-card-bloco--valor">
        <div className="price cmp-card-mensal">
          <span className="cmp-card-mensal-valor">
            {formatCentavos(n?.proposta_mensal_centavos)}
          </span>
          <span className="cmp-card-mensal-rotulo">/ mês</span>
        </div>
        {seguroNovo ? (
          <div className={`delta cmp-card-diff ${diffCls}`}>
            <span>{formatCentavos(n?.diff_mes_centavos)}</span>
            <span className="cmp-card-diff-vs">vs menor proposta</span>
          </div>
        ) : (
          <div className={`delta cmp-card-diff ${diffCls}`}>
            <span>{formatCentavos(n?.diff_mes_centavos)}</span>
            <span className="cmp-card-diff-sep" aria-hidden>
              ·
            </span>
            <span>{formatBps(n?.diff_bps)}</span>
            <span className="cmp-card-diff-vs">vs atual</span>
          </div>
        )}
      </div>

      <div className="proposal-foot cmp-card-bloco cmp-card-bloco--rodape">
        <span className="cmp-card-chip">{rotuloCopartCurto(proposta.regime_coparticipacao)}</span>
        {!somenteLeitura && (
          <button
            type="button"
            className={
              selecionada
                ? "select-toggle cmp-card-btn cmp-card-btn--ativo"
                : "select-toggle cmp-card-btn"
            }
            onClick={() => onToggle(proposta.opcao_id)}
          >
            {selecionada ? "No documento" : "Adicionar"}
          </button>
        )}
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

function vidasDaProposta(proposta) {
  return (proposta?.secoes || []).flatMap((s) => s.vidas || []);
}

function recorteSubgrupo(proposta, subgrupoId) {
  return (proposta?.subgrupos || []).find((s) => s.subgrupo_id === subgrupoId);
}

function valorUnico(itens, campo) {
  const vals = [...new Set((itens || []).map((x) => x?.[campo]).filter((v) => v))];
  return vals.length === 1 ? vals[0] : null;
}

function somarCampo(itens, campo) {
  return (itens || []).reduce((acc, x) => acc + (x?.[campo] || 0), 0);
}

/** Seções da matriz por grupo_regime — mesmo critério do HTML de apresentação. */
function agruparPropostasPorRegime(propostas) {
  const buckets = { sem_copart: [], com_copart: [] };
  for (const p of propostas || []) {
    const chave = p.grupo_regime === "com_copart" ? "com_copart" : "sem_copart";
    buckets[chave].push(p);
  }
  const secoes = [];
  if (buckets.sem_copart.length) {
    secoes.push({
      chave: "sem_copart",
      rotulo: "Sem coparticipação",
      propostas: buckets.sem_copart,
    });
  }
  if (buckets.com_copart.length) {
    const rotulo =
      valorUnico(buckets.com_copart, "regime_coparticipacao") || "Com coparticipação";
    secoes.push({
      chave: "com_copart",
      rotulo,
      propostas: buckets.com_copart,
    });
  }
  return secoes;
}

function CabecalhoMatriz({ planosAtuais, propostas, seguroNovo }) {
  const varios = (planosAtuais || []).length > 1;
  const unico = (planosAtuais || []).length === 1 ? planosAtuais[0] : null;
  return (
    <thead className="cmp-matriz-thead">
      <tr>
        <th className="cmp-matriz-rotulo-col" scope="col">
          Indicador
        </th>
        {!seguroNovo && (
          <th className="cmp-col-atual" scope="col">
            <span className="cmp-col-badge">Contrato atual</span>
            <strong>{varios ? "Contrato atual" : unico?.plano_nome || "Plano atual"}</strong>
            {!varios && unico?.operadora && (
              <span className="cmp-col-sub">{unico.operadora}</span>
            )}
            {varios && <span className="cmp-col-sub">vários planos</span>}
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

function DetalhesFixosMatriz({ planosAtuais, propostas, seguroNovo }) {
  const consolidadoMensal = somarCampo(planosAtuais, "mensal_centavos");
  const linhas = [
    {
      rotulo: "Acomodação",
      atual: valorUnico(planosAtuais, "acomodacao") || "—",
      proposta: (p) => p.acomodacao || "—",
    },
    {
      rotulo: "Coparticipação",
      atual: valorUnico(planosAtuais, "regime_coparticipacao") || "—",
      proposta: (p) => p.regime_coparticipacao || "—",
    },
    {
      rotulo: "Custo total mensal",
      atual: formatCentavos(planosAtuais?.length ? consolidadoMensal : null),
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

function CelulaPlanoAtual({ plano, percentual }) {
  const [aberto, setAberto] = useState(false);
  const reajustado = formatCentavos(plano?.reajustado_centavos);
  const vigente = formatCentavos(plano?.vigente_centavos);
  const temVigente = plano?.vigente_centavos != null;

  return (
    <div className="cmp-cel-reajuste">
      <button
        type="button"
        className="cmp-cel-reajuste__botao"
        aria-expanded={aberto}
        aria-label={
          temVigente
            ? `Contrato reajustado ${reajustado}${percentual ? ` ${percentual}` : ""}. Ativar para ver o valor vigente.`
            : `Contrato reajustado ${reajustado}`
        }
        disabled={!temVigente}
        onClick={() => setAberto((v) => !v)}
      >
        <span className="cmp-cel-reajuste__valor">{reajustado}</span>
        {percentual ? <span className="cmp-cel-reajuste__pct">{percentual}</span> : null}
      </button>
      {aberto && temVigente && (
        <div className="cmp-cel-reajuste__caixa" role="region" aria-label="Valor vigente">
          Antes: {vigente}
        </div>
      )}
    </div>
  );
}

function CelulaVigenteOculto({ vigente, vigenteUnitario, quantidade }) {
  const [aberto, setAberto] = useState(false);
  return (
    <div className="cmp-cel-reajuste cmp-cel-reajuste--faixa">
      <button
        type="button"
        className="cmp-cel-reajuste__botao cmp-cel-reajuste__botao--link"
        aria-expanded={aberto}
        aria-label="Ver valor vigente desta faixa"
        onClick={() => setAberto((v) => !v)}
      >
        {aberto ? "Ocultar vigente" : "Ver vigente"}
      </button>
      {aberto && (
        <div className="cmp-cel-reajuste__caixa" role="region" aria-label="Valor vigente">
          {celulaFaixa({
            unitario: vigenteUnitario,
            quantidade,
            subtotal: vigente,
            sufixo: "vigente",
          })}
        </div>
      )}
    </div>
  );
}

function celulaFaixa({ unitario, quantidade, subtotal, sufixo }) {
  const extra = sufixo ? ` ${sufixo}` : "";
  if (unitario != null && quantidade > 0) {
    return (
      <div>
        {formatCentavos(unitario)}
        <small className="cmp-faixa-detalhe">
          {" "}
          · {quantidade} · {formatCentavos(subtotal)}
          {extra}
        </small>
      </div>
    );
  }
  return (
    <div>
      {formatCentavos(subtotal)}
      {extra && <small className="cmp-faixa-qtd">{extra}</small>}
    </div>
  );
}

function TabelaFaixasPlano({ plano, propostas, seguroNovo }) {
  if (!plano?.faixas?.length) {
    return (
      <p className="muted">
        Nenhuma faixa etária disponível neste recorte. Os totais do comparativo
        não foram agregados nesta tela.
      </p>
    );
  }

  return (
    <table className="conferencia cmp-matriz">
      <caption className="cmp-matriz-caption">
        {seguroNovo
          ? "Distribuição por faixa etária"
          : `Plano atual — ${plano.operadora} · ${plano.plano_nome}`}
      </caption>
      <CabecalhoMatriz
        planosAtuais={seguroNovo ? [] : [plano]}
        propostas={propostas}
        seguroNovo={seguroNovo}
      />
      <tbody className="cmp-matriz-dados">
        {plano.faixas.map((fx) => (
          <tr key={fx.faixa}>
            <th scope="row">
              {fx.rotulo}
              {fx.quantidade > 1 && (
                <small className="cmp-faixa-qtd"> ({fx.quantidade} vidas)</small>
              )}
              {fx.observacao_valor && (
                <small className="cmp-faixa-obs">{fx.observacao_valor}</small>
              )}
            </th>
            {!seguroNovo && (
              <td className="cmp-col-atual">
                {celulaFaixa({
                  unitario: fx.reajustado_unitario_centavos,
                  quantidade: fx.quantidade,
                  subtotal: fx.reajustado_total_centavos,
                })}
                {plano.reajuste_percentual_exibicao ? (
                  <div className="cmp-cel-reajuste__pct">{plano.reajuste_percentual_exibicao}</div>
                ) : null}
                {fx.vigente_total_centavos != null && (
                  <CelulaVigenteOculto
                    vigente={fx.vigente_total_centavos}
                    vigenteUnitario={fx.vigente_unitario_centavos}
                    quantidade={fx.quantidade}
                  />
                )}
              </td>
            )}
            {propostas.map((p) => {
              const col = (fx.propostas || []).find((c) => c.opcao_id === p.opcao_id);
              return (
                <td key={p.opcao_id}>
                  {celulaFaixa({
                    unitario: col?.unitario_centavos,
                    quantidade: col?.quantidade || 0,
                    subtotal: col?.subtotal_centavos,
                  })}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
      <tfoot className="cmp-matriz-totais">
        <tr>
          <th scope="row">Totais</th>
          {!seguroNovo && (
            <td className="cmp-col-atual">
              <CelulaPlanoAtual
                plano={plano}
                percentual={plano.reajuste_percentual_exibicao}
              />
            </td>
          )}
          {propostas.map((p) => (
            <td key={p.opcao_id}>
              {formatCentavos(
                seguroNovo
                  ? p.numerico?.proposta_mensal_centavos
                  : recorteSubgrupo(p, plano.subgrupo_id)?.proposta_centavos
              )}
            </td>
          ))}
        </tr>
      </tfoot>
    </table>
  );
}

function ConteudoMatriz({
  planosAtuais,
  propostas,
  vista,
  mostrarNomes,
  seguroNovo,
  faixasEstudo,
  reajusteConsolidadoPct,
}) {
  const vidasRef = vidasDaProposta(propostas[0]);

  return (
    <>
      {vista === "faixas" ? (
        <>
          <p className="cmp-matriz-separador-texto">Valores por faixa etária (soma do grupo)</p>
          {seguroNovo ? (
            <TabelaFaixasPlano
              plano={{ faixas: faixasEstudo || [] }}
              propostas={propostas}
              seguroNovo
            />
          ) : !(planosAtuais || []).length ? (
            <p className="muted">Nenhum plano vigente neste estudo para montar a tabela de faixas.</p>
          ) : (
            planosAtuais.map((plano) => (
              <TabelaFaixasPlano
                key={plano.subgrupo_id}
                plano={plano}
                propostas={propostas}
                seguroNovo={false}
              />
            ))
          )}
        </>
      ) : (
      <table className="conferencia cmp-matriz">
        <CabecalhoMatriz
          planosAtuais={planosAtuais}
          propostas={propostas}
          seguroNovo={seguroNovo}
        />
        <DetalhesFixosMatriz
          planosAtuais={planosAtuais}
          propostas={propostas}
          seguroNovo={seguroNovo}
        />

        {vista === "resumo" && (
          <>
            <SeparadorMatriz rotulo="Resumo executivo" />
            <tbody className="cmp-matriz-dados">
              {!seguroNovo &&
                (planosAtuais || []).map((pl) => (
                  <tr key={pl.subgrupo_id}>
                    <th scope="row">{pl.plano_nome}</th>
                    <td className="cmp-col-atual">
                      <CelulaPlanoAtual
                        plano={pl}
                        percentual={pl.reajuste_percentual_exibicao}
                      />
                    </td>
                    {propostas.map((p) => (
                      <td key={p.opcao_id}>
                        {formatCentavos(recorteSubgrupo(p, pl.subgrupo_id)?.proposta_centavos)}
                      </td>
                    ))}
                  </tr>
                ))}
              {!seguroNovo && (planosAtuais || []).length > 0 && (
                <tr>
                  <th scope="row">Consolidado</th>
                  <td className="cmp-col-atual">
                    <CelulaPlanoAtual
                      plano={{
                        vigente_centavos: somarCampo(planosAtuais, "vigente_centavos"),
                        reajustado_centavos: somarCampo(planosAtuais, "reajustado_centavos"),
                      }}
                      percentual={reajusteConsolidadoPct}
                    />
                  </td>
                  {propostas.map((p) => (
                    <td key={p.opcao_id}>
                      {formatCentavos(p.numerico?.proposta_mensal_centavos)}
                    </td>
                  ))}
                </tr>
              )}
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
              {vidasRef.map((v) => (
                <tr key={v.vida_id}>
                  <th scope="row">
                    {mostrarNomes ? v.nome : `Beneficiário · ${v.faixa_rotulo || "faixa não informada"}`}
                    {!seguroNovo && v.plano_atual && (
                      <small className="cmp-faixa-qtd"> · {v.plano_atual}</small>
                    )}
                  </th>
                  {!seguroNovo && (
                    <td className="cmp-col-atual">
                      {formatCentavos(v.atual_centavos)}
                    </td>
                  )}
                  {propostas.map((p) => {
                    const pv = vidasDaProposta(p).find((x) => x.vida_id === v.vida_id);
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
      )}
    </>
  );
}

function MatrizComparativa({
  planosAtuais,
  propostas,
  vista,
  mostrarNomes,
  seguroNovo,
  faixasEstudo,
  reajusteConsolidadoPct,
}) {
  if (!propostas.length) {
    return <p className="muted">Selecione ao menos uma proposta para montar a matriz comparativa.</p>;
  }

  const secoes = agruparPropostasPorRegime(propostas);

  return (
    <>
      <div className="cmp-matriz-scroll cmp-matriz-tela">
        {secoes.map((secao) => (
          <div key={secao.chave} className="cmp-matriz-regime">
            <h4 className="cmp-matriz-regime-titulo">{secao.rotulo}</h4>
            <ConteudoMatriz
              planosAtuais={planosAtuais}
              propostas={secao.propostas}
              vista={vista}
              mostrarNomes={mostrarNomes}
              seguroNovo={seguroNovo}
              faixasEstudo={faixasEstudo}
              reajusteConsolidadoPct={reajusteConsolidadoPct}
            />
          </div>
        ))}
      </div>
      <div className="cmp-matriz-impressao">
        {secoes.map((secao) => {
          const paginas = paginarPropostas(secao.propostas);
          return paginas.map((chunk) => (
            <div
              className="cmp-matriz-pagina-print"
              key={`${secao.chave}-${chunk.map((p) => p.opcao_id).join("-")}`}
            >
              <h4 className="cmp-matriz-regime-titulo">{secao.rotulo}</h4>
              <ConteudoMatriz
                planosAtuais={planosAtuais}
                propostas={chunk}
                vista={vista}
                mostrarNomes={mostrarNomes}
                seguroNovo={seguroNovo}
                faixasEstudo={faixasEstudo}
                reajusteConsolidadoPct={reajusteConsolidadoPct}
              />
            </div>
          ));
        })}
      </div>
    </>
  );
}

export default function ComparativoExperiencia({
  estudoId,
  resultado,
  rascunho = null,
  etapaIndice = 5,
  totalEtapas = 5,
  rotuloEtapa = "Comparativo",
  confirmado = false,
  confirmando = false,
  onConfirmar,
  onRecalcular,
  onSelecaoSalva,
  avisoSelecaoAlterada = false,
  recalculando,
  origemCongelada = false,
}) {
  const seguroNovo =
    resultado?.formato === "novo" || rascunho?.formato === "novo";

  const todas = useMemo(
    () => (resultado?.propostas || []).filter((p) => p.calculo_realizado),
    [resultado]
  );

  const [modo, setModo] = useState(origemCongelada ? "previa" : "analise");
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
      if (origemCongelada || !estudoId) return;
      setSalvandoSelecao(true);
      try {
        await salvarSelecaoApresentacao(estudoId, novaSelecao);
        await onSelecaoSalva?.();
      } finally {
        setSalvandoSelecao(false);
      }
    },
    [estudoId, origemCongelada, onSelecaoSalva]
  );

  function toggleSelecao(opcaoId) {
    if (origemCongelada) return;
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
  const planosAtuais = resultado.planos_atuais || [];
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
      <div className="page-head">
        <div>
          <div className="page-kicker">
            Etapa {etapaIndice} de {totalEtapas}
          </div>
          <h1>Comparativo</h1>
          <p className="lead">
            Revise as propostas calculadas, escolha o que entra no documento e confirme o
            comparativo antes da exportação.
          </p>
        </div>
        <div className="page-head-acoes">
          {onRecalcular && (
            <button
              type="button"
              className="secundario"
              onClick={onRecalcular}
              disabled={recalculando}
            >
              {recalculando ? "Calculando…" : "Recalcular"}
            </button>
          )}
          {resultado.consistencia && (
            <span
              className={`badge ${resultado.consistencia.consistente ? "badge--ok" : "badge--alerta"}`}
              title={resultado.consistencia.mensagem || undefined}
            >
              {resultado.consistencia.consistente ? "Consistente" : "Inconsistente"}{" "}
              {resultado.consistencia.resultados_apresentados}/
              {resultado.consistencia.cenarios_configurados ??
                resultado.consistencia.propostas_selecionadas ??
                resultado.consistencia.resultados_esperados}
            </span>
          )}
          {salvandoSelecao && <span className="muted">Salvando…</span>}
        </div>
      </div>

      <div className="summary-band num">
        <div className="summary-top">
          <div className="summary-title">
            <span className="badge badge--blue">{rotuloEtapa}</span>
            <b>{resultado.titulo || "Análise comparativa"}</b>
          </div>
          <div className="muted summary-hint">
            {origemCongelada
              ? "Matriz congelada no snapshot aprovado"
              : modo === "analise"
                ? "Catálogo completo · selecione propostas para o documento"
                : "Espelho do material ao cliente · somente selecionados"}
          </div>
        </div>
        <div className="summary-metrics">
          <div className="mini-stat">
            <small>Calculadas</small>
            <strong className="num">{todas.length}</strong>
          </div>
          <div className="mini-stat">
            <small>No documento</small>
            <strong className="num">{selecionadas.length}</strong>
          </div>
          <div className="mini-stat">
            <small>Beneficiários</small>
            <strong className="num">{resultado.beneficiarios_calculados ?? "—"}</strong>
          </div>
          {resultado.validade_proposta && (
            <div className="mini-stat">
              <small>Validade</small>
              <strong className="num">{resultado.validade_proposta}</strong>
            </div>
          )}
          {planosAtuais.length > 0 && (
            <div
              className="reference-price"
              title={planosAtuais.map((p) => `${p.plano_nome} · ${p.operadora}`).join(" | ")}
            >
              <small>
                Referência ·{" "}
                {planosAtuais.length === 1
                  ? planosAtuais[0].plano_nome
                  : `${planosAtuais.length} planos vigentes`}
              </small>
              <strong className="num">
                {formatCentavos(somarCampo(planosAtuais, "mensal_centavos"))}
              </strong>
            </div>
          )}
        </div>
        {!origemCongelada && (
          <div className="summary-modos">
            <div className="cmp-segmento" role="tablist" aria-label="Modo de visualização">
              <button
                type="button"
                role="tab"
                aria-selected={modo === "analise"}
                className={modo === "analise" ? "cmp-seg cmp-seg--ativo" : "cmp-seg"}
                onClick={() => setModo("analise")}
              >
                Análise Newport
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={modo === "previa"}
                className={modo === "previa" ? "cmp-seg cmp-seg--ativo" : "cmp-seg"}
                onClick={() => setModo("previa")}
              >
                Prévia do cliente
              </button>
            </div>
          </div>
        )}
      </div>

      {modo === "analise" && (
        <section className="panel panel-flat cmp-filtros">
          <div className="panel-head">
            <div>
              <h2>Refinar catálogo</h2>
              <p>
                {catalogo.length}/{todas.length} visíveis
                {filtrosAtivos > 0 ? ` · ${filtrosAtivos} filtro(s)` : ""}
              </p>
            </div>
            {filtrosAtivos > 0 && (
              <button type="button" className="secundario btn-compacto" onClick={limparFiltros}>
                Limpar filtros
              </button>
            )}
          </div>
          <div className="panel-body">
            <div className="cmp-filtros-grid catalog-filters">
              <div className="cmp-filtro field">
                <label className="cmp-filtro-label">Coparticipação</label>
                <select
                  value={filtros.grupoRegime}
                  onChange={(e) => setFiltros((f) => ({ ...f, grupoRegime: e.target.value }))}
                >
                  <option value="">Todas</option>
                  <option value="sem_copart">Sem coparticipação</option>
                  <option value="com_copart">Com coparticipação</option>
                </select>
              </div>
              <div className="cmp-filtro field">
                <label className="cmp-filtro-label">Acomodação</label>
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
              <div className="cmp-filtro field">
                <label className="cmp-filtro-label">Operadora</label>
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
              <div className="cmp-filtro field">
                <label className="cmp-filtro-label">Diferença</label>
                <select
                  value={filtros.semantica}
                  onChange={(e) => setFiltros((f) => ({ ...f, semantica: e.target.value }))}
                >
                  <option value="">Todas</option>
                  <option value="economia">Economia</option>
                  <option value="aumento">Aumento</option>
                </select>
              </div>
              <div className="cmp-filtro cmp-filtro--preco field">
                <label className="cmp-filtro-label">Faixa de preço (R$)</label>
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
              <div className="cmp-filtro cmp-filtro--ordem field">
                <label className="cmp-filtro-label">Ordenar por</label>
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
          </div>
        </section>
      )}

      <section className="panel panel-flat cmp-cards-secao">
        <header className="panel-head">
          <div>
            <h2>
              {modo === "analise" ? "Propostas calculadas" : "Planos no documento"}
            </h2>
            <p>
              {modo === "analise"
                ? `${catalogo.length}/${todas.length} visíveis · clique em Adicionar para incluir na matriz.`
                : "Material que será entregue ao cliente."}
            </p>
          </div>
          {modo === "analise" && selecionadas.length > 0 && (
            <span className="badge badge--blue">{selecionadas.length} no documento</span>
          )}
        </header>
        <div className="panel-body">
          <div className="cmp-cards-grid proposal-grid">
            {exibirCards.map((p) => (
              <CardProposta
                key={p.opcao_id}
                proposta={p}
                selecionada={selecao.includes(p.opcao_id)}
                onToggle={toggleSelecao}
                compacto={modo === "previa"}
                seguroNovo={seguroNovo}
                somenteLeitura={origemCongelada}
              />
            ))}
          </div>
          {modo === "previa" && !exibirCards.length && (
            <p className="muted">
              Nenhum plano selecionado — volte à Análise Newport e adicione propostas à comparação.
            </p>
          )}
        </div>
      </section>

      <section className="panel cmp-matriz-secao">
        <header className="panel-head cmp-matriz-cabecalho">
          <div>
            <h2>Matriz comparativa</h2>
            <p>
              {seguroNovo
                ? `Comparativo entre propostas · ${selecionadas.length} proposta(s) selecionada(s)`
                : `Contrato atual na primeira coluna · ${selecionadas.length} proposta(s) selecionada(s)`}
            </p>
          </div>
          <div className="cmp-vistas tabs">
            <button
              type="button"
              className={vista === "resumo" ? "cmp-vista cmp-vista--ativa tab active" : "cmp-vista tab"}
              onClick={() => setVista("resumo")}
            >
              Resumo executivo
            </button>
            <button
              type="button"
              className={vista === "faixas" ? "cmp-vista cmp-vista--ativa tab active" : "cmp-vista tab"}
              onClick={() => setVista("faixas")}
            >
              Faixas etárias
            </button>
            <button
              type="button"
              className={
                vista === "beneficiarios" ? "cmp-vista cmp-vista--ativa tab active" : "cmp-vista tab"
              }
              onClick={() => setVista("beneficiarios")}
            >
              Por beneficiário
            </button>
          </div>
        </header>
        <div className="panel-body">
          {vista === "beneficiarios" && (modo === "analise" || origemCongelada) && (
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
            planosAtuais={planosAtuais}
            propostas={selecionadas}
            vista={vista}
            mostrarNomes={(modo === "analise" || origemCongelada) && mostrarNomes}
            seguroNovo={seguroNovo}
            faixasEstudo={resultado.faixas_estudo || []}
            reajusteConsolidadoPct={resultado.reajuste_consolidado_percentual_exibicao}
          />
        </div>
      </section>

      {resultado?.calculo_realizado && onConfirmar && (
        <section className="panel cmp-confirmacao-secao">
          <div className="panel-head">
            <div>
              <h2>Confirmar revisão</h2>
              <p>
                {selecao.length === 0
                  ? "Adicione ao menos uma proposta na matriz (botão «Adicionar» nos cards)."
                  : confirmado
                    ? "Comparativo confirmado. Aprove abaixo para liberar a exportação ao cliente."
                    : `${selecao.length} proposta(s) selecionada(s) para o material ao cliente.`}
              </p>
            </div>
          </div>
          <div className="panel-body">
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
            {avisoSelecaoAlterada && !confirmado && selecao.length > 0 && (
              <p className="cmp-aviso-selecao-alterada" role="status">
                Seleção alterada — confirme o comparativo novamente antes de exportar.
              </p>
            )}
            <button
              type="button"
              className="cmp-btn-principal"
              disabled={!podeConfirmar}
              onClick={() => onConfirmar(selecao)}
            >
              {confirmando
                ? "Confirmando e congelando…"
                : "Confirmar comparativo"}
            </button>
          </div>
        </section>
      )}

      {modo === "analise" && (
        <>
          <section className="panel panel-flat cmp-detalhes-tecnicos">
            <header className="panel-head">
              <div>
                <h2>Detalhamento técnico</h2>
                <p>Expanda cada proposta para revisar valores por beneficiário (uso interno).</p>
              </div>
              <span className="badge badge--muted">{catalogo.length} propostas</span>
            </header>
            <div className="panel-body">
              <div className="cmp-detalhes-lista tech-list">
                {catalogo.map((p) => {
                  const n = p.numerico;
                  const diffCls = classeVariacao(n?.diff_mes_centavos ?? n?.diff_bps);
                  return (
                    <details key={p.opcao_id} className="cmp-detalhe tech-row">
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
                            {formatCentavos(n?.diff_mes_centavos)}
                            {n?.diff_bps != null && !seguroNovo && (
                              <> · {formatBps(n.diff_bps)}</>
                            )}
                          </span>
                          {(p.pendencias?.length > 0 || p.auditoria?.length > 0) && (
                            <span className="cmp-detalhe-alerta" title="Pendências nesta proposta">
                              {p.pendencias?.length || "!"}
                            </span>
                          )}
                        </div>
                      </summary>
                      <div className="cmp-detalhe-corpo">
                        {p.pendencias?.length > 0 && <Pendencias items={p.pendencias} />}
                        {vidasDaProposta(p).length > 0 ? (
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
                                {vidasDaProposta(p).map((v) => (
                                  <tr key={v.vida_id}>
                                    <td>{v.nome}</td>
                                    <td>{v.idade ?? "—"}</td>
                                    <td>{v.faixa_rotulo || "—"}</td>
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
            </div>
          </section>

          <section className="panel cmp-auditoria-secao">
            <div className="panel-head">
              <div>
                <h2>Pendências e alertas</h2>
                <p>Códigos à esquerda · texto operacional à direita.</p>
              </div>
            </div>
            <div className="panel-body">
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
            </div>
          </section>
        </>
      )}
    </div>
  );
}

