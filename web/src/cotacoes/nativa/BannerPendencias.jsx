import { useCallback, useEffect, useState } from "react";
import { chamarRpa } from "../rpaClient";
import { useConfirmacao } from "./Confirmacao";
import { TEXTO_PENDENCIA, empresaDe, formatarCnpj } from "./regrasNova";

/**
 * Banner de pendências (espelho do painel em cotacoes.js / início).
 * Visível na Nova cotação e no Andamento: o robô não reemite enquanto estiverem aqui.
 */
export default function BannerPendencias({ aviso }) {
  const [lista, setLista] = useState([]);
  const [confirmar, modal] = useConfirmacao();

  const carregar = useCallback(() => {
    chamarRpa("GET", "/api/pendencias")
      .then((d) => setLista(Array.isArray(d) ? d : []))
      .catch(() => setLista([]));
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function resolver(p, acao) {
    const opcoes =
      acao === "liberar"
        ? {
            titulo: "Liberar para emitir de novo?",
            texto: [
              "Faça isso só se você conferiu no portal, em Cotações emitidas, que esta cotação não saiu.",
              "Se ela saiu e você liberar, a próxima vez gera uma cotação repetida.",
            ],
            ok: "Conferi: não saiu. Liberar",
            principal: false,
          }
        : {
            titulo: "Marcar como resolvida?",
            texto: [
              "Use quando a cotação saiu no portal e você já tem o PDF (baixado à mão).",
              "O robô continua sem emitir esta cotação de novo.",
            ],
            ok: "Marcar como resolvida",
          };
    if (!(await confirmar(opcoes))) return;
    try {
      await chamarRpa("POST", acao === "liberar" ? "/api/liberar" : "/api/concluir", {
        operadora: p.operadora,
        chave: p.chave,
      });
      aviso?.(acao === "liberar" ? "Liberada. Peça a cotação de novo quando quiser." : "Pendência resolvida.");
      carregar();
    } catch (e) {
      aviso?.(e.message, "erro");
    }
  }

  if (!lista.length) return modal;

  return (
    <section className="cartao nativa-pendencias" aria-label="Pendências no portal">
      {modal}
      <h2>
        {lista.length === 1
          ? "Uma cotação pede conferência no portal"
          : `${lista.length} cotações pedem conferência no portal`}
      </h2>
      <p className="muted">
        Enquanto estiverem aqui, o robô não emite estas cotações de novo. Assim não sai cotação repetida.
      </p>
      <ul className="nativa-pend-lista">
        {lista.map((p) => (
          <li key={`${p.operadora}-${p.chave}`} className="nativa-pend-item">
            <div>
              <strong>
                {p.razao_social || empresaDe(p) || formatarCnpj(p.cnpj)}: {p.plano}
                {p.acomodacao ? `, ${p.acomodacao}` : ""}
              </strong>
              <div className="muted">
                {TEXTO_PENDENCIA[p.status] || p.status}
                {p.protocolo ? ` Protocolo ${p.protocolo}.` : ""}
              </div>
            </div>
            <div className="nativa-acoes-linha">
              {p.status === "emitindo" ? (
                <button type="button" className="secundario btn-compacto" onClick={() => resolver(p, "liberar")}>
                  Não saiu: liberar
                </button>
              ) : null}
              <button type="button" className="secundario btn-compacto" onClick={() => resolver(p, "concluir")}>
                {p.status === "emitindo" ? "Saiu: já tenho o PDF" : "Já tenho o PDF"}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
