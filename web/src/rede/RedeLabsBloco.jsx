function rotuloPlanoColuna(col) {
  if (col.contrato_atual) return { op: "Contrato atual", pl: col.plano_nome };
  return { op: col.operadora, pl: col.plano_nome };
}

function celulaLab(val) {
  const t = (val || "").trim();
  if (!t || t === "—") return { texto: t === "—" ? "—" : "", on: false };
  return { texto: t, on: true };
}

export default function RedeLabsBloco({ colunas, laboratorios }) {
  const linhas = laboratorios?.linhas || [];
  if (!linhas.length) return null;
  const contagem = laboratorios.contagem_por_coluna || {};
  return (
    <div className="rede-bloco-municipio rede-bloco-labs">
      <div className="rede-bloco-titulo">Laboratórios</div>
      <div className="tabela-scroll">
        <table className="conferencia rede-selecao-tabela tabela-rede">
          <thead>
            <tr>
              <th className="rede-col-prestador" scope="col">
                Laboratório
              </th>
              {colunas.map((col) => {
                const { op, pl } = rotuloPlanoColuna(col);
                return (
                  <th
                    key={col.chave}
                    className={
                      col.contrato_atual ? "rede-col-plano atual" : "rede-col-plano"
                    }
                    scope="col"
                  >
                    <span className="op">{op}</span>
                    <span className="pl">{pl}</span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {linhas.map((ln) => (
              <tr key={ln.marca}>
                <td className="nm rede-col-prestador">
                  <span className="cell-main">{ln.marca}</span>
                </td>
                {colunas.map((col) => {
                  const { texto, on } = celulaLab(ln.celulas?.[col.chave]);
                  return (
                    <td
                      key={col.chave}
                      className={`rede-col-plano ${on ? "on" : "off"}`}
                    >
                      {texto}
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr className="cont-rede">
              <td>Cobertos</td>
              {colunas.map((col) => (
                <td key={col.chave}>{contagem[col.chave] ?? 0}</td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
