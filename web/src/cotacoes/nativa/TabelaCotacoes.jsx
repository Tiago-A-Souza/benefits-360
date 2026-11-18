import { useState } from "react";
import { baixarUrlRpa, chamarRpa } from "../rpaClient";
import LogoOperadora from "./LogoOperadora";
import {
  FAIXAS as FAIXAS_CENSO,
  STATUS_COTACAO,
  agruparVersoes,
  digitos,
  empresaDe,
  formatarCnpj,
  formatarDataLista,
  formatarValorRobo,
  motivoCotacao,
  textoVersao,
} from "./regrasNova";

const FAIXAS_DETALHE = FAIXAS_CENSO.map(([, r]) => r);

function Selo({ status }) {
  return <span className={`nativa-selo nativa-selo--${status}`}>{STATUS_COTACAO[status] || status}</span>;
}

function Linha({
  c,
  empresa,
  data,
  selecao,
  onToggle,
  cotarDeNovo,
  onCotarDeNovo,
  operadoras,
  aviso,
}) {
  const [aberto, setAberto] = useState(false);
  const valores = c.valores_por_vida || {};
  const temValores = Object.keys(valores).length > 0;
  const motivo = motivoCotacao(c, operadoras);
  const colunas = 5 + (empresa ? 1 : 0) + (data ? 1 : 0) + (selecao ? 1 : 0);
  const versaoTxt = textoVersao(c, operadoras);

  async function baixarPdf() {
    try {
      await baixarUrlRpa(`/api/cotacoes/${c.id}/pdf`);
    } catch (e) {
      aviso?.(e.message, "erro");
    }
  }
  async function abrirPasta() {
    try {
      await chamarRpa("POST", `/api/cotacoes/${c.id}/abrir-pasta`);
    } catch (e) {
      aviso?.(e.message, "erro");
    }
  }

  return (
    <>
      <tr className={c._mesmoPlano ? "nativa-mesmo-plano" : undefined}>
        {selecao ? (
          <td>
            <input
              type="checkbox"
              aria-label={`Selecionar ${c.plano}`}
              disabled={!c.tem_pdf}
              checked={!!selecao.has(c.id)}
              onChange={(e) => onToggle?.(c.id, e.target.checked)}
            />
          </td>
        ) : null}
        {data ? <td className="muted num nativa-sem-quebra">{formatarDataLista(c.criado_em)}</td> : null}
        {empresa ? (
          <td className="nativa-col-empresa">
            <div className="nativa-empresa-nome">{empresaDe(c)}</div>
            <div className="muted num">
              {formatarCnpj(c.cnpj)}
              {cotarDeNovo && onCotarDeNovo ? (
                <>
                  {" "}
                  <button type="button" className="link" onClick={() => onCotarDeNovo(digitos(c.cnpj))}>
                    cotar de novo
                  </button>
                </>
              ) : null}
            </div>
          </td>
        ) : null}
        <td>
          <div className="nativa-plano-com-op">
            <LogoOperadora operadora={c.operadora} tamanho="sm" />
            <div>
              <div className="nativa-empresa-nome">{c.plano || "—"}</div>
              <div className="muted">
                {c.acomodacao || ""}
                {c.versao ? <span className={`nativa-versao nativa-versao--${c.versao}`}>{versaoTxt}</span> : null}
              </div>
            </div>
          </div>
        </td>
        <td className="right num">
          {formatarValorRobo(c.total_com_iof)}
          {temValores ? (
            <div>
              <button
                type="button"
                className="link"
                aria-expanded={aberto}
                onClick={() => setAberto((v) => !v)}
              >
                {aberto ? "fechar" : "ver por faixa"}
              </button>
            </div>
          ) : null}
        </td>
        <td className="num">{c.protocolo || <span className="muted">—</span>}</td>
        <td>
          <Selo status={c.status} />
        </td>
        <td>
          <div className="nativa-acoes-linha">
            {c.tem_pdf ? (
              <button type="button" className="secundario btn-compacto" onClick={baixarPdf}>
                Baixar PDF
              </button>
            ) : null}
            {c.tem_pdf ? (
              <button type="button" className="secundario btn-compacto" onClick={abrirPasta}>
                Abrir pasta
              </button>
            ) : null}
          </div>
        </td>
      </tr>
      {motivo ? (
        <tr className={`nativa-motivo nativa-motivo--${c.status}`}>
          <td colSpan={colunas}>{motivo}</td>
        </tr>
      ) : null}
      {temValores ? (
        <tr className="nativa-detalhe" hidden={!aberto}>
          <td colSpan={colunas}>
            <div className="nativa-faixas-detalhe">
              {FAIXAS_DETALHE.filter((f) => valores[f] !== undefined).map((f) => (
                <div key={f}>
                  <span>{f} anos </span>
                  <span className="num">{formatarValorRobo(valores[f])}</span>
                </div>
              ))}
            </div>
            <p className="muted">
              Valor mensal por vida em cada faixa.
              {c.total_sem_iof
                ? ` Total sem IOF ${formatarValorRobo(c.total_sem_iof)}, IOF ${formatarValorRobo(c.iof)}.`
                : ""}
            </p>
          </td>
        </tr>
      ) : null}
    </>
  );
}

export default function TabelaCotacoes({
  cotacoes,
  empresa = false,
  data = false,
  selecao = null,
  onToggle,
  cotarDeNovo = false,
  onCotarDeNovo,
  operadoras,
  aviso,
}) {
  const lista = agruparVersoes([...(cotacoes || [])], operadoras);
  return (
    <div className="tabela-scroll nativa-tabela-rolagem">
      <table className="nativa-tabela">
        <thead>
          <tr>
            {selecao ? <th /> : null}
            {data ? <th>Quando</th> : null}
            {empresa ? <th>Empresa</th> : null}
            <th>Plano</th>
            <th className="right">Total com IOF</th>
            <th>Protocolo</th>
            <th>Situação</th>
            <th>
              <span className="visually-hidden">Ações</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {lista.map((c) => (
            <Linha
              key={`${c.id}-${c.versao || ""}-${c.plano}`}
              c={c}
              empresa={empresa}
              data={data}
              selecao={selecao}
              onToggle={onToggle}
              cotarDeNovo={cotarDeNovo}
              onCotarDeNovo={onCotarDeNovo}
              operadoras={operadoras}
              aviso={aviso}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
