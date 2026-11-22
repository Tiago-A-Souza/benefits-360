# Guia do corretor — robô local com o Benefits na nuvem

O site https://benefits-360-production.up.railway.app **não** emite cotação sozinho. O robô roda no **seu Windows** e o navegador fala com ele em `http://127.0.0.1:8600`.

## 1. Instalar (uma vez)

1. Instale o **Python 3.11 ou mais novo** em https://www.python.org/downloads/  
   Marque **Add python.exe to PATH**.
2. Na pasta `rpa` do Benefits, dê dois cliques em **`instalar.bat`**.  
   Ele cria o ambiente, instala as bibliotecas e o Chromium do robô (não é o seu Chrome).

## 2. Ligar o robô (todo dia de cotação)

1. Dê dois cliques em **`Abrir Benefits Robo.bat`**.
2. Deixe a janela preta **aberta**. Fechar a janela desliga o robô.
3. Este atalho **não** abre o Benefits local (`localhost:5173`). O site é o da nuvem.

Não use `Abrir Newport Cotacoes.bat` para o site hospedado: aquele é o atalho de desenvolvimento local.

## 3. Usar no navegador

1. Abra **Chrome ou Edge** (Safari costuma bloquear).
2. Entre em https://benefits-360-production.up.railway.app
3. Vá em **Cotações**.
4. Na primeira vez o navegador pede **acesso à rede local / loopback**: clique **Permitir**.

## 4. Login das operadoras

O CPF/senha do portal fica no **cofre do Windows** (Gerenciador de Credenciais), no seu usuário. Guarde uma vez na aba Cotações (Conexões). Nada disso vai para a nuvem.

## 5. Onde ficam os PDFs

No PC: pasta `rpa\saida` (por operadora).  
Para o estudo no site, **envie o PDF** na etapa de cotações do estudo. O robô não grava sozinho no servidor.

## 6. Se a aba Cotações não enxergar o robô

- A janela do bat está aberta?
- Usou Chrome ou Edge e permitiu a rede local?
- Recarregue a página do site (Ctrl+F5).
