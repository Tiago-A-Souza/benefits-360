import { tituloProblemaLogin } from "./regrasNova";

const NA_ENGRENAGEM = ["sem_credenciais", "recusadas", "troca_senha", "senha_comprida"];

export default function FaixaProblemaLogin({ problema, operadoras, urlRobo, onFechar }) {
  if (!problema) return null;
  const op = (operadoras || []).find((o) => o.id === problema.operadora);
  const nome = op ? op.nome : problema.operadora;
  const motivo = problema.motivo;
  const titulo = tituloProblemaLogin(nome, motivo);
  const texto =
    motivo === "sem_credenciais"
      ? "O robô entra no portal sozinho com o login guardado na engrenagem. Sem ele, nem abre o portal."
      : problema.mensagem || "";
  const naEngrenagem = NA_ENGRENAGEM.includes(motivo);

  return (
    <div className="nativa-faixa-problema" role="alert">
      <div>
        <strong>{titulo}</strong>
        {texto ? <span className="muted"> {texto}</span> : null}
      </div>
      <div className="nativa-acoes-linha">
        {naEngrenagem ? (
          <a
            className="secundario btn-compacto"
            href={`${urlRobo}/#/robo/${problema.operadora}?login=1`}
            target="_blank"
            rel="noreferrer"
            onClick={onFechar}
          >
            Abrir a engrenagem
          </a>
        ) : null}
        <button type="button" className="secundario btn-compacto" onClick={onFechar}>
          Fechar
        </button>
      </div>
    </div>
  );
}
