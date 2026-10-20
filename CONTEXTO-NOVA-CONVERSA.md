> Cole este documento no início de uma nova conversa. Ele carrega todo o
> contexto necessário para continuar o trabalho sem repetir o histórico.

---

# CONTEXTO — Sistema de Estudos Newport

## Quem sou e o que preciso

Sou **Tiago**, da Turya. Trabalho no **Newport-Sistema-Estudos**, plataforma
que gera estudos comparativos de planos de saúde para clientes corporativos da
**Newport Consultoria de Benefícios** (design partner do produto).

Não sou desenvolvedor. Uso o **Cursor AI** para implementar correções, a partir
de prompts prontos que preciso apenas colar. Meu chefe é **Leonardo Brunetti**.

**Como preciso ser ajudado:** prompts consolidados em bloco único, prontos para
colar no Cursor. Documentos em `.md`. Sem rodeios.

---

## Como o assistente pode validar de verdade

O projeto pode ser enviado como zip e descompactado no container. Comandos que
funcionam:

```
pip install --break-system-packages pydantic pytest httpx fastapi \
  "uvicorn[standard]" openpyxl python-multipart pdfplumber pymupdf pypdf
python3 -m pytest -q
```

Para invocar o motor direto, sem FastAPI:

```python
import sys; sys.path.insert(0, "src")
from newport_motor.engine import calcular
```

**Isso foi decisivo.** Vários defeitos só apareceram rodando os parsers contra
os PDFs reais e comparando com os estudos entregues aos clientes.

**Cuidado com o zip:** use `git archive --format=zip -o fonte.zip HEAD`, que
filtra pelo `.gitignore`. Um envio anterior incluiu `.private/` com PDFs reais
de cliente.

---

## Arquitetura em uma página

**Um motor só.** `calcular(estudo, policy) → resultado`, função pura, idêntica
para todas as operadoras e todos os estudos.

```
idade na data de referência  →  faixa etária ANS (0 a 9)
faixa                        →  valor na tabela do plano
tipo fiscal seguradora       →  IOF de 2,38%
formato renovação            →  reajuste, aplicado vida a vida
soma                         →  vida → subgrupo → seção → cenário
```

**Regras:** dinheiro sempre em centavos inteiros, nunca float. Taxas em basis
points (IOF = 238). Arredondamento half-up. Estratégia homologada
`por_vida_entao_soma` — aplica por vida e depois soma; aplicar sobre o total dá
resultado diferente (3 centavos na Anistia).

**O que varia por operadora** não é o cálculo, são dois campos de declaração:

| Campo | Pergunta |
|---|---|
| Tipo fiscal | esta operadora recolhe IOF? |
| Base de preço | o IOF já está dentro do número impresso? |

| Operadora | Tipo fiscal |
|---|---|
| Amil, Hapvida, Unimed, NotreDame | operadora — sem IOF |
| Porto, SulAmérica, Bradesco | seguradora — IOF 2,38% |

**Parsers de PDF** são específicos por operadora (12 famílias de template).
Só extraem números; depois todos entregam a mesma estrutura tipada.

**Camadas relevantes:**

| Arquivo | Papel |
|---|---|
| `src/newport_motor/` | motor puro — **validado, não alterar** |
| `adapters/motor_out.py` | resultado → tela do comparativo (etapa 5) |
| `presentation/builder.py` | resultado → HTML |
| `cotacao_pdf/parsers/` | amil, porto, sulamerica, omint, bradesco |
| `siscor_importer/` | importação da planilha de posição cadastral |
| `web/src/PlanosSelecionadosPanel.jsx` | matriz cenário × subgrupo (etapa 4) |
| `web/src/ConfigEstudo.jsx` | etapa 2 |
| `web/src/constants.js` | rótulos dos dropdowns |

---

## Estado atual

**20/10/2026 — `master` em `4a87368`, tag `selecao-rede-no-sistema`.** Merge da
`rede-etapa5-alternativa`: **seis etapas** (Rede credenciada na 5ª, comparativo e
exportação na 6ª); seleção grava **exclusões** no rascunho; HTML completo **sem**
sandbox na aba Rede (`rede_entrega_cliente=True`). Código do sandbox D2 **ainda no
repo**, morto no export — remoção em entrega dedicada.

