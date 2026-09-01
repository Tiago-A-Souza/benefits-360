/** Rosca de sexo e barras por faixa etária — etapa 1.
 *
 * Lê o mesmo objeto `tabela` que a tabela de faixas exibe; toda a derivação
 * está em `graficosFaixas.js`. Nada é calculado aqui.
 */

import { useId } from "react";
import {
  ROSCA_CIRCUNFERENCIA,
  ROSCA_ESPESSURA,
  ROSCA_RAIO,
  descricaoBarras,
  descricaoRosca,
} from "./graficosFaixas";

function Rosca({ rosca }) {
  const idBase = useId();
  const idTexto = `${idBase}-texto`;
  const idHachura = `${idBase}-hachura`;
  const descricao = descricaoRosca(rosca);

  return (
    <figure className="gr-card">
      <figcaption className="gr-titulo">
        Sexo
        <span className="gr-sub">
          {rosca.total} {rosca.total === 1 ? "vida" : "vidas"}
        </span>
      </figcaption>
      <div className="gr-rosca-corpo">
        <svg
          className="gr-rosca-svg"
          viewBox="0 0 200 200"
          role="img"
          aria-labelledby={idTexto}
        >
          <defs>
            <pattern
              id={idHachura}
              width="7"
              height="7"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <line x1="0" y1="0" x2="0" y2="7" className="gr-hachura-traco" />
            </pattern>
          </defs>
          <circle
            className="gr-rosca-trilho"
            cx="100"
            cy="100"
            r={ROSCA_RAIO}
            strokeWidth={ROSCA_ESPESSURA}
          />
          <g transform="rotate(-90 100 100)">
            {rosca.fatias.map((fatia) => (
              <circle
                key={fatia.chave}
                className={`gr-fatia gr-fatia--${fatia.chave}`}
                cx="100"
                cy="100"
                r={ROSCA_RAIO}
                strokeWidth={ROSCA_ESPESSURA}
                strokeDasharray={
                  fatia.completa
                    ? undefined
                    : `${fatia.comprimento} ${ROSCA_CIRCUNFERENCIA - fatia.comprimento}`
                }
                strokeDashoffset={fatia.completa ? undefined : -fatia.offset}
              />
            ))}
            {rosca.fatias
              .filter((fatia) => fatia.chave !== "feminino")
              .map((fatia) => (
                <circle
                  key={`${fatia.chave}-textura`}
                  className="gr-fatia-textura"
                  cx="100"
                  cy="100"
                  r={ROSCA_RAIO}
                  strokeWidth={ROSCA_ESPESSURA}
                  stroke={`url(#${idHachura})`}
                  strokeDasharray={
                    fatia.completa
                      ? undefined
                      : `${fatia.comprimento} ${ROSCA_CIRCUNFERENCIA - fatia.comprimento}`
                  }
                  strokeDashoffset={fatia.completa ? undefined : -fatia.offset}
                />
              ))}
          </g>
          <text className="gr-rosca-centro" x="100" y="102">
            {rosca.total}
          </text>
          <text className="gr-rosca-centro-rotulo" x="100" y="118">
            {rosca.total === 1 ? "vida" : "vidas"}
          </text>
        </svg>
        <ul className="gr-legenda">
          {rosca.todas.map((fatia) => (
            <li key={fatia.chave} className="gr-legenda-item">
              <span
                className={`gr-swatch gr-swatch--${fatia.chave}`}
                aria-hidden="true"
              />
              <span className="gr-legenda-rotulo">{fatia.rotulo}</span>
              <span className="gr-legenda-valor num">{fatia.valor}</span>
              <span className="gr-legenda-pct num">{fatia.percentual}%</span>
            </li>
          ))}
        </ul>
      </div>
      <p className="apenas-leitor" id={idTexto}>
        {descricao}
      </p>
    </figure>
  );
}

function Barras({ barras }) {
  const idBase = useId();
  const idTexto = `${idBase}-texto`;
  const descricao = descricaoBarras(barras);

  return (
    <figure className="gr-card gr-card--largo">
      <figcaption className="gr-titulo">
        Faixa etária
        <span className="gr-sub">
          {barras.total} {barras.total === 1 ? "vida" : "vidas"} · maior faixa com{" "}
          {barras.maior}
        </span>
      </figcaption>
      <ul className="gr-barras" role="img" aria-labelledby={idTexto}>
        {barras.itens.map((item) => (
          <li
            key={item.faixa}
            className={`gr-barra${item.valor === 0 ? " gr-barra--zero" : ""}`}
          >
            <span className="gr-barra-valor num">{item.valor}</span>
            <span className="gr-barra-trilho">
              <span
                className="gr-barra-preenchimento"
                style={{ "--fracao": item.fracao }}
              />
            </span>
            <span className="gr-barra-rotulo">{item.rotuloCurto}</span>
          </li>
        ))}
      </ul>
      <p className="apenas-leitor" id={idTexto}>
        {descricao}
      </p>
    </figure>
  );
}

export default function GraficosFaixasCotacao({ graficos }) {
  if (!graficos?.disponivel) return null;
  return (
    <div className="gr-faixas">
      <Rosca rosca={graficos.rosca} />
      <Barras barras={graficos.barras} />
    </div>
  );
}
