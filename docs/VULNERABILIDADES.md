# Auditoria de dependências (P9 — 2026-11-19)

Atualizado o que era **seguro** (sem `npm audit fix --force` e sem quebrar testes).
O que sobrou e por quê.

## npm (`web/`)

**Corrigido** (lockfile, sem `--force`): `nanoid` 3.3.20, `postcss` 8.5.33,
`source-map-js` 1.2.3.

**Ainda aberto (6):** o conserto pede Vite 6 / Vitest 4 (`npm audit fix --force`),
quebra de major. Não feito neste passo.

| Pacote | Gravidade | Onde | Por que ficou |
|---|---|---|---|
| `tinypool` (via `vitest`) | critical | só `npm test`, **não entra no `web/dist`** | upgrade = Vitest 4 |
| `@vitest/mocker` / `vitest` | moderate | testes | idem |
| `esbuild` / `vite` / `vite-node` | moderate | `vite` dev e build | advisory do **servidor de desenvolvimento** (`vite --host`); o piloto usa `npm run build` + API. Vite 6 é major |

No piloto hospedado o corretor **não** fala com o Vite; fala com o `dist` servido
pela API.

## pip (venv da API)

**Corrigido no ambiente e no `pyproject.toml` `[app]`:** `certifi>=2026.10.18`,
`pillow>=13`, `pypdf>=6.21.4`.

**Ainda aberto:** nenhum no `pip-audit` depois desses upgrades (a conferir no CI
local após o pytest). O pacote local `newport-motor` não está no PyPI — o
auditor ignora, esperado.
