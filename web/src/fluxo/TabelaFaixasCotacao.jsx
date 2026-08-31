/** Tabela faixa × sexo × tit/dep — copy-paste para cotação na operadora. */

import { useCallback, useMemo, useState } from "react";

function celula(valor) {
  if (valor == null) return "—";
  return valor;
}

export default function TabelaFaixasCotacao({ tabela }) {
  const [copiado, setCopiado] = useState(false);

  const mostrarSexo = tabela?.modo_sexo !== "sem_sexo";
  const mostrarNi = tabela?.modo_sexo === "parcial";

  const tsv = useMemo(() => {
    if (!tabela?.linhas?.length) return "";
    const header = mostrarSexo
      ? ["Faixa", "Tit. M", "Tit. F", "Dep. M", "Dep. F"]
      : ["Faixa", "Titulares", "Dependentes"];
    if (mostrarNi) header.push("Não informado");
    header.push("Total");
    const rows = tabela.linhas.map((ln) => {
      const row = mostrarSexo
        ? [ln.rotulo, ln.tit_m ?? 0, ln.tit_f ?? 0, ln.dep_m ?? 0, ln.dep_f ?? 0]
        : [ln.rotulo, ln.titulares ?? 0, ln.dependentes ?? 0];
      if (mostrarNi) row.push(ln.nao_informado ?? 0);
      row.push(ln.total ?? 0);
      return row.join("\t");
    });
    return [header.join("\t"), ...rows].join("\n");
  }, [tabela, mostrarSexo, mostrarNi]);

  const copiar = useCallback(async () => {
    if (!tsv) return;
    try {
      await navigator.clipboard.writeText(tsv);
      setCopiado(true);
      window.setTimeout(() => setCopiado(false), 2000);
    } catch {
      setCopiado(false);
    }
  }, [tsv]);

  if (!tabela?.linhas?.length) return null;

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h2>Faixas para cotação</h2>
          <p>
            Quadro ANS para colar no formulário da operadora
            {tabela.data_referencia
              ? ` · referência ${String(tabela.data_referencia).slice(0, 10)}`
              : ""}
            .
          </p>
        </div>
        <button type="button" className="btn-compacto secundario" onClick={copiar}>
          {copiado ? "Copiado" : "Copiar tabela"}
        </button>
      </div>
      <div className="panel-body">
        {tabela.aviso_sexo && (
          <div className="notice notice--amber" role="status">
            <div className="notice-icon" aria-hidden="true">
              !
            </div>
            <div>
              <b>Sexo ausente ou incompleto</b>
              <p>{tabela.aviso_sexo}</p>
            </div>
          </div>
        )}
        <div className="table-wrap">
          <table className="num tabela-fluxo tabela-faixas-cotacao" tabIndex={0}>
            <thead>
              <tr>
                <th>Faixa</th>
                {mostrarSexo ? (
                  <>
                    <th className="right">Tit. M</th>
                    <th className="right">Tit. F</th>
                    <th className="right">Dep. M</th>
                    <th className="right">Dep. F</th>
                  </>
                ) : (
                  <>
                    <th className="right">Titulares</th>
                    <th className="right">Dependentes</th>
                  </>
                )}
                {mostrarNi && <th className="right">Não informado</th>}
                <th className="right">Total</th>
              </tr>
            </thead>
            <tbody>
              {tabela.linhas.map((ln) => (
                <tr key={ln.faixa}>
                  <td>
                    <span className="cell-main">{ln.rotulo}</span>
                  </td>
                  {mostrarSexo ? (
                    <>
                      <td className="right">{celula(ln.tit_m)}</td>
                      <td className="right">{celula(ln.tit_f)}</td>
                      <td className="right">{celula(ln.dep_m)}</td>
                      <td className="right">{celula(ln.dep_f)}</td>
                    </>
                  ) : (
                    <>
                      <td className="right">{celula(ln.titulares)}</td>
                      <td className="right">{celula(ln.dependentes)}</td>
                    </>
                  )}
                  {mostrarNi && (
                    <td className="right">{celula(ln.nao_informado)}</td>
                  )}
                  <td className="right">{ln.total}</td>
                </tr>
              ))}
              <tr className="total-row">
                <td>Total</td>
                {mostrarSexo ? (
                  <>
                    <td className="right">
                      {tabela.linhas.reduce((s, l) => s + (l.tit_m || 0), 0)}
                    </td>
                    <td className="right">
                      {tabela.linhas.reduce((s, l) => s + (l.tit_f || 0), 0)}
                    </td>
                    <td className="right">
                      {tabela.linhas.reduce((s, l) => s + (l.dep_m || 0), 0)}
                    </td>
                    <td className="right">
                      {tabela.linhas.reduce((s, l) => s + (l.dep_f || 0), 0)}
                    </td>
                  </>
                ) : (
                  <>
                    <td className="right">{tabela.total_titulares}</td>
                    <td className="right">{tabela.total_dependentes}</td>
                  </>
                )}
                {mostrarNi && (
                  <td className="right">{tabela.total_nao_informado ?? 0}</td>
                )}
                <td className="right">{tabela.total_vidas}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
