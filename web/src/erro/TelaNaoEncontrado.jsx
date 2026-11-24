import AppChrome, { useAppChrome } from "../layout/AppChrome";
import BarraLateral from "../layout/BarraLateral";
import NavegacaoFerramentas from "../NavegacaoFerramentas";

const TEXTOS = {
  estudo: {
    titulo: "Estudo não encontrado",
    corpo:
      "Este estudo não foi encontrado ou você não tem acesso. Nada foi exibido.",
  },
  rota: {
    titulo: "Esta página não existe",
    corpo: "Este endereço não corresponde a nenhuma tela do Benefits.",
  },
  erro: {
    titulo: "Não foi possível abrir este estudo",
    corpo: "A tela não carregou. Os seus estudos continuam no lugar; nada foi apagado.",
  },
};

export default function TelaNaoEncontrado({
  tipo = "rota",
  onVoltarEstudos,
  onSimularRede,
  onCotacoes,
  onSair,
  onTentar,
}) {
  const chrome = useAppChrome();
  const t = TEXTOS[tipo] || TEXTOS.rota;
  const pagina = (
    <div className="lista-shell">
      <BarraLateral>
        <NavegacaoFerramentas
          ativo="estudos"
          onMeusEstudos={onVoltarEstudos}
          onSimularRede={onSimularRede}
          onCotacoes={onCotacoes}
        />
      </BarraLateral>
      <main className="lista-main">
        <div className="tela-erro" role="alert">
          <h1>{t.titulo}</h1>
          <p>{t.corpo}</p>
          <div className="tela-erro-acoes">
            {onTentar ? (
              <button type="button" onClick={onTentar}>
                Tentar de novo
              </button>
            ) : null}
            <button type="button" className={onTentar ? "secundario" : undefined} onClick={onVoltarEstudos}>
              Voltar aos estudos
            </button>
          </div>
        </div>
      </main>
    </div>
  );

  if (chrome) return pagina;
  return <AppChrome onSair={onSair}>{pagina}</AppChrome>;
}
