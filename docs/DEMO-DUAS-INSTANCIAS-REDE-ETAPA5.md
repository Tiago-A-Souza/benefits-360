# Demonstração lado a lado — master (sandbox HTML) × rede-etapa5-alternativa

## Master (intocada) — portas **5173** / **8002**

```powershell
cd C:\np
git checkout master
$env:NEWPORT_MODO = "demo"
.\.venv\Scripts\python.exe -m uvicorn newport_app.api.main:app --reload --port 8002
```

Outro terminal:

```powershell
cd C:\np\web
npm run dev
```

Abrir **http://localhost:5173** — etapa 5 = Comparativo; aba Rede no HTML com sandbox e download `_para_cliente`.

## Alternativa (branch `rede-etapa5-alternativa`) — portas **5174** / **8003**

Copie o banco demo **uma vez** (evita gravar `selecao_rede` no mesmo arquivo da master):

```powershell
cd C:\np
git checkout rede-etapa5-alternativa
New-Item -ItemType Directory -Force -Path .\.data\demo-etapa5-alt | Out-Null
Copy-Item .\.data\estudos_demo.db .\.data\demo-etapa5-alt\estudos_demo.db -Force
$env:NEWPORT_MODO = "demo"
$env:NEWPORT_DATA_DIR = (Resolve-Path .\.data\demo-etapa5-alt).Path
.\.venv\Scripts\python.exe -m uvicorn newport_app.api.main:app --reload --port 8003
```

Outro terminal:

```powershell
cd C:\np\web
npm run dev:alt
```

Abrir **http://localhost:5174** — etapa 5 = Rede credenciada; etapa 6 = Comparativo e exportação; documento gerado **sem** sandbox na aba Rede.

## Prova de origem

| URL | Branch | API | Banco |
|-----|--------|-----|-------|
| localhost:5173 | `master` | 8002 | `.data/` padrão |
| localhost:5174 | `rede-etapa5-alternativa` | 8003 | `NEWPORT_DATA_DIR` → cópia |
