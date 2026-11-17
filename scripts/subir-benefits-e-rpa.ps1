# Sobe Benefits (API 8002) e RPA Cotacoes (tela 8600, modo simulador) em processos separados.
# Uso (na raiz do repositorio):
#   powershell -ExecutionPolicy Bypass -File .\scripts\subir-benefits-e-rpa.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\subir-benefits-e-rpa.ps1 -SemSimulador
# Ctrl+C neste script encerra os dois.

param(
    [switch]$SemSimulador
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$pyBenefits = Join-Path $raiz ".venv\Scripts\python.exe"
$pyRpa = Join-Path $raiz "rpa\.venv\Scripts\python.exe"

if (-not (Test-Path $pyBenefits)) {
    Write-Error "Benefits: nao achei $pyBenefits. Crie o venv na raiz e instale as deps do Benefits."
}
if (-not (Test-Path $pyRpa)) {
    Write-Error "RPA: nao achei $pyRpa. Em rpa\, rode instalar.bat (ou python -m venv .venv + pip install -r requirements.txt + playwright install chromium)."
}

$jobs = @()

Write-Host "Benefits API -> http://127.0.0.1:8002"
$jobs += Start-Process -PassThru -NoNewWindow -WorkingDirectory $raiz -FilePath $pyBenefits -ArgumentList @(
    "-m", "uvicorn", "newport_app.api.main:app", "--host", "127.0.0.1", "--port", "8002"
)

# config_simulador.yaml usa porta 8601 por padrao (para nao colidir com a tela real).
# Aqui forcamos 8600 para o par Benefits+RPA ficar previsivel na maquina local.
$rpaArgs = @("-m", "app", "--porta", "8600", "--sem-navegador")
if (-not $SemSimulador) {
    $rpaArgs = @(
        "-m", "app",
        "--config", "config_simulador.yaml",
        "--porta", "8600",
        "--com-simulador",
        "--sem-navegador"
    )
    Write-Host "RPA Cotacoes (simulador) -> http://127.0.0.1:8600  (config_simulador.yaml + --porta 8600)"
} else {
    Write-Host "RPA Cotacoes -> http://127.0.0.1:8600  (config.yaml - portal real se emitir)"
}

$jobs += Start-Process -PassThru -NoNewWindow -WorkingDirectory (Join-Path $raiz "rpa") -FilePath $pyRpa -ArgumentList $rpaArgs

Write-Host ""
Write-Host "Os dois estao no ar. Ctrl+C neste terminal encerra ambos."
Write-Host "Frontend Vite (opcional): cd web; npm run dev  -> http://localhost:5173"
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
    Write-Host "Encerrado."
}
