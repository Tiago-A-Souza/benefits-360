import { useEffect, useState } from "react";
import { obterPendencias, obterRascunho, obterResumoPlanoAtual, salvarRascunho } from "./api";
import {
  MODALIDADES,
  OPERADORAS,
  REGIMES_COPART,
  TIPOS_FISCAIS,
  ensureRegime,
} from "./constants";

export default function ConfigEstudo({ estudoId, onSalvo }) {
  const [rascunho, setRascunho] = useState(null);
  const [pendencias, setPendencias] = useState([]);
  const [resumoAtual, setResumoAtual] = useState(null);
  const [confirmacaoFinal, setConfirmacaoFinal] = useState(false);
  const [erro, setErro] = useState(null);
  const [msg, setMsg] = useState(null);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (!estudoId) return;
    Promise.all([
      obterRascunho(estudoId),
      obterPendencias(estudoId),
      obterResumoPlanoAtual(estudoId).catch(() => null),
    ])
      .then(([r, p, resumo]) => {
        setRascunho(r);
        setPendencias(p);
        setResumoAtual(resumo);
        setConfirmacaoFinal(
          Boolean(
            r.escolhas?.baseline_escolhido?.confirmado &&
              (!resumo?.exige_escolha_precedencia ||
                r.escolhas?.precedencia_atual_vida?.confirmado)
          )
        );
      })
      .catch((e) => setErro(e.message));
  }, [estudoId]);

  function atualizarSubgrupo(idx, campo, valor) {
    setRascunho((prev) => {
      const copia = structuredClone(prev);
      if (campo === "regime_copart_id") {
        ensureRegime(copia, valor);
        copia.subgrupos_atuais[idx].regime_copart_id = `regime-${valor}`;
      } else if (campo === "tipo_fiscal") {
        copia.subgrupos_atuais[idx].tipo_fiscal = valor;
        // Basis explícito a partir do tipo (campo IOF saiu da UI). Só preenche
        // quando ainda desconhecido / inválido para o tipo — não sobrescreve legado.
        const atual = copia.subgrupos_atuais[idx].fatura_price_basis;
        if (valor === "operadora" && (atual === "desconhecido" || !atual)) {
          copia.subgrupos_atuais[idx].fatura_price_basis = "nao_aplica";
        } else if (
          valor === "seguradora" &&
          (atual === "desconhecido" || atual === "nao_aplica" || !atual)
        ) {
          copia.subgrupos_atuais[idx].fatura_price_basis = "exclui_iof";
        }
      } else {
        copia.subgrupos_atuais[idx][campo] = valor;
      }
      return copia;
    });
  }

  function atualizarEscolha(campo, valor) {
    setRascunho((prev) => {
      const copia = structuredClone(prev);
      if (campo === "data_referencia_idade") {
        copia.escolhas.data_referencia_idade = valor || null;
      } else if (campo === "baseline") {
        copia.escolhas.baseline_escolhido.valor = valor;
      } else if (campo === "precedencia") {
        copia.escolhas.precedencia_atual_vida.valor = valor;
      }
      return copia;
    });
  }

  async function handleSalvar() {
    if (!rascunho) return;
    setSalvando(true);
    setErro(null);
    const copia = structuredClone(rascunho);
    const seguroNovo = copia.formato === "novo";
    const exigePrecedencia = Boolean(resumoAtual?.exige_escolha_precedencia);
    if (seguroNovo) {
      copia.escolhas.baseline_escolhido.confirmado = false;
      copia.escolhas.baseline_escolhido.valor = null;
      copia.escolhas.precedencia_atual_vida.confirmado = false;
      copia.escolhas.precedencia_atual_vida.valor = null;
    } else {
      copia.escolhas.baseline_escolhido.confirmado = confirmacaoFinal;
      if (exigePrecedencia) {
        copia.escolhas.precedencia_atual_vida.confirmado = confirmacaoFinal;
      }
      // Fonte única: o servidor grava valor explícito em salvar_rascunho.
    }
    try {
      await salvarRascunho(estudoId, copia);
      const [r, p, resumo] = await Promise.all([
        obterRascunho(estudoId),
        obterPendencias(estudoId),
        obterResumoPlanoAtual(estudoId).catch(() => null),
      ]);
      setRascunho(r);
      setPendencias(p);
      setResumoAtual(resumo);
      setConfirmacaoFinal(
        Boolean(
          r.escolhas?.baseline_escolhido?.confirmado &&
            (!resumo?.exige_escolha_precedencia ||
              r.escolhas?.precedencia_atual_vida?.confirmado)
        )
      );
      setMsg(seguroNovo ? "Referência de idades salva." : "Informações do plano atual salvas.");
      onSalvo?.();
    } catch (e) {
      setErro(e.message);
    } finally {
      setSalvando(false);
    }
  }

  if (!rascunho) return <p className="muted">Carregando plano atual…</p>;

  if (rascunho.formato === "novo") {
    return (
      <section className="secao-fluxo">
        <header className="secao-fluxo-cabecalho">
          <h2>Referência do estudo</h2>
          <p className="lead">
            Seguro novo não possui contrato vigente. Informe apenas a data usada para calcular as
            idades dos beneficiários.
          </p>
        </header>

        <div className="bloco-secao bloco-secao--escolhas">
          <label className="campo-form campo-form--data">
            Data usada para calcular as idades
            <input
              type="date"
              value={rascunho.escolhas.data_referencia_idade || ""}
              onChange={(e) => atualizarEscolha("data_referencia_idade", e.target.value)}
            />
          </label>
        </div>

        <footer className="secao-fluxo-rodape">
          <div className="secao-fluxo-acoes">
            {msg && <p className="ok">{msg}</p>}
            {erro && <p className="erro">{erro}</p>}
            <button type="button" onClick={handleSalvar} disabled={salvando}>
              {salvando ? "Salvando…" : "Salvar referência"}
            </button>
          </div>
        </footer>
      </section>
    );
  }

  return (
    <section className="secao-fluxo">
      <header className="secao-fluxo-cabecalho">
        <h2>Plano atual</h2>
        <p className="lead">
          Confirme os dados do contrato vigente e como a Newport fará a comparação com as novas
          cotações.
        </p>
      </header>

      {rascunho.subgrupos_atuais.length === 0 && (
        <p className="alerta">Importe a base SISCOR na etapa anterior.</p>
      )}

      {rascunho.subgrupos_atuais.length > 0 && (
        <div className="subgrupos-atuais">
          {rascunho.subgrupos_atuais.map((sg, idx) => (
            <article key={sg.id} className="subgrupo-atual cartao cartao--interno">
              <header className="subgrupo-atual-cabecalho">
                <span className="subgrupo-atual-indice">Plano {idx + 1}</span>
                <h3>{sg.plano_nome || `Plano ${idx + 1}`}</h3>
              </header>
              <div className="grid-compacto grid-campos">
                <label className="campo-form">
                  Operadora
                  <input
                    value={sg.operadora || ""}
                    onChange={(e) => atualizarSubgrupo(idx, "operadora", e.target.value)}
                    list="operadoras-list"
                  />
                </label>
                <label className="campo-form">
                  Nome do plano
                  <input
                    value={sg.plano_nome || ""}
                    onChange={(e) => atualizarSubgrupo(idx, "plano_nome", e.target.value)}
                  />
                </label>
                <label className="campo-form">
                  Tipo fiscal
                  <select
                    value={sg.tipo_fiscal || ""}
                    onChange={(e) => atualizarSubgrupo(idx, "tipo_fiscal", e.target.value || null)}
                    className={!sg.tipo_fiscal ? "campo-pendente" : undefined}
                  >
                    <option value="">Selecione…</option>
                    {TIPOS_FISCAIS.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="campo-form">
                  Adesão dos funcionários
                  <select
                    value={sg.modalidade || ""}
                    onChange={(e) => atualizarSubgrupo(idx, "modalidade", e.target.value || null)}
                  >
                    <option value="">Selecione…</option>
                    {MODALIDADES.map((m) => (
                      <option key={m.value} value={m.value}>
                        {m.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="campo-form">
                  Regime de coparticipação
                  <select
                    value={sg.regime_copart_id?.replace("regime-", "") || ""}
                    onChange={(e) => atualizarSubgrupo(idx, "regime_copart_id", e.target.value)}
                    className={!sg.regime_copart_id ? "campo-pendente" : undefined}
                  >
                    <option value="">Selecione…</option>
                    {REGIMES_COPART.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="campo-form">
                  Reajuste previsto na renovação (%)
                  <input
                    type="number"
                    step="0.01"
                    value={sg.reajuste_bps != null ? sg.reajuste_bps / 100 : ""}
                    onChange={(e) => {
                      const v = e.target.value;
                      atualizarSubgrupo(
                        idx,
                        "reajuste_bps",
                        v === "" ? null : Math.round(parseFloat(v) * 100)
                      );
                    }}
                  />
                </label>
              </div>
            </article>
          ))}
        </div>
      )}

      <div className="bloco-secao bloco-secao--escolhas">
        <h3>Como faremos a comparação</h3>
        <p className="muted">Escolha a referência do contrato vigente para a comparação.</p>

        <div className="grupo-escolhas">
          <h4 className="grupo-escolhas-titulo">Referência do contrato</h4>
          <div className="cartoes-escolha">
            <label
              className={`cartao-escolha${
                rascunho.escolhas.baseline_escolhido.valor === "vigente"
                  ? " cartao-escolha--ativo"
                  : ""
              }`}
            >
              <input
                type="radio"
                name="baseline"
                checked={rascunho.escolhas.baseline_escolhido.valor === "vigente"}
                onChange={() => atualizarEscolha("baseline", "vigente")}
              />
              <strong>Contrato vigente</strong>
              <span className="muted">Valores atuais sem aplicar reajuste negociado.</span>
            </label>
            <label
              className={`cartao-escolha${
                rascunho.escolhas.baseline_escolhido.valor === "reajustado"
                  ? " cartao-escolha--ativo"
                  : ""
              }`}
            >
              <input
                type="radio"
                name="baseline"
                checked={rascunho.escolhas.baseline_escolhido.valor === "reajustado"}
                onChange={() => atualizarEscolha("baseline", "reajustado")}
              />
              <strong>Contrato reajustado</strong>
              <span className="muted">Inclui o reajuste informado para a renovação.</span>
            </label>
          </div>

          <h4 className="grupo-escolhas-titulo">Origem dos valores atuais</h4>
          {resumoAtual?.exige_escolha_precedencia ? (
            <>
              <p className="alerta">
                {resumoAtual.origem_valores_descricao ||
                  "Tabela e fatura coexistem — escolha qual fonte prevalece."}
              </p>
              <div className="cartoes-escolha">
                <label
                  className={`cartao-escolha${
                    rascunho.escolhas.precedencia_atual_vida.valor === "valor_fatura"
                      ? " cartao-escolha--ativo"
                      : ""
                  }`}
                >
                  <input
                    type="radio"
                    name="precedencia"
                    checked={rascunho.escolhas.precedencia_atual_vida.valor === "valor_fatura"}
                    onChange={() => atualizarEscolha("precedencia", "valor_fatura")}
                  />
                  <strong>Valores importados do SISCOR</strong>
                  <span className="muted">Usa o valor de fatura de cada beneficiário.</span>
                </label>
                <label
                  className={`cartao-escolha${
                    rascunho.escolhas.precedencia_atual_vida.valor === "tabela_atual"
                      ? " cartao-escolha--ativo"
                      : ""
                  }`}
                >
                  <input
                    type="radio"
                    name="precedencia"
                    checked={rascunho.escolhas.precedencia_atual_vida.valor === "tabela_atual"}
                    onChange={() => atualizarEscolha("precedencia", "tabela_atual")}
                  />
                  <strong>Tabela oficial do plano</strong>
                  <span className="muted">Usa a tabela tarifária cadastrada do contrato.</span>
                </label>
              </div>
            </>
          ) : (
            <p className="origem-valores-info muted">
              {resumoAtual?.origem_valores_descricao ||
                "A origem dos valores atuais será definida automaticamente conforme a base importada."}
            </p>
          )}

          <label className="campo-form campo-form--data">
            Data usada para calcular as idades
            <input
              type="date"
              value={rascunho.escolhas.data_referencia_idade || ""}
              onChange={(e) => atualizarEscolha("data_referencia_idade", e.target.value)}
            />
          </label>
        </div>
      </div>

      {(resumoAtual?.total_vigente_reais || resumoAtual?.total_reajustado_reais) && (
        <div className="resumo-plano-atual-totais muted">
          {resumoAtual.total_vigente_reais && (
            <p>
              Total vigente na base: <strong>{resumoAtual.total_vigente_reais}</strong>
            </p>
          )}
          {resumoAtual.total_reajustado_reais && (
            <p>
              Total reajustado: <strong>{resumoAtual.total_reajustado_reais}</strong>
              {resumoAtual.planos?.length === 1 &&
                resumoAtual.planos[0].reajuste_percentual_exibicao && (
                  <>
                    {" "}
                    ({resumoAtual.planos[0].reajuste_percentual_exibicao})
                  </>
                )}
            </p>
          )}
        </div>
      )}

      {pendencias.filter((p) => p.etapa === 2).length > 0 && (
        <ul className="pendencias">
          {pendencias
            .filter((p) => p.etapa === 2)
            .map((p, i) => (
              <li key={p.codigo || i} className={`pendencia pendencia--${p.tipo}`}>
                <strong>{p.titulo}</strong>
                {p.descricao && <p>{p.descricao}</p>}
                {p.codigo === "APP-IMP-001" && (
                  <p className="acao">
                    Em cada plano acima, preencha o campo <strong>Tipo fiscal</strong> (Seguradora
                    ou Operadora).
                  </p>
                )}
              </li>
            ))}
        </ul>
      )}

      <footer className="secao-fluxo-rodape">
        <label className="checkbox confirmacao-final">
          <input
            type="checkbox"
            checked={confirmacaoFinal}
            onChange={(e) => setConfirmacaoFinal(e.target.checked)}
          />
          Revisei e confirmo as informações do plano atual.
        </label>
        <div className="secao-fluxo-acoes">
          {msg && <p className="ok">{msg}</p>}
          {erro && <p className="erro">{erro}</p>}
          <button type="button" onClick={handleSalvar} disabled={salvando}>
            {salvando ? "Salvando…" : "Salvar plano atual"}
          </button>
        </div>
      </footer>

      <datalist id="operadoras-list">
        {OPERADORAS.map((o) => (
          <option key={o} value={o} />
        ))}
      </datalist>
    </section>
  );
}
