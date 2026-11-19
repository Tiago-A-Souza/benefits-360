# Comparativo — Simular rede × Etapa 5 (seleção + HTML)

> Só leitura · 2026-11-18 · `master` @ `a7401e5`.  
> Duas superfícies, **mesma base SiscorNet** e **mesmo cache** (`carregar_base_rede_hospital` / `carregar_hospitais_principais`). Não grava nada no Simular; a etapa 5 grava `selecao_rede` no rascunho e alimenta o HTML.

---

## 1. Retrato de cada superfície

### 1.1 Simular rede (menu lateral)

| Aspecto | O que faz |
|---------|-----------|
| Onde | Menu **Simular rede** (`NavegacaoFerramentas`); `web/src/simularRede/SimularRede.jsx`. Sem estudo aberto. |
| Rotas | `GET /api/simular-rede/opcoes`, `/por-hospital`, `/por-plano` (`api/main.py` ~990–1041; `rede_consulta.py`). Somente leitura. |
| Fonte | Aba **`Matriz_Hospital`** do xlsx SiscorNet (`docs/SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx` ou `NEWPORT_REDE_XLSX`). Marcação **principal / rede verticalizada / zona** em `docs/hospitais_principais_base.csv`. Aliases de **regras comerciais** só para nome canônico de operadora nas colunas. **Não** usa `planos_rede_aliases.csv` (as colunas são as da matriz, não as da cotação). |
| Modos | **Por hospital** — “quais planos cobrem estes nomes?”. **Por plano** — “onde este plano da matriz atende?”. |
| Filtros | UF → município → zona (encadeados, opções da base inteira). Modo hospital: busca por nome (vários termos `;` / vírgula; ignora “Hospital/Hosp”); checkboxes de **operadora** para reduzir colunas. Modo plano: select operadora → plano (todas as colunas SiscorNet). Checkbox **Ver todos os prestadores** (padrão: só principais). Sem filtro de tipo H/M/PS (só exibição). Sem filtro de laboratório. |
| Colunas | Prestador (sigla de zona em SP/RJ + nome + bairro + selos “Rede própria” / “Não principal”). Depois **uma coluna por plano da matriz** que tiver cobertura naquele resultado (modo hospital) ou **uma** coluna (modo plano). Códigos H / HD / M / PS. |
| Totais | `total_linhas`, `total_encontrado`, `ocultos_nao_principais`; contagem por bloco de município; data da base (`mtime` do xlsx). Modo plano sem geo e >100 visíveis: **não lista** até confirmar. |
| Busca texto | Sim, núcleo da consulta hospitalar (`termos_de_busca` + tokens no nome e bairro). |
| Comparar vários planos | **Sim** no modo hospital (todas as operadoras, ou um subconjunto). Modo plano = 1 coluna. |
| Inclusão manual | **Não.** Não há rascunho. |
| Exportar / imprimir | **Não.** Tela de consulta; print do browser não é entregável. |
| Limitações | Padrão só **principais** (~391 de 1.071). Sem recorte por beneficiário (o corretor escolhe a geografia). Sem aba **Matriz_Laboratorio**. Sem casamento cotação↔coluna (plano = rótulo SiscorNet). Cobertura por célula ainda exige HGER/HD/PSGER/MAT (`_coberto_na_coluna`); linha sem isso aparece vazia. |

### 1.2 Etapa 5 do estudo (tela + busca de inclusão + HTML)

