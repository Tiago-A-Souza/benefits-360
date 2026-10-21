# Demonstração lado a lado — master (sandbox HTML) × rede-etapa5-alternativa

Duas instâncias **ao mesmo tempo**: código da `master` num **worktree** separado; branch `rede-etapa5-alternativa` no clone principal (`C:\np`). **Não** use `git checkout` para alternar — isso impede rodar as duas juntas e, pior, se você subir API e Vite da “master” e da “alternativa” **a partir da mesma pasta** (`C:\np\web`), **as duas URLs usam o mesmo código**: o que estiver checked out no clone. Na prática a **5173 pode servir a branch alternativa** (6 etapas, etapa Rede) enquanto você acha que está na master. O sintoma que quase aconteceu: comparar sandbox × etapa 5 e ver **as duas UIs iguais**.

| Instância | UI | API | Código | Banco |
|-----------|-----|-----|--------|-------|
| **Master** | 5173 | 8002 | worktree `C:\wt\np-master` | `C:\np\.data\newport_app.db` (original) |
| **Alternativa** | 5174 | 8003 | clone `C:\np` (branch `rede-etapa5-alternativa`) | `C:\np\.data\demo-etapa5-alt\newport_app.db` (cópia via VACUUM INTO) |

Modo demo: `NEWPORT_MODO=demo`. O app usa **`newport_app.db`** em `NEWPORT_DATA_DIR` (padrão: `.data/` do repositório em uso).

---

## Preparação (uma vez)

Worktree da master em caminho **curto** (evita “Filename too long” no Windows):

```powershell
cd C:\np
git worktree add C:\wt\np-master master
```

Cópia do banco da alternativa (evita gravar `selecao_rede` no mesmo arquivo da master):

**Não use `Copy-Item` no `.db` bruto.** Cópia de arquivo preserva fragmentação e estatísticas desatualizadas; na prática a listagem `GET /api/estudos` na 8003 ficou ~2× mais lenta que a master com o mesmo código. Use **`VACUUM INTO`** (reconstrói o arquivo e índices) e depois **`ANALYZE`**.

```powershell
# Derrube a API 8003 antes, se estiver usando demo-etapa5-alt.
New-Item -ItemType Directory -Force -Path C:\np\.data\demo-etapa5-alt | Out-Null
Remove-Item -Force -ErrorAction SilentlyContinue C:\np\.data\demo-etapa5-alt\newport_app.db*

C:\np\.venv\Scripts\python.exe -c @"
import sqlite3
src = r'C:\np\.data\newport_app.db'
dst = r'C:\np\.data\demo-etapa5-alt\newport_app.db'
with sqlite3.connect(src) as c:
    c.execute('VACUUM INTO ?', (dst,))
with sqlite3.connect(dst) as c:
    c.execute('ANALYZE')
    c.commit()
print('demo-etapa5-alt: VACUUM INTO + ANALYZE ok')
"@
```

Equivalente com `sqlite3` no PATH:

```powershell
sqlite3 C:\np\.data\newport_app.db "VACUUM INTO 'C:\np\.data\demo-etapa5-alt\newport_app.db'"
sqlite3 C:\np\.data\demo-etapa5-alt\newport_app.db "ANALYZE;"
```

Atalho (mesma lógica): `C:\np\.venv\Scripts\python.exe C:\np\scripts\recriar_demo_etapa5_alt_db.py` — derrube a 8003 antes.

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

Abrir **http://127.0.0.1:5173** — fluxo completo com etapa **Rede credenciada**; documento exportado **estático** (zero JavaScript), nome `apresentacao_completo_*.html`.

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