pytest: **1463 passed, 16 skipped** (~7 min 35 s). Playwright etapa 5 + rede D2 legado:
**20 passed**. vitest: **136 passed**. `npm run build`: ok. Snapshots demo:
**107/107** hashes iguais (`HASH_DIVERGENTE=0`). `SNAPSHOT_VERSAO`: **2.8.0**
(campo `selecao_rede` no rascunho, como `selecao_apresentacao`). Rascunhos demo:
**109** carregam, **80** compilam. Harness: **16/16** mutações detectadas.

**Instância única:** Vite **5173** + API **8002**, `NEWPORT_DATA_DIR=C:\np\.data`.
Encerrar 5174/8003 e worktree de demo lado a lado quando não for comparar branches.

**Próximas entregas (2–4):** colunas de planos na etapa 5; remover sandbox do HTML;
Simular Rede na home.

Tags recentes: **`selecao-rede-no-sistema`**, `sandbox-rede`, `rede-fase-d1`.
Branch `rede-etapa5-alternativa` preservada (não apagar).

**Ainda aberto (§12):** validade da cotação em cenário misto; confirmações
Wesley (regras comerciais e **recorte geográfico da rede** — prática Newport
vs. «município + capital»); demais itens do §12 no registro técnico.

**22 defeitos** da validação com dados reais permanecem o histórico; o motor
financeiro (IOF, half-up, `por_vida_entao_soma`) não foi alterado.

**Ata de 16/08:** ajustes 1–3 concluídos. O ajuste 4 (seleção par a par) foi
implementado pelas sete fases: `cenario.atribuicoes` passa a ser a grade, a
etapa 4 e o documento.

### Três estudos reproduzidos ao centavo contra o que a Newport entregou

**ATEF** — 3 vidas, renovação, Porto e SulAmérica

| Item | Estudo entregue | Sistema |
|---|---|---|
| Total reajustado (11,98%) | R$ 2.387 | R$ 2.387,45 |
| Porto P220 Q COPAR | R$ 1.365 | R$ 1.365,09 |
| Economia anual | R$ 12.268 | R$ 12.268,32 |

**Anistia** — 41 vidas, **2 planos vigentes**, Porto + 2 SulAmérica

| Item | Valor |
|---|---|
| Vigente total | R$ 43.285,14 |
| Reajustado (10%) | **R$ 47.613,62** |
| AMIL S750 (36 vidas) | R$ 26.238,22 → **R$ 28.862,01** |
| AMIL ONE S2500 (5 vidas) | R$ 17.046,92 → **R$ 18.751,61** |
| Porto OURO MAIS I Q | R$ 42.222,37 |
| SulAmérica Especial 100 R1 | R$ 29.697,36 |
| SulAmérica Especial Vital RC | R$ 26.661,31 |
| Porto OURO MAIS I Q COPAR 30 | R$ 34.622,37 |

**IVTEC** — 12 vidas, **seguro novo** (sem plano vigente), Amil

| Item | Estudo entregue | Sistema |
|---|---|---|
| Amil Bronze SP + TP | R$ 3.741,89 | R$ 3.741,89 |
| Amil Prata TP | R$ 5.652,04 | R$ 5.652,04 |

**Validação independente:** no Anistia o sistema calculou o Porto
P320 Q COPAR em R$ 1.500,82 — exatamente o valor que a Porto imprime no
resumo da própria cotação.

---

## Invariantes estabelecidos

Regras que impedem classes de erro. Devem ser preservadas em qualquer
alteração futura.

1. **O total é sempre a soma de todos os valores conhecidos.** Homogeneidade
   de valores numa faixa decide apenas se dá para exibir valor unitário —
   nunca se a faixa entra no total.

2. **Nenhum campo que altere valor calculado recebe valor por omissão.** Se
   não pode ser extraído com segurança, fica ausente e o operador declara.

3. **Todo valor exibido vem do motor** ou é soma direta de valores importados.
   A camada de exibição não aplica taxas nem arredondamentos próprios.

4. **Quando o cálculo não produz resultado, a interface mostra por quê** — com
   código, mensagem e alvo. Nunca só uma contagem.

5. **Nenhum identificador interno (UUID) aparece em texto lido por humano.**

6. **Se a aplicação considera um rascunho sincronizado, o motor não pode
   devolver bloqueio estrutural.** Divergência entre as duas validações é
   defeito.

7. **A matriz comparativa e o documento gerado apresentam o mesmo conteúdo.**
   Divergência entre camadas é defeito.

8. **Valores de tabela por faixa etária são não decrescentes** — regra da ANS.
   Violação gera alerta em qualquer parser.

9. **Nenhum documento é gerado sem cálculo congelado e atestado de revisão.**

---

## Defeitos corrigidos — para não reintroduzir

