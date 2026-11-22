import { useEffect, useState } from "react";
import { obterEstadoRpaCotacoes } from "../api";
import NavegacaoFerramentas from "../NavegacaoFerramentas";

export default function CotacoesRpa({ onMeusEstudos, onSimularRede, onVoltarEstudo, rotuloEstudo }) {
  const [diag, setDiag] = useState(null);
  const [erro, setErro] = useState(null);

  useEffect(() => {
    let vivo = true;
    obterEstadoRpaCotacoes()
      .then((d) => vivo && setDiag(d))
      .catch((e) => vivo && setErro(e.message || "Falha ao consultar o RPA."));
    return () => {
      vivo = false;
    };
  }, []);

  const ligado = diag?.ligado;
  const url = diag?.url || "http://127.0.0.1:8600";

  return (
    <div className="lista-shell">
      <aside className="lista-rail app-sidebar">
        <NavegacaoFerramentas
          ativo="cotacoes"
          onMeusEstudos={onMeusEstudos}
          onSimularRede={onSimularRede}
          onCotacoes={() => {}}
          onVoltarEstudo={onVoltarEstudo}
          rotuloEstudo={rotuloEstudo}
        />
      </aside>

      <main className="lista-main cotacoes-rpa">
        <header className="lista-head">
          <div>
            <h1>Cotações</h1>
            <p>
              Versão iframe do robô (comparar / reverter). A aba Cotações padrão é nativa; tire{" "}
              <code>?cotacoes-iframe=1</code> da URL para voltar.
            </p>
          </div>
        </header>

        {erro && <p className="erro">{erro}</p>}

        {!diag && !erro && <p className="lista-carregando">Conferindo se o robô está no ar…</p>}

        {diag && diag.hospedado ? (
          <div className="cotacoes-rpa-off" role="status">
            <p>
              <strong>Esta tela iframe não funciona no site da nuvem.</strong>
            </p>
            <p>{diag.aviso}</p>
            <p>
              Volte à aba <strong>Cotações</strong> (sem <code>?cotacoes-iframe=1</code>) e deixe o
              robô ligado no PC com <code>Abrir Benefits Robo.bat</code>.
            </p>
          </div>
        ) : null}

        {diag && !diag.hospedado && !ligado && (
          <div className="cotacoes-rpa-off" role="status">
            <p>
              <strong>O robô de cotações não está ligado</strong> em <code>{url}</code>.
            </p>
            <p>Na raiz do repositório, execute:</p>
            <pre className="cotacoes-rpa-cmd">
              <code>{diag.comando_subir || "powershell -ExecutionPolicy Bypass -File .\\scripts\\subir-benefits-e-rpa.ps1"}</code>
            </pre>
            <p className="cotacoes-rpa-hint">Depois recarregue esta página.</p>
          </div>
        )}

        {diag && !diag.hospedado && ligado && (
          <iframe
            className="cotacoes-rpa-iframe"
            title="Newport Cotações (RPA)"
            src={url}
            allow="clipboard-read; clipboard-write"
          />
        )}
      </main>
    </div>
  );
}