# Como publicar o Benefits 360 no Railway (piloto)

Este guia é para quem vai **ligar o piloto**. Não precisa programar.
**Ainda não publique** até o Tiago validar o código (esta branch não foi
mesclada nem enviada ao GitHub).

O Benefits no ar é **um único site** (tela + API juntos). Os estudos ficam
num **disco persistente** (volume). O robô de cotações continua no
**computador de cada corretor**.

Há **uma só instância**. Não aumente o número de réplicas: o banco SQLite
não aguenta duas ao mesmo tempo.

---

## O que você precisa ter em mãos

1. Conta na [Railway](https://railway.app) (o Leonardo cria, se ainda não houver).
2. O repositório Git **depois** do merge desta preparação (hoje isso ainda
   não foi feito).
3. No painel do **Supabase** (projeto Benefits):
   - URL do projeto (`https://xxxx.supabase.co`)
   - chave **anon** / *publishable* (pública)
   - **Nunca** a chave `service_role` / *secret*
4. Se forem aproveitar estudos já feitos no PC da Newport: os arquivos
   listados mais abaixo (bancos e pastas). Se o piloto começa vazio, ignore.

---

## 1. Criar o serviço

1. No Railway: **New project** → **Deploy from GitHub repo** (o repositório
   Newport, branch `master` **depois** do merge).
2. O Railway deve detectar o `Dockerfile` (já está no repositório, com
   `railway.toml`). Se perguntar o builder, escolha **Dockerfile**.
3. **Settings → Replicas / instances:** deixe **1**.
4. Ainda não abra o site para os corretores. Primeiro volume e variáveis.

---

## 2. Volume persistente (o “disco” dos estudos)

Sem volume, cada deploy **apaga** os estudos.

1. No serviço: **Volumes** → **Add volume**.
2. Caminho de montagem (mount path): `/data`
3. Tamanho sugerido no piloto pequeno: **5 GB** (dá para crescer depois).
   Os dados atuais da Newport, se copiados, passam de 1 GB.

Esse volume guarda: bancos SQLite, PDFs de cotação, planilhas SISCOR e o
HTML do estudo. **Não** guarda o robô (ele fica no PC).

---

## 3. Variáveis (Variables)

Cole no painel **Variables** do serviço. Sem aspas. Sem commit no Git.

| Nome | Valor | Obrigatória? |
|---|---|---|
| `NEWPORT_MODO` | `real` | sim |
| `NEWPORT_HOSTED` | `1` | sim |
| `NEWPORT_VOLUME_DIR` | `/data` | sim |
| `NEWPORT_BACKUP_DIR` | `/data/backups` | sim |
| `NEWPORT_BACKUP_RETENCAO_DIAS` | `14` | recomendada |
| `SUPABASE_URL` | `https://SEU-REF.supabase.co` | sim — **igual** à `VITE_SUPABASE_URL` |
| `VITE_SUPABASE_URL` | o mesmo `https://SEU-REF.supabase.co` | sim (entra no **build** da tela) |
| `VITE_SUPABASE_ANON_KEY` | a chave **anon** | sim (entra no **build**) |
| `VITE_FAIXA_RASCUNHO` | `1` | sim no piloto, até a Newport homologar os cálculos |
| `BENEFITS_DONO_LEGADO_ID` | UUID do usuário dono dos estudos antigos | só se forem copiar dados que existiam antes do login |
| `NEWPORT_CORS_ORIGENS` | `https://SEU-DOMINIO.up.railway.app` | depois que o domínio existir (veja §4) |

A Railway preenche `PORT` sozinha. Não invente porta.

**Proibido:** `SUPABASE_SERVICE_ROLE`, `service_role`, senhas de portal,
arquivos `.env.local`.

As variáveis que começam com `VITE_` são **assadas no JavaScript na hora do
build**. Se mudar a chave anon depois, **dispare um novo deploy** (Rebuild).
Só alterar a variável no painel **não** atualiza a tela.

---

## 4. Domínio HTTPS

1. **Settings → Networking → Generate domain** (fica
   `algo.up.railway.app`) **ou** ligue o domínio da Newport.
2. O HTTPS a plataforma entrega. Não compre certificado à parte.
3. Copie a URL `https://...` e coloque em `NEWPORT_CORS_ORIGENS`.
4. A mesma URL vai no robô de cada corretor (`NEWPORT_RPA_ORIGENS` — §8).

---

## 5. Build e primeiro deploy

1. **Deploy** (ou o primeiro já dispara ao conectar o Git).
2. Espere o build: primeiro a tela (`npm run build` com as `VITE_`), depois
   o Python. Demora alguns minutos.
3. Healthcheck: o Railway chama `/api/saude`. Se o serviço não subir, leia
   os **logs**. Mensagens típicas:
   - `NEWPORT_MODO=real e SUPABASE_URL não está definida`
   - `NEWPORT_HOSTED=1 exige NEWPORT_VOLUME_DIR`
   - `NEWPORT_HOSTED=1 não permite NEWPORT_MODO=demo`
4. Abra a URL do domínio. Deve aparecer a faixa vermelha
   **RASCUNHO INTERNO** e a tela de login do Supabase.
5. Crie **uma** conta de teste, entre, veja “Meus estudos”. Se o volume
   estava vazio, a lista começa vazia — isso é normal.

Nesta máquina de desenvolvimento o Docker **não estava instalado**; o
primeiro build real será o da Railway.

---

## 6. Como carregar dados no volume (opcional)

**Piloto do zero:** não copie nada. Os bancos nascem no `/data` no primeiro
uso.

**Levar estudos que já existem no PC da Newport:**

Copie **somente** isto para `/data/` (nomes do modo real):

- `estudos.db`
- `importacoes.db`
- `cotacoes.db`
- pasta `uploads/`
- pasta `cotacoes/` (PDFs)
- pasta `entregaveis/` (HTML)

**Não copie:** `.data/` (demo/teste), pastas `_tmp_*`, `.env.local`,
`rpa/saida`, PDFs de corpus de desenvolvimento.

Como copiar na prática (peça ajuda a quem tem o Railway CLI ou o painel):

1. Pare o serviço (Deployments → Remove / Pause) para o banco não estar
   aberto.
2. Envie os arquivos para o volume montado em `/data`.
3. Suba o serviço de novo.

Quem decide se a planilha SiscorNet e os CSVs de regras/PME/rede ficam **na
imagem** (já vão no Docker) ou **também no volume** (`NEWPORT_REDE_XLSX`) é
o Tiago / Leonardo. Padrão: **na imagem**.

---

## 7. Backup diário e restauração

Detalhes técnicos: `docs/BACKUP.md`.

### Agendar

1. No mesmo projeto Railway: **New** → **Cron job** (serviço agendado).
2. Mesma imagem do site, **mesmo volume** em `/data`.
3. Comando: `python -m newport_app.backup`
4. Agenda: `0 6 * * *` (06:00 UTC = 03:00 em Brasília).
5. Variáveis: `NEWPORT_MODO=real`, `NEWPORT_HOSTED=1`,
   `NEWPORT_VOLUME_DIR=/data`, `NEWPORT_BACKUP_DIR=/data/backups`.
   O cron **não** precisa das chaves `VITE_` nem de `SUPABASE_URL`.

De vez em quando baixe a pasta `/data/backups` para um disco da Newport.
Se a conta Railway for apagada, o volume some junto.

### Restaurar

1. **Pare** o site.
2. No volume, rode (trocando a data):

   `python -m newport_app.backup restaurar 2026-11-19`

3. Suba o site. Confira um estudo que vocês conheçam.

A restauração **já foi testada** em máquina local (os testes automatizados
apagaram os arquivos e o backup devolveu o conteúdo).

---

## 8. Robô no PC de cada corretor

O site na nuvem **não** emite cotação no portal. O robô continua em
`http://127.0.0.1:8600` no Windows do corretor.

1. O corretor deixa o robô ligado (janela preta / `python -m app`).
2. No PC dele, antes de subir o robô:

   `$env:NEWPORT_RPA_ORIGENS="https://SEU-DOMINIO.up.railway.app"`

   Ou acrescente essa URL em `origens_permitidas` no `config.yaml` **local**
   (não coloque domínio de produção no Git).
3. No **Chrome ou Edge**, a primeira vez que o site HTTPS falar com o
   localhost, o navegador pede **acesso à rede local**. O corretor deve
   **Permitir**. Sem isso a Cotações nativa não enxerga o robô.

---

## 9. Como reverter um deploy ruim

1. Railway → o serviço → **Deployments**.
2. Ache o deploy **anterior que funcionava**.
3. Os três pontinhos → **Rollback** (voltar).
4. Se o problema for **dado** (banco corrompido), rollback de código não
   resolve: use o **backup** (§7).
5. Se o problema for a faixa RASCUNHO ou o login: mude a variável
   (`VITE_FAIXA_RASCUNHO=0` some a faixa) e **Rebuild**, porque `VITE_` só
   vale no build.

Para desligar o piloto: **Settings → Pause** ou remova o domínio. O volume
continua até você apagá-lo.

---

## 10. Checklist rápido antes de chamar o corretor

- [ ] Uma instância só
- [ ] Volume em `/data`
- [ ] `NEWPORT_MODO=real` e `NEWPORT_HOSTED=1`
- [ ] `SUPABASE_URL` + `VITE_SUPABASE_*` (anon, nunca service_role)
- [ ] Faixa **RASCUNHO INTERNO** visível
- [ ] `/api/saude` responde ao abrir `https://SEU-DOMINIO/api/saude`
- [ ] Login cria sessão e “Meus estudos” abre
- [ ] Cron de backup ligado
- [ ] URL do site passada para o robô de cada PC
- [ ] Aviso ao corretor sobre “acesso à rede local” no Chrome/Edge

Mais detalhe de variáveis: `docs/VARIAVEIS-AMBIENTE.md`.  
O que vai no disco e o que não vai: `docs/INVENTARIO-RUNTIME-HOSPEDAGEM.md`.
