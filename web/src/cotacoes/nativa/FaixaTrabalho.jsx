import { nomeEtapa } from "./regrasNova";

/** Banner “Robô trabalhando” quando a Nova cotação está aberta e há pedido em andamento. */
export default function FaixaTrabalho({ trabalho, etapa, operadoras, onAcompanhar }) {
  if (!trabalho) return null;
  const op = etapa ? (operadoras || []).find((o) => o.id === etapa.operadora) : null;
  const tela = etapa && op ? nomeEtapa(operadoras, etapa.operadora, etapa.etapa) : null;
  const parando = Boolean(trabalho.parando);
  return (
    <div className="nativa-faixa-trabalho" role="status">
      <span>
        {parando ? "Parando o robô" : "Robô trabalhando"}
        {etapa && etapa.plano ? `: ${etapa.plano}` : ""}
        {tela ? ` (tela ${tela})` : ""}
      </span>
      <button type="button" className="secundario btn-compacto" onClick={() => onAcompanhar(trabalho.id)}>
        Acompanhar
      </button>
    </div>
  );
}