| Aspecto | O que faz |
|---------|-----------|
| Onde | Passo **Rede credenciada** do wizard (`RedeSelecaoPanel.jsx`). Persistência `PUT /api/estudos/{id}/rede-selecao`. Inclusão `GET …/rede-selecao/busca`, `POST …/incluidos` e `…/incluidos/remover`. Documento: aba **Rede credenciada** (`rede_renderer.py` + `html_renderer.py` `#tab-rede`). |
| Fonte | **Mesmo** xlsx + `hospitais_principais_base.csv`. **Mais** `docs/planos_rede_aliases.csv` (e regra automática `casamento_rede.py`) para casar plano do **estudo** com coluna da matriz. Recorte: UF+cidade das **vidas incluídas** (`rede_recorte.py`, `MUNICIPIO_E_CAPITAL_UF`). |
| Filtros na tela | **Zona**, **município** e **busca por nome** — só sobre as linhas **já na tabela** (principais do recorte + manuais). Sem select de UF (a geografia veio das vidas). Sem “ver todos”. Sem filtro H/M/PS. Sem laboratório. |
| Colunas | Checkbox Incl.; Prestador (mesmo rótulo/bairro/sigla); **Contrato atual** + propostas do cenário (nomes via `nome_plano_documento`). Seção **por subgrupo**. Plano sem casamento: “Rede não mapeada”. |
| Totais | `{incluídos} de {linhas}` no cabeçalho; “N de M visíveis” nos filtros; HTML: “N prestadores” por bloco + linha **Cobertos** por coluna. Funil interno: base → geo → especialidade (`VisaoRedeEstudo`). |
| Busca texto | (a) Filtro da tabela: `includes` em minúsculas no nome, só linhas já listadas. (b) Inclusão: **base inteira**, sem recorte e sem especialidade, ≥2 letras, máx. 30 hits — **reusa** `termos_de_busca` do Simular (`rede_inclusao.py`). |
| Comparar vários planos | **Sim**, mas só os do **estudo** (atual + propostas atribuídas), não o catálogo SiscorNet. |
| Inclusão manual | **Sim** — hospital fora dos principais; selos «Manual» / «Fora do critério padrão» só na tela; no HTML vira linha comum. |
| Exportar / imprimir | HTML autocontido (impressão do documento; thead sticky / cabeçalho repetido). Tela da etapa 5 **não** exporta CSV/xlsx. |
| Limitações | Só **principais** do recorte, salvo inclusão. Sem UF/cidade nas vidas → tabela vazia + aviso. Sem `planos_rede` → coluna “não mapeada”. Laboratório não entra. Recorte provisório (Wesley). Porto Medservice fora de SP/RJ/DF: rodapé do HTML avisa cobertura vazia. |

---

## 2. Tabela comparativa

Legenda: **sim** / **não** / **parcial**.

| Funcionalidade | Simular rede | Etapa 5 (tela) | HTML entregável | Observação |
|----------------|:------------:|:--------------:|:---------------:|------------|
| Sem abrir estudo | **sim** | não | — | Propósito do Simular |
| Grava seleção no estudo | não | **sim** (`excluidos` / `incluidos`) | lê a seleção | HTML **remove** desmarcados do DOM |
| SiscorNet `Matriz_Hospital` | **sim** | **sim** | **sim** | Mesmo cache |
| `Matriz_Laboratorio` | não | não | não | Fase posterior (`rede_siscor_README.md`) |
| CSV principais | **sim** | **sim** | **sim** | |
| `planos_rede_aliases.csv` | **não** | **sim** | **sim** | Simular usa colunas cruas da matriz |
| Recorte por beneficiário (município + capital) | **não** | **sim** | **sim** | Simular: filtro explícito UF/mun/zona |
| Filtro UF | **sim** | não | não | Etapa 5: UF só via vidas |
| Filtro município | **sim** (base inteira) | **sim** (só linhas da tabela) | não (documento estático) | Universos diferentes |
| Filtro zona | **sim** (base) | **sim** (tabela) | não | |
| Filtro operadora (colunas) | **sim** (modo hospital) | não | não | Etapa 5: colunas = estudo |
| Escolher 1 plano do **catálogo** SiscorNet | **sim** (modo plano) | não | não | |
| Comparar **vários** planos lado a lado | **sim** (hospital = todos da matriz) | **sim** (só estudo) | **sim** (estudo; fatias se muitas propostas) | |
| Busca por nome de hospital | **sim** (consulta) | **parcial** (filtro local + inclusão) | não | Algoritmo da inclusão = o do Simular |
| Vários nomes na mesma busca (`Einstein; Sírio`) | **sim** | **parcial** (só na inclusão) | não | Filtro da tabela é um `includes` |
| Filtro tipo H / HD / M / PS | não (só legenda) | não (só células) | não | Etapa 5 **exclui da lista** quem não tem esses códigos em nenhuma célula |
| Ver não-principais em lote | **sim** («Ver todos») | não | não | Etapa 5: um a um via inclusão |
| Inclusão manual pontual | não | **sim** | linha entra | |
| Marcar/desmarcar para o cliente | não | **sim** | efeito permanente | |
| Seções por subgrupo / contrato atual | não | **sim** | **sim** | |
| Plano sem mapeamento | n/a | **sim** (aviso na coluna) | **sim** | |
| Aviso sem localização | n/a | **sim** | **sim** | |
| Rede verticalizada (selos/aviso) | **sim** | **parcial** (cobertura) | rodapé | Mesma regra `_coberto_na_coluna` |
| Contagem «Cobertos» por coluna | não | não na tela | **sim** | |
| Confirmação se volume >100 sem geo | **sim** (modo plano) | n/a | n/a | Recorte da etapa 5 já limita |
| Data da base na UI | **sim** | não | **sim** (rodapé) | |
| Exportação / PDF / CSV | não | não | **imprimir HTML** | |
| Persistência / snapshot | não | **sim** | gerado do snapshot | |

