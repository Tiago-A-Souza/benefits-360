# Recria o junction C:\np -> este repositório.
# Não copia arquivos. O apontador não sobrevive a formatação da máquina.
#
# Uso (PowerShell):
#   powershell -ExecutionPolicy Bypass -File scripts\recriar-junction-np.ps1
#
# Depois:  cd C:\np\web   e   npm run dev  /  npm run build

$ErrorActionPreference = "Stop"

function Get-RepoRealPath {
    $scripts = $PSScriptRoot
    $drive = $scripts.Substring(0, 2)
    $substLine = subst 2>$null | Where-Object { $_ -match "^$([regex]::Escape($drive))\\:" }
    if ($substLine -match "=>\s+(.+)$") {
        $mapped = $Matches[1].Trim()
        $rest = $scripts.Substring(2).TrimStart("\")
        if ($rest) {
            return (Join-Path $mapped $rest | Split-Path -Parent)
        }
        return $mapped
    }
    return (Resolve-Path (Join-Path $scripts "..")).Path
}

$repo = Get-RepoRealPath
$link = "C:\np"

Write-Host "Repositório: $repo"
Write-Host "Junction:    $link"

if (Test-Path $link) {
    $item = Get-Item $link -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        cmd /c "rmdir `"$link`""
        if (Test-Path $link) {
            throw "Não foi possível remover o junction existente em $link"
        }
    } else {
        throw "$link já existe e não é um junction. Remova manualmente."
    }
}

cmd /c "mklink /J `"$link`" `"$repo`""
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $link)) {
    throw "mklink /J falhou. Tente um PowerShell elevado."
}

Write-Host "OK. Frontend: cd C:\np\web"
Write-Host "API:         cd C:\np  e  .\.venv\Scripts\python.exe -m uvicorn ..."
