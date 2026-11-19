# Variáveis de ambiente — Benefits 360

Nada disto vai no Git com valor real. Copie `.env.example` → `.env.local` na
máquina local. No Railway, preencha o painel **Variables** (nunca no repositório).
**Nunca** use a chave `service_role` do Supabase.

## Como o front “vê” as variáveis `VITE_`

O Vite **grava** `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY` **no JavaScript
no momento do `npm run build`**. Mudar a variável no Railway **depois** do
deploy **não** atualiza o front: é preciso **gerar o `web/dist` de novo**.

Local (PowerShell), na pasta `web/`:

```powershell
$env:VITE_SUPABASE_URL="https://SEU-REF.supabase.co"
$env:VITE_SUPABASE_ANON_KEY="a-chave-anon-publica"
npm run build
```

No Docker/Railway o mesmo valor entra como `ARG`/`ENV` **durante o build** da
imagem (veja `docs/HOSPEDAGEM.md`).

## Backend (API)

| Variável | Quando | Sem ela |
|---|---|---|
| `NEWPORT_MODO` | sempre | assume `demo` |
| `SUPABASE_URL` | `real` | **recusa subir** |
| `SUPABASE_JWT_SECRET` | opcional (JWT HS256 legado) | usa JWKS do Supabase |
| `BENEFITS_DONO_LEGADO_ID` | opcional | estudos antigos sem dono não são herdados |
| `NEWPORT_HOSTED` | `1` no Railway | modo real só aceita localhost |
| `NEWPORT_BIND_HOST` | hospedado: `0.0.0.0` | `127.0.0.1` |
| `NEWPORT_VOLUME_DIR` | hospedado | **recusa subir** se `NEWPORT_HOSTED=1` e também não houver `NEWPORT_PRIVATE_RUNTIME` |
| `NEWPORT_PRIVATE_RUNTIME` | real local | `.private/runtime` |
| `NEWPORT_DATA_DIR` | demo | `.data` |
| `NEWPORT_DOCS_DIR` | catálogos | `docs/` |
| `NEWPORT_WEB_DIST` | front compilado | `web/dist` |
| `NEWPORT_REDE_XLSX` | planilha SiscorNet | `docs/SiscorNet_….xlsx` |
| `NEWPORT_CORS_ORIGENS` | origens extras (vírgula) | só Vite `5173`/`5174` |
| `NEWPORT_UPLOAD_MAX_BYTES` | limite de upload | 10 MiB |

Com `NEWPORT_HOSTED=1` o backend **recusa**:

- `NEWPORT_MODO=demo`
- `SUPABASE_URL` vazia
- volume não apontado (`NEWPORT_VOLUME_DIR` ou `NEWPORT_PRIVATE_RUNTIME`)

## Front (`web/`)

| Variável | Quando | Sem ela |
|---|---|---|
| `VITE_SUPABASE_URL` | login real | tela de login cai em modo demonstração |
| `VITE_SUPABASE_ANON_KEY` | login real | cliente Supabase não liga |
| `VITE_FAIXA_RASCUNHO` | piloto (`1` / `true` / `sim`) | some a faixa **RASCUNHO INTERNO** |

## Robô no PC do corretor (`rpa/`, `127.0.0.1:8600`)

O site hospedado (HTTPS) chama o robô **na máquina do corretor** (HTTP).
Isso não é CORS entre front e API do Benefits (mesma origem). É CORS **do
navegador para o robô**.

| Variável / config | O quê |
|---|---|
| `tela.origens_permitidas` em `rpa/config.yaml` | localhost do Vite; acrescente o domínio HTTPS |
| `NEWPORT_RPA_ORIGENS` | extra, vírgula, ex. `https://benefits.up.railway.app` |
| Chrome / Edge | o site HTTPS pedirá **acesso à rede local**; o corretor precisa permitir. O robô já responde `Access-Control-Allow-Private-Network` no preflight. |

Exemplo no PC do corretor, antes de `python -m app`:

```powershell
$env:NEWPORT_RPA_ORIGENS="https://SEU-DOMINIO.up.railway.app"
```

Ou acrescente a mesma URL em `origens_permitidas` e `frame_ancestors` no
`config.yaml` local (não commitar domínio de produção no repositório).