### O que o Simular cobre e a Etapa 5 **não** cobre

- Consulta **fora do estudo** (conversa com o cliente antes de montar o comparativo).
- Catálogo **completo** de planos da matriz (não só os cotados).
- Modo **por hospital** com dezenas de colunas de operadoras ao mesmo tempo.
- Filtro **UF** e geografia da **base nacional**, sem depender de SISCOR.
- **Ver todos** os 1.071 (não só principais), com um clique.
- Confirmação de volume alto.
- Data da planilha no cabeçalho da tela.

### O que a Etapa 5 cobre e o Simular **não** cobre

- Recorte automático pelas **vidas** (município + capital da UF).
- Casamento cotação ↔ coluna (`planos_rede_aliases` + regra).
- Coluna **contrato atual** vs propostas; seções por **subgrupo**.
- Seleção persistida (incluir/excluir) e **HTML** para o cliente.
- **Inclusão manual** de um hospital pedido pelo cliente.
- Avisos de **sem localização** e **rede não mapeada**.
- Linha **Cobertos**, paginação de propostas, pontos de atenção (Porto/Medservice).
- Selos Manual / Fora do critério (tela).

---

## 3. Trazer o que só o Simular tem para a Etapa 5

| Item só no Simular | Reaproveitar? | Esforço | Nota |
|--------------------|---------------|---------|------|
| Filtro **UF** na tabela da etapa 5 | **Fácil** — mesmo padrão de zona/município em `filtrarLinhasRede` | 2–4 h | Só filtra o que já está no recorte; não amplia geografia |
| Geografia encadeada da **base inteira** (UF→mun→zona nacionais) | Trabalho **novo** de produto | 8–16 h | Mistura recorte das vidas com “olhar o Brasil”; risco de contradizer o recorte Wesley |
| «Ver todos» (não-principais em lote) | **Parcial** — `montar_visao_rede_estudo` já tem `principal=False`; a montagem **pula** esses (`rede_apresentacao.py:322`) | 8–12 h | Alternativa já existe: inclusão. «Ver todos» infla o HTML |
| Busca da tabela com `termos_de_busca` (acento, vários nomes) | **Fácil** — função já importável; hoje o filtro é `includes` | 3–6 h | |
| Checkboxes de **operadora** para esconder colunas | **Fácil** na UI | 4–6 h | Não muda o documento a menos que a seleção de colunas entre no snapshot |
| Modo **por hospital** (todas as colunas SiscorNet) | Trabalho **novo** | 16–24 h | Endpoint `por-hospital` reutilizável; a etapa 5 deixaria de ser “estudo” e viraria o Simular embutido |
| Modo **por plano** do catálogo SiscorNet | Trabalho **novo** | 12–20 h | Idem; pouco sentido *dentro* de um estudo que já tem planos escolhidos |
| Confirmação >100 sem geo | **Não necessário** | 0 | Recorte das vidas já corta |
| Data da base no cabeçalho da etapa 5 | **Fácil** — `_data_base_rede()` / `opcoes_simulacao` | 1–2 h | HTML já mostra no rodapé |
| Exportar/imprimir a consulta do Simular | Trabalho **novo** | 8–16 h | Ou “mandar para o estudo” (inclusão em lote) |