### Produziam valor errado, em silêncio

| Defeito | Impacto medido |
|---|---|
| Base descartava faixas com valores heterogêneos | 14 de 36 vidas fora do total (Anistia) — R$ 9.183,23 |
| Amil truncava valores ≥ R$ 1.000 (regex exigia ponto de milhar) | R$ 1.000/mês no IVTEC; 7 de 10 faixas corrompidas no BLACK |
| Tipo fiscal assumia «seguradora» por omissão | toda cotação de operadora inflada em 2,38% |
| Porto: série «P» descartada | 14 planos/documento, incluindo o P220 vendido ao ATEF |
| SulAmérica: anotação «1 vida» entre valores quebrava o parser | duas famílias de layout com zero planos |
| Total «observado» exibia valor reajustado | rótulo enganoso + cálculo fora do motor |

- Matriz comparativa atribuindo o total consolidado dos planos vigentes ao nome
  do primeiro deles, com o segundo contrato invisível

### Bloqueavam trabalho

- Estudos com 2+ planos vigentes nunca calculavam (B-06 inevitável) →
  corrigido com matriz cenário × subgrupo
- Seguro novo não tinha jornada → corrigido: escolha de formato, isenção de
  valor de fatura, etapa 2 reduzida, atribuição por vida
- Upload em lote abortava no primeiro erro
- Extração vazia era beco sem saída (sem entrada manual)
- Amil: linhas de subtotal oferecidas como plano selecionável
- Amil: nome do plano capturado de texto institucional («mais»)

### Governança

**A trava de confirmação humana estava desativada** — uma sessão anterior de
IA trocou `confirmado = bool(campo.confirmado)` por `confirmado = aceito`, e
havia um teste consagrando o bypass. Restaurada; a confirmação ocorre pela
seleção consciente do plano.

**741 linhas não commitadas** de sessões anteriores foram auditadas e
organizadas em sete commits.

---

## Lições de processo — importantes

**Sempre commitar antes e depois de cada tarefa.** O Cursor não commita
sozinho. Foi assim que nasceram as 741 linhas órfãs.

**Verificar se o uvicorn antigo morreu.** Servidor na porta 8002 de sessão
anterior serve código velho. Custou horas de confusão.

```powershell
Get-NetTCPConnection -LocalPort 8002 -State Listen
```

**Rebuild do frontend** após mudança em `.jsx`:

```powershell
cd web; npm run build; cd ..
```

**Cole isto no fim de cada prompt ao Cursor:**

```markdown
## AO TERMINAR — obrigatório
1. Rode a suíte completa. Informe o número exato de testes passando.
2. Se houver mais falhas do que antes: pare, não commite, e relate.
3. Se tudo passar, commite com mensagem descritiva. Um commit por assunto.
4. Rode `git status` e mostre o resultado. Explique o que sobrou.
5. Liste o que encontrou e NÃO consertou por estar fora do escopo, com
   arquivo:linha.
```

**Três padrões que se repetiram:**

- Correção entra numa camada e não na outra (`builder.py` sim, `motor_out.py`
  não). Sempre pedir teste de paridade.
- Testes que consagram o defeito. Apareceu três vezes. Ao corrigir, verificar
  se algum teste protegia o comportamento errado.
- O sistema tinha a informação e não comunicava. Vale para quase todos os 22
  defeitos.
- **Correção de apresentação exige teste de paridade entre as duas camadas.**
  Três correções da seção 8 do registro constavam como concluídas e existiam
  apenas no `builder.py`. `motor_out.py` e `builder.py` chegam aos mesmos
  números por caminhos diferentes; teste que chame a mesma função duas vezes não
  prova paridade.
- **Teste de payload não prova que a tela mudou.** As correções 8.8 e 8.9
  passaram em todos os testes com o JSX ainda exibindo o comportamento antigo,
  porque a suíte verifica o payload e não há teste de tela. Validação visual em
  `localhost:5173` é obrigatória para toda alteração de renderização.
- **Só a porta 5173 serve o código da branch.** A 5174 aponta para uma cópia de
  `web/src` fora do repositório e a 8002 serve um `dist` desatualizado, porque
  `npm run build` falha no caminho longo — o rollup recusa caminho absoluto.
  Validar em qualquer outra porta mostra código antigo.

---

## O QUE FAZER AGORA

A apresentação à Newport aconteceu em 17/08 com a versão validada. Estes são
os ajustes pedidos pelo Leonardo na ata de 16/08.

### Situação dos quatro ajustes prioritários

