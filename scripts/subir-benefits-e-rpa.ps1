# Sobe Benefits (API 8002 + Vite 5173) e o motor do robô (8600).
# A única interface é http://localhost:5173 (aba Cotações). A 8600 é só API.
# Uso (na raiz do repositorio):
#   powershell -ExecutionPolicy Bypass -File .\scripts\subir-benefits-e-rpa.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\subir-benefits-e-rpa.ps1 -SemSimulador
# Ctrl+C neste script encerra só o que ESTE script subiu (não derruba um robô que já estava na 8600).

param(
    [switch]$SemSimulador
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
# Login real (JWT) e dados em .private/runtime. O Python ainda lê C:\np\.env.local
# (SUPABASE_URL, BENEFITS_DONO_LEGADO_ID). Demo: $env:NEWPORT_MODO='demo' antes de chamar.
if (-not $env:NEWPORT_MODO) {
    $env:NEWPORT_MODO = "real"
}
$pyBenefits = Join-Path $raiz ".venv\Scripts\python.exe"
$pyRpa = Join-Path $raiz "rpa\.venv\Scripts\python.exe"
$npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source

if (-not (Test-Path $pyBenefits)) {
    Write-Error "Benefits: nao achei $pyBenefits. Crie o venv na raiz e instale as deps do Benefits."
}
if (-not (Test-Path $pyRpa)) {
    Write-Error "RPA: nao achei $pyRpa. Em rpa\, rode instalar.bat."
}
if (-not $npm) {
    Write-Error "Nao achei npm.cmd. Instale o Node.js para o Vite (porta 5173)."
}

function Get-Ouvinte {
    param([int]$Porta)
    $c = Get-NetTCPConnection -LocalPort $Porta -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $c) { return $null }
    $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
    $wmi = Get-CimInstance Win32_Process -Filter "ProcessId=$($c.OwningProcess)" -ErrorAction SilentlyContinue
    [pscustomobject]@{
        Porta = $Porta
        Pid   = $c.OwningProcess
        Nome  = if ($proc) { $proc.ProcessName } else { "?" }
        Linha = if ($wmi) { [string]$wmi.CommandLine } else { "" }
    }
}

function Test-EhRobo {
    param($Info)
    return ($Info.Linha -match '-m app' -or $Info.Linha -match '--porta 8600')
}

function Confirm-Encerrar {
    param($Info)
    Write-Host ""
    Write-Host ("Porta {0} ocupada por {1} (PID {2})" -f $Info.Porta, $Info.Nome, $Info.Pid)
    if ($Info.Linha) { Write-Host $Info.Linha }
    if ([Console]::IsInputRedirected) {
        Write-Host "Entrada nao interativa: mantenho o processo."
        return $false
    }
    $r = Read-Host "Encerrar esse processo? (s/n)"
    return ($r -eq "s" -or $r -eq "S")
}

function Resolve-Porta {
    param(
        [int]$Porta,
        [ValidateSet("rpa", "api", "vite")]
        [string]$Tipo
    )
    $info = Get-Ouvinte $Porta
    if (-not $info) {
        return "subir"
    }
    if ($Tipo -eq "rpa" -and (Test-EhRobo $info)) {
        Write-Host "robô já estava ligado (PID $($info.Pid)). Nao derrubo a API."
        return "reusar"
    }
    if (-not (Confirm-Encerrar $info)) {
        Write-Host ("Mantendo o processo da porta {0}." -f $Porta)
        return "reusar"
    }
    if ($Tipo -eq "rpa" -and (Test-EhRobo $info)) {
        Write-Host "robô já estava ligado. Nao derrubo a API."
        return "reusar"
    }
    Stop-Process -Id $info.Pid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 400
    return "subir"
}

$jobs = @()

$acao8002 = Resolve-Porta 8002 "api"
if ($acao8002 -eq "subir") {
    Write-Host ("Benefits API -> http://127.0.0.1:8002  (NEWPORT_MODO={0})" -f $env:NEWPORT_MODO)
    $jobs += Start-Process -PassThru -NoNewWindow -WorkingDirectory $raiz -FilePath $pyBenefits -ArgumentList @(
        "-m", "uvicorn", "newport_app.api.main:app", "--host", "127.0.0.1", "--port", "8002"
    )
} else {
    Write-Host "Benefits API ja estava em http://127.0.0.1:8002"
}

$rpaArgs = @("-m", "app", "--porta", "8600", "--sem-navegador")
if (-not $SemSimulador) {
    $rpaArgs = @(
        "-m", "app",
        "--config", "config_simulador.yaml",
        "--porta", "8600",
        "--com-simulador",
        "--sem-navegador"
    )
}

$acao8600 = Resolve-Porta 8600 "rpa"
if ($acao8600 -eq "subir") {
    if ($SemSimulador) {
        Write-Host "Motor do robo (config.yaml) -> http://127.0.0.1:8600  (so API; use a aba Cotacoes no Benefits)"
    } else {
        Write-Host "Motor do robo (simulador) -> http://127.0.0.1:8600  (so API; use a aba Cotacoes no Benefits)"
    }
    $jobs += Start-Process -PassThru -NoNewWindow -WorkingDirectory (Join-Path $raiz "rpa") -FilePath $pyRpa -ArgumentList $rpaArgs
}

$acao5173 = Resolve-Porta 5173 "vite"
if ($acao5173 -eq "subir") {
    Write-Host "Benefits (Vite) -> http://localhost:5173"
    $jobs += Start-Process -PassThru -NoNewWindow -WorkingDirectory (Join-Path $raiz "web") -FilePath $npm -ArgumentList @("run", "dev")
} else {
    Write-Host "Benefits (Vite) ja estava em http://localhost:5173"
}

$deadline = (Get-Date).AddSeconds(20)
do {
    $ok = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
    if ($ok) { break }
    Start-Sleep -Milliseconds 400
} while ((Get-Date) -lt $deadline)

Write-Host ""
Write-Host "Abrindo somente http://localhost:5173  (aba Cotacoes). Nao abra a 8600."
Start-Process "http://localhost:5173"

if ($jobs.Count -eq 0) {
    Write-Host "Nada novo para vigiar (servicos ja estavam no ar). Encerrando o script; os processos seguem."
    exit 0
}

Write-Host "Ctrl+C neste terminal encerra so o que este script subiu."
Write-Host ""

try {
    while ($true) {
        foreach ($p in $jobs) {
            if ($p.HasExited) {
                Write-Host "Processo PID $($p.Id) encerrou (exit $($p.ExitCode))."
                throw "Um dos servicos parou."
            }
        }
        Start-Sleep -Seconds 2
    }
} finally {
    foreach ($p in $jobs) {
        if (-not $p.HasExited) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "Encerrado o que este script subiu."
}