**Já compartilhado (não duplicar):** cache da matriz, CSV de principais, `_coberto_na_coluna`, códigos H/HD/M/PS, rótulo de prestador, `termos_de_busca` na **inclusão**.

---

## 4. Inconsistências entre as duas

1. **Recorte geográfico.** Etapa 5/HTML: município da vida **mais a capital da UF** (`CRITERIO_RECORTE_GEOGRAFICO`, pendência Wesley). Simular: só o que o corretor marcou — UF “RJ” **não** inclui automaticamente a capital se o filtro for outro município. O mesmo cliente em Niterói vê **Rio** na etapa 5 e **não** no Simular se filtrar só Niterói.

2. **Quem entra na lista.** Etapa 5: especialidade (HGER/HD/PSGER/MAT em **alguma** célula) **e** `principal=sim`, depois omite linha sem cobertura na seção. Simular: nome+geo; principais por padrão; **não** descarta o prestador por especialidade — célula vazia. Hospital “não principal” ou sem aqueles códigos: no Simular com «Ver todos» aparece; na etapa 5 só se for inclusão manual.

3. **Nome do plano.** Simular: `rotulo_completo` da coluna SiscorNet. Etapa 5/HTML: nome da cotação passado por `nome_plano_documento` (tira acomodação/abrangência). O **mesmo** produto pode chamar-se “PRATA AO PLATINUM S750…” num lado e “S750” no outro.

4. **Conjunto de colunas.** Simular hospital = todas as colunas da matriz (dezenas). Etapa 5 = 1 atual + N propostas. Comparar “Amil vs Porto vs SulAmérica” no Simular **não** é o mesmo recorte da Anistia na etapa 5.

5. **Identidade da linha.** Simular: `l{linha_idx}` da planilha. Etapa 5: SHA-256 curto de subgrupo+prestador+município+bairro. O mesmo hospital **não** compartilha id entre as telas.

6. **Busca.** Simular/inclusão: normaliza acento, ignora “Hospital”, vários termos. Filtro da tabela etapa 5: substring ASCII-ish (`toLowerCase().includes`). “Sírio” vs “Sirio” pode divergir no filtro local, não na inclusão.

7. **Zona.** Mesma origem (CSV principais, senão `região` da matriz). Selects do Simular listam zonas da **base**; etapa 5 só zonas **já presentes nas linhas do recorte**.

8. **Laboratório.** Nenhuma das duas lê `Matriz_Laboratorio` — se o corretor espera “lab” nas duas, as duas falham igual.

9. **Porto / Medservice.** O aviso está no **rodapé do HTML**, não no Simular nem na etapa 5. Consulta Porto fora de SP/RJ/DF no Simular pode parecer “sem cobertura” sem explicação.

10. **Documento vs tela etapa 5.** Inclusão manual: selos só na tela; HTML iguala às outras linhas. Simular não entra no HTML.

---

## Fontes

`rede_consulta.py`, `simular_rede.py`, `SimularRede.jsx`, `opcoesSimulacao.js`, `RedeSelecaoPanel.jsx`, `redeSelecaoFiltros.js`, `InclusaoManual.jsx`, `rede_inclusao.py`, `rede_selecao_ui.py`, `rede_visao.py`, `rede_recorte.py`, `rede_especialidade.py`, `rede_apresentacao.py`, `rede_renderer.py`, `html_renderer.py`, `api/main.py`, `api.js`, `docs/rede_siscor_README.md`, `planos_rede_README.md`, `hospitais_principais_README.md`, `REGISTRO-TECNICO-ALTERACOES.md` (entregas 4 e 5).
