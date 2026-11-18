import { tituloProblemaLogin } from "./regrasNova";

const NA_LOGIN = ["sem_credenciais", "recusadas", "troca_senha", "senha_comprida"];

export default function FaixaProblemaLogin({ problema, operadoras, onAbrirLogin, onFechar }) {
  if (!problema) return null;
  const op = (operadoras || []).find((o) => o.id === problema.operadora);
  const nome = op ? op.nome : problema.operadora;
  const motivo = problema.motivo;
  const titulo = tituloProblemaLogin(nome, motivo);
  const texto =
    motivo === "sem_credenciais"
      ? "O robô entra no portal sozinho com o login guardado em Conexões. Sem ele, nem abre o portal."
      : problema.mensagem || "";
  const naLogin = NA_LOGIN.includes(motivo);

  return (
    <div className="nativa-faixa-problema" role="alert">
      <div>
        <strong>{titulo}</strong>
        {texto ? <span className="muted"> {texto}</span> : null}
      </div>
      <div className="nativa-acoes-linha">
        {naLogin ? (
          <button
            type="button"
            className="secundario btn-compacto"
            onClick={() => {
              onAbrirLogin?.(problema.operadora);
              onFechar?.();
            }}
          >
            Abrir o login
          </button>
        ) : null}
        <button type="button" className="secundario btn-compacto" onClick={onFechar}>
          Fechar
        </button>
      </div>
    </div>
  );
}
