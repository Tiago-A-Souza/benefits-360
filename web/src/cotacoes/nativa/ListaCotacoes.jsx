import { useCallback, useEffect, useState } from "react";
import { baixarUrlRpa, chamarRpa } from "../rpaClient";
import BannerPendencias from "./BannerPendencias";
import TabelaCotacoes from "./TabelaCotacoes";
import { FILTROS_LISTA } from "./regrasNova";

export default function ListaCotacoes({
  operadoras,
  aviso,
  onNova,
  onCotarEmpresa,
  recarregarSinal = 0,
}) {
  const [busca, setBusca] = useState("");
  const [buscaDeb, setBuscaDeb] = useState("");
  const [status, setStatus] = useState("OK");
  const [lista, setLista] = useState(null);
  const [selecao, setSelecao] = useState(() => new Set());

  useEffect(() => {
    const t = setTimeout(() => setBuscaDeb(busca.trim()), 250);
    return () => clearTimeout(t);
  }, [busca]);

  const carregar = useCallback(() => {
    const q = new URLSearchParams();
    if (buscaDeb) q.set("busca", buscaDeb);
    if (status) q.set("status", status);
    chamarRpa("GET", `/api/cotacoes?${q}`)
      .then((d) => {
        const arr = Array.isArray(d) ? d : [];
        setLista(arr);
        setSelecao((sel) => {
          const next = new Set([...sel].filter((id) => arr.some((c) => c.id === id && c.tem_pdf)));
          return next;
        });
      })
      .catch((e) => aviso?.(e.message, "erro"));
  }, [buscaDeb, status, aviso]);

  useEffect(() => {
    carregar();
  }, [carregar, recarregarSinal]);

  function toggle(id, on) {
    setSelecao((sel) => {
      const next = new Set(sel);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  async function baixarZip() {
    const ids = [...selecao];
    if (!ids.length) return;
    try {
      await baixarUrlRpa(
        ids.length === 1 ? `/api/cotacoes/${ids[0]}/pdf` : `/api/pdfs.zip?ids=${ids.join(",")}`,
      );
    } catch (e) {
      aviso?.(e.message, "erro");
    }
  }

  const nadaPadrao = !buscaDeb && (!status || status === "OK");

  return (
    <div>
      <h1>Cotações</h1>
      <p className="muted">Tudo o que o robô já cotou. Baixe o PDF daqui, sem entrar no portal.</p>
      <BannerPendencias aviso={aviso} recarregarSinal={recarregarSinal} />
      <section className="cartao">
        <div className="nativa-filtros">
          <input
            className="campo"
            type="search"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            aria-label="Buscar"
            placeholder="Buscar por empresa, CNPJ, plano ou protocolo"
          />
          <div className="nativa-segmentos" role="group" aria-label="Mostrar">
            {FILTROS_LISTA.map(([v, texto]) => (
              <button
                key={texto}
                type="button"
                className="secundario"
                aria-pressed={v === status}
                onClick={() => setStatus(v)}
              >
                {texto}
              </button>
            ))}
          </div>
          <span className="nativa-filtros-espaco" />
          {selecao.size > 0 ? (
            <button type="button" className="secundario" onClick={baixarZip}>
              {selecao.size === 1 ? "Baixar 1 PDF" : `Baixar ${selecao.size} PDFs (.zip)`}
            </button>
          ) : null}
        </div>
        {lista === null ? <p className="lista-carregando">Carregando cotações…</p> : null}
        {lista && lista.length === 0 ? (
          <div className="nativa-vazio">
            <p>
              {nadaPadrao
                ? "Nenhuma cotação ainda. As cotações que o robô fizer aparecem aqui, com o PDF para baixar."
                : "Nada encontrado com esse filtro."}
            </p>
            {nadaPadrao && onNova ? (
              <button type="button" onClick={onNova}>
                Fazer a primeira cotação
              </button>
            ) : null}
          </div>
        ) : null}
        {lista && lista.length > 0 ? (
          <>
            <TabelaCotacoes
              cotacoes={lista}
              empresa
              data
              selecao={selecao}
              onToggle={toggle}
              cotarDeNovo
              onCotarDeNovo={onCotarEmpresa}
              operadoras={operadoras}
              aviso={aviso}
            />
            {lista.length >= 300 ? (
              <p className="muted">Mostrando as 300 mais recentes. Use a busca para achar as mais antigas.</p>
            ) : null}
          </>
        ) : null}
      </section>
    </div>
  );
}
