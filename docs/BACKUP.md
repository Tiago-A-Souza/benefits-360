# Backup e restauração — Benefits 360

Os bancos SQLite **não** devem ser copiados com o arquivo aberto (`copy`,
Explorer, robocopy no `.db`). O comando abaixo usa a **API de backup do
SQLite** (`Connection.backup`) e depois copia as pastas de PDF e HTML.

## Fazer um backup agora

No servidor (mesmo volume da API):

```
python -m newport_app.backup
```

Cria `NEWPORT_BACKUP_DIR/<AAAA-MM-DD>/` com:

- `estudos.db`, `importacoes.db`, `cotacoes.db`
- pastas `uploads/`, `cotacoes/` (PDFs), `entregaveis/` (HTML)
- `MANIFEST.txt`

Padrão de pasta: `<dados>/backups`. No Railway: `NEWPORT_BACKUP_DIR=/data/backups`.
Guarda os últimos **14** dias (`NEWPORT_BACKUP_RETENCAO_DIAS`).

## Agendar na plataforma (Railway)

1. Crie um **Cron Job** (ou serviço agendado) **no mesmo projeto**.
2. Use a **mesma imagem** da API e o **mesmo volume** montado em `/data`.
3. Comando: `python -m newport_app.backup`
4. Agenda sugerida: `0 6 * * *` (06:00 UTC, 03:00 em Brasília).
5. Variáveis iguais às da API: `NEWPORT_MODO=real`, `NEWPORT_HOSTED=1`,
   `NEWPORT_VOLUME_DIR=/data`, `NEWPORT_BACKUP_DIR=/data/backups`.
   O cron **não** precisa de `SUPABASE_URL` (não sobe a API).

Copie também, de vez em quando, a pasta `/data/backups` para fora da Railway
(máquina da Newport ou outro disco). Volume sozinho não protege se a conta
for apagada.

## Restaurar

1. **Pare** o serviço da API (senão o banco volta a ser gravado por cima).
2. No volume:

```
python -m newport_app.backup restaurar 2026-11-19
```

Ou aponte a pasta:

```
python -m newport_app.backup restaurar /data/backups/2026-11-19 --destino /data
```

3. Suba a API de novo. Abra o site e confira um estudo conhecido.

## Restaurar na máquina local (teste)

Com o venv, modo demo isolado:

```
$env:NEWPORT_MODO="demo"
$env:NEWPORT_DATA_DIR="C:\caminho\de\teste"
.\.venv\Scripts\python.exe -m newport_app.backup
# apague ou altere um .db de teste, depois:
.\.venv\Scripts\python.exe -m newport_app.backup restaurar 2026-11-19
```

Os testes automatizados (`tests/test_backup_hospedagem.py`) fazem backup,
apagam os arquivos e conferem que a restauração devolve o conteúdo.
