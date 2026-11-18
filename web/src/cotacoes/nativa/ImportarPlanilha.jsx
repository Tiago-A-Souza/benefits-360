import { useRef, useState } from "react";
import { baixarUrlRpa, chamarRpa, RpaClienteErro } from "../rpaClient";
import { useConfirmacao } from "./Confirmacao";
import {
  itensDoImport,
  linhaErroImport,
  problemaArquivoImportar,
  resumoImportacao,
  textoPlanosImport,
} from "./regrasRestante";
import LogoOperadora from "./LogoOperadora";
import { attrsCartaoOperadora } from "./operadoras";
import { formatarCnpj, plural } from "./regrasNova";

export default function ImportarPlanilha({ operadoras, aviso, onEnfileirado }) {
  const ops = operadoras || [];
  const [opId, setOpId] = useState(ops.length === 1 ? ops[0].id : "");
  const [resultado, setResultado] = useState(null);
  const [nomeArquivo, setNomeArquivo] = useState("");
  const [lendo, setLendo] = useState(false);
  const [sobre, setSobre] = useState(false);
  const entrada = useRef(null);
  const [confirmar, modal] = useConfirmacao();

  function escolherOp(id) {
    setOpId(id);
    setResultado(null);
    setNomeArquivo("");
  }

  async function baixarModelo() {
    if (!opId) {
      aviso?.("Escolha antes a operadora da planilha.", "erro");
      return;
    }
    try {
      await baixarUrlRpa(`/api/modelo/${opId}`, `cotacoes_modelo_${opId}.xlsx`);
    } catch (e) {
      aviso?.(e.message, "erro");
    }
  }

  async function enviar(arquivo) {
    if (!arquivo) return;
    if (!opId) {
      aviso?.("Escolha antes a operadora da planilha.", "erro");
      return;
    }
    const problema = problemaArquivoImportar(arquivo);
    if (problema) {
      aviso?.(problema, "erro");
      return;
    }
    const form = new FormData();
    form.append("arquivo", arquivo);
    form.append("operadora", opId);
    setLendo(true);
    try {
      const r = await chamarRpa("POST", "/api/importar", form);
      setResultado(r);
      setNomeArquivo(arquivo.name);
    } catch (e) {
      aviso?.(e.message, "erro");
    } finally {
      setLendo(false);
      if (entrada.current) entrada.current.value = "";
    }
  }

  async function gerar(modo) {
    const { validos, erros, n } = resumoImportacao(resultado);
    if (!validos.length) return;
    if (modo === "emitir") {
      const op = ops.find((o) => o.id === opId);
      const ok = await confirmar({
        titulo: `Gerar ${plural(n, "cotação", "cotações")} na ${op ? op.nome : "operadora"}?`,
        texto: [
          `São ${plural(validos.length, "empresa", "empresas")}. Cada cotação gera um protocolo de verdade no portal.`,
          erros.length ? `As ${plural(erros.length, "linha", "linhas")} com problema ficam de fora.` : "",
          "O robô entra no portal sozinho, com o login guardado em Conexões.",
        ].filter(Boolean),
        ok: `Gerar ${plural(n, "cotação", "cotações")}`,
      });
      if (!ok) return;
    }
    try {
      const r = await chamarRpa("POST", "/api/trabalhos", {
        modo,
        confirmado: modo === "emitir",
        itens: itensDoImport(opId, validos),
      });
      onEnfileirado?.(r.id);
    } catch (e) {
      if (e instanceof RpaClienteErro && e.dados && e.dados.problemas) {
        aviso?.(
          `Algumas linhas não passaram: ${Object.keys(e.dados.problemas).join(", ")}. Corrija na planilha e importe de novo.`,
          "erro",
        );
      } else {
        aviso?.(e.message, "erro");
      }
    }
  }

  const { validos, erros, n, resumo } = resumoImportacao(resultado);

  return (
    <div>
      {modal}
      <h1>Importar planilha</h1>
      <p className="muted">
        Para cotar várias empresas de uma vez. Uma linha por empresa, no formato da planilha modelo. O robô confere
        tudo antes de começar.
      </p>

      <section className="cartao">
        {ops.length ? (
          <div className="nativa-form-linha">
            <div className="nativa-rotulo">Operadora</div>
            <div className="nativa-op-escolhas" role="group" aria-label="Operadora">
              {ops.map((o) => {
                const marca = attrsCartaoOperadora(o.id, o.id === opId);
                return (
                  <button
                    key={o.id}
                    type="button"
                    className={marca.className}
                    aria-pressed={o.id === opId}
                    title={o.nome}
                    style={marca.style}
                    data-cor-op={marca["data-cor-op"]}
                    onClick={() => escolherOp(o.id)}
                  >
                    <LogoOperadora operadora={o.id} tamanho="md" />
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}

        <input
          ref={entrada}
          type="file"
          accept=".xlsx"
          hidden
          aria-label="Planilha .xlsx"
          onChange={(e) => enviar(e.target.files[0])}
        />
        <div
          className={`nativa-soltar${sobre ? " nativa-soltar--sobre" : ""}`}
          role="button"
          tabIndex={0}
          aria-label="Escolher a planilha"
          aria-busy={lendo ? "true" : undefined}
          onClick={() => entrada.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              entrada.current?.click();
            }
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setSobre(true);
          }}
          onDragLeave={() => setSobre(false)}
          onDrop={(e) => {
            e.preventDefault();
            setSobre(false);
            enviar(e.dataTransfer.files[0]);
          }}
        >
          <strong>{lendo ? "Lendo a planilha..." : resultado ? "Trocar de planilha" : "Arraste a planilha para cá"}</strong>
          <div className="muted">ou clique para escolher o arquivo .xlsx</div>
        </div>
        <p className="muted nativa-modelo-linha">
          <button type="button" className="link" onClick={baixarModelo}>
            Baixar a planilha modelo
          </button>
          . A aba “como_preencher” explica cada coluna.
        </p>
      </section>

      {resultado ? (
        <section className="cartao">
          <div className="nativa-painel-cabeca">
            <h2>{nomeArquivo}</h2>
            <span className="muted">{resumo}</span>
          </div>
          {erros.length ? (
            <div className="nativa-problemas">
              <strong>Estas linhas ficam de fora até você corrigir na planilha:</strong>
              <ul>
                {erros.map((e) => (
                  <li key={`${e.linha}-${e.id}`}>{linhaErroImport(e)}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {validos.length ? (
            <div className="tabela-scroll nativa-tabela-rolagem">
              <table className="nativa-tabela">
                <thead>
                  <tr>
                    <th>Linha</th>
                    <th>Empresa</th>
                    <th>CNPJ</th>
                    <th className="right">Vidas</th>
                    <th className="right">Cotações</th>
                    <th>Planos</th>
                  </tr>
                </thead>
                <tbody>
                  {validos.map((v) => (
                    <tr key={`${v.linha}-${v.id}`}>
                      <td className="muted num">{String(v.linha)}</td>
                      <td className="nativa-empresa-nome">{/^L\d+$/.test(v.id) ? "—" : v.id}</td>
                      <td className="num">{formatarCnpj(v.cnpj)}</td>
                      <td className="right num">{String(v.vidas)}</td>
                      <td className="right num">{String(v.cotacoes)}</td>
                      <td className="muted">{textoPlanosImport(v.dados && v.dados.planos)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">Nenhuma linha está pronta para cotar.</p>
          )}
        </section>
      ) : null}

      {resultado && validos.length ? (
        <div className="nativa-barra-acao">
          <div className="nativa-resumo">
            {plural(n, "cotação", "cotações")} em {plural(validos.length, "empresa", "empresas")}
          </div>
          <div className="nativa-acoes">
            <button type="button" className="secundario" onClick={() => gerar("ensaio")}>
              Ensaiar sem emitir
            </button>
            <button type="button" onClick={() => gerar("emitir")}>
              Gerar {plural(n, "cotação", "cotações")}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
