# Relatório ETAPA 2.1 — Walking skeleton

> UTF-8 · 2026-07-22 · Dados **fictícios** apenas.

---

## 1. Objetivo entregue

Interface web mínima que carrega um estudo fictício de renovação (12 beneficiários), aciona o **motor real** (`newport_motor`, pós-ETAPA 1.2.2) e exibe comparativo financeiro com pendências em linguagem simples.

---

## 2. Componentes

| Camada | Caminho | Função |
|--------|---------|--------|
| UI | `web/` (React + Vite) | Navegador — homologação operacional |
| API | `src/newport_app/api/main.py` | FastAPI enxuto |
| Serviço | `services/calculo.py` | Orquestra repositório → motor → resposta |
| DTO | `models/draft.py`, `models/responses.py` | Formato amigável da aplicação |
| Adaptadores | `adapters/motor_in.py`, `motor_out.py` | Tradução mínima ↔ motor |
| Repositório | `repository/sqlite.py` | SQLite via `StudyRepository` |
| Seed | `seed/ficticio.py` | `demo-12` e `demo-41` fictícios |

**Separação:** rascunho (app) → adaptador → `EstudoInput` + `EffectivePolicy` → `MotorResult` → resposta amigável.

---

## 3. Estudos fictícios pré-carregados

| ID | Beneficiários | Uso |
|----|---------------|-----|
| `demo-12` | 12 | Fluxo principal da demonstração |
| `demo-41` | 41 | Escala + alerta faixa homologada (sem truncamento) |

---

## 4. Como executar

```bash
# Backend (raiz do repositório)
pip install -e ".[app,dev]"
uvicorn newport_app.api.main:app --reload --port 8000

# Frontend (outro terminal)
cd web
npm install
npm run dev
```

Abrir `http://localhost:5173` → selecionar estudo → **Calcular comparativo**.

Produção local (UI servida pelo FastAPI): `npm run build` em `web/` e acessar `http://127.0.0.1:8000`.

Banco SQLite: `.data/newport_app.db` (gitignored).

---

## 5. Testes

```
100 passed
```

| Suíte | Novos |
|-------|-------|
| Motor (93 existentes) | inalterados |
| `test_api_walking_skeleton.py` | 7 testes API/integração |

Inclui: 12 vidas calcula; 41 vidas + H-01 alerta; zero vidas bloqueia; repositório preserva 41 vidas; UI JSON sem termos internos como título.

---

## 6. Fora de escopo (confirmado)

SISCOR, documentos reais, entrada manual de propostas, PDF, snapshot/aprovação, PPTX, auth, Postgres, worker, alterações no motor.

---

## 7. Pendências registradas

| Tema | Quando decidir |
|------|----------------|
| **`quantidade_cotada` vs vidas do plano** | Antes da ETAPA 2.4/2.5 e antes de homologação financeira real |
| Caso dourado financeiro | Ainda pendente (proposta alinhada à população) |
| Confirmação revisor acima da faixa homologada | ETAPA 2.7 (camada app) |

---

## 8. Próximo passo

**ETAPA 2.2** — compilador/mapper único do rascunho (endurecer contrato entre DTO e motor).
