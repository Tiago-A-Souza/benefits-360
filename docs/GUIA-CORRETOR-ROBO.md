# Guia do corretor — robô local com o Benefits na nuvem

O site https://benefits-360-production.up.railway.app **não** emite cotação sozinho. O robô roda no **seu Windows**. O site da nuvem fala com o robô **REAL** em `http://127.0.0.1:8600`.

Há dois modos, em portas e pastas **separadas**. Misturar os dois era o que escondia as cotações reais.

| | Robô REAL | Modo TREINO (simulador) |
|---|---|---|
| Atalho | `rpa\Abrir Benefits Robo.bat` | `rpa\Treinar no simulador.bat` |
| Config | `config.yaml` | `config_simulador.yaml` |
| Porta | **8600** | **8601** |
| Pasta | `rpa\saida` (histórico de verdade) | `rpa\saida_simulador` |
| Site | nuvem (Railway) ou Benefits local | só Benefits local, apontando para 8601 |

O programa **recusa** subir `config_simulador.yaml` na porta 8600 e `config.yaml` na porta 8601, com mensagem em português. Só um robô por porta: o segundo atalho avisa e sai; **não** desliga o que já está no ar.

## 1. Instalar (uma vez)

1. Instale o **Python 3.11 ou mais novo** em https://www.python.org/downloads/  
   Marque **Add python.exe to PATH**.
2. Na pasta `rpa` do Benefits, dê dois cliques em **`instalar.bat`**.  
   Ele cria o ambiente, instala as bibliotecas e o Chromium do robô (não é o seu Chrome).

## 2. Ligar o robô REAL (todo dia de cotação)

1. Dê dois cliques em **`Abrir Benefits Robo.bat`**.
2. Deixe a janela preta **aberta**. Fechar a janela desliga o robô.
3. Este atalho **não** depende do Cursor: pode fechar o Cursor que o robô continua, enquanto a janela preta estiver aberta.
4. Log em `%LOCALAPPDATA%\NewportCotacoes\logs\robo-real.log`.
5. Origem padrão da nuvem: `https://benefits-360-production.up.railway.app` (variável `NEWPORT_RPA_ORIGENS` no atalho).

Não use `Abrir Newport Cotacoes.bat` para o site hospedado: aquele é o atalho de desenvolvimento local.

### Iniciar com o Windows (opcional — só ative se autorizar)

O script **não** cria a tarefa sozinho. Quando quiser:

1. PowerShell nesta pasta: `rpa\scripts\instalar-inicio-windows.ps1`  
   Cria a tarefa `NewportRoboReal` no **logon deste usuário** (não precisa ser administrador).
2. Para desligar: `rpa\scripts\remover-inicio-windows.ps1`  
   ou Agendador de Tarefas → apagar `NewportRoboReal`.

Enquanto a tarefa existir, ao entrar no Windows o robô REAL (8600) sobe sozinho. A janela preta aparece; não feche se for cotar.

## 3. Usar no navegador

1. Abra **Chrome ou Edge** (Safari costuma bloquear).
2. Entre em https://benefits-360-production.up.railway.app
3. Vá em **Cotações**.
4. Na primeira vez o navegador pede **acesso à rede local / loopback**: clique **Permitir**.

Em **Ajustes dos robôs** aparece o **caminho absoluto** da pasta de saída neste computador.

## 4. Login das operadoras

O CPF/senha do portal fica no **cofre do Windows** (Gerenciador de Credenciais), no seu usuário. Guarde uma vez na aba Cotações (Conexões). Nada disso vai para a nuvem.

## 5. Onde ficam os PDFs e o histórico

No PC: pasta **`rpa\saida`** (caminho completo na aba Ajustes e em `/api/estado`).  
Há um arquivo `tela.db` (lista da aba Cotações) e os PDFs por operadora.

Para o estudo no site, **envie o PDF** na etapa de cotações do estudo. O robô não grava sozinho no servidor.

**Se a aba Cotações disser que o robô está desligado:** o histórico **não foi perdido**. Ligue pelo atalho **Abrir Benefits Robo** e clique em Tentar de novo. O endereço tentado aparece na mensagem (`http://127.0.0.1:8600`).

## 6. Modo treino (simulador)

1. Dê dois cliques em **`Treinar no simulador.bat`** (porta **8601**, pasta `saida_simulador`).
2. No Benefits **local**, aponte o front para essa porta (`VITE_RPA_URL=http://127.0.0.1:8601`). O site da nuvem continua falando com a **8600** (cotações reais).
3. A aba Cotações mostra o aviso vermelho **ROBÔ EM MODO TREINO — não são as suas cotações reais**.
4. Log em `%LOCALAPPDATA%\NewportCotacoes\logs\robo-treino.log`.

Não use o atalho de treino no lugar do robô real. Não use `--porta 8600` com `config_simulador.yaml`.

## 7. Backup do histórico (não roda sozinho)

Script: `rpa\scripts\backup_historico.py`. Pastas padrão (também em `config.yaml`, seção `backup`):

- Diário: cópia consistente do `tela.db` (API de backup do SQLite) em `C:\Backups\rpa-tela\AAAA-MM-DD.sqlite`, retenção **14 dias só nessa pasta de backup**. **Nunca apaga** o `tela.db` original nem `rpa\saida`.
- Semanal: `robocopy /E` de `rpa\saida` para `C:\Backups\rpa-saida-semanal` **sem** `/MIR` e **sem** `/PURGE` (não apaga o destino).

Comandos, só quando autorizar:

```
cd rpa
.venv\Scripts\python.exe scripts\backup_historico.py --diario
.venv\Scripts\python.exe scripts\backup_historico.py --semanal
```

Nada disso entra no Agendador até você pedir.

## 8. Se a aba Cotações não enxergar o robô

- A janela do **Abrir Benefits Robo** está aberta? (porta 8600, `config.yaml`)
- Usou Chrome ou Edge e permitiu a rede local?
- Recarregue a página do site (Ctrl+F5).
- Confira se não ligou o **treino** no lugar do real (aviso vermelho, ou pasta `saida_simulador`).
- Se um segundo atalho abriu e fechou na hora: o primeiro já estava no ar — use aquele.
