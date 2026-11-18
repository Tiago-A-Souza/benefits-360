import { useEffect, useRef, useState } from "react";
import { baixarUrlRpa, chamarRpa, ouvirEventosRpa } from "../rpaClient";
import { useConfirmacao } from "./Confirmacao";
import LogoOperadora from "./LogoOperadora";
import { attrsCartaoOperadora } from "./operadoras";
import TabelaCotacoes from "./TabelaCotacoes";
import {
  CONFIRMACOES_REPETIR,
  CONEXAO,
  contarStatus,
  digitos,
  horaRegistro,
  nomeEtapa,
  plural,
  subtituloTrabalho,
} from "./regrasNova";

function EtapasPilulas({ op, etapa }) {
  if (!op) return null;
  const atual = etapa ? op.etapas.findIndex((x) => x.id === etapa.etapa) : -1;
  return (
    <ol className="nativa-etapas" aria-label="Telas do portal">
      {op.etapas.map((x, i) => (
        <li
          key={x.id}
          className={i < atual ? "feita" : i === atual ? "atual" : ""}
          aria-current={i === atual ? "step" : undefined}
        >
          {x.nome}
        </li>
      ))}
    </ol>
  );
}

export default function Andamento({
  trabalhoId,
  operadoras,
  conexaoExterna = {},
  onNovoTrabalho,
  onNova,
  onIrIframeCotacoes,
  onIrLogin,
  urlRobo,
  aviso,
}) {
  const [t, setT] = useState(null);
  const [falhou, setFalhou] = useState(false);
  const [etapa, setEtapa] = useState(null);
  const [pedidoAtual, setPedidoAtual] = useState(null);
  const [conexao, setConexao] = useState(conexaoExterna);
  const [parando, setParando] = useState(false);
  const tRef = useRef(null);
  const timer = useRef(null);
  const [confirmar, modal] = useConfirmacao();

  useEffect(() => {
    tRef.current = t;
  }, [t]);

  useEffect(() => {
    setConexao((c) => ({ ...c, ...conexaoExterna }));
  }, [conexaoExterna]);

  useEffect(() => {
    let vivo = true;
    setFalhou(false);
    setT(null);
    setEtapa(null);
    setPedidoAtual(null);
    setParando(false);
    chamarRpa("GET", `/api/trabalhos/${trabalhoId}`)
      .then((d) => {
        if (vivo) {
          setT(d);
          if (d.parando) setParando(true);
        }
      })
      .catch(() => {
        if (vivo) setFalhou(true);
      });
    return () => {
      vivo = false;
    };
  }, [trabalhoId]);

  function recarregar() {
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const novo = await chamarRpa("GET", `/api/trabalhos/${trabalhoId}`);
        setT((ant) => Object.assign(novo, { eventos: (ant && ant.eventos) || novo.eventos || [] }));
        if (novo.parando) setParando(true);
        if (novo.status && novo.status !== "rodando") setParando(false);
      } catch {
        /* a próxima atualização tenta de novo */
      }
    }, 250);
  }

  useEffect(() => {
    const { fechar } = ouvirEventosRpa((ev) => {
      const tid = Number(trabalhoId);
      if (ev.tipo === "conexao") {
        setConexao((c) => ({ ...c, [ev.operadora]: ev.status }));
        return;
      }
      if (ev.tipo === "parando" && Number(ev.trabalho) === tid) {
        setParando(true);
        return;
      }
      if (ev.trabalho !== tid) return;
      if (ev.tipo === "etapa") setEtapa(ev);
      else if (ev.tipo === "pedido") setPedidoAtual(ev.pedido);
      else if (ev.tipo === "log") {
        setT((ant) => {
          if (!ant) return ant;
          return {
            ...ant,
            eventos: [
              ...(ant.eventos || []),
              { tipo: "log", texto: ev.texto, dados: { nivel: ev.nivel }, em: new Date().toISOString() },
            ],
          };
        });
      } else if (ev.tipo === "trabalho") {
        setT((ant) => (ant ? { ...ant, status: ev.status, mensagem: ev.mensagem || ant.mensagem } : ant));
        if (ev.status !== "rodando") {
          setEtapa(null);
          setParando(false);
        }
        recarregar();
      } else if (ev.tipo === "cotacao") recarregar();
      else if (["login_entrando", "login_aguardando", "login_ok", "codigo_necessario", "login_problema"].includes(ev.tipo)) {
        /* painel redesenha via conexao / recarregar */
      }
    });
    return () => {
      fechar();
      clearTimeout(timer.current);
    };
  }, [trabalhoId]);

  async function repetir(modo, motivo = "gerar") {
    const atual = tRef.current;
    if (!atual) return;
    if (modo === "emitir" && !(await confirmar(CONFIRMACOES_REPETIR[motivo] || CONFIRMACOES_REPETIR.gerar))) return;
    try {
      const r = await chamarRpa("POST", `/api/trabalhos/${atual.id}/repetir`, { modo, confirmado: modo === "emitir" });
      onNovoTrabalho?.(r.id);
    } catch (e) {
      if (e.dados && e.dados.problemas) {
        aviso?.("Os dados deste pedido não passam mais na conferência. Abra a Nova cotação e confira.", "erro");
      } else aviso?.(e.message, "erro");
    }
  }

  async function parar() {
    const atual = tRef.current;
    if (!atual) return;
    if (parando) {
      aviso?.("O robô ainda está soltando esta tela. Espere um instante — o pedido de parada já foi enviado.", "info");
      return;
    }
    const naFila = atual.status === "na_fila";
    const ok = await confirmar({
      titulo: naFila ? "Tirar este pedido da fila?" : "Parar o robô?",
      texto: naFila
        ? ["O robô não vai começar este pedido."]
        : [
            "O robô para agora, nesta tela. Não espera a próxima tela e não emite mais nada.",
            "Se o clique de emitir já foi dado, o robô ainda lê o protocolo dessa cotação.",
          ],
      ok: naFila ? "Tirar da fila" : "Parar o robô",
      principal: false,
    });
    if (!ok) return;
    try {
      const r = await chamarRpa("POST", `/api/trabalhos/${atual.id}/parar`);
      if (!r.ok) aviso?.("Este pedido já terminou ou já começou: veja a situação abaixo.", "erro");
      else {
        if (!naFila) setParando(true);
        aviso?.(naFila ? "Pedido tirado da fila." : "Parando agora. O robô solta esta tela e não emite mais nada.");
      }
    } catch (e) {
      aviso?.(e.message, "erro");
    }
  }

  async function abrirPastaCliente(c) {
    try {
      await chamarRpa("POST", `/api/cotacoes/${c.id}/abrir-pasta`);
    } catch (e) {
      aviso?.(e.message, "erro");
    }
  }

  if (falhou) {
    return (
      <div className="nativa-andamento">
        <header className="lista-head">
          <div>
            <h1>Pedido não encontrado</h1>
            <p>Ele pode ter sido apagado. As cotações feitas continuam na lista.</p>
          </div>
        </header>
        <button type="button" className="secundario" onClick={() => onIrIframeCotacoes?.()}>
          Ver as cotações
        </button>
      </div>
    );
  }

  if (!t) {
    return <p className="lista-carregando">Carregando o pedido…</p>;
  }

  const opId = (etapa && etapa.operadora) || (t.operadoras || [])[0];
  const op = (operadoras || []).find((o) => o.id === opId) || (operadoras || [])[0];
  const n = contarStatus(t.cotacoes);
  const feitas = (t.cotacoes || []).length;
  const conexaoOp = op ? conexao[op.id] || "" : "";

  let tituloPainel = "";
  let linhaPainel = "";
  const botoes = [];

  if (t.status === "na_fila") {
    tituloPainel = "Na fila";
    linhaPainel = "O robô começa assim que terminar o pedido anterior.";
    botoes.push(
      <button key="fila" type="button" className="secundario" onClick={parar}>
        Tirar da fila
      </button>,
    );
  } else if (t.status === "rodando") {
    tituloPainel = "O robô está no portal";
    linhaPainel = "Abrindo o portal";
    if (parando) {
      tituloPainel = "Parando agora";
      linhaPainel = "O robô está saindo desta tela. A janela do portal fica aberta.";
    } else if (conexaoOp === "aguardando_codigo") {
      tituloPainel = "Esperando o código de verificação";
      linhaPainel = "Digite na faixa do topo o código que o portal mandou para o seu celular/e-mail.";
    } else if (conexaoOp === "aguardando_portal") {
      tituloPainel = "Esperando o portal liberar o acesso";
      linhaPainel =
        ((op && op.textos) || {}).aguardando_portal ||
        "O portal ainda tem uma sessão aberta para este login (outro navegador ou uma janela fechada). O robô entra de novo sozinho em instantes; não precisa fazer nada.";
    } else if (conexaoOp === "entrando") {
      tituloPainel = "Entrando no portal";
      linhaPainel = `O robô entra sozinho na ${op.nome}, com o login guardado em Conexões.`;
    } else if (etapa) {
      const nomeTela = nomeEtapa(operadoras, etapa.operadora, etapa.etapa);
      if (etapa.plano) {
        const [plano, acomod] = etapa.plano.split(" | ");
        tituloPainel = `Cotando ${plano}${acomod ? `, ${acomod}` : ""}`;
        if (etapa.total > 1) tituloPainel += ` (plano ${etapa.indice + 1} de ${etapa.total})`;
      } else if (etapa.etapa === "planos") {
        tituloPainel = "Escolhendo os planos mais baratos";
      }
      linhaPainel = `Tela ${nomeTela}${pedidoAtual && t.total_pedidos > 1 ? `, empresa ${pedidoAtual}` : ""}`;
    }
    botoes.push(
      <button key="parar" type="button" className="nativa-perigo" onClick={parar} disabled={parando}>
        {parando ? "Parando…" : "Parar o robô"}
      </button>,
    );
  } else if (t.tipo === "conectar") {
    const ok = t.status === "concluido";
    tituloPainel = ok ? `Login ok na ${op ? op.nome : "operadora"}` : "O login não deu certo";
    linhaPainel = ok
      ? "O robô entrou no portal e parou na tela de módulos, sem cotar. As próximas cotações usam esta sessão."
      : t.mensagem || "O robô não conseguiu entrar no portal.";
    if (ok) {
      botoes.push(
        <button key="nova" type="button" onClick={() => onNova?.()}>
          Nova cotação
        </button>,
      );
    } else if (op) {
      botoes.push(
        <button key="eng" type="button" className="secundario" onClick={() => onIrLogin?.(op.id)}>
          Abrir o login
        </button>,
      );
    }
  } else if (t.status === "concluido") {
    const pendentes = (n.ERRO || 0) + (n.VERIFICAR || 0) + (n.PARADO || 0);
    if (t.modo === "ensaio") {
      const okEnsaio = n.ENSAIO_OK || 0;
      tituloPainel = okEnsaio && !pendentes ? "Ensaio concluído" : "O ensaio encontrou problemas";
      linhaPainel =
        okEnsaio && !pendentes
          ? "O robô percorreu as telas com o primeiro plano de cada empresa e parou antes de emitir. Se os valores abaixo batem com o que você espera, gere as cotações."
          : "Veja o motivo em cada linha abaixo. Nada foi emitido.";
      if (okEnsaio) {
        botoes.push(
          <button key="gerar" type="button" onClick={() => repetir("emitir")}>
            Gerar as cotações
          </button>,
        );
      }
      botoes.push(
        <button key="ensaio" type="button" className="secundario" onClick={() => repetir("ensaio")}>
          Ensaiar de novo
        </button>,
      );
    } else {
      const emitidas = n.OK || 0;
      const puladas = n.PULADO || 0;
      const pdfs = (t.cotacoes || []).filter((c) => c.tem_pdf).length;
      const naPasta = (t.cotacoes || []).find((c) => c.pdf_destino && c.tem_pdf);
      const soPuladas = !emitidas && !pendentes && puladas > 0 && puladas === (t.cotacoes || []).length;
      tituloPainel = emitidas ? `Pronto: ${plural(emitidas, "cotação emitida", "cotações emitidas")}` : "Nenhuma cotação nova";
      if (soPuladas) tituloPainel = puladas === 1 ? "Esta cotação já tinha sido emitida" : "Estas cotações já tinham sido emitidas";
      if (pendentes) tituloPainel = `${plural(pendentes, "cotação ficou", "cotações ficaram")} sem emitir`;
      linhaPainel = "Veja a situação de cada plano abaixo.";
      if (pendentes) linhaPainel = "Veja o motivo em cada linha. Pedir de novo é seguro: o robô não repete o que já foi emitido.";
      else if (soPuladas) {
        linhaPainel =
          "Sozinho, o robô não emite de novo a mesma cotação (mesma empresa, vidas, opções e plano): ele entrou no portal, conferiu e terminou. O PDF de antes está abaixo. Para emitir de novo de propósito (teste ou demonstração), clique em Cotar de novo, depois em Gerar e, no aviso, em “Emitir de novo mesmo assim”.";
      } else if (naPasta) linhaPainel = "Os PDFs já estão na pasta do cliente. Também dá para baixar daqui.";
      else if (pdfs) linhaPainel = "Baixe os PDFs abaixo.";
      if (pendentes) {
        botoes.push(
          <button key="tentar" type="button" onClick={() => repetir("emitir", "tentar")}>
            Tentar de novo as que faltaram
          </button>,
        );
      }
      const cnpjs = [...new Set((t.cotacoes || []).map((c) => c.cnpj).filter(Boolean))];
      if (soPuladas && cnpjs.length === 1) {
        botoes.push(
          <button key="cotar" type="button" onClick={() => onNova?.(digitos(cnpjs[0]))}>
            Cotar de novo
          </button>,
        );
      }
      if (naPasta) {
        botoes.push(
          <button key="pasta" type="button" className="secundario" onClick={() => abrirPastaCliente(naPasta)}>
            Abrir a pasta do cliente
          </button>,
        );
      }
    }
  } else if (t.status === "erro") {
    tituloPainel = "O robô parou";
    linhaPainel = "Confira se a janela do portal continua aberta e peça de novo. O que já foi emitido não sai de novo.";
    if (t.tipo === "cotar") {
      botoes.push(
        <button key="tentar" type="button" onClick={() => repetir(t.modo, "tentar")}>
          Tentar de novo
        </button>,
      );
    }
  } else if (t.status === "cancelado") {
    tituloPainel = "Parado";
    linhaPainel = feitas
      ? "Você parou o robô. O que ficou pronto até ali está abaixo."
      : "Você parou o robô antes de ele emitir qualquer cotação.";
    if (t.tipo === "cotar") {
      botoes.push(
        <button key="cont" type="button" onClick={() => repetir(t.modo, "continuar")}>
          {t.modo === "ensaio" ? "Ensaiar de novo" : "Continuar de onde parou"}
        </button>,
      );
    }
  } else if (t.status === "interrompido") {
    tituloPainel = "Interrompido";
    linhaPainel =
      "A janela preta do Newport Cotações foi fechada enquanto o robô trabalhava. Se faltar alguma cotação, peça de novo: o robô não repete o que já foi emitido.";
    if (t.tipo === "cotar") {
      botoes.push(
        <button key="pedir" type="button" className="secundario" onClick={() => repetir(t.modo, "continuar")}>
          Pedir de novo
        </button>,
      );
    }
  }

  const comPdf = (t.cotacoes || []).filter((c) => c.tem_pdf);
  const varias = new Set((t.cotacoes || []).map((c) => c.cnpj)).size > 1 || t.total_pedidos > 1;
  const eventos = (t.eventos || []).filter((e) => e.texto);
  const marca = op ? attrsCartaoOperadora(op.id, t.status === "rodando") : null;

  return (
    <div className="nativa-andamento">
      {modal}
      <header className="lista-head">
        <div>
          <h1>{t.titulo || "Pedido"}</h1>
          <p>{subtituloTrabalho(t)}</p>
        </div>
      </header>

      <section
        className={`cartao nativa-painel-robo ${marca ? marca.className : ""}`}
        style={marca ? marca.style : undefined}
        data-cor-op={marca ? marca["data-cor-op"] : undefined}
        aria-live="polite"
      >
        <div className="nativa-op-cabeca">
          <h2>
            {op ? <LogoOperadora operadora={op.id} tamanho="md" /> : null} {tituloPainel}
          </h2>
        </div>
        {t.status === "erro" ? <div className="nativa-problemas">{t.mensagem || "erro sem descrição"}</div> : null}
        <p className="muted">{linhaPainel}</p>
        {t.status === "rodando" && t.tipo === "cotar" && op ? <EtapasPilulas op={op} etapa={etapa} /> : null}
        {t.status === "rodando" && t.tipo === "cotar" && t.total_cotacoes > 1 ? (
          <p className="muted">
            {feitas} de {plural(t.total_cotacoes, "cotação pronta", "cotações prontas")}
          </p>
        ) : null}
        {conexaoOp && t.status === "rodando" ? (
          <p className="muted">
            <span className={`nativa-ponto nativa-ponto--${conexaoOp}`} /> {CONEXAO[conexaoOp] || conexaoOp}
          </p>
        ) : null}
        {botoes.length ? <div className="nativa-acoes-robo">{botoes}</div> : null}
      </section>

      {t.tipo === "cotar" ? (
        <section className="cartao">
          <div className="nativa-painel-cabeca">
            <h2>{t.modo === "ensaio" ? "Resultado do ensaio" : "Cotações deste pedido"}</h2>
            {comPdf.length > 1 ? (
              <button
                type="button"
                className="secundario"
                onClick={() => baixarUrlRpa(`/api/pdfs.zip?trabalho=${t.id}`).catch((e) => aviso?.(e.message, "erro"))}
              >
                Baixar os {comPdf.length} PDFs (.zip)
              </button>
            ) : null}
          </div>
          {!(t.cotacoes || []).length ? (
            <p className="muted">
              {["na_fila", "rodando"].includes(t.status)
                ? "Cada cotação aparece aqui assim que fica pronta, com o PDF para baixar."
                : "Nenhuma cotação foi registrada neste pedido."}
            </p>
          ) : (
            <TabelaCotacoes
              cotacoes={[...(t.cotacoes || [])].reverse()}
              empresa={varias}
              operadoras={operadoras}
              aviso={aviso}
            />
          )}
        </section>
      ) : null}

      <section className="cartao">
        <details>
          <summary>Ver o registro do robô, linha a linha</summary>
          <div className="nativa-registro" role="log">
            {eventos.length ? (
              eventos.map((ev, i) => (
                <p
                  key={i}
                  className={
                    (ev.dados && ev.dados.nivel) === "error" || ev.tipo === "erro"
                      ? "erro"
                      : (ev.dados && ev.dados.nivel) === "warning"
                        ? "nativa-warning"
                        : ""
                  }
                >
                  <span className="num">{horaRegistro(ev.em)}</span> {ev.texto}
                </p>
              ))
            ) : (
              <p>Ainda sem registro.</p>
            )}
          </div>
        </details>
      </section>
    </div>
  );
}
