# Demonstração lado a lado — master (sandbox HTML) × rede-etapa5-alternativa

Duas instâncias **ao mesmo tempo**: código da `master` num **worktree** separado; branch `rede-etapa5-alternativa` no clone principal (`C:\np`). **Não** use `git checkout` para alternar — isso impede rodar as duas juntas e, pior, se você subir API e Vite da “master” e da “alternativa” **a partir da mesma pasta** (`C:\np\web`), **as duas URLs usam o mesmo código**: o que estiver checked out no clone. Na prática a **5173 pode servir a branch alternativa** (6 etapas, etapa Rede) enquanto você acha que está na master. O sintoma que quase aconteceu: comparar sandbox × etapa 5 e ver **as duas UIs iguais**.

| Instância | UI | API | Código | Banco |
|-----------|-----|-----|--------|-------|
| **Master** | 5173 | 8002 | worktree `C:\wt\np-master` | `C:\np\.data\newport_app.db` (original) |
| **Alternativa** | 5174 | 8003 | clone `C:\np` (branch `rede-etapa5-alternativa`) | `C:\np\.data\demo-etapa5-alt\newport_app.db` (cópia) |

Modo demo: `NEWPORT_MODO=demo`. O app usa **`newport_app.db`** em `NEWPORT_DATA_DIR` (padrão: `.data/` do repositório em uso).

---

## Preparação (uma vez)

Worktree da master em caminho **curto** (evita “Filename too long” no Windows):

```powershell
cd C:\np
git worktree add C:\wt\np-master master
```

Cópia do banco da alternativa (evita gravar `selecao_rede` no mesmo arquivo da master):

```powershell
New-Item -ItemType Directory -Force -Path C:\np\.data\demo-etapa5-alt | Out-Null
Copy-Item C:\np\.data\newport_app.db C:\np\.data\demo-etapa5-alt\newport_app.db -Force
```

Junção do `node_modules` no worktree (Vite da master roda em `C:\wt\np-master\web`):

```powershell
if (-not (Test-Path C:\wt\np-master\web\node_modules)) {
  New-Item -ItemType Junction -Path C:\wt\np-master\web\node_modules -Target C:\np\web\node_modules | Out-Null
}
```

Use o mesmo venv do clone principal, por exemplo `C:\np\.venv\Scripts\python.exe`.

---

## Subir — um comando por instância

Cada linha abre **duas** janelas PowerShell (API + Vite).

**Master (5173 + 8002, banco original):**

```powershell
Start-Process powershell -ArgumentList '-NoExit','-Command','cd C:\wt\np-master; $env:NEWPORT_MODO=''demo''; $env:NEWPORT_DATA_DIR=''C:\np\.data''; C:\np\.venv\Scripts\python.exe -m uvicorn newport_app.api.main:app --reload --host 127.0.0.1 --port 8002'; Start-Process powershell -ArgumentList '-NoExit','-Command','cd C:\wt\np-master\web; npm run dev -- --host 127.0.0.1 --port 5173'
```

Abrir **http://127.0.0.1:5173** — até **5** etapas visíveis (sem etapa Rede no wizard); etapa 5 = Comparativo; HTML da aba Rede **com** sandbox e download `_para_cliente`.

**Alternativa (5174 + 8003, banco copiado):**

```powershell
Start-Process powershell -ArgumentList '-NoExit','-Command','cd C:\np; $env:NEWPORT_MODO=''demo''; $env:NEWPORT_DATA_DIR=''C:\np\.data\demo-etapa5-alt''; C:\np\.venv\Scripts\python.exe -m uvicorn newport_app.api.main:app --reload --host 127.0.0.1 --port 8003'; Start-Process powershell -ArgumentList '-NoExit','-Command','cd C:\np\web; npm run dev:alt'
```

Abrir **http://127.0.0.1:5174** — **6** etapas (Rede na **5ª**); Comparativo e exportação na **6ª**; documento gerado **sem** sandbox na aba Rede.

Proxy Vite: 5173 → 8002; 5174 → 8003 (`web/vite.config.js` e `web/vite.config.alternativa.js`).

---

## Prova rápida de origem

```powershell
(Invoke-WebRequest http://127.0.0.1:5173/src/fluxo/passos.js -UseBasicParsing).Content -match 'chave: "rede"'   # master: False
(Invoke-WebRequest http://127.0.0.1:5174/src/fluxo/passos.js -UseBasicParsing).Content -match 'chave: "rede"'   # alternativa: True
git -C C:\wt\np-master log -1 --oneline
git -C C:\np log -1 --oneline
Resolve-Path C:\np\.data\newport_app.db, C:\np\.data\demo-etapa5-alt\newport_app.db
```

Logs de subida: nas janelas da API/Vite, confira branch e commit (`ORIGIN` / `git log -1`) e `NEWPORT_DATA_DIR\newport_app.db`.