| # | Ajuste | Situação |
|---|---|---|
| 1 | Eliminar etapa 6, exportar da etapa 5 | **concluído** (fases 1 e 2) |
| 2 | Simplificar etapa 2 removendo dois campos | **concluído** |
| 3 | Incluir o segundo plano no comparativo | **concluído** |
| 4 | Seleção par a par plano × cotação | **aguarda definição do Leonardo** |

### Ajuste 1 — concluído em duas fases

**Fase 1 — paridade da matriz.** Concluída e validada visualmente nas três visões
da matriz contra o documento gerado.

**Fase 2 — unificar a exportação.** Concluída: snapshot no «Confirmar
comparativo», aprovação na etapa 5, exportação a partir do comparativo
congelado, três modos de apresentação (resumo, faixas, beneficiário).

**Três testes que devem falhar:**
- exportar sem aprovar → recusado (B-01)
- aprovar sem marcar o atestado → recusado
- alterar o rascunho e exportar do snapshot antigo → invalidado

### Ajuste 2 — concluído

A caixa «Origem dos valores atuais» saiu da etapa 2; o campo permanece no
modelo com gravação explícita. O campo «valor informado já inclui IOF» saiu da
interface; `BASES_IOF` na cotação manual ficou com duas opções. Ver seção 8.12
do registro técnico.

## Correções à ata de 16/08

Três imprecisões que valem registrar:

**O motor de cálculo nunca esteve errado.** A ata diz que o truncamento
corrompia «tanto a fórmula quanto a extração». Era só a extração — uma regex no
parser da Amil. O motor não foi alterado em nenhuma das 22 correções.

**O alerta de 41 vidas não tem relação com o segundo plano.** O H-01 avisa que
o estudo excede a faixa comercial homologada de 29 vidas. É configurável e
continua aparecendo depois do ajuste 3. Vale perguntar à Newport se 29 é o
número certo.

**O Bradesco não precisa de OCR.** É PDF de texto (3.222 caracteres
extraíveis, tabela legível, com totais de conferência: 47 vidas, prêmio
R$ 18.963,32, IOF R$ 451,33, total R$ 19.414,65). O parser existe em
`parsers/bradesco.py` mas **nunca foi registrado** em `FAMILIAS`
(`template_families.py:78-210`). É correção de horas.

---

## Backlog restante

| Item | Efeito |
|---|---|
| Registrar parser Bradesco em `FAMILIAS` | conclui IVTEC e Lunvox |
| Deduplicar planos idênticos entre documentos | elimina colunas repetidas |
| Acomodação ausente não gera aviso | alerta de divergência não dispara |
| Revisar tipo fiscal gravado antes da correção | dado legado |
| Etapa 1 exige plano/seguradora em seguro novo | lista de vidas simples |
| Comparativo em seguro novo | verificar se ficou resolvido |

### Não construído

**Formato misto** — estudo que combina renovação de um grupo com vidas novas
em outro. Caso EVOPE: 9 sócios em renovação (dois planos Bradesco distintos) +
22 colaboradores novos. O modelo admite um formato por estudo. Requer decisão
de produto.

**Fora do escopo do software** — rede credenciada, reembolso, procedimentos
reembolsáveis, odonto, seguro de vida, carências, condições contratuais. A
saída é HTML, não PowerPoint. Roadmap: comparativo de rede credenciada é o
bloco seguinte, a ser unificado no HTML em abas.

---

## Arquivos de referência que eu tenho

| Arquivo | Conteúdo |
|---|---|
| `REGISTRO-TECNICO-ALTERACOES.md` | as 22 correções por camada |
| `RELATORIO-VALIDACAO-NEWPORT.md` | versão executiva |
| `PLANO-ETAPA5-EXPORTACAO.md` | plano em duas fases com prompts |
| `ROTEIRO-COMPLETO-ANISTIA.md` | teste campo a campo |
| `ROTEIRO-COMPLETO-IVTEC.md` | teste campo a campo |
| `POSICAO_CADASTRAL_IVTEC_TESTE.xlsx` | base de 12 vidas, valor zerado |
| `POSICAO_CADASTRAL_LUNVOX_TESTE.xlsx` | base de 47 vidas, 3 subgrupos |

Posso enviá-los quando forem úteis.

---

## Meu pedido para esta conversa

Quero implementar os ajustes da ata, começando pela **fase 1 do ajuste 1** — a
paridade da matriz comparativa.

Preciso de prompts prontos para colar no Cursor, e da validação dos resultados
contra os valores esperados acima.
