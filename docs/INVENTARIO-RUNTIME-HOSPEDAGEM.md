# Inventário de runtime — o que o Benefits precisa e não vai no Git

Piloto hospedado: **uma instância**, volume persistente, `NEWPORT_MODO=real`.
Medidas locais em 2026-11-19 (máquina de desenvolvimento). Tamanhos mudam.

**Decisão em aberto (Tiago / Leonardo):** catálogos de rede/regras/PME já estão
no Git (`docs/`). Podem ir **na imagem**. Se a Newport quiser atualizar a
planilha SiscorNet sem rebuild, coloque uma cópia no volume e aponte
`NEWPORT_REDE_XLSX`. O restante gravável (bancos, PDFs, HTML) **só no volume**.

## O que NÃO está no Git (gravável)

| Item | Onde fica hoje | Tamanho local | Imagem | Volume | Dado pessoal |
|---|---|---|---|---|---|
| `estudos.db` | `.private/runtime/estudos.db` (real) / `.data/newport_app.db` (demo) | ~101 MB real | não | **sim** | **sim** — rascunhos, vidas, CNPJ |
| `importacoes.db` | `.private/runtime/importacoes.db` | ~4 MB | não | **sim** | **sim** — SISCOR importado |
| `cotacoes.db` | `.private/runtime/cotacoes.db` | ~77 MB | não | **sim** | **sim** — extrações de PDF |
| Uploads SISCOR | `.private/runtime/uploads/` | ~2 MB | não | **sim** | **sim** — planilhas de posição |
| PDFs de cotação | `.private/runtime/cotacoes/` | ~359 MB | não | **sim** | **sim** — propostas com nomes |
| HTML entregável | `.private/runtime/entregaveis/` | ~182 MB | não | **sim** | **sim** — estudo do cliente |
| `diagnostico.jsonl` | mesmo runtime | pequeno | não | **sim** | possível (ids de estudo) |
| Backups locais | `.private/runtime/backups/` | ~237 MB | não | pasta de backup **à parte** | **sim** |
| Demo `.data/` | `.data/` | ~940 MB (inclui lixo de teste) | não | não no piloto real | fictício / mistura de testes |
| Corpus `.private/corpus/` | `.private/corpus/` | variável | não | não (só máquina de dev) | **sim** se houver PDF real |
| `.env.local` | raiz e `web/` | — | **nunca** | **nunca** | segredos |
| Saída do robô | `rpa/saida/` no **PC do corretor** | ~1,1 GB aqui | não entra no host | no PC | **sim** — PDFs e sessão |

Pastas `_tmp_*`, scripts de diagnóstico e HTML de gabarito em `.private/runtime/`
são lixo de desenvolvimento: **não copiar para o volume do piloto**.

## O que ESTÁ no Git (catálogo compartilhado Newport)

Pode ir na **imagem**. Sem PII. Atualização = novo deploy, ou override por env.

| Item | Onde | Tamanho | Imagem | Volume | PII |
|---|---|---|---|---|---|
| SiscorNet xlsx | `docs/SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx` | 2,0 MB | sim | opcional (`NEWPORT_REDE_XLSX`) | não (rede nacional) |
| Hospitais principais | `docs/hospitais_principais_base.csv` | 100 KB | sim | não | não |
| Laboratórios principais | `docs/laboratorios_principais_base.csv` | 0,3 KB | sim | não | não |
| Aliases de plano/rede | `docs/planos_rede_aliases.csv` | 2 KB | sim | não | não |
| Regras comerciais + aliases | `docs/regras_comerciais_*.csv` | ~9 KB | sim | não | não |
| Reajuste PME | `docs/reajustes_pme_base.csv` | 10 KB | sim | não | não |
| Legenda de códigos | `docs/codigos_rede_legenda.csv` | 0,6 KB | sim | não | não |
| Logo Newport | `docs/newport-logo.png` + `src/.../assets` | pequeno | sim | não | não |

## O que NÃO sobe no host (fica no PC)

| Item | Por quê |
|---|---|
| Robô RPA (`rpa/`, porta 8600) | Roda no computador do corretor; o site hospedado chama `http://127.0.0.1:8600` |
| Cofre de senha do portal | Windows DPAPI, nunca no Benefits |
| `rpa/saida/` | PDFs e sessão do portal no PC |
| `.venv`, `web/node_modules`, `web/dist` de dev | a imagem gera o `dist` no build |

## Variáveis que apontam para disco (hoje)

| Variável | Padrão se ausente |
|---|---|
| `NEWPORT_DATA_DIR` | `<repo>/.data` (só modo demo) |
| `NEWPORT_PRIVATE_RUNTIME` | `<repo>/.private/runtime` (modo real) |
| `NEWPORT_REDE_XLSX` | `docs/SiscorNet_….xlsx` (há um fallback local em Downloads) |
| `NEWPORT_CORPUS_COTACOES` | `.private/corpus/cotacoes` (dev) |
| `NEWPORT_UPLOAD_MAX_BYTES` | 10 MiB |
