# Cria a tarefa "NewportRoboReal" no início de sessão DESTE usuário.
# NÃO rode sem autorização do corretor.
# Desfazer: .\remover-inicio-windows.ps1
$ErrorActionPreference = "Stop"
$bat = (Resolve-Path (Join-Path $PSScriptRoot "..\Abrir Benefits Robo.bat")).Path
schtasks /Create /TN "NewportRoboReal" /TR "`"$bat`"" /SC ONLOGON /RL LIMITED /F
Write-Host "Tarefa NewportRoboReal criada. No próximo logon o robô REAL (8600) sobe sozinho."
Write-Host "Para desligar: rpa\scripts\remover-inicio-windows.ps1"
